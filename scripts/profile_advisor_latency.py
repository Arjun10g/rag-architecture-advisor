from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from agents.critic import critique
from agents.research_agents import run_research_agents
from agents.specialists import FOCUS_QUERIES, run_specialists
from agents.synthesizer import synthesize
from graph.edges import SPECIALIST_NAMES
from graph.nodes import conflict_node, elicitation_node, router_node
from graph.state import AdvisorState
from retrieval.service import get_retriever, retrieve
from scripts.api_output_probe import DEFAULT_BRIEF


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile advisor latency by graph stage.")
    parser.add_argument("--brief", default=DEFAULT_BRIEF)
    parser.add_argument("--deep-thinking", action="store_true")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--provider", choices=["env", "disabled", "hf"], default="env")
    parser.add_argument("--warmup-retriever", action="store_true")
    parser.add_argument(
        "--legacy-specialist-timing",
        action="store_true",
        help="Disable batched specialists so each retrieval call can be timed separately.",
    )
    args = parser.parse_args()

    if load_dotenv:
        load_dotenv()
    if args.provider != "env":
        os.environ["LLM_PROVIDER"] = args.provider

    if args.warmup_retriever:
        get_retriever().search("warmup retrieval", top_k=1, namespace="knowledge")

    runs = [
        _profile_once(
            args.brief,
            deep_thinking=args.deep_thinking,
            legacy_specialist_timing=args.legacy_specialist_timing,
        )
        for _ in range(args.runs)
    ]
    print(json.dumps(_summarize(runs), indent=2, sort_keys=True))


def _profile_once(
    brief: str,
    *,
    deep_thinking: bool,
    legacy_specialist_timing: bool,
) -> dict[str, Any]:
    timings: dict[str, float] = {}
    started = time.perf_counter()
    state = AdvisorState.from_input({"user_brief": brief, "deep_thinking": deep_thinking})

    state = _time_stage(timings, "router", lambda: router_node(state))
    state = _time_stage(timings, "elicitation", lambda: elicitation_node(state))
    state = _time_stage(timings, "conflict", lambda: conflict_node(state))

    retrieval_timings: list[dict[str, Any]] = []
    timed_retrieve = _timed_retrieve(retrieval_timings)
    retrieve_fn = timed_retrieve if legacy_specialist_timing else None
    state.agent_findings = _time_stage(
        timings,
        "specialists",
        lambda: run_specialists(state, retrieve_fn=retrieve_fn),
    )
    timings["specialist_retrieval_sum_ms"] = round(
        sum(item["latency_ms"] for item in retrieval_timings), 2
    )
    timings["specialist_retrieval_max_ms"] = round(
        max((item["latency_ms"] for item in retrieval_timings), default=0.0), 2
    )

    if deep_thinking:
        state.research_findings = _time_stage(
            timings,
            "research_agents",
            lambda: run_research_agents(state),
        )
    else:
        timings["research_agents"] = 0.0

    state.draft_output = _time_stage(timings, "synthesizer", lambda: synthesize(state))
    state.critique = _time_stage(timings, "critic", lambda: critique(state))
    timings["total_ms"] = round((time.perf_counter() - started) * 1000, 2)

    generation = (state.draft_output or {}).get("generation") or {}
    return {
        "timings_ms": timings,
        "retrieval_calls": retrieval_timings,
        "batched_specialists": not legacy_specialist_timing,
        "retrieval_mode": os.getenv("RETRIEVAL_MODE", "lexical"),
        "vector_backend": os.getenv("VECTOR_STORE_BACKEND", "memory"),
        "embedding_dim": os.getenv("EMBEDDING_DIM"),
        "generation": {
            "status": generation.get("status"),
            "provider": generation.get("provider"),
            "model": generation.get("model"),
        },
    }


def _time_stage(timings: dict[str, float], name: str, fn: Any) -> Any:
    started = time.perf_counter()
    result = fn()
    timings[name] = round((time.perf_counter() - started) * 1000, 2)
    return result


def _timed_retrieve(records: list[dict[str, Any]]) -> Any:
    def wrapper(
        query: str,
        namespace: str = "knowledge",
        top_k: int = 8,
        filters: dict[str, str] | None = None,
    ) -> Any:
        started = time.perf_counter()
        results = retrieve(query, namespace=namespace, top_k=top_k, filters=filters)
        records.append(
            {
                "query_focus": _focus_name(query),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "results": len(results),
            }
        )
        return results

    return wrapper


def _focus_name(query: str) -> str:
    for name, focus_query in FOCUS_QUERIES.items():
        if focus_query in query:
            return name
    return "unknown"


def _summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if len(runs) == 1:
        return runs[0]
    timing_keys = sorted(runs[0]["timings_ms"])
    return {
        "runs": len(runs),
        "profiles": runs,
        "summary_ms": {
            key: {
                "p50": round(statistics.median(run["timings_ms"][key] for run in runs), 2),
                "max": round(max(run["timings_ms"][key] for run in runs), 2),
            }
            for key in timing_keys
        },
    }


if __name__ == "__main__":
    main()
