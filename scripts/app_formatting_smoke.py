from __future__ import annotations

import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["LLM_PROVIDER"] = "disabled"

from app import advise, advise_api, advise_detailed, clear_detail_response


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
    if "Accepted Tradeoff" not in decisions or "Reasoning Chunks" not in decisions:
        raise AssertionError("architecture tab is missing detailed reasoning")
    if not sources or len(sources[0]) != 5:
        raise AssertionError("source table rows are malformed")
    if not sources[0][-1]:
        raise AssertionError("source table should show reasoning chunks instead of file paths")
    if any("corpus_" in str(cell) for row in sources for cell in row):
        raise AssertionError("source table should not expose raw chunk IDs")
    if any(str(row[-1]).startswith(("Generated:", "```")) for row in sources):
        raise AssertionError("source table should prefer substantive reasoning chunks")
    if "flowchart LR" not in deployment or "Deployment Projection" not in deployment or "Vector database" not in deployment:
        raise AssertionError("deployment tab is missing projection details")
    if "terraform" not in terraform:
        raise AssertionError("terraform tab is missing sketch")
    if "modules/database/main.tf" not in terraform:
        raise AssertionError("terraform sketch is missing module tree output")
    if "Advisor Reasoning Trace" not in decision_trace or "Read the literature chunks" not in decision_trace:
        raise AssertionError("trace tab is missing literature-grounded reasoning")
    visible_output = "\n".join([recommendation, decisions, deployment, decision_trace])
    forbidden = ["corpus_", "router:start", "Graph Trace", "Requirement Vector", "two_stage_hybrid_rerank", "retrieval_strategy"]
    if any(token in visible_output for token in forbidden):
        raise AssertionError("visible output should not expose raw source IDs, graph markers, or internal keys")
    if "Agentic Reasoning Trace" not in recommendation:
        raise AssertionError("recommendation should include an agentic reasoning trace")
    if not raw.get("draft_output", {}).get("architecture_decisions"):
        raise AssertionError("raw trace is missing architecture decisions")
    panel = raw.get("draft_output", {}).get("panel", {})
    if not panel.get("items") or not panel.get("tradeoffs"):
        raise AssertionError("panel is missing requirement-specific reasoning")
    if raw.get("draft_output", {}).get("generation", {}).get("status") != "fallback":
        raise AssertionError("deterministic smoke should use LLM fallback path")

    public = advise_api(brief)
    public_text = str(public)
    if "raw_trace" in public or "graph_trace" in public or "draft_output" in public:
        raise AssertionError("public API response should not expose raw graph internals")
    if any(token in public_text for token in ("corpus_", "source_path", "router:start")):
        raise AssertionError("public API response should not expose raw source IDs or graph markers")
    if not public.get("reasoning_chunks") or not public.get("advisor_reasoning_trace"):
        raise AssertionError("public API response is missing advisor reasoning fields")

    unresolved = advise_detailed("We need a RAG system, but the domain is unknown.")
    if "Questions To Confirm" not in unresolved[0]:
        raise AssertionError("detailed response should surface pending elicitation")

    resolved = advise_detailed(
        "A clinical HIPAA assistant over PHI patient records asks to use an external API.",
        conflict_resolution="preserve_compliance",
    )
    if "conflict:resolved:preserve_compliance" not in resolved[6].get("graph_trace", []):
        raise AssertionError("conflict resolution control was not passed into the graph")

    cleared = clear_detail_response()
    if cleared != ("", "", [], "", "", "", "", {}):
        raise AssertionError("clear response shape changed")

    print(f"sources={len(sources)} domain={raw['domain_prior']}")


if __name__ == "__main__":
    main()
