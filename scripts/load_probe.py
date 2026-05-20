from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience.
    load_dotenv = None

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.api_output_probe import (
    DEFAULT_BRIEF,
    _enforce_latency_slo,
    _latency_slo,
    _predict,
    _validate_public_payload,
)


def main() -> None:
    if load_dotenv:
        load_dotenv()

    parser = argparse.ArgumentParser(description="Run a small concurrent public API load probe.")
    parser.add_argument("--url", default="http://127.0.0.1:8022")
    parser.add_argument("--endpoint", default="/advise")
    parser.add_argument("--brief", default=DEFAULT_BRIEF)
    parser.add_argument("--requests", type=int, default=6)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--deep-thinking", action="store_true")
    parser.add_argument("--hf-token", default=None)
    parser.add_argument("--auth-username", default=None)
    parser.add_argument("--auth-password", default=None)
    parser.add_argument("--slo-p50-ms", type=float, default=None)
    parser.add_argument("--slo-p99-ms", type=float, default=None)
    parser.add_argument("--slo-from-env", action="store_true")
    args = parser.parse_args()
    if args.requests < 1:
        raise SystemExit("--requests must be at least 1")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")

    latencies: list[float] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(_run_once, args) for _ in range(args.requests)]
        for future in as_completed(futures):
            try:
                latencies.append(future.result())
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {str(exc)[:300]}")

    summary = _summary(latencies)
    slo_p50, slo_p99 = _latency_slo(args)
    slo_status = _enforce_latency_slo(summary, p50_ms=slo_p50, p99_ms=slo_p99) if latencies else None
    payload = {
        "url": args.url,
        "endpoint": args.endpoint,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "successes": len(latencies),
        "errors": errors,
        "client_latency_ms": summary,
        "latency_slo": slo_status,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


def _run_once(args: argparse.Namespace) -> float:
    run_args = SimpleNamespace(
        url=args.url,
        endpoint=args.endpoint,
        brief=args.brief,
        elicitation_answers="",
        conflict_resolution="",
        deep_thinking=args.deep_thinking,
        hf_token=args.hf_token,
        auth_username=args.auth_username,
        auth_password=args.auth_password,
    )
    started = time.perf_counter()
    payload = _predict(run_args)
    _validate_public_payload(payload)
    return (time.perf_counter() - started) * 1000


def _summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p95": None, "p99": None, "max": None}
    ordered = sorted(values)
    return {
        "p50": round(statistics.median(ordered), 2),
        "p95": _percentile(ordered, 0.95),
        "p99": _percentile(ordered, 0.99),
        "max": round(max(ordered), 2),
    }


def _percentile(ordered: list[float], percentile: float) -> float:
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return round(ordered[index], 2)


if __name__ == "__main__":
    main()
