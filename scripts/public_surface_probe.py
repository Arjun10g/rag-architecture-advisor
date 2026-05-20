from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience.
    load_dotenv = None

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))


def main() -> None:
    if load_dotenv:
        load_dotenv()

    parser = argparse.ArgumentParser(description="Probe public health and token-protected metrics endpoints.")
    parser.add_argument("--url", default="http://127.0.0.1:8022")
    parser.add_argument("--hf-token", default=None)
    parser.add_argument("--auth-username", default=None)
    parser.add_argument("--auth-password", default=None)
    parser.add_argument("--metrics-token", default=None)
    args = parser.parse_args()

    from gradio_client import Client

    client = Client(
        args.url,
        token=args.hf_token or os.getenv("HF_TOKEN") or os.getenv("HF_ACCESS_TOKEN") or None,
        auth=_client_auth(args),
        verbose=False,
    )
    health = client.predict(api_name="/health")
    metrics = client.predict(
        args.metrics_token or os.getenv("METRICS_AUTH_TOKEN") or os.getenv("OPERATIONS_TOKEN") or "",
        api_name="/metrics",
    )
    _validate_health(health)
    _validate_metrics(metrics)
    print(
        json.dumps(
            {
                "status": "ok",
                "health": {
                    "status": health.get("status"),
                    "checks": {
                        key: (health.get("checks") or {}).get(key)
                        for key in (
                            "retrieval_mode",
                            "vector_store_backend",
                            "embedding_provider",
                            "public_access_mode",
                            "public_access_configured",
                            "auth_configured",
                            "rate_limit_configured",
                            "metrics_protected",
                            "audit_log_configured",
                            "raw_trace_hidden",
                        )
                    },
                },
                "metrics": {
                    "requests_total": metrics.get("requests_total"),
                    "errors_total": metrics.get("errors_total"),
                    "latency_ms": metrics.get("latency_ms"),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


def _client_auth(args: argparse.Namespace) -> tuple[str, str] | None:
    username = args.auth_username or os.getenv("GRADIO_AUTH_USERNAME", "").strip()
    password = args.auth_password or os.getenv("GRADIO_AUTH_PASSWORD", "").strip()
    if bool(username) != bool(password):
        raise AssertionError("Provide both Gradio auth username and password, or neither.")
    return (username, password) if username and password else None


def _validate_health(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise AssertionError("health payload should be an object")
    if payload.get("status") != "ok":
        raise AssertionError(f"health endpoint is not ok: {payload}")
    checks = payload.get("checks") or {}
    required = {
        "auth_configured",
        "public_access_configured",
        "rate_limit_configured",
        "metrics_protected",
        "audit_log_configured",
        "raw_trace_hidden",
    }
    missing = [key for key in required if not checks.get(key)]
    if missing:
        raise AssertionError(f"health checks failed: {missing}")
    if "metrics" in payload:
        raise AssertionError("health endpoint should not expose metrics")


def _validate_metrics(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise AssertionError("metrics payload should be an object")
    if "latency_ms" not in payload:
        raise AssertionError("metrics payload is missing latency percentiles")
    if payload.get("requests_total") is None:
        raise AssertionError("metrics payload is missing request count")


if __name__ == "__main__":
    main()
