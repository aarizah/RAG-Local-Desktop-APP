from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from src.rag.chunking import ChunkingPort
from src.contracts import ChunkRefV1, IngestBatchResponseV1, IngestRequestV1, IngestResponseV1
from src.rag.embedding import EmbeddingPort
from src.stores.lexical_store import SqliteFtsRepository
from src.stores.vector_store import VectorRecord, VectorStorePort


class DuplicateDocumentError(ValueError):
    def __init__(self, duplicate_hashes: list[str]):
        hashes = ", ".join(sorted(set(duplicate_hashes)))
        super().__init__(f"Document already exists for content hash(es): {hashes}")
        self.duplicate_hashes = sorted(set(duplicate_hashes))


class IngestionService:
    def __init__(
        self,
        *,
        sqlite_path: str,
        chunker: ChunkingPort,
        embedding: EmbeddingPort,
        vector_store: VectorStorePort,
        lexical_store: SqliteFtsRepository,
        s3_dir: str,
    ):
        self.sqlite_path = sqlite_path
        self.chunker = chunker
        self.embedding = embedding
        self.vector_store = vector_store
        self.lexical_store = lexical_store
        self.s3_dir = Path(s3_dir).resolve()
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        self.s3_dir.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(document_id, version)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_at TEXT NOT NULL,
                    details TEXT
                )
                """
            )

    @staticmethod
    def _sha256_file(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as file:
            while True:
                block = file.read(1024 * 1024)
                if not block:
                    break
                hasher.update(block)
        return hasher.hexdigest()

    def _resolve_source_path(self, source_path: str) -> Path:
        candidate = Path(source_path)
        if candidate.is_absolute():
            raise ValueError("source_path must be relative to s3")

        full_path = (self.s3_dir / candidate).resolve()
        if full_path != self.s3_dir and self.s3_dir not in full_path.parents:
            raise ValueError("source_path points outside s3")
        if full_path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files are supported for ingestion")
        if not full_path.exists() or not full_path.is_file():
            raise ValueError(f"Source file not found: {source_path}")
        return full_path

    def _ingest_one(self, *, document_id: str, resolved_path: Path, content_hash: str) -> IngestResponseV1:
        version = 1

        chunks = self.chunker.chunk(
            document_id=document_id,
            version=version,
            source_path=str(resolved_path),
        )
        embeddings = self.embedding.embed_documents([chunk.text for chunk in chunks])

        records: list[VectorRecord] = []
        for chunk, vector in zip(chunks, embeddings, strict=False):
            ref = ChunkRefV1(
                document_id=chunk.document_id,
                version=chunk.version,
                chunk_id=chunk.chunk_id,
                source_path=chunk.source_path,
                source_file=chunk.source_file,
                pages=chunk.pages,
                first_page=chunk.first_page,
                headings=chunk.headings,
            )
            records.append(VectorRecord(ref=ref, text=chunk.text, embedding=vector))
            self.lexical_store.upsert_chunk(ref=ref, text=chunk.text)

        self.vector_store.upsert(records)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents(document_id, version, content_hash, source_path, status, created_at)
                VALUES(?, ?, ?, ?, 'indexed', datetime('now'))
                """,
                (document_id, version, content_hash, str(resolved_path)),
            )

        return IngestResponseV1(
            document_id=document_id,
            version=version,
            status="indexed",
            content_hash=content_hash,
            chunks_indexed=len(chunks),
        )

    def ingest(self, req: IngestRequestV1) -> IngestBatchResponseV1:
        resolved_files: list[tuple[str, Path, str]] = []
        for source_path in req.files:
            resolved_path = self._resolve_source_path(source_path)
            content_hash = self._sha256_file(resolved_path)
            resolved_files.append((source_path, resolved_path, content_hash))

        seen_hashes: set[str] = set()
        duplicated_in_batch: set[str] = set()
        for _, _, content_hash in resolved_files:
            if content_hash in seen_hashes:
                duplicated_in_batch.add(content_hash)
            seen_hashes.add(content_hash)
        if duplicated_in_batch:
            raise DuplicateDocumentError(duplicate_hashes=list(duplicated_in_batch))

        content_hashes = [content_hash for _, _, content_hash in resolved_files]
        placeholders = ", ".join("?" for _ in content_hashes)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT content_hash FROM documents WHERE content_hash IN ({placeholders})",
                tuple(content_hashes),
            ).fetchall()
        duplicated_in_db = [str(row["content_hash"]) for row in rows]
        if duplicated_in_db:
            raise DuplicateDocumentError(duplicate_hashes=duplicated_in_db)

        results = [
            self._ingest_one(
                document_id=content_hash,
                resolved_path=resolved_path,
                content_hash=content_hash,
            )
            for _, resolved_path, content_hash in resolved_files
        ]
        return IngestBatchResponseV1(results=results)

    def list_documents(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT document_id, version, source_path, content_hash, status, created_at
                FROM documents
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]
