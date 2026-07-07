from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    GENERATION_FAILED = "GENERATION_FAILED"
    INGESTION_FAILED = "INGESTION_FAILED"
    DUPLICATE_DOCUMENT = "DUPLICATE_DOCUMENT"


class ApiErrorV1(BaseModel):
    code: ErrorCode
    message: str
    correlation_id: str | None = None


class ChunkRefV1(BaseModel):
    document_id: str
    version: int = Field(ge=1)
    chunk_id: str
    source_path: str
    source_file: str | None = None
    pages: list[int] | None = None
    first_page: int | None = None
    headings: list[str] | None = None

    @property
    def citation(self) -> str:
        return f"{self.document_id}/{self.chunk_id}"


class RetrievedChunkV1(BaseModel):
    ref: ChunkRefV1
    text: str
    score: float = 0.0


class QueryRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)


class QueryResponseV1(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunkV1] = Field(default_factory=list)
    """Compatibilidad con clientes antiguos: mismas refs que en cada ítem de retrieved_chunks."""
    chunks: list[ChunkRefV1] = Field(default_factory=list)
    correlation_id: str
    total_ms: float = 0.0


class IngestRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str | None = None
    source_paths: list[str] | None = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> "IngestRequestV1":
        has_single = bool(self.source_path and self.source_path.strip())
        has_many = bool(self.source_paths)

        if has_single and has_many:
            raise ValueError("Provide source_path or source_paths, not both")
        if not has_single and not has_many:
            raise ValueError("At least one source path is required")

        if self.source_paths is not None and len(self.source_paths) == 0:
            raise ValueError("source_paths cannot be empty")
        return self

    @property
    def files(self) -> list[str]:
        if self.source_paths:
            return self.source_paths
        return [self.source_path] if self.source_path else []


class IngestResponseV1(BaseModel):
    document_id: str
    version: int
    status: str
    content_hash: str
    created_at: datetime = Field(default_factory=utc_now)
    chunks_indexed: int = 0


class IngestBatchResponseV1(BaseModel):
    results: list[IngestResponseV1] = Field(default_factory=list)


class DocumentItemV1(BaseModel):
    document_id: str
    version: int
    source_file: str
    content_hash: str
    status: str
    created_at: str


class DocumentListResponseV1(BaseModel):
    documents: list[DocumentItemV1] = Field(default_factory=list)
    total: int = 0
