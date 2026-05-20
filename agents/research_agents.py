from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from html.parser import HTMLParser
import operator
import os
from pathlib import Path
import re
import time
from typing import Annotated, Callable, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agents.snippets import display_snippet
from graph.state import (
    AdvisorState,
    ResearchApproachSummary,
    ResearchFinding,
    ResearchLink,
    SourceRef,
)
from ingestion.build_index import build_index
from retrieval.index import HybridRetriever, SearchResult
from retrieval.service import retrieve

try:  # LangGraph is the preferred orchestrator; CI still has a no-surprises fallback.
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - fallback path covers missing optional installs.
    END = None
    START = None
    StateGraph = None


ResearchRetrieveFn = Callable[[str, str, int, dict[str, str] | None], list[SearchResult]]
FullTextFetchFn = Callable[[ResearchLink], "FullTextDocument"]


@dataclass(frozen=True)
class FullTextDocument:
    label: str
    url: str
    source_type: str
    text: str
    status: str = "ok"
    error: str = ""

    @property
    def word_count(self) -> int:
        return len(self.text.split())


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
    full_text_fetcher: FullTextFetchFn | None = None,
) -> dict[str, ResearchFinding]:
    retrieve_fn = retrieve_fn or _default_retrieve_fn()
    langgraph_findings = _run_with_langgraph(state, retrieve_fn, full_text_fetcher)
    if langgraph_findings is not None:
        return langgraph_findings
    return _run_with_thread_pool(state, retrieve_fn, full_text_fetcher)


def _default_retrieve_fn() -> ResearchRetrieveFn:
    mode = os.getenv("DEEP_RESEARCH_RETRIEVAL_MODE", "lexical").lower().strip()
    if mode in {"runtime", "default", "configured"}:
        return retrieve
    return _lexical_retrieve


def _lexical_retrieve(
    query: str,
    namespace: str,
    top_k: int,
    filters: dict[str, str] | None,
) -> list[SearchResult]:
    return _research_lexical_retriever().search(
        query,
        top_k=top_k,
        namespace=namespace,
        filters=filters,
    )


@lru_cache(maxsize=1)
def _research_lexical_retriever() -> HybridRetriever:
    return HybridRetriever(build_index().chunks)


def _run_with_langgraph(
    state: AdvisorState,
    retrieve_fn: ResearchRetrieveFn,
    full_text_fetcher: FullTextFetchFn | None,
) -> dict[str, ResearchFinding] | None:
    if StateGraph is None or START is None or END is None:
        return None
    try:
        graph = StateGraph(ResearchGraphState)
        for spec in RESEARCH_AGENT_SPECS:
            graph.add_node(spec.name, _langgraph_node(spec, full_text_fetcher))
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


def _langgraph_node(
    spec: ResearchAgentSpec,
    full_text_fetcher: FullTextFetchFn | None,
):
    def node(graph_state: ResearchGraphState) -> dict[str, dict[str, ResearchFinding]]:
        try:
            finding = _run_research_agent(
                spec,
                graph_state["advisor_state"],
                graph_state["retrieve_fn"],
                full_text_fetcher,
            )
        except Exception as exc:
            finding = _failed_finding(spec.name, exc)
        return {"findings": {spec.name: finding}}

    return node


def _run_with_thread_pool(
    state: AdvisorState,
    retrieve_fn: ResearchRetrieveFn,
    full_text_fetcher: FullTextFetchFn | None,
) -> dict[str, ResearchFinding]:
    findings: dict[str, ResearchFinding] = {}
    with ThreadPoolExecutor(max_workers=len(RESEARCH_AGENT_SPECS)) as executor:
        futures = {
            executor.submit(
                _run_research_agent,
                spec,
                state,
                retrieve_fn,
                full_text_fetcher,
            ): spec.name
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
        approach_summaries=[],
        sources=[],
        source_ids=[],
        duration_ms=0.0,
    )


def _run_research_agent(
    spec: ResearchAgentSpec,
    state: AdvisorState,
    retrieve_fn: ResearchRetrieveFn,
    full_text_fetcher: FullTextFetchFn | None,
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
    links = [*external_links, *selected_corpus_links]
    approach_summaries = _approach_summaries(
        spec,
        state,
        links,
        full_text_fetcher=full_text_fetcher,
    )
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    return ResearchFinding(
        agent=spec.name,
        summary=_summary(spec, sources, external_links, selected_corpus_links, approach_summaries),
        status="ok",
        subqueries=list(spec.subqueries),
        links=links,
        approach_summaries=approach_summaries,
        source_ids=[source.source_id for source in sources],
        sources=sources,
        duration_ms=duration_ms,
    )


def _source_ref(result: SearchResult) -> SourceRef:
    chunk = result.chunk
    section = " > ".join(chunk.metadata.get("section_path") or [])
    element_type = str(chunk.metadata.get("element_type") or "")
    return SourceRef(
        source_id=chunk.chunk_id,
        title=chunk.title,
        section=section,
        source_path=str(chunk.metadata.get("source_path") or chunk.source_path),
        score=round(result.score, 6),
        snippet=display_snippet(
            chunk.text_original,
            limit=220,
            section=section,
            element_type=element_type,
        ),
        element_type=element_type,
        url=chunk.metadata.get("source_url"),
    )


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
    approach_summaries: list[ResearchApproachSummary],
) -> str:
    link_types = sorted({link.source_type for link in [*external_links, *corpus_links]})
    read_count = sum(1 for item in approach_summaries if item.status == "ok")
    return (
        f"{spec.summary_template} Retrieved {len(sources)} local evidence chunks and "
        f"attached {len(external_links) + len(corpus_links)} public links"
        + (f" across {', '.join(link_types)}." if link_types else ".")
        + (
            f" Read and summarized {read_count} full public references."
            if approach_summaries
            else " Full-reference summarization was not enabled for this run."
        )
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


def _approach_summaries(
    spec: ResearchAgentSpec,
    state: AdvisorState,
    links: list[ResearchLink],
    *,
    full_text_fetcher: FullTextFetchFn | None,
) -> list[ResearchApproachSummary]:
    if not _env_bool("DEEP_RESEARCH_FULL_TEXT", True) and full_text_fetcher is None:
        return []

    selected = _summary_links(links, limit=_env_int("DEEP_RESEARCH_MAX_FULL_TEXT_LINKS", 4))
    if not selected:
        return []

    fetcher = full_text_fetcher or fetch_full_text
    summaries: list[ResearchApproachSummary] = []
    workers = min(len(selected), _env_int("DEEP_RESEARCH_FETCH_WORKERS", 4))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetcher, link): link for link in selected}
        for future in as_completed(futures):
            link = futures[future]
            try:
                document = future.result()
            except Exception as exc:
                document = FullTextDocument(
                    label=link.label,
                    url=link.url,
                    source_type=link.source_type,
                    text="",
                    status="failed",
                    error=str(exc),
                )
            summaries.append(_summarize_document(spec, state, link, document))

    order = {link.url: index for index, link in enumerate(selected)}
    return sorted(summaries, key=lambda item: order.get(item.url, 999))


def _summary_links(links: list[ResearchLink], *, limit: int) -> list[ResearchLink]:
    priority = {
        "paper": 0,
        "docs": 1,
        "github": 2,
        "medium": 3,
        "hugging-face": 4,
        "community": 5,
    }
    seen: set[str] = set()
    unique = []
    for link in sorted(links, key=lambda item: priority.get(item.source_type, 9)):
        if link.url in seen:
            continue
        seen.add(link.url)
        unique.append(link)
        if len(unique) >= limit:
            break
    return unique


def fetch_full_text(link: ResearchLink) -> FullTextDocument:
    cache_path = _full_text_cache_path(link.url)
    if cache_path.exists():
        return FullTextDocument(
            label=link.label,
            url=link.url,
            source_type=link.source_type,
            text=cache_path.read_text(encoding="utf-8"),
            status="ok",
        )

    url = _fetch_url(link.url)
    request = Request(url, headers={"User-Agent": "rag-architecture-advisor/1.0"})
    try:
        with urlopen(request, timeout=_env_float("DEEP_RESEARCH_FETCH_TIMEOUT_SECONDS", 6.0)) as response:
            content_type = response.headers.get("content-type", "")
            raw = response.read(_env_int("DEEP_RESEARCH_MAX_FETCH_BYTES", 2_000_000))
    except (HTTPError, URLError, TimeoutError) as exc:
        return FullTextDocument(
            label=link.label,
            url=link.url,
            source_type=link.source_type,
            text="",
            status="failed",
            error=str(exc),
        )

    text = _decode_response(raw, content_type)
    if "html" in content_type.lower() or "<html" in text[:500].lower():
        text = _html_to_text(text)
    text = _normalize_text(text)
    if text:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
    return FullTextDocument(
        label=link.label,
        url=link.url,
        source_type=link.source_type,
        text=text,
        status="ok" if text else "empty",
    )


def _fetch_url(url: str) -> str:
    if "github.com" not in url or "/blob/" not in url:
        return url
    return (
        url.replace("https://github.com/", "https://raw.githubusercontent.com/")
        .replace("/blob/", "/")
    )


def _full_text_cache_path(url: str) -> Path:
    digest = sha256(url.encode("utf-8")).hexdigest()
    return Path(os.getenv("DEEP_RESEARCH_CACHE_DIR", ".cache/deep_research")) / f"{digest}.txt"


def _decode_response(raw: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type, flags=re.IGNORECASE)
    if match:
        charset = match.group(1)
    return raw.decode(charset, errors="replace")


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs):
        if tag in {"script", "style", "svg", "noscript"}:
            self.skip_depth += 1
        if tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "pre", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag in {"script", "style", "svg", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "pre", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str):
        if self.skip_depth:
            return
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return "\n".join(parser.parts)


def _normalize_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        compact = " ".join(line.split())
        if compact:
            lines.append(compact)
    return "\n".join(lines)


def _summarize_document(
    spec: ResearchAgentSpec,
    state: AdvisorState,
    link: ResearchLink,
    document: FullTextDocument,
) -> ResearchApproachSummary:
    if document.status != "ok" or document.word_count < 80:
        return ResearchApproachSummary(
            label=link.label,
            url=link.url,
            source_type=link.source_type,
            status=document.status,
            word_count=document.word_count,
            summary=document.error or "Full text could not be read into a useful summary.",
        )

    sentences = _sentences(document.text)
    themes = _themes(document.text)
    approach_steps = _select_sentences(
        sentences,
        _agent_keywords(spec.name) | {"approach", "pipeline", "system", "workflow", "retrieval"},
        limit=5,
    )
    implementation_notes = _select_sentences(
        sentences,
        {"implement", "index", "rerank", "agent", "graph", "tool", "evaluation", "metadata", "vector"},
        limit=4,
    )
    limitations = _select_sentences(
        sentences,
        {"latency", "cost", "risk", "limit", "failure", "tradeoff", "benchmark", "quality"},
        limit=3,
        fallback=False,
    )
    summary = (
        f"Read {document.word_count} words from the full reference. "
        f"The approach emphasizes {', '.join(themes[:4]) or 'agentic retrieval design'} "
        f"and is relevant to this brief because it informs {spec.name.replace('_', ' ')} "
        "choices before synthesis."
    )
    return ResearchApproachSummary(
        label=link.label,
        url=link.url,
        source_type=link.source_type,
        status="ok",
        word_count=document.word_count,
        summary=summary,
        approach_steps=approach_steps,
        implementation_notes=implementation_notes,
        limitations=limitations,
    )


def _sentences(text: str) -> list[str]:
    compact = " ".join(text.split())
    raw_sentences = re.split(r"(?<=[.!?])\s+", compact)
    return [
        sentence.strip()
        for sentence in raw_sentences
        if 45 <= len(sentence.strip()) <= 360 and not _boilerplate_sentence(sentence)
    ]


def _select_sentences(
    sentences: list[str],
    keywords: set[str],
    *,
    limit: int,
    fallback: bool = True,
) -> list[str]:
    scored = []
    for index, sentence in enumerate(sentences):
        lowered = sentence.lower()
        score = sum(1 for keyword in keywords if keyword in lowered)
        if score:
            scored.append((score, -index, sentence))
    selected = [sentence for _, _, sentence in sorted(scored, reverse=True)[:limit]]
    if selected:
        return selected
    return sentences[:limit] if fallback else []


def _boilerplate_sentence(sentence: str) -> bool:
    lowered = sentence.lower()
    boilerplate_terms = (
        "skip to main content",
        "cookie",
        "sign in",
        "bibliographic tools",
        "toggle navigation",
        "search documentation",
        "privacy policy",
        "terms of service",
        "subscribe to",
    )
    return any(term in lowered for term in boilerplate_terms)


def _themes(text: str) -> list[str]:
    candidates = {
        "hybrid retrieval": ("hybrid", "bm25", "lexical"),
        "dense vector search": ("embedding", "vector", "dense"),
        "reranking": ("rerank", "cross-encoder", "colbert"),
        "agent orchestration": ("agent", "tool", "graph", "workflow"),
        "evaluation": ("evaluation", "benchmark", "metric", "quality"),
        "latency control": ("latency", "throughput", "timeout"),
        "governance": ("permission", "audit", "security", "guardrail"),
    }
    lowered = text.lower()
    scored = [
        (sum(lowered.count(term) for term in terms), label)
        for label, terms in candidates.items()
    ]
    return [label for score, label in sorted(scored, reverse=True) if score > 0]


def _agent_keywords(agent: str) -> set[str]:
    return {
        "literature_review": {"survey", "benchmark", "retrieval", "generation", "evaluation"},
        "agent_frameworks": {"agent", "pipeline", "graph", "tool", "workflow"},
        "community_implementations": {"github", "implementation", "hybrid", "rerank", "observability"},
        "huggingface_spaces": {"space", "gradio", "hugging face", "smolagents", "agent"},
    }.get(agent, {"retrieval", "generation", "agent"})


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.lower().strip() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return float(value)
