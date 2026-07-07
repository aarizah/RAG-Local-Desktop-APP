from pathlib import Path

import pytest

from tests.e2e_eval_runner import run_e2e_evaluation


@pytest.mark.skipif(not Path("tests/golden_set.jsonl").exists(), reason="golden set not present yet")
def test_e2e_metrics_meet_slo_and_quality_targets(tmp_path: Path) -> None:
    report = run_e2e_evaluation(
        golden_set_path=Path("tests/golden_set.jsonl"),
        workdir=tmp_path,
    )

    assert report.evaluated_queries == 100
    assert report.p50_total_ms <= 2500
    assert report.p95_total_ms <= 6000
    assert report.recall_at_5 >= 0.75
    assert report.citation_coverage == 1.0

    assert report.p50_retrieval_ms >= 0
    assert report.p95_retrieval_ms >= 0
    assert report.p50_rerank_ms >= 0
    assert report.p95_rerank_ms >= 0
    assert report.p50_generation_ms >= 0
    assert report.p95_generation_ms >= 0
