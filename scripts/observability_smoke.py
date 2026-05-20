from __future__ import annotations

from pathlib import Path
import sys

import os

os.environ["LLM_PROVIDER"] = "disabled"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["RETRIEVAL_MODE"] = "lexical"
os.environ["VECTOR_STORE_BACKEND"] = "memory"
os.environ["PREWARM_RETRIEVER"] = "false"

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import advise_api, health_api, metrics_api


def main() -> None:
    previous_provider = os.environ.get("LLM_PROVIDER")
    previous_rate_limit = os.environ.get("RATE_LIMIT_ENABLED")
    previous_retrieval_mode = os.environ.get("RETRIEVAL_MODE")
    previous_vector_backend = os.environ.get("VECTOR_STORE_BACKEND")
    os.environ["LLM_PROVIDER"] = "disabled"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["RETRIEVAL_MODE"] = "lexical"
    os.environ["VECTOR_STORE_BACKEND"] = "memory"
    try:
        before = metrics_api()
        health = health_api()
        if "status" not in health or "checks" not in health:
            raise AssertionError("health endpoint changed shape")
        payload = advise_api("Build an internal API docs assistant over fast-moving SDK docs.")
        after = metrics_api()
    finally:
        if previous_provider is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = previous_provider
        if previous_rate_limit is None:
            os.environ.pop("RATE_LIMIT_ENABLED", None)
        else:
            os.environ["RATE_LIMIT_ENABLED"] = previous_rate_limit
        if previous_retrieval_mode is None:
            os.environ.pop("RETRIEVAL_MODE", None)
        else:
            os.environ["RETRIEVAL_MODE"] = previous_retrieval_mode
        if previous_vector_backend is None:
            os.environ.pop("VECTOR_STORE_BACKEND", None)
        else:
            os.environ["VECTOR_STORE_BACKEND"] = previous_vector_backend

    if "runtime" not in payload or "graph_timings_ms" not in payload["runtime"]:
        raise AssertionError("public API no longer exposes runtime timings")
    if after["requests_total"] <= before["requests_total"]:
        raise AssertionError("metrics endpoint did not count the request")
    if after["latency_ms"]["p50"] is None:
        raise AssertionError("metrics endpoint did not report latency percentiles")
    print("observability_smoke=ok")


if __name__ == "__main__":
    main()
