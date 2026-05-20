from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

try:
    import gradio as gr
except ImportError:  # pragma: no cover
    gr = None

from graph.build import build_graph
from graph.state import AdvisorState
from synth.panel import ATTRIBUTE_LABELS


if load_dotenv:
    load_dotenv()


EXAMPLE_BRIEFS = [
    "Build an internal API docs assistant over fast-moving SDK docs with strict citations, mixed markdown and code, and high exact-match terminology needs.",
    "Build a banking compliance assistant over customer policy, PCI controls, KYC procedures, and transaction runbooks where mistakes are costly and every answer needs auditability.",
    "Build a mental health therapy literature assistant for clinicians reviewing CBT studies and narrative research notes, with citation support and lower exact-match pressure than API documentation.",
    "We need a RAG system, but the domain, document type, sensitivity, update cadence, and latency requirements are not known yet.",
]
APP_CSS = """
.gradio-container {
  width: 100% !important;
  max-width: 1180px !important;
  margin: 0 auto !important;
  padding-left: 16px !important;
  padding-right: 16px !important;
  box-sizing: border-box !important;
  overflow-x: hidden !important;
}
body, gradio-app { overflow-x: hidden !important; }
.gradio-container .main { width: 100% !important; max-width: 100% !important; }
.gradio-container * { box-sizing: border-box !important; min-width: 0 !important; }
.advisor-shell { padding: 18px 0 6px; border-bottom: 1px solid #e5e7eb; margin-bottom: 14px; }
.advisor-title h1 { margin-bottom: 4px !important; font-size: 32px !important; letter-spacing: 0 !important; }
.advisor-title p { margin: 0 !important; color: #475569; font-size: 15px; white-space: normal !important; }
.advisor-notice { color: #475569; font-size: 13px; }
.advisor-input-grid {
  display: grid !important;
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr) !important;
  gap: 16px !important;
  align-items: start !important;
}
.advisor-input-grid > *, .advisor-main-column, .advisor-side-column {
  width: 100% !important;
  max-width: 100% !important;
}
.advisor-action-row {
  display: grid !important;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) !important;
  gap: 16px !important;
}
.advisor-tabs [role="tablist"], .advisor-tabs .tab-nav {
  overflow-x: auto !important;
  flex-wrap: nowrap !important;
}
textarea, .wrap textarea { font-size: 15px !important; line-height: 1.45 !important; }
button { max-width: 100% !important; white-space: normal !important; }
.contain .tabs { border-radius: 6px !important; }
footer { display: none !important; }
@media (max-width: 720px) {
  .gradio-container {
    max-width: 100vw !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
    padding-left: 12px !important;
    padding-right: 12px !important;
  }
  .gradio-container .main {
    margin-left: 0 !important;
    margin-right: 0 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    max-width: calc(100vw - 24px) !important;
  }
  .gradio-container .block,
  .gradio-container .wrap,
  .gradio-container .form,
  .advisor-shell,
  .advisor-input-grid,
  .advisor-action-row,
  .advisor-tabs {
    width: calc(100vw - 24px) !important;
    max-width: calc(100vw - 24px) !important;
  }
  .advisor-main-column,
  .advisor-side-column,
  .advisor-input-grid > *,
  .advisor-action-row > *,
  .advisor-action-row button {
    width: calc(100vw - 24px) !important;
    max-width: calc(100vw - 24px) !important;
  }
  .advisor-shell { padding-top: 14px; }
  .advisor-title h1 { font-size: 28px !important; line-height: 1.12 !important; }
  .advisor-title p { font-size: 14px !important; line-height: 1.45 !important; }
  .advisor-input-grid { grid-template-columns: minmax(0, 1fr) !important; }
  .advisor-action-row { grid-template-columns: minmax(0, 1fr) !important; }
  .advisor-title p, .advisor-notice, .advisor-notice * {
    max-width: 100% !important;
    overflow-wrap: anywhere !important;
  }
  .gradio-container .row { flex-direction: column !important; flex-wrap: nowrap !important; }
  .gradio-container .column {
    width: 100% !important;
    max-width: 100% !important;
    flex-basis: 100% !important;
  }
  .gradio-container [role="tablist"], .gradio-container .tab-nav {
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    white-space: nowrap !important;
  }
}
"""
PUBLIC_HEADER_MD = """
<div class="advisor-shell">
  <div class="advisor-title">
    <h1>RAG Architecture Advisor</h1>
    <p>Retrieval, generation, evaluation, deployment, and governance guidance.</p>
  </div>
</div>
"""
PUBLIC_NOTICE_MD = """
**Public beta boundary**

- Do not enter secrets, private customer data, or regulated personal data.
- The advisor provides architecture guidance, not legal, compliance, medical, or security certification.
- Briefs are processed by hosted inference and retrieval services. Audit records store hashed brief metadata and decision lineage.
- Deep thinking reads selected public references and may take longer than a standard run.
"""

DetailResponse = tuple[str, str, list[list[Any]], str, str, str, str, dict[str, Any]]
ClearDetailResponse = tuple[str, str, list[list[Any]], str, str, str, str, str, dict[str, Any]]
_RATE_LIMIT_EVENTS: dict[str, deque[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()
_METRICS_LOCK = threading.Lock()
_REQUEST_LOG_LOCK = threading.Lock()
_USAGE_BUDGET_LOCK = threading.Lock()
_REQUEST_EVENT_TIMES: deque[float] = deque()
_REQUEST_METRICS: dict[str, Any] = {
    "total": 0,
    "errors": 0,
    "latencies_ms": [],
    "deep_thinking_total": 0,
    "generation_status": {},
    "last_error": None,
    "last_request_at": None,
    "last_timings_ms": {},
}
_ALLOWED_PUBLIC_ACCESS_MODES = {"private", "authenticated", "gateway", "anonymous"}


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.lower().strip() in {"1", "true", "yes", "on"}


def _env_str(key: str, default: str = "") -> str:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip()


def _auth_credentials() -> tuple[str, str] | None:
    username = os.getenv("GRADIO_AUTH_USERNAME", "").strip()
    password = os.getenv("GRADIO_AUTH_PASSWORD", "").strip()
    if bool(username) != bool(password):
        raise RuntimeError("Set both GRADIO_AUTH_USERNAME and GRADIO_AUTH_PASSWORD, or neither.")
    return (username, password) if username and password else None


def _public_access_status() -> tuple[str, bool, str | None]:
    mode = _env_str("PUBLIC_ACCESS_MODE", "private").lower() or "private"
    if mode not in _ALLOWED_PUBLIC_ACCESS_MODES:
        return mode, False, "PUBLIC_ACCESS_MODE must be private, authenticated, gateway, or anonymous"
    username = _env_str("GRADIO_AUTH_USERNAME")
    password = _env_str("GRADIO_AUTH_PASSWORD")
    if mode == "authenticated" and not (username and password):
        return mode, False, "authenticated mode requires Gradio username and password"
    if mode == "gateway" and not _env_bool("EXTERNAL_AUTH_GATEWAY"):
        return mode, False, "gateway mode requires EXTERNAL_AUTH_GATEWAY=true"
    if mode == "anonymous" and not _env_bool("ALLOW_ANONYMOUS_PUBLIC"):
        return mode, False, "anonymous mode requires ALLOW_ANONYMOUS_PUBLIC=true"
    return mode, True, None


def _launch_auth_credentials() -> tuple[str, str] | None:
    """Use Gradio auth only when the public mode expects platform-local auth."""
    mode, _, _ = _public_access_status()
    if mode in {"anonymous", "gateway"}:
        return None
    return _auth_credentials()


def _auth_active() -> bool:
    return bool(_launch_auth_credentials() or _env_bool("EXTERNAL_AUTH_GATEWAY", False))


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return int(value)


def _rate_limit_key(bucket: str, suffix: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "_" for ch in bucket.upper()).strip("_")
    return f"RATE_LIMIT_{normalized}_{suffix}"


def _hash_identity(value: str) -> str:
    salt = _env_str("RATE_LIMIT_IDENTITY_SALT") or _env_str("HF_SPACE_ID") or "rag-advisor"
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()[:20]


def _request_identity(request: gr.Request | None = None) -> str:
    """Return a stable, privacy-preserving identity for rate limiting."""
    if request is None:
        return "anonymous:unknown"

    username = str(getattr(request, "username", "") or "").strip()
    if username:
        return f"user:{_hash_identity(username)}"

    headers = getattr(request, "headers", {}) or {}
    header_get = getattr(headers, "get", None)
    forwarded_hosts: list[str] = []
    if callable(header_get) and _env_bool("TRUST_PROXY_HEADERS", True):
        for header_name in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for", "x-client-ip"):
            header_value = str(header_get(header_name, "") or "").strip()
            if header_value:
                forwarded_hosts.append(header_value.split(",", 1)[0].strip())

    client = getattr(request, "client", None)
    client_host = str(getattr(client, "host", "") or "").strip()
    if client_host:
        forwarded_hosts.append(client_host)

    for host in forwarded_hosts:
        if host:
            return f"ip:{_hash_identity(host)}"

    session_hash = str(getattr(request, "session_hash", "") or "").strip()
    if session_hash:
        return f"session:{_hash_identity(session_hash)}"
    return "anonymous:unknown"


def _consume_rate_limit(
    *,
    event_key: str,
    max_requests: int,
    window_seconds: int,
    label: str,
) -> None:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _RATE_LIMIT_LOCK:
        events = _RATE_LIMIT_EVENTS.setdefault(event_key, deque())
        while events and events[0] < cutoff:
            events.popleft()
        if len(events) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - events[0])))
            raise RuntimeError(
                f"Rate limit exceeded ({label}). "
                f"Try again in about {retry_after} seconds."
            )
        events.append(now)


def _enforce_rate_limit(bucket: str, request: gr.Request | None = None) -> None:
    if not _env_bool("RATE_LIMIT_ENABLED", False):
        return

    max_requests = max(
        1,
        _env_int(
            _rate_limit_key(bucket, "MAX_REQUESTS"),
            _env_int("RATE_LIMIT_MAX_REQUESTS", 30),
        ),
    )
    window_seconds = max(
        1,
        _env_int(
            _rate_limit_key(bucket, "WINDOW_SECONDS"),
            _env_int("RATE_LIMIT_WINDOW_SECONDS", 60),
        ),
    )
    identity = _request_identity(request)
    per_identity = _env_bool("RATE_LIMIT_PER_IDENTITY", True)
    event_key = f"{bucket}:{identity}" if per_identity else bucket
    _consume_rate_limit(
        event_key=event_key,
        max_requests=max_requests,
        window_seconds=window_seconds,
        label="Per-user" if per_identity else "Deployment",
    )

    global_max_requests = _env_int(
        _rate_limit_key(bucket, "GLOBAL_MAX_REQUESTS"),
        _env_int("RATE_LIMIT_GLOBAL_MAX_REQUESTS", 0),
    )
    if global_max_requests > 0:
        global_window_seconds = max(
            1,
            _env_int(
                _rate_limit_key(bucket, "GLOBAL_WINDOW_SECONDS"),
                _env_int("RATE_LIMIT_GLOBAL_WINDOW_SECONDS", window_seconds),
            ),
        )
        _consume_rate_limit(
            event_key=f"{bucket}:global",
            max_requests=max(1, global_max_requests),
            window_seconds=global_window_seconds,
            label="Deployment",
        )


def _reset_rate_limiter_for_tests() -> None:
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_EVENTS.clear()


def _validate_text_limit(label: str, value: str | None, key: str, default: int) -> str:
    text = value or ""
    limit = max(1, _env_int(key, default))
    if len(text) > limit:
        raise RuntimeError(f"{label} is too long. Limit it to {limit} characters.")
    return text


def _prepare_advisor_inputs(
    user_brief: str,
    elicitation_answers: str | None,
    conflict_resolution: str | None,
    deep_thinking: bool,
) -> tuple[str, str | None, str | None]:
    brief = _validate_text_limit("Brief", user_brief, "MAX_BRIEF_CHARS", 4000).strip()
    answers = _validate_text_limit(
        "Follow-up answers",
        elicitation_answers,
        "MAX_ELICITATION_CHARS",
        2000,
    )
    conflict = _validate_text_limit(
        "Conflict resolution",
        conflict_resolution,
        "MAX_CONFLICT_CHARS",
        1000,
    )
    if deep_thinking and not _env_bool("DEEP_THINKING_ENABLED", True):
        raise RuntimeError("Deep thinking is currently disabled for this deployment.")
    return brief, answers, conflict


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_log_path(env_key: str) -> Path | None:
    raw_path = _env_str(env_key)
    return Path(raw_path).expanduser() if raw_path else None


def _append_jsonl(env_key: str, payload: dict[str, Any]) -> None:
    path = _json_log_path(env_key)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _REQUEST_LOG_LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except OSError:
        # Logging must never make the public endpoint unavailable.
        return


def _usage_budget_limits(deep_thinking: bool) -> dict[str, int]:
    return {
        "daily": _env_int("DAILY_REQUEST_BUDGET", 0),
        "monthly": _env_int("MONTHLY_REQUEST_BUDGET", 0),
        "daily_deep": _env_int("DAILY_DEEP_REQUEST_BUDGET", 0) if deep_thinking else 0,
        "monthly_deep": _env_int("MONTHLY_DEEP_REQUEST_BUDGET", 0) if deep_thinking else 0,
    }


def _usage_budget_configured() -> bool:
    return bool(_json_log_path("ADVISOR_USAGE_COUNTER_PATH")) and any(
        _usage_budget_limits(True).values()
    )


def _public_deep_thinking_controls_ok() -> bool:
    if not _env_bool("DEEP_THINKING_ENABLED", True):
        return True
    standard_limit = _env_int(
        "RATE_LIMIT_ADVISOR_MAX_REQUESTS",
        _env_int("RATE_LIMIT_MAX_REQUESTS", 30),
    )
    deep_limit = _env_int("RATE_LIMIT_ADVISOR_DEEP_MAX_REQUESTS", 0)
    daily_deep = _env_int("DAILY_DEEP_REQUEST_BUDGET", 0)
    monthly_deep = _env_int("MONTHLY_DEEP_REQUEST_BUDGET", 0)
    max_full_text_links = _env_int("DEEP_RESEARCH_MAX_FULL_TEXT_LINKS", 4)
    return (
        0 < deep_limit <= max(1, standard_limit)
        and 0 < daily_deep <= monthly_deep
        and 0 <= max_full_text_links <= 4
    )


def _enforce_usage_budget(deep_thinking: bool) -> None:
    path = _json_log_path("ADVISOR_USAGE_COUNTER_PATH")
    limits = _usage_budget_limits(deep_thinking)
    if path is None or not any(limits.values()):
        return

    now = _utc_now()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    with _USAGE_BUDGET_LOCK:
        state: dict[str, Any] = {}
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                state = {}
        if state.get("day") != today:
            state["day"] = today
            state["requests_today"] = 0
            state["deep_requests_today"] = 0
        if state.get("month") != month:
            state["month"] = month
            state["requests_month"] = 0
            state["deep_requests_month"] = 0

        checks = [
            ("daily", "requests_today", "daily public request budget"),
            ("monthly", "requests_month", "monthly public request budget"),
        ]
        if deep_thinking:
            checks.extend(
                [
                    ("daily_deep", "deep_requests_today", "daily deep-thinking budget"),
                    ("monthly_deep", "deep_requests_month", "monthly deep-thinking budget"),
                ]
            )
        for limit_name, counter_name, label in checks:
            limit = int(limits.get(limit_name) or 0)
            if limit > 0 and int(state.get(counter_name) or 0) >= limit:
                raise RuntimeError(f"The {label} has been reached for this deployment.")

        state["requests_today"] = int(state.get("requests_today") or 0) + 1
        state["requests_month"] = int(state.get("requests_month") or 0) + 1
        if deep_thinking:
            state["deep_requests_today"] = int(state.get("deep_requests_today") or 0) + 1
            state["deep_requests_month"] = int(state.get("deep_requests_month") or 0) + 1
        state["updated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        except OSError:
            raise RuntimeError("Usage budget counter is not writable.")


def _ops_token() -> str:
    return _env_str("METRICS_AUTH_TOKEN") or _env_str("OPERATIONS_TOKEN")


def _require_ops_token(token: str | None) -> None:
    configured = _ops_token()
    if configured and (token or "").strip() != configured:
        raise RuntimeError("Metrics endpoint requires a valid operations token.")


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return round(ordered[index], 2)


def _metrics_sample_limit() -> int:
    return max(10, _env_int("OBSERVABILITY_SAMPLE_LIMIT", 200))


def _advisor_concurrency_limit() -> int:
    return max(1, _env_int("ADVISOR_CONCURRENCY_LIMIT", 2))


def _advisor_queue_max_size() -> int:
    return max(1, _env_int("ADVISOR_QUEUE_MAX_SIZE", 32))


def _record_request_metric(
    *,
    latency_ms: float,
    deep_thinking: bool,
    generation_status: str,
    timings_ms: dict[str, Any] | None = None,
    request_identity: str | None = None,
    error: Exception | None = None,
) -> None:
    now = _utc_now()
    alert_reasons: list[str] = []
    with _METRICS_LOCK:
        _REQUEST_METRICS["total"] += 1
        _REQUEST_METRICS["last_request_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        _REQUEST_METRICS["last_timings_ms"] = dict(timings_ms or {})
        if deep_thinking:
            _REQUEST_METRICS["deep_thinking_total"] += 1
        statuses = _REQUEST_METRICS["generation_status"]
        statuses[generation_status] = int(statuses.get(generation_status, 0)) + 1
        if error is not None:
            _REQUEST_METRICS["errors"] += 1
            _REQUEST_METRICS["last_error"] = {
                "type": type(error).__name__,
                "message": str(error)[:300],
            }
            alert_reasons.append("failed_call")
        samples = _REQUEST_METRICS["latencies_ms"]
        samples.append(round(latency_ms, 2))
        del samples[:-_metrics_sample_limit()]

        window_seconds = max(1, _env_int("REQUEST_ALERT_WINDOW_SECONDS", 300))
        spike_threshold = _env_int("REQUEST_ALERT_MAX_REQUESTS", 0)
        monotonic_now = time.monotonic()
        _REQUEST_EVENT_TIMES.append(monotonic_now)
        cutoff = monotonic_now - window_seconds
        while _REQUEST_EVENT_TIMES and _REQUEST_EVENT_TIMES[0] < cutoff:
            _REQUEST_EVENT_TIMES.popleft()
        spike_count = len(_REQUEST_EVENT_TIMES)
        if spike_threshold > 0 and spike_count >= spike_threshold:
            alert_reasons.append("traffic_spike")

    latency_alert_ms = _env_int("REQUEST_ALERT_LATENCY_MS", 0)
    if latency_alert_ms > 0 and latency_ms >= latency_alert_ms:
        alert_reasons.append("slow_call")

    event = {
        "event": "request",
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deep_thinking": bool(deep_thinking),
        "generation_status": generation_status,
        "latency_ms": round(latency_ms, 2),
        "graph_timings_ms": dict(timings_ms or {}),
        "request_identity": request_identity,
        "error_type": type(error).__name__ if error else None,
    }
    _append_jsonl("ADVISOR_REQUEST_LOG_PATH", event)
    if alert_reasons:
        _append_jsonl(
            "ADVISOR_ALERT_LOG_PATH",
            {
                "event": "alert",
                "timestamp": event["timestamp"],
                "reasons": sorted(set(alert_reasons)),
                "request": event,
                "window_seconds": _env_int("REQUEST_ALERT_WINDOW_SECONDS", 300),
                "window_request_count": spike_count if "traffic_spike" in alert_reasons else None,
            },
        )


def metrics_api(token: str = "") -> dict[str, Any]:
    """Return process-local advisor metrics without exposing request content."""
    _require_ops_token(token)
    with _METRICS_LOCK:
        latencies = list(_REQUEST_METRICS["latencies_ms"])
        return {
            "requests_total": int(_REQUEST_METRICS["total"]),
            "errors_total": int(_REQUEST_METRICS["errors"]),
            "deep_thinking_total": int(_REQUEST_METRICS["deep_thinking_total"]),
            "generation_status": dict(_REQUEST_METRICS["generation_status"]),
            "latency_ms": {
                "count": len(latencies),
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "p99": _percentile(latencies, 0.99),
                "max": round(max(latencies), 2) if latencies else None,
            },
            "last_request_at": _REQUEST_METRICS["last_request_at"],
            "last_timings_ms": dict(_REQUEST_METRICS["last_timings_ms"]),
            "last_error": _REQUEST_METRICS["last_error"],
        }


def health_api() -> dict[str, Any]:
    """Return a cheap production health/config summary with no secrets."""
    vector_backend = os.getenv("VECTOR_STORE_BACKEND", "memory").strip().lower()
    qdrant_configured = bool(os.getenv("QDRANT_URL", "").strip() or os.getenv("QDRANT_LOCAL_PATH", "").strip())
    public_mode, public_access_configured, public_access_error = _public_access_status()
    auth_error = ""
    try:
        auth_configured = _auth_active()
    except RuntimeError as exc:
        auth_configured = False
        auth_error = str(exc)
    rate_limit_configured = _env_bool("RATE_LIMIT_ENABLED", False) or _env_bool(
        "EXTERNAL_RATE_LIMITING",
        False,
    )
    identity_rate_limit_configured = (
        _env_bool("RATE_LIMIT_ENABLED", False)
        and _env_bool("RATE_LIMIT_PER_IDENTITY", True)
    ) or _env_bool("EXTERNAL_RATE_LIMITING", False)
    request_log_configured = bool(_json_log_path("ADVISOR_REQUEST_LOG_PATH"))
    alert_log_configured = bool(_json_log_path("ADVISOR_ALERT_LOG_PATH"))
    usage_budget_configured = _usage_budget_configured()
    deep_thinking_enabled = _env_bool("DEEP_THINKING_ENABLED", True)
    public_deep_thinking_controls_ok = _public_deep_thinking_controls_ok()
    anonymous_controls_ok = (
        public_mode != "anonymous"
        or (
            identity_rate_limit_configured
            and request_log_configured
            and alert_log_configured
            and usage_budget_configured
            and public_deep_thinking_controls_ok
        )
    )
    checks = {
        "llm_provider": os.getenv("LLM_PROVIDER", "hf").strip().lower(),
        "retrieval_mode": os.getenv("RETRIEVAL_MODE", "lexical").strip().lower(),
        "vector_store_backend": vector_backend,
        "vector_store_configured": vector_backend != "qdrant" or qdrant_configured,
        "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "local").strip().lower(),
        "public_access_mode": public_mode,
        "public_access_configured": public_access_configured,
        "public_access_error": public_access_error,
        "auth_configured": auth_configured,
        "auth_error": auth_error,
        "rate_limit_configured": rate_limit_configured,
        "identity_rate_limit_configured": identity_rate_limit_configured,
        "advisor_concurrency_limit": _advisor_concurrency_limit(),
        "advisor_queue_max_size": _advisor_queue_max_size(),
        "metrics_protected": bool(_ops_token()),
        "audit_log_configured": bool(os.getenv("ADVISOR_AUDIT_LOG_PATH", "").strip()),
        "request_log_configured": request_log_configured,
        "alert_log_configured": alert_log_configured,
        "usage_budget_configured": usage_budget_configured,
        "deep_thinking_enabled": deep_thinking_enabled,
        "public_deep_thinking_controls_ok": public_deep_thinking_controls_ok,
        "anonymous_controls_ok": anonymous_controls_ok,
        "raw_trace_hidden": not _env_bool("SHOW_RAW_TRACE", False),
    }
    return {
        "status": "ok"
        if checks["vector_store_configured"]
        and checks["public_access_configured"]
        and checks["anonymous_controls_ok"]
        and checks["raw_trace_hidden"]
        and checks["metrics_protected"]
        and not auth_error
        else "degraded",
        "checks": checks,
    }


def _evidence_refs_text(refs: list[str]) -> str:
    return " ".join(f"[{ref}]" for ref in refs)


def _source_label(source: dict[str, Any], fallback_index: int) -> str:
    return str(source.get("evidence_label") or f"E{fallback_index}")


def _parse_elicitation_answers(value: str | None) -> dict[str, str]:
    if not value or not value.strip():
        return {}
    stripped = value.strip()
    if stripped.startswith("{"):
        parsed = json.loads(stripped)
        return {str(key): str(item) for key, item in parsed.items() if str(item).strip()}

    answers: dict[str, str] = {}
    for line in stripped.splitlines():
        if "=" not in line:
            continue
        key, answer = line.split("=", 1)
        if key.strip() and answer.strip():
            answers[key.strip()] = answer.strip()
    return answers


def _requirement_value(state: AdvisorState, attr: str) -> str | None:
    return state.requirement_vector.get(attr).value if attr in state.requirement_vector else None


def _format_topology_rationale(state: AdvisorState, topology: dict) -> str:
    drivers = []
    for attr in ("A2", "A3", "A1", "A8", "A11", "A12"):
        value = _requirement_value(state, attr)
        if value:
            drivers.append(f"{ATTRIBUTE_LABELS.get(attr, attr)} is **{value}**")
    driver_text = "; ".join(drivers)
    lines = [
        "Selected by applying the resolved requirements to the fixed topology catalog.",
    ]
    if driver_text:
        lines.append(f"Key drivers: {driver_text}.")
    lines.extend(_readable_topology_filters(topology))
    return " ".join(lines)


def _readable_topology_filters(topology: dict) -> list[str]:
    filters = (topology.get("selection") or {}).get("filters") or []
    readable_filters = []
    for item in filters:
        if "A2 high" in item:
            readable_filters.append(
                "Dense-only options were removed because exact terminology dependence is high."
            )
        elif "A12 gated" in item:
            readable_filters.append(
                "Direct-answer options were removed because the workflow requires a review gate."
            )
        elif "A8 strict" in item:
            readable_filters.append(
                "Adaptive loops were avoided unless risk justified the extra latency."
            )
    return readable_filters


def _readable_constraint(constraint: str) -> str:
    if constraint.startswith("A2 high"):
        return "High exact terminology dependence makes lexical or hybrid retrieval mandatory."
    if constraint.startswith("A4 sectoral"):
        return "Sectoral compliance requires in-boundary generation providers."
    if constraint.startswith("A5 regulated-personal"):
        return "Regulated personal data requires permission-aware retrieval and redaction."
    if constraint.startswith("A11 mandatory"):
        return "Mandatory citation needs require decision lineage logging."
    if constraint.startswith("A12 gated"):
        return "Human review requirements rule out direct-answer deployment without a review gate."
    return constraint


def _format_output(state: AdvisorState) -> str:
    output = state.draft_output or {}
    topology = output.get("topology", {})
    panel = output.get("panel", {})
    terraform = output.get("terraform", "")
    architecture_decisions = output.get("architecture_decisions") or []
    sources = output.get("sources") or []
    generated_answer = output.get("generated_answer")

    lines = [
        "## Recommendation",
        f"**Topology:** {topology.get('name', 'pending')}",
        "",
        "## Why",
    ]
    for entry in state.decision_log[:8]:
        label = ATTRIBUTE_LABELS.get(entry.attr, entry.attr)
        lines.append(f"- {label}: {entry.value} ({entry.source.replace('-', ' ')})")

    if generated_answer:
        lines.extend(["", "## Generated Advisor Summary", str(generated_answer).strip()])

    lines.extend(["", "## Strengths"])
    for item in panel.get("strengths", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Weaknesses"])
    for item in panel.get("weaknesses", []):
        lines.append(f"- {item}")

    if architecture_decisions:
        lines.extend(["", "## Architecture Decisions"])
        for decision in architecture_decisions:
            area = str(decision.get("area") or "decision").replace("_", " ").title()
            choice = decision.get("choice") or "Pending"
            evidence_refs = decision.get("evidence_refs") or []
            lines.append(f"- **{area}:** {choice}")
            if decision.get("rationale"):
                lines.append(f"  {decision['rationale']}")
            for step in decision.get("reasoning_steps") or []:
                lines.append(f"  - {step}")
            if decision.get("tradeoff"):
                lines.append(f"  Tradeoff: {decision['tradeoff']}")
            if decision.get("validation"):
                lines.append(f"  Validate: {decision['validation']}")
            if evidence_refs:
                lines.append(f"  Evidence: {_evidence_refs_text(evidence_refs[:3])}")

    if terraform:
        lines.extend(["", "## Terraform Sketch", "```hcl", terraform.strip(), "```"])

    if sources:
        lines.extend(["", "## Sources"])
        for index, source in enumerate(sources[:8], start=1):
            title = source.get("title") or "Untitled source"
            section = source.get("section") or "Unsectioned"
            evidence_label = source.get("evidence_label") or f"E{index}"
            used_by = ", ".join(source.get("used_by") or [])
            label = section if section.startswith(title) else f"{title} - {section}"
            lines.append(f"- [{evidence_label}] {label}")
            if used_by:
                lines.append(f"  Used by: {used_by}")
            if source.get("snippet"):
                lines.append(f"  Evidence summary: {source['snippet']}")

    return "\n".join(lines)


def _format_recommendation(state: AdvisorState) -> str:
    output = state.draft_output or {}
    topology = output.get("topology", {})
    panel = output.get("panel", {})
    generated_answer = output.get("generated_answer")
    lines = [
        f"## {topology.get('name', 'Pending')}",
        _format_topology_rationale(state, topology),
    ]

    if generated_answer:
        lines.extend(["", str(generated_answer).strip()])

    if state.pending_elicitation:
        lines.extend(["", "### Questions To Confirm"])
        for attr in state.pending_elicitation:
            lines.append(f"- {ATTRIBUTE_LABELS.get(attr, attr)}")

    strengths = panel.get("strengths", [])[:3]
    weaknesses = panel.get("weaknesses", [])[:3]
    if strengths or weaknesses:
        lines.extend(["", "### Advisor Checks"])
        for item in strengths:
            lines.append(f"- Strength: {item}")
        for item in weaknesses:
            lines.append(f"- Risk: {item}")

    return "\n".join(line for line in lines if line is not None)


def _format_architecture_decisions(state: AdvisorState) -> str:
    decisions = (state.draft_output or {}).get("architecture_decisions") or []
    if not decisions:
        return "No architecture decisions generated."

    lines = []
    for decision in decisions:
        area = str(decision.get("area") or "decision").replace("_", " ").title()
        lines.append(f"### {area}")
        lines.append(str(decision.get("choice") or "Pending"))
        if decision.get("rationale"):
            lines.extend(["", "**Why:**", str(decision["rationale"])])
        if decision.get("reasoning_steps"):
            lines.extend(["", "**Reasoning:**"])
            for step in decision["reasoning_steps"]:
                lines.append(f"- {step}")
        if decision.get("tradeoff"):
            lines.extend(["", "**Accepted Tradeoff:**", str(decision["tradeoff"])])
        if decision.get("validation"):
            lines.extend(["", "**Validation Gate:**", str(decision["validation"])])
        evidence_refs = decision.get("evidence_refs") or []
        if evidence_refs:
            lines.extend(["", "**Evidence:** " + _evidence_refs_text(evidence_refs)])
        evidence_chunks = decision.get("evidence_chunks") or []
        if evidence_chunks:
            lines.extend(["", "**Evidence Summaries:**"])
            for chunk in evidence_chunks:
                label = chunk.get("evidence_label") or "E?"
                lines.append(
                    f"- [{label}] {chunk.get('reasoning_chunk') or chunk.get('snippet') or ''}"
                )
        lines.append("")
    return "\n".join(lines).strip()


def _source_rows(state: AdvisorState) -> list[list[Any]]:
    sources = (state.draft_output or {}).get("sources") or []
    rows: list[list[Any]] = []
    for index, source in enumerate(sources, start=1):
        rows.append(
            [
                index,
                ", ".join(source.get("used_by") or []),
                source.get("evidence_label") or f"E{index}",
                source.get("section") or "",
                source.get("snippet") or "",
            ]
        )
    return rows


def _public_reasoning_chunks(source_rows: list[list[Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for row in source_rows:
        chunks.append(
            {
                "rank": row[0],
                "used_by": row[1],
                "evidence": row[2],
                "section": row[3],
                "reasoning_chunk": row[4],
            }
        )
    return chunks


def _public_generation_status(raw_trace: dict[str, Any]) -> dict[str, Any]:
    generation = raw_trace.get("draft_output", {}).get("generation") or {}
    return {
        "status": generation.get("status"),
        "provider": generation.get("provider"),
        "model": generation.get("model"),
        "quality_issue": generation.get("quality_issue"),
    }


def _public_research_links(raw_trace: dict[str, Any]) -> list[dict[str, Any]]:
    links = (raw_trace.get("draft_output", {}) or {}).get("research_links") or []
    return [
        {
            "agent": link.get("agent"),
            "label": link.get("label"),
            "url": link.get("url"),
            "source_type": link.get("source_type"),
            "relevance": link.get("relevance"),
        }
        for link in links
        if str(link.get("url") or "").startswith("http")
    ]


def _public_research_findings(raw_trace: dict[str, Any]) -> list[dict[str, Any]]:
    findings = (raw_trace.get("draft_output", {}) or {}).get("research_findings") or []
    return [
        {
            "agent": finding.get("agent"),
            "summary": finding.get("summary"),
            "status": finding.get("status"),
            "duration_ms": finding.get("duration_ms"),
            "link_count": len(finding.get("links") or []),
            "approach_summaries": [
                {
                    "label": item.get("label"),
                    "url": item.get("url"),
                    "source_type": item.get("source_type"),
                    "status": item.get("status"),
                    "word_count": item.get("word_count"),
                    "summary": item.get("summary"),
                    "approach_steps": item.get("approach_steps") or [],
                    "implementation_notes": item.get("implementation_notes") or [],
                    "limitations": item.get("limitations") or [],
                }
                for item in finding.get("approach_summaries") or []
            ],
        }
        for finding in findings
    ]


def _public_research_approach_summaries(raw_trace: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for finding in _public_research_findings(raw_trace):
        agent = finding.get("agent")
        for item in finding.get("approach_summaries") or []:
            summaries.append({"agent": agent, **item})
    return summaries


def _format_deployment(state: AdvisorState) -> str:
    projection = (state.draft_output or {}).get("projection") or {}
    pipeline_nodes = projection.get("pipeline_nodes") or []
    deployment_components = projection.get("deployment_components") or []
    projection_edges = projection.get("projection_edges") or []

    lines = ["## Diagram", "```mermaid", "flowchart LR"]
    if pipeline_nodes:
        lines.append("  subgraph pipeline[Pipeline]")
        for node in pipeline_nodes:
            node_id = str(node.get("id") or "").replace("-", "_")
            label = str(node.get("label") or node.get("id") or "")
            lines.append(f"    {node_id}[{label}]")
        lines.append("  end")
    if deployment_components:
        lines.append("  subgraph deployment[Deployment]")
        for component in deployment_components:
            component_id = str(component.get("id") or "").replace("-", "_")
            label = str(component.get("label") or component.get("id") or "")
            lines.append(f"    {component_id}[{label}]")
        lines.append("  end")
    for edge in projection_edges[:40]:
        source = str(edge.get("from") or "").replace("-", "_")
        target = str(edge.get("to") or "").replace("-", "_")
        lines.append(f"  {source} -.-> {target}")
    lines.extend(["```", "", "## Pipeline"])
    for node in pipeline_nodes:
        lines.append(f"{node.get('order')}. **{node.get('label')}** (`{node.get('id')}`)")

    lines.extend(["", "## Deployment Projection"])
    for component in deployment_components:
        serves = ", ".join(f"`{stage}`" for stage in component.get("serves") or [])
        controls = ", ".join(f"`{control}`" for control in component.get("controls") or [])
        lines.append(f"- **{component.get('label')}** ({component.get('pillar')})")
        lines.append(f"  Serves: {serves or 'none'}")
        lines.append(f"  Controls: {controls or 'none'}")

    if projection_edges:
        lines.extend(["", "## Projection Edges"])
        for edge in projection_edges[:24]:
            lines.append(f"- `{edge.get('from')}` -> `{edge.get('to')}`")
    return "\n".join(lines)


def _format_trace(state: AdvisorState) -> str:
    output = state.draft_output or {}
    topology = output.get("topology") or {}
    evidence_pack = output.get("evidence_pack") or {}
    decisions = output.get("architecture_decisions") or []
    panel = output.get("panel") or {}

    lines = [
        "## Advisor Reasoning Trace",
        "### 1. Interpreted the brief",
        f"- Domain prior: **{state.domain_prior or 'unknown'}**.",
    ]

    stated = [entry for entry in state.decision_log if entry.source == "stated"]
    strong = [
        entry
        for entry in state.decision_log
        if entry.source == "domain-prior" and entry.confidence >= 0.9
    ]
    if stated:
        lines.append("- User-stated signals:")
        for entry in stated:
            label = ATTRIBUTE_LABELS.get(entry.attr, entry.attr)
            lines.append(f"  - {label}: **{entry.value}**.")
    if strong:
        lines.append("- Strong prior signals:")
        for entry in strong[:6]:
            label = ATTRIBUTE_LABELS.get(entry.attr, entry.attr)
            lines.append(f"  - {label}: **{entry.value}**.")

    if state.pending_elicitation:
        pending_labels = [
            ATTRIBUTE_LABELS.get(attr, attr)
            for attr in state.pending_elicitation
        ]
        lines.append(
            "- Still uncertain: "
            + ", ".join(pending_labels)
            + ". The recommendation remains provisional until these are confirmed."
        )

    if state.hard_constraints:
        lines.extend(["", "### 2. Applied hard constraints"])
        for constraint in state.hard_constraints:
            lines.append(f"- {_readable_constraint(constraint)}")

    sources = evidence_pack.get("sources") or []
    if sources:
        lines.extend(["", "### 3. Read the literature chunks"])
        for index, source in enumerate(sources[:8], start=1):
            label = _source_label(source, index)
            used_by = ", ".join(source.get("used_by") or [])
            section = source.get("section") or "Unsectioned"
            snippet = source.get("snippet") or ""
            lines.append(f"- [{label}] {section}")
            if used_by:
                lines.append(f"  Used for: {used_by}")
            if snippet:
                lines.append(f"  Evidence summary: {snippet}")

    if topology:
        lines.extend(["", "### 4. Selected the topology"])
        lines.append(f"- Selected **{topology.get('name', 'pending')}**.")
        lines.append(f"- {_format_topology_rationale(state, topology)}")
        selection = topology.get("selection") or {}
        filters = selection.get("filters") or []
        readable_filters = _readable_topology_filters(topology)
        if filters and readable_filters:
            lines.append("- Filters applied:")
            for item in readable_filters:
                lines.append(f"  - {item}")

    if decisions:
        lines.extend(["", "### 5. Turned evidence into architecture decisions"])
        for decision in decisions:
            area = str(decision.get("area") or "decision").replace("_", " ").title()
            refs = _evidence_refs_text(decision.get("evidence_refs") or [])
            evidence = f" {refs}" if refs else ""
            lines.append(f"- **{area}:** {decision.get('choice', 'Pending')}{evidence}")
            if decision.get("rationale"):
                lines.append(f"  Why: {decision['rationale']}")
            if decision.get("tradeoff"):
                lines.append(f"  Tradeoff: {decision['tradeoff']}")

    panel_items = panel.get("items") or []
    if panel_items:
        lines.extend(["", "### 6. Checked user-facing tradeoffs"])
        for item in panel_items[:8]:
            refs = _evidence_refs_text(item.get("evidence_refs") or [])
            evidence = f" {refs}" if refs else ""
            lines.append(
                f"- **{item.get('label')}:** {item.get('accepted_tradeoff')}{evidence}"
            )

    research_findings = (output.get("research_findings") or []) if output else []
    if state.deep_thinking and research_findings:
        lines.extend(["", "### 7. Ran deep research agents"])
        for finding in research_findings:
            approaches = finding.get("approach_summaries") or []
            read_count = sum(1 for item in approaches if item.get("status") == "ok")
            lines.append(
                f"- **{finding.get('agent')}:** {finding.get('summary')} "
                f"(status: {finding.get('status')}; full references read: {read_count})"
            )

    if state.conflict:
        lines.extend(["", "### Unresolved conflict"])
        lines.append(state.conflict.rationale)
        for option in state.conflict.options:
            lines.append(f"- {option}")

    if state.critique:
        lines.extend(["", "### Critic check"])
        for item in state.critique:
            lines.append(f"- {item}")
    else:
        lines.extend(["", "### Critic check", "- No skeleton-level critique remained after synthesis."])
    return "\n".join(lines)


def _format_research(state: AdvisorState) -> str:
    output = state.draft_output or {}
    findings = output.get("research_findings") or []
    if not state.deep_thinking:
        return "Deep thinking is disabled for this run."
    if not findings:
        return "Deep thinking was enabled, but no research findings were returned."

    lines = ["## Deep Research Agents"]
    for finding in findings:
        lines.append(f"### {str(finding.get('agent') or 'research').replace('_', ' ').title()}")
        lines.append(str(finding.get("summary") or "No summary returned."))
        lines.append(f"Status: `{finding.get('status')}` - Duration: `{finding.get('duration_ms')} ms`")
        links = finding.get("links") or []
        if links:
            lines.append("")
            lines.append("Links:")
            for link in links[:8]:
                label = str(link.get("label") or link.get("url") or "Source")
                url = str(link.get("url") or "")
                source_type = str(link.get("source_type") or "web")
                relevance = str(link.get("relevance") or "")
                lines.append(f"- [{label}]({url}) - `{source_type}`")
                if relevance:
                    lines.append(f"  {relevance}")
        approaches = finding.get("approach_summaries") or []
        if approaches:
            lines.append("")
            lines.append("Full-Reference Approach Summaries:")
            for item in approaches[:6]:
                label = str(item.get("label") or "Reference")
                url = str(item.get("url") or "")
                status = str(item.get("status") or "unknown")
                word_count = item.get("word_count") or 0
                lines.append(f"- [{label}]({url}) - `{status}`, `{word_count}` words")
                if item.get("summary"):
                    lines.append(f"  {item['summary']}")
                for step in (item.get("approach_steps") or [])[:3]:
                    lines.append(f"  Approach: {step}")
                for note in (item.get("implementation_notes") or [])[:2]:
                    lines.append(f"  Implementation: {note}")
                for limitation in (item.get("limitations") or [])[:2]:
                    lines.append(f"  Limitation: {limitation}")
        subqueries = finding.get("subqueries") or []
        if subqueries:
            lines.append("")
            lines.append("Subqueries:")
            for query in subqueries[:6]:
                lines.append(f"- {query}")
        lines.append("")
    return "\n".join(lines).strip()


def _terraform(state: AdvisorState) -> str:
    return str((state.draft_output or {}).get("terraform") or "")


def _empty_detail_response(
    message: str,
) -> DetailResponse:
    return message, "", [], "", "", "", "", {}


def clear_detail_response() -> ClearDetailResponse:
    return "", "", [], "", "", "", "", "", {}


def advise(user_brief: str, request: gr.Request | None = None) -> tuple[str, dict[str, Any]]:
    brief, _, _ = _prepare_advisor_inputs(user_brief, None, None, False)
    if not brief:
        return "Enter a brief to generate an initial advisor trace.", {}
    _enforce_rate_limit("legacy", request)
    _enforce_usage_budget(False)

    graph = build_graph()
    state = graph.invoke({"user_brief": brief})
    return _format_output(state), state.to_dict()


def advise_detailed(
    user_brief: str,
    elicitation_answers: str | None = None,
    conflict_resolution: str | None = None,
    deep_thinking: bool = False,
    request: gr.Request | None = None,
) -> DetailResponse:
    brief, answers, conflict = _prepare_advisor_inputs(
        user_brief,
        elicitation_answers,
        conflict_resolution,
        deep_thinking,
    )
    if not brief:
        return _empty_detail_response("Enter a brief to generate an initial advisor trace.")
    _enforce_rate_limit("advisor_deep" if deep_thinking else "advisor", request)
    _enforce_usage_budget(deep_thinking)

    graph = build_graph()
    state = graph.invoke(
        {
            "user_brief": brief,
            "elicitation_answers": _parse_elicitation_answers(answers),
            "conflict_resolution": (conflict or "").strip() or None,
            "deep_thinking": deep_thinking,
        }
    )
    return (
        _format_recommendation(state),
        _format_architecture_decisions(state),
        _source_rows(state),
        _format_deployment(state),
        _terraform(state),
        _format_trace(state),
        _format_research(state),
        state.to_dict(),
    )


def advise_api(
    user_brief: str,
    elicitation_answers: str | None = None,
    conflict_resolution: str | None = None,
    deep_thinking: bool = False,
    request: gr.Request | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    request_identity = _request_identity(request)
    try:
        (
            recommendation,
            architecture_decisions,
            source_rows,
            deployment_projection,
            terraform_sketch,
            advisor_reasoning_trace,
            research,
            raw_trace,
        ) = advise_detailed(user_brief, elicitation_answers, conflict_resolution, deep_thinking, request)
        topology = raw_trace.get("draft_output", {}).get("topology") or {}
        generation = _public_generation_status(raw_trace)
        timings_ms = raw_trace.get("timings_ms") or {}
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        payload = {
            "topology": topology.get("name"),
            "recommendation": recommendation,
            "architecture_decisions": architecture_decisions,
            "reasoning_chunks": _public_reasoning_chunks(source_rows),
            "deployment_projection": deployment_projection,
            "terraform_sketch": terraform_sketch,
            "advisor_reasoning_trace": advisor_reasoning_trace,
            "deep_thinking": bool(raw_trace.get("deep_thinking")),
            "research": research,
            "research_findings": _public_research_findings(raw_trace),
            "research_approach_summaries": _public_research_approach_summaries(raw_trace),
            "research_links": _public_research_links(raw_trace),
            "pending_questions": [
                ATTRIBUTE_LABELS.get(attr, attr)
                for attr in raw_trace.get("pending_elicitation", [])
            ],
            "generation": generation,
            "runtime": {
                "latency_ms": latency_ms,
                "graph_timings_ms": timings_ms,
            },
        }
        _record_request_metric(
            latency_ms=latency_ms,
            deep_thinking=bool(raw_trace.get("deep_thinking")),
            generation_status=str(generation.get("status") or "unknown"),
            timings_ms=timings_ms,
            request_identity=request_identity,
        )
        return payload
    except Exception as exc:
        _record_request_metric(
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            deep_thinking=deep_thinking,
            generation_status="error",
            request_identity=request_identity,
            error=exc,
        )
        raise


def build_demo():
    if gr is None:
        raise RuntimeError("gradio is not installed. Install requirements.txt to run the app.")

    with gr.Blocks(title="RAG Architecture Advisor") as demo:
        show_raw_trace = _env_bool("SHOW_RAW_TRACE", False)
        deep_thinking_enabled = _env_bool("DEEP_THINKING_ENABLED", True)
        public_notice = (
            PUBLIC_NOTICE_MD
            if deep_thinking_enabled
            else PUBLIC_NOTICE_MD.replace(
                "- Deep thinking reads selected public references and may take longer than a standard run.",
                "- Deep thinking is disabled for anonymous public access.",
            )
        )
        gr.HTML(f"<style>{APP_CSS}</style>")
        gr.Markdown(PUBLIC_HEADER_MD)
        with gr.Row(equal_height=False, elem_classes=["advisor-input-grid"]):
            with gr.Column(scale=2, min_width=0, elem_classes=["advisor-main-column"]):
                brief = gr.Textbox(
                    label="Brief",
                    lines=9,
                    max_lines=14,
                    placeholder=(
                        "Describe the use case, users, sources, freshness, sensitivity, "
                        "latency, and citation needs. Do not paste secrets."
                    ),
                )
                with gr.Row(elem_classes=["advisor-action-row"]):
                    run = gr.Button("Advise", variant="primary", scale=2)
                    clear = gr.Button("Clear", scale=1)
                gr.Examples(examples=EXAMPLE_BRIEFS, inputs=brief, label="Examples")
                with gr.Accordion("Optional controls", open=False):
                    elicitation_answers = gr.Textbox(
                        label="Follow-up answers",
                        lines=4,
                        placeholder='JSON like {"A7": "periodic"} or lines like A7=periodic',
                    )
                    conflict_resolution = gr.Textbox(
                        label="Conflict resolution",
                        lines=2,
                        placeholder="Example: preserve_compliance",
                    )
                    deep_thinking = gr.Checkbox(
                        label="Deep thinking",
                        value=False,
                        visible=deep_thinking_enabled,
                    )
            with gr.Column(scale=1, min_width=0, elem_classes=["advisor-side-column"]):
                gr.Markdown(public_notice, elem_classes=["advisor-notice"])
                with gr.Accordion("Operational boundary", open=False):
                    gr.Markdown(
                        "Public runs are rate limited. Standard mode is the default. "
                        + (
                            "Deep thinking is reserved for briefs that need full-reference "
                            "research synthesis."
                            if deep_thinking_enabled
                            else "Deep thinking is disabled on the anonymous public surface."
                        )
                    )

        with gr.Tabs(elem_classes=["advisor-tabs"]):
            with gr.Tab("Recommendation"):
                recommendation = gr.Markdown(label="Recommendation")
            with gr.Tab("Architecture"):
                decisions = gr.Markdown(label="Architecture Decisions")
            with gr.Tab("Evidence"):
                sources = gr.Dataframe(
                    headers=["#", "Used By", "Evidence", "Section", "Evidence Summary"],
                    datatype=["number", "str", "str", "str", "str"],
                    interactive=False,
                    label="Evidence Summaries",
                )
            with gr.Tab("Deployment"):
                deployment = gr.Markdown(label="Deployment Projection")
            with gr.Tab("Terraform"):
                terraform = gr.Textbox(label="Terraform Sketch", lines=18)
            with gr.Tab("Trace"):
                trace = gr.Markdown(label="Advisor Reasoning Trace")
            with gr.Tab("Research"):
                research = gr.Markdown(label="Deep Research Links")
            if show_raw_trace:
                with gr.Tab("Raw JSON"):
                    raw_trace = gr.JSON(label="Raw Trace")
            else:
                raw_trace = gr.JSON(label="Raw Trace", visible=False)
        public_api_payload = gr.JSON(label="Public API Response", visible=False)
        public_api_trigger = gr.Button("Public API", visible=False)
        health_payload = gr.JSON(label="Health Response", visible=False)
        metrics_payload = gr.JSON(label="Metrics Response", visible=False)
        health_trigger = gr.Button("Health", visible=False)
        metrics_trigger = gr.Button("Metrics", visible=False)
        metrics_token = gr.Textbox(label="Metrics Token", visible=False)

        outputs = [recommendation, decisions, sources, deployment, terraform, trace, research, raw_trace]
        run.click(
            fn=advise_detailed,
            inputs=[brief, elicitation_answers, conflict_resolution, deep_thinking],
            outputs=outputs,
            api_name="advise_detailed",
            api_visibility="private",
            concurrency_limit=_advisor_concurrency_limit(),
            concurrency_id="advisor",
        )
        clear.click(
            fn=clear_detail_response,
            inputs=None,
            outputs=[brief, *outputs],
            api_name="clear_detail_response",
            api_visibility="private",
        )
        public_api_trigger.click(
            fn=advise_api,
            inputs=[brief, elicitation_answers, conflict_resolution, deep_thinking],
            outputs=public_api_payload,
            api_name="advise",
            api_description="Return the public advisor response without raw graph internals.",
            api_visibility="public",
            concurrency_limit=_advisor_concurrency_limit(),
            concurrency_id="advisor",
        )
        health_trigger.click(
            fn=health_api,
            inputs=None,
            outputs=health_payload,
            api_name="health",
            api_description="Return non-secret runtime health and production-control status.",
            api_visibility="public",
        )
        metrics_trigger.click(
            fn=metrics_api,
            inputs=metrics_token,
            outputs=metrics_payload,
            api_name="metrics",
            api_description="Return token-protected latency/error counters without request text.",
            api_visibility="public",
        )
        demo.queue(max_size=_advisor_queue_max_size())
    return demo


def _prewarm_runtime() -> None:
    if not _env_bool("PREWARM_RETRIEVER", False):
        return
    try:
        from retrieval.service import get_retriever

        get_retriever().search("warmup retrieval query", top_k=1, namespace="knowledge")
    except Exception:
        # Prewarming is an optimization only; app startup should still proceed
        # and surface any real retrieval failures on the first request.
        return


demo = build_demo() if gr else None
_prewarm_runtime()


if __name__ == "__main__":
    if demo is None:
        sample = advise("Build an internal API docs assistant over fast-moving SDK docs.")
        print(sample[0])
        print(json.dumps(sample[1], indent=2))
    else:
        demo.launch(
            server_name=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
            server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
            share=os.getenv("GRADIO_SHARE", "false").lower() == "true",
            auth=_launch_auth_credentials(),
        )
