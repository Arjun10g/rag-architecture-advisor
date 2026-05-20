from __future__ import annotations

import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["LLM_PROVIDER"] = "disabled"

from graph.build import build_graph


def main() -> None:
    graph = build_graph()

    unknown = graph.invoke(
        {"user_brief": "A museum archive wants retrieval over curator notes and scanned letters."}
    )
    if not any(item.startswith("elicitation:pending") for item in unknown.graph_trace):
        raise AssertionError("unknown-domain path did not route through elicitation")
    if not unknown.draft_output:
        raise AssertionError("graph should still synthesize with best-available pending state")

    unresolved = graph.invoke(
        {
            "user_brief": (
                "A clinical HIPAA assistant over PHI patient records asks to use an external API."
            )
        }
    )
    if "conflict:unresolved" not in unresolved.graph_trace:
        raise AssertionError("unresolved conflict was not traced")
    if unresolved.conflict is None:
        raise AssertionError("unresolved conflict should remain visible in final state")

    resolved = graph.invoke(
        {
            "user_brief": (
                "A clinical HIPAA assistant over PHI patient records asks to use an external API."
            ),
            "conflict_resolution": "preserve_compliance",
        }
    )
    if "conflict:resolved:preserve_compliance" not in resolved.graph_trace:
        raise AssertionError("resolved conflict was not traced")
    if resolved.conflict is not None:
        raise AssertionError("resolved conflict should be cleared")

    deep = graph.invoke(
        {
            "user_brief": "Build an internal API docs assistant over fast-moving SDK docs.",
            "deep_thinking": True,
        }
    )
    if "research:start" not in deep.graph_trace or "research:complete" not in deep.graph_trace:
        raise AssertionError("deep-thinking path did not run research agents")
    if not deep.research_findings:
        raise AssertionError("deep-thinking path did not retain research findings")
    if not (deep.draft_output or {}).get("research_links"):
        raise AssertionError("deep-thinking path did not expose research links")

    print(
        "graph_flow_smoke=ok "
        f"unknown_trace={len(unknown.graph_trace)} "
        f"resolved_trace={len(resolved.graph_trace)} "
        f"deep_agents={len(deep.research_findings)}"
    )


if __name__ == "__main__":
    main()
