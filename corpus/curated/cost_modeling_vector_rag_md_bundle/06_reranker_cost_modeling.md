# Reranker Cost Modeling

## Why reranking deserves its own model

Reranking is often introduced as a relevance-improvement step after vector retrieval. It can substantially improve answer quality, but it can also become one of the largest costs in the retrieval stack.

A common RAG pipeline is:

```text
query → query embedding → vector/hybrid retrieval top_k=100 → rerank top_k=100 → keep top_n=5–20 → generate answer
```

The expensive part is that a reranker often evaluates the query against every candidate passage.

## Reranker types

| Type | Cost shape | Strengths | Risks |
|---|---|---|---|
| Cross-encoder reranker | query × candidate pairs | strong relevance quality | latency and cost scale with candidate count |
| LLM reranker | tokens across query + candidates | flexible, instruction-following | very expensive for long candidates |
| Lightweight bi-encoder second pass | extra vector operations | cheaper | usually weaker than cross-encoder |
| Sparse/late-interaction reranker | term/token interaction | strong lexical/semantic mix | infra/model complexity |
| Hosted rerank API | per request or per token | easy to integrate | opaque margins, request or token cost |
| Self-hosted reranker | GPU capacity | can be cheap at scale | high ops/latency/batching complexity |

## Per-request pricing model

Some rerankers are priced per request:

```text
C_rerank = monthly_rerank_requests × price_per_1000_requests / 1000
```

Example:

```text
monthly_rerank_requests = 1,000,000
price = $2 / 1,000 requests
C = 1,000,000 × 2 / 1000 = $2,000/month
```

This can dwarf query embedding. At $0.08/M tokens and 32 query tokens:

```text
1M query embeddings = 1,000,000 × 32 × 0.08 / 1,000,000 = $2.56
```

So in this example:

```text
reranking cost / query_embedding cost = 2,000 / 2.56 ≈ 781×
```

## Token-priced reranker model

For token-priced rerankers:

```text
tokens_per_rerank = query_tokens + top_k_reranked × avg_candidate_tokens
C_rerank = monthly_queries × tokens_per_rerank × price_per_million_tokens / 1,000,000
```

### Example

Assume:

```text
monthly_queries = 1,000,000
query_tokens = 32
top_k_reranked = 50
avg_candidate_tokens = 256
price = $1 / 1M processed tokens
```

Then:

```text
tokens_per_rerank = 32 + 50 × 256 = 12,832 tokens
monthly_tokens = 12.832B tokens
cost = $12,832/month
```

The candidate fanout is the dominant term.

## Fanout sensitivity

The marginal cost of increasing rerank top-k by one candidate is:

```text
ΔC / Δk = monthly_queries × avg_candidate_tokens × price_per_token
```

At 1M queries/month, 256 candidate tokens, and $1/M tokens:

```text
ΔC / Δk = 1,000,000 × 256 × 1 / 1,000,000 = $256/month per extra candidate
```

Increasing rerank fanout from 50 to 100 adds:

```text
50 × $256 = $12,800/month
```

## Latency model

Reranking latency can be modeled as:

```text
latency = queueing_delay + model_forward_time(top_k, candidate_tokens, batch_size) + serialization_overhead
```

For per-candidate cross-encoders, approximate work scales as:

```text
work ∝ top_k × sequence_length × model_size
```

For LLM reranking, work may scale with prompt length and output length:

```text
work ∝ input_tokens + output_tokens
```

## Self-hosted reranker model

```text
C_self_rerank = ceil(required_rerank_QPS / sustainable_rerank_QPS_per_gpu) × gpu_hourly × monthly_hours
```

Where:

```text
required_rerank_QPS = query_QPS × fraction_queries_reranked
```

But sustainable rerank QPS is strongly affected by:

- model size;
- max sequence length;
- top-k fanout;
- batching strategy;
- latency SLO;
- GPU memory;
- quantization;
- CPU tokenization overhead.

## When reranking saves money

Reranking can be cost-positive if it reduces downstream generation or error costs.

### Context reduction savings

If reranking lets you send fewer chunks to the generator:

```text
savings = monthly_queries × (chunks_without_rerank - chunks_with_rerank) × avg_chunk_tokens × LLM_input_price_per_token
```

Reranking is cost-justified when:

```text
rerank_cost < context_token_savings + retry_savings + support_escalation_savings + quality_value
```

### Example

Assume:

```text
monthly_queries = 1,000,000
chunks_without_rerank = 20
chunks_with_rerank = 8
avg_chunk_tokens = 250
LLM input price = $1 / 1M tokens
rerank cost = $2,000/month
```

Savings:

```text
1,000,000 × (20 - 8) × 250 × $1 / 1,000,000 = $3,000/month
```

In this case, reranking saves $3,000 in input tokens and costs $2,000, so it is cost-positive before considering quality improvements.

If the generator input price is much lower, or if chunk reduction is smaller, reranking may not save money directly.

## Reranker optimization levers

| Lever | Cost effect | Quality risk |
|---|---|---|
| Lower top-k reranked | directly lowers cost | may miss relevant candidates |
| Retrieve better first-stage candidates | lowers needed fanout | requires tuning hybrid/vector retrieval |
| Use two-stage rerank | cheap reranker filters before expensive reranker | extra complexity |
| Shorten candidate passages | lowers tokens | may remove needed context |
| Deduplicate near-identical chunks | lowers fanout | requires robust chunk IDs/similarity logic |
| Cache rerank results | lowers repeated-query cost | invalidation can be hard |
| Use adaptive reranking | rerank only uncertain/important queries | requires confidence/router logic |
| Self-host high-volume reranker | lower unit cost at scale | ops burden |

## Adaptive reranking policy

A practical policy:

```text
if query_is_navigational_or_exact_match:
    skip reranker or use small fanout
elif first_stage_score_margin_high:
    rerank top 10-20
elif query_is_high_value_or_ambiguous:
    rerank top 50-100
else:
    rerank top 25
```

Signals:

- top-1/top-2 score margin;
- lexical match strength;
- query length/complexity;
- user tier;
- domain risk;
- answer confidence;
- cache hit availability;
- cost budget remaining.

## Interview-ready answer

> I would not treat reranking as a fixed add-on. I would model it as a candidate-fanout cost. Query embedding might be pennies or dollars per million queries, while reranking can be thousands per million queries depending on pricing. The right design is adaptive: tune first-stage recall, deduplicate candidates, rerank only as many as needed, and compare reranker cost against saved LLM context tokens and quality gains.
