# Cost Model Formulas

This file collects reusable formulas for cost modeling vector search and RAG systems.

## 1. Monthly traffic conversions

```text
seconds_per_month = 30 × 24 × 3600 = 2,592,000
hours_per_month   = 30 × 24 = 720
monthly_queries   = QPS × 2,592,000
```

For irregular workloads, replace average QPS with a traffic distribution:

```text
monthly_queries = Σ queries_in_window_i
peak_QPS        = max(QPS_i)
p95_QPS         = percentile(QPS_i, 95)
```

Use average QPS for token/API spend and p95/p99 QPS for capacity planning.

## 2. Hosted API embedding cost

```text
C_api_embed = monthly_tokens × price_per_million_tokens / 1,000,000
```

For query embeddings:

```text
monthly_tokens = monthly_queries × avg_query_tokens
C_api_query_embed = QPS × seconds_per_month × avg_query_tokens × price_per_million_tokens / 1,000,000
```

For document embeddings:

```text
monthly_doc_tokens = docs_embedded_per_month × avg_doc_tokens
C_api_doc_embed = docs_embedded_per_month × avg_doc_tokens × price_per_million_tokens / 1,000,000
```

For chunk-level embeddings:

```text
chunks_per_doc = ceil(avg_doc_tokens / target_chunk_tokens) × overlap_multiplier
monthly_chunk_tokens = docs_per_month × chunks_per_doc × avg_chunk_tokens
```

Important: overlap increases effective token volume.

## 3. Self-host embedding capacity cost

Fixed-capacity monthly cost:

```text
C_self = ceil(required_QPS / sustainable_QPS_per_gpu) × gpu_hourly_price × hours_per_month
```

A simple sustainable throughput model:

```text
sustainable_QPS_per_gpu = productive_utilization × effective_batch_size / batch_latency_seconds
```

Where:

- `productive_utilization` excludes idle time, warmup, restarts, batching inefficiency, and deployment overhead.
- `effective_batch_size` depends on sequence length, model size, memory, and serving stack.
- `batch_latency_seconds` must be measured, not guessed.

## 4. API vs self-host crossover

Single-GPU pure-compute break-even:

```text
q_star = (gpu_hourly_price × hours_per_month) /
         (seconds_per_month × avg_query_tokens × price_per_million_tokens / 1,000,000)
```

With labor and overhead:

```text
q_star_with_overhead = (gpu_hourly_price × hours_per_month + monthly_ops_overhead + monthly_platform_overhead) /
                       (seconds_per_month × avg_query_tokens × price_per_million_tokens / 1,000,000)
```

With N+1 failover:

```text
C_self_HA = (active_gpus + standby_gpus) × gpu_hourly_price × hours_per_month
```

With replicas:

```text
C_self_replicated = replica_count × C_single_serving_stack
```

## 5. Reserved, committed, and spot capacity

Reserved effective used-hour cost:

```text
effective_used_hour_reserved = reserved_hourly_price / scheduled_utilization
```

Spot/preemptible effective used-hour cost:

```text
effective_used_hour_spot = spot_hourly_price / (1 - lost_fraction_from_interruptions)
                           + restart_penalty_per_productive_hour
```

Capacity block effective cost:

```text
effective_hourly_capacity_block = total_block_price / block_hours
```

Always distinguish:

- wall-clock utilization;
- accelerator utilization;
- productive business utilization;
- paid-but-idle reserved capacity.

## 6. Vector storage footprint

Raw dense FP32 vector bytes:

```text
raw_vector_bytes = num_vectors × dimensions × 4
```

FP16 vector bytes:

```text
raw_vector_bytes_fp16 = num_vectors × dimensions × 2
```

Int8/SQ bytes:

```text
raw_vector_bytes_int8 = num_vectors × dimensions × 1
```

HNSW approximate memory:

```text
hnsw_memory ≈ raw_vector_bytes + graph_overhead + metadata + allocator_overhead
```

A rough lower-bound graph edge estimate:

```text
graph_edge_bytes ≈ num_vectors × M × bytes_per_neighbor_id × level_multiplier
```

Where `M` is the HNSW max neighbor parameter and `level_multiplier` captures extra upper layers.

Total replicated footprint:

```text
total_storage = (vector_bytes + index_overhead + metadata_bytes) × replica_count + backup_bytes
```

## 7. Managed vector store cost

Generic managed vector store cost:

```text
C_vector_store = C_storage + C_reads + C_writes + C_index_build + C_backups + C_restore + C_network + C_minimums + C_enterprise_features
```

Where:

```text
C_storage = GB_month × price_per_GB_month
C_reads   = read_units × price_per_read_unit
C_writes  = write_units × price_per_write_unit
C_network = GB_returned_or_egress × price_per_GB
```

For scan-priced vendors:

```text
C_query_scan = TiB_queried × price_per_TiB_queried
```

For resource-priced vendors:

```text
C_cluster = Σ(node_type_hourly × node_count × hours) + disk + backups + transfer
```

## 8. Reranker cost

Per-request rerank cost:

```text
C_rerank_request = monthly_queries_reranked × price_per_1000_requests / 1000
```

Token-priced rerank cost:

```text
tokens_per_rerank_request = query_tokens + top_k_reranked × avg_candidate_tokens
C_rerank_tokens = monthly_queries_reranked × tokens_per_rerank_request × price_per_million_tokens / 1,000,000
```

Self-host reranker cost:

```text
C_self_rerank = ceil(required_rerank_QPS / sustainable_rerank_QPS_per_gpu) × gpu_hourly_price × hours_per_month
```

Rerank fanout sensitivity:

```text
ΔC_rerank / Δtop_k = monthly_queries × avg_candidate_tokens × price_per_token
```

## 9. LLM generation cost

```text
C_generation = input_tokens × input_price_per_token + output_tokens × output_price_per_token
```

With RAG context:

```text
input_tokens = system_prompt_tokens + user_query_tokens + retrieved_context_tokens + tool_schema_tokens + conversation_history_tokens
```

If reranking lets you reduce retrieved context from `K1` chunks to `K2` chunks:

```text
savings = monthly_queries × (K1 - K2) × avg_chunk_tokens × input_price_per_token
```

Reranking is justified on cost alone when:

```text
C_rerank < LLM_context_savings + retry_reduction_savings + escalation_reduction_savings
```

## 10. Cache savings

Embedding cache savings:

```text
C_saved_embedding = cache_hits × avg_query_tokens × embed_price_per_token
```

Result cache savings:

```text
C_saved_result = cache_hits × (query_embed_cost + vector_search_cost + rerank_cost + generation_cost)
```

Semantic cache expected value:

```text
EV_semantic_cache = hit_rate × avoided_cost - false_hit_rate × expected_error_cost - cache_infra_cost
```

Use semantic cache only when false-hit risk is acceptable or outputs are low-stakes.

## 11. Total cost of ownership

```text
TCO = direct_cloud_costs
    + vendor_minimums
    + network_and_private_link
    + observability
    + backups_and_restore_tests
    + security_and_compliance
    + on_call_and_ops_labor
    + incident_cost
    + migration/reindex_cost
    + amortized_training_or_fine_tuning
```

Amortized training/fine-tuning:

```text
amortized_train_per_1000_ops = training_cost / lifetime_operations × 1000
```

## 12. Sensitivity analysis template

Vary at least these:

```text
QPS: [1, 5, 25, 50, 100, 250, 500, 1000]
avg_query_tokens: [16, 32, 64, 128]
docs_per_day: [10k, 100k, 1M, 10M]
avg_doc_tokens: [200, 500, 1000]
top_k_retrieved: [20, 50, 100, 200]
top_k_reranked: [10, 25, 50, 100]
avg_candidate_tokens: [128, 256, 512]
dimensions: [384, 768, 1024, 1536, 3072]
replica_count: [1, 2, 3]
cache_hit_rate: [0%, 20%, 50%, 80%]
productive_gpu_utilization: [15%, 30%, 50%, 70%, 90%]
```
