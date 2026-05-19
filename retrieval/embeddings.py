from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
import os
from pathlib import Path
import pickle
import re
from typing import Any

from retrieval.chunking import Chunk
from retrieval.index import SearchResult


DEFAULT_EMBEDDING_MODEL = "mixedbread-ai/mxbai-embed-large-v1"
DEFAULT_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DEFAULT_DIMENSIONS = (1024, 768, 512, 384, 256)


class EmbeddingUnavailable(RuntimeError):
    """Raised when optional embedding dependencies or model files are unavailable."""


@dataclass(frozen=True)
class EmbeddingConfig:
    model_name: str = DEFAULT_EMBEDDING_MODEL
    native_dimension: int = 1024
    dimensions: tuple[int, ...] = DEFAULT_DIMENSIONS
    query_prefix: str = DEFAULT_QUERY_PREFIX
    batch_size: int = 16
    cache_dir: str = ".cache/embeddings"

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        return cls(
            model_name=os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            native_dimension=_env_int("EMBEDDING_NATIVE_DIM", 1024),
            dimensions=_parse_dimensions(os.getenv("EMBEDDING_DIMS"), DEFAULT_DIMENSIONS),
            query_prefix=_query_prefix(os.getenv("EMBEDDING_QUERY_PREFIX", DEFAULT_QUERY_PREFIX)),
            batch_size=_env_int("EMBEDDING_BATCH_SIZE", 16),
            cache_dir=os.getenv("EMBEDDING_CACHE_DIR", ".cache/embeddings"),
        )


class SentenceTransformerEmbedder:
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._model: Any | None = None

    def encode(self, texts: list[str], *, is_query: bool, dimension: int) -> list[list[float]]:
        if not texts:
            return []
        _validate_dimension(dimension, self.config.native_dimension)

        prepared = [self._prepare_query(text) for text in texts] if is_query else texts
        try:
            raw_vectors = self._load_model().encode(
                prepared,
                batch_size=self.config.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:  # pragma: no cover - depends on optional ML runtime/model cache.
            raise EmbeddingUnavailable(
                f"Could not encode with {self.config.model_name}: {exc}"
            ) from exc

        return [_normalize(_to_float_list(vector)[:dimension]) for vector in raw_vectors]

    def _prepare_query(self, text: str) -> str:
        prefix = self.config.query_prefix
        return text if text.startswith(prefix) else f"{prefix}{text}"

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency.
            raise EmbeddingUnavailable(
                "sentence-transformers is not installed; run "
                "`python3 -m pip install -r requirements.txt` before dense retrieval "
                "or embedding ablations."
            ) from exc

        try:
            self._model = SentenceTransformer(self.config.model_name)
        except Exception as exc:  # pragma: no cover - depends on local model/network availability.
            raise EmbeddingUnavailable(
                f"Could not load embedding model {self.config.model_name}: {exc}"
            ) from exc
        return self._model


class DenseVectorIndex:
    def __init__(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]],
        embedder: SentenceTransformerEmbedder,
        dimension: int,
    ):
        self.chunks = chunks
        self.vectors = vectors
        self.embedder = embedder
        self.dimension = dimension

    @classmethod
    def from_chunks(
        cls,
        chunks: list[Chunk],
        config: EmbeddingConfig | None = None,
        *,
        dimension: int | None = None,
        rebuild: bool = False,
    ) -> "DenseVectorIndex":
        config = config or EmbeddingConfig.from_env()
        dimension = dimension or config.native_dimension
        _validate_dimension(dimension, config.native_dimension)

        embedder = SentenceTransformerEmbedder(config)
        vectors = _load_or_build_vectors(chunks, embedder, config, dimension, rebuild=rebuild)
        return cls(chunks=chunks, vectors=vectors, embedder=embedder, dimension=dimension)

    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        filters = filters or {}
        query_vector = self.embedder.encode([query], is_query=True, dimension=self.dimension)[0]
        scored: list[SearchResult] = []
        for chunk, vector in zip(self.chunks, self.vectors):
            if namespace and chunk.metadata.get("namespace") != namespace:
                continue
            if any(str(chunk.metadata.get(key)) != str(value) for key, value in filters.items()):
                continue
            scored.append(SearchResult(chunk=chunk, score=_dot(query_vector, vector)))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return int(value)


def _parse_dimensions(raw: str | None, default: tuple[int, ...]) -> tuple[int, ...]:
    if raw is None or not raw.strip():
        return default
    dimensions = []
    for part in raw.split(","):
        value = part.strip()
        if value:
            dimensions.append(int(value))
    return tuple(dimensions) or default


def _query_prefix(value: str) -> str:
    return value if value.endswith(" ") else f"{value} "


def _validate_dimension(dimension: int, native_dimension: int) -> None:
    if dimension < 1 or dimension > native_dimension:
        raise ValueError(
            f"Embedding dimension must be between 1 and {native_dimension}; got {dimension}."
        )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug or "model"


def _cache_path(config: EmbeddingConfig, dimension: int) -> Path:
    return Path(config.cache_dir) / _slug(config.model_name) / f"dim_{dimension}.pkl"


def _cache_key(chunks: list[Chunk], config: EmbeddingConfig, dimension: int) -> str:
    digest = sha256()
    digest.update(config.model_name.encode("utf-8"))
    digest.update(str(dimension).encode("utf-8"))
    digest.update(str(config.native_dimension).encode("utf-8"))
    for chunk in chunks:
        digest.update(chunk.chunk_id.encode("utf-8"))
        digest.update(str(chunk.metadata.get("content_hash", "")).encode("utf-8"))
    return digest.hexdigest()


def _load_or_build_vectors(
    chunks: list[Chunk],
    embedder: SentenceTransformerEmbedder,
    config: EmbeddingConfig,
    dimension: int,
    *,
    rebuild: bool,
) -> list[list[float]]:
    cache_path = _cache_path(config, dimension)
    key = _cache_key(chunks, config, dimension)

    if not rebuild and cache_path.exists():
        cached = _read_cache(cache_path)
        if cached.get("cache_key") == key:
            vectors = cached.get("vectors")
            if isinstance(vectors, list) and len(vectors) == len(chunks):
                return vectors

    texts = [chunk.text_for_embedding for chunk in chunks]
    vectors = embedder.encode(texts, is_query=False, dimension=dimension)
    _write_cache(cache_path, {"cache_key": key, "vectors": vectors})
    return vectors


def _read_cache(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            value = pickle.load(handle)
    except (OSError, pickle.PickleError, EOFError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_cache(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _to_float_list(vector: Any) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(value) for value in vector]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))
