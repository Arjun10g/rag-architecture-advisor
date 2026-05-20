from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

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


RetrieveFn = Callable[[str, str, int, dict[str, str] | None], list[SearchResult]]


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


def _run_specialist(
    name: str,
    *,
    user_brief: str,
    pending_elicitation: list[str],
    retrieve_fn: RetrieveFn,
) -> Finding:
    query = f"{user_brief} {FOCUS_QUERIES[name]}"
    results = retrieve_fn(query, "knowledge", 5, None)
    sources = [_source_ref(result) for result in results]
    source_ids = [source.source_id for source in sources]
    top_sections = [
        " > ".join(result.chunk.metadata.get("section_path") or [])
        for result in results[:3]
    ]
    return Finding(
        agent=name,
        recommendation=f"{name} specialist retrieved {len(results)} grounded candidates.",
        decisions=top_sections or ["No retrieval candidates found."],
        open_questions=list(pending_elicitation),
        source_ids=source_ids,
        sources=sources,
    )


def _failed_finding(name: str, exc: Exception, pending_elicitation: list[str]) -> Finding:
    return Finding(
        agent=name,
        recommendation=f"{name} specialist could not retrieve grounded candidates.",
        decisions=["Specialist failed gracefully and returned an explicit gap."],
        open_questions=[*pending_elicitation, f"{name} retrieval failed: {exc}"],
        source_ids=[],
        sources=[],
    )


def run_specialists(
    state: AdvisorState,
    retrieve_fn: RetrieveFn | None = None,
) -> dict[str, Finding]:
    retrieve_fn = retrieve_fn or retrieve
    findings: dict[str, Finding] = {}
    pending_elicitation = list(state.pending_elicitation)
    with ThreadPoolExecutor(max_workers=len(SPECIALIST_NAMES)) as executor:
        futures = {
            executor.submit(
                _run_specialist,
                name,
                user_brief=state.user_brief,
                pending_elicitation=pending_elicitation,
                retrieve_fn=retrieve_fn,
            ): name
            for name in SPECIALIST_NAMES
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                findings[name] = future.result()
            except Exception as exc:
                findings[name] = _failed_finding(name, exc, pending_elicitation)

    return {name: findings[name] for name in SPECIALIST_NAMES}
