from __future__ import annotations

import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["LLM_PROVIDER"] = "disabled"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["ADVISOR_LATENCY_PROFILE"] = "quality"
os.environ["DEEP_RESEARCH_FULL_TEXT"] = "false"
os.environ["DEEP_THINKING_ENABLED"] = "true"
os.environ["PREWARM_RETRIEVER"] = "false"
os.environ["RETRIEVAL_MODE"] = "lexical"
os.environ["VECTOR_STORE_BACKEND"] = "memory"
os.environ["ADVISOR_USAGE_COUNTER_PATH"] = ""

from app import advise, advise_api, advise_detailed, clear_detail_response


def main() -> None:
    brief = "Build an internal API docs assistant over fast-moving SDK docs."
    summary, trace = advise(brief)
    if "## Recommendation" not in summary:
        raise AssertionError("legacy summary is missing recommendation heading")
    if not trace.get("draft_output", {}).get("sources"):
        raise AssertionError("legacy trace is missing sources")

    (
        recommendation,
        implementation_plan,
        design_plan,
        literature_curation,
        decisions,
        sources,
        deployment,
        terraform,
        decision_trace,
        research,
        raw,
    ) = advise_detailed(brief)
    if "Two-stage hybrid" not in recommendation:
        raise AssertionError("recommendation tab is missing selected topology")
    for heading in ("Confirm The Brief", "Build Retrieval Profiles", "Gate Production"):
        if heading not in implementation_plan:
            raise AssertionError(f"build plan is missing {heading}")
    for heading in (
        "Curated Literature Map",
        "Chunking And Parsing",
        "Embedding And Vector Operations",
        "Retrieval And Matching",
        "Evaluation And Gold Sets",
    ):
        if heading not in literature_curation:
            raise AssertionError(f"literature map is missing {heading}")
    if "raw file names" not in literature_curation:
        raise AssertionError("literature map should explain that raw file names are hidden")
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
        if heading not in design_plan:
            raise AssertionError(f"design plan is missing {heading}")
    for metric in ("Recall@k", "MRR", "nDCG", "p50/p95/p99"):
        if metric not in design_plan:
            raise AssertionError(f"design plan is missing evaluation metric {metric}")
    if "Retrieval Strategy" not in decisions:
        raise AssertionError("architecture tab is missing retrieval decision")
    if "Accepted Tradeoff" not in decisions or "Evidence Summaries" not in decisions:
        raise AssertionError("architecture tab is missing detailed reasoning")
    if not sources or len(sources[0]) != 5:
        raise AssertionError("source table rows are malformed")
    if not sources[0][-1]:
        raise AssertionError("source table should show reasoning chunks instead of file paths")
    if any("corpus_" in str(cell) for row in sources for cell in row):
        raise AssertionError("source table should not expose raw chunk IDs")
    if any(str(row[-1]).startswith(("Generated:", "```")) for row in sources):
        raise AssertionError("source table should prefer substantive reasoning chunks")
    if any(str(row[-1]).count("|") >= 4 or "|---" in str(row[-1]) for row in sources):
        raise AssertionError("source table should show cleaned summaries, not raw markdown tables")
    if "flowchart LR" not in deployment or "Deployment Projection" not in deployment or "Vector database" not in deployment:
        raise AssertionError("deployment tab is missing projection details")
    if "terraform" not in terraform:
        raise AssertionError("terraform tab is missing sketch")
    if "modules/database/main.tf" not in terraform:
        raise AssertionError("terraform sketch is missing module tree output")
    if "Advisor Reasoning Trace" not in decision_trace or "Read the literature chunks" not in decision_trace:
        raise AssertionError("trace tab is missing literature-grounded reasoning")
    if "Deep thinking is disabled" not in research:
        raise AssertionError("research tab should explain when deep thinking is disabled")
    visible_output = "\n".join(
        [recommendation, implementation_plan, design_plan, literature_curation, decisions, deployment, decision_trace]
    )
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
    if "Evaluation Sets" not in str(public.get("design_plan") or ""):
        raise AssertionError("public API response is missing the structured design plan")
    if "Gate Production" not in str(public.get("implementation_plan") or ""):
        raise AssertionError("public API response is missing the coherent build plan")
    if "Curated Literature Map" not in str(public.get("literature_curation") or ""):
        raise AssertionError("public API response is missing literature curation")

    deep_public = advise_api(brief, deep_thinking=True)
    if not deep_public.get("deep_thinking"):
        raise AssertionError("public API did not preserve deep-thinking mode")
    if not deep_public.get("research_links"):
        raise AssertionError("deep-thinking API response should include research links")
    if not any("github.com" in str(link.get("url")) for link in deep_public["research_links"]):
        raise AssertionError("deep-thinking research links should include community GitHub references")
    if not any("huggingface.co" in str(link.get("url")) for link in deep_public["research_links"]):
        raise AssertionError("deep-thinking research links should include Hugging Face references")

    deep_detailed = advise_detailed(brief, deep_thinking=True)
    if "Deep Research Agents" not in deep_detailed[9]:
        raise AssertionError("research tab should render deep-thinking agent findings")
    if "Ran deep research agents" not in deep_detailed[8]:
        raise AssertionError("trace tab should include the deep-thinking agent step")

    unresolved = advise_detailed("We need a RAG system, but the domain is unknown.")
    if "Questions To Confirm" not in unresolved[0]:
        raise AssertionError("detailed response should surface pending elicitation")

    resolved = advise_detailed(
        "A clinical HIPAA assistant over PHI patient records asks to use an external API.",
        conflict_resolution="preserve_compliance",
    )
    if "conflict:resolved:preserve_compliance" not in resolved[10].get("graph_trace", []):
        raise AssertionError("conflict resolution control was not passed into the graph")

    cleared = clear_detail_response()
    if cleared != ("", "", "", "", "", "", [], "", "", "", "", {}):
        raise AssertionError("clear response shape changed")

    print(f"sources={len(sources)} domain={raw['domain_prior']}")


if __name__ == "__main__":
    main()
