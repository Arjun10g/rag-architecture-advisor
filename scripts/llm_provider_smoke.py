from __future__ import annotations

import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["LLM_PROVIDER"] = "disabled"

from graph.build import build_graph
from llm.provider import GenerationConfig, LLMProviderUnavailable, _extract_chat_content, get_provider


def main() -> None:
    provider = get_provider(GenerationConfig(provider="disabled"))
    try:
        provider.generate("hello")
    except LLMProviderUnavailable:
        pass
    else:
        raise AssertionError("disabled provider should not generate text")

    content = _extract_chat_content({"choices": [{"message": {"content": "ok"}}]})
    if content != "ok":
        raise AssertionError("chat response parsing changed")
    if "llama" not in GenerationConfig().model.lower():
        raise AssertionError("default generator model should use a stronger Llama instruct model")

    state = build_graph().invoke(
        {"user_brief": "Build an internal API docs assistant over fast-moving SDK docs."}
    )
    output = state.draft_output or {}
    generation = output.get("generation") or {}
    if generation.get("status") != "fallback":
        raise AssertionError(f"expected deterministic fallback, got {generation}")
    if "generated_answer" not in output:
        raise AssertionError("synthesizer did not attach generated_answer")
    if not output.get("architecture_decisions"):
        raise AssertionError("structured architecture decisions disappeared")

    print(f"llm_provider_smoke={generation['status']}")


if __name__ == "__main__":
    main()
