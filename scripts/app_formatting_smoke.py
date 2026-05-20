from __future__ import annotations

import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["LLM_PROVIDER"] = "disabled"

from app import advise, advise_detailed, clear_detail_response


def main() -> None:
    brief = "Build an internal API docs assistant over fast-moving SDK docs."
    summary, trace = advise(brief)
    if "## Recommendation" not in summary:
        raise AssertionError("legacy summary is missing recommendation heading")
    if not trace.get("draft_output", {}).get("sources"):
        raise AssertionError("legacy trace is missing sources")

    recommendation, decisions, sources, deployment, terraform, decision_trace, raw = advise_detailed(brief)
    if "Two-stage hybrid" not in recommendation:
        raise AssertionError("recommendation tab is missing selected topology")
    if "Retrieval Strategy" not in decisions:
        raise AssertionError("architecture tab is missing retrieval decision")
    if not sources or len(sources[0]) != 6:
        raise AssertionError("source table rows are malformed")
    if "Deployment Projection" not in deployment or "Vector database" not in deployment:
        raise AssertionError("deployment tab is missing projection details")
    if "terraform" not in terraform:
        raise AssertionError("terraform tab is missing sketch")
    if "modules/database/main.tf" not in terraform:
        raise AssertionError("terraform sketch is missing module tree output")
    if "Decision Trace" not in decision_trace:
        raise AssertionError("trace tab is missing heading")
    if not raw.get("draft_output", {}).get("architecture_decisions"):
        raise AssertionError("raw trace is missing architecture decisions")
    if raw.get("draft_output", {}).get("generation", {}).get("status") != "fallback":
        raise AssertionError("deterministic smoke should use LLM fallback path")

    cleared = clear_detail_response()
    if cleared != ("", "", [], "", "", "", "", {}):
        raise AssertionError("clear response shape changed")

    print(f"sources={len(sources)} domain={raw['domain_prior']}")


if __name__ == "__main__":
    main()
