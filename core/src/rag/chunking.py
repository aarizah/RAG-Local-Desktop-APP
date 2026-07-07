from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


@dataclass(slots=True)
class Chunk:
    document_id: str
    version: int
    chunk_id: str
    source_path: str
    source_file: str
    pages: list[int] | None
    first_page: int | None
    headings: list[str] | None
    created_at: str
    text: str


class ChunkingPort(Protocol):
    def chunk(self, *, document_id: str, version: int, source_path: str) -> list[Chunk]: ...


class DoclingPdfChunkingAdapter:
    def __init__(
        self,
        *,
        tokenizer_model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
        max_tokens: int = 256,
    ):
        try:
            from docling.chunking import HybridChunker
            from docling.document_converter import DocumentConverter
            from transformers import AutoTokenizer
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "DoclingPdfChunkingAdapter requires optional dependencies: docling and transformers"
            ) from exc

        self.converter = DocumentConverter()
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_model_id)
        self.chunker: Any = HybridChunker(
            tokenizer=tokenizer,
            max_tokens=max_tokens,
            merge_peers=True,
            merge_list_items=True,
        )

    @staticmethod
    def _extract_pages(meta: object | None) -> list[int] | None:
        if meta is None:
            return None

        pages: set[int] = set()
        for item in getattr(meta, "doc_items", []) or []:
            prov = getattr(item, "prov", None) or []
            for source in prov:
                page_no = getattr(source, "page_no", None)
                if isinstance(page_no, int):
                    pages.add(page_no)

        if not pages:
            return None
        return sorted(pages)

    @staticmethod
    def _extract_headings(meta: object | None) -> list[str] | None:
        if meta is None:
            return None
        headings = getattr(meta, "headings", None)
        if not headings:
            return None
        values = [str(h).strip() for h in headings if str(h).strip()]
        return values or None

    def chunk(self, *, document_id: str, version: int, source_path: str) -> list[Chunk]:
        result = self.converter.convert(source=str(source_path))
        document = getattr(result, "document", result)
        created_at = datetime.now(timezone.utc).isoformat()

        chunks: list[Chunk] = []
        for idx, raw_chunk in enumerate(self.chunker.chunk(document), start=1):
            text = str(getattr(raw_chunk, "text", "")).strip()
            if not text:
                continue

            meta = getattr(raw_chunk, "meta", None)
            pages = self._extract_pages(meta)
            headings = self._extract_headings(meta)
            chunks.append(
                Chunk(
                    document_id=document_id,
                    version=version,
                    chunk_id=f"v{version}-c{idx:04d}",
                    source_path=source_path,
                    source_file=Path(source_path).name,
                    pages=pages,
                    first_page=min(pages) if pages else None,
                    headings=headings,
                    created_at=created_at,
                    text=text,
                )
            )

        return chunks
