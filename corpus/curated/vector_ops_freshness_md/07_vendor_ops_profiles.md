# 07 — Vendor Operational Profiles for Ops and Freshness

This file summarizes operational patterns for the major vector-store candidates. Always verify current vendor docs before implementing: public APIs and managed-service capabilities change quickly.

## Comparative matrix

| Vendor | Incremental ingestion | Deletes/tombstones | Blue-green/versioning | Tenancy | Caching notes |
|---|---|---|---|---|---|
| Pinecone | Upsert/import APIs; application CDC writer common. Freshness checks documented. | Delete by ID/filter/namespace depending API; verify physical retention separately. | Use index/namespace versioning and app router; native atomic alias swap not clearly specified in reviewed docs. | Namespaces are the documented multi-tenancy primitive. | Include namespace/index/model version in result keys. |
| Weaviate | Batch imports and object operations; tenant-aware ingestion. | Tombstone/cleanup knobs exposed in vector index config. | Collection aliases can support swaps. | First-class multi-tenancy. | Cache by tenant, collection alias target, schema/index version. |
| Milvus/Zilliz | Bulk insert, streaming/message-queue architecture in Milvus ecosystem; partition-key patterns. | Delete records and compaction; L0 compaction mentioned in release notes. | Version collections/aliases or app routing depending deployment. | Databases/collections/partitions/partition keys. | Cache by collection/partition/index params/version. |
| Qdrant | Point upserts/deletes; distributed deployment and shard concepts. | Live deletes; snapshots; compaction behavior should be validated for workload. | Version collections or use aliases/app router depending version. | Collections, shards, shard keys, cloud/project controls. | Include collection/shard/tenant/filter in keys. |
| pgvector | Use DB writes or Postgres CDC; transactional semantics inherited from Postgres. | PostgreSQL delete/MVCC/VACUUM/REINDEX rules apply. | Table/schema/view versioning; transactional cutovers possible. | Postgres schemas/tables/RLS/roles. | Cache invalidation can subscribe to DB CDC/NOTIFY patterns. |
| Elastic | Bulk indexing, pipelines, transforms; index aliases. | Deletes reclaimed on segment merge; disk usage docs cover cleanup behavior. | Native aliases are strong. | Index/project/security model, DLS where licensed/applicable. | Include alias target/index generation and user role/ACL hash. |
| OpenSearch | Bulk indexing; aliases; managed/serverless options. | Deletes reclaimed by Lucene segment merges. | Index aliases support swaps. | Index/security-domain patterns. | Same as Elastic: alias/index/filter/role in key. |
| Vespa | Feed API and document operations; built for online serving. | Document delete operations; background reindex for schema/index changes. | Reindexing is a first-class operation. | Tenant/application/instance/environment in cloud; app-level data isolation. | Cache query profiles and results carefully by app/package version. |
| LanceDB | Add/update/delete table operations; object-store-backed workflows. | Soft delete/update lifecycle plus optimize/table maintenance patterns. | Table versioning supports reproducibility; app routing for active versions. | Database/table/namespace patterns; Enterprise features may matter. | Cache by table version for reproducibility. |
| Chroma | Upsert/delete API; tenant/database/collection architecture. | Verify physical retention/backup semantics per OSS/Cloud deployment. | Version collections/databases and route in app. | Tenant/database/collection. | Include tenant/database/collection and collection version. |
| Redis | Key writes and RediSearch indexing; excellent for hot mutable data. | Key deletes/expiry; persistence/backups/replicas matter. | Version key prefixes or indexes. | ACLs, DBs, key prefixes, deployment isolation. | Redis is itself often the cache; avoid mixing cache and source semantics. |
| MongoDB Atlas Vector Search | MongoDB writes and change streams can drive vector updates. | MongoDB delete semantics plus vector search index propagation. | Collection/index versioning and app routing. | Org/project/cluster/db/collection/roles. | Change streams can trigger cache invalidation. |
| Vertex AI Vector Search | Batch and streaming update paths depending index type. | Update/rebuild docs guide operations. | Parallel index deployments and endpoint/routing patterns. | GCP projects, IAM, endpoints, collections/indexes. | Include deployed index ID, model version, endpoint, and IAM/tenant context. |
| Azure AI Search | Push APIs and indexers; aliases for stable endpoint. | Push deletes through indexing APIs; rebuild when schema/index changes. | Native index aliases. | Search services, indexes, Azure RBAC. | Include alias target/index name, semantic config, user/ACL context. |

## Pinecone

Pinecone is easiest when treated as a managed serving index behind an application-owned ingestion log. Use stable vector IDs, namespaces for tenants, and explicit metadata versions. Because managed systems may have write-to-query visibility lag, run freshness probes after upserts/deletes.

Recommended pattern:

```text
CDC/event log → embedding worker → Pinecone upsert/delete → freshness probe
```

For model upgrades, create a new index or namespace version and route at the application layer unless your current Pinecone plan/API exposes an alias-like primitive suitable for your needs.

Sources: Pinecone freshness, indexing overview, multi-tenancy docs.

## Weaviate

Weaviate is strong when first-class tenants matter. Use Weaviate multi-tenancy instead of only a `tenant_id` metadata filter when tenant counts are high and lifecycle operations matter. Collection aliases are useful for versioned swaps. Tombstone/cleanup settings are exposed in vector index configuration, so high-delete workloads should monitor tombstone ratio and cleanup behavior.

Recommended pattern:

```text
tenant-aware batch/CDC writer → Weaviate tenant collection → collection alias for active version
```

## Milvus/Zilliz

Milvus/Zilliz is powerful but requires more operational design. Use partition keys, collections, or databases according to tenant isolation needs. High-delete workloads should monitor compaction, delete records, and storage amplification. For structural changes, create new collections and cut over via aliases or application routing.

Recommended pattern:

```text
bulk/stream ingest → collection/partition strategy → compaction monitoring → versioned collection migration
```

## Qdrant

Qdrant is operationally attractive for filtered vector search. Use payload indexes for common filters and shard keys/collections for tenant or scale boundaries. Ensure delete and snapshot behavior matches your compliance needs. For index versioning, version collections and route through an application mapping table if native aliases are not sufficient in your deployment.

## pgvector

pgvector's main advantage is operational co-location with PostgreSQL. Use normal database transactions, CDC, schemas, roles, and RLS. However, vector indexes can bloat and require Postgres maintenance. HNSW/IVFFlat index changes may require concurrent index build or new tables.

Recommended pattern:

```text
source rows and vectors in Postgres → transactional update → SQL filters/RLS → optional CDC invalidation
```

This is one of the best options when read-after-write consistency matters more than specialized vector-DB features.

## Elastic and OpenSearch

Elastic/OpenSearch are strongest when vector retrieval is part of a broader search platform. Use index aliases for blue-green swaps. Remember that deletes are usually reclaimed on segment merge, not immediately as disk reduction. Use document-level security or application-enforced filters carefully.

Recommended pattern:

```text
bulk index to docs_v12 → validate → alias docs_current -> docs_v12 → retire docs_v11
```

## Vespa

Vespa is designed for online serving and complex ranking. It has a first-class reindexing story for schema/index changes. Use Vespa when retrieval/ranking logic is central and you can adopt its deployment model. Treat application package/schema versions as part of your cache and rollout keys.

## LanceDB

LanceDB is attractive for object-store/table-version-oriented vector workflows. Table versioning is useful for reproducible indexing and rollback-like workflows. Use `optimize`/maintenance processes according to docs for cleanup after updates/deletes. Application routing is typically the control plane for active versions.

## Chroma

Chroma's tenant/database/collection concepts make it simple to structure smaller applications. For production Cloud usage, verify current quotas, retention, and backup behavior. Use collection versioning for model/chunker changes.

## Redis

Redis is best when vector search is close to hot application state, session memory, or cache workloads. Use ACLs, key prefixes, and deployment isolation. Be careful not to let cached vector results become the hidden source of truth. Use short TTLs for mutable/private data.

## MongoDB Atlas Vector Search

Atlas is best when source documents already live in MongoDB. Change streams can drive cache invalidation or external indexing. If using Atlas Vector Search directly, document the lag between document writes and vector-search visibility. Use Atlas project/cluster/database/collection boundaries for tenancy.

## Vertex AI Vector Search

Vertex is best inside GCP-native architectures. Use IAM, endpoints, and deployed index IDs as operational boundaries. For major upgrades, build new indexes and route through endpoints/application logic. Use batch or streaming update modes according to freshness and cost requirements.

## Azure AI Search

Azure AI Search is strongest for Azure-governed enterprise search/RAG. Use index aliases for blue-green swaps and Azure RBAC for access management. Treat integrated vectorization/indexers as part of the ingestion pipeline and monitor indexer lag.

## Sources

- [Pinecone freshness](https://docs.pinecone.io/guides/index-data/check-data-freshness)
- [Pinecone multitenancy](https://docs.pinecone.io/guides/index-data/implement-multitenancy)
- [Weaviate multitenancy](https://docs.weaviate.io/weaviate/manage-collections/multi-tenancy)
- [Weaviate aliases](https://docs.weaviate.io/weaviate/manage-collections/collection-aliases)
- [Milvus multitenancy](https://milvus.io/docs/multi_tenancy.md)
- [Milvus release notes](https://milvus.io/docs/v2.4.x/release_notes.md)
- [Qdrant distributed deployment](https://qdrant.tech/documentation/distributed_deployment/)
- [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md)
- [Elastic aliases](https://www.elastic.co/docs/manage-data/data-store/aliases)
- [Elastic disk usage](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/disk-usage)
- [OpenSearch aliases](https://docs.opensearch.org/latest/im-plugin/index-alias/)
- [Vespa reindexing](https://docs.vespa.ai/en/operations/reindexing.html)
- [LanceDB updates](https://docs.lancedb.com/tables/update)
- [LanceDB versioning](https://docs.lancedb.com/tables/versioning)
- [Chroma architecture](https://docs.trychroma.com/reference/architecture/overview)
- [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/)
- [MongoDB change streams](https://www.mongodb.com/docs/manual/changestreams/)
- [MongoDB Vector Search](https://www.mongodb.com/docs/vector-search/)
- [Vertex update/rebuild index](https://docs.cloud.google.com/vertex-ai/docs/vector-search/update-rebuild-index)
- [Vertex IAM vectorsearch roles](https://docs.cloud.google.com/iam/docs/roles-permissions/vectorsearch)
- [Azure Search aliases](https://learn.microsoft.com/en-us/azure/search/search-how-to-alias)
- [Azure Search RBAC](https://learn.microsoft.com/en-us/azure/search/search-security-rbac)
