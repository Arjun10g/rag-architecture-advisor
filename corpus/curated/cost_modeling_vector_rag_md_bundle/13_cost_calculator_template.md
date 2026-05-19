# Cost Calculator Template

Copy these variables into a spreadsheet or notebook.

## Inputs

```yaml
traffic:
  avg_qps:
  p95_qps:
  queries_per_month:
  avg_query_tokens:

corpus:
  documents_total:
  documents_added_per_month:
  avg_document_tokens:
  chunks_per_document:
  avg_chunk_tokens:
  vectors_total:
  embedding_dimensions:
  bytes_per_dimension: 4
  avg_metadata_bytes_per_vector:

embedding_api:
  price_per_million_tokens:

self_host_embedding:
  gpu_hourly_price:
  monthly_hours: 720
  sustainable_qps_per_gpu:
  active_gpus:
  standby_gpus:
  ops_fte:
  fully_loaded_fte_annual_cost:

vector_store:
  storage_price_per_gb_month:
  read_unit_price:
  write_unit_price:
  read_units_per_query:
  write_units_per_vector:
  backup_price_per_gb_month:
  egress_price_per_gb:
  plan_minimum:

reranking:
  fraction_queries_reranked:
  top_k_reranked:
  avg_candidate_tokens:
  per_1000_request_price:
  token_price_per_million:
  pricing_mode: request_or_token

generation:
  input_price_per_million_tokens:
  output_price_per_million_tokens:
  avg_input_tokens_per_answer:
  avg_output_tokens_per_answer:

cache:
  embedding_cache_hit_rate:
  retrieval_cache_hit_rate:
  semantic_cache_hit_rate:
```

## Derived fields

```text
seconds_per_month = 2,592,000
queries_per_month = avg_qps × seconds_per_month
query_embedding_tokens = queries_per_month × avg_query_tokens
doc_embedding_tokens = documents_added_per_month × avg_document_tokens
raw_vector_gb = vectors_total × embedding_dimensions × bytes_per_dimension / 1024^3
metadata_gb = vectors_total × avg_metadata_bytes_per_vector / 1024^3
serving_storage_gb = (raw_vector_gb + metadata_gb) × index_overhead_multiplier × replica_count
```

## Cost lines

```text
query_embedding_api_cost = query_embedding_tokens × embed_price_per_million / 1,000,000
doc_embedding_api_cost = doc_embedding_tokens × embed_price_per_million / 1,000,000
self_host_embedding_cost = (active_gpus + standby_gpus) × gpu_hourly_price × 720 + ops_fte × annual_fte_cost / 12
storage_cost = serving_storage_gb × storage_price_per_gb_month
read_cost = queries_per_month × read_units_per_query × read_unit_price
write_cost = new_vectors_per_month × write_units_per_vector × write_unit_price
backup_cost = backup_gb × backup_price_per_gb_month
network_cost = egress_gb × egress_price_per_gb
rerank_request_cost = queries_per_month × fraction_reranked × per_1000_request_price / 1000
rerank_token_cost = queries_per_month × fraction_reranked × (avg_query_tokens + top_k_reranked × avg_candidate_tokens) × token_price_per_million / 1,000,000
generation_cost = queries_per_month × (input_tokens × input_price_per_million + output_tokens × output_price_per_million) / 1,000,000
total_monthly_cost = sum(cost_lines) + plan_minimum_adjustment
cost_per_1000_queries = total_monthly_cost / queries_per_month × 1000
```

## Sensitivity runs

Run scenarios for:

```text
avg_qps = 5, 50, 250, 1000
embedding_dimensions = 384, 768, 1536, 3072
top_k_reranked = 0, 10, 25, 50, 100
cache_hit_rate = 0%, 25%, 50%, 80%
ops_fte = 0, 0.1, 0.25, 0.5
replica_count = 1, 2, 3
model_upgrade_frequency = annual, quarterly, monthly
```
