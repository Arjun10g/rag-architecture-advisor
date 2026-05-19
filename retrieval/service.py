from __future__ import annotations

from functools import lru_cache
import os
from typing import Protocol

from ingestion.build_index import build_index
from retrieval.chunking import Chunk
from retrieval.embeddings import DenseVectorIndex, EmbeddingConfig, EmbeddingUnavailable
from retrieval.index import HybridRetriever, SearchResult, reciprocal_rank_fusion


try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


if load_dotenv:
    load_dotenv()


class Retriever(Protocol):
    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        ...


class DenseOnlyRetriever:
    def __init__(self, dense: DenseVectorIndex):
        self.dense = dense

    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        return self.dense.search(query, top_k=top_k, namespace=namespace, filters=filters)


class DenseHybridRetriever:
    def __init__(
        self,
        lexical: HybridRetriever,
        dense: DenseVectorIndex,
        *,
        lexical_top_k: int = 100,
        dense_top_k: int = 100,
        rrf_k: int = 60,
        lexical_weight: float = 1.0,
        dense_weight: float = 1.0,
    ):
        self.lexical = lexical
        self.dense = dense
        self.lexical_top_k = lexical_top_k
        self.dense_top_k = dense_top_k
        self.rrf_k = rrf_k
        self.lexical_weight = lexical_weight
        self.dense_weight = dense_weight

    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        lexical_results = self.lexical.search(
            query, top_k=self.lexical_top_k, namespace=namespace, filters=filters
        )
        dense_results = self.dense.search(
            query, top_k=self.dense_top_k, namespace=namespace, filters=filters
        )
        by_id = {result.chunk.chunk_id: result.chunk for result in lexical_results + dense_results}
        rankings = [
            [result.chunk.chunk_id for result in lexical_results],
            [result.chunk.chunk_id for result in dense_results],
        ]
        fused = reciprocal_rank_fusion(
            rankings,
            k=self.rrf_k,
            weights=[self.lexical_weight, self.dense_weight],
        )
        return [
            SearchResult(chunk=by_id[chunk_id], score=score)
            for chunk_id, score in fused[:top_k]
        ]


def build_retriever(
    chunks: list[Chunk],
    *,
    mode: str = "lexical",
    embedding_config: EmbeddingConfig | None = None,
    embedding_dimension: int | None = None,
    rebuild_embeddings: bool = False,
    allow_fallback: bool = True,
) -> Retriever:
    mode = mode.lower().strip()
    lexical = HybridRetriever(chunks)
    if mode == "lexical":
        return lexical

    try:
        dense = DenseVectorIndex.from_chunks(
            chunks,
            config=embedding_config,
            dimension=embedding_dimension,
            rebuild=rebuild_embeddings,
        )
    except EmbeddingUnavailable:
        if allow_fallback:
            return lexical
        raise

    if mode == "dense":
        return DenseOnlyRetriever(dense)
    if mode == "hybrid":
        return DenseHybridRetriever(
            lexical,
            dense,
            lexical_top_k=_env_int("LEXICAL_TOP_K", 100),
            dense_top_k=_env_int("DENSE_TOP_K", 100),
            rrf_k=_env_int("FUSION_RRF_K", 60),
            lexical_weight=_env_float("LEXICAL_WEIGHT", 1.0),
            dense_weight=_env_float("DENSE_WEIGHT", 1.0),
        )
    raise ValueError(f"Unknown RETRIEVAL_MODE {mode!r}; expected lexical, dense, or hybrid.")


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    store = build_index()
    return build_retriever(
        store.chunks,
        mode=os.getenv("RETRIEVAL_MODE", "lexical"),
        embedding_config=EmbeddingConfig.from_env(),
        embedding_dimension=_optional_env_int("EMBEDDING_DIM"),
        allow_fallback=os.getenv("RETRIEVAL_STRICT_DENSE", "false").lower() != "true",
    )


def retrieve(
    query: str,
    namespace: str = "knowledge",
    top_k: int = 8,
    filters: dict[str, str] | None = None,
) -> list[SearchResult]:
    return get_retriever().search(query, top_k=top_k, namespace=namespace, filters=filters)


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return int(value)


def _optional_env_int(key: str) -> int | None:
    value = os.getenv(key)
    if value is None or not value.strip():
        return None
    return int(value)


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return float(value)
