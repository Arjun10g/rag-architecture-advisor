from __future__ import annotations

import json
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["LLM_PROVIDER"] = "disabled"

from app import advise_api, advise_detailed
from graph.build import build_graph
from scripts.api_output_probe import (
    DEFAULT_BRIEF,
    _validate_deep_research_payload,
    _validate_public_payload,
)


EXPECTED_AGENTS = {
    "literature_review",
    "agent_frameworks",
    "community_implementations",
    "huggingface_spaces",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _urls(links: list[dict]) -> list[str]:
    return [str(link.get("url") or "") for link in links]


def main() -> None:
    graph = build_graph()
    state = graph.invoke({"user_brief": DEFAULT_BRIEF, "deep_thinking": True})
    _require("research:start" in state.graph_trace, "deep run did not start research node")
    _require("research:complete" in state.graph_trace, "deep run did not complete research node")
    _require(EXPECTED_AGENTS.issubset(state.research_findings), "deep run missed research agents")

    draft = state.draft_output or {}
    links = draft.get("research_links") or []
    _require(links, "deep run did not attach research links")
    urls = _urls(links)
    for host in ("arxiv.org", "github.com", "huggingface.co", "medium.com"):
        _require(any(host in url for url in urls), f"deep run missed {host} link")

    public = advise_api(DEFAULT_BRIEF, deep_thinking=True)
    public_summary = _validate_public_payload(public)
    deep_summary = _validate_deep_research_payload(public)

    detailed = advise_detailed(DEFAULT_BRIEF, deep_thinking=True)
    _require("Deep Research Agents" in detailed[6], "research tab did not render agent findings")
    _require("Ran deep research agents" in detailed[5], "trace tab did not explain research agents")

    print(
        json.dumps(
            {
                "status": "ok",
                "agents": sorted(EXPECTED_AGENTS),
                "links": deep_summary["research_links"],
                "source_types": deep_summary["research_source_types"],
                "topology": public_summary["topology"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
