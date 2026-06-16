from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class GenerationResult:
    text: str
    backend: str
    model: str
    latency_seconds: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw: dict | None = None


class TextProvider(Protocol):
    def generate(
        self,
        prompt: str,
        max_tokens: int = 192,
        temperature: float = 1.0,
        top_p: float = 0.95,
        top_k: int = 64,
    ) -> GenerationResult:
        ...
