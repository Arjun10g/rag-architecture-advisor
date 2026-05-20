from __future__ import annotations

from graph.state import AdvisorState, RequirementValue


ATTRIBUTE_LABELS = {
    "A1": "answer risk",
    "A2": "exact terminology dependence",
    "A3": "reasoning complexity",
    "A4": "compliance boundary",
    "A5": "data sensitivity",
    "A6": "document shape",
    "A7": "freshness cadence",
    "A8": "latency tolerance",
    "A9": "language coverage",
    "A10": "jargon distance",
    "A11": "citation and audit need",
    "A12": "human review posture",
}


SOURCE_AGENTS_BY_ATTR = {
    "A1": ("security", "evaluation"),
    "A2": ("retrieval",),
    "A3": ("retrieval", "evaluation"),
    "A4": ("security", "cloud_iac"),
    "A5": ("security",),
    "A6": ("retrieval",),
    "A7": ("cloud_iac", "retrieval"),
    "A8": ("evaluation", "cloud_iac"),
    "A9": ("retrieval",),
    "A10": ("retrieval",),
    "A11": ("security", "evaluation"),
    "A12": ("security", "cloud_iac"),
}


def _value(vector: dict[str, RequirementValue], attr: str) -> str | None:
    return vector.get(attr, RequirementValue()).value


def _source_ids(evidence_pack: dict | None, *agents: str, limit: int = 3) -> list[str]:
    if not evidence_pack:
        return []
    source_ids: list[str] = []
    for agent in agents:
        for source in evidence_pack.get("by_agent", {}).get(agent, []):
            source_id = str(source.get("source_id") or "")
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)
            if len(source_ids) >= limit:
                return source_ids
    return source_ids


def _evidence_chunks(evidence_pack: dict | None, *agents: str, limit: int = 2) -> list[dict]:
    if not evidence_pack:
        return []
    chunks: list[dict] = []
    seen: set[str] = set()
    for agent in agents:
        for source in evidence_pack.get("by_agent", {}).get(agent, []):
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            chunks.append(
                {
                    "source_id": source_id,
                    "section": source.get("section") or "",
                    "snippet": source.get("snippet") or "",
                }
            )
            if len(chunks) >= limit:
                return chunks
    return chunks


def _record(
    *,
    kind: str,
    attr: str,
    requirement: str,
    reasoning: str,
    decision_effect: str,
    accepted_tradeoff: str,
    evidence_pack: dict | None,
) -> dict:
    agents = SOURCE_AGENTS_BY_ATTR.get(attr, ("retrieval", "evaluation"))
    return {
        "kind": kind,
        "attr": attr,
        "label": ATTRIBUTE_LABELS[attr],
        "requirement": requirement,
        "reasoning": reasoning,
        "decision_effect": decision_effect,
        "accepted_tradeoff": accepted_tradeoff,
        "source_ids": _source_ids(evidence_pack, *agents),
        "evidence_chunks": _evidence_chunks(evidence_pack, *agents),
    }


def _format_record(record: dict) -> str:
    source_ids = " ".join(f"`{source_id}`" for source_id in record.get("source_ids") or [])
    citation = f" {source_ids}" if source_ids else ""
    return (
        f"{record['attr']} {record['label']}: {record['reasoning']} "
        f"Effect: {record['decision_effect']} "
        f"Tradeoff: {record['accepted_tradeoff']}{citation}"
    )


def _topology_strength(topology: dict, evidence_pack: dict | None) -> dict:
    source_ids = _source_ids(evidence_pack, "retrieval", "evaluation")
    return {
        "kind": "strength",
        "attr": "topology",
        "label": "topology selection",
        "requirement": topology.get("key", "unknown"),
        "reasoning": f"{topology.get('name', 'The selected topology')} is chosen from a fixed catalog.",
        "decision_effect": "The recommendation is auditable because the selected stages are deterministic.",
        "accepted_tradeoff": "The catalog constrains creativity in exchange for repeatability and eval coverage.",
        "source_ids": source_ids,
        "evidence_chunks": _evidence_chunks(evidence_pack, "retrieval", "evaluation"),
    }


def _requirement_records(state: AdvisorState, topology: dict, evidence_pack: dict | None) -> list[dict]:
    vector = state.requirement_vector
    records: list[dict] = []
    topology_key = str(topology.get("key") or "")

    if _value(vector, "A2") == "high":
        records.append(
            _record(
                kind="strength",
                attr="A2",
                requirement="high",
                reasoning="The brief needs exact API/control terminology, so dense-only retrieval would be too brittle.",
                decision_effect="Hybrid retrieval and lexical indexing stay in the design path.",
                accepted_tradeoff="A lexical sidecar adds index operations and fusion tuning.",
                evidence_pack=evidence_pack,
            )
        )

    if "rerank" in topology_key or topology_key == "adaptive_agentic":
        records.append(
            _record(
                kind="strength",
                attr="A3",
                requirement=_value(vector, "A3") or "inferred",
                reasoning="The request benefits from a second ranking pass before context packing.",
                decision_effect="Candidate fanout is reranked before generation.",
                accepted_tradeoff="Reranking improves precision but adds latency and model-serving cost.",
                evidence_pack=evidence_pack,
            )
        )

    if _value(vector, "A5") in {"regulated-personal", "internal"}:
        records.append(
            _record(
                kind="weakness",
                attr="A5",
                requirement=_value(vector, "A5") or "unset",
                reasoning="Sensitive or private data makes retrieval permissions part of correctness.",
                decision_effect="ACL-aware retrieval, redaction, and scoped logging must precede prompt construction.",
                accepted_tradeoff="Security filtering can reduce recall if permissions metadata is incomplete.",
                evidence_pack=evidence_pack,
            )
        )

    if _value(vector, "A7") == "fast-moving":
        records.append(
            _record(
                kind="weakness",
                attr="A7",
                requirement="fast-moving",
                reasoning="The corpus can drift faster than a static embedding index.",
                decision_effect="Blue-green index aliases and freshness probes become deployment requirements.",
                accepted_tradeoff="Frequent reindexing costs more but avoids stale SDK or policy answers.",
                evidence_pack=evidence_pack,
            )
        )

    if _value(vector, "A8") == "strict":
        records.append(
            _record(
                kind="weakness",
                attr="A8",
                requirement="strict",
                reasoning="Strict latency competes with hybrid retrieval, reranking, and review gates.",
                decision_effect="The design needs candidate caps, p50/p95/p99 latency gates, and a 512d speed profile.",
                accepted_tradeoff="Lower latency profiles may sacrifice recall or ranking depth.",
                evidence_pack=evidence_pack,
            )
        )

    if _value(vector, "A11") in {"mandatory", "recommended"}:
        records.append(
            _record(
                kind="strength",
                attr="A11",
                requirement=_value(vector, "A11") or "unset",
                reasoning="Citation, audit logging, and lineage requirements are visible in answer generation and CI gates.",
                decision_effect="Each major architecture decision carries source IDs and reasoning chunks plus audit logging hooks.",
                accepted_tradeoff="Cited answers are more verbose but easier to audit.",
                evidence_pack=evidence_pack,
            )
        )

    if _value(vector, "A12") == "gated":
        records.append(
            _record(
                kind="weakness",
                attr="A12",
                requirement="gated",
                reasoning="Human review prevents unsafe direct answers but turns the RAG system into a workflow.",
                decision_effect="A review queue appears in the pipeline and Terraform sketch.",
                accepted_tradeoff="The system optimizes for controlled release over immediate response.",
                evidence_pack=evidence_pack,
            )
        )

    return records


def _operational_records(state: AdvisorState, evidence_pack: dict | None) -> list[dict]:
    records: list[dict] = []
    if state.pending_elicitation:
        records.append(
            {
                "kind": "weakness",
                "attr": "pending",
                "label": "missing requirements",
                "requirement": ", ".join(state.pending_elicitation),
                "reasoning": "Some attributes still need explicit user confirmation.",
                "decision_effect": "The recommendation should be treated as provisional.",
                "accepted_tradeoff": "The graph can continue with priors, but confidence is lower.",
                "source_ids": _source_ids(evidence_pack, "evaluation"),
                "evidence_chunks": _evidence_chunks(evidence_pack, "evaluation"),
            }
        )
    if state.conflict:
        records.append(
            {
                "kind": "weakness",
                "attr": "conflict",
                "label": "router conflict",
                "requirement": ", ".join(state.conflict.attributes),
                "reasoning": state.conflict.rationale,
                "decision_effect": "The user should choose which tradeoff wins before deployment.",
                "accepted_tradeoff": "The graph keeps both options visible instead of silently resolving them.",
                "source_ids": _source_ids(evidence_pack, "security", "evaluation"),
                "evidence_chunks": _evidence_chunks(evidence_pack, "security", "evaluation"),
            }
        )
    return records


def build_panel(
    state: AdvisorState,
    topology: dict,
    evidence_pack: dict | None = None,
    projection: dict | None = None,
) -> dict:
    items = [
        _topology_strength(topology, evidence_pack),
        *_requirement_records(state, topology, evidence_pack),
        *_operational_records(state, evidence_pack),
    ]

    strengths = [_format_record(item) for item in items if item["kind"] == "strength"]
    weaknesses = [_format_record(item) for item in items if item["kind"] == "weakness"]
    tradeoffs = [
        {
            "attr": item["attr"],
            "requirement": item["requirement"],
            "accepted_tradeoff": item["accepted_tradeoff"],
            "source_ids": item["source_ids"],
        }
        for item in items
    ]
    if not weaknesses:
        weaknesses.append("No requirement-specific weakness was found at the current skeleton level.")
    return {
        "items": items,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "tradeoffs": tradeoffs,
        "projection_components": [
            component["id"]
            for component in (projection or {}).get("deployment_components", [])
        ],
    }
