# References and Source Map

This report uses a mix of primary vendor documentation, legal text references, and academic/industry security research. URLs were current during report creation on **2026-05-19**.

## Core governance, privacy, and encryption sources

1. **AWS KMS Developer Guide — AWS KMS keys and key hierarchy**  
   https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html  
   Used for customer-managed keys, AWS-managed keys, AWS-owned keys, CloudTrail auditability, key hierarchy, data keys, rotation, and customer key-control tradeoffs.

2. **GDPR Article 17 — Right to erasure / right to be forgotten**  
   https://gdpr-info.eu/art-17-gdpr/  
   Used for the legal requirement that drives erasure design, deletion workflows, propagation to processors, and audit evidence.

3. **Google Cloud Sensitive Data Protection — de-identifying sensitive data**  
   https://cloud.google.com/sensitive-data-protection/docs/deidentify-sensitive-data  
   Used for de-identification patterns, inspection, masking, replacement, and tokenization-style privacy controls.

4. **Microsoft Presidio documentation**  
   https://microsoft.github.io/presidio/  
   Used for open-source PII detection/anonymization pipeline design.

5. **NIST AI Risk Management Framework and Generative AI guidance**  
   https://www.nist.gov/itl/ai-risk-management-framework  
   https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf  
   Used for governance controls, risk measurement, documentation, human oversight, and model/system monitoring.

## Vector database, RBAC, and permission-aware retrieval sources

6. **Pinecone Docs — Implement multitenancy**  
   https://docs.pinecone.io/guides/index-data/implement-multitenancy  
   Used for namespace-per-tenant isolation, physical isolation, metadata-filter tradeoffs, query cost effects, and tenant offboarding.

7. **Weaviate Docs — RBAC overview**  
   https://docs.weaviate.io/weaviate/configuration/rbac  
   Used for role/permission/action/resource abstractions and vector-database RBAC.

8. **Qdrant Docs — Security / granular access control / TLS / audit logging**  
   https://qdrant.tech/documentation/operations/security/  
   Used for API keys, JWT granular access control, TLS, hardening, and audit logging concepts.

9. **Milvus Docs — RBAC explained**  
   https://milvus.io/docs/rbac.md  
   Used for collection/database/instance-level privilege models, privilege groups, and role-to-user assignment.

10. **Curator: Efficient Indexing for Multi-Tenant Vector Databases**  
    https://arxiv.org/abs/2401.07119  
    Used for the shared-index vs per-tenant-index tradeoff and filtered search costs in multi-tenant vector databases.

11. **HoneyBee: Efficient Role-based Access Control for Vector Databases via Dynamic Partitioning**  
    https://arxiv.org/abs/2505.01538  
    Used for RBAC-specific vector partitioning, role-based duplication, latency/storage tradeoffs, and access-control-aware indexing.

12. **ACORN: Performant and Predicate-Agnostic Search Over Vector Embeddings and Structured Data**  
    https://arxiv.org/abs/2403.04871  
    Used for predicate-aware HNSW traversal and the difficulty of hybrid vector + structured predicate search.

## HNSW deletion, erasure, and dynamic ANN sources

13. **hnswlib README — delete by mark_deleted and replace_deleted**  
    https://github.com/nmslib/hnswlib  
    Used for HNSW deletion semantics: marking deleted elements, omitting from search, replacement, and persistence caveats.

14. **FAISS Wiki — Special operations on indexes / remove_ids**  
    https://github.com/facebookresearch/faiss/wiki/Special-operations-on-indexes  
    Used for vector index deletion/removal behavior across index types.

15. **Enhancing HNSW Index for Real-Time Updates: Addressing Unreachable Points and Performance Degradation**  
    https://arxiv.org/abs/2407.07871  
    Used for the technical claim that HNSW and graph ANN indexes can degrade under long periods of deletion/update operations, including unreachable-point phenomena.

16. **Right to be Forgotten in the Era of Large Language Models**  
    https://arxiv.org/abs/2307.03941  
    Used for RTBF challenges in ML/LLM systems and solution families such as unlearning, editing, guardrails, and process controls.

## Prompt injection and poisoned retrieval sources

17. **OWASP Top 10 for LLM Applications 2025 — LLM01 Prompt Injection**  
    https://owasp.org/www-project-top-10-for-large-language-model-applications/  
    Used for prompt injection as a top LLM application risk and the distinction between direct/indirect injection.

18. **OWASP LLM Prompt Injection Prevention Cheat Sheet**  
    https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html  
    Used for practical prompt injection prevention, least privilege, output validation, and human-in-the-loop controls.

19. **Not what you’ve signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection**  
    https://arxiv.org/abs/2302.12173  
    Used for indirect prompt injection through retrieved/web/document content, data exfiltration, tool misuse, and remote attack surface.

20. **PoisonedRAG: Knowledge Corruption Attacks to Retrieval-Augmented Generation of Large Language Models**  
    https://arxiv.org/abs/2402.07867  
    Used for RAG-specific knowledge poisoning attacks and the empirical finding that small numbers of malicious texts can strongly manipulate RAG answers.

21. **Poisoned-MRAG: Knowledge Poisoning Attacks to Multimodal Retrieval Augmented Generation**  
    https://arxiv.org/abs/2503.06254  
    Used for multimodal poisoned retrieval risk.

22. **A Few Words Can Distort Graphs: Knowledge Poisoning Attacks on Graph-based RAG**  
    https://arxiv.org/abs/2508.04276  
    Used for GraphRAG-specific poisoning risks during graph construction.

## PII detection and privacy evaluation sources

23. **Enhancing the De-identification of Personally Identifiable Information in Educational Data**  
    https://arxiv.org/abs/2501.09765  
    Used for PII detection benchmark discussion and comparison against Presidio/Azure-style systems.

24. **Adaptive PII Mitigation Framework for Large Language Models**  
    https://arxiv.org/abs/2501.12465  
    Used for policy-aware PII masking, regulatory alignment, and context-sensitive risk scoring.

25. **Hardening x402: PII-Safe Agentic Payments via Pre-Execution Metadata Filtering**  
    https://arxiv.org/abs/2604.11430  
    Used as a recent example of low-latency pre-execution PII filtering in agentic systems.
