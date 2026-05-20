from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
from typing import Callable

from graph.edges import SPECIALIST_NAMES
from graph.state import AdvisorState, Finding, SourceRef
from retrieval.index import SearchResult
from retrieval.service import get_retriever, retrieve


FOCUS_QUERIES = {
    "retrieval": "production hybrid RAG pipeline BM25 dense RRF cross encoder rerank exact terminology two-stage",
    "security": "RBAC permission-aware retrieval ACL propagation pre-filter post-filter audit lineage",
    "cloud_iac": "embedding dimension lower higher storage recall quality vector search blue-green dimension changes managed vector options model endpoints observability",
    "evaluation": "RAG evaluation gold set retrieval metrics nDCG MRR citation latency percentiles CI",
}
RAW_CORPUS_PATH_RE = re.compile(r"\bcorpus/(?:[^\s`),;]+)?")


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
        element_type=str(chunk.metadata.get("element_type") or ""),
        snippet=_snippet(chunk.text_original),
        url=chunk.metadata.get("source_url"),
    )


def _snippet(text: str, limit: int = 240) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped in {"---", "```", "```text", "```python", "```json", "```yaml"}:
            continue
        if stripped.startswith("```"):
            continue
        if stripped.startswith("#"):
            continue
        lines.append(stripped)
    compact = _sanitize_snippet(" ".join(lines).strip() or " ".join(text.split()))
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def _sanitize_snippet(text: str) -> str:
    return RAW_CORPUS_PATH_RE.sub("the curated corpus", text)


def _run_specialist(
    name: str,
    *,
    user_brief: str,
    pending_elicitation: list[str],
    retrieve_fn: RetrieveFn,
) -> Finding:
    query = f"{user_brief} {FOCUS_QUERIES[name]}"
    results = retrieve_fn(query, "knowledge", 8, None)
    return _finding_from_results(
        name,
        results=results,
        pending_elicitation=pending_elicitation,
    )


def _finding_from_results(
    name: str,
    *,
    results: list[SearchResult],
    pending_elicitation: list[str],
) -> Finding:
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
    if retrieve_fn is None:
        batched = _run_specialists_batched(state)
        if batched is not None:
            return batched

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


def _run_specialists_batched(state: AdvisorState) -> dict[str, Finding] | None:
    retriever = get_retriever()
    search_many = getattr(retriever, "search_many", None)
    if search_many is None:
        return None

    pending_elicitation = list(state.pending_elicitation)
    names = list(SPECIALIST_NAMES)
    queries = [f"{state.user_brief} {FOCUS_QUERIES[name]}" for name in names]
    try:
        shared_dense = getattr(retriever, "search_many_with_shared_dense", None)
        if _env_bool("SPECIALIST_SHARED_DENSE_QUERY", True) and shared_dense is not None:
            result_batches = shared_dense(
                queries,
                state.user_brief,
                top_k=8,
                namespace="knowledge",
                filters=None,
            )
        else:
            result_batches = search_many(queries, top_k=8, namespace="knowledge", filters=None)
    except Exception:
        return None
    return {
        name: _finding_from_results(
            name,
            results=results,
            pending_elicitation=pending_elicitation,
        )
        for name, results in zip(names, result_batches)
    }


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
