from __future__ import annotations

import re
import time
from contextlib import contextmanager
from typing import Iterator

import structlog
from prometheus_client import Counter, Histogram


PII_PATTERN = re.compile(r"\b\d{8,}\b")

RETRIEVAL_MS = Histogram("retrieval_ms", "Latency retrieval stage")
RERANK_MS = Histogram("rerank_ms", "Latency rerank stage")
GENERATION_MS = Histogram("generation_ms", "Latency generation stage")
TOTAL_MS = Histogram("total_ms", "Latency full query")
CITATION_COVERAGE = Counter("citation_coverage", "Responses with citations", ["has_citation"])


def configure_logging(json_logs: bool = True) -> None:
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(processors=processors)


def get_logger():
    return structlog.get_logger()


def redact_pii(text: str) -> str:
    return PII_PATTERN.sub("[REDACTED]", text)


@contextmanager
def timed_stage(histogram: Histogram) -> Iterator[dict[str, float]]:
    start = time.perf_counter()
    payload = {"ms": 0.0}
    try:
        yield payload
    finally:
        payload["ms"] = (time.perf_counter() - start) * 1000
        histogram.observe(payload["ms"])
