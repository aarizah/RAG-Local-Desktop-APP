from __future__ import annotations

from src.contracts import ChunkRefV1, ErrorCode

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover
    Llama = None


class GenerationError(RuntimeError):
    def __init__(self, message: str, correlation_id: str):
        super().__init__(message)
        self.code = ErrorCode.GENERATION_FAILED
        self.correlation_id = correlation_id


class LlamaCppGenerationAdapter:
    def __init__(
        self,
        *,
        model_path: str,
        n_ctx: int,
        n_threads: int,
        n_gpu_layers: int,
        max_tokens: int,
        temperature: float,
    ):
        if not model_path:
            raise ValueError("LLAMACPP_MODEL_PATH is required")
        if Llama is None:
            raise RuntimeError("llama-cpp-python is not installed")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )

    def generate(self, *, question: str, contexts: list[tuple[ChunkRefV1, str]], correlation_id: str) -> str:
        evidence = "\n".join(
            f"- [{ref.citation}] {text[:400]}" for ref, text in contexts
        )
        system_prompt = (
            "Eres un asistente que responde preguntas basándose ÚNICAMENTE en el contexto proporcionado. "
            "Sé muy conciso. Si el dato solicitado aparece en el contexto, extráelo y respóndelo directamente. "
            "Solo di 'No tengo suficiente evidencia para responder' si el dato realmente no está en el contexto."
        )
        user_prompt = f"Contexto:\n{evidence}\n\nPregunta: {question}"

        try:
            output = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return output["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # pragma: no cover
            raise GenerationError(str(exc), correlation_id) from exc
