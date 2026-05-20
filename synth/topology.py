from __future__ import annotations

from dataclasses import dataclass

from graph.state import RequirementValue


@dataclass(frozen=True)
class Topology:
    key: str
    name: str
    stages: tuple[str, ...]
    supports_exact_match: bool
    uses_rerank: bool
    uses_adaptive: bool
    direct_answer: bool
    quality_rank: int
    latency_rank: int


TOPOLOGY_CATALOG = {
    "single_stage_dense": Topology(
        key="single_stage_dense",
        name="Single-stage dense",
        stages=("parse_chunk", "embed", "vector_search", "generate"),
        supports_exact_match=False,
        uses_rerank=False,
        uses_adaptive=False,
        direct_answer=True,
        quality_rank=1,
        latency_rank=1,
    ),
    "single_stage_hybrid": Topology(
        key="single_stage_hybrid",
        name="Single-stage hybrid",
        stages=("parse_chunk", "embed", "vector_search", "bm25", "generate"),
        supports_exact_match=True,
        uses_rerank=False,
        uses_adaptive=False,
        direct_answer=True,
        quality_rank=2,
        latency_rank=2,
    ),
    "two_stage_dense_rerank": Topology(
        key="two_stage_dense_rerank",
        name="Two-stage dense + rerank",
        stages=("parse_chunk", "embed", "vector_search", "rerank", "generate"),
        supports_exact_match=False,
        uses_rerank=True,
        uses_adaptive=False,
        direct_answer=False,
        quality_rank=3,
        latency_rank=3,
    ),
    "two_stage_hybrid_rerank": Topology(
        key="two_stage_hybrid_rerank",
        name="Two-stage hybrid + rerank",
        stages=("parse_chunk", "embed", "vector_search", "bm25", "rerank", "generate"),
        supports_exact_match=True,
        uses_rerank=True,
        uses_adaptive=False,
        direct_answer=False,
        quality_rank=4,
        latency_rank=4,
    ),
    "adaptive_agentic": Topology(
        key="adaptive_agentic",
        name="Adaptive/agentic",
        stages=(
            "query_planner",
            "parse_chunk",
            "embed",
            "vector_search",
            "bm25",
            "rerank",
            "generate",
        ),
        supports_exact_match=True,
        uses_rerank=True,
        uses_adaptive=True,
        direct_answer=False,
        quality_rank=5,
        latency_rank=5,
    ),
}


def _value(vector: dict[str, RequirementValue], attr: str) -> str | None:
    item = vector.get(attr)
    return item.value if item else None


def _candidate(candidates: list[Topology], key: str) -> Topology | None:
    for candidate in candidates:
        if candidate.key == key:
            return candidate
    return None


def _choose_candidate(
    candidates: list[Topology],
    *,
    complexity: str | None,
    risk: str | None,
    exact_match: str | None,
) -> Topology:
    if complexity == "multi-hop":
        adaptive = _candidate(candidates, "adaptive_agentic")
        if adaptive:
            return adaptive

    if exact_match == "high" and risk in {"costly", "catastrophic"}:
        hybrid_rerank = _candidate(candidates, "two_stage_hybrid_rerank")
        if hybrid_rerank:
            return hybrid_rerank

    if exact_match == "high":
        single_hybrid = _candidate(candidates, "single_stage_hybrid")
        if single_hybrid:
            return single_hybrid

    dense_rerank = _candidate(candidates, "two_stage_dense_rerank")
    if dense_rerank:
        return dense_rerank
    return max(candidates, key=lambda candidate: candidate.quality_rank)


def _topology_payload(
    selected: Topology,
    *,
    filters: list[str],
    exact_match: str | None,
    complexity: str | None,
    risk: str | None,
    latency: str | None,
    human_review: str | None,
    auditability: str | None,
    candidates: list[Topology],
) -> dict:
    requirements = {
        "lexical_required": exact_match == "high",
        "rerank_recommended": selected.uses_rerank,
        "adaptive_recommended": selected.uses_adaptive,
        "review_gate_required": human_review == "gated",
        "audit_log_required": auditability == "mandatory",
    }
    rationale_parts = [
        "Selected by hard constraints first, then quality within survivors.",
        f"A2={exact_match or 'unset'}, A3={complexity or 'unset'}, A1={risk or 'unset'}, A8={latency or 'unset'}.",
    ]
    if filters:
        rationale_parts.append(" ".join(filters))

    return {
        "key": selected.key,
        "name": selected.name,
        "rationale": " ".join(rationale_parts),
        "stages": list(selected.stages),
        "requirements": requirements,
        "selection": {
            "filters": filters,
            "candidate_keys": [candidate.key for candidate in candidates],
            "quality_rank": selected.quality_rank,
            "latency_rank": selected.latency_rank,
        },
    }


def select_topology(requirement_vector: dict[str, RequirementValue]) -> dict:
    exact_match = _value(requirement_vector, "A2")
    complexity = _value(requirement_vector, "A3")
    risk = _value(requirement_vector, "A1")
    latency = _value(requirement_vector, "A8")
    human_review = _value(requirement_vector, "A12")
    auditability = _value(requirement_vector, "A11")

    candidates = list(TOPOLOGY_CATALOG.values())
    filters: list[str] = []

    if exact_match == "high":
        candidates = [candidate for candidate in candidates if candidate.supports_exact_match]
        filters.append("A2 high removed dense-only topologies.")

    if human_review == "gated":
        candidates = [candidate for candidate in candidates if not candidate.direct_answer]
        filters.append("A12 gated removed direct-answer topologies.")

    if latency == "strict" and risk not in {"costly", "catastrophic"}:
        candidates = [candidate for candidate in candidates if not candidate.uses_adaptive]
        filters.append("A8 strict removed adaptive loops unless risk justifies the extra stage.")

    if not candidates:
        candidates = list(TOPOLOGY_CATALOG.values())
        filters.append("No candidate survived all filters; restored catalog and marked as unresolved.")

    selected = _choose_candidate(candidates, complexity=complexity, risk=risk, exact_match=exact_match)
    return _topology_payload(
        selected,
        filters=filters,
        exact_match=exact_match,
        complexity=complexity,
        risk=risk,
        latency=latency,
        human_review=human_review,
        auditability=auditability,
        candidates=candidates,
    )
