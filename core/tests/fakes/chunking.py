from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.rag.chunking import Chunk


class SimpleChunkingAdapter:
    """Fake chunker for tests that don't need Docling runtime."""

    def __init__(self, max_chars: int = 900, overlap: int = 120):
        self.max_chars = max_chars
        self.overlap = overlap

    def chunk(self, *, document_id: str, version: int, source_path: str) -> list[Chunk]:
        content = Path(source_path).read_text(encoding="utf-8").strip()
        if not content:
            return []

        created_at = datetime.now(timezone.utc).isoformat()
        parts: list[str] = []
        start = 0
        while start < len(content):
            end = min(start + self.max_chars, len(content))
            parts.append(content[start:end])
            if end == len(content):
                break
            start = max(0, end - self.overlap)

        return [
            Chunk(
                document_id=document_id,
                version=version,
                chunk_id=f"v{version}-c{idx:04d}",
                source_path=source_path,
                source_file=Path(source_path).name,
                pages=None,
                first_page=None,
                headings=None,
                created_at=created_at,
                text=part,
            )
            for idx, part in enumerate(parts, start=1)
        ]
