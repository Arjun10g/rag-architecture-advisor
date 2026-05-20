from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from graph.state import AdvisorState
from llm.provider import LLMProviderUnavailable, get_provider
from synth.panel import build_panel
from synth.projection import project_deployment
from synth.terraform_emit import emit_terraform
from synth.topology import select_topology


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
    return {"sources": list(sources.values()), "by_agent": by_agent}


def _source_ids(evidence_pack: dict, *agents: str, limit: int = 3) -> list[str]:
    source_ids: list[str] = []
    for agent in agents:
        for source in evidence_pack["by_agent"].get(agent, []):
            source_id = source["source_id"]
            if source_id not in source_ids:
                source_ids.append(source_id)
            if len(source_ids) >= limit:
                return source_ids
    return source_ids


def _evidence_chunks(evidence_pack: dict, *agents: str, limit: int = 2) -> list[dict]:
    chunks: list[dict] = []
    seen: set[str] = set()
    for agent in agents:
        for source in evidence_pack["by_agent"].get(agent, []):
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            chunks.append(
                {
                    "source_id": source_id,
                    "section": source.get("section") or "",
                    "reasoning_chunk": source.get("snippet") or "",
                }
            )
            if len(chunks) >= limit:
                return chunks
    return chunks


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
    return {
        "area": area,
        "choice": choice,
        "rationale": rationale,
        "reasoning_steps": reasoning_steps,
        "tradeoff": tradeoff,
        "validation": validation,
        "source_ids": _source_ids(evidence_pack, *agents),
        "evidence_chunks": _evidence_chunks(evidence_pack, *agents),
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
                f"Topology key `{topology['key']}` determines whether lexical, dense, or hybrid retrieval is mandatory.",
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
            agents=("retrieval", "evaluation"),
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
        sources = ", ".join(decision.get("source_ids") or [])
        line = f"- {area}: {choice}"
        if decision.get("rationale"):
            line += f"\n  why: {decision['rationale']}"
        if decision.get("tradeoff"):
            line += f"\n  tradeoff: {decision['tradeoff']}"
        if decision.get("validation"):
            line += f"\n  validate: {decision['validation']}"
        if sources:
            line += f"\n  source_ids: {sources}"
        lines.append(line)
    return "\n".join(lines)


def _requirement_summary(state: AdvisorState) -> str:
    lines = []
    for entry in state.decision_log[:12]:
        lines.append(f"- {entry.attr}: {entry.value} ({entry.source}, confidence {entry.confidence:.2f})")
    if state.pending_elicitation:
        lines.append("- pending elicitation: " + ", ".join(state.pending_elicitation))
    return "\n".join(lines)


def _source_summary(evidence_pack: dict, limit: int = 10) -> str:
    lines = []
    for source in evidence_pack["sources"][:limit]:
        source_id = source.get("source_id") or "unknown"
        section = source.get("section") or "Unsectioned"
        snippet = source.get("snippet") or ""
        lines.append(f"- {source_id}: {section}. Reasoning chunk: {snippet}")
    return "\n".join(lines)


def _hard_constraint_summary(state: AdvisorState) -> str:
    if not state.hard_constraints:
        return "- none"
    return "\n".join(f"- {constraint}" for constraint in state.hard_constraints)


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
        "requirements, decisions, and source IDs. Do not invent new sources, products, "
        "or requirements. Explain the reasoning behind each major decision, including "
        "the tradeoff accepted and the validation gate that should catch regressions."
    )
    prompt = f"""
User brief:
{state.user_brief}

Selected topology:
{topology.get("name")} ({topology.get("key")})
{topology.get("rationale")}

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

Mention source IDs inline where they support a claim. Prefer reasoning chunks
over source filenames; do not list file paths.
""".strip()
    return system, prompt


def _fallback_answer(topology: dict, architecture_decisions: list[dict]) -> str:
    lines = [
        "### Recommendation",
        f"Use {topology.get('name', 'the selected topology')} for this brief.",
        "",
        "### Why each decision was made",
    ]
    for decision in architecture_decisions:
        source_ids = " ".join(f"`{source_id}`" for source_id in decision.get("source_ids") or [])
        lines.append(f"- **{decision.get('area', 'decision')}:** {decision.get('choice', 'Pending')} {source_ids}")
        lines.append(f"  {decision.get('rationale', '')}")
        for step in decision.get("reasoning_steps") or []:
            lines.append(f"  - {step}")
    lines.append("")
    lines.append("### Accepted tradeoffs")
    for decision in architecture_decisions:
        lines.append(f"- **{decision.get('area', 'decision')}:** {decision.get('tradeoff', 'No tradeoff recorded.')}")
    lines.extend(
        [
            "",
            "### What to validate next",
        ]
    )
    for decision in architecture_decisions:
        lines.append(f"- **{decision.get('area', 'decision')}:** {decision.get('validation', 'Run the gold-set gates.')}")
    return "\n".join(lines)


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
        return _fallback_answer(topology, architecture_decisions), {
            "status": "fallback",
            "provider": getattr(provider, "name", "unknown"),
            "model": getattr(provider, "model", None),
            "reason": str(exc),
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
        for source in evidence_pack.get("sources", [])
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
