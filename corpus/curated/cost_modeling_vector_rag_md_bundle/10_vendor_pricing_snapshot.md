# Vendor Pricing Snapshot

**Date-stamp:** compiled/accessed around **May 19, 2026**. Pricing is volatile. Use this file as a modeling checklist, not a procurement quote.

## Provider and vendor pricing summary

| Vendor / provider | Public billing model observed | Main cost drivers | Modeling caveat |
|---|---|---|---|
| OpenAI | API token pricing for models, embeddings, and generation | input tokens, output tokens, embedding tokens, batch/API settings | Re-check official page; model lineup and prices change often |
| Anthropic | API token pricing for Claude models | input/output tokens, prompt caching if applicable | Re-check official page; model prices change |
| Cohere | API and dedicated deployment pricing for embed/rerank/generation | tokens or dedicated instance hours/month | Dedicated hosting can change crossover math |
| Voyage AI | API pricing for embeddings and reranking | tokens, rerank processed tokens | Candidate length and top-k matter greatly |
| Pinecone | Serverless plans, storage, read/write units, embedding and rerank, backup/restore/import | read/write units, storage, reranking, plan minimums | Rerank can dwarf embedding cost |
| Weaviate Cloud | Calculator/resource-oriented pricing | objects, vector dimensions, resource usage, plan | Use calculator for exact workload |
| Milvus OSS | Open-source; no vendor license | infra, storage, ops, cloud services | Ops burden and compaction/rebuild cost are yours |
| Zilliz Cloud | Managed Milvus; compute/storage/transfer/build dimensions | compute, storage, data transfer, index build, audit logs | Multi-part bill; model write-heavy workloads carefully |
| Qdrant Cloud | Resource-based cloud pricing | CPU, memory, disk, backups, inference tokens | HNSW memory can dominate |
| pgvector | Open-source Postgres extension | underlying Postgres compute, memory, IO, storage, HA | Not a separate bill; Postgres scaling is the bill |
| AWS OpenSearch | Instance-based or serverless OCU model | instances/OCUs, storage, semantic search, transfer | Semantic/ML dimensions may be separate |
| Elastic | Hosted and serverless; ingest/search/ML VCUs plus storage/egress | VCUs, storage, egress, support | VCU profile matters more than raw storage |
| Vespa Cloud | Resource pricing | vCPU, memory, disk, GPU memory, hourly | Transparent resource modeling; requires capacity planning |
| LanceDB | OSS/self-host, Enterprise/BYOC | object storage, compute, enterprise terms | Public enterprise pricing limited |
| Chroma Cloud | Writes, storage, query scan volume, returned network | GiB written, GiB-month, TiB queried, GiB returned | Payload size and scanned volume explicit |
| Redis Cloud | Subscription/resource tiers | memory, throughput, persistence, replicas | Vector workloads can be memory-heavy |
| MongoDB Atlas Vector Search | Atlas cluster plus search/vector-search node billing | cluster hours, search nodes, backup, data transfer | DB node and search node economics separate |
| Vertex Vector Search | Calculator-oriented; serving resources, storage, update/rebuild | serving capacity, shards, rebuild/update, storage | Exact rates need calculator and region |
| Azure AI Search | Tier/service-unit based via pricing page/calculator | replicas, partitions, storage, skillsets, vector capacity | Exact regional pricing needs calculator |

## Pricing-page data model

For each vendor, collect these fields before making a decision:

```yaml
vendor:
  pricing_page_url:
  accessed_date:
  service_region:
  plan_or_tier:
  minimum_monthly_commit:
  storage_unit:
  storage_price:
  read_unit_definition:
  read_unit_price:
  write_unit_definition:
  write_unit_price:
  index_build_unit_definition:
  index_build_price:
  backup_price:
  restore_price:
  network_egress_price:
  private_network_price:
  support_price:
  enterprise_feature_price:
  free_tier_limits:
  notes:
```

## Vendor-specific cost questions

### Pinecone

- What are read/write unit assumptions for the workload?
- Does the plan minimum dominate expected usage?
- Are backups/restore/import required?
- Is hosted embedding or hosted reranking used?
- How many namespaces/tenants?

### Weaviate

- What are object count, dimensions, and object size?
- Is managed Cloud, BYOC, or self-hosted used?
- Is vector quantization enabled?
- How are tenants isolated?
- What cluster size is needed for p95 latency?

### Milvus/Zilliz

- OSS Milvus or managed Zilliz?
- How much RAM is needed for the chosen index?
- What is the compaction/write pattern?
- Are index builds separately metered?
- What are storage request and transfer costs?

### Qdrant

- Memory footprint for collections and payload indexes?
- Are quantization or on-disk payloads used?
- How many replicas/shards?
- Is cloud inference used?
- Are backups enabled?

### pgvector

- What Postgres instance size is needed?
- Will vector search share the OLTP primary?
- Are read replicas needed?
- Is HNSW/IVFFlat memory acceptable?
- What is the impact on vacuum, backups, and migrations?

### OpenSearch/Elastic

- Instance-based or serverless?
- How many ingest/search/ML units?
- Is hybrid search and semantic enrichment used?
- How many replicas and shards?
- What are snapshot and egress costs?

### Vespa

- What are vCPU, memory, disk, and GPU needs?
- Is ranking custom and CPU-heavy?
- How many content/search nodes?
- What redundancy is required?
- Is the application multi-tenant?

### LanceDB

- Is it embedded/local, self-hosted, BYOC, or enterprise?
- What object store is used?
- What compute serves queries?
- Is versioning/snapshotting required?
- How will hot/cold data be handled?

### Chroma

- How much data is written per month?
- How much data is scanned per query?
- How large are returned results?
- Does returned network dominate?
- Is Team/Enterprise required?

### Redis

- How much memory is needed after vector/index overhead?
- Are persistence and replicas required?
- What throughput tier is needed?
- Does all data need to be in memory?
- Is Redis already used operationally?

### MongoDB Atlas Vector Search

- What Atlas cluster tier is required?
- Are dedicated search/vector nodes required?
- How much data transfer occurs between DB and search nodes?
- Are backups and PITR enabled?
- Does co-locating metadata and vectors reduce system complexity?

### Vertex Vector Search

- Batch or streaming update?
- How often do compactions/rebuilds occur?
- How many shards/replicas?
- What restrict/filter fields affect shard count?
- Is data already on GCP?

### Azure AI Search

- What tier supports the required vector capacity?
- How many replicas/partitions/service units?
- Are skillsets/indexers used?
- Is semantic ranking used?
- Is the deployment tied to Azure networking/compliance requirements?

## Practical instruction

Before presenting a cost comparison, include the date-stamp and a caveat:

> Prices are based on public pages accessed on May 19, 2026. Provider pricing is volatile; final procurement should re-check official calculators in the target region.
