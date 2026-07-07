from datetime import datetime

from tests.fakes.chunking import SimpleChunkingAdapter


def test_chunking_generates_required_metadata_and_unique_ids(tmp_path) -> None:
    chunker = SimpleChunkingAdapter(max_chars=40, overlap=5)
    content = "chunking valido con metadatos obligatorios " * 8
    source = tmp_path / "doc-meta.txt"
    source.write_text(content, encoding="utf-8")

    chunks = chunker.chunk(
        document_id="doc-meta",
        version=3,
        source_path=str(source),
    )

    assert len(chunks) > 1

    ids = {chunk.chunk_id for chunk in chunks}
    assert len(ids) == len(chunks)

    for chunk in chunks:
        assert chunk.document_id == "doc-meta"
        assert chunk.version == 3
        assert chunk.source_path == str(source)
        assert chunk.source_file == "doc-meta.txt"
        assert chunk.pages is None
        assert chunk.first_page is None
        assert chunk.headings is None
        assert chunk.chunk_id.startswith("v3-c")
        assert chunk.text
        parsed = datetime.fromisoformat(chunk.created_at)
        assert parsed.tzinfo is not None
