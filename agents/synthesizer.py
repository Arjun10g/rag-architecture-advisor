from __future__ import annotations

from dataclasses import asdict

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
        {
            "area": "retrieval_strategy",
            "choice": _retrieval_choice(topology),
            "rationale": (
                "The selected topology needs both semantic recall and exact terminology handling, "
                "so candidate generation should be grounded in the retrieval evidence rather than "
                "chosen from the router output alone."
            ),
            "source_ids": _source_ids(evidence_pack, "retrieval"),
        },
        {
            "area": "reranking",
            "choice": _rerank_choice(topology),
            "rationale": (
                "Reranking is tied to the topology risk profile and should be evaluated as a "
                "separate stage with bounded fanout."
            ),
            "source_ids": _source_ids(evidence_pack, "retrieval", "evaluation"),
        },
        {
            "area": "embedding_dimension",
            "choice": "Use 1024-dimensional Matryoshka embeddings for quality; keep 512d as the speed profile",
            "rationale": (
                "The dimension choice is explicit so the production profile and the low-latency "
                "profile can be compared under the same gold sets."
            ),
            "source_ids": _source_ids(evidence_pack, "retrieval", "evaluation"),
        },
        {
            "area": "vector_database",
            "choice": "Managed vector index with lexical sidecar, metadata filters, and blue-green index aliases",
            "rationale": (
                "The deployment needs vector search, exact-match support, safe reindexing, and "
                "metadata-aware filtering rather than a bare embedding store."
            ),
            "source_ids": _source_ids(evidence_pack, "cloud_iac", "retrieval"),
        },
        {
            "area": "deployment",
            "choice": "Provision " + ", ".join(component["id"] for component in projection["deployment_components"]),
            "rationale": (
                "The Terraform sketch follows the retrieved IaC guidance by separating compute, "
                "storage, database, security, monitoring, and scaling concerns."
            ),
            "source_ids": _source_ids(evidence_pack, "cloud_iac"),
        },
        {
            "area": "security_governance",
            "choice": "Apply ACL-aware retrieval before prompt construction and retain audit lineage",
            "rationale": (
                "Security controls are represented as retrieval-time constraints, not only as "
                "post-generation review."
            ),
            "source_ids": _source_ids(evidence_pack, "security"),
        },
        {
            "area": "evaluation",
            "choice": "Gate retrieval, routing, topology, answer citations, and latency percentiles in CI",
            "rationale": (
                "The recommendation remains auditable only if source coverage and p50/p95/p99 "
                "latency stay visible in the gold-set reports."
            ),
            "source_ids": _source_ids(evidence_pack, "evaluation", "retrieval"),
        },
    ]


def _decision_summary(decisions: list[dict]) -> str:
    lines = []
    for decision in decisions:
        area = str(decision.get("area") or "decision")
        choice = str(decision.get("choice") or "Pending")
        sources = ", ".join(decision.get("source_ids") or [])
        line = f"- {area}: {choice}"
        if sources:
            line += f" [sources: {sources}]"
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
        title = source.get("title") or "Untitled"
        section = source.get("section") or "Unsectioned"
        snippet = source.get("snippet") or ""
        lines.append(f"- {source_id}: {title} / {section}. {snippet}")
    return "\n".join(lines)


def _generation_prompt(
    state: AdvisorState,
    topology: dict,
    architecture_decisions: list[dict],
    evidence_pack: dict,
) -> tuple[str, str]:
    system = (
        "You are a precise RAG architecture advisor. Write only from the supplied "
        "requirements, decisions, and source IDs. Do not invent new sources, products, "
        "or requirements. Keep the answer concise and citation-aware."
    )
    prompt = f"""
User brief:
{state.user_brief}

Selected topology:
{topology.get("name")} ({topology.get("key")})
{topology.get("rationale")}

Resolved requirement vector:
{_requirement_summary(state)}

Architecture decisions:
{_decision_summary(architecture_decisions)}

Evidence snippets:
{_source_summary(evidence_pack)}

Write a final recommendation in three short sections:
1. Recommendation
2. Key tradeoffs
3. What to validate next

Mention source IDs inline where they support a claim.
""".strip()
    return system, prompt


def _fallback_answer(topology: dict, architecture_decisions: list[dict]) -> str:
    lines = [
        f"### Recommendation",
        f"Use {topology.get('name', 'the selected topology')} for this brief.",
        "",
        "### Key tradeoffs",
    ]
    for decision in architecture_decisions[:4]:
        source_ids = " ".join(f"`{source_id}`" for source_id in decision.get("source_ids") or [])
        lines.append(f"- {decision.get('area', 'decision')}: {decision.get('choice', 'Pending')} {source_ids}")
    lines.extend(
        [
            "",
            "### What to validate next",
            "- Run the gold-set retrieval and answer gates after changing retrieval mode, embedding dimension, or reranker settings.",
        ]
    )
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
    return {
        "topology": topology,
        "projection": projection,
        "terraform": emit_terraform(topology, projection),
        "panel": build_panel(state, topology),
        "evidence_pack": evidence_pack,
        "architecture_decisions": architecture_decisions,
        "sources": evidence_pack["sources"],
        "generated_answer": generated_answer,
        "generation": generation,
    }
