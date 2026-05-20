from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import operator
import re
import time
from typing import Annotated, Callable, TypedDict

from graph.state import AdvisorState, ResearchFinding, ResearchLink, SourceRef
from retrieval.index import SearchResult
from retrieval.service import retrieve

try:  # LangGraph is the preferred orchestrator; CI still has a no-surprises fallback.
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - fallback path covers missing optional installs.
    END = None
    START = None
    StateGraph = None


ResearchRetrieveFn = Callable[[str, str, int, dict[str, str] | None], list[SearchResult]]


@dataclass(frozen=True)
class ResearchAgentSpec:
    name: str
    summary_template: str
    subqueries: tuple[str, ...]
    links: tuple[ResearchLink, ...]


class ResearchGraphState(TypedDict):
    advisor_state: AdvisorState
    retrieve_fn: ResearchRetrieveFn
    findings: Annotated[dict[str, ResearchFinding], operator.or_]


RESEARCH_AGENT_SPECS = (
    ResearchAgentSpec(
        name="literature_review",
        summary_template=(
            "Reviews the internal literature corpus for peer-reviewed and provider-backed "
            "patterns before the synthesizer turns the recommendation into user-facing reasoning."
        ),
        subqueries=(
            "agentic RAG literature hybrid retrieval reranking evaluation citation grounded generation",
            "RAG surveys self-RAG corrective RAG adaptive RAG retrieval evaluation latency citations",
            "context grounding compression lost in the middle citation abstention trustworthy RAG",
        ),
        links=(
            ResearchLink(
                label="Hybrid retrieval and reranking framework for evidence-grounded RAG",
                url="https://arxiv.org/abs/2605.01664",
                source_type="paper",
                relevance="Recent paper supporting hybrid retrieval plus reranking as a precision/recall pattern.",
            ),
            ResearchLink(
                label="RAGPerf benchmark",
                url="https://arxiv.org/abs/2603.10765",
                source_type="paper",
                relevance="Benchmark framing for embedding, indexing, retrieval, reranking, and generation latency.",
            ),
            ResearchLink(
                label="RoutIR retrieval pipeline serving",
                url="https://arxiv.org/abs/2601.10644",
                source_type="paper",
                relevance="Recent work on configurable retrieval pipelines with fusion and reranking stages.",
            ),
        ),
    ),
    ResearchAgentSpec(
        name="agent_frameworks",
        summary_template=(
            "Checks current agent orchestration libraries so deep mode can reason about task "
            "decomposition using established graph, pipeline, and multi-agent patterns."
        ),
        subqueries=(
            "LangGraph agentic RAG graph state nodes conditional edges retrieval tool",
            "Pydantic AI multi-agent patterns structured output retries graph execution",
            "Haystack AsyncPipeline parallel retrievers loops agentic pipelines",
            "CrewAI flows crews multi-agent orchestration production workflow",
        ),
        links=(
            ResearchLink(
                label="Haystack Pipelines and AsyncPipeline",
                url="https://docs.haystack.deepset.ai/docs/pipelines",
                source_type="docs",
                relevance="Documents branching, loops, and parallel execution for independent pipeline components.",
            ),
            ResearchLink(
                label="Pydantic AI agents",
                url="https://pydantic.dev/docs/ai/core-concepts/agent/",
                source_type="docs",
                relevance="Current typed-agent API with reusable agents, tools, graph iteration, and output validation.",
            ),
            ResearchLink(
                label="CrewAI introduction",
                url="https://docs.crewai.com/en/introduction",
                source_type="docs",
                relevance="Frames Crews and Flows as production-oriented multi-agent orchestration patterns.",
            ),
            ResearchLink(
                label="LangGraph agentic RAG guide",
                url="https://docs.langchain.com/oss/javascript/langgraph/agentic-rag",
                source_type="docs",
                relevance="Official agentic RAG example using graph state, retrieval tools, and conditional flow.",
            ),
        ),
    ),
    ResearchAgentSpec(
        name="community_implementations",
        summary_template=(
            "Surfaces practical GitHub and Medium implementation patterns so the recommendation can "
            "compare the literature against what builders are shipping."
        ),
        subqueries=(
            "GitHub LangGraph agentic RAG hybrid search reranking Qdrant implementation",
            "Medium self-evaluating RAG agent hybrid search LangGraph reranking observability",
            "community implementations hybrid RAG BM25 RRF reranker LangGraph GitHub",
        ),
        links=(
            ResearchLink(
                label="LangGraph agentic RAG notebook",
                url="https://github.com/langchain-ai/langgraph/blob/main/examples/rag/langgraph_agentic_rag.ipynb",
                source_type="github",
                relevance="Community-visible implementation notebook for an agentic RAG graph.",
            ),
            ResearchLink(
                label="Hybrid RAG GitHub topic",
                url="https://github.com/topics/hybrid-rag",
                source_type="github",
                relevance="Live community index of hybrid RAG repos using BM25, RRF, rerankers, and vector DBs.",
            ),
            ResearchLink(
                label="Self-evaluating RAG agent with hybrid search",
                url="https://medium.com/@sharmaranupama/beyond-the-demo-building-a-rag-system-from-scratch-that-routes-retrieves-and-evaluates-itself-4bb1dc66e524",
                source_type="medium",
                relevance="Recent practical article combining hybrid retrieval, routing, observability, and evaluation.",
            ),
            ResearchLink(
                label="retrievalagent package",
                url="https://pypi.org/project/retrievalagent/0.11.0/",
                source_type="community",
                relevance="Recent package describing LangGraph-based hybrid retrieval, reranking, retry, and quality gates.",
            ),
        ),
    ),
    ResearchAgentSpec(
        name="huggingface_spaces",
        summary_template=(
            "Looks at Hugging Face agent and Spaces-facing references so the deployed app can stay "
            "compatible with the platform it runs on."
        ),
        subqueries=(
            "Hugging Face smolagents managed agents multi agent systems agentic RAG",
            "Hugging Face Spaces Gradio agentic RAG examples smolagents tools",
            "Hugging Face inference providers Spaces Gradio agent deployment",
        ),
        links=(
            ResearchLink(
                label="smolagents agent reference",
                url="https://huggingface.co/docs/smolagents/en/reference/agents",
                source_type="hugging-face",
                relevance="Reference for MultiStepAgent managed_agents, planning intervals, and final answer checks.",
            ),
            ResearchLink(
                label="smolagents documentation",
                url="https://huggingface.co/docs/smolagents/v1.14.0/en/index",
                source_type="hugging-face",
                relevance="Hugging Face documentation with agentic RAG and multi-agent tutorials.",
            ),
            ResearchLink(
                label="smolagents GitHub repository",
                url="https://github.com/huggingface/smolagents",
                source_type="github",
                relevance="Open-source implementation of HF agents that think in code and can use managed agents.",
            ),
        ),
    ),
)


URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def run_research_agents(
    state: AdvisorState,
    retrieve_fn: ResearchRetrieveFn | None = None,
) -> dict[str, ResearchFinding]:
    retrieve_fn = retrieve_fn or retrieve
    langgraph_findings = _run_with_langgraph(state, retrieve_fn)
    if langgraph_findings is not None:
        return langgraph_findings
    return _run_with_thread_pool(state, retrieve_fn)


def _run_with_langgraph(
    state: AdvisorState,
    retrieve_fn: ResearchRetrieveFn,
) -> dict[str, ResearchFinding] | None:
    if StateGraph is None or START is None or END is None:
        return None
    try:
        graph = StateGraph(ResearchGraphState)
        for spec in RESEARCH_AGENT_SPECS:
            graph.add_node(spec.name, _langgraph_node(spec))
            graph.add_edge(START, spec.name)
            graph.add_edge(spec.name, END)
        result = graph.compile().invoke(
            {"advisor_state": state, "retrieve_fn": retrieve_fn, "findings": {}}
        )
    except Exception:
        return None

    findings = result.get("findings") or {}
    expected = {spec.name for spec in RESEARCH_AGENT_SPECS}
    if not expected.issubset(findings):
        return None
    return {spec.name: findings[spec.name] for spec in RESEARCH_AGENT_SPECS}


def _langgraph_node(spec: ResearchAgentSpec):
    def node(graph_state: ResearchGraphState) -> dict[str, dict[str, ResearchFinding]]:
        try:
            finding = _run_research_agent(
                spec,
                graph_state["advisor_state"],
                graph_state["retrieve_fn"],
            )
        except Exception as exc:
            finding = _failed_finding(spec.name, exc)
        return {"findings": {spec.name: finding}}

    return node


def _run_with_thread_pool(
    state: AdvisorState,
    retrieve_fn: ResearchRetrieveFn,
) -> dict[str, ResearchFinding]:
    findings: dict[str, ResearchFinding] = {}
    with ThreadPoolExecutor(max_workers=len(RESEARCH_AGENT_SPECS)) as executor:
        futures = {
            executor.submit(_run_research_agent, spec, state, retrieve_fn): spec.name
            for spec in RESEARCH_AGENT_SPECS
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                findings[name] = future.result()
            except Exception as exc:
                findings[name] = _failed_finding(name, exc)
    return {spec.name: findings[spec.name] for spec in RESEARCH_AGENT_SPECS}


def _failed_finding(name: str, exc: Exception) -> ResearchFinding:
    return ResearchFinding(
        agent=name,
        summary=(
            "Deep research agent failed gracefully and returned an explicit gap. "
            f"Reason: {exc}"
        ),
        status="failed",
        subqueries=[],
        links=[],
        sources=[],
        source_ids=[],
        duration_ms=0.0,
    )


def _run_research_agent(
    spec: ResearchAgentSpec,
    state: AdvisorState,
    retrieve_fn: ResearchRetrieveFn,
) -> ResearchFinding:
    started = time.perf_counter()
    sources: list[SourceRef] = []
    seen_sources: set[str] = set()
    corpus_links: list[ResearchLink] = []
    seen_links: set[str] = set()

    for subquery in spec.subqueries:
        query = f"{state.user_brief} {subquery}"
        for result in retrieve_fn(query, "knowledge", 6, None):
            source = _source_ref(result)
            if source.source_id not in seen_sources:
                sources.append(source)
                seen_sources.add(source.source_id)
            for link in _links_from_result(spec.name, result):
                if link.url not in seen_links:
                    corpus_links.append(link)
                    seen_links.add(link.url)

    external_links = [
        ResearchLink(
            label=link.label,
            url=link.url,
            source_type=link.source_type,
            relevance=link.relevance,
            agent=spec.name,
        )
        for link in spec.links
    ]
    for link in external_links:
        seen_links.add(link.url)

    selected_corpus_links = [
        link for link in corpus_links if link.url not in {item.url for item in external_links}
    ][:6]
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    return ResearchFinding(
        agent=spec.name,
        summary=_summary(spec, sources, external_links, selected_corpus_links),
        status="ok",
        subqueries=list(spec.subqueries),
        links=[*external_links, *selected_corpus_links],
        source_ids=[source.source_id for source in sources],
        sources=sources,
        duration_ms=duration_ms,
    )


def _source_ref(result: SearchResult) -> SourceRef:
    chunk = result.chunk
    section = " > ".join(chunk.metadata.get("section_path") or [])
    return SourceRef(
        source_id=chunk.chunk_id,
        title=chunk.title,
        section=section,
        source_path=str(chunk.metadata.get("source_path") or chunk.source_path),
        score=round(result.score, 6),
        snippet=_snippet(chunk.text_original),
        element_type=str(chunk.metadata.get("element_type") or ""),
        url=chunk.metadata.get("source_url"),
    )


def _snippet(text: str, limit: int = 220) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def _links_from_result(agent: str, result: SearchResult) -> list[ResearchLink]:
    text = result.chunk.text_original
    links: list[ResearchLink] = []
    seen: set[str] = set()
    for label, url in MARKDOWN_LINK_RE.findall(text):
        clean_url = _clean_url(url)
        if clean_url not in seen:
            seen.add(clean_url)
            links.append(
                ResearchLink(
                    label=_clean_label(label),
                    url=clean_url,
                    source_type=_source_type(clean_url),
                    relevance="Extracted from the retrieved literature corpus.",
                    agent=agent,
                )
            )
    for url in URL_RE.findall(text):
        clean_url = _clean_url(url)
        if clean_url not in seen:
            seen.add(clean_url)
            links.append(
                ResearchLink(
                    label=_label_from_url(clean_url),
                    url=clean_url,
                    source_type=_source_type(clean_url),
                    relevance="Extracted from the retrieved literature corpus.",
                    agent=agent,
                )
            )
    return links


def _summary(
    spec: ResearchAgentSpec,
    sources: list[SourceRef],
    external_links: list[ResearchLink],
    corpus_links: list[ResearchLink],
) -> str:
    link_types = sorted({link.source_type for link in [*external_links, *corpus_links]})
    return (
        f"{spec.summary_template} Retrieved {len(sources)} local evidence chunks and "
        f"attached {len(external_links) + len(corpus_links)} public links"
        + (f" across {', '.join(link_types)}." if link_types else ".")
    )


def _clean_url(url: str) -> str:
    return url.strip().rstrip(".,;")


def _clean_label(label: str) -> str:
    return " ".join(label.split())[:120] or "Source"


def _label_from_url(url: str) -> str:
    host = url.split("//", 1)[-1].split("/", 1)[0]
    tail = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
    return _clean_label(f"{host}: {tail}")


def _source_type(url: str) -> str:
    lowered = url.lower()
    if "arxiv.org" in lowered or "openreview.net" in lowered:
        return "paper"
    if "github.com" in lowered:
        return "github"
    if "huggingface.co" in lowered:
        return "hugging-face"
    if "medium.com" in lowered:
        return "medium"
    if "docs." in lowered or "learn.microsoft.com" in lowered:
        return "docs"
    return "web"
