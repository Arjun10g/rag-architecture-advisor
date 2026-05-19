# Executive Summary

## Main thesis

Cost modeling for vector search and RAG is mostly a problem of **utilization, billing units, and pipeline shape**. The visible list price of a vector database, embedding model, or GPU is rarely enough to explain the bill. The dominant cost center changes by workload regime:

- **Prototype / low-QPS workloads:** API calls, managed vector store minimums, and developer time dominate.
- **Fresh ingestion workloads:** embedding, index build, compaction, and write units dominate.
- **Mature high-QPS retrieval workloads:** search serving, reranking, replicas, and cache miss rates dominate.
- **Long-answer RAG workloads:** generation tokens may dominate unless retrieval and reranking reduce context waste.
- **Regulated enterprise workloads:** private networking, audit logs, isolation, backups, and operations can dominate raw compute.

## Key conclusions

### 1. API vs self-host is a utilization question

Token-priced APIs scale linearly with usage. Self-hosted GPUs scale in capacity steps. At low utilization, self-hosting is expensive because the GPU sits idle. At high utilization, self-hosting can become dramatically cheaper on pure compute.

The single-GPU break-even for embedding is approximately:

```text
q* = (gpu_hourly_price × monthly_hours) / (monthly_seconds × tokens_per_query × api_price_per_token)
```

Where `api_price_per_token = price_per_million_tokens / 1,000,000`.

In the report's worked example, using a low-cost hosted embedding rate of **$0.08 per million tokens** and **32 query tokens**, the pure-compute crossover was approximately:

| GPU price assumption | Approx. monthly cost | Query-only crossover |
|---:|---:|---:|
| $1.52/hour A10G-class | $1,109.60/month | ~167 QPS |
| $2.00/hour A100-class | $1,460/month | ~220 QPS |
| $4.326/hour H100-class | $3,157.98/month | ~476 QPS |

Those break-evens move upward once you add ops/labor, standby capacity, deployment overhead, monitoring, failover, and reserved spare capacity.

### 2. Storage-based billing is usually not just storage

Managed vector stores bill through combinations of:

- GB-month or GiB-month storage.
- Read/search units.
- Write/upsert units.
- Query scanned volume.
- Returned network payload.
- Ingest/search/ML compute units.
- Index-build or compaction charges.
- Backups and restore.
- Private networking, audit logs, or enterprise features.
- Minimum monthly plan commitments.

This means naive comparisons like “vendor A is cheaper per GB than vendor B” are usually misleading. The full bill depends on the workload: read-heavy, write-heavy, rerank-heavy, filter-heavy, multi-tenant, fresh-indexing, or archival.

### 3. Reranking can dwarf query embedding cost

Reranking is a major hidden cost because it scales with either:

- query count, when priced per rerank request; or
- candidate count × candidate tokens, when priced by processed tokens; or
- fixed GPU capacity, when self-hosted.

A useful mental model:

```text
Reranker cost ∝ queries × candidates_reranked × average_candidate_tokens
```

When reranking is priced per request, the fanout may be hidden in the vendor’s price. When it is token-priced or self-hosted, fanout is explicit. A 100-candidate rerank over long passages can cost far more than query embedding.

### 4. Cost concentrates differently across the lifecycle

| System phase | Common dominant cost |
|---|---|
| Initial build | document embedding, bulk import, index build |
| Early prototype | API calls, managed minimums, developer time |
| High-QPS production | search serving, replicas, cache misses, reranking |
| Frequent refresh | CDC processing, re-embedding, compaction/rebuild |
| Enterprise rollout | isolation, backups, network, compliance, ops |
| Long-context generation | generation tokens and latency |

### 5. Algorithm choice affects TCO

Index algorithms are not only accuracy/latency choices. They change hardware requirements:

- **HNSW**: high recall and low latency, but memory-heavy; graph overhead and replicas matter.
- **IVF-PQ / PQ**: lower storage and memory, but more quantization loss; useful when RAM or storage dominates.
- **ScaNN-style partition/reorder**: strong serving efficiency for large-scale vector retrieval; useful when partitioned serving throughput is critical.
- **DiskANN**: shifts much of the footprint to SSD and can reduce RAM cost; useful when memory is the limiting resource.
- **Faiss GPU**: good for brute-force or compressed search on GPUs, especially batch/offline or high-throughput workloads.

### 6. The practical recommendation

Use API/managed services first when QPS is low, utilization is unknown, or the model stack is changing. Move to self-host/dedicated capacity when workload is steady, high-throughput, and measurable. Treat reranking and generation as first-class cost centers, not optional footnotes.
