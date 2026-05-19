# 08 — Studies, Articles, and Source Guide

This file lists the most relevant sources for operational design around freshness, CDC, indexing lifecycle, multi-tenancy, deletes, caching, and vendor-specific patterns.

## CDC and streaming correctness

### Debezium documentation

Debezium is the standard open-source reference for log-based change data capture. Its features and connector docs explain how database changes are captured from transaction logs and emitted as events.

Why it matters for vector stores:

- CDC is the safest way to keep vector indexes synchronized with source databases.
- CDC events provide ordering and version metadata that can support idempotent upserts.
- CDC helps detect deletes that timestamp-based crawlers often miss.

Sources:

- [Debezium features](https://debezium.io/documentation/reference/stable/features.html)
- [Debezium PostgreSQL connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)

### Kafka delivery semantics

Kafka's delivery semantics documentation is useful for understanding at-least-once, at-most-once, and exactly-once boundaries. In vector ingestion, the practical lesson is that downstream vector writes must be idempotent even if upstream streaming has strong delivery guarantees.

Source:

- [Kafka delivery semantics](https://docs.confluent.io/kafka/design/delivery-semantics.html)

### Google Pub/Sub ordering and exactly-once docs

Pub/Sub's ordering and exactly-once-delivery documentation is relevant for GCP-native ingestion pipelines. It is especially useful when designing per-document ordering and retry behavior.

Sources:

- [Google Pub/Sub exactly once](https://docs.cloud.google.com/pubsub/docs/exactly-once-delivery)
- [Google Pub/Sub ordering](https://docs.cloud.google.com/pubsub/docs/ordering)

## Freshness and write visibility

### Pinecone freshness guide

Pinecone explicitly documents checking data freshness, which is important because vector-store write acknowledgement and query visibility may not be identical. This concept generalizes across managed vector services.

Source:

- [Pinecone freshness](https://docs.pinecone.io/guides/index-data/check-data-freshness)

## Multi-tenancy docs

### Pinecone namespaces

Pinecone's multi-tenancy docs make namespaces the central primitive for tenant isolation in a shared index design.

Source:

- [Pinecone multitenancy](https://docs.pinecone.io/guides/index-data/implement-multitenancy)

### Weaviate multi-tenancy

Weaviate provides first-class multi-tenancy at the collection level, which is useful for SaaS-style systems with many tenant partitions.

Source:

- [Weaviate multitenancy](https://docs.weaviate.io/weaviate/manage-collections/multi-tenancy)

### Milvus multi-tenancy

Milvus documents several multi-tenancy approaches, including database/collection/partition-level organization. This is useful when mapping isolation strength to cost and complexity.

Source:

- [Milvus multitenancy](https://milvus.io/docs/multi_tenancy.md)

### Redis ACLs

Redis ACL documentation is relevant when Redis is used for vector search, caching, or agent memory and tenant/user-level access must be controlled.

Source:

- [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/)

### Azure RBAC and Vertex IAM

Azure AI Search and Vertex AI Vector Search inherit much of their tenancy and access model from their cloud IAM systems.

Sources:

- [Azure Search RBAC](https://learn.microsoft.com/en-us/azure/search/search-security-rbac)
- [Vertex IAM vectorsearch roles](https://docs.cloud.google.com/iam/docs/roles-permissions/vectorsearch)

## Deletes, tombstones, and compaction

### Weaviate vector index config

Weaviate's vector index configuration exposes cleanup/tombstone-related controls. This is a useful example of why delete-heavy workloads need operational monitoring.

Source:

- [Weaviate vector index config](https://docs.weaviate.io/weaviate/config-refs/indexing/vector-index)

### Milvus release notes and compaction

Milvus release notes mention compaction improvements such as L0 compaction. Milvus-style architectures make compaction an important part of delete-heavy operations.

Source:

- [Milvus release notes](https://milvus.io/docs/v2.4.x/release_notes.md)

### Elastic disk usage and Lucene-style segment cleanup

Elastic's disk usage guidance is relevant because deletes in search engines are often reclaimed through background segment merges rather than immediate physical deletion.

Source:

- [Elastic disk usage](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/disk-usage)

### LanceDB update/delete and table versioning

LanceDB docs on update/delete and table versioning are relevant to object-store/table-oriented vector workflows.

Sources:

- [LanceDB updates](https://docs.lancedb.com/tables/update)
- [LanceDB versioning](https://docs.lancedb.com/tables/versioning)

## Blue-green and index versioning

### Elastic aliases

Elastic aliases are a canonical search-engine mechanism for blue-green index swaps.

Source:

- [Elastic aliases](https://www.elastic.co/docs/manage-data/data-store/aliases)

### OpenSearch aliases

OpenSearch index aliases support similar blue-green routing patterns.

Source:

- [OpenSearch aliases](https://docs.opensearch.org/latest/im-plugin/index-alias/)

### Azure Search aliases

Azure AI Search aliases are useful for pointing applications at a logical index while swapping physical index versions underneath.

Source:

- [Azure Search aliases](https://learn.microsoft.com/en-us/azure/search/search-how-to-alias)

### Weaviate collection aliases

Weaviate collection aliases support logical routing across physical collections.

Source:

- [Weaviate aliases](https://docs.weaviate.io/weaviate/manage-collections/collection-aliases)

### Vespa reindexing

Vespa's reindexing docs are relevant for systems where schema and ranking application changes are managed through Vespa's deployment/reindex model rather than simple index aliases.

Source:

- [Vespa reindexing](https://docs.vespa.ai/en/operations/reindexing.html)

### Vertex update/rebuild docs

Vertex AI Vector Search update/rebuild docs are important for understanding batch/stream update modes and when rebuilds are needed.

Source:

- [Vertex update/rebuild index](https://docs.cloud.google.com/vertex-ai/docs/vector-search/update-rebuild-index)

## Co-located operational stores

### pgvector

pgvector is relevant when vector search should live inside PostgreSQL and inherit relational transactions, roles, schemas, and operational tooling.

Source:

- [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md)

### MongoDB Atlas Vector Search and change streams

MongoDB Atlas Vector Search is relevant when vectors live beside JSON documents, and MongoDB change streams can drive downstream freshness and cache invalidation.

Sources:

- [MongoDB Vector Search](https://www.mongodb.com/docs/vector-search/)
- [MongoDB change streams](https://www.mongodb.com/docs/manual/changestreams/)

## Practical synthesis: when to use which operational pattern

| Pattern | Best supporting sources | Use when |
|---|---|---|
| CDC streaming | Debezium, Kafka, Pub/Sub | Need low-lag updates/deletes from transactional systems. |
| Batch import + blue-green | Elastic/OpenSearch/Azure aliases, Vertex rebuild docs | Need large rebuilds, model upgrades, or cheap periodic refresh. |
| Namespace tenancy | Pinecone, Weaviate | Many small tenants need cheap logical separation. |
| Separate index/cluster tenancy | Milvus, Elastic/OpenSearch, cloud IAM docs | Regulated/noisy/large tenants require blast-radius isolation. |
| Tombstone-first deletes | Weaviate config, Milvus compaction, Elastic disk usage | Deletes must be query-hidden quickly and physically cleaned later. |
| Co-located vectors | pgvector, MongoDB Atlas | Read-after-write, transactions, or operational-data co-location matters. |
| Table/index versioning | LanceDB, Elastic aliases, Azure aliases, Weaviate aliases | Need reproducible rebuilds and rollback. |

## Full source list

- [Debezium features](https://debezium.io/documentation/reference/stable/features.html)
- [Debezium PostgreSQL connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [Kafka delivery semantics](https://docs.confluent.io/kafka/design/delivery-semantics.html)
- [Google Pub/Sub exactly once](https://docs.cloud.google.com/pubsub/docs/exactly-once-delivery)
- [Google Pub/Sub ordering](https://docs.cloud.google.com/pubsub/docs/ordering)
- [Pinecone freshness](https://docs.pinecone.io/guides/index-data/check-data-freshness)
- [Pinecone multitenancy](https://docs.pinecone.io/guides/index-data/implement-multitenancy)
- [Pinecone indexing overview](https://docs.pinecone.io/guides/index-data/indexing-overview)
- [Weaviate multitenancy](https://docs.weaviate.io/weaviate/manage-collections/multi-tenancy)
- [Weaviate aliases](https://docs.weaviate.io/weaviate/manage-collections/collection-aliases)
- [Weaviate vector index config](https://docs.weaviate.io/weaviate/config-refs/indexing/vector-index)
- [Milvus multitenancy](https://milvus.io/docs/multi_tenancy.md)
- [Milvus release notes](https://milvus.io/docs/v2.4.x/release_notes.md)
- [Qdrant distributed deployment](https://qdrant.tech/documentation/distributed_deployment/)
- [Qdrant fundamentals](https://qdrant.tech/documentation/faq/qdrant-fundamentals/)
- [Qdrant production article](https://qdrant.tech/articles/vector-search-production/)
- [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md)
- [Elastic aliases](https://www.elastic.co/docs/manage-data/data-store/aliases)
- [Elastic disk usage](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/disk-usage)
- [Elastic search application security](https://www.elastic.co/docs/solutions/elasticsearch-solution-project/search-applications/search-application-security)
- [OpenSearch aliases](https://docs.opensearch.org/latest/im-plugin/index-alias/)
- [Vespa reindexing](https://docs.vespa.ai/en/operations/reindexing.html)
- [LanceDB updates](https://docs.lancedb.com/tables/update)
- [LanceDB versioning](https://docs.lancedb.com/tables/versioning)
- [Chroma architecture](https://docs.trychroma.com/reference/architecture/overview)
- [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/)
- [MongoDB change streams](https://www.mongodb.com/docs/manual/changestreams/)
- [MongoDB Vector Search](https://www.mongodb.com/docs/vector-search/)
- [Vertex IAM vectorsearch roles](https://docs.cloud.google.com/iam/docs/roles-permissions/vectorsearch)
- [Vertex update/rebuild index](https://docs.cloud.google.com/vertex-ai/docs/vector-search/update-rebuild-index)
- [Azure Search aliases](https://learn.microsoft.com/en-us/azure/search/search-how-to-alias)
- [Azure Search RBAC](https://learn.microsoft.com/en-us/azure/search/search-security-rbac)
