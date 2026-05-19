from __future__ import annotations

from graph.edges import SPECIALIST_NAMES
from graph.state import AdvisorState, Finding
from retrieval.service import retrieve


FOCUS_QUERIES = {
    "retrieval": "hybrid retrieval reranking chunking pipeline decision",
    "security": "permission aware retrieval pii redaction audit lineage security governance",
    "cloud_iac": "terraform cloud platform mapping vector database model endpoint observability",
    "evaluation": "rag evaluation gold set faithfulness routing topology metrics ci",
}


def run_specialists(state: AdvisorState) -> dict[str, Finding]:
    findings: dict[str, Finding] = {}
    for name in SPECIALIST_NAMES:
        query = f"{state.user_brief} {FOCUS_QUERIES[name]}"
        results = retrieve(query, namespace="knowledge", top_k=5)
        source_ids = [result.chunk.chunk_id for result in results]
        top_sections = [
            " > ".join(result.chunk.metadata.get("section_path") or [])
            for result in results[:3]
        ]
        findings[name] = Finding(
            agent=name,
            recommendation=f"{name} specialist retrieved {len(results)} grounded candidates.",
            decisions=top_sections or ["No retrieval candidates found."],
            open_questions=list(state.pending_elicitation),
            source_ids=source_ids,
        )
    return findings
