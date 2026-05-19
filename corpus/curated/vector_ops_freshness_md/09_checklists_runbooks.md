# 09 — Production Checklists and Runbooks

## Operational readiness checklist

### Identity and metadata

- [ ] Every vector has a stable `vector_id`.
- [ ] Every record has `tenant_id`.
- [ ] Every record has `source_doc_id` and `chunk_id`.
- [ ] Every record has `source_version` or `source_updated_at`.
- [ ] Every record has `embedding_model_version`.
- [ ] Every record has `chunker_version` and `parser_version`.
- [ ] Every record has `index_version`.
- [ ] Every record has `content_hash`.
- [ ] ACL metadata is versioned or hashable.

### Freshness

- [ ] Freshness SLO is defined.
- [ ] Source-to-CDC lag is measured.
- [ ] CDC-to-embedding lag is measured.
- [ ] Embedding queue backlog is measured.
- [ ] Vector write errors are alerted.
- [ ] Write-to-query-visible lag is measured with probes.
- [ ] Delete visibility lag is measured.
- [ ] Stale-hit rate is measured on sampled queries.

### Deletes

- [ ] Tombstone ledger exists outside vector DB.
- [ ] Delete-by-ID or delete-by-document manifest exists.
- [ ] Cache invalidation on delete is implemented.
- [ ] Deleted records are excluded from rebuilds.
- [ ] Physical compaction/cleanup policy is documented.
- [ ] Backup retention is documented.
- [ ] Tenant offboarding purge runbook exists.

### Reindexing and upgrades

- [ ] Index versioning convention exists.
- [ ] Blue-green or alias/router cutover exists.
- [ ] Rollback has been tested.
- [ ] Shadow evaluation exists.
- [ ] Canary routing exists for at least tenant-level or traffic-level rollout.
- [ ] Old index remains live during confidence window.
- [ ] Caches include index/model version.

### Multi-tenancy

- [ ] Tenant is derived from auth context, not user-provided filters.
- [ ] Cross-tenant leakage tests exist.
- [ ] Tenant delete/offboarding path exists.
- [ ] Noisy-tenant throttling exists.
- [ ] Tenant-level cost attribution exists.
- [ ] Regulated tenants have stronger isolation pattern.

### Caching

- [ ] Embedding cache includes model version.
- [ ] Result cache includes tenant, ACL hash, filters, top-k, index version, and retrieval policy version.
- [ ] Cache TTLs match freshness requirements.
- [ ] Event invalidation exists for deletes and ACL changes.
- [ ] Semantic/generation caches include cited document versions.
- [ ] Tenant purge deletes cache entries.

## Runbook: freshness lag incident

Symptoms:

- new documents not retrievable;
- old versions returned;
- freshness probe failing;
- CDC backlog growing;
- embedding queue stalled.

Steps:

1. Check source CDC connector health and source offset/LSN.
2. Check event log lag by partition/tenant.
3. Check dead-letter queue for poison documents.
4. Check embedding worker rate limits and failures.
5. Check vector DB write error rate and throttling.
6. Check write-to-query-visible probe.
7. Sample stale hits and compare `source_version` against source DB.
8. If backlog is large, prioritize deletes/ACL updates before normal upserts.
9. Communicate current freshness lag in user-visible terms.
10. After recovery, replay missed events from last known safe watermark.

## Runbook: delete leakage incident

Symptoms:

- deleted document appears in retrieval;
- revoked ACL still has access;
- cached answer cites deleted source.

Steps:

1. Classify severity: compliance/security versus normal stale data.
2. Add or verify tombstone in durable ledger.
3. Delete by known chunk IDs and source document metadata.
4. Invalidate caches by tenant/document/user/ACL hash.
5. Query all active index versions for the document ID.
6. Check blue/green old indexes and canary routes.
7. Confirm backup/retention obligations if hard deletion is required.
8. Add regression test for the leaked document/ACL path.
9. Audit whether stable IDs or random chunk IDs caused incomplete delete.

## Runbook: embedding model upgrade

Steps:

1. Define model, dimension, metric, and chunk/schema compatibility.
2. Create offline evaluation set.
3. Build vNext index/collection/table.
4. Backfill hot and representative data first.
5. Replay CDC from migration watermark.
6. Shadow queries and compare retrieval quality.
7. Canary low-risk tenants or small traffic slice.
8. Monitor latency, recall, stale-hit rate, and answer quality.
9. Swap alias/router.
10. Keep old index until rollback window expires.
11. Retire old caches and old index.

Rollback triggers:

- p95/p99 latency exceeds threshold;
- grounded answer quality drops;
- recall drops on critical query set;
- delete/ACL leakage appears;
- cost exceeds budget unexpectedly.

## Runbook: blue-green swap

Pre-swap:

- [ ] Green cardinality matches expected chunk count.
- [ ] Green CDC lag is zero or under threshold.
- [ ] Tombstone reconciliation passes.
- [ ] Tenant isolation tests pass.
- [ ] Cache versioning is ready.
- [ ] Rollback alias/router target is verified.

Swap:

1. Freeze index configuration changes.
2. Switch alias/router to green.
3. Purge or version-bypass result caches.
4. Run synthetic freshness/delete probes.
5. Watch dashboards for 30–120 minutes depending traffic.

Post-swap:

- [ ] Keep blue in read-only mode.
- [ ] Continue dual-write or replay if rollback requires blue freshness.
- [ ] Compare sampled results.
- [ ] Retire blue only after confidence window.

## Runbook: tenant migration from shared to dedicated

1. Add tenant routing-table entry for target dedicated index/cluster.
2. Snapshot tenant's source data.
3. Backfill dedicated target.
4. Replay tenant-specific CDC.
5. Validate document count, delete ledger, ACLs, and query quality.
6. Canary only that tenant.
7. Switch tenant route.
8. Monitor p99 latency and cost.
9. Delete tenant data from shared pool after retention/rollback window.
10. Invalidate tenant-scoped caches.

## Runbook: cache leakage or stale cache

1. Identify cache layer: embedding, result, reranker, semantic, generation.
2. Identify missing key dimension: tenant, ACL, index version, model version, filter, top_k, reranker version.
3. Purge affected tenant/user/document keys.
4. Disable risky cache layer if security-sensitive.
5. Add version/key fields and regression tests.
6. Re-enable with shorter TTL and monitoring.

## Dashboard metrics

| Category | Metrics |
|---|---|
| Ingestion | events/sec, lag, DLQ count, retry count, worker saturation. |
| Embedding | embeddings/sec, model latency, error rate, token/input size, cost. |
| Vector DB writes | upsert rate, delete rate, write latency, throttling, failed writes. |
| Freshness | source-to-visible lag, stale-hit rate, freshness probe success. |
| Deletes | delete-visible lag, tombstone count, tombstone age, compaction backlog. |
| Query | p50/p95/p99, recall probes, zero-result rate, filter selectivity. |
| Tenancy | per-tenant QPS, storage, latency, error rate, spend. |
| Cache | hit rate, stale hit reports, invalidation count, cache memory, evictions. |

## Sources

- [Debezium features](https://debezium.io/documentation/reference/stable/features.html)
- [Kafka delivery semantics](https://docs.confluent.io/kafka/design/delivery-semantics.html)
- [Pinecone freshness](https://docs.pinecone.io/guides/index-data/check-data-freshness)
- [Pinecone multitenancy](https://docs.pinecone.io/guides/index-data/implement-multitenancy)
- [Weaviate multitenancy](https://docs.weaviate.io/weaviate/manage-collections/multi-tenancy)
- [Elastic aliases](https://www.elastic.co/docs/manage-data/data-store/aliases)
- [OpenSearch aliases](https://docs.opensearch.org/latest/im-plugin/index-alias/)
- [Azure Search aliases](https://learn.microsoft.com/en-us/azure/search/search-how-to-alias)
- [Vespa reindexing](https://docs.vespa.ai/en/operations/reindexing.html)
- [MongoDB change streams](https://www.mongodb.com/docs/manual/changestreams/)
