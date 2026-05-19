# 05 — Multi-Tenancy Patterns in Vector Stores

## The multi-tenancy problem

Multi-tenancy in vector stores has two different meanings:

1. **Logical tenancy**: queries for tenant A must not return tenant B's data.
2. **Operational tenancy**: tenant A's scale, deletes, latency spikes, or backfills should not harm tenant B.

Many systems solve the first with metadata filters but fail the second. The right pattern depends on isolation, tenant count, tenant size distribution, compliance, and cost.

## Main patterns

| Pattern | Description | Best for | Weakness |
|---|---|---|---|
| Metadata filter | Shared index; each vector has `tenant_id`; every query filters by tenant. | Many small tenants, simple ops. | Weak blast-radius isolation; filter mistakes are dangerous. |
| Namespace / tenant primitive | Vendor-supported logical partition inside index/collection. | Many tenants with better delete/query partitioning. | Isolation depends on vendor implementation. |
| Collection/index per tenant | Separate physical index or collection for each tenant. | Medium tenants, clear lifecycle, easier offboarding. | Many indexes can increase ops and cost. |
| Database/schema per tenant | Separate DB/schema but shared cluster. | Stronger admin boundaries and backup/restore. | More provisioning overhead. |
| Cluster/project/account per tenant | Dedicated deployment. | Regulated, large, or noisy tenants. | Highest cost and operational burden. |
| Hybrid tiering | Small tenants shared; large/regulatory tenants isolated. | Most SaaS platforms. | Requires tenant migration tooling. |

## Namespace versus metadata filter versus separate index

### Metadata filter

```text
shared_index
  record metadata: tenant_id = T1
  query: vector_search(q, filter={tenant_id: T1})
```

Pros:

- lowest cost;
- easiest global capacity pooling;
- simple when tenants are tiny;
- fewer indexes to monitor.

Cons:

- every query must include correct tenant filter;
- high-selectivity filters may harm ANN recall/latency depending on engine;
- tenant delete/offboarding may be expensive;
- a noisy tenant can affect shared index performance;
- security depends heavily on application-layer enforcement.

Use metadata filters only when tenants are small, risk is low, and you have strong query construction tests.

### Namespace / tenant primitive

```text
index: docs
  namespace: tenant_A
  namespace: tenant_B
```

Pros:

- better logical separation than pure metadata filter;
- often easier tenant delete/export;
- still cost-efficient;
- vendor may optimize queries within tenant partition.

Cons:

- not always equivalent to physical isolation;
- cross-namespace analytics may be harder;
- per-namespace limits may apply;
- vendor lock-in to namespace semantics.

Pinecone explicitly documents namespaces for multi-tenancy. Weaviate has first-class multi-tenancy at collection level. Milvus discusses multi-tenancy patterns using databases/collections/partitions/partition keys depending on need.

### Separate index/collection per tenant

```text
tenant_A_docs_v12
tenant_B_docs_v12
```

Pros:

- strong lifecycle boundaries;
- tenant-specific index params;
- easier offboarding and backups;
- easier per-tenant blue-green migrations;
- reduced cross-tenant filter leakage risk.

Cons:

- many indexes/collections can become operationally heavy;
- small tenants waste capacity;
- global schema changes require orchestration;
- query fan-out across tenants is harder.

### Separate cluster/project/account

Pros:

- strongest blast-radius isolation;
- separate encryption/networking/IAM;
- clearer compliance story;
- tenant-specific scaling and cost attribution.

Cons:

- high fixed cost;
- provisioning and upgrade overhead;
- complex fleet management.

Use for regulated customers, very large tenants, or tenants with custom contractual requirements.

## Isolation dimensions

Evaluate tenancy across these axes:

| Dimension | Question |
|---|---|
| Query isolation | Can a bug return another tenant's data? |
| Write isolation | Can one tenant's backfill slow others? |
| Delete isolation | Can one tenant be purged without scanning shared data? |
| Cost isolation | Can spend be attributed and capped per tenant? |
| Performance isolation | Can noisy tenants hurt p99 latency? |
| Admin isolation | Can tenant admins access only their data? |
| Network isolation | Does tenant require private networking or dedicated region? |
| Crypto isolation | Does tenant require separate keys? |
| Backup isolation | Can tenant restore/export/delete independently? |

## Tenant lifecycle operations

A tenant-aware vector platform needs runbooks for:

- create tenant;
- assign region/storage/index type;
- ingest initial corpus;
- rotate keys;
- update ACL policy;
- migrate tenant from shared to dedicated;
- re-embed tenant only;
- export tenant data;
- delete/offboard tenant;
- verify no cross-tenant retrieval.

## Tenant routing table

Maintain a routing table outside the vector DB:

```json
{
  "tenant_id": "tenant_123",
  "tier": "dedicated|shared|regulated",
  "region": "ca-central-1",
  "vector_backend": "qdrant",
  "physical_index": "shared_docs_ca_v12",
  "namespace": "tenant_123",
  "active_index_version": "v12",
  "embedding_model_version": "embed-v3",
  "cache_policy": "tenant-private",
  "status": "active"
}
```

This enables tenant migration without changing application logic.

## Security guardrails

- Require `tenant_id` at the API boundary.
- Do not accept tenant filters from the client directly; derive them from auth context.
- Include tenant ID in vector DB namespace/index selection and metadata filter where possible.
- Include tenant and ACL hash in cache keys.
- Add automated tests that query with missing tenant filters and expect failure.
- Run canary cross-tenant leakage probes.
- Prefer separate physical indexes/clusters for regulated tenants.

## Cost model

| Pattern | Fixed cost | Marginal cost | Operational complexity | Isolation |
|---|---:|---:|---:|---:|
| Metadata filter | Low | Low | Low | Low |
| Namespace/tenant primitive | Low-medium | Low | Medium | Medium |
| Index per tenant | Medium | Medium | Medium-high | High |
| Cluster per tenant | High | High | High | Very high |
| Hybrid tiering | Medium | Optimized | High | Tunable |

The most common production pattern is hybrid: small tenants share capacity; large or regulated tenants move to separate indexes or clusters.

## Vendor patterns

| Vendor | Tenancy primitive |
|---|---|
| Pinecone | Namespaces are the main documented multi-tenancy primitive. |
| Weaviate | Multi-tenancy is first-class at the collection level. |
| Milvus/Zilliz | Databases, collections, partitions, partition keys; choose by isolation level. |
| Qdrant | Collections, shards, shard keys, and API/cloud controls; application routing often matters. |
| pgvector | Postgres schemas/tables/roles/RLS; tenancy inherited from Postgres. |
| Elastic/OpenSearch | Index/project/security model; document-level security and aliases can help. |
| Vespa | Tenant/application/instance/environment model in Vespa Cloud; schema/query filters for data-level isolation. |
| LanceDB | Namespaces/databases/table organization; verify Enterprise features for strict tenancy. |
| Chroma | Tenant/database/collection concepts in architecture. |
| Redis | Databases, key prefixes, ACLs, and deployment-level isolation. |
| MongoDB Atlas | Organization/project/cluster/database/collection plus roles; vector search lives in Atlas data model. |
| Vertex AI Vector Search | GCP projects, IAM, endpoints, collections/indexes. |
| Azure AI Search | Search services, indexes, aliases, Azure RBAC. |

## When to use which pattern

| Situation | Recommended tenancy pattern |
|---|---|
| 10,000 tiny tenants, low compliance risk | Namespace/tenant primitive or metadata filter with strong tests. |
| 100 medium tenants with independent lifecycle | Collection/index per tenant or namespace with routing table. |
| One huge tenant plus many small tenants | Dedicated index/cluster for huge tenant; shared pool for small tenants. |
| Regulated enterprise customer | Separate cluster/project/account, private networking, separate keys. |
| Frequent tenant offboarding | Namespace/index per tenant to simplify deletion. |
| Heavy per-tenant custom ranking/schema | Separate index or collection per tenant. |
| Shared public corpus with user-level ACLs | Shared index plus document-level ACL filters; cache keys must include ACL. |

## Sources

- [Pinecone multitenancy](https://docs.pinecone.io/guides/index-data/implement-multitenancy)
- [Weaviate multitenancy](https://docs.weaviate.io/weaviate/manage-collections/multi-tenancy)
- [Milvus multitenancy](https://milvus.io/docs/multi_tenancy.md)
- [Qdrant distributed deployment](https://qdrant.tech/documentation/distributed_deployment/)
- [Elastic search application security](https://www.elastic.co/docs/solutions/elasticsearch-solution-project/search-applications/search-application-security)
- [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/)
- [Vertex IAM vectorsearch roles](https://docs.cloud.google.com/iam/docs/roles-permissions/vectorsearch)
- [Azure Search RBAC](https://learn.microsoft.com/en-us/azure/search/search-security-rbac)
- [Chroma architecture](https://docs.trychroma.com/reference/architecture/overview)
