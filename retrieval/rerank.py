from __future__ import annotations

from dataclasses import dataclass
import os

try:
    import spaces
except ImportError:  # pragma: no cover
    spaces = None

from retrieval.index import SearchResult


DEFAULT_COLBERT_MODEL = "answerdotai/answerai-colbert-small-v1"
_RERANKER_CACHE = {}


class RerankerUnavailable(RuntimeError):
    """Raised when optional reranking dependencies or model files are unavailable."""


@dataclass
class ColbertReranker:
    model_name: str = DEFAULT_COLBERT_MODEL
    device: str | None = None

    def __post_init__(self) -> None:
        self._ranker = None

    @classmethod
    def from_env(cls) -> "ColbertReranker":
        return cls(
            model_name=os.getenv("COLBERT_MODEL", DEFAULT_COLBERT_MODEL),
            device=os.getenv("COLBERT_DEVICE") or None,
        )

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 8,
    ) -> list[SearchResult]:
        if not results:
            return []
        docs = [result.chunk.text_for_embedding for result in results]
        try:
            ranked = self._load().rank(
                query=query,
                docs=docs,
                doc_ids=list(range(len(results))),
            )
        except Exception as exc:  # pragma: no cover - optional ML runtime/model cache.
            raise RerankerUnavailable(f"Could not rerank with {self.model_name}: {exc}") from exc

        ordered = []
        for item in ranked.top_k(min(top_k, len(results))):
            doc_id = int(item.document.doc_id)
            ordered.append(SearchResult(chunk=results[doc_id].chunk, score=float(item.score)))
        return ordered

    def _load(self):
        if self._ranker is not None:
            return self._ranker
        cache_key = (self.model_name, self.device)
        if cache_key in _RERANKER_CACHE:
            self._ranker = _RERANKER_CACHE[cache_key]
            return self._ranker
        try:
            from rerankers import Reranker
        except ImportError as exc:  # pragma: no cover - optional dependency.
            raise RerankerUnavailable(
                "rerankers is not installed; run "
                "`python3 -m pip install 'rerankers[transformers]'` before ColBERT ablations."
            ) from exc

        kwargs = {"model_type": "colbert"}
        if self.device:
            kwargs["device"] = self.device
        try:
            self._ranker = Reranker(self.model_name, **kwargs)
        except Exception as exc:  # pragma: no cover - depends on local model/network availability.
            raise RerankerUnavailable(f"Could not load ColBERT model {self.model_name}: {exc}") from exc
        _RERANKER_CACHE[cache_key] = self._ranker
        return self._ranker


def _gpu_decorator(fn):
    if spaces is None:
        return fn
    return spaces.GPU(fn)


@_gpu_decorator
def rerank(query: str, results: list[SearchResult], top_k: int = 8) -> list[SearchResult]:
    return results[:top_k]
