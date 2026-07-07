from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from src.contracts import ChunkRefV1, RetrievedChunkV1


class SqliteFtsRepository:
    def __init__(self, db_path: str, table_name: str = "chunks_fts", tokenizer: str = "unicode61"):
        self.db_path = db_path
        self.table_name = table_name
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {self.table_name}
                USING fts5(
                    chunk_uid UNINDEXED,
                    document_id UNINDEXED,
                    version UNINDEXED,
                    chunk_id UNINDEXED,
                    source_path UNINDEXED,
                    source_file UNINDEXED,
                    pages_json UNINDEXED,
                    first_page UNINDEXED,
                    headings_json UNINDEXED,
                    text,
                    tokenize='{tokenizer}'
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert_chunk(self, *, ref: ChunkRefV1, text: str) -> None:
        chunk_uid = f"{ref.document_id}:{ref.version}:{ref.chunk_id}"
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {self.table_name} WHERE chunk_uid = ?", (chunk_uid,))
            conn.execute(
                f"""
                INSERT INTO {self.table_name}(
                    chunk_uid, document_id, version, chunk_id, source_path, source_file,
                    pages_json, first_page, headings_json, text
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_uid,
                    ref.document_id,
                    ref.version,
                    ref.chunk_id,
                    ref.source_path,
                    ref.source_file,
                    json.dumps(ref.pages) if ref.pages is not None else None,
                    ref.first_page,
                    json.dumps(ref.headings, ensure_ascii=False) if ref.headings is not None else None,
                    text,
                ),
            )

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Strip FTS5 special characters so raw natural-language queries don't crash the parser."""
        tokens = re.sub(r"[^\w\s]", " ", query, flags=re.UNICODE).split()
        return " ".join(tokens) if tokens else '""'

    def search(self, query: str, limit: int = 10) -> list[RetrievedChunkV1]:
        fts_query = self._sanitize_fts_query(query)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    document_id, version, chunk_id, source_path, source_file,
                    pages_json, first_page, headings_json, text,
                    bm25({self.table_name}) AS score
                FROM {self.table_name}
                WHERE {self.table_name} MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()

        return [
            RetrievedChunkV1(
                ref=ChunkRefV1(
                    document_id=row["document_id"],
                    version=int(row["version"]),
                    chunk_id=row["chunk_id"],
                    source_path=row["source_path"],
                    source_file=row["source_file"],
                    pages=json.loads(row["pages_json"]) if row["pages_json"] else None,
                    first_page=(int(row["first_page"]) if row["first_page"] is not None else None),
                    headings=json.loads(row["headings_json"]) if row["headings_json"] else None,
                ),
                text=row["text"],
                score=float(-row["score"]),
            )
            for row in rows
        ]
