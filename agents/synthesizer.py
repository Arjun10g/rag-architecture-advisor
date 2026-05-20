from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from graph.state import AdvisorState
from llm.provider import LLMProviderUnavailable, get_provider
from synth.panel import ATTRIBUTE_LABELS, build_panel
from synth.projection import project_deployment
from synth.terraform_emit import emit_terraform
from synth.topology import select_topology


SPECIALIST_ORDER = {
    "retrieval": 0,
    "security": 1,
    "cloud_iac": 2,
    "evaluation": 3,
}

AREA_LABELS = {
    "retrieval_strategy": "Retrieval strategy",
    "reranking": "Reranking",
    "embedding_dimension": "Embedding dimension",
    "vector_database": "Vector database",
    "deployment": "Deployment",
    "security_governance": "Security and governance",
    "evaluation": "Evaluation",
}

LOW_VALUE_PATH_SUFFIXES = (
    "00_readme.md",
    "06_references.md",
    "07_references.md",
    "09_references_and_source_map.md",
)

LOW_VALUE_SECTION_TERMS = (
    "references",
    "source map",
    "source pointers",
)

LOW_VALUE_ELEMENT_TYPES = {
    "code_fence",
    "mermaid",
    "reference",
}

USEFUL_SNIPPET_TERMS = (
    "acl",
    "authorization",
    "bm25",
    "blue-green",
    "candidate",
    "citation",
    "dense",
    "gold",
    "hybrid",
    "latency",
    "metadata",
    "mrr",
    "ndcg",
    "permission",
    "quality",
    "recall",
    "rerank",
    "retrieval",
    "rrf",
    "storage",
    "vector",
)

FORBIDDEN_GENERATED_PATTERNS = (
    "corpus_",
    "corpus/",
    ".md",
    "router:start",
    "Graph Trace",
    "Requirement Vector",
    "source_id",
    "source_ids",
    "chunk_id",
    "two_stage_",
)

A_CODE_RE = re.compile(r"\bA(?:1[0-2]|[1-9])\s*(?::|=)")
EVIDENCE_REF_RE = re.compile(r"\[E\d+\]")


def _agent_rank(source: dict) -> int:
    ranks = [
        SPECIALIST_ORDER.get(str(agent), 99)
        for agent in source.get("used_by", [])
    ]
    return min(ranks) if ranks else 99


def _evidence_quality(source: dict) -> int:
    snippet = str(source.get("snippet") or "").strip()
    lower_snippet = snippet.lower()
    section = str(source.get("section") or "").lower()
    source_path = str(source.get("source_path") or "").lower()
    element_type = str(source.get("element_type") or "").lower()

    score = 0
    if len(snippet) >= 120:
        score += 3
    elif len(snippet) >= 70:
        score += 1
    else:
        score -= 4

    if element_type in LOW_VALUE_ELEMENT_TYPES:
        score -= 9
    if any(source_path.endswith(suffix) for suffix in LOW_VALUE_PATH_SUFFIXES):
        score -= 5
    if any(term in section for term in LOW_VALUE_SECTION_TERMS):
        score -= 4
    if lower_snippet.startswith("generated:"):
        score -= 6
    if lower_snippet.startswith("```"):
        score -= 5
    if lower_snippet.count("http") >= 2:
        score -= 3
    if "blue-green" in lower_snippet or "dimension changes" in lower_snippet:
        score += 4
    if "embedding model upgrades" in lower_snippet or "re-embedding" in lower_snippet:
        score += 3
    if "choose embedding dimension" in section or "lower dimension" in section:
        score += 5
    if "dimension choice drives" in lower_snippet:
        score += 4

    score += min(5, sum(1 for term in USEFUL_SNIPPET_TERMS if term in lower_snippet))
    return score


def _source_sort_key(source: dict) -> tuple[int, int, float]:
    quality = source.get("evidence_quality")
    if quality is None:
        quality = _evidence_quality(source)
    return (
        _agent_rank(source),
        -int(quality),
        -float(source.get("score") or 0.0),
    )


def _source_quality_value(source: dict, default: int = -99) -> int:
    quality = source.get("evidence_quality")
    return int(quality) if quality is not None else default


def _rank_sources(sources: list[dict]) -> list[dict]:
    for source in sources:
        source["evidence_quality"] = _evidence_quality(source)
    return sorted(sources, key=_source_sort_key)


def _rank_agent_sources(evidence_pack: dict, *agents: str, require_displayable: bool = True) -> list[dict]:
    ranked: list[dict] = []
    seen: set[str] = set()
    for agent in agents:
        agent_sources = sorted(
            evidence_pack.get("by_agent", {}).get(agent, []),
            key=_source_sort_key,
        )
        for source in agent_sources:
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in seen:
                continue
            if require_displayable and _source_quality_value(source) < 0:
                continue
            seen.add(source_id)
            ranked.append(source)
    return ranked


def _display_sources(all_sources: list[dict], *, per_agent: int = 6) -> list[dict]:
    selected: list[dict] = []
    seen: set[str] = set()
    for agent in SPECIALIST_ORDER:
        agent_sources = [
            source
            for source in all_sources
            if agent in source.get("used_by", [])
        ]
        displayable = [
            source
            for source in agent_sources
            if _source_quality_value(source) >= 0
        ]
        cohort = displayable or agent_sources[:1]
        for source in cohort[:per_agent]:
            source_id = str(source.get("source_id") or "")
            if source_id and source_id not in seen:
                seen.add(source_id)
                selected.append(source)
    return selected


def _area_label(area: str) -> str:
    return AREA_LABELS.get(area, area.replace("_", " ").title())


def _constraint_label(constraint: str) -> str:
    if constraint.startswith("A2 high"):
        return "Exact terminology is high, so lexical or hybrid retrieval is mandatory."
    if constraint.startswith("A4 sectoral"):
        return "Sectoral compliance requires an in-boundary generation provider."
    if constraint.startswith("A5 regulated-personal"):
        return "Regulated personal data requires permission-aware retrieval and redaction."
    if constraint.startswith("A11 mandatory"):
        return "Mandatory citation/audit requirements require lineage logging."
    if constraint.startswith("A12 gated"):
        return "Human review requirements rule out direct-answer deployment without a review gate."
    return constraint


def _evidence_pack(state: AdvisorState) -> dict:
    sources: dict[str, dict] = {}
    by_agent: dict[str, list[dict]] = {}
    for finding in state.agent_findings.values():
        by_agent[finding.agent] = []
        for source in finding.sources:
            record = sources.setdefault(source.source_id, asdict(source) | {"used_by": []})
            if finding.agent not in record["used_by"]:
                record["used_by"].append(finding.agent)
            by_agent[finding.agent].append(record)
    ordered_sources = _rank_sources(list(sources.values()))
    by_agent = {
        agent: sorted(records, key=_source_sort_key)
        for agent, records in by_agent.items()
    }
    display_sources = _display_sources(ordered_sources)
    display_ids = {str(source.get("source_id") or "") for source in display_sources}
    label_order = [
        *display_sources,
        *[
            source
            for source in ordered_sources
            if str(source.get("source_id") or "") not in display_ids
        ],
    ]
    labels = {}
    for index, source in enumerate(label_order, start=1):
        label = f"E{index}"
        source["evidence_label"] = label
        labels[source["source_id"]] = label
    return {
        "sources": display_sources,
        "all_sources": ordered_sources,
        "by_agent": by_agent,
        "labels": labels,
    }


def _source_ids(evidence_pack: dict, *agents: str, limit: int = 3) -> list[str]:
    source_ids: list[str] = []
    candidates = _rank_agent_sources(evidence_pack, *agents, require_displayable=True)
    if not candidates:
        candidates.extend(_rank_agent_sources(evidence_pack, *agents, require_displayable=False))
    for source in candidates:
        source_id = source["source_id"]
        if source_id not in source_ids:
            source_ids.append(source_id)
        if len(source_ids) >= limit:
            return source_ids
    return source_ids


def _evidence_chunks(evidence_pack: dict, *agents: str, limit: int = 2) -> list[dict]:
    chunks: list[dict] = []
    seen: set[str] = set()
    candidates = _rank_agent_sources(evidence_pack, *agents, require_displayable=True)
    if not candidates:
        candidates.extend(_rank_agent_sources(evidence_pack, *agents, require_displayable=False))
    for source in candidates:
        source_id = str(source.get("source_id") or "")
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        chunks.append(
            {
                "evidence_label": source.get("evidence_label") or evidence_pack.get("labels", {}).get(source_id, ""),
                "source_id": source_id,
                "section": source.get("section") or "",
                "reasoning_chunk": source.get("snippet") or "",
            }
        )
        if len(chunks) >= limit:
            return chunks
    return chunks


def _evidence_refs_for_source_ids(evidence_pack: dict, source_ids: list[str]) -> list[str]:
    labels = evidence_pack.get("labels", {})
    return [labels[source_id] for source_id in source_ids if source_id in labels]


def _decision(
    *,
    area: str,
    choice: str,
    rationale: str,
    reasoning_steps: list[str],
    tradeoff: str,
    validation: str,
    evidence_pack: dict,
    agents: tuple[str, ...],
) -> dict:
    source_ids = _source_ids(evidence_pack, *agents)
    evidence_chunks = _evidence_chunks(evidence_pack, *agents)
    return {
        "area": area,
        "choice": choice,
        "rationale": rationale,
        "reasoning_steps": reasoning_steps,
        "tradeoff": tradeoff,
        "validation": validation,
        "source_ids": source_ids,
        "evidence_refs": _evidence_refs_for_source_ids(evidence_pack, source_ids),
        "evidence_chunks": evidence_chunks,
    }


def _retrieval_choice(topology: dict) -> str:
    key = topology["key"]
    if "hybrid" in key:
        return "Hybrid lexical + dense candidate generation with reciprocal rank fusion"
    if key == "adaptive_agentic":
        return "Adaptive query planning over specialist retrieval paths"
    return "Dense candidate generation with lexical fallback for exact-match gaps"


def _rerank_choice(topology: dict) -> str:
    key = topology["key"]
    if "rerank" in key:
        return "Enable reranking over the candidate fanout before context packing"
    if key == "adaptive_agentic":
        return "Rerank high-risk or multi-hop branches before generation"
    return "Keep reranking optional until offline eval shows ranking defects"


def _architecture_decisions(topology: dict, projection: dict, evidence_pack: dict) -> list[dict]:
    return [
        _decision(
            area="retrieval_strategy",
            choice=_retrieval_choice(topology),
            rationale=(
                "The selected topology needs both semantic recall and exact terminology handling, "
                "so candidate generation should be grounded in retrieval evidence, not only in the "
                "router label."
            ),
            reasoning_steps=[
                "The selected catalog entry requires lexical and dense candidate generation before reranking.",
                "Exact terminology pressure pushes the design toward lexical support when available.",
                "The retrieved matching guidance supports fusion when semantic recall and precise terms both matter.",
            ],
            tradeoff="Hybrid retrieval improves recall and exact-match handling, but requires lexical index operations and fusion tuning.",
            validation="Compare lexical, dense, and hybrid runs on the gold retrieval set before changing the default.",
            evidence_pack=evidence_pack,
            agents=("retrieval",),
        ),
        _decision(
            area="reranking",
            choice=_rerank_choice(topology),
            rationale=(
                "Reranking is tied to the topology risk profile and should be evaluated as a "
                "separate stage with bounded candidate fanout."
            ),
            reasoning_steps=[
                "Candidate generation optimizes recall, so a second pass is needed when precision matters.",
                "The rerank stage is present in the selected topology catalog entry.",
                "Bounded fanout keeps the reranker cost and latency measurable.",
            ],
            tradeoff="Reranking usually improves precision, but adds latency and model-serving cost.",
            validation="Track nDCG/MRR and p50/p95/p99 latency with and without reranking.",
            evidence_pack=evidence_pack,
            agents=("retrieval", "evaluation"),
        ),
        _decision(
            area="embedding_dimension",
            choice="Use 1024-dimensional Matryoshka embeddings for quality; keep 512d as the speed profile",
            rationale=(
                "The dimension choice is explicit so the 1024 quality profile and the 512 speed "
                "profile can be compared under the same gold sets."
            ),
            reasoning_steps=[
                "The embedding model is Matryoshka-capable, so lower dimensions can be evaluated without changing models.",
                "Persisting both 1024 and 512 avoids rebuilding the vector database for the common quality/speed switch.",
                "The selected production default should be evidence-driven by ablation results.",
            ],
            tradeoff="1024d costs more storage and vector math; 512d is cheaper but may lose fine-grained ranking signal.",
            validation="Run dimension ablations across 1024, 768, 512, 384, and 256 before locking production defaults.",
            evidence_pack=evidence_pack,
            agents=("cloud_iac", "evaluation"),
        ),
        _decision(
            area="vector_database",
            choice="Managed vector index with lexical sidecar, metadata filters, and blue-green index aliases",
            rationale=(
                "The deployment needs vector search, exact-match support, safe reindexing, and "
                "metadata-aware filtering rather than a bare embedding store."
            ),
            reasoning_steps=[
                "Vector search serves semantic recall while the lexical sidecar protects exact terminology.",
                "Metadata filters are required for namespace, domain, sensitivity, and tenant controls.",
                "Blue-green aliases let embedding and dimension upgrades roll out without replacing the serving path in place.",
            ],
            tradeoff="A managed vector index reduces serving risk but introduces platform cost and migration discipline.",
            validation="Build and smoke both `chunks_dim_1024` and `chunks_dim_512` tables before deployment.",
            evidence_pack=evidence_pack,
            agents=("cloud_iac", "retrieval"),
        ),
        _decision(
            area="deployment",
            choice="Provision " + ", ".join(component["id"] for component in projection["deployment_components"]),
            rationale=(
                "The Terraform sketch follows the retrieved IaC guidance by separating compute, "
                "storage, database, security, monitoring, and scaling concerns."
            ),
            reasoning_steps=[
                "Pipeline stages are projected into the seven required cloud pillars.",
                "Cross-cutting networking, security, monitoring, and scalability components serve every topology.",
                "The emitted module tree keeps environment-specific values in tfvars instead of hardcoding them.",
            ],
            tradeoff="More modules create more IaC surface area, but make review, reuse, and ownership clearer.",
            validation="Export the sketch, run `terraform fmt`, then run `terraform validate` when Terraform is installed.",
            evidence_pack=evidence_pack,
            agents=("cloud_iac",),
        ),
        _decision(
            area="security_governance",
            choice="Apply ACL-aware retrieval before prompt construction and retain audit lineage",
            rationale=(
                "Security controls are represented as ACL-aware retrieval-time constraints and "
                "audit lineage, not only as post-generation review."
            ),
            reasoning_steps=[
                "Permission checks must happen before context enters the prompt.",
                "Audit lineage records why each decision and answer used a given evidence chunk.",
                "Gated review appears when the requirement vector asks for human approval.",
            ],
            tradeoff="Security filtering and audit logging add friction, but prevent unauthorized context exposure.",
            validation="Add tests that deny inaccessible chunks and verify citation/audit records are retained.",
            evidence_pack=evidence_pack,
            agents=("security",),
        ),
        _decision(
            area="evaluation",
            choice="Gate retrieval, routing, topology, answer citations, and latency percentiles in CI",
            rationale=(
                "The recommendation remains auditable only if source coverage and p50/p95/p99 "
                "latency stay visible in the gold-set reports."
            ),
            reasoning_steps=[
                "Routing accuracy protects the requirement vector.",
                "Retrieval metrics protect evidence recall and ranking quality.",
                "Answer and panel gates protect the final user-facing reasoning, citations, and tradeoffs.",
            ],
            tradeoff="CI gates add maintenance work, but catch regressions before they reach the deployed advisor.",
            validation="Run all gold sets after topology, retrieval, reranking, or generator prompt changes.",
            evidence_pack=evidence_pack,
            agents=("evaluation", "retrieval"),
        ),
    ]


def _decision_summary(decisions: list[dict]) -> str:
    lines = []
    for decision in decisions:
        area = str(decision.get("area") or "decision")
        choice = str(decision.get("choice") or "Pending")
        evidence_refs = " ".join(f"[{ref}]" for ref in decision.get("evidence_refs") or [])
        line = f"- {_area_label(area)}: {choice}"
        if decision.get("rationale"):
            line += f"\n  why: {decision['rationale']}"
        for chunk in decision.get("evidence_chunks") or []:
            label = chunk.get("evidence_label") or "evidence"
            snippet = chunk.get("reasoning_chunk") or ""
            if snippet:
                line += f"\n  evidence [{label}]: {snippet}"
        if decision.get("tradeoff"):
            line += f"\n  tradeoff: {decision['tradeoff']}"
        if decision.get("validation"):
            line += f"\n  validate: {decision['validation']}"
        if evidence_refs:
            line += f"\n  supported by: {evidence_refs}"
        lines.append(line)
    return "\n".join(lines)


def _requirement_summary(state: AdvisorState) -> str:
    lines = []
    for entry in state.decision_log[:12]:
        label = ATTRIBUTE_LABELS.get(entry.attr, entry.attr)
        source = "user stated" if entry.source == "stated" else entry.source.replace("-", " ")
        lines.append(f"- {label}: {entry.value} ({source}, confidence {entry.confidence:.2f})")
    if state.pending_elicitation:
        pending = [ATTRIBUTE_LABELS.get(attr, attr) for attr in state.pending_elicitation]
        lines.append("- pending elicitation: " + ", ".join(pending))
    return "\n".join(lines)


def _source_summary(evidence_pack: dict, limit: int = 10) -> str:
    lines = []
    for source in evidence_pack["sources"][:limit]:
        evidence_label = source.get("evidence_label") or "E?"
        section = source.get("section") or "Unsectioned"
        snippet = source.get("snippet") or ""
        lines.append(f"- {evidence_label}: {section}. Reasoning chunk: {snippet}")
    return "\n".join(lines)


def _hard_constraint_summary(state: AdvisorState) -> str:
    if not state.hard_constraints:
        return "- none"
    return "\n".join(f"- {_constraint_label(constraint)}" for constraint in state.hard_constraints)


def _conflict_summary(state: AdvisorState) -> str:
    if not state.conflict:
        return "- none"
    options = "\n".join(f"  - {option}" for option in state.conflict.options)
    return f"- {state.conflict.rationale}\n{options}"


def _generation_prompt(
    state: AdvisorState,
    topology: dict,
    architecture_decisions: list[dict],
    evidence_pack: dict,
) -> tuple[str, str]:
    system = (
        "You are a precise RAG architecture advisor. Write only from the supplied "
        "requirements, decisions, and evidence labels. Do not invent new sources, products, "
        "or requirements. Explain the reasoning behind each major decision, including "
        "the tradeoff accepted and the validation gate that should catch regressions. "
        "Do not reveal raw source IDs, file names, or debug-looking chunk identifiers."
    )
    prompt = f"""
User brief:
{state.user_brief}

Selected topology:
{topology.get("name")}

Resolved requirement vector:
{_requirement_summary(state)}

Hard constraints:
{_hard_constraint_summary(state)}

Router conflicts:
{_conflict_summary(state)}

Architecture decisions:
{_decision_summary(architecture_decisions)}

Evidence snippets:
{_source_summary(evidence_pack)}

Write a final recommendation in four sections:
1. Recommendation
2. Why each decision was made
3. Accepted tradeoffs
4. What to validate next

Use evidence labels such as [E1] inline where they support a claim. Prefer
reasoning chunks over source names; do not list file paths or raw chunk IDs.
""".strip()
    return system, prompt


def _refs(decision: dict) -> str:
    refs = [f"[{ref}]" for ref in decision.get("evidence_refs") or []]
    return " ".join(refs)


def _chunk_bullets(decision: dict, *, limit: int = 2) -> list[str]:
    bullets = []
    for chunk in (decision.get("evidence_chunks") or [])[:limit]:
        label = chunk.get("evidence_label") or "E?"
        snippet = chunk.get("reasoning_chunk") or ""
        if snippet:
            bullets.append(f"  Evidence [{label}]: {snippet}")
    return bullets


def _reasoning_trace(topology: dict, architecture_decisions: list[dict]) -> list[str]:
    retrieval = next(
        (decision for decision in architecture_decisions if decision.get("area") == "retrieval_strategy"),
        {},
    )
    evaluation = next(
        (decision for decision in architecture_decisions if decision.get("area") == "evaluation"),
        {},
    )
    return [
        f"1. Router mapped the brief into human-readable topology drivers, then selected {topology.get('name', 'the selected topology')} from the fixed catalog.",
        f"2. Retrieval evidence { _refs(retrieval) or '[unlabeled]' } was used to decide how semantic recall and exact terminology should be balanced.",
        "3. The synthesizer projected the chosen stages into deployment components, then checked tradeoffs for latency, cost, security, and evaluation.",
        f"4. Evaluation evidence { _refs(evaluation) or '[unlabeled]' } set the validation gates so the recommendation can be regression-tested.",
    ]


def _driver_summary(state: AdvisorState) -> str:
    drivers = [
        f"{entry.value} {ATTRIBUTE_LABELS.get(entry.attr, entry.attr)}"
        for entry in state.decision_log
        if entry.attr.startswith("A") and entry.confidence >= 0.9
    ][:5]
    if not drivers:
        return "The available requirement signals"
    return "The strongest requirement signals (" + ", ".join(drivers) + ")"


def _fallback_answer(
    state: AdvisorState,
    topology: dict,
    architecture_decisions: list[dict],
) -> str:
    lines = [
        "### Recommendation",
        (
            f"Use **{topology.get('name', 'the selected topology')}**. "
            f"{_driver_summary(state)} point to this topology, and the retrieved literature chunks "
            "explain which retrieval, deployment, security, and evaluation controls are needed."
        ),
        "",
        "### Agentic Reasoning Trace",
        *_reasoning_trace(topology, architecture_decisions),
        "",
        "### Decision Rationale",
    ]
    for decision in architecture_decisions:
        refs = _refs(decision)
        suffix = f" {refs}" if refs else ""
        area = _area_label(str(decision.get("area") or "decision"))
        lines.append(f"- **{area}:** {decision.get('choice', 'Pending')}{suffix}")
        lines.append(f"  {decision.get('rationale', '')}")
        for step in decision.get("reasoning_steps") or []:
            lines.append(f"  - {step}")
        lines.extend(_chunk_bullets(decision))
    lines.append("")
    lines.append("### Accepted Tradeoffs")
    for decision in architecture_decisions:
        area = _area_label(str(decision.get("area") or "decision"))
        lines.append(f"- **{area}:** {decision.get('tradeoff', 'No tradeoff recorded.')}")
    lines.extend(
        [
            "",
            "### Validation Plan",
        ]
    )
    for decision in architecture_decisions:
        area = _area_label(str(decision.get("area") or "decision"))
        lines.append(f"- **{area}:** {decision.get('validation', 'Run the gold-set gates.')}")
    return "\n".join(lines)


def _answer_quality_issue(answer: str) -> str | None:
    for pattern in FORBIDDEN_GENERATED_PATTERNS:
        if pattern in answer:
            return f"generated answer exposed internal marker {pattern!r}"
    if A_CODE_RE.search(answer):
        return "generated answer exposed raw attribute codes"
    if not EVIDENCE_REF_RE.search(answer):
        return "generated answer omitted evidence labels"
    lower = answer.lower()
    if "tradeoff" not in lower:
        return "generated answer omitted accepted tradeoffs"
    if "validat" not in lower:
        return "generated answer omitted validation guidance"
    return None


def _generate_answer(
    state: AdvisorState,
    topology: dict,
    architecture_decisions: list[dict],
    evidence_pack: dict,
) -> tuple[str, dict]:
    provider = None
    try:
        provider = get_provider()
        system, prompt = _generation_prompt(state, topology, architecture_decisions, evidence_pack)
        answer = provider.generate(prompt, system=system)
    except LLMProviderUnavailable as exc:
        return _fallback_answer(state, topology, architecture_decisions), {
            "status": "fallback",
            "provider": getattr(provider, "name", "unknown"),
            "model": getattr(provider, "model", None),
            "reason": str(exc),
        }
    quality_issue = _answer_quality_issue(answer)
    if quality_issue:
        return _fallback_answer(state, topology, architecture_decisions), {
            "status": "guarded_fallback",
            "provider": getattr(provider, "name", "unknown"),
            "model": getattr(provider, "model", None),
            "reason": quality_issue,
        }
    return answer, {
        "status": "ok",
        "provider": getattr(provider, "name", "unknown"),
        "model": getattr(provider, "model", None),
    }


def _audit_record(
    state: AdvisorState,
    topology: dict,
    architecture_decisions: list[dict],
    evidence_pack: dict,
    generation: dict,
) -> dict:
    source_ids = [
        source.get("source_id")
        for source in evidence_pack.get("all_sources", evidence_pack.get("sources", []))
        if source.get("source_id")
    ]
    return {
        "event": "advisor_synthesis",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "brief_hash": hashlib.sha256(state.user_brief.encode("utf-8")).hexdigest()[:16],
        "domain_prior": state.domain_prior,
        "topology_key": topology.get("key"),
        "decision_areas": [decision.get("area") for decision in architecture_decisions],
        "source_ids": source_ids,
        "pending_elicitation": list(state.pending_elicitation),
        "conflict": asdict(state.conflict) if state.conflict else None,
        "generation": generation,
        "graph_trace": list(state.graph_trace),
    }


def _maybe_write_audit(record: dict) -> None:
    path = os.getenv("ADVISOR_AUDIT_LOG_PATH", "").strip()
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def synthesize(state: AdvisorState) -> dict:
    topology = select_topology(state.requirement_vector)
    projection = project_deployment(topology)
    evidence_pack = _evidence_pack(state)
    architecture_decisions = _architecture_decisions(topology, projection, evidence_pack)
    generated_answer, generation = _generate_answer(
        state,
        topology,
        architecture_decisions,
        evidence_pack,
    )
    audit_record = _audit_record(
        state,
        topology,
        architecture_decisions,
        evidence_pack,
        generation,
    )
    _maybe_write_audit(audit_record)
    return {
        "topology": topology,
        "projection": projection,
        "terraform": emit_terraform(topology, projection),
        "panel": build_panel(state, topology, evidence_pack=evidence_pack, projection=projection),
        "evidence_pack": evidence_pack,
        "architecture_decisions": architecture_decisions,
        "sources": evidence_pack["sources"],
        "generated_answer": generated_answer,
        "generation": generation,
        "audit_record": audit_record,
    }
