# 06 — Caching and Invalidation for Vector Retrieval

## Why caching is dangerous in RAG

Caching can dramatically reduce cost and latency, but it is also one of the easiest ways to serve stale or unauthorized content. In vector search, cache correctness depends on more than the query text. It depends on:

- tenant;
- authenticated user or ACL policy;
- query normalization;
- embedding model version;
- index version;
- vector store namespace;
- metadata filters;
- top-k and rerank depth;
- reranker model version;
- prompt/citation policy;
- freshness requirements.

A cache key that ignores any of these can serve incorrect results.

## Cache layers

| Cache | What it stores | Primary benefit | Primary risk |
|---|---|---|---|
| Embedding cache | Text → embedding vector. | Avoids repeated embedding cost. | Stale if model/version changes; privacy risk. |
| Query embedding cache | Normalized query → query vector. | Lowers query latency. | User-specific query leakage if not scoped. |
| Semantic cache | Similar prior query → answer or retrieval plan. | Avoids retrieval/generation for repeated intents. | Hallucinated/stale answers; hard invalidation. |
| Result cache | Query+filters → retrieved doc IDs/chunks. | Faster retrieval pipeline. | Stale docs, ACL leakage. |
| Reranker cache | Query+candidate IDs → reranked order. | Saves reranker cost. | Invalid after candidate/document changes. |
| Generation cache | Query+context+prompt → answer. | Saves LLM cost. | Highest stale/hallucination/security risk. |

## Embedding cache

Use an embedding cache keyed by normalized text and model version:

```text
embedding_cache_key = sha256(
  normalized_text +
  embedding_model_name +
  embedding_model_version +
  embedding_dim +
  text_normalizer_version
)
```

Good for:

- repeated chunks across documents;
- retries;
- backfills;
- duplicate content;
- reprocessing after non-content metadata changes.

Avoid or encrypt when:

- queries contain sensitive personal data;
- tenant contracts prohibit cross-tenant caching;
- model provider terms constrain storage;
- text normalization could collapse distinct sensitive inputs.

For document embeddings, a global cache can be safe if keyed by content hash and model version, but many enterprise systems still scope cache by tenant for privacy and contractual simplicity.

## Query embedding cache

Query embedding cache is useful for high-QPS repeated queries. The key should include:

```text
tenant_id | user_or_acl_hash | normalized_query | embedding_model_version | query_rewrite_version
```

If query embeddings are not sensitive in your domain, you may use shorter TTLs and broader sharing. If queries can contain private data, scope by tenant/user and encrypt at rest.

## Result cache

A result cache stores retrieved IDs/chunks for a query. It must include every retrieval-affecting setting:

```text
result_cache_key = hash({
  tenant_id,
  acl_hash,
  normalized_query,
  query_embedding_model_version,
  index_version,
  namespace_or_collection,
  filters,
  top_k,
  hybrid_weights,
  reranker_version,
  retrieval_policy_version
})
```

TTL should be tied to freshness needs:

| Data type | Suggested TTL |
|---|---:|
| Static public docs | Hours to days. |
| Internal knowledge base | Minutes to hours. |
| Frequently edited tickets/docs | Seconds to minutes. |
| ACL-sensitive data | Very short or event-invalidated only. |
| Compliance-sensitive deletes | Immediate event invalidation; avoid long TTL. |

## Semantic cache

Semantic cache maps a new query to a similar previous query/answer. It is riskier than exact result caching because invalidation is fuzzy.

Use it when:

- domain is stable;
- answers are low-risk;
- sources change slowly;
- you can attach source/version provenance;
- cache entries expire aggressively.

Avoid it when:

- facts change often;
- user-specific ACLs matter;
- legal/medical/financial correctness is high-stakes;
- answers require current source citations;
- user queries contain private information.

Safer semantic-cache design:

```text
semantic_cache_entry:
  query_embedding
  answer
  cited_doc_ids
  cited_doc_versions
  index_version
  tenant_id
  acl_hash
  created_at
  ttl
```

Before serving, confirm cited docs and versions are still valid.

## Invalidation events

Every ingestion pipeline should publish invalidation events:

```json
{
  "event_type": "doc_upsert|doc_delete|acl_update|index_swap|model_upgrade|tenant_offboard",
  "tenant_id": "tenant_123",
  "source_doc_id": "doc_456",
  "chunk_ids": ["..."],
  "old_index_version": "v11",
  "new_index_version": "v12",
  "acl_hash_before": "...",
  "acl_hash_after": "...",
  "occurred_at": "2026-05-18T20:10:00Z"
}
```

Invalidation by event type:

| Event | Invalidate |
|---|---|
| Document content update | result cache entries containing doc/chunk; generation cache using doc; optionally semantic cache. |
| Document delete | all caches referencing doc/chunk; tenant-level emergency purge if uncertain. |
| ACL update | all result/generation/semantic caches for affected doc or users/roles. |
| Embedding model upgrade | query/document embedding caches for old model unless retained by version; result caches for old index. |
| Index alias swap | all result/reranker/generation caches unless key includes index version. |
| Tenant offboarding | all tenant-scoped caches, embeddings, and logs per policy. |

## Versioned keys beat mass invalidation

The safest invalidation method is versioned keys. If `index_version` is part of the key, an alias swap naturally misses old result caches. Old caches can expire asynchronously.

```text
result:v12:tenant_123:acl_abc:query_hash:filters_hash
```

Versioned keys are not enough for deletes if old entries are still directly accessible. For delete-sensitive data, actively purge by document and tenant too.

## Cache stampede controls

When a popular query expires, many requests may recompute it simultaneously.

Use:

- request coalescing/single-flight;
- stale-while-revalidate for low-risk data;
- jittered TTLs;
- negative caching for empty results;
- per-tenant cache quotas;
- background warming after blue-green swaps.

## Privacy and security

Caching can create hidden data retention. For enterprise RAG:

- include tenant and ACL hash in keys;
- encrypt cache storage;
- avoid cross-tenant semantic cache unless data is public;
- maintain cache purge APIs by tenant/document/user;
- log cache hits with provenance;
- never cache generated answers without cited document versions;
- set shorter TTLs for private data than public data.

## When to use which cache

| Workload | Recommended caching |
|---|---|
| Expensive embedding backfills | Document embedding cache keyed by content hash + model version. |
| High-QPS repeated queries | Query embedding cache + result cache. |
| Static public docs | Result and generation cache with long TTL. |
| Enterprise ACL-heavy RAG | Short TTL result cache; avoid broad semantic/generation cache. |
| Fast-changing tickets/support data | Embedding cache only; result cache with very short TTL or event invalidation. |
| Agent memory/session search | Redis-like short-lived scoped cache can be useful. |

## Sources

- [Kafka delivery semantics](https://docs.confluent.io/kafka/design/delivery-semantics.html)
- [Google Pub/Sub exactly once](https://docs.cloud.google.com/pubsub/docs/exactly-once-delivery)
- [Pinecone freshness](https://docs.pinecone.io/guides/index-data/check-data-freshness)
- [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/)
- [MongoDB change streams](https://www.mongodb.com/docs/manual/changestreams/)
- [Elastic search application security](https://www.elastic.co/docs/solutions/elasticsearch-solution-project/search-applications/search-application-security)
