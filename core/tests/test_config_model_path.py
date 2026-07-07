from pathlib import Path

from src.config import detect_default_gguf_model_path


def test_detect_default_gguf_model_path_returns_empty_when_no_models(tmp_path: Path) -> None:
    assert detect_default_gguf_model_path(tmp_path) == ""


def test_detect_default_gguf_model_path_picks_first_sorted_gguf(tmp_path: Path) -> None:
    second = tmp_path / "zeta-model.gguf"
    first = tmp_path / "alpha-model.gguf"
    second.write_bytes(b"z")
    first.write_bytes(b"a")

    detected = detect_default_gguf_model_path(tmp_path)
    assert detected == str(first.resolve())
