from pathlib import Path

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from transformers import AutoTokenizer


DEFAULT_PDF_PATH = (
    Path(__file__).resolve().parents[1]
    / "uploaded_documents"
    / "Acta_91695_201920733.pdf"
)

EMBED_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MAX_TOKENS = 2048


def pack_chunk_for_vector_store(chunk, chunk_id: int) -> dict:
    """Extract only lightweight, retrieval-friendly metadata."""
    meta = chunk.meta
    pages = sorted(
        {
            prov.page_no
            for item in (meta.doc_items or [])
            for prov in (item.prov or [])
            if prov.page_no is not None
        }
    )

    return {
        "chunk_id": chunk_id,
        "text": chunk.text,
        "metadata": {
            "source_file": meta.origin.filename if meta.origin else None,
            "headings": " / ".join(meta.headings or []),
            "pages": ",".join(str(page) for page in pages),
            "first_page": pages[0] if pages else None
        },
    }


def chunk_pdf_for_vector_store(pdf_path: str | Path) -> list[dict]:
    """Run Docling chunking pipeline for a PDF and return packed chunks."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"No existe el PDF esperado: {pdf_path}")

    converter = DocumentConverter()
    result = converter.convert(source=str(pdf_path))
    doc = result.document

    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL_ID)
    chunker = HybridChunker(
        tokenizer=tokenizer,
        max_tokens=MAX_TOKENS,
        merge_peers=True,
        merge_list_items=True,
    )

    chunks = list(chunker.chunk(doc))
    return [pack_chunk_for_vector_store(chunk, i) for i, chunk in enumerate(chunks)]


if __name__ == "__main__":
    packed_chunks = chunk_pdf_for_vector_store(DEFAULT_PDF_PATH)
    for packed in packed_chunks:
        print(f"\nChunk text: {packed['text'][:100]}...")
        print(f"Metadata esencial: {packed['metadata']}")

