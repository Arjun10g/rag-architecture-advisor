from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.build_index import build_index
from retrieval.embeddings import DEFAULT_EMBEDDING_MODEL, EmbeddingConfig, EmbeddingUnavailable
from retrieval.vector_store import LanceDBVectorIndex, VectorStoreConfig, VectorStoreUnavailable


DEFAULT_INDEX_DIMENSIONS = "1024,512"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build persisted LanceDB vector indexes.")
    parser.add_argument("--backend", default="lancedb", choices=["lancedb", "lance"])
    parser.add_argument("--index-dir", default="corpus/index/lancedb")
    parser.add_argument("--table", default="chunks")
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--native-dim", type=int, default=1024)
    parser.add_argument(
        "--dimensions",
        default=os.getenv("VECTOR_INDEX_DIMS", DEFAULT_INDEX_DIMENSIONS),
        help="Comma-separated dimensions to persist. Default: 1024,512.",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=None,
        help="Single-dimension shortcut; overrides --dimensions when provided.",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--cache-dir", default=".cache/embeddings")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    dimensions = [args.dimension] if args.dimension else _parse_dimensions(args.dimensions)
    build_order = _build_order(dimensions, args.native_dim)

    embedding_config = EmbeddingConfig(
        model_name=args.model,
        native_dimension=args.native_dim,
        dimensions=tuple(dimensions),
        batch_size=args.batch_size,
        cache_dir=args.cache_dir,
    )
    vector_config = VectorStoreConfig(
        backend=args.backend,
        index_dir=args.index_dir,
        table_name=args.table,
    )

    store = build_index()
    built_indexes = []
    try:
        for dimension in build_order:
            index = LanceDBVectorIndex.from_chunks(
                store.chunks,
                store_config=vector_config,
                embedding_config=embedding_config,
                dimension=dimension,
                rebuild=args.rebuild,
            )
            built_indexes.append(
                {
                    "dimension": dimension,
                    "table": index.table_name,
                    "chunks": len(index.chunks),
                }
            )
    except (EmbeddingUnavailable, VectorStoreUnavailable) as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "backend": args.backend,
                    "index_dir": args.index_dir,
                    "table_base": args.table,
                    "model": args.model,
                    "dimensions": dimensions,
                    "reason": str(exc),
                },
                indent=2,
                sort_keys=True,
            )
        )
        raise SystemExit(2) from exc

    print(
        json.dumps(
            {
                "status": "ok",
                "backend": args.backend,
                "index_dir": args.index_dir,
                "table_base": args.table,
                "model": args.model,
                "dimensions": dimensions,
                "indexes": built_indexes,
            },
            indent=2,
            sort_keys=True,
        )
    )
    _write_manifest(
        index_dir=Path(args.index_dir),
        payload={
            "backend": args.backend,
            "index_dir": args.index_dir,
            "table_base": args.table,
            "model": args.model,
            "native_dimension": args.native_dim,
            "dimensions": dimensions,
            "indexes": built_indexes,
        },
    )


def _parse_dimensions(value: str) -> list[int]:
    dimensions = []
    for part in value.split(","):
        stripped = part.strip()
        if stripped:
            dimensions.append(int(stripped))
    if not dimensions:
        raise SystemExit("At least one embedding dimension is required.")
    return dimensions


def _build_order(dimensions: list[int], native_dimension: int) -> list[int]:
    unique_dimensions = list(dict.fromkeys(dimensions))
    if native_dimension in unique_dimensions:
        return [native_dimension] + [
            dimension for dimension in unique_dimensions if dimension != native_dimension
        ]
    return unique_dimensions


def _write_manifest(index_dir: Path, payload: dict) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "vector_manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
