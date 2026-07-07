import pytest
from pydantic import ValidationError

from src.contracts import IngestRequestV1, QueryRequestV1


def test_query_request_accepts_only_query() -> None:
    model = QueryRequestV1(query="hola")
    assert model.query == "hola"


def test_query_request_rejects_client_k_overrides() -> None:
    with pytest.raises(ValidationError):
        QueryRequestV1(query="hola", final_k=1)


def test_ingest_request_rejects_inline_content() -> None:
    with pytest.raises(ValidationError):
        IngestRequestV1(source_path="a.pdf", content="no permitido")


def test_ingest_request_rejects_document_id_from_client() -> None:
    with pytest.raises(ValidationError):
        IngestRequestV1(document_id="doc-1", source_path="a.pdf")


def test_ingest_request_accepts_multiple_pdf_paths() -> None:
    payload = IngestRequestV1(
        source_paths=["a.pdf", "b.pdf"],
    )
    assert payload.files == ["a.pdf", "b.pdf"]
