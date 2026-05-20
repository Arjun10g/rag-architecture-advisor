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
from retrieval.vector_store import VectorStoreConfig, table_name_for_dimension
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
    "scripts/load_probe.py",
    "scripts/observability_smoke.py",
    "scripts/public_surface_probe.py",
    "scripts/qdrant_blue_green_promote.py",
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


def _deep_thinking_enabled() -> bool:
    return os.getenv("DEEP_THINKING_ENABLED", "true").lower().strip() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _env_float(key: str) -> float | None:
    value = os.getenv(key)
    if value is None or not value.strip():
        return None
    return float(value)


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return int(value)


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
    return _persistent_path_ok("ADVISOR_AUDIT_LOG_PATH")


def _persistent_path_ok(key: str) -> tuple[bool, str]:
    raw = os.getenv(key, "").strip()
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


def _audit_failure_mode_ok() -> tuple[bool, str]:
    mode = os.getenv("ADVISOR_AUDIT_FAILURE_MODE", "warn").strip().lower()
    if mode not in {"warn", "fail"}:
        return False, "must be warn or fail"
    if mode != "fail":
        return False, "set ADVISOR_AUDIT_FAILURE_MODE=fail for production"
    return True, "fail"


def _public_access_ok() -> tuple[bool, str]:
    mode = os.getenv("PUBLIC_ACCESS_MODE", "private").strip().lower()
    if mode not in {"private", "authenticated", "gateway", "anonymous"}:
        return False, "PUBLIC_ACCESS_MODE must be private, authenticated, gateway, or anonymous"
    username_set = _nonempty_env("GRADIO_AUTH_USERNAME")
    password_set = _nonempty_env("GRADIO_AUTH_PASSWORD")
    gateway_set = _env_bool("EXTERNAL_AUTH_GATEWAY")
    if mode == "anonymous" and not _env_bool("ALLOW_ANONYMOUS_PUBLIC"):
        return False, "anonymous mode requires ALLOW_ANONYMOUS_PUBLIC=true"
    if mode == "authenticated" and not (username_set and password_set):
        return False, "authenticated mode requires GRADIO_AUTH_USERNAME/PASSWORD"
    if mode == "gateway" and not gateway_set:
        return False, "gateway mode requires EXTERNAL_AUTH_GATEWAY=true"
    return True, mode


def _raw_trace_ok() -> tuple[bool, str]:
    if _env_bool("SHOW_RAW_TRACE"):
        return False, "SHOW_RAW_TRACE must be false in production"
    return True, "hidden"


def _metrics_token_ok() -> tuple[bool, str]:
    if _secret_present("METRICS_AUTH_TOKEN", "OPERATIONS_TOKEN"):
        return True, "set"
    return False, "set METRICS_AUTH_TOKEN or OPERATIONS_TOKEN"


def _input_bounds_ok() -> tuple[bool, str]:
    brief = _env_int("MAX_BRIEF_CHARS", 4000)
    elicitation = _env_int("MAX_ELICITATION_CHARS", 2000)
    conflict = _env_int("MAX_CONFLICT_CHARS", 1000)
    max_tokens = _env_int("LLM_MAX_TOKENS", 1800)
    deep_links = _env_int("DEEP_RESEARCH_MAX_FULL_TEXT_LINKS", 4)
    if not (1 <= brief <= 8000):
        return False, "MAX_BRIEF_CHARS must be between 1 and 8000"
    if not (1 <= elicitation <= 4000):
        return False, "MAX_ELICITATION_CHARS must be between 1 and 4000"
    if not (1 <= conflict <= 2000):
        return False, "MAX_CONFLICT_CHARS must be between 1 and 2000"
    if not (1 <= max_tokens <= 2200):
        return False, "LLM_MAX_TOKENS must be between 1 and 2200"
    if not (0 <= deep_links <= 8):
        return False, "DEEP_RESEARCH_MAX_FULL_TEXT_LINKS must be between 0 and 8"
    return True, f"brief<={brief} elicitation<={elicitation} conflict<={conflict} tokens<={max_tokens} full_text_links<={deep_links}"


def _cost_controls_ok() -> tuple[bool, str]:
    if not _env_bool("RATE_LIMIT_ENABLED") and not _env_bool("EXTERNAL_RATE_LIMITING"):
        return False, "rate limiting or external rate limiting is required"
    if _env_bool("RATE_LIMIT_ENABLED") and not _env_bool("RATE_LIMIT_PER_IDENTITY"):
        return False, "RATE_LIMIT_PER_IDENTITY=true is required for public traffic"
    standard_limit = _env_int("RATE_LIMIT_MAX_REQUESTS", 30)
    deep_limit = _env_int("RATE_LIMIT_ADVISOR_DEEP_MAX_REQUESTS", standard_limit)
    if deep_limit > standard_limit:
        return False, "deep-thinking request limit cannot exceed the standard limit"
    if _deep_thinking_enabled() and deep_limit <= 0:
        return False, "deep-thinking limit must be positive when deep thinking is enabled"
    return True, f"standard_limit={standard_limit} deep_limit={deep_limit}"


def _request_logging_ok() -> tuple[bool, str]:
    request_ok, request_detail = _persistent_path_ok("ADVISOR_REQUEST_LOG_PATH")
    alert_ok, alert_detail = _persistent_path_ok("ADVISOR_ALERT_LOG_PATH")
    if not request_ok:
        return False, f"request log {request_detail}"
    if not alert_ok:
        return False, f"alert log {alert_detail}"
    spike_threshold = _env_int("REQUEST_ALERT_MAX_REQUESTS", 0)
    latency_threshold = _env_int("REQUEST_ALERT_LATENCY_MS", 0)
    if spike_threshold <= 0 or latency_threshold <= 0:
        return False, "REQUEST_ALERT_MAX_REQUESTS and REQUEST_ALERT_LATENCY_MS must be positive"
    return True, f"request_log=set alert_log=set spike_threshold={spike_threshold}"


def _usage_budget_ok() -> tuple[bool, str]:
    counter_ok, counter_detail = _persistent_path_ok("ADVISOR_USAGE_COUNTER_PATH")
    if not counter_ok:
        return False, f"usage counter {counter_detail}"
    daily = _env_int("DAILY_REQUEST_BUDGET", 0)
    monthly = _env_int("MONTHLY_REQUEST_BUDGET", 0)
    if daily <= 0 or monthly <= 0:
        return False, "DAILY_REQUEST_BUDGET and MONTHLY_REQUEST_BUDGET must be positive"
    if daily > monthly:
        return False, "DAILY_REQUEST_BUDGET cannot exceed MONTHLY_REQUEST_BUDGET"
    if _deep_thinking_enabled():
        daily_deep = _env_int("DAILY_DEEP_REQUEST_BUDGET", 0)
        monthly_deep = _env_int("MONTHLY_DEEP_REQUEST_BUDGET", 0)
        if daily_deep <= 0 or monthly_deep <= 0:
            return False, "deep budgets must be positive when deep thinking is enabled"
    return True, f"daily={daily} monthly={monthly}"


def _anonymous_controls_ok() -> tuple[bool, str]:
    mode = os.getenv("PUBLIC_ACCESS_MODE", "private").strip().lower()
    if mode != "anonymous":
        return True, "not anonymous mode"
    if _deep_thinking_enabled():
        return False, "anonymous mode must set DEEP_THINKING_ENABLED=false"
    logging_ok, logging_detail = _request_logging_ok()
    if not logging_ok:
        return False, logging_detail
    budget_ok, budget_detail = _usage_budget_ok()
    if not budget_ok:
        return False, budget_detail
    controls_ok, controls_detail = _cost_controls_ok()
    if not controls_ok:
        return False, controls_detail
    return True, "anonymous controls hardened"


def _serving_capacity_ok() -> tuple[bool, str]:
    concurrency = _env_int("ADVISOR_CONCURRENCY_LIMIT", 2)
    queue_size = _env_int("ADVISOR_QUEUE_MAX_SIZE", 32)
    if not (1 <= concurrency <= 8):
        return False, "ADVISOR_CONCURRENCY_LIMIT must be between 1 and 8"
    if not (1 <= queue_size <= 256):
        return False, "ADVISOR_QUEUE_MAX_SIZE must be between 1 and 256"
    return True, f"advisor_concurrency={concurrency} queue_max={queue_size}"


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


def _qdrant_aliases_ok(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"
    if str(payload.get("backend") or "").lower() != "qdrant":
        return False, "alias manifest must use backend=qdrant"
    alias_table = str(payload.get("alias_table") or os.getenv("VECTOR_TABLE_NAME", "")).strip()
    if not alias_table:
        return False, "missing alias_table"
    required = {1024, 512}
    aliases = payload.get("aliases") or []
    targets = {
        int(item.get("dimension") or 0): (
            str(item.get("alias_collection") or ""),
            str(item.get("target_collection") or ""),
        )
        for item in aliases
    }
    if not required.issubset(set(targets)):
        return False, "alias manifest must include 1024 and 512 dimensions"

    try:
        from qdrant_client import QdrantClient
    except ImportError:
        return False, "qdrant-client is not installed, so Qdrant aliases cannot be verified"

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
            return False, "Qdrant alias verification requires QDRANT_URL or QDRANT_LOCAL_PATH"
        active_aliases = {item.alias_name: item.collection_name for item in client.get_aliases().aliases}
    except Exception as exc:
        return False, f"could not read Qdrant aliases: {exc}"

    verified = []
    for dimension in sorted(required):
        alias_name, target_name = targets[dimension]
        expected_alias = table_name_for_dimension(alias_table, dimension)
        if alias_name != expected_alias:
            return False, f"manifest alias {alias_name} does not match runtime alias {expected_alias}"
        if active_aliases.get(alias_name) != target_name:
            return False, f"alias {alias_name} points at {active_aliases.get(alias_name)}, expected {target_name}"
        verified.append(f"{dimension}:{alias_name}->{target_name}")
    return True, "verified Qdrant aliases " + ", ".join(verified)


def _lancedb_table_names(db: Any) -> set[str]:
    if hasattr(db, "list_tables"):
        response = db.list_tables()
        return set(getattr(response, "tables", response))
    return set(db.table_names())


def _validate_direct_public_api() -> tuple[bool, str]:
    previous = os.environ.get("LLM_PROVIDER")
    previous_rate_limit = os.environ.get("RATE_LIMIT_ENABLED")
    previous_retrieval_mode = os.environ.get("RETRIEVAL_MODE")
    previous_usage_counter = os.environ.get("ADVISOR_USAGE_COUNTER_PATH")
    os.environ["LLM_PROVIDER"] = "disabled"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["RETRIEVAL_MODE"] = "lexical"
    os.environ.pop("ADVISOR_USAGE_COUNTER_PATH", None)
    get_retriever.cache_clear()
    _reset_rate_limiter_for_tests()
    try:
        payload = advise_api(DEFAULT_BRIEF)
        summary = _validate_public_payload(payload)
        deep_summary: dict[str, Any] = {"research_links": "disabled"}
        if _deep_thinking_enabled():
            deep_payload = advise_api(DEFAULT_BRIEF, deep_thinking=True)
            deep_summary = _validate_public_payload(deep_payload)
            _validate_deep_research_payload(deep_payload)
        else:
            try:
                advise_api(DEFAULT_BRIEF, deep_thinking=True)
            except RuntimeError as exc:
                if "Deep thinking is currently disabled" not in str(exc):
                    raise
            else:
                raise AssertionError("deep-thinking request should be rejected when disabled")
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
        if previous_usage_counter is None:
            os.environ.pop("ADVISOR_USAGE_COUNTER_PATH", None)
        else:
            os.environ["ADVISOR_USAGE_COUNTER_PATH"] = previous_usage_counter
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
    parser.add_argument("--alias-manifest", default="corpus/index/qdrant/alias_manifest.json")
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
        ok, detail = _audit_failure_mode_ok()
        _check("audit_failure_mode", ok, detail, checks)
        ok, detail = _public_access_ok()
        _check("public_access_mode", ok, detail, checks)
        ok, detail = _raw_trace_ok()
        _check("raw_trace_hidden", ok, detail, checks)
        ok, detail = _metrics_token_ok()
        _check("metrics_token", ok, detail, checks)
        ok, detail = _input_bounds_ok()
        _check("input_and_cost_bounds", ok, detail, checks)
        ok, detail = _cost_controls_ok()
        _check("cost_controls", ok, detail, checks)
        ok, detail = _request_logging_ok()
        _check("request_logging_alerting", ok, detail, checks)
        ok, detail = _usage_budget_ok()
        _check("usage_budget_caps", ok, detail, checks)
        ok, detail = _anonymous_controls_ok()
        _check("anonymous_public_controls", ok, detail, checks)
        ok, detail = _serving_capacity_ok()
        _check("serving_capacity", ok, detail, checks)
        ok, detail = _latency_slo_ok()
        _check("latency_slo_standard", ok, detail, checks)
        ok, detail = (
            (True, "deep thinking disabled")
            if not _deep_thinking_enabled()
            else _latency_slo_ok("DEEP_")
        )
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
        if os.getenv("PUBLIC_ACCESS_MODE", "private").strip().lower() in {"authenticated", "gateway"}:
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
    if _env_bool("QDRANT_REQUIRE_ALIASES"):
        ok, detail = _qdrant_aliases_ok(Path(args.alias_manifest))
        _check("qdrant_aliases", ok, detail, checks)

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
