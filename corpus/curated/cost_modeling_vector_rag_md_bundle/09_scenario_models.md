# Scenario Models and Sensitivity Analysis

## Purpose

This file gives reusable scenario models for estimating vector/RAG costs. Replace the assumptions with measured values from your workload.

## Scenario 1: Light support chatbot

### Assumptions

```text
QPS = 5
queries/month = 5 × 2,592,000 = 12,960,000
avg query tokens = 32
embedding API price = $0.08/M tokens
top_k retrieved = 20
top_k reranked = 0 or 10
LLM input tokens/query = 2,000
LLM output tokens/query = 300
```

### Query embedding cost

```text
12,960,000 × 32 × $0.08 / 1,000,000 = $33.18/month
```

### Interpretation

At this scale, query embedding is not the main cost. The likely dominant costs are:

- managed service plan minimums;
- LLM generation;
- developer time;
- observability/evaluation setup;
- support/compliance features.

Self-hosting a GPU purely for query embeddings is unlikely to be economical unless there are strict governance constraints or the GPU is shared with other workloads.

## Scenario 2: Mid-size persistent search

### Assumptions

```text
QPS = 50
queries/month = 129,600,000
avg query tokens = 32
embedding price = $0.08/M
```

### Query embedding cost

```text
129,600,000 × 32 × $0.08 / 1,000,000 = $331.78/month
```

### Interpretation

Still below the pure-compute cost of a single always-on GPU under many common assumptions. API remains attractive unless:

- query tokens are much higher;
- embedding API is expensive;
- same GPU is shared across tasks;
- workload has strict data restrictions;
- high-volume document embedding also runs on the same fleet.

## Scenario 3: Steady production search

### Assumptions

```text
QPS = 250
queries/month = 648,000,000
avg query tokens = 32
embedding price = $0.08/M
single A10G-class GPU = $1.52/hour
```

### Query embedding API cost

```text
648,000,000 × 32 × $0.08 / 1,000,000 = $1,658.88/month
```

### Single GPU monthly cost

```text
$1.52 × 720 = $1,094.40/month
```

### Interpretation

Self-hosting may win on pure compute, but only if:

- one GPU can actually serve the load under latency SLO;
- utilization is high;
- operations overhead is low or shared;
- failover requirements do not multiply capacity too much.

Add 0.1 FTE operations overhead and the self-host side becomes:

```text
$1,094 + $1,833 = $2,927/month
```

Then API may still be cheaper until higher QPS.

## Scenario 4: Large daily batch embedding

### Assumptions

```text
docs/day = 3,000,000
avg tokens/doc = 300
embedding price = $0.08/M
```

### Monthly API cost

```text
3,000,000 × 30 × 300 × $0.08 / 1,000,000 = $2,160/month
```

### Interpretation

Self-hosting or spot/preemptible capacity becomes attractive if GPUs can be kept highly utilized. Batch embedding is usually a stronger self-host candidate than live query embedding because queueing is acceptable and batching can be efficient.

## Scenario 5: Rerank-heavy RAG

### Assumptions

```text
queries/month = 1,000,000
rerank price = $2 / 1,000 requests
query embedding = 32 tokens at $0.08/M
```

### Costs

```text
reranking = 1,000,000 × $2 / 1,000 = $2,000/month
query embedding = 1,000,000 × 32 × $0.08 / 1,000,000 = $2.56/month
```

### Interpretation

Reranking can dominate query embedding by orders of magnitude. Model reranking explicitly.

## Scenario 6: Token-priced reranking sensitivity

### Assumptions

```text
queries/month = 1,000,000
query tokens = 32
candidate tokens = 256
reranker price = $1/M processed tokens
```

### Cost by top-k reranked

| top_k reranked | tokens/request | monthly tokens | cost/month |
|---:|---:|---:|---:|
| 10 | 2,592 | 2.592B | $2,592 |
| 25 | 6,432 | 6.432B | $6,432 |
| 50 | 12,832 | 12.832B | $12,832 |
| 100 | 25,632 | 25.632B | $25,632 |

### Interpretation

Candidate length and top-k are first-order cost levers.

## Scenario 7: Storage footprint for 100M vectors

### Raw FP32 lower bound

| Dimensions | Raw size | At $0.33/GB-month | At $0.047/GB-month |
|---:|---:|---:|---:|
| 768 | ~286 GiB | ~$94/month | ~$13/month |
| 1536 | ~572 GiB | ~$189/month | ~$27/month |
| 3072 | ~1.12 TiB | ~$378/month | ~$54/month |

### Interpretation

Raw storage alone may look cheap compared with serving, reranking, or generation. But raw vector storage is only the lower bound. Add index overhead, metadata, replicas, backups, and migration double-storage.

## Scenario 8: Blue/green re-embedding peak cost

### Assumptions

```text
old index = 1 TB serving footprint
new index = 1.5 TB serving footprint
replicas = 2
rollback snapshots = 1 TB
```

### Peak storage

```text
peak = (1TB + 1.5TB) × 2 + 1TB = 6TB
```

### Interpretation

Migration windows can require many times steady-state storage. Re-embedding cost models need a peak-cost line, not just steady-state cost.

## Sensitivity matrix

| Variable | Low | Medium | High | Why it matters |
|---|---:|---:|---:|---|
| QPS | 5 | 50 | 500 | drives API and serving spend |
| avg query tokens | 16 | 64 | 256 | drives query embedding and generation |
| docs/day | 10k | 1M | 10M | drives ingestion and document embedding |
| top_k reranked | 10 | 50 | 100 | drives reranker spend |
| candidate tokens | 128 | 256 | 512 | drives token-priced rerankers |
| vector dimensions | 384 | 1536 | 3072 | drives storage/memory |
| replicas | 1 | 2 | 3 | multiplies serving/storage |
| cache hit rate | 0% | 50% | 80% | reduces query-time costs |
| model upgrade cadence | annual | quarterly | monthly | drives re-embedding/reindex cost |
| ops labor | 0 FTE | 0.1 FTE | 0.5 FTE | shifts self-host crossover |

## Recommended spreadsheet columns

```text
scenario_name
qps_avg
qps_p95
queries_month
avg_query_tokens
documents_month
avg_doc_tokens
embedding_price_per_million
query_embedding_cost
doc_embedding_cost
vectors_total
vector_dimensions
raw_vector_gb
index_overhead_multiplier
replicas
storage_gb_month
storage_cost
read_units
read_cost
write_units
write_cost
top_k_retrieved
top_k_reranked
avg_candidate_tokens
rerank_cost
generator_input_tokens
generator_output_tokens
generation_cost
cache_hit_rate
network_gb
network_cost
ops_fte
ops_cost
monthly_total
cost_per_1000_queries
```
