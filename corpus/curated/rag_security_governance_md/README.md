# RAG Security & Governance Markdown Bundle

Generated: **2026-05-19**

This bundle covers the security and governance layer that is often missing from RAG architecture reviews: encryption/KMS, RBAC and permission-aware retrieval, PII handling, audit/lineage, GDPR erasure in ANN/HNSW indexes, and indirect prompt injection / poisoned retrieval.

## Files

| File | Purpose |
|---|---|
| `00_executive_summary.md` | Top-level conclusions, decision matrix, and architecture priorities. |
| `01_encryption_kms_architectures.md` | Encryption at rest/in transit, KMS, envelope encryption, tenant keying, rotation, BYOK/HYOK. |
| `02_rbac_permission_aware_retrieval.md` | ACL propagation, tenant isolation, metadata filters, namespaces, RBAC-aware vector search, failure modes. |
| `03_pii_detection_redaction_and_log_hygiene.md` | PII detection/redaction across ingestion, embeddings, prompts, outputs, and observability logs. |
| `04_audit_lineage_and_logging.md` | End-to-end audit, retrieval provenance, lineage, tamper-evidence, retention, and evidence models. |
| `05_gdpr_erasure_in_ann_indexes.md` | Right-to-erasure in vector systems, HNSW deletion problems, tombstones, rebuilds, crypto-erasure. |
| `06_poisoned_retrieval_and_prompt_injection.md` | Indirect prompt injection, poisoned retrieval, GraphRAG poisoning, and layered mitigations. |
| `07_implementation_playbook.md` | Practical rollout plan, reference architecture, tests, policy gates, and operational checklists. |
| `08_interview_question_checklist.md` | Interview-ready questions and what strong answers sound like. |
| `09_references_and_source_map.md` | Consolidated references grouped by topic. |
| `FULL_REPORT.md` | Concatenated single-file version of the bundle. |

## How to use this bundle

Use the files as modular briefing notes. For interview prep, start with `00_executive_summary.md`, then `02_rbac_permission_aware_retrieval.md`, `05_gdpr_erasure_in_ann_indexes.md`, and `06_poisoned_retrieval_and_prompt_injection.md`. Those three sections tend to produce the most differentiated answers because they deal with problems that are specific to RAG and vector databases rather than generic cloud security.
