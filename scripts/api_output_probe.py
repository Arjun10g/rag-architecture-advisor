from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience.
    load_dotenv = None

if load_dotenv:
    load_dotenv()

DEFAULT_BRIEF = (
    "Build an internal API docs assistant over fast-moving SDK docs with strict "
    "citations, mixed markdown and code, and high exact-match terminology needs."
)

FORBIDDEN_PUBLIC_TOKENS = (
    "corpus_",
    "corpus/",
    "router:start",
    "Graph Trace",
    "Requirement Vector",
    "graph_trace",
    "raw_trace",
    "two_stage_",
    "retrieval_strategy",
)

A_CODE_RE = re.compile(r"\bA(?:1[0-2]|[1-9])\s*(?::|=)")
EVIDENCE_RE = re.compile(r"^E\d+$")
RAW_SOURCE_ID_RE = re.compile(r"corpus_[\w_]+:\d+:[a-f0-9]{8,}")
FORBIDDEN_PUBLIC_KEYS = {
    "source_id",
    "source_ids",
    "source_path",
    "chunk_id",
    "graph_trace",
    "raw_trace",
    "draft_output",
    "decision_log",
    "requirement_vector",
}


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return _json_text(value)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        matches = [f"{path}.{key}" for key in value if key in FORBIDDEN_PUBLIC_KEYS]
        for key, item in value.items():
            matches.extend(_find_forbidden_keys(item, f"{path}.{key}"))
        return matches
    if isinstance(value, list):
        matches: list[str] = []
        for index, item in enumerate(value):
            matches.extend(_find_forbidden_keys(item, f"{path}[{index}]"))
        return matches
    return []


def _first_env(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()
    return None


def _client_auth(args: argparse.Namespace) -> tuple[str, str] | None:
    explicit = args.auth_username is not None or args.auth_password is not None
    public_mode = os.getenv("PUBLIC_ACCESS_MODE", "").strip().lower()
    if not explicit and public_mode in {"anonymous", "gateway"}:
        return None
    username = (args.auth_username if args.auth_username is not None else os.getenv("GRADIO_AUTH_USERNAME", "")).strip()
    password = (args.auth_password if args.auth_password is not None else os.getenv("GRADIO_AUTH_PASSWORD", "")).strip()
    if bool(username) != bool(password):
        raise AssertionError("Provide both Gradio auth username and password, or neither.")
    return (username, password) if username and password else None


def _predict(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from gradio_client import Client
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "gradio_client is required. Install requirements.txt before running this probe."
        ) from exc

    client = Client(
        args.url,
        token=args.hf_token or _first_env("HF_TOKEN", "HF_ACCESS_TOKEN"),
        auth=_client_auth(args),
    )
    result = client.predict(
        user_brief=args.brief,
        elicitation_answers=args.elicitation_answers,
        conflict_resolution=args.conflict_resolution,
        deep_thinking=args.deep_thinking,
        api_name=args.endpoint,
    )
    _require(isinstance(result, dict), "public API should return one JSON object")
    return result


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _latency_summary(values: list[float]) -> dict[str, float]:
    return {
        "p50": round(_percentile(values, 0.50), 2),
        "p95": round(_percentile(values, 0.95), 2),
        "p99": round(_percentile(values, 0.99), 2),
        "max": round(max(values) if values else 0.0, 2),
    }


def _optional_env_float(key: str) -> float | None:
    value = os.getenv(key)
    if value is None or not value.strip():
        return None
    return float(value)


def _latency_slo(args: argparse.Namespace) -> tuple[float | None, float | None]:
    if not args.slo_from_env:
        return args.slo_p50_ms, args.slo_p99_ms
    prefix = "DEEP_" if args.deep_thinking else ""
    return (
        _optional_env_float(f"{prefix}LATENCY_SLO_P50_MS"),
        _optional_env_float(f"{prefix}LATENCY_SLO_P99_MS"),
    )


def _enforce_latency_slo(
    summary: dict[str, float],
    *,
    p50_ms: float | None,
    p99_ms: float | None,
) -> dict[str, Any]:
    status = {
        "p50_ms": p50_ms,
        "p99_ms": p99_ms,
        "ok": True,
    }
    failures = []
    if p50_ms is not None and summary["p50"] > p50_ms:
        failures.append(f"p50 {summary['p50']}ms exceeded {p50_ms}ms")
    if p99_ms is not None and summary["p99"] > p99_ms:
        failures.append(f"p99 {summary['p99']}ms exceeded {p99_ms}ms")
    if failures:
        status["ok"] = False
        status["failures"] = failures
        raise AssertionError("latency SLO failed: " + "; ".join(failures))
    return status


def _validate_chunks(chunks: Any) -> list[dict[str, Any]]:
    _require(isinstance(chunks, list) and chunks, "reasoning_chunks should be a non-empty list")
    normalized: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        _require(isinstance(chunk, dict), f"reasoning chunk {index} is not an object")
        evidence = str(chunk.get("evidence") or "")
        reasoning_chunk = str(chunk.get("reasoning_chunk") or "")
        _require(EVIDENCE_RE.match(evidence) is not None, f"reasoning chunk {index} has bad evidence label")
        _require(len(reasoning_chunk) >= 70, f"reasoning chunk {index} is too thin")
        _require(
            not reasoning_chunk.startswith(("Generated:", "```")),
            f"reasoning chunk {index} is not a substantive literature chunk",
        )
        _require(
            not (reasoning_chunk.count("|") >= 4 or "|---" in reasoning_chunk),
            f"reasoning chunk {index} leaked raw markdown table text",
        )
        normalized.append(chunk)
    return normalized


def _validate_deep_research_payload(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload.get("deep_thinking") is True, "deep-thinking flag was not preserved")
    research = str(payload.get("research") or "")
    findings = payload.get("research_findings")
    links = payload.get("research_links")
    approach_summaries = payload.get("research_approach_summaries") or []
    _require("Deep Research Agents" in research, "research tab output is missing agent summaries")
    _require(isinstance(findings, list) and findings, "deep-thinking findings should be non-empty")
    _require(isinstance(links, list) and links, "deep-thinking links should be non-empty")

    agents = {str(finding.get("agent") or "") for finding in findings if isinstance(finding, dict)}
    expected_agents = {
        "literature_review",
        "agent_frameworks",
        "community_implementations",
        "huggingface_spaces",
    }
    missing_agents = sorted(expected_agents - agents)
    _require(not missing_agents, f"deep-thinking missed agents: {', '.join(missing_agents)}")

    urls = [str(link.get("url") or "") for link in links if isinstance(link, dict)]
    source_types = {str(link.get("source_type") or "") for link in links if isinstance(link, dict)}
    for host in ("arxiv.org", "github.com", "huggingface.co", "medium.com"):
        _require(any(host in url for url in urls), f"deep-thinking links missed {host}")
    _require({"paper", "github", "hugging-face"}.issubset(source_types), "deep-thinking link types are too thin")
    if payload.get("_require_full_text"):
        _require(
            isinstance(approach_summaries, list) and approach_summaries,
            "deep-thinking full-text approach summaries should be non-empty",
        )
        read_items = [item for item in approach_summaries if item.get("status") == "ok"]
        _require(read_items, "deep-thinking full-text summaries should include at least one successfully read reference")
    return {
        "research_agents": len(agents),
        "research_links": len(urls),
        "research_approach_summaries": len(approach_summaries),
        "research_source_types": sorted(source_types),
    }


def _validate_public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public_text = _as_text(payload)
    leaked_tokens = [token for token in FORBIDDEN_PUBLIC_TOKENS if token in public_text]
    _require(not leaked_tokens, f"public API leaked internal tokens: {', '.join(leaked_tokens)}")
    leaked_keys = _find_forbidden_keys(payload)
    _require(not leaked_keys, f"public API leaked internal keys: {', '.join(leaked_keys[:8])}")
    _require(RAW_SOURCE_ID_RE.search(public_text) is None, "public API leaked raw corpus source IDs")
    _require(A_CODE_RE.search(public_text) is None, "public API leaked raw requirement attribute codes")

    recommendation = str(payload.get("recommendation") or "")
    design_plan = str(payload.get("design_plan") or "")
    decisions = str(payload.get("architecture_decisions") or "")
    trace = str(payload.get("advisor_reasoning_trace") or "")
    deployment = str(payload.get("deployment_projection") or "")
    terraform = str(payload.get("terraform_sketch") or "")
    generation = payload.get("generation") or {}
    chunks = _validate_chunks(payload.get("reasoning_chunks"))

    _require("Two-stage hybrid" in recommendation, "recommendation is missing the selected topology")
    _require("Agentic Reasoning Trace" in recommendation, "recommendation is missing agentic reasoning")
    for heading in (
        "Embedding Model",
        "Embedding Dimension",
        "Chunking Strategy",
        "Pooling Strategy",
        "Vector Database",
        "Retrieval Methods",
        "Re-Ranking Strategy",
        "Context For Generation",
        "Evaluation Sets",
    ):
        _require(heading in design_plan, f"design plan is missing {heading}")
    for metric in ("Recall@k", "MRR", "nDCG", "p50/p95/p99"):
        _require(metric in design_plan, f"design plan is missing evaluation metric {metric}")
    _require("Retrieval Strategy" in decisions, "architecture decisions are missing retrieval reasoning")
    _require("Accepted Tradeoff" in decisions, "architecture decisions are missing tradeoffs")
    _require("Evidence Summaries" in decisions, "architecture decisions are missing evidence summaries")
    _require("Advisor Reasoning Trace" in trace, "trace is missing the public reasoning heading")
    _require("Read the literature chunks" in trace, "trace does not describe literature-grounding")
    _require("Deployment Projection" in deployment, "deployment projection is missing")
    _require("modules/database/main.tf" in terraform, "Terraform sketch is missing database module output")
    _require(isinstance(generation, dict), "generation status should be an object")

    deep_summary = (
        _validate_deep_research_payload(payload)
        if payload.get("deep_thinking")
        else {"research_agents": 0, "research_links": 0, "research_source_types": []}
    )
    return {
        "topology": payload.get("topology"),
        "generation_status": generation.get("status"),
        "generation_model": generation.get("model"),
        "reasoning_chunks": len(chunks),
        "evidence_labels": [chunk.get("evidence") for chunk in chunks[:5]],
        **deep_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Call the public Gradio API and fail if user-facing output leaks internals."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8022")
    parser.add_argument("--endpoint", default="/advise")
    parser.add_argument("--brief", default=DEFAULT_BRIEF)
    parser.add_argument("--elicitation-answers", default="")
    parser.add_argument("--conflict-resolution", default="")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--show-preview", action="store_true")
    parser.add_argument("--deep-thinking", action="store_true")
    parser.add_argument("--require-full-text", action="store_true")
    parser.add_argument("--hf-token", default=None, help="HF token for private Spaces; defaults to HF_TOKEN/HF_ACCESS_TOKEN.")
    parser.add_argument("--auth-username", default=None, help="Gradio auth username; defaults to GRADIO_AUTH_USERNAME.")
    parser.add_argument("--auth-password", default=None, help="Gradio auth password; defaults to GRADIO_AUTH_PASSWORD.")
    parser.add_argument("--slo-p50-ms", type=float, default=None)
    parser.add_argument("--slo-p99-ms", type=float, default=None)
    parser.add_argument(
        "--slo-from-env",
        action="store_true",
        help="Read standard or deep-thinking latency SLOs from the environment.",
    )
    args = parser.parse_args()
    _require(args.runs >= 1, "--runs must be at least 1")

    payload: dict[str, Any] | None = None
    latencies = []
    for _ in range(args.runs):
        started = time.perf_counter()
        payload = _predict(args)
        latencies.append((time.perf_counter() - started) * 1000)
        validation_payload = dict(payload)
        if args.require_full_text:
            validation_payload["_require_full_text"] = True
        _validate_public_payload(validation_payload)
    assert payload is not None
    latency = _latency_summary(latencies)
    slo_p50, slo_p99 = _latency_slo(args)
    slo_status = _enforce_latency_slo(latency, p50_ms=slo_p50, p99_ms=slo_p99)
    summary = {
        "url": args.url,
        "endpoint": args.endpoint,
        **_validate_public_payload(
            dict(payload) | {"_require_full_text": True}
            if args.require_full_text
            else payload
        ),
        "client_latency_ms": latency,
        "latency_slo": slo_status,
    }
    if args.show_preview:
        summary["recommendation_preview"] = str(payload.get("recommendation") or "")[:800]
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"API output probe failed: {exc}", file=sys.stderr)
        raise
