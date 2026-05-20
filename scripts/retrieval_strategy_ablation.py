from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from eval.harness import DEFAULT_GOLD_PATH, run_eval
from ingestion.build_index import build_index
from retrieval.embeddings import DEFAULT_EMBEDDING_MODEL, EmbeddingConfig, EmbeddingUnavailable
from retrieval.rerank import DEFAULT_COLBERT_MODEL, RerankerUnavailable
from retrieval.service import build_retriever


DIMENSIONAL_STRATEGIES = {"dense", "hybrid", "dense_colbert", "hybrid_colbert"}


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _csv_ints(value: str) -> list[int]:
    return [int(part) for part in _csv(value)]


def _strategy_runs(strategies: list[str], dimensions: list[int]) -> list[tuple[str, int | None]]:
    runs: list[tuple[str, int | None]] = []
    for strategy in strategies:
        if strategy in DIMENSIONAL_STRATEGIES:
            runs.extend((strategy, dimension) for dimension in dimensions)
        else:
            runs.append((strategy, None))
    return runs


def _result(
    *,
    gold: str,
    strategy: str,
    dimension: int | None,
    status: str,
    seconds: float,
    metrics: dict[str, float] | None = None,
    counts: dict[str, int] | None = None,
    failure_count: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "gold": gold,
        "strategy": strategy,
        "dimension": dimension,
        "status": status,
        "seconds": round(seconds, 3),
    }
    if metrics is not None:
        payload["metrics"] = metrics
    if counts is not None:
        payload["counts"] = counts
    if failure_count is not None:
        payload["failure_count"] = failure_count
    if reason:
        payload["reason"] = reason
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare retrieval strategies across gold sets.")
    parser.add_argument(
        "--gold",
        default=str(DEFAULT_GOLD_PATH),
        help="Comma-separated gold JSON paths.",
    )
    parser.add_argument(
        "--strategies",
        default="lexical,dense,hybrid,lexical_colbert,hybrid_colbert",
        help="Comma-separated strategies: lexical,dense,hybrid,lexical_colbert,dense_colbert,hybrid_colbert.",
    )
    parser.add_argument("--dimensions", default="1024,768,512,384,256")
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--native-dim", type=int, default=1024)
    parser.add_argument("--colbert-model", default=DEFAULT_COLBERT_MODEL)
    parser.add_argument("--candidate-top-k", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--cache-dir", default=".cache/embeddings")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--out", default="", help="Optional JSON output path.")
    parser.add_argument("--fail-on-skip", action="store_true")
    args = parser.parse_args()

    gold_paths = _csv(args.gold)
    strategies = [strategy.lower() for strategy in _csv(args.strategies)]
    dimensions = _csv_ints(args.dimensions)
    config = EmbeddingConfig(
        model_name=args.model,
        native_dimension=args.native_dim,
        dimensions=tuple(dimensions),
        batch_size=args.batch_size,
        cache_dir=args.cache_dir,
    )

    store = build_index()
    results = []
    for strategy, dimension in _strategy_runs(strategies, dimensions):
        for gold_path in gold_paths:
            started = time.perf_counter()
            try:
                retriever = build_retriever(
                    store.chunks,
                    mode=strategy,
                    embedding_config=config,
                    embedding_dimension=dimension,
                    rebuild_embeddings=args.rebuild,
                    allow_fallback=False,
                )
                if "colbert" in strategy and hasattr(retriever, "reranker"):
                    retriever.reranker.model_name = args.colbert_model
                    retriever.candidate_top_k = args.candidate_top_k
                report = run_eval(gold_path, retrieve_fn=retriever.search)
                results.append(
                    _result(
                        gold=gold_path,
                        strategy=strategy,
                        dimension=dimension,
                        status="ok",
                        seconds=time.perf_counter() - started,
                        metrics=report.metrics,
                        counts=report.counts,
                        failure_count=len(report.failures),
                    )
                )
            except (EmbeddingUnavailable, RerankerUnavailable, ImportError, RuntimeError) as exc:
                results.append(
                    _result(
                        gold=gold_path,
                        strategy=strategy,
                        dimension=dimension,
                        status="skipped",
                        seconds=time.perf_counter() - started,
                        reason=str(exc),
                    )
                )
                if args.fail_on_skip:
                    raise SystemExit(2) from exc

    payload = {
        "status": "ok",
        "embedding_model": args.model,
        "colbert_model": args.colbert_model,
        "gold": gold_paths,
        "strategies": strategies,
        "dimensions": dimensions,
        "results": results,
    }
    output = json.dumps(payload, indent=2, sort_keys=True)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
