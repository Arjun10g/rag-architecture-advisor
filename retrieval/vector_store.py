from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from typing import Any

from retrieval.chunking import Chunk
from retrieval.embeddings import DenseVectorIndex, EmbeddingConfig, SentenceTransformerEmbedder
from retrieval.index import SearchResult


DEFAULT_VECTOR_INDEX_DIR = "corpus/index/lancedb"
DEFAULT_VECTOR_TABLE_NAME = "chunks"
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
}


class VectorStoreUnavailable(RuntimeError):
    """Raised when an optional vector-store backend cannot be used."""


@dataclass(frozen=True)
class VectorStoreConfig:
    backend: str = "memory"
    index_dir: str = DEFAULT_VECTOR_INDEX_DIR
    table_name: str = DEFAULT_VECTOR_TABLE_NAME

    @classmethod
    def from_env(cls) -> "VectorStoreConfig":
        return cls(
            backend=os.getenv("VECTOR_STORE_BACKEND", "memory"),
            index_dir=os.getenv("VECTOR_INDEX_DIR", DEFAULT_VECTOR_INDEX_DIR),
            table_name=os.getenv("VECTOR_TABLE_NAME", DEFAULT_VECTOR_TABLE_NAME),
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


def _import_lancedb() -> Any:
    try:
        import lancedb
    except ImportError as exc:  # pragma: no cover - optional deployment dependency.
        raise VectorStoreUnavailable(
            "lancedb is not installed; run `python3 -m pip install -r requirements.txt` "
            "or set VECTOR_STORE_BACKEND=memory."
        ) from exc
    return lancedb


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


def _indexed_filters(namespace: str | None, filters: dict[str, str]) -> dict[str, str]:
    indexed: dict[str, str] = {}
    if namespace:
        indexed["namespace"] = namespace
    for key, value in filters.items():
        if key in INDEXED_FILTER_COLUMNS:
            indexed[key] = str(value)
    return indexed


def _where_clause(filters: dict[str, str]) -> str:
    clauses = []
    for key, value in sorted(filters.items()):
        safe_value = value.replace("'", "''")
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
