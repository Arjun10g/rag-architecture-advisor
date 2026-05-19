# Managed Vector Store Billing Models

## Why vector-store billing is hard

Managed vector-store pricing is rarely a simple “dollars per GB” comparison. Real bills often include:

```text
storage + reads + writes + index build + replicas + backups + restore + network + private connectivity + minimums + support
```

The same vendor can be cheap for a low-write, low-return-payload workload and expensive for a high-refresh, high-rerank, high-egress workload.

## Billing dimensions to model

| Dimension | What it means | Why it matters |
|---|---|---|
| Raw vector storage | N × dimensions × bytes per dimension | Dimension choice drives baseline footprint |
| Index overhead | HNSW graph, IVF lists, PQ codes, filter indexes | Can exceed raw vector size for memory-heavy indexes |
| Metadata storage | payloads, fields, ACLs, tenant IDs | Especially important for permission-aware RAG |
| Read units / search units | query/search compute | Dominates high-QPS systems |
| Write units / ingest units | upsert/delete/update load | Dominates fresh or CDC-heavy systems |
| Index-build compute | batch build, compaction, merge, rebuild | Dominates re-embedding/model-upgrade periods |
| Query scan volume | bytes or TiB scanned | Important for scan-priced services |
| Returned network | result payload and egress | Large chunks and cross-region traffic add cost |
| Backup/restore | snapshots and restores | Often ignored until compliance review |
| Minimum plan spend | plan floor | Can dominate small workloads |
| Enterprise features | SSO, audit logs, private networking, support | Can dominate regulated deployments |

## Vendor billing patterns

### Pattern A: usage-metered serverless

Examples: Pinecone Serverless, Elastic Serverless, Chroma Cloud, some Zilliz/Qdrant modes.

Typical bill:

```text
C = storage + read/search units + write/ingest units + network + backup + feature add-ons
```

Best for:

- unpredictable traffic;
- small-to-medium workloads;
- prototypes;
- workloads where avoiding ops burden matters.

Risk:

- high QPS and high write rates can become expensive;
- metered dimensions are easy to underestimate;
- minimum paid plan commitments can dominate small workloads.

### Pattern B: resource-cluster pricing

Examples: Vespa Cloud, Redis Cloud, Mongo Atlas dedicated/search nodes, many Qdrant cluster deployments, self-hosted Milvus/Weaviate/Elastic.

Typical bill:

```text
C = node_count × node_hourly + disk + backups + network + support
```

Best for:

- steady workloads;
- known capacity requirements;
- predictable SLOs;
- teams that can capacity-plan.

Risk:

- idle capacity;
- overprovisioning for peaks;
- operational responsibility;
- shard/replica rebalancing cost.

### Pattern C: hybrid resource + operation pricing

Examples: Zilliz cost model, Vertex Vector Search, OpenSearch Serverless semantic search, managed systems with separately billed builds/compaction.

Typical bill:

```text
C = serving_capacity + storage + build/update_ops + transfer + backups + feature charges
```

Best for:

- large systems where billing dimensions can be modeled;
- systems requiring managed service but predictable operations.

Risk:

- reindexing and compaction bills surprise teams;
- frequent updates can be much more expensive than read-only workloads.

## Vendor profile summary

| Vendor | Pricing model summary | Main cost drivers | Watch-outs |
|---|---|---|---|
| Pinecone | Serverless with plan minimums, storage, read/write units, embeddings, reranking, backups/restore/import | read/write units, storage, rerank requests, paid-plan minimums | Reranking can dwarf query embedding; backups/import/restore separate |
| Weaviate Cloud | Calculator/resource-oriented; dimensions/object counts and plan matter | object count, vector dimensions, resource usage, plan | Exact estimate requires calculator; workload-dependent |
| Milvus OSS | No license cost; infra and ops cost dominate | compute, RAM, disk, object storage, ops labor | You own scaling, compaction, backup, upgrades |
| Zilliz Cloud | Managed Milvus with compute, storage, transfer, index/build related dimensions | CU/vCU, storage, storage requests, data transfer, audit logs | Multi-part bill; write/build heavy workloads need modeling |
| Qdrant Cloud | Resource-based cloud pricing with CPU/memory/disk/backup/inference tokens | memory, disk, CPU, replicas, inference | High-HNSW memory footprint can dominate |
| pgvector | Extension cost is zero; underlying Postgres cost | Postgres compute, RAM, IO, storage, HA, backups | Scaling large ANN and high-QPS can stress DB primary/read replicas |
| OpenSearch | Instance or serverless OCU model; semantic search can add OCU charges | OCUs, storage, data transfer, semantic enrichment | Ingest/search/ML dimensions separate |
| Elastic | Hosted or serverless; ingest/search/ML VCUs, storage, egress | VCUs, storage, support tier, egress | Support and VCU dimensions matter more than raw storage |
| Vespa | Resource-priced cloud plans | vCPU, memory, disk, GPU memory, replicas | Very transparent for resource modeling; must capacity-plan |
| LanceDB | OSS/self-host or Enterprise/BYOC | object storage, compute, query serving, enterprise contract | Public enterprise pricing limited; self-host infra modeling needed |
| Chroma | Usage pricing: writes, storage, query scan, returned network | GiB written, GiB-month, TiB queried, GiB returned | Returned payload and scanned volume are explicit costs |
| Redis | Resource/subscription pricing | memory footprint, throughput, persistence, replicas | Vector workloads can be memory-heavy |
| Mongo Atlas Vector Search | Atlas clusters plus search/vector search nodes | cluster hours, search node hours, backup, data transfer | Separate DB and search-node capacity can surprise teams |
| Vertex Vector Search | Calculator-oriented; serving resources, builds/updates, storage | index serving, shard count, rebuild/update, storage | Streaming updates/compaction can add billed rebuild/update cost |
| Azure AI Search | Tier/service-unit based pricing via calculator | search units/replicas/partitions, storage, skillsets | Exact regional pricing needs calculator; vector capacity varies by tier |

## Questions to answer before vendor selection

1. What is the expected p50, p95, and peak QPS?
2. How many vectors, dimensions, metadata bytes, and replicas?
3. Is the workload read-heavy, write-heavy, or rebuild-heavy?
4. What is the required freshness lag?
5. How often will embeddings be regenerated?
6. What is top-k retrieved and top-k reranked?
7. Does the workload need hybrid search, ACL filtering, or high-cardinality metadata filters?
8. Is tenant isolation implemented through namespaces, filters, separate indexes, or separate clusters?
9. Are backups, restore tests, audit logs, SSO, and private networking required?
10. Is there a minimum monthly spend that dwarfs actual usage?

## Cost model template

```text
Monthly vector-store cost =
  storage_GB_month × storage_price
+ read_units × read_unit_price
+ write_units × write_unit_price
+ index_build_units × build_unit_price
+ backup_GB_month × backup_price
+ restore_GB × restore_price
+ network_GB × egress_price
+ enterprise_feature_fee
+ plan_minimum
```

For cluster-priced systems:

```text
Monthly vector-store cost =
  Σ(node_hourly_price × node_count × 720)
+ disk_GB_month × disk_price
+ backup_GB_month × backup_price
+ egress_GB × egress_price
+ support_fee
+ ops_labor
```

## Practical conclusion

Do not choose a vector store by storage price alone. Choose it by the **dominant metered dimension** of your workload: reads, writes, rebuilds, memory, network, isolation, or operations.
