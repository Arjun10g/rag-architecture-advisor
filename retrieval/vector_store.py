from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from typing import Any
import uuid

from retrieval.chunking import Chunk
from retrieval.embeddings import DenseVectorIndex, EmbeddingConfig, SentenceTransformerEmbedder
from retrieval.index import SearchResult


DEFAULT_VECTOR_INDEX_DIR = "corpus/index/lancedb"
DEFAULT_VECTOR_TABLE_NAME = "chunks"
QDRANT_POINT_NAMESPACE = uuid.UUID("7a6f8a86-6df5-4d0f-b5e5-6b4198ea4b7d")
INDEXED_FILTER_COLUMNS = {
    "chunk_id",
    "document_id",
    "parent_id",
    "source_path",
    "namespace",
    "domain",
    "content_kind",
    "trust_tier",
    "volatility",
    "contested",
    "element_type",
    "embedding_model",
    "embedding_dimension",
    "embedding_native_dimension",
}


class VectorStoreUnavailable(RuntimeError):
    """Raised when an optional vector-store backend cannot be used."""


@dataclass(frozen=True)
class VectorStoreConfig:
    backend: str = "memory"
    index_dir: str = DEFAULT_VECTOR_INDEX_DIR
    table_name: str = DEFAULT_VECTOR_TABLE_NAME
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_local_path: str = ""
    qdrant_prefer_grpc: bool = False
    qdrant_timeout_seconds: int = 30
    qdrant_upload_batch_size: int = 128

    @classmethod
    def from_env(cls) -> "VectorStoreConfig":
        return cls(
            backend=os.getenv("VECTOR_STORE_BACKEND", "memory"),
            index_dir=os.getenv("VECTOR_INDEX_DIR", DEFAULT_VECTOR_INDEX_DIR),
            table_name=os.getenv("VECTOR_TABLE_NAME", DEFAULT_VECTOR_TABLE_NAME),
            qdrant_url=os.getenv("QDRANT_URL", ""),
            qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
            qdrant_local_path=os.getenv("QDRANT_LOCAL_PATH", ""),
            qdrant_prefer_grpc=_env_bool("QDRANT_PREFER_GRPC", False),
            qdrant_timeout_seconds=_env_int("QDRANT_TIMEOUT_SECONDS", 30),
            qdrant_upload_batch_size=_env_int("QDRANT_UPLOAD_BATCH_SIZE", 128),
        )

    @property
    def normalized_backend(self) -> str:
        return self.backend.lower().strip()


class LanceDBVectorIndex:
    """Persisted LanceDB vector index with the same search API as DenseVectorIndex."""

    def __init__(
        self,
        chunks: list[Chunk],
        table: Any | None,
        embedder: SentenceTransformerEmbedder,
        dimension: int,
        table_name: str = "",
    ):
        self.chunks = chunks
        self.table = table
        self.embedder = embedder
        self.dimension = dimension
        self.table_name = table_name
        self._chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}

    @classmethod
    def from_chunks(
        cls,
        chunks: list[Chunk],
        store_config: VectorStoreConfig | None = None,
        embedding_config: EmbeddingConfig | None = None,
        *,
        dimension: int | None = None,
        rebuild: bool = False,
    ) -> "LanceDBVectorIndex":
        store_config = store_config or VectorStoreConfig.from_env()
        embedding_config = embedding_config or EmbeddingConfig.from_env()
        dimension = dimension or embedding_config.native_dimension
        embedder = SentenceTransformerEmbedder(embedding_config)

        if not chunks:
            return cls(chunks=[], table=None, embedder=embedder, dimension=dimension)

        lancedb = _import_lancedb()
        index_dir = Path(store_config.index_dir)
        _bootstrap_index_dir(index_dir)
        index_dir.mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(index_dir.as_posix())
        table_name = table_name_for_dimension(store_config.table_name, dimension)

        table = None
        table_names = _table_names(db)
        if not rebuild and table_name in table_names:
            candidate = db.open_table(table_name)
            if _table_matches_chunks(candidate, chunks, embedding_config, dimension):
                table = candidate

        if table is None:
            dense = DenseVectorIndex.from_chunks(
                chunks,
                config=embedding_config,
                dimension=dimension,
                rebuild=rebuild,
            )
            rows = [
                _row_for_chunk(chunk, vector, embedding_config, dimension)
                for chunk, vector in zip(chunks, dense.vectors)
            ]
            db.drop_table(table_name, ignore_missing=True)
            table = db.create_table(table_name, data=rows)

        return cls(
            chunks=chunks,
            table=table,
            embedder=embedder,
            dimension=dimension,
            table_name=table_name,
        )

    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        if self.table is None or top_k < 1:
            return []

        filters = filters or {}
        query_vector = self.embedder.encode([query], is_query=True, dimension=self.dimension)[0]
        query_builder = self.table.search(query_vector)
        indexed_filters = _indexed_filters(namespace, filters)
        where_clause = _where_clause(indexed_filters)
        if where_clause:
            query_builder = query_builder.where(where_clause)

        rows = query_builder.limit(_candidate_limit(top_k, filters)).to_list()
        results: list[SearchResult] = []
        for row in rows:
            chunk = self._chunks_by_id.get(str(row.get("chunk_id", "")))
            if chunk is None:
                continue
            if not _metadata_matches(chunk, namespace, filters):
                continue
            results.append(SearchResult(chunk=chunk, score=_score_from_lance_row(row)))
            if len(results) >= top_k:
                break
        return results


class QdrantVectorIndex:
    """Qdrant-backed vector index using the same search API as DenseVectorIndex."""

    def __init__(
        self,
        chunks: list[Chunk],
        client: Any | None,
        embedder: SentenceTransformerEmbedder,
        dimension: int,
        collection_name: str = "",
        timeout_seconds: int = 30,
    ):
        self.chunks = chunks
        self.client = client
        self.embedder = embedder
        self.dimension = dimension
        self.collection_name = collection_name
        self.table_name = collection_name
        self.timeout_seconds = timeout_seconds
        self._chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}

    @classmethod
    def from_chunks(
        cls,
        chunks: list[Chunk],
        store_config: VectorStoreConfig | None = None,
        embedding_config: EmbeddingConfig | None = None,
        *,
        dimension: int | None = None,
        rebuild: bool = False,
        client: Any | None = None,
    ) -> "QdrantVectorIndex":
        store_config = store_config or VectorStoreConfig.from_env()
        embedding_config = embedding_config or EmbeddingConfig.from_env()
        dimension = dimension or embedding_config.native_dimension
        embedder = SentenceTransformerEmbedder(embedding_config)
        collection_name = table_name_for_dimension(store_config.table_name, dimension)

        if not chunks:
            return cls(
                chunks=[],
                client=client,
                embedder=embedder,
                dimension=dimension,
                collection_name=collection_name,
                timeout_seconds=store_config.qdrant_timeout_seconds,
            )

        qdrant_client = client or _build_qdrant_client(store_config)
        collection_exists = qdrant_client.collection_exists(collection_name)
        if rebuild and collection_exists:
            qdrant_client.delete_collection(
                collection_name=collection_name,
                timeout=store_config.qdrant_timeout_seconds,
            )
            collection_exists = False

        if collection_exists:
            if not _qdrant_collection_matches(
                qdrant_client,
                collection_name,
                chunks,
                embedding_config,
                dimension,
                store_config.qdrant_timeout_seconds,
            ):
                raise VectorStoreUnavailable(
                    f"Qdrant collection {collection_name!r} already exists but does not "
                    "match this corpus/model/dimension; refusing to overwrite without rebuild."
                )
        else:
            _create_qdrant_collection(
                qdrant_client,
                collection_name,
                dimension,
                timeout_seconds=store_config.qdrant_timeout_seconds,
            )
            dense = DenseVectorIndex.from_chunks(
                chunks,
                config=embedding_config,
                dimension=dimension,
                rebuild=rebuild,
            )
            _upload_qdrant_points(
                qdrant_client,
                collection_name,
                chunks,
                dense.vectors,
                embedding_config,
                dimension,
                batch_size=store_config.qdrant_upload_batch_size,
                timeout_seconds=store_config.qdrant_timeout_seconds,
            )

        return cls(
            chunks=chunks,
            client=qdrant_client,
            embedder=embedder,
            dimension=dimension,
            collection_name=collection_name,
            timeout_seconds=store_config.qdrant_timeout_seconds,
        )

    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        if self.client is None or top_k < 1:
            return []

        filters = filters or {}
        query_vector = self.embedder.encode([query], is_query=True, dimension=self.dimension)[0]
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=_qdrant_filter(namespace, filters),
            limit=_candidate_limit(top_k, filters),
            with_payload=["chunk_id"],
            with_vectors=False,
            timeout=self.timeout_seconds,
        )
        results: list[SearchResult] = []
        for point in response.points:
            payload = point.payload or {}
            chunk = self._chunks_by_id.get(str(payload.get("chunk_id", "")))
            if chunk is None:
                continue
            if not _metadata_matches(chunk, namespace, filters):
                continue
            results.append(SearchResult(chunk=chunk, score=float(point.score)))
            if len(results) >= top_k:
                break
        return results


def _import_lancedb() -> Any:
    try:
        import lancedb
    except ImportError as exc:  # pragma: no cover - optional deployment dependency.
        raise VectorStoreUnavailable(
            "lancedb is not installed; run `python3 -m pip install -r requirements.txt` "
            "or set VECTOR_STORE_BACKEND=memory."
        ) from exc
    return lancedb


def _import_qdrant() -> tuple[Any, Any]:
    try:
        from qdrant_client import QdrantClient, models
    except ImportError as exc:  # pragma: no cover - optional deployment dependency.
        raise VectorStoreUnavailable(
            "qdrant-client is not installed; run `python3 -m pip install -r requirements.txt` "
            "or set VECTOR_STORE_BACKEND=memory."
        ) from exc
    return QdrantClient, models


def _qdrant_models() -> Any:
    _, models = _import_qdrant()
    return models


def _build_qdrant_client(store_config: VectorStoreConfig) -> Any:
    QdrantClient, _ = _import_qdrant()
    if store_config.qdrant_url:
        return QdrantClient(
            url=store_config.qdrant_url,
            api_key=store_config.qdrant_api_key or None,
            prefer_grpc=store_config.qdrant_prefer_grpc,
            timeout=store_config.qdrant_timeout_seconds,
        )
    if store_config.qdrant_local_path:
        return QdrantClient(
            path=store_config.qdrant_local_path,
            timeout=store_config.qdrant_timeout_seconds,
        )
    raise VectorStoreUnavailable(
        "VECTOR_STORE_BACKEND=qdrant requires QDRANT_URL plus QDRANT_API_KEY for "
        "Qdrant Cloud, or QDRANT_LOCAL_PATH for a local Qdrant store."
    )


def table_name_for_dimension(base_name: str, dimension: int) -> str:
    if "{dimension}" in base_name:
        return base_name.format(dimension=dimension)
    suffix = f"_dim_{dimension}"
    if base_name.endswith(suffix):
        return base_name
    return f"{base_name}{suffix}"


def _bootstrap_index_dir(index_dir: Path) -> None:
    bootstrap_dir = os.getenv("VECTOR_INDEX_BOOTSTRAP_DIR", "").strip()
    if not bootstrap_dir:
        return
    source = Path(bootstrap_dir)
    if source.resolve() == index_dir.resolve():
        return
    if (index_dir / "vector_manifest.json").exists():
        return
    if not (source / "vector_manifest.json").exists():
        return
    index_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, index_dir, dirs_exist_ok=True)


def _table_names(db: Any) -> set[str]:
    if hasattr(db, "list_tables"):
        response = db.list_tables()
        return set(getattr(response, "tables", response))
    return set(db.table_names())


def _qdrant_collection_matches(
    client: Any,
    collection_name: str,
    chunks: list[Chunk],
    embedding_config: EmbeddingConfig,
    dimension: int,
    timeout_seconds: int,
) -> bool:
    try:
        if not client.collection_exists(collection_name):
            return False
        total = client.count(
            collection_name=collection_name,
            exact=True,
            timeout=timeout_seconds,
        ).count
        if int(total) != len(chunks):
            return False
        matching = client.count(
            collection_name=collection_name,
            count_filter=_qdrant_filter(
                None,
                {
                    "embedding_model": embedding_config.model_name,
                    "embedding_dimension": dimension,
                    "embedding_native_dimension": embedding_config.native_dimension,
                },
            ),
            exact=True,
            timeout=timeout_seconds,
        ).count
    except Exception:
        return False
    return int(matching) == len(chunks)


def _create_qdrant_collection(
    client: Any,
    collection_name: str,
    dimension: int,
    *,
    timeout_seconds: int,
) -> None:
    models = _qdrant_models()
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
        timeout=timeout_seconds,
    )
    _create_qdrant_payload_indexes(client, collection_name, timeout_seconds)


def _create_qdrant_payload_indexes(
    client: Any,
    collection_name: str,
    timeout_seconds: int,
) -> None:
    models = _qdrant_models()
    integer_fields = {
        "chunk_index",
        "start_line",
        "end_line",
        "embedding_dimension",
        "embedding_native_dimension",
    }
    keyword_fields = sorted(INDEXED_FILTER_COLUMNS - integer_fields)
    for field_name in keyword_fields:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
                timeout=timeout_seconds,
            )
        except Exception:
            continue
    for field_name in sorted(integer_fields):
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.INTEGER,
                wait=True,
                timeout=timeout_seconds,
            )
        except Exception:
            continue


def _upload_qdrant_points(
    client: Any,
    collection_name: str,
    chunks: list[Chunk],
    vectors: list[list[float]],
    embedding_config: EmbeddingConfig,
    dimension: int,
    *,
    batch_size: int,
    timeout_seconds: int,
) -> None:
    models = _qdrant_models()
    points = []
    for chunk, vector in zip(chunks, vectors):
        row = _row_for_chunk(chunk, vector, embedding_config, dimension)
        row.pop("vector", None)
        points.append(
            models.PointStruct(
                id=_qdrant_point_id(chunk.chunk_id),
                vector=[float(value) for value in vector],
                payload=row,
            )
        )
        if len(points) >= batch_size:
            client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
                timeout=timeout_seconds,
            )
            points = []
    if points:
        client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
            timeout=timeout_seconds,
        )


def _table_matches_chunks(
    table: Any,
    chunks: list[Chunk],
    embedding_config: EmbeddingConfig,
    dimension: int,
) -> bool:
    try:
        if table.count_rows() != len(chunks):
            return False
        frame = table.to_pandas()
        existing = set(str(value) for value in frame["chunk_id"].tolist())
    except Exception:
        return False
    expected = {chunk.chunk_id for chunk in chunks}
    if existing != expected:
        return False
    required_columns = {"embedding_model", "embedding_dimension", "embedding_native_dimension"}
    if not required_columns.issubset(set(frame.columns)):
        return False
    first_row = frame.iloc[0]
    return (
        str(first_row["embedding_model"]) == embedding_config.model_name
        and int(first_row["embedding_dimension"]) == dimension
        and int(first_row["embedding_native_dimension"]) == embedding_config.native_dimension
    )


def _row_for_chunk(
    chunk: Chunk,
    vector: list[float],
    embedding_config: EmbeddingConfig,
    dimension: int,
) -> dict[str, Any]:
    metadata = chunk.metadata
    return {
        "chunk_id": chunk.chunk_id,
        "vector": [float(value) for value in vector],
        "embedding_model": embedding_config.model_name,
        "embedding_dimension": int(dimension),
        "embedding_native_dimension": int(embedding_config.native_dimension),
        "document_id": chunk.document_id,
        "parent_id": chunk.parent_id,
        "source_path": chunk.source_path,
        "chunk_index": int(chunk.chunk_index),
        "title": chunk.title,
        "section": " > ".join(chunk.section_path),
        "namespace": _metadata_str(metadata, "namespace"),
        "domain": _metadata_str(metadata, "domain"),
        "content_kind": _metadata_str(metadata, "content_kind"),
        "trust_tier": _metadata_str(metadata, "trust_tier"),
        "volatility": _metadata_str(metadata, "volatility"),
        "contested": _metadata_str(metadata, "contested"),
        "element_type": chunk.element_type,
        "start_line": int(chunk.start_line or 0),
        "end_line": int(chunk.end_line or 0),
        "text_for_embedding": chunk.text_for_embedding,
        "text_original": chunk.text_original,
        "text_for_generation": chunk.text_for_generation,
        "metadata_json": json.dumps(metadata, sort_keys=True, default=str),
    }


def _metadata_str(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key, "")
    if value is None:
        return ""
    return str(value)


def _qdrant_point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(QDRANT_POINT_NAMESPACE, chunk_id))


def _indexed_filters(namespace: str | None, filters: dict[str, Any]) -> dict[str, Any]:
    indexed: dict[str, Any] = {}
    if namespace:
        indexed["namespace"] = namespace
    for key, value in filters.items():
        if key in INDEXED_FILTER_COLUMNS:
            indexed[key] = value
    return indexed


def _qdrant_filter(namespace: str | None, filters: dict[str, Any]) -> Any | None:
    indexed = _indexed_filters(namespace, filters)
    if not indexed:
        return None
    models = _qdrant_models()
    return models.Filter(
        must=[
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=_qdrant_filter_value(value)),
            )
            for key, value in sorted(indexed.items())
        ]
    )


def _qdrant_filter_value(value: Any) -> Any:
    if isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _where_clause(filters: dict[str, str]) -> str:
    clauses = []
    for key, value in sorted(filters.items()):
        safe_value = str(value).replace("'", "''")
        clauses.append(f"{key} = '{safe_value}'")
    return " AND ".join(clauses)


def _candidate_limit(top_k: int, filters: dict[str, str]) -> int:
    if set(filters).issubset(INDEXED_FILTER_COLUMNS):
        return top_k
    return max(top_k, min(1000, top_k * 25))


def _metadata_matches(
    chunk: Chunk,
    namespace: str | None,
    filters: dict[str, str],
) -> bool:
    if namespace and str(chunk.metadata.get("namespace")) != str(namespace):
        return False
    return all(str(chunk.metadata.get(key)) == str(value) for key, value in filters.items())


def _score_from_lance_row(row: dict[str, Any]) -> float:
    distance = row.get("_distance")
    try:
        return -float(distance)
    except (TypeError, ValueError):
        return 0.0


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.lower().strip() in {"1", "true", "yes", "on"}
