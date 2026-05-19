from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from eval.harness import DEFAULT_GOLD_PATH, run_eval
from ingestion.build_index import build_index
from retrieval.embeddings import DEFAULT_EMBEDDING_MODEL, EmbeddingConfig, EmbeddingUnavailable
from retrieval.service import build_retriever


def _parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _parse_csv_strings(value: str) -> list[str]:
    return [part.strip().lower() for part in value.split(",") if part.strip()]


def _report_payload(
    *,
    status: str,
    model: str,
    gold: str,
    dimensions: list[int],
    modes: list[str],
    results: list[dict[str, Any]],
    reason: str | None = None,
) -> dict[str, Any]:
    payload = {
        "status": status,
        "model": model,
        "gold": gold,
        "dimensions": dimensions,
        "modes": modes,
        "results": results,
    }
    if reason:
        payload["reason"] = reason
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ablate Matryoshka embedding dimensions on a gold set."
    )
    parser.add_argument("--gold", default=str(DEFAULT_GOLD_PATH), help="Gold JSON path.")
    parser.add_argument(
        "--model", default=DEFAULT_EMBEDDING_MODEL, help="SentenceTransformer model name."
    )
    parser.add_argument(
        "--native-dim", type=int, default=1024, help="Model's full embedding dimension."
    )
    parser.add_argument(
        "--dimensions", default="1024,768,512,384,256", help="Comma-separated dimensions."
    )
    parser.add_argument(
        "--modes", default="dense,hybrid", help="Comma-separated modes: dense,hybrid."
    )
    parser.add_argument("--batch-size", type=int, default=16, help="Embedding batch size.")
    parser.add_argument(
        "--cache-dir", default=".cache/embeddings", help="Embedding cache directory."
    )
    parser.add_argument(
        "--rebuild", action="store_true", help="Ignore cached embeddings and rebuild."
    )
    parser.add_argument(
        "--fail-on-skip", action="store_true", help="Exit non-zero if embeddings are unavailable."
    )
    args = parser.parse_args()

    dimensions = _parse_csv_ints(args.dimensions)
    modes = _parse_csv_strings(args.modes)
    config = EmbeddingConfig(
        model_name=args.model,
        native_dimension=args.native_dim,
        dimensions=tuple(dimensions),
        batch_size=args.batch_size,
        cache_dir=args.cache_dir,
    )

    store = build_index()
    results = []
    try:
        for dimension in dimensions:
            for mode in modes:
                retriever = build_retriever(
                    store.chunks,
                    mode=mode,
                    embedding_config=config,
                    embedding_dimension=dimension,
                    rebuild_embeddings=args.rebuild,
                    allow_fallback=False,
                )
                report = run_eval(args.gold, retrieve_fn=retriever.search)
                results.append(
                    {
                        "dimension": dimension,
                        "mode": mode,
                        "version": report.version,
                        "metrics": report.metrics,
                        "counts": report.counts,
                        "failure_count": len(report.failures),
                    }
                )
    except EmbeddingUnavailable as exc:
        payload = _report_payload(
            status="skipped",
            model=args.model,
            gold=args.gold,
            dimensions=dimensions,
            modes=modes,
            results=results,
            reason=str(exc),
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        if args.fail_on_skip:
            raise SystemExit(2) from exc
        return

    print(
        json.dumps(
            _report_payload(
                status="ok",
                model=args.model,
                gold=args.gold,
                dimensions=dimensions,
                modes=modes,
                results=results,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
