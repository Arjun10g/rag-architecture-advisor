from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience.
    load_dotenv = None

from app import _reset_rate_limiter_for_tests, advise_api
from llm.provider import DEFAULT_HF_INFERENCE_MODEL
from retrieval.service import get_retriever
from retrieval.vector_store import VectorStoreConfig
from scripts.api_output_probe import (
    DEFAULT_BRIEF,
    _validate_deep_research_payload,
    _validate_public_payload,
)


REQUIRED_FILES = (
    "app.py",
    "README.md",
    ".env.example",
    "agents/research_agents.py",
    "corpus/manifest.yaml",
    "scripts/api_output_probe.py",
    "scripts/qdrant_cloud_bootstrap.py",
    "scripts/deep_research_full_text_smoke.py",
    "scripts/deep_research_smoke.py",
    "scripts/hf_generation_probe.py",
    "eval/gold/v0_2_expanded.json",
    "eval/gold/v0_4_answer_quality.json",
    "eval/gold/v0_5_panel_quality.json",
)


def _check(name: str, ok: bool, detail: str, checks: list[dict[str, Any]]) -> None:
    checks.append({"name": name, "ok": ok, "detail": detail})


def _secret_present(*keys: str) -> bool:
    return any(bool(os.getenv(key, "").strip()) for key in keys)


def _nonempty_env(key: str) -> bool:
    return bool(os.getenv(key, "").strip())


def _env_bool(key: str) -> bool:
    return os.getenv(key, "").lower().strip() in {"1", "true", "yes", "on"}


def _env_float(key: str) -> float | None:
    value = os.getenv(key)
    if value is None or not value.strip():
        return None
    return float(value)


def _latency_slo_ok(prefix: str = "") -> tuple[bool, str]:
    p50_key = f"{prefix}LATENCY_SLO_P50_MS"
    p99_key = f"{prefix}LATENCY_SLO_P99_MS"
    p50 = _env_float(p50_key)
    p99 = _env_float(p99_key)
    if p50 is None or p99 is None:
        return False, f"missing {p50_key}/{p99_key}"
    if p50 <= 0 or p99 <= 0:
        return False, "SLO values must be positive milliseconds"
    if p50 > p99:
        return False, f"{p50_key} cannot exceed {p99_key}"
    return True, f"p50<={p50:g}ms p99<={p99:g}ms"


def _audit_log_path_ok() -> tuple[bool, str]:
    raw = os.getenv("ADVISOR_AUDIT_LOG_PATH", "").strip()
    if not raw:
        return False, "missing"
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return False, "must be an absolute path on persistent storage"

    temp_root = Path(tempfile.gettempdir()).resolve()
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        resolved = path
    if resolved == temp_root or temp_root in resolved.parents:
        return False, "points at temporary storage"
    if ".cache" in resolved.parts or "eval" in resolved.parts:
        return False, "looks like cache/eval output, not durable audit storage"
    return True, "set"


def _vector_manifest_ok(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"
    dimensions = {int(value) for value in payload.get("dimensions") or []}
    indexes = payload.get("indexes") or []
    indexed_dimensions = {int(item.get("dimension")) for item in indexes if item.get("dimension")}
    required = {1024, 512}
    if not required.issubset(dimensions | indexed_dimensions):
        return False, "manifest must include 1024 and 512 dimensional indexes"
    backend = str(payload.get("backend") or os.getenv("VECTOR_STORE_BACKEND", "")).strip().lower()
    if backend == "qdrant":
        return _qdrant_manifest_ok(indexes, required)

    try:
        import lancedb
    except ImportError:
        return False, "lancedb is not installed, so vector tables cannot be verified"

    try:
        db = lancedb.connect(path.parent.as_posix())
        table_names = _lancedb_table_names(db)
    except Exception as exc:
        return False, f"could not open LanceDB index at {path.parent}: {exc}"

    verified = []
    for item in indexes:
        dimension = int(item.get("dimension") or 0)
        if dimension not in required:
            continue
        expected_chunks = int(item.get("chunks") or 0)
        if expected_chunks <= 0:
            return False, "1024 and 512 indexes must contain chunks"
        table_name = str(item.get("table") or "")
        if table_name not in table_names:
            return False, f"missing LanceDB table {table_name}"
        try:
            actual_chunks = int(db.open_table(table_name).count_rows())
        except Exception as exc:
            return False, f"could not read LanceDB table {table_name}: {exc}"
        if actual_chunks != expected_chunks:
            return False, (
                f"LanceDB table {table_name} row count {actual_chunks} "
                f"does not match manifest {expected_chunks}"
            )
        verified.append(f"{dimension}:{actual_chunks}")
    return True, f"verified LanceDB tables {', '.join(verified)}"


def _qdrant_manifest_ok(indexes: list[dict[str, Any]], required: set[int]) -> tuple[bool, str]:
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        return False, "qdrant-client is not installed, so Qdrant collections cannot be verified"

    config = VectorStoreConfig.from_env()
    try:
        if config.qdrant_url:
            client = QdrantClient(
                url=config.qdrant_url,
                api_key=config.qdrant_api_key or None,
                prefer_grpc=config.qdrant_prefer_grpc,
                timeout=config.qdrant_timeout_seconds,
            )
        elif config.qdrant_local_path:
            client = QdrantClient(path=config.qdrant_local_path, timeout=config.qdrant_timeout_seconds)
        else:
            return False, "Qdrant verification requires QDRANT_URL or QDRANT_LOCAL_PATH"
    except Exception as exc:
        return False, f"could not create Qdrant client: {exc}"

    verified = []
    for item in indexes:
        dimension = int(item.get("dimension") or 0)
        if dimension not in required:
            continue
        expected_chunks = int(item.get("chunks") or 0)
        if expected_chunks <= 0:
            return False, "1024 and 512 indexes must contain chunks"
        collection_name = str(item.get("collection") or item.get("table") or "")
        if not collection_name:
            return False, f"missing Qdrant collection name for {dimension}"
        try:
            if not client.collection_exists(collection_name):
                return False, f"missing Qdrant collection {collection_name}"
            actual_chunks = int(
                client.count(
                    collection_name=collection_name,
                    exact=True,
                    timeout=config.qdrant_timeout_seconds,
                ).count
            )
        except Exception as exc:
            return False, f"could not read Qdrant collection {collection_name}: {exc}"
        if actual_chunks != expected_chunks:
            return False, (
                f"Qdrant collection {collection_name} row count {actual_chunks} "
                f"does not match manifest {expected_chunks}"
            )
        verified.append(f"{dimension}:{actual_chunks}")
    return True, f"verified Qdrant collections {', '.join(verified)}"


def _lancedb_table_names(db: Any) -> set[str]:
    if hasattr(db, "list_tables"):
        response = db.list_tables()
        return set(getattr(response, "tables", response))
    return set(db.table_names())


def _validate_direct_public_api() -> tuple[bool, str]:
    previous = os.environ.get("LLM_PROVIDER")
    previous_rate_limit = os.environ.get("RATE_LIMIT_ENABLED")
    previous_retrieval_mode = os.environ.get("RETRIEVAL_MODE")
    os.environ["LLM_PROVIDER"] = "disabled"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["RETRIEVAL_MODE"] = "lexical"
    get_retriever.cache_clear()
    _reset_rate_limiter_for_tests()
    try:
        payload = advise_api(DEFAULT_BRIEF)
        summary = _validate_public_payload(payload)
        deep_payload = advise_api(DEFAULT_BRIEF, deep_thinking=True)
        deep_summary = _validate_public_payload(deep_payload)
        _validate_deep_research_payload(deep_payload)
    finally:
        if previous is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = previous
        if previous_rate_limit is None:
            os.environ.pop("RATE_LIMIT_ENABLED", None)
        else:
            os.environ["RATE_LIMIT_ENABLED"] = previous_rate_limit
        if previous_retrieval_mode is None:
            os.environ.pop("RETRIEVAL_MODE", None)
        else:
            os.environ["RETRIEVAL_MODE"] = previous_retrieval_mode
        get_retriever.cache_clear()
        _reset_rate_limiter_for_tests()
    return (
        True,
        (
            f"topology={summary['topology']} chunks={summary['reasoning_chunks']} "
            f"deep_links={deep_summary['research_links']}"
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check release-readiness guardrails without printing secrets."
    )
    parser.add_argument("--profile", choices=["demo", "production"], default="demo")
    parser.add_argument("--require-auth", action="store_true")
    parser.add_argument("--require-vector-index", action="store_true")
    parser.add_argument("--vector-manifest", default="corpus/index/lancedb/vector_manifest.json")
    args = parser.parse_args()

    if load_dotenv:
        load_dotenv()

    checks: list[dict[str, Any]] = []
    root = Path.cwd()

    for relative in REQUIRED_FILES:
        path = root / relative
        _check(f"file:{relative}", path.exists(), "present" if path.exists() else "missing", checks)

    try:
        ok, detail = _validate_direct_public_api()
    except Exception as exc:
        ok, detail = False, str(exc)
    _check("public_api_contract", ok, detail, checks)

    provider = os.getenv("LLM_PROVIDER", "hf").strip().lower()
    configured_model = os.getenv("HF_INFERENCE_MODEL") or DEFAULT_HF_INFERENCE_MODEL
    _check("llm_provider_configured", provider in {"hf", "disabled"}, f"LLM_PROVIDER={provider}", checks)
    _check(
        "hf_model_configured",
        bool(configured_model.strip()),
        "model=set" if configured_model.strip() else "model=missing",
        checks,
    )

    retrieval_mode = os.getenv("RETRIEVAL_MODE", "lexical").strip().lower()
    known_modes = {"lexical", "dense", "hybrid", "dense_colbert", "hybrid_colbert", "colbert"}
    _check(
        "retrieval_mode",
        retrieval_mode in known_modes,
        f"RETRIEVAL_MODE={retrieval_mode}",
        checks,
    )

    if args.profile == "production":
        _check(
            "hf_token_secret",
            _secret_present("HF_TOKEN", "HF_ACCESS_TOKEN"),
            "set" if _secret_present("HF_TOKEN", "HF_ACCESS_TOKEN") else "missing",
            checks,
        )
        ok, detail = _audit_log_path_ok()
        _check("audit_log_path", ok, detail, checks)
        ok, detail = _latency_slo_ok()
        _check("latency_slo_standard", ok, detail, checks)
        ok, detail = _latency_slo_ok("DEEP_")
        _check("latency_slo_deep_thinking", ok, detail, checks)

        vector_backend = os.getenv("VECTOR_STORE_BACKEND", "memory").strip().lower()
        _check(
            "vector_store_backend",
            vector_backend in {"lancedb", "lance", "qdrant"},
            f"VECTOR_STORE_BACKEND={vector_backend}",
            checks,
        )
        production_modes = {"dense", "hybrid", "dense_colbert", "hybrid_colbert"}
        _check(
            "production_retrieval_mode",
            retrieval_mode in production_modes,
            f"RETRIEVAL_MODE={retrieval_mode}",
            checks,
        )
        _check(
            "rate_limit_or_gateway",
            _env_bool("RATE_LIMIT_ENABLED") or _env_bool("EXTERNAL_RATE_LIMITING"),
            (
                "set"
                if _env_bool("RATE_LIMIT_ENABLED") or _env_bool("EXTERNAL_RATE_LIMITING")
                else "enable RATE_LIMIT_ENABLED or set EXTERNAL_RATE_LIMITING=true"
            ),
            checks,
        )
        args.require_auth = True
        args.require_vector_index = True

    if args.require_auth:
        username_set = _nonempty_env("GRADIO_AUTH_USERNAME")
        password_set = _nonempty_env("GRADIO_AUTH_PASSWORD")
        gateway_set = _env_bool("EXTERNAL_AUTH_GATEWAY")
        _check(
            "auth_or_gateway",
            (username_set and password_set) or gateway_set,
            (
                "set"
                if (username_set and password_set) or gateway_set
                else "missing username/password pair or EXTERNAL_AUTH_GATEWAY=true"
            ),
            checks,
        )

    if args.require_vector_index:
        ok, detail = _vector_manifest_ok(Path(args.vector_manifest))
        _check("vector_manifest", ok, detail, checks)

    failures = [check for check in checks if not check["ok"]]
    print(
        json.dumps(
            {
                "profile": args.profile,
                "status": "ok" if not failures else "failed",
                "checks": checks,
                "failure_count": len(failures),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
