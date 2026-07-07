import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest
from starlette.responses import Response

from src.contracts import (
    ApiErrorV1,
    DocumentItemV1,
    DocumentListResponseV1,
    ErrorCode,
    IngestBatchResponseV1,
    IngestRequestV1,
    IngestResponseV1,
    QueryRequestV1,
    QueryResponseV1,
)
from src.config import get_settings
from src.rag.generation import GenerationError
from src.rag.ingestion import DuplicateDocumentError, IngestionService
from src.observability import (
    CITATION_COVERAGE,
    GENERATION_MS,
    RETRIEVAL_MS,
    RERANK_MS,
    TOTAL_MS,
    get_logger,
    redact_pii,
    timed_stage,
)
from src.rag.rerank import Reranker
from src.rag.retrieval import RetrievalService

# ui/dist/ lives two levels above core/src/
_UI_DIST = Path(__file__).resolve().parent.parent.parent / "ui" / "dist"


def create_app(
    *,
    ingestion_service: IngestionService,
    retrieval_service: RetrievalService,
    reranker: Reranker,
    generation_service: object,
) -> FastAPI:
    if not hasattr(generation_service, "generate"):
        raise TypeError("generation_service must provide a generate() method")

    app = FastAPI(title="Local RAG", version="1.0.0")
    logger = get_logger()
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Ingestion ──────────────────────────────────────────────────────────────

    @app.post("/v1/ingest", response_model=IngestBatchResponseV1)
    def ingest(req: IngestRequestV1):
        try:
            return ingestion_service.ingest(req)
        except DuplicateDocumentError as exc:
            error = ApiErrorV1(code=ErrorCode.DUPLICATE_DOCUMENT, message=str(exc))
            raise HTTPException(status_code=409, detail=error.model_dump()) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/upload", response_model=IngestResponseV1)
    async def upload(file: UploadFile = File(...)):
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")

        dest = ingestion_service.s3_dir / file.filename
        content = await file.read()
        dest.write_bytes(content)

        req = IngestRequestV1(source_path=file.filename)
        try:
            batch = ingestion_service.ingest(req)
            return batch.results[0]
        except DuplicateDocumentError as exc:
            error = ApiErrorV1(code=ErrorCode.DUPLICATE_DOCUMENT, message=str(exc))
            raise HTTPException(status_code=409, detail=error.model_dump()) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ── Documents ──────────────────────────────────────────────────────────────

    @app.get("/v1/documents", response_model=DocumentListResponseV1)
    def list_documents():
        rows = ingestion_service.list_documents()
        items = [
            DocumentItemV1(
                document_id=row["document_id"],
                version=row["version"],
                source_file=Path(row["source_path"]).name,
                content_hash=row["content_hash"],
                status=row["status"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return DocumentListResponseV1(documents=items, total=len(items))

    # ── Query ──────────────────────────────────────────────────────────────────

    @app.post("/v1/query", response_model=QueryResponseV1)
    def query(req: QueryRequestV1):
        candidate_k = settings.rag_candidate_k
        rerank_k = settings.rag_rerank_k
        final_k = settings.rag_final_k
        correlation_id = str(uuid.uuid4())
        with timed_stage(TOTAL_MS) as total:
            with timed_stage(RETRIEVAL_MS) as retrieval:
                candidates = retrieval_service.retrieve(query=req.query, candidate_k=candidate_k)
            with timed_stage(RERANK_MS) as rerank:
                ranked = reranker.rerank(candidates, rerank_k, final_k, query=req.query)
            contexts = [(chunk.ref, chunk.text) for chunk in ranked]
            try:
                with timed_stage(GENERATION_MS) as generation:
                    answer = generation_service.generate(
                        question=req.query,
                        contexts=contexts,
                        correlation_id=correlation_id,
                    )
            except GenerationError as exc:
                error = ApiErrorV1(code=exc.code, message=str(exc), correlation_id=correlation_id)
                raise HTTPException(status_code=500, detail=error.model_dump()) from exc

        citations = [chunk.ref.citation for chunk in ranked]
        CITATION_COVERAGE.labels(has_citation=str(bool(citations)).lower()).inc()
        logger.info(
            "query_completed",
            correlation_id=correlation_id,
            candidate_k=candidate_k,
            rerank_k=rerank_k,
            final_k=final_k,
            status="ok",
            query=redact_pii(req.query),
            citations=len(citations),
            retrieval_ms=round(retrieval["ms"], 3),
            rerank_ms=round(rerank["ms"], 3),
            generation_ms=round(generation["ms"], 3),
            total_ms=round(total["ms"], 3),
        )
        return QueryResponseV1(
            answer=answer,
            citations=citations,
            retrieved_chunks=ranked,
            chunks=[c.ref for c in ranked],
            correlation_id=correlation_id,
            total_ms=round(total["ms"], 3),
        )

    # ── Metrics ────────────────────────────────────────────────────────────────

    @app.get("/metrics")
    def metrics():
        return Response(content=generate_latest(), media_type="text/plain")

    # ── SPA static serving (production) ────────────────────────────────────────
    # Must be last so API routes take precedence.

    if _UI_DIST.exists():
        app.mount("/", StaticFiles(directory=str(_UI_DIST), html=True), name="static")

    return app
