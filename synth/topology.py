from __future__ import annotations

from graph.state import RequirementValue


TOPOLOGIES = {
    "single_stage_dense": "Single-stage dense",
    "single_stage_hybrid": "Single-stage hybrid",
    "two_stage_dense_rerank": "Two-stage dense + rerank",
    "two_stage_hybrid_rerank": "Two-stage hybrid + rerank",
    "adaptive_agentic": "Adaptive/agentic",
}


def _value(vector: dict[str, RequirementValue], attr: str) -> str | None:
    item = vector.get(attr)
    return item.value if item else None


def select_topology(requirement_vector: dict[str, RequirementValue]) -> dict:
    exact_match = _value(requirement_vector, "A2")
    complexity = _value(requirement_vector, "A3")
    risk = _value(requirement_vector, "A1")

    if complexity == "multi-hop":
        key = "adaptive_agentic"
    elif exact_match == "high" and risk in {"costly", "catastrophic"}:
        key = "two_stage_hybrid_rerank"
    elif exact_match == "high":
        key = "single_stage_hybrid"
    else:
        key = "two_stage_dense_rerank"

    return {
        "key": key,
        "name": TOPOLOGIES[key],
        "rationale": "Selected by hard constraints first, then quality within survivors.",
    }

