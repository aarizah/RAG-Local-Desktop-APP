from pathlib import Path

import json

import pytest


@pytest.mark.skipif(not Path("tests/golden_set.jsonl").exists(), reason="golden set not present yet")
def test_golden_set_must_have_100_queries() -> None:
    lines = Path("tests/golden_set.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 100


@pytest.mark.skipif(not Path("tests/golden_set.jsonl").exists(), reason="golden set not present yet")
def test_golden_set_contract_fields() -> None:
    rows = [json.loads(line) for line in Path("tests/golden_set.jsonl").read_text(encoding="utf-8").strip().splitlines()]
    required = {"id", "query", "document_id", "content", "expected_citation"}
    for row in rows:
        assert required.issubset(row)
        assert row["expected_citation"].startswith(f"{row['document_id']}/")
