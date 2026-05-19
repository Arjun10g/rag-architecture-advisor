# Decision Playbooks

## 1. API vs self-host embeddings

### Use API embeddings when

- QPS is low or unknown.
- Traffic is bursty.
- The model choice is changing.
- You need fast iteration.
- You do not have strong GPU/SRE operations capacity.
- Data can leave your environment under policy.
- You do not yet know utilization.

### Use self-host embeddings when

- QPS is high and steady.
- You have large offline embedding/backfill jobs.
- You can keep GPUs highly utilized.
- You need custom/fine-tuned models.
- You need strict data locality.
- You can handle deployment, monitoring, scaling, and incidents.

### Decision test

```text
if measured_self_host_monthly_cost_with_labor_and_HA < api_monthly_cost × safety_factor:
    consider self-hosting
else:
    stay API/managed
```

Use a safety factor such as 0.7 to require meaningful savings before taking on ops burden.

## 2. Managed vector DB vs OSS/self-host

### Use managed when

- time-to-production matters;
- team is small;
- workload is not infrastructure-differentiated;
- backups/upgrades/monitoring should be outsourced;
- traffic is unpredictable;
- compliance can be met through managed service features.

### Use OSS/self-host when

- cost at scale justifies ops burden;
- custom index/control is needed;
- strict network/data residency constraints apply;
- cloud/provider lock-in is unacceptable;
- team already operates similar stateful systems;
- workload requires nonstandard compaction, sharding, or ranking.

### Key warning

OSS is not free. The software license may be free, but the bill becomes:

```text
infra + storage + backups + observability + upgrades + incidents + labor
```

## 3. Serverless vector store vs provisioned cluster

### Serverless is best when

- traffic is spiky;
- workload is small-to-medium;
- you want usage metering;
- you want less capacity planning;
- team values operational simplicity.

### Provisioned/resource cluster is best when

- traffic is steady;
- SLOs are strict;
- utilization is predictable;
- reserved capacity discounts apply;
- you need custom resource control.

### Decision test

```text
serverless_cost_at_p95_usage vs provisioned_cost_at_required_capacity
```

Do not compare average serverless cost against underprovisioned cluster cost.

## 4. Rerank or no rerank

### Use reranking when

- first-stage retrieval recall is high but precision is weak;
- hallucination/context waste is expensive;
- answer quality matters;
- candidate fanout can be controlled;
- reranking reduces LLM input context or retries.

### Skip or limit reranking when

- queries are simple/exact-match;
- first-stage score margin is strong;
- cost budget is tight;
- latency SLO is strict;
- candidate passages are very long;
- cache hit rate is high and stable.

### Adaptive policy

```text
if exact_match or high score margin:
    skip or small rerank
elif high-risk/high-value/ambiguous query:
    larger rerank
else:
    medium rerank
```

## 5. Reduce generation cost

### Levers

- reduce retrieved context tokens;
- rerank to increase precision;
- compress context;
- deduplicate chunks;
- cap answer length;
- cache deterministic answers;
- use smaller generator for easy queries;
- route hard queries to stronger model.

### Decision test

```text
cost_saved_by_context_reduction > cost_of_rerank_or_compression
```

## 6. Choose embedding dimension

### Lower dimension is attractive when

- storage/memory cost dominates;
- recall remains acceptable;
- latency is strict;
- index fits in RAM only at lower dimension;
- many tenants are small.

### Higher dimension is attractive when

- retrieval quality is the main bottleneck;
- corpus is semantically complex;
- downstream generation failures are expensive;
- storage cost is minor relative to quality losses.

### Test

Evaluate:

```text
recall@k, MRR/NDCG, answer faithfulness, storage, latency, rerank cost, generation cost
```

Do not pick dimensions by storage alone.

## 7. Caching playbook

### Embedding cache

Best for repeated or normalized queries.

```text
key = model_version + normalized_query
```

Invalidate on model version change.

### Retrieval/result cache

Best for repeated queries and low-freshness-risk content.

```text
key = query + filters + tenant + index_version + permissions_hash
```

Invalidate on index updates, ACL changes, or content changes.

### Semantic cache

Best for low-risk, high-repeat domains.

Risk: false hits return wrong answers.

Use only with:

- confidence thresholds;
- TTL;
- tenant isolation;
- auditability;
- fallback to retrieval.

## 8. Re-embedding/model upgrade playbook

1. Add embedding model version to every vector.
2. Build new embeddings in parallel.
3. Write to a new index/namespace/table.
4. Evaluate retrieval quality and cost.
5. Canary traffic.
6. Switch alias/router.
7. Keep rollback window.
8. Delete old index after safety window.
9. Update caches and invalidate model-version keys.

Cost model:

```text
upgrade_cost = new_embedding_cost + new_index_build_cost + temporary_double_storage + validation + canary + rollback_storage
```

## 9. Multi-tenant cost playbook

| Pattern | Cost | Isolation | Use when |
|---|---|---|---|
| Metadata filter | lowest | weakest | many small low-risk tenants |
| Namespace/collection | medium | medium | SaaS tenants with moderate isolation |
| Separate index | higher | strong | large or regulated tenants |
| Separate cluster/project | highest | strongest | strict compliance or noisy-neighbor concerns |

Decision rule:

```text
small tenants → shared index / namespace
growing tenants → separate namespace or index
regulated/high-value tenants → separate index or cluster
```

## 10. Procurement-ready checklist

Before signing a vendor or GPU commitment, answer:

- What is the 12-month traffic forecast?
- What is the p95/p99 latency SLO?
- What is expected cache hit rate?
- What is top-k retrieved and reranked?
- What is corpus growth/month?
- What is model upgrade cadence?
- What are steady-state and migration peak footprints?
- What is the required isolation level?
- What is the cost per 1,000 queries?
- What is cost per document ingested?
- What is cost per tenant?
- What happens if traffic doubles?
- What happens if the embedding model dimension doubles?
- What happens if rerank top-k doubles?
- What is the rollback plan?
- Who owns on-call?

## Final rule

Choose the architecture with the lowest **risk-adjusted total cost**, not the lowest visible unit price.
