# Routing Attribute Taxonomy

**Role in system:** This is the spine the router reasons over. The router never maps a domain directly to a pipeline. It maps the user's situation onto these orthogonal attributes, and the attributes — not the domain label — drive the recommended pipeline and deployment. Domain profile cards exist only to supply *prior* values for these attributes, which stated user specifics override.

**How to read each attribute:** every attribute has discrete levels; each level carries a concrete pipeline effect and a concrete deployment/security effect, plus the failure mode that occurs if it is set wrong, plus the guide-corpus area that grounds the rule.

---

## A1. Cost of a wrong/hallucinated answer
*How damaging is a confident-but-wrong answer?*

- **Levels:** tolerable · costly · catastrophic
- **Pipeline effect:** higher cost → mandatory grounding prompt, mandatory citations, abstention path, reranking to raise precision, and at `catastrophic` a confidence gate / human-in-the-loop review stage.
- **Deployment effect:** at `catastrophic`, answer logging + traceability become non-optional; review queue infrastructure appears in the deployment diagram.
- **Failure if mis-set:** set too low for a high-stakes domain → the system answers when it should abstain (the single most dangerous error).
- **Grounded by:** context construction & abstention; evaluation (faithfulness).

## A2. Exact-match / terminology dependence
*Do answers hinge on precise tokens — codes, identifiers, statute numbers, API symbols, drug names?*

- **Levels:** low · moderate · high
- **Pipeline effect:** `high` mandates lexical or hybrid retrieval (BM25/SPLADE in the candidate stage); dense-only is disqualified regardless of other attributes.
- **Deployment effect:** a lexical index component appears alongside the vector store (extra storage + a second query path).
- **Failure if mis-set:** dense-only on an identifier-heavy corpus silently misses exact matches — a recall failure that does not show up in casual testing.
- **Grounded by:** embedding model choices; matching strategies.

## A3. Query complexity / multi-hop reasoning
*Are answers single-fact lookups, or do they require chaining across multiple sources?*

- **Levels:** lookup · synthetic · multi-hop
- **Pipeline effect:** `lookup` → single-stage is acceptable. `synthetic`/`multi-hop` → adaptive/agentic retrieval, query decomposition, iterative retrieval; consider GraphRAG when relationships matter.
- **Deployment effect:** adaptive loops raise tail latency and token cost — flows into the scalability/cost reasoning.
- **Failure if mis-set:** forcing single-stage on multi-hop queries → partial-evidence answers that read fluent but are incomplete.
- **Grounded by:** retrieval pipelines; adaptive retrieval (Self-RAG/CRAG/FLARE).

## A4. Regulatory / compliance regime
*What legal regime governs the data and the answers?*

- **Levels:** none · privacy (GDPR/CCPA) · sectoral (HIPAA/PCI-DSS/GxP/FERPA/legal privilege)
- **Pipeline effect:** at `sectoral`, an external LLM API may be disallowed → in-VPC / open-weights generation becomes a hard constraint that overrides quality-based model choice.
- **Deployment effect:** drives encryption + KMS, access control, audit logging, data residency, right-to-erasure handling, tenant isolation. This is the dominant *deployment*-side attribute.
- **Failure if mis-set:** under-set → a design that is technically good and legally unshippable.
- **Grounded by:** security & governance; cloud platform mapping.

## A5. Data sensitivity / confidentiality
*How sensitive is the corpus and the query content (PII/PHI/financial/privileged)?*

- **Levels:** public · internal · regulated-personal
- **Pipeline effect:** `regulated-personal` → PII/PHI redaction before indexing and before prompting; permission-aware retrieval (document ACLs propagated into the index).
- **Deployment effect:** secrets management, no-train guarantees on any external model, log scrubbing.
- **Failure if mis-set:** PII leaks via retrieved context into prompts/logs — a breach class the report's base material does not cover.
- **Grounded by:** security & governance; operations (multi-tenancy).

## A6. Corpus structure & modality
*What shape is the source material?*

- **Levels:** narrative prose · long hierarchical documents · semi-structured records · code · tabular · mixed
- **Pipeline effect:** drives chunking and parsing — recursive/sentence-window for prose, parent-child for long hierarchical docs, AST-aware for code, layout-aware for tables/PDFs.
- **Deployment effect:** heavy parsing (PDF layout, OCR) adds an ingestion-compute component.
- **Failure if mis-set:** naive fixed-size chunking on hierarchical or code corpora destroys retrievable units.
- **Grounded by:** chunking & parsing strategies.

## A7. Corpus volatility / freshness need
*How fast does ground truth change, and how stale an answer is acceptable?*

- **Levels:** static · periodic · fast-moving
- **Pipeline effect:** `fast-moving` → versioned chunks, recency-aware retrieval, possibly metadata-filtered to current version.
- **Deployment effect:** sets reindex cadence, incremental-ingestion/CDC, tombstones, blue-green reindex, freshness SLA.
- **Failure if mis-set:** stale answers presented with full confidence (acute in fast-moving technical and regulatory corpora).
- **Grounded by:** operations & freshness.

## A8. Latency tolerance
*What response-time budget does the use context allow?*

- **Levels:** strict (interactive/point-of-use) · moderate · relaxed (batch/research)
- **Pipeline effect:** `strict` caps the number of pipeline stages; reranking included only if A1 (cost of wrong answer) overrides; adaptive loops disallowed.
- **Deployment effect:** drives caching layers, dynamic batching, and GPU vs CPU for the rerank/generate stages.
- **Failure if mis-set:** a quality-maximal pipeline that violates the interaction budget and is abandoned by users.
- **Grounded by:** retrieval pipelines (latency budget); operations.

## A9. Multilinguality
*One language, or many — in corpus and/or queries?*

- **Levels:** monolingual · cross-lingual · multilingual
- **Pipeline effect:** constrains embedding model to multilingual-capable options; may force a multilingual reranker.
- **Deployment effect:** minor; model-size/cost only.
- **Failure if mis-set:** a strong monolingual embedding model chosen for a multilingual corpus → silent cross-language recall collapse.
- **Grounded by:** embedding model choices.

## A10. Domain-language drift from general text
*How far is the domain vocabulary from general web/Wikipedia text the base models were trained on?*

- **Levels:** near-general · moderate-jargon · far-jargon (clinical/legal/scientific)
- **Pipeline effect:** `far-jargon` → favor instruction-tuned or domain-adapted embeddings; raise hybrid weight on lexical; consider domain-tuned reranker.
- **Deployment effect:** possible fine-tuned-embedding hosting (a model-serving component).
- **Failure if mis-set:** generic embeddings on far-jargon corpora → semantically "close" but clinically/legally wrong neighbors.
- **Grounded by:** embedding model choices; reranking.

## A11. Auditability / explainability requirement
*Must every answer be traceable to its evidence for accountability or regulators?*

- **Levels:** none · recommended · mandatory
- **Pipeline effect:** `mandatory` → citations enforced, retrieval+decision logged, deterministic-where-possible selection.
- **Deployment effect:** decision/audit log store and lineage tracking appear in the deployment diagram.
- **Failure if mis-set:** an unauditable pipeline in a domain that is legally required to explain itself.
- **Grounded by:** security & governance; evaluation.

## A12. Human-in-the-loop expectation
*Is a human expected to review or sign off before an answer is acted on?*

- **Levels:** none · advisory · gated
- **Pipeline effect:** `gated` → the recommended pipeline ends in a confidence-scored review stage rather than direct answer delivery.
- **Deployment effect:** review-queue + feedback-capture infrastructure.
- **Failure if mis-set:** autonomous answering in a domain where unreviewed answers cause real-world harm.
- **Grounded by:** evaluation; operations.

---

## Orthogonality note

These twelve are deliberately chosen to be as independent as possible so a domain prior can set some while the user freely overrides others without contradiction. Two attributes correlate strongly in practice — A4 (compliance) and A5 (sensitivity), and A1 (cost of wrong answer) and A11 (auditability) — but they are kept separate because real cases decouple them (public data under strict compliance; high-stakes answers with no audit requirement). The router treats all twelve independently and resolves conflicts explicitly (see router decision logic).
