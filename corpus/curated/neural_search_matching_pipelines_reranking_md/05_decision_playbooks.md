# 05 — Decision Playbooks: When to Use Which Retrieval Strategy

## 1. The shortest useful answer

Use this default unless evaluation proves otherwise:

```text
BM25 + dense retrieval → RRF → cross-encoder reranker → context packing
```

Then specialize:

- Use **SPLADE** for lexical-semantic corpora.
- Use **ColBERT** when first-stage quality is the bottleneck.
- Use **query transforms** for vague, multi-hop, or metadata-heavy queries.
- Use **adaptive routing** for mixed workloads.
- Use **GraphRAG/KG** for global and relational questions.
- Use **LLM reranking** only when the candidate set is small and query value is high.

## 2. Corpus-driven decisions

| Corpus type | Retrieval stack | Why |
|---|---|---|
| HR/policy docs | BM25+dense+rerank | exact clauses plus semantic phrasing |
| legal contracts | BM25/SPLADE+dense+strict metadata+rerank | exact wording and versioning matter |
| product catalog | BM25/SPLADE+dense+filters | SKUs and attributes matter |
| code/API docs | BM25/SPLADE+dense+code-aware rerank | symbols and semantics both matter |
| academic PDFs | dense+BM25+rerank; add layout/table retrieval | citation and terminology mix |
| customer support tickets | dense+metadata filters+rerank | semantic similarity plus product/version filters |
| enterprise wiki | BM25+dense+RRF+rerank | mixed document styles |
| meeting transcripts | dense+speaker/time filters+summaries | semantic recall and temporal context |
| relationship-heavy intelligence | KG/GraphRAG+text retrieval | entity links and provenance |
| large narrative corpus | GraphRAG global summaries + local text evidence | global questions exceed chunk retrieval |

## 3. Query-driven decisions

| Query type | Example | Recommended path |
|---|---|---|
| exact lookup | “SOC2 report 2024” | BM25/metadata first |
| semantic lookup | “How do we handle stale embeddings?” | dense+BM25 hybrid |
| vague query | “freshness strategy” | HyDE or multi-query + hybrid |
| comparison | “Compare Qdrant and pgvector for tenancy” | decomposition + hybrid + rerank |
| multi-hop | “Which projects used X after Y changed?” | decomposition + metadata + graph if available |
| global theme | “What are the main risks across these docs?” | GraphRAG/global summaries |
| entity relation | “How is team A connected to system B?” | KG subgraph + text evidence |
| schema constrained | “papers after 2022 about SPLADE” | self-query filters + retrieval |
| report writing | “Write a detailed report on…” | iterative retrieval or FLARE-like retrieval |
| low stakes | “define RRF” | small retrieval or no retrieval if known |

## 4. Latency-driven decisions

| Latency budget | Pipeline |
|---|---|
| <200ms | lexical/dense only; small top-k; no LLM query transform |
| 200–800ms | hybrid retrieval + lightweight reranker on small top-k |
| 800ms–3s | hybrid + query transform + cross-encoder rerank |
| 3–10s | decomposition or multi-query + rerank |
| 10s+ | agentic/iterative retrieval, GraphRAG, LLM reranking |
| offline/batch | large ablations, listwise LLM reranking, graph construction |

## 5. Cost-driven decisions

| Cost pressure | Recommendation |
|---|---|
| very high | BM25+dense, RRF, no rerank or tiny reranker |
| moderate | cross-encoder rerank top 30–50 |
| low | multi-query/decomposition plus larger reranker |
| high-value per query | LLM rerank, graph retrieval, iterative retrieval |
| unpredictable traffic | adaptive routing and caching |

## 6. Accuracy-driven decisions

| Failure observed | Likely fix |
|---|---|
| misses exact terms | add BM25/SPLADE; increase sparse weight |
| returns semantically related but wrong docs | add reranker; add metadata constraints |
| misses paraphrases | improve embedding model; add HyDE/multi-query |
| poor multi-hop answers | decomposition + rerank against original query |
| answers lack global perspective | GraphRAG/community summaries |
| context has duplicates | dedupe/source grouping/diversification |
| citations do not support answer | citation verifier or evidence-aware reranker |
| bad retrieval causes hallucination | CRAG-style retrieval evaluator/fallback |
| unnecessary retrieval on simple tasks | Adaptive-RAG/no-retrieval routing |

## 7. Managed vs self-hosted decision

| Need | Prefer managed | Prefer self-hosted |
|---|---|---|
| fastest implementation | yes | no |
| data residency/control | maybe | yes |
| custom model/fine-tune | limited | yes |
| predictable ops | yes | maybe |
| lowest unit cost at scale | maybe | often yes if optimized |
| enterprise support | yes | depends |
| experimentation | managed first | self-host after validation |

## 8. The “build-up” maturity ladder

### Level 0: naive RAG

```text
dense top-k → generator
```

Good for demos, weak for production.

### Level 1: hybrid retrieval

```text
BM25 + dense → RRF → generator
```

Strong first production baseline.

### Level 2: reranked hybrid

```text
BM25 + dense → RRF → cross-encoder rerank → generator
```

Best default for serious RAG.

### Level 3: query-aware retrieval

```text
query classifier → transform/decompose/self-query → hybrid → rerank → generator
```

Good for varied query types.

### Level 4: adaptive retrieval

```text
complexity router → no/single/iterative/graph retrieval → rerank → generator
```

Good for production cost-quality balance.

### Level 5: agentic/graph-enhanced retrieval

```text
planner → tools/indexes/graph/search → evaluator → answer with provenance
```

Good for high-value complex tasks, reports, and global sensemaking.

## 9. “Do not overbuild” checklist

Do not add query transforms if:

- baseline recall is already high;
- latency is tight;
- generated queries drift;
- the corpus is small;
- there is no evaluation set.

Do not add GraphRAG if:

- most questions are local lookup questions;
- entity extraction is poor;
- graph maintenance is unsupported;
- users do not ask global/relationship questions.

Do not use LLM reranking for all queries if:

- cross-encoder reranking is sufficient;
- top-k is large;
- cost per query matters;
- determinism matters.

Do not tune alpha/weights blindly if:

- you have no labels;
- score normalization is unstable;
- query types are mixed and need routing rather than one global alpha.

## 10. Recommended research questions for an applied paper

A publishable applied study could ask:

1. When does RRF outperform convex fusion, and when does alpha tuning win?
2. Does SPLADE+dense beat BM25+dense in domain-specific RAG?
3. Which query transform improves downstream answer quality, not just retrieval metrics?
4. When does decomposition improve multi-hop answer faithfulness?
5. Does GraphRAG improve global questions enough to justify indexing cost?
6. At what candidate size does reranking saturate?
7. Are LLM rerankers worth their latency/cost over modern cross-encoders?
8. Can an adaptive router reduce cost without reducing answer quality?

## 11. Suggested factorial design

| Factor | Levels |
|---|---|
| first-stage retrieval | dense, BM25, BM25+dense, SPLADE+dense, ColBERT |
| fusion | none, RRF, convex alpha tuned |
| query transform | none, HyDE, multi-query, decomposition, step-back, self-query |
| reranker | none, BGE, Mixedbread/Jina/Cohere, LLM reranker |
| context packing | top-n, dedupe, source-diverse, parent-child |
| routing | static, query-class adaptive |

Dependent variables:

- Recall@50;
- nDCG@10;
- answer accuracy;
- citation support;
- latency;
- cost;
- failure class.

## 12. Final rule of thumb

Retrieval quality improves most reliably in this order:

1. fix chunking and metadata;
2. add BM25+dense hybrid retrieval;
3. add reranking;
4. tune top-k and context packing;
5. add query transforms for known query classes;
6. add adaptive routing;
7. add graph/agentic retrieval for genuinely global or relational tasks;
8. add LLM reranking only when the marginal gain justifies cost.
