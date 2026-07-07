from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol

from src.contracts import ChunkRefV1, RetrievedChunkV1

try:
    import chromadb
except ImportError:  # pragma: no cover - runtime guarded
    chromadb = None


@dataclass(slots=True)
class VectorRecord:
    ref: ChunkRefV1
    text: str
    embedding: list[float]


class VectorStorePort(Protocol):
    def upsert(self, records: list[VectorRecord]) -> None: ...

    def search(self, query_embedding: list[float], limit: int) -> list[RetrievedChunkV1]: ...


class ChromaVectorRepository:
    def __init__(self, *, persist_dir: str, collection_name: str, distance: str = "cosine"):
        if chromadb is None:
            raise RuntimeError("chromadb is not installed")

        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": distance},
        )

    def upsert(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        self.collection.upsert(
            ids=[f"{record.ref.document_id}:{record.ref.chunk_id}" for record in records],
            documents=[record.text for record in records],
            embeddings=[record.embedding for record in records],
            metadatas=[
                {
                    "document_id": record.ref.document_id,
                    "version": record.ref.version,
                    "chunk_id": record.ref.chunk_id,
                    "source_path": record.ref.source_path,
                    "source_file": record.ref.source_file,
                    "pages": json.dumps(record.ref.pages) if record.ref.pages is not None else None,
                    "first_page": record.ref.first_page,
                    "headings": (
                        json.dumps(record.ref.headings, ensure_ascii=False)
                        if record.ref.headings is not None
                        else None
                    ),
                }
                for record in records
            ],
        )

    def search(self, query_embedding: list[float], limit: int) -> list[RetrievedChunkV1]:
        result = self.collection.query(query_embeddings=[query_embedding], n_results=limit)
        docs = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        chunks: list[RetrievedChunkV1] = []
        for doc, metadata, distance in zip(docs, metadatas, distances, strict=False):
            ref = ChunkRefV1(
                document_id=metadata["document_id"],
                version=int(metadata["version"]),
                chunk_id=metadata["chunk_id"],
                source_path=metadata["source_path"],
                source_file=metadata.get("source_file"),
                pages=json.loads(metadata["pages"]) if metadata.get("pages") else None,
                first_page=(int(metadata["first_page"]) if metadata.get("first_page") else None),
                headings=json.loads(metadata["headings"]) if metadata.get("headings") else None,
            )
            chunks.append(RetrievedChunkV1(ref=ref, text=doc, score=1.0 - float(distance)))
        return chunks
