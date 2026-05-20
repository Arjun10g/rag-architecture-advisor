from __future__ import annotations

from graph.edges import SPECIALIST_NAMES
from graph.state import AdvisorState, Finding, SourceRef
from retrieval.index import SearchResult
from retrieval.service import retrieve


FOCUS_QUERIES = {
    "retrieval": "hybrid retrieval reranking chunking pipeline decision",
    "security": "permission aware retrieval pii redaction audit lineage security governance",
    "cloud_iac": "terraform cloud platform mapping vector database model endpoint observability",
    "evaluation": "rag evaluation gold set faithfulness routing topology metrics ci",
}


def _source_ref(result: SearchResult) -> SourceRef:
    chunk = result.chunk
    section = " > ".join(chunk.metadata.get("section_path") or [])
    return SourceRef(
        source_id=chunk.chunk_id,
        title=chunk.title,
        section=section,
        source_path=str(chunk.metadata.get("source_path") or chunk.source_path),
        score=round(result.score, 6),
        snippet=_snippet(chunk.text_original),
    )


def _snippet(text: str, limit: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def run_specialists(state: AdvisorState) -> dict[str, Finding]:
    findings: dict[str, Finding] = {}
    for name in SPECIALIST_NAMES:
        query = f"{state.user_brief} {FOCUS_QUERIES[name]}"
        results = retrieve(query, namespace="knowledge", top_k=5)
        sources = [_source_ref(result) for result in results]
        source_ids = [source.source_id for source in sources]
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
            sources=sources,
        )
    return findings
