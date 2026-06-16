from __future__ import annotations

import time
from dataclasses import dataclass

from mafia.models.provider_types import GenerationResult


APP_NAME = "mafia-gemma4-inference"


@dataclass(slots=True)
class ModalModelClient:
    class_name: str
    model_label: str
    app_name: str = APP_NAME

    @classmethod
    def mafia_bf16(cls) -> "ModalModelClient":
        return cls("MergedBF16Model", "Alfaxad/mafia-gemma-4-12B-it")

    @classmethod
    def base_moderator_bf16(cls) -> "ModalModelClient":
        return cls("BaseBF16Model", "google/gemma-4-12B-it")

    @classmethod
    def gguf_q8(cls) -> "ModalModelClient":
        return cls("GGUFQ8Model", "Alfaxad/mafia-gemma-4-12B-it-gguf")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 192,
        temperature: float = 1.0,
        top_p: float = 0.95,
        top_k: int = 64,
    ) -> GenerationResult:
        started = time.perf_counter()
        try:
            import modal
        except Exception as exc:  # pragma: no cover - modal may not be installed in CI/dev.
            raise RuntimeError("Modal is required for model-backed inference.") from exc

        remote_cls = modal.Cls.from_name(self.app_name, self.class_name)
        instance = remote_cls()
        result = instance.generate.remote(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
        )
        return GenerationResult(
            text=str(result.get("text", "")),
            backend=str(result.get("backend", "modal")),
            model=str(result.get("model", self.model_label)),
            latency_seconds=float(result.get("latency_seconds", time.perf_counter() - started)),
            prompt_tokens=result.get("prompt_tokens"),
            completion_tokens=result.get("completion_tokens"),
            raw=result,
        )
