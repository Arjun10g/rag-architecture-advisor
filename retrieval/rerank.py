from __future__ import annotations

try:
    import spaces
except ImportError:  # pragma: no cover
    spaces = None

from retrieval.index import SearchResult


def _gpu_decorator(fn):
    if spaces is None:
        return fn
    return spaces.GPU(fn)


@_gpu_decorator
def rerank(query: str, results: list[SearchResult], top_k: int = 8) -> list[SearchResult]:
    return results[:top_k]

