# 04 — Reranking Model Cards and Selection Guide

## 1. What reranking does

A reranker reads a query and a candidate document/chunk and produces a more precise relevance judgment than the first-stage retriever. Reranking is usually the highest-ROI upgrade after adding hybrid retrieval.

Typical pipeline:

```text
retrieve top 50–200 → rerank → keep top 5–20 for context
```

## 2. Reranker families

| Family | Input | Output | Strength | Weakness | Best use |
|---|---|---|---|---|---|
| Cross-encoder | query + one document | relevance score | strong precision, easy to deploy | pairwise scoring cost | default reranking |
| LLM-style pairwise reranker | query + one document | yes/no or score logit | stronger reasoning | heavier inference | high-value multilingual/long-context cases |
| Listwise reranker | query + list of docs | ordered list | models cross-document tradeoffs | harder to calibrate, context-limited | small candidate sets |
| LLM-as-reranker | prompt with candidate docs | ranking/rationales | flexible, instruction-following | slow, expensive, non-deterministic | premium or offline reranking |
| Learned-to-rank model | features + candidates | ranking score | fast at scale | feature engineering/labels needed | high-QPS product search |

## 3. Reranker scoring caveat

Do not treat raw reranker scores as universal probabilities. Scores are usually meaningful **within the candidate set for one query**, not across all queries.

Practical implications:

- thresholding on a fixed raw score is brittle;
- calibrate if thresholding matters;
- evaluate rank metrics rather than just score distributions;
- listwise and LLM rerankers are especially candidate-set dependent.

## 4. BGE rerankers

### BAAI/bge-reranker-v2-m3

| Field | Notes |
|---|---|
| Type | cross-encoder reranker |
| Base | BGE-M3 / XLM-R style family |
| Languages | multilingual |
| License | Apache-2.0 on the Hugging Face model card |
| Typical max length | example usage uses 512 tokens for normal reranker |
| Deployment | Hugging Face Transformers, Sentence Transformers, FlagEmbedding, TEI-compatible paths |
| Strength | strong open multilingual reranking baseline |
| Cost profile | self-hosting infra cost; GPU recommended for throughput |

### Operational notes

BGE rerankers output relevance scores. The model card notes that scores can be mapped with a sigmoid, but that mapping should be treated as a convenience transform rather than a calibrated probability.

### Use BGE when

- you want open weights;
- you need multilingual support;
- you want local/private deployment;
- you can host GPUs or accept CPU latency;
- you want a standard baseline for RAG evaluation.

### Avoid BGE when

- you need a fully managed SLA-backed API only;
- you need long-document reranking without chunking;
- you need listwise cross-document reasoning;
- you cannot support model hosting.

Reference: https://huggingface.co/BAAI/bge-reranker-v2-m3

## 5. Mixedbread mxbai-rerank

### mxbai-rerank-v2 family

| Field | Notes |
|---|---|
| Type | cross-encoder reranker |
| Sizes | base-v2 around 0.5B; large-v2 around 1.5B according to vendor blog |
| Languages | 100+ languages according to vendor blog |
| Context | up to 8k tokens, 32k-compatible according to vendor blog |
| License | Apache-2.0 according to vendor blog |
| Strength | multilingual, code/tool retrieval, long-context reranking |
| Deployment | open model weights and API/store integrations depending on product path |

### Use Mixedbread when

- multilingual quality matters;
- long candidate passages matter;
- code/tool/API retrieval is in scope;
- you want open-source licensing and/or managed API options;
- latency budget allows a larger reranker for top candidates.

### Avoid or validate carefully when

- strict cost constraints dominate;
- your candidate chunks are always short and simple;
- a smaller cross-encoder already saturates quality;
- vendor benchmarks do not reflect your domain.

Reference: https://www.mixedbread.com/blog/mxbai-rerank-v2

## 6. Cohere Rerank

### Cohere Rerank API

| Field | Notes |
|---|---|
| Type | managed API reranker |
| Current example model in docs | `rerank-v4.0-pro` appears in API example |
| Input | query + list of documents |
| Output | ordered results with relevance scores |
| Recommended request size | docs recommend against sending more than 1,000 documents in one request |
| Long-document behavior | docs note long documents are truncated to `max_tokens_per_doc`; default shown as 4096 |
| Structured data | docs recommend YAML strings for structured data |
| Strength | managed, strong enterprise ergonomics |

### Use Cohere when

- you want a managed API;
- you do not want to host GPUs;
- documents include semi-structured text;
- enterprise support/rate limits matter;
- predictable integration is more important than full model control.

### Avoid or validate carefully when

- data cannot leave your environment;
- per-query API cost is too high;
- you need full control over weights or fine-tuning;
- latency has to be extremely low and local.

Reference: https://docs.cohere.com/reference/rerank

## 7. Jina rerankers

### jina-reranker-v2-base-multilingual

| Field | Notes |
|---|---|
| Type | cross-encoder reranker |
| Parameters | 278M according to Jina model page |
| Input length | 1K / 1024-token context according to Jina model page |
| Supported languages | 108 supported languages according to Jina model page |
| License | CC-BY-NC-4.0 according to model page |
| Strength | multilingual, function calling, code search, efficient compact model |
| Deployment | Jina API, cloud marketplaces, Hugging Face, framework integrations |

### jina-reranker-v3

| Field | Notes |
|---|---|
| Type | listwise reranker / last-but-not-late interaction style |
| Parameters | about 0.6B in paper abstract |
| Strength | cross-document/listwise ranking in one context window |
| Best fit | small candidate sets where relative ordering among candidates matters |

### Use Jina when

- multilingual retrieval is central;
- code/API/function-calling search matters;
- you want a compact cross-encoder option;
- listwise reranking is attractive for small top-k pools.

### Avoid or validate carefully when

- non-commercial license constraints conflict with your deployment;
- candidate passages exceed context window and chunking could distort meaning;
- you need score thresholds that generalize across query sets.

References:

- https://jina.ai/models/jina-reranker-v2-base-multilingual/
- https://jina.ai/models/jina-reranker-v3/
- https://arxiv.org/abs/2509.25085

## 8. LLM-as-reranker

LLM reranking uses a generative model to rank candidates through prompting. Patterns include:

- pointwise scoring: score each document independently;
- pairwise comparison: compare document A vs B;
- listwise ranking: rank a whole candidate list;
- setwise/batched ranking: rank subsets and merge;
- rationale-based reranking: ask for evidence/rationale plus ranking.

### Prompt skeleton

```text
You are ranking search results for a user query.
Query: {query}

Rank the following passages by how directly they answer the query.
Prefer exact evidence over general topical similarity.
Return only passage IDs in ranked order.

Passages:
[1] ...
[2] ...
[3] ...
```

### Strengths

- flexible;
- can apply instructions;
- can account for nuanced relevance;
- can handle small listwise judgments;
- useful for offline evaluation and high-value queries.

### Weaknesses

- expensive;
- slow;
- prompt-sensitive;
- non-deterministic;
- can be position-biased;
- can over-rely on lexical similarity or verbosity;
- hard to calibrate.

### Use LLM reranking when

- candidate set is small, e.g. top 5–20;
- the query is high-value;
- relevance depends on instruction following or nuanced reasoning;
- offline evaluation or dataset creation is the task;
- latency/cost are acceptable.

### Avoid LLM reranking when

- every query needs sub-second latency;
- candidate set is large;
- cost per query must be tiny;
- deterministic ranking is mandatory;
- a cross-encoder already solves the problem.

## 9. Candidate sizing by reranker type

| Reranker | Practical candidate count |
|---|---:|
| small cross-encoder | 30–200 |
| large cross-encoder | 20–100 |
| managed API reranker | 20–500 depending on cost/latency |
| listwise reranker | 5–50 depending on context |
| LLM pairwise | 5–20 unless using tournament/batching |
| LLM listwise | 5–30 depending on context |

## 10. Reranker evaluation

Evaluate with:

- nDCG@5/10;
- MRR@10;
- Recall@k before and after reranking;
- answer correctness after generation;
- citation precision;
- latency per candidate and per query;
- cost per 1,000 queries;
- calibration curves if thresholding;
- failure analysis by query type.

### Recommended ablations

| Ablation | Purpose |
|---|---|
| no reranker | quantify reranker lift |
| small vs large reranker | quality/latency curve |
| top-20 vs top-50 vs top-100 | find candidate saturation |
| cross-encoder vs LLM reranker | see if LLM premium is justified |
| rerank raw chunks vs parent docs | test chunk granularity |
| rerank original query vs transformed query | avoid query drift |

## 11. Selection guide

| Situation | Reranker choice |
|---|---|
| default open-source baseline | BGE reranker v2-m3 |
| stronger multilingual/long context | Mixedbread large-v2 or Cohere/Jina API depending constraints |
| compact multilingual/code/API docs | Jina v2 |
| managed enterprise API | Cohere Rerank |
| small premium candidate sets | listwise reranker or LLM-as-reranker |
| privacy / on-prem | self-host BGE, Mixedbread, Jina-compatible open model subject to license |
| tight latency | smaller cross-encoder, quantization, batching, lower top-k |

## 12. Deployment notes

### Batch reranking

Batch candidate pairs across queries where possible:

```text
batch = [(q1,d1), (q1,d2), ..., (qN,dM)]
```

### Quantization

For self-hosting, evaluate:

- FP16/BF16;
- INT8 quantization;
- ONNX/TensorRT/OpenVINO;
- batch size vs latency;
- max sequence length truncation;
- GPU utilization.

### Caching

Cache reranker outputs by:

```text
hash(query_normalized, doc_id, doc_version, reranker_model_version)
```

Invalidate when:

- query rewrite logic changes;
- document changes;
- reranker model changes;
- chunking changes;
- metadata filters change.

## 13. References

- BGE reranker model card — https://huggingface.co/BAAI/bge-reranker-v2-m3
- Mixedbread rerank v2 — https://www.mixedbread.com/blog/mxbai-rerank-v2
- Cohere Rerank API — https://docs.cohere.com/reference/rerank
- Jina reranker v2 — https://jina.ai/models/jina-reranker-v2-base-multilingual/
- Jina reranker v3 paper — https://arxiv.org/abs/2509.25085
- RankGPT / LLM reranking — https://arxiv.org/abs/2306.17563
- RankLLM package — https://arxiv.org/abs/2505.19284
- RankZephyr — https://arxiv.org/abs/2312.02724
