from __future__ import annotations

import json
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["DEEP_RESEARCH_FULL_TEXT"] = "true"
os.environ["DEEP_RESEARCH_MAX_FULL_TEXT_LINKS"] = "2"

from agents.research_agents import FullTextDocument, run_research_agents
from graph.state import AdvisorState, ResearchLink


def _retrieve_empty(query: str, namespace: str, top_k: int, filters: dict[str, str] | None):
    return []


def _fake_fetch(link: ResearchLink) -> FullTextDocument:
    text = (
        "This article describes an agentic RAG approach that uses a graph workflow "
        "to route questions, retrieve evidence, evaluate retrieved passages, and "
        "rerank candidates before generation. The implementation creates a hybrid "
        "retrieval pipeline with lexical BM25 matching, dense vector search, metadata "
        "filters, and a reranker that improves precision before context packing. "
        "The system adds evaluation gates for recall, citation coverage, answer "
        "quality, latency, and failure handling so regressions are visible before "
        "deployment. The main limitation is cost and latency because full agentic "
        "reasoning, reranking, and benchmark evaluation require more compute than "
        "a simple dense retrieval demo. The tradeoff is accepted when the application "
        "needs auditability, exact terminology support, and trustworthy citations."
    )
    return FullTextDocument(
        label=link.label,
        url=link.url,
        source_type=link.source_type,
        text=text,
        status="ok",
    )


def main() -> None:
    state = AdvisorState(
        user_brief=(
            "Build an internal API docs assistant with strict citations, hybrid retrieval, "
            "reranking, and evaluation gates."
        ),
        deep_thinking=True,
    )
    findings = run_research_agents(
        state,
        retrieve_fn=_retrieve_empty,
        full_text_fetcher=_fake_fetch,
    )
    if not findings:
        raise AssertionError("full-text research did not return findings")

    summaries = [
        summary
        for finding in findings.values()
        for summary in finding.approach_summaries
    ]
    if not summaries:
        raise AssertionError("full-text research did not produce approach summaries")
    if not all(summary.word_count >= 80 for summary in summaries):
        raise AssertionError("approach summaries should record full-document word counts")
    if not any(summary.approach_steps for summary in summaries):
        raise AssertionError("approach summaries should include approach steps")
    if not any(summary.implementation_notes for summary in summaries):
        raise AssertionError("approach summaries should include implementation notes")
    if not any(summary.limitations for summary in summaries):
        raise AssertionError("approach summaries should include limitations")

    print(
        json.dumps(
            {
                "status": "ok",
                "agents": sorted(findings),
                "approach_summaries": len(summaries),
                "first_word_count": summaries[0].word_count,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
