from __future__ import annotations

from functools import lru_cache

from ingestion.build_index import build_index
from retrieval.index import HybridRetriever, SearchResult


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    store = build_index()
    return HybridRetriever(store.chunks)


def retrieve(
    query: str,
    namespace: str = "knowledge",
    top_k: int = 8,
    filters: dict[str, str] | None = None,
) -> list[SearchResult]:
    return get_retriever().search(query, top_k=top_k, namespace=namespace, filters=filters)
