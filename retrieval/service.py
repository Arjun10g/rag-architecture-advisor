from __future__ import annotations

from functools import lru_cache
import os
from typing import Protocol

from ingestion.build_index import build_index
from retrieval.chunking import Chunk
from retrieval.embeddings import DenseVectorIndex, EmbeddingConfig, EmbeddingUnavailable
from retrieval.index import HybridRetriever, SearchResult, reciprocal_rank_fusion
from retrieval.rerank import ColbertReranker, RerankerUnavailable
from retrieval.vector_store import (
    LanceDBVectorIndex,
    QdrantVectorIndex,
    VectorStoreConfig,
    VectorStoreUnavailable,
)


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


class BatchRetriever(Retriever, Protocol):
    def search_many(
        self,
        queries: list[str],
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[list[SearchResult]]:
        ...


class DenseOnlyRetriever:
    def __init__(self, dense: Retriever):
        self.dense = dense

    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        return self.dense.search(query, top_k=top_k, namespace=namespace, filters=filters)

    def search_many(
        self,
        queries: list[str],
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[list[SearchResult]]:
        if hasattr(self.dense, "search_many"):
            return self.dense.search_many(queries, top_k=top_k, namespace=namespace, filters=filters)
        return [
            self.search(query, top_k=top_k, namespace=namespace, filters=filters)
            for query in queries
        ]


class DenseHybridRetriever:
    def __init__(
        self,
        lexical: HybridRetriever,
        dense: Retriever,
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

    def search_many(
        self,
        queries: list[str],
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[list[SearchResult]]:
        lexical_batches = (
            self.lexical.search_many(
                queries,
                top_k=self.lexical_top_k,
                namespace=namespace,
                filters=filters,
            )
            if hasattr(self.lexical, "search_many")
            else [
                self.lexical.search(
                    query,
                    top_k=self.lexical_top_k,
                    namespace=namespace,
                    filters=filters,
                )
                for query in queries
            ]
        )
        dense_batches = (
            self.dense.search_many(
                queries,
                top_k=self.dense_top_k,
                namespace=namespace,
                filters=filters,
            )
            if hasattr(self.dense, "search_many")
            else [
                self.dense.search(
                    query,
                    top_k=self.dense_top_k,
                    namespace=namespace,
                    filters=filters,
                )
                for query in queries
            ]
        )
        return [
            self._fuse_results(lexical_results, dense_results, top_k=top_k)
            for lexical_results, dense_results in zip(lexical_batches, dense_batches)
        ]

    def _fuse_results(
        self,
        lexical_results: list[SearchResult],
        dense_results: list[SearchResult],
        *,
        top_k: int,
    ) -> list[SearchResult]:
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


class RerankRetriever:
    def __init__(
        self,
        base: Retriever,
        reranker: ColbertReranker,
        *,
        candidate_top_k: int = 50,
        allow_fallback: bool = True,
    ):
        self.base = base
        self.reranker = reranker
        self.candidate_top_k = candidate_top_k
        self.allow_fallback = allow_fallback

    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        candidates = self.base.search(
            query,
            top_k=max(top_k, self.candidate_top_k),
            namespace=namespace,
            filters=filters,
        )
        try:
            return self.reranker.rerank(query, candidates, top_k=top_k)
        except RerankerUnavailable:
            if self.allow_fallback:
                return candidates[:top_k]
            raise


def build_retriever(
    chunks: list[Chunk],
    *,
    mode: str = "lexical",
    embedding_config: EmbeddingConfig | None = None,
    embedding_dimension: int | None = None,
    vector_store_config: VectorStoreConfig | None = None,
    rebuild_embeddings: bool = False,
    allow_fallback: bool = True,
) -> Retriever:
    mode = mode.lower().strip()
    use_colbert = mode.endswith("_colbert") or mode == "colbert"
    base_mode = "lexical" if mode == "colbert" else mode.removesuffix("_colbert")
    lexical = HybridRetriever(chunks)
    if base_mode == "lexical":
        retriever: Retriever = lexical
    elif base_mode in {"dense", "hybrid"}:
        try:
            dense = _build_dense_index(
                chunks,
                embedding_config=embedding_config,
                dimension=embedding_dimension,
                vector_store_config=vector_store_config,
                rebuild=rebuild_embeddings,
            )
        except (EmbeddingUnavailable, VectorStoreUnavailable):
            if allow_fallback:
                retriever = lexical
                dense = None
            else:
                raise

        if dense is None:
            pass
        elif base_mode == "dense":
            retriever = DenseOnlyRetriever(dense)
        elif base_mode == "hybrid":
            retriever = DenseHybridRetriever(
                lexical,
                dense,
                lexical_top_k=_env_int("LEXICAL_TOP_K", 100),
                dense_top_k=_env_int("DENSE_TOP_K", 100),
                rrf_k=_env_int("FUSION_RRF_K", 60),
                lexical_weight=_env_float("LEXICAL_WEIGHT", 1.0),
                dense_weight=_env_float("DENSE_WEIGHT", 1.0),
            )
    else:
        raise ValueError(
            f"Unknown RETRIEVAL_MODE {mode!r}; expected lexical, dense, hybrid, or *_colbert."
        )

    if use_colbert:
        return RerankRetriever(
            retriever,
            ColbertReranker.from_env(),
            candidate_top_k=_env_int("COLBERT_CANDIDATE_TOP_K", 50),
            allow_fallback=allow_fallback,
        )
    return retriever


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    store = build_index()
    return build_retriever(
        store.chunks,
        mode=os.getenv("RETRIEVAL_MODE", "lexical"),
        embedding_config=EmbeddingConfig.from_env(),
        embedding_dimension=_optional_env_int("EMBEDDING_DIM"),
        vector_store_config=VectorStoreConfig.from_env(),
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


def _build_dense_index(
    chunks: list[Chunk],
    *,
    embedding_config: EmbeddingConfig | None,
    dimension: int | None,
    vector_store_config: VectorStoreConfig | None,
    rebuild: bool,
) -> Retriever:
    vector_store_config = vector_store_config or VectorStoreConfig.from_env()
    backend = vector_store_config.normalized_backend
    if backend in {"memory", "in_memory", "local"}:
        return DenseVectorIndex.from_chunks(
            chunks,
            config=embedding_config,
            dimension=dimension,
            rebuild=rebuild,
        )
    if backend in {"lance", "lancedb"}:
        return LanceDBVectorIndex.from_chunks(
            chunks,
            store_config=vector_store_config,
            embedding_config=embedding_config,
            dimension=dimension,
            rebuild=rebuild,
        )
    if backend == "qdrant":
        return QdrantVectorIndex.from_chunks(
            chunks,
            store_config=vector_store_config,
            embedding_config=embedding_config,
            dimension=dimension,
            rebuild=rebuild,
        )
    raise VectorStoreUnavailable(
        f"Unknown VECTOR_STORE_BACKEND {vector_store_config.backend!r}; "
        "expected memory, lancedb, or qdrant."
    )
