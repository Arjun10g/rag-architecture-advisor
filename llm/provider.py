from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LLMProvider:
    name: str
    model: str | None = None

    def generate(self, prompt: str) -> str:
        return f"[{self.name}] generation placeholder for: {prompt[:120]}"


def get_provider() -> LLMProvider:
    return LLMProvider(
        name=os.getenv("LLM_PROVIDER", "hf"),
        model=os.getenv("HF_INFERENCE_MODEL") or None,
    )

