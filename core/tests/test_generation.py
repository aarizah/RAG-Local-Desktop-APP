import pytest

from src.rag.generation import LlamaCppGenerationAdapter


def test_generation_requires_model_path() -> None:
    with pytest.raises(ValueError):
        LlamaCppGenerationAdapter(
            model_path="",
            n_ctx=2048,
            n_threads=2,
            n_gpu_layers=0,
            max_tokens=128,
            temperature=0.2,
        )
