# Interview Question Checklist — RAG Security & Governance

## 1. How would you enforce permissions in RAG?

Strong answer:

> “I would not rely on the LLM or similarity search for authorization. I would propagate source ACLs into chunk metadata, normalize them into tenant/group/project/role labels, use a policy engine to compute authorized filters at query time, pre-filter retrieval, and then post-check every retrieved chunk before prompt construction. I would log the policy snapshot and ACL version for audit.”

Follow-up details to mention:

- avoid huge user-ID filters;
- use namespaces/indexes for tenant isolation;
- reconcile ACL drift;
- run canary authorization tests.

## 2. Why is post-filtering alone risky?

Strong answer:

> “Post-filtering can collapse recall because the top-k may be filled with unauthorized chunks. It also risks leaking unauthorized candidates into logs, traces, or prompts if implemented incorrectly. I would use it as a second guardrail, but not as the only security boundary.”

## 3. How would you handle GDPR erasure in a vector DB?

Strong answer:

> “I would maintain lineage from source document/data subject to chunks, embeddings, index IDs, prompt traces, caches, and evaluation datasets. On erasure, I would tombstone immediately to suppress retrieval, delete vectors and payloads, purge caches/logs where allowed, and schedule index compaction or blue-green rebuild. For HNSW, I would not assume mark-deleted equals physical erasure.”

## 4. What is the role of KMS in RAG?

Strong answer:

> “KMS should protect every derived artifact, not just the source documents. I would use envelope encryption with customer-managed keys for parsed text, chunks, vector indexes, snapshots, prompt traces, and logs. For tenant-sensitive systems I would use tenant-scoped keys and store key IDs/versions in lineage.”

## 5. Are embeddings PII?

Strong answer:

> “They can be. Embeddings generated from personal data are derived artifacts that may preserve sensitive semantics. I would treat them as controlled data, encrypt and access-control them, avoid embedding raw high-risk identifiers, and preserve lineage for deletion.”

## 6. How do you defend against indirect prompt injection?

Strong answer:

> “Treat retrieved documents as untrusted data. Delimit context, instruct the model not to follow retrieved instructions, scan for injection patterns, use source trust scoring, require corroboration for high-risk claims, verify citations, and enforce tool permissions outside the model.”

## 7. What audit data should a RAG system keep?

Strong answer:

> “For each answer: user, tenant, policy version, query hash, allowed filters, retrieved chunk IDs, source versions, model and prompt versions, citation map, verifier result, and response hash. I would avoid full prompt logging by default and use redacted/encrypted break-glass traces for incidents.”

## 8. How would you evaluate a vendor’s vector DB for secure RAG?

Ask:

- How does metadata filtering interact with ANN search?
- Are namespaces physically isolated?
- Can filters scale to group/RBAC predicates?
- How are deletes represented internally?
- Is compaction/rebuild available?
- Are snapshots encrypted with customer-managed keys?
- Are audit logs available for query filters and returned IDs?
- Can data be deleted by document ID, tenant ID, and metadata predicate?

## 9. What are the most common RAG security anti-patterns?

- Shared index with no tenant filtering.
- User-level ACL lists embedded in every chunk.
- Post-filter-only authorization.
- Full prompt logging in production.
- No lineage from source to embedding.
- No deletion plan for ANN indexes.
- Treating retrieved text as trusted instruction.
- Using external model APIs without data-retention review.
- Caching answers without source/permission invalidation.
- Ignoring backups and evaluation datasets in erasure workflows.

## 10. One-sentence summary

> “Secure RAG means carrying encryption, ACLs, privacy classification, lineage, and deletion semantics from the source document into every derived chunk, vector, prompt, answer, cache, and log — while treating retrieved content as untrusted input.”

---

## Source note

See `09_references_and_source_map.md` for the full source map. Key sources for this section include vendor documentation and papers listed there.
