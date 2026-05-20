from __future__ import annotations

import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["LLM_PROVIDER"] = "disabled"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["ADVISOR_LATENCY_PROFILE"] = "quality"
os.environ["DEEP_RESEARCH_FULL_TEXT"] = "false"
os.environ["DEEP_THINKING_ENABLED"] = "true"
os.environ["PREWARM_RETRIEVER"] = "false"
os.environ["RETRIEVAL_MODE"] = "lexical"
os.environ["VECTOR_STORE_BACKEND"] = "memory"
os.environ["ADVISOR_USAGE_COUNTER_PATH"] = ""

from app import advise_api, advise_detailed


ACCURACY_BRIEF = (
    "Build an API docs assistant and prioritize maximal accuracy over latency. "
    "Use the best possible answer quality, strict citations, and enough review to avoid wrong recommendations."
)
LATENCY_BRIEF = (
    "Build an in-IDE API docs assistant for real-time interactive latency and fast response, "
    "while still supporting citations over public SDK docs."
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _visible_text(payload: dict) -> str:
    return "\n".join(
        str(payload.get(key) or "")
        for key in (
            "recommendation",
            "implementation_plan",
            "design_plan",
            "literature_curation",
            "architecture_decisions",
        )
    )


def _check_grounded(payload: dict) -> None:
    text = _visible_text(payload)
    _require("[E" in text, "visible plan should cite selected evidence labels")
    _require("Evidence from selected chunks" in text, "design plan should show chunk-grounded evidence")
    _require("Curated Literature Map" in text, "literature curation should be included")
    _require("corpus_" not in text and "source_id" not in text, "public text leaked internal source identifiers")
    chunks = payload.get("reasoning_chunks") or []
    _require(isinstance(chunks, list) and chunks, "public payload should include reasoning chunks")


def main() -> None:
    accuracy_detail = advise_detailed(ACCURACY_BRIEF)
    accuracy_plan = accuracy_detail[1]
    accuracy_design = accuracy_detail[2]
    accuracy_raw = accuracy_detail[-1]
    _require("Plan profile:** Accuracy-first" in accuracy_plan, "accuracy brief did not switch build plan profile")
    _require("Plan profile:** Accuracy-first" in accuracy_design, "accuracy brief did not switch design plan profile")
    _require("1024d" in accuracy_plan, "accuracy plan should keep the 1024d quality profile visible")
    _require("Rerank" in accuracy_plan or "rerank" in accuracy_plan, "accuracy plan should emphasize reranking")
    topology = (accuracy_raw.get("draft_output") or {}).get("topology") or {}
    _require(
        topology.get("name") in {"Adaptive/agentic", "Two-stage hybrid + rerank"},
        "accuracy brief should select a high-quality topology",
    )
    _check_grounded(advise_api(ACCURACY_BRIEF))

    latency_detail = advise_detailed(LATENCY_BRIEF)
    latency_plan = latency_detail[1]
    latency_design = latency_detail[2]
    _require("Plan profile:** Latency-first" in latency_plan, "latency brief did not switch build plan profile")
    _require("Plan profile:** Latency-first" in latency_design, "latency brief did not switch design plan profile")
    _require("512d" in latency_plan, "latency plan should make the 512d speed profile visible")
    _check_grounded(advise_api(LATENCY_BRIEF))

    print("component_strategy_smoke=ok")


if __name__ == "__main__":
    main()
