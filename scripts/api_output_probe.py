from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

try:
    from gradio_client import Client
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "gradio_client is required. Install requirements.txt before running this probe."
    ) from exc


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


def _predict(args: argparse.Namespace) -> dict[str, Any]:
    client = Client(args.url)
    result = client.predict(
        user_brief=args.brief,
        elicitation_answers=args.elicitation_answers,
        conflict_resolution=args.conflict_resolution,
        api_name=args.endpoint,
    )
    _require(isinstance(result, dict), "public API should return one JSON object")
    return result


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
        normalized.append(chunk)
    return normalized


def _validate_public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public_text = _as_text(payload)
    leaked_tokens = [token for token in FORBIDDEN_PUBLIC_TOKENS if token in public_text]
    _require(not leaked_tokens, f"public API leaked internal tokens: {', '.join(leaked_tokens)}")
    leaked_keys = _find_forbidden_keys(payload)
    _require(not leaked_keys, f"public API leaked internal keys: {', '.join(leaked_keys[:8])}")
    _require(RAW_SOURCE_ID_RE.search(public_text) is None, "public API leaked raw corpus source IDs")
    _require(A_CODE_RE.search(public_text) is None, "public API leaked raw requirement attribute codes")

    recommendation = str(payload.get("recommendation") or "")
    decisions = str(payload.get("architecture_decisions") or "")
    trace = str(payload.get("advisor_reasoning_trace") or "")
    deployment = str(payload.get("deployment_projection") or "")
    terraform = str(payload.get("terraform_sketch") or "")
    generation = payload.get("generation") or {}
    chunks = _validate_chunks(payload.get("reasoning_chunks"))

    _require("Two-stage hybrid" in recommendation, "recommendation is missing the selected topology")
    _require("Agentic Reasoning Trace" in recommendation, "recommendation is missing agentic reasoning")
    _require("Retrieval Strategy" in decisions, "architecture decisions are missing retrieval reasoning")
    _require("Accepted Tradeoff" in decisions, "architecture decisions are missing tradeoffs")
    _require("Reasoning Chunks" in decisions, "architecture decisions are missing evidence chunks")
    _require("Advisor Reasoning Trace" in trace, "trace is missing the public reasoning heading")
    _require("Read the literature chunks" in trace, "trace does not describe literature-grounding")
    _require("Deployment Projection" in deployment, "deployment projection is missing")
    _require("modules/database/main.tf" in terraform, "Terraform sketch is missing database module output")
    _require(isinstance(generation, dict), "generation status should be an object")

    return {
        "topology": payload.get("topology"),
        "generation_status": generation.get("status"),
        "generation_model": generation.get("model"),
        "reasoning_chunks": len(chunks),
        "evidence_labels": [chunk.get("evidence") for chunk in chunks[:5]],
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
    parser.add_argument("--show-preview", action="store_true")
    args = parser.parse_args()

    payload = _predict(args)
    summary = {
        "url": args.url,
        "endpoint": args.endpoint,
        **_validate_public_payload(payload),
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
