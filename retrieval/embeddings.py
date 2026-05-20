from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
import math
import os
from pathlib import Path
import pickle
import re
import threading
import time
from typing import Any

from retrieval.chunking import Chunk
from retrieval.index import SearchResult


DEFAULT_EMBEDDING_MODEL = "mixedbread-ai/mxbai-embed-large-v1"
DEFAULT_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DEFAULT_DIMENSIONS = (1024, 768, 512, 384, 256)
_MODEL_CACHE: dict[str, Any] = {}
_MODEL_CACHE_LOCK = threading.Lock()
_MODEL_ENCODE_LOCK = threading.Lock()
_QUERY_VECTOR_CACHE: OrderedDict[tuple[str, str, int, str], tuple[float, list[float]]] = OrderedDict()
_QUERY_CACHE_LOCK = threading.Lock()


class EmbeddingUnavailable(RuntimeError):
    """Raised when optional embedding dependencies or model files are unavailable."""


@dataclass(frozen=True)
class EmbeddingConfig:
    model_name: str = DEFAULT_EMBEDDING_MODEL
    provider: str = "local"
    hf_provider: str = "auto"
    native_dimension: int = 1024
    dimensions: tuple[int, ...] = DEFAULT_DIMENSIONS
    query_prefix: str = DEFAULT_QUERY_PREFIX
    batch_size: int = 16
    cache_dir: str = ".cache/embeddings"
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        return cls(
            model_name=os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            provider=os.getenv("EMBEDDING_PROVIDER", "local"),
            hf_provider=os.getenv("EMBEDDING_HF_PROVIDER", "auto"),
            native_dimension=_env_int("EMBEDDING_NATIVE_DIM", 1024),
            dimensions=_parse_dimensions(os.getenv("EMBEDDING_DIMS"), DEFAULT_DIMENSIONS),
            query_prefix=_query_prefix(os.getenv("EMBEDDING_QUERY_PREFIX", DEFAULT_QUERY_PREFIX)),
            batch_size=_env_int("EMBEDDING_BATCH_SIZE", 16),
            cache_dir=os.getenv("EMBEDDING_CACHE_DIR", ".cache/embeddings"),
            timeout_seconds=_env_float("EMBEDDING_TIMEOUT_SECONDS", 30.0),
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
        if is_query and _query_cache_size() > 0:
            return self._encode_queries_cached(prepared, dimension=dimension)
        return self._encode_prepared(prepared, dimension=dimension)

    def _encode_queries_cached(self, texts: list[str], *, dimension: int) -> list[list[float]]:
        cached: dict[int, list[float]] = {}
        misses: list[tuple[int, str]] = []
        for index, text in enumerate(texts):
            cached_vector = _query_cache_get(self.config, text, dimension)
            if cached_vector is None:
                misses.append((index, text))
            else:
                cached[index] = cached_vector

        if misses:
            miss_vectors = self._encode_prepared([text for _, text in misses], dimension=dimension)
            for (index, text), vector in zip(misses, miss_vectors):
                cached[index] = vector
                _query_cache_set(self.config, text, dimension, vector)
        return [cached[index] for index in range(len(texts))]

    def _encode_prepared(self, prepared: list[str], *, dimension: int) -> list[list[float]]:
        if self.config.provider.lower().strip() in {"hf", "huggingface", "huggingface_hub"}:
            return self._encode_hf(prepared, dimension=dimension)

        try:
            with _MODEL_ENCODE_LOCK:
                raw_vectors = self._load_model().encode(
                    prepared,
                    batch_size=self.config.batch_size,
                    normalize_embeddings=True,
                    truncate_dim=dimension,
                    show_progress_bar=False,
                )
        except Exception as exc:  # pragma: no cover - depends on optional ML runtime/model cache.
            raise EmbeddingUnavailable(
                f"Could not encode with {self.config.model_name}: {exc}"
            ) from exc

        return [_normalize(_to_float_list(vector)[:dimension]) for vector in raw_vectors]

    def _encode_hf(self, texts: list[str], *, dimension: int) -> list[list[float]]:
        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:  # pragma: no cover - optional dependency.
            raise EmbeddingUnavailable(
                "huggingface_hub is not installed; run `python3 -m pip install -r requirements.txt` "
                "or set EMBEDDING_PROVIDER=local."
            ) from exc

        try:
            client = InferenceClient(
                model=self.config.model_name,
                provider=self.config.hf_provider,
                token=_first_env("HF_TOKEN", "HF_ACCESS_TOKEN"),
                timeout=self.config.timeout_seconds,
            )
            raw_vectors = client.feature_extraction(
                texts,
                normalize=True,
                dimensions=dimension,
            )
        except Exception as exc:  # pragma: no cover - network/provider dependent.
            raise EmbeddingUnavailable(
                f"Could not encode with HF feature extraction {self.config.model_name}: {exc}"
            ) from exc

        return [_normalize(_to_float_list(vector)[:dimension]) for vector in raw_vectors]

    def _prepare_query(self, text: str) -> str:
        prefix = self.config.query_prefix
        return text if text.startswith(prefix) else f"{prefix}{text}"

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        with _MODEL_CACHE_LOCK:
            if self.config.model_name in _MODEL_CACHE:
                self._model = _MODEL_CACHE[self.config.model_name]
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
            _MODEL_CACHE[self.config.model_name] = self._model
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
        return self._search_with_vector(
            self.embedder.encode([query], is_query=True, dimension=self.dimension)[0],
            top_k=top_k,
            namespace=namespace,
            filters=filters,
        )

    def search_many(
        self,
        queries: list[str],
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[list[SearchResult]]:
        query_vectors = self.embedder.encode(queries, is_query=True, dimension=self.dimension)
        return [
            self._search_with_vector(
                query_vector,
                top_k=top_k,
                namespace=namespace,
                filters=filters,
            )
            for query_vector in query_vectors
        ]

    def _search_with_vector(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        namespace: str | None,
        filters: dict[str, str] | None,
    ) -> list[SearchResult]:
        filters = filters or {}
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


def _query_cache_size() -> int:
    return max(0, _env_int("EMBEDDING_QUERY_CACHE_SIZE", 128))


def _query_cache_ttl_seconds() -> float:
    return max(1.0, _env_float("EMBEDDING_QUERY_CACHE_TTL_SECONDS", 600.0))


def _query_cache_key(config: EmbeddingConfig, text: str, dimension: int) -> tuple[str, str, int, str]:
    provider = config.provider.lower().strip()
    model = config.model_name.strip()
    return provider, model, dimension, sha256(text.encode("utf-8")).hexdigest()


def _query_cache_get(
    config: EmbeddingConfig,
    text: str,
    dimension: int,
) -> list[float] | None:
    key = _query_cache_key(config, text, dimension)
    now = time_now()
    ttl = _query_cache_ttl_seconds()
    with _QUERY_CACHE_LOCK:
        cached = _QUERY_VECTOR_CACHE.get(key)
        if cached is None:
            return None
        created_at, vector = cached
        if now - created_at > ttl:
            _QUERY_VECTOR_CACHE.pop(key, None)
            return None
        _QUERY_VECTOR_CACHE.move_to_end(key)
        return list(vector)


def _query_cache_set(
    config: EmbeddingConfig,
    text: str,
    dimension: int,
    vector: list[float],
) -> None:
    max_size = _query_cache_size()
    if max_size <= 0:
        return
    key = _query_cache_key(config, text, dimension)
    with _QUERY_CACHE_LOCK:
        _QUERY_VECTOR_CACHE[key] = (time_now(), list(vector))
        _QUERY_VECTOR_CACHE.move_to_end(key)
        while len(_QUERY_VECTOR_CACHE) > max_size:
            _QUERY_VECTOR_CACHE.popitem(last=False)


def time_now() -> float:
    return time.monotonic()


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return float(value)


def _first_env(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value and value.strip():
            return value
    return None


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

    if dimension != config.native_dimension and not rebuild:
        native_vectors = _load_native_vectors(chunks, config)
        if native_vectors:
            vectors = [_normalize(vector[:dimension]) for vector in native_vectors]
            _write_cache(cache_path, {"cache_key": key, "vectors": vectors})
            return vectors

    texts = [chunk.text_for_embedding for chunk in chunks]
    vectors = embedder.encode(texts, is_query=False, dimension=dimension)
    _write_cache(cache_path, {"cache_key": key, "vectors": vectors})
    return vectors


def _load_native_vectors(chunks: list[Chunk], config: EmbeddingConfig) -> list[list[float]] | None:
    native_path = _cache_path(config, config.native_dimension)
    if not native_path.exists():
        return None
    cached = _read_cache(native_path)
    if cached.get("cache_key") != _cache_key(chunks, config, config.native_dimension):
        return None
    vectors = cached.get("vectors")
    if not isinstance(vectors, list) or len(vectors) != len(chunks):
        return None
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
