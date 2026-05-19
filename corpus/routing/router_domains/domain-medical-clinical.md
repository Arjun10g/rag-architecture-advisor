# Domain Profile — Medical / Clinical

**Scope:** clinical decision support, patient-record Q&A, treatment-guideline retrieval, medical literature synthesis. **Not** consumer health chat (that is a different, lower-stakes profile).

**Defining attributes (what makes this domain this domain):** A1 catastrophic · A4 sectoral · A10 far-jargon. If a case does not have these three, it is probably not really the clinical profile — re-check domain detection.

## Prior vector

| Attr | Prior | Confidence | Why |
|---|---|---|---|
| A1 cost of wrong | catastrophic | strong | A confident-wrong clinical answer can cause direct patient harm. Forces grounding, citations, abstention, reranking, and a confidence gate. |
| A2 exact-match | high | strong | Drug names, dosages, ICD/SNOMED codes, contraindications are token-exact. Hybrid mandatory; dense-only disqualified. |
| A3 query complexity | synthetic | elicit | Differential reasoning is multi-hop; simple guideline lookup is not. Varies by product — confirm. |
| A4 compliance | sectoral (HIPAA / regional equivalents) | strong | Often forces in-VPC or open-weights generation; external API egress frequently disallowed. |
| A5 sensitivity | regulated-personal (PHI) | strong | Redaction before indexing and prompting; permission-aware retrieval. |
| A6 corpus structure | semi-structured records + long hierarchical guidelines | elicit | Records vs literature vs both changes chunking — confirm the mix. |
| A7 freshness | periodic | elicit | Guidelines update periodically; a live formulary is fast-moving — confirm. |
| A8 latency | strict if point-of-care, relaxed if research | elicit | High variance; this is the classic attribute to never assume for this domain. |
| A9 multilinguality | monolingual | elicit | Often single-language but international systems are not. |
| A10 jargon drift | far-jargon | strong | Clinical vocabulary is far from general text → domain-adapted/instruction embeddings, higher lexical weight, domain reranker. |
| A11 auditability | mandatory | strong | Clinical accountability requires evidence traceability for every answer. |
| A12 human-in-loop | gated | strong | Unreviewed clinical answers acting on patients is unacceptable; pipeline terminates in a review/confidence stage. |

## Resulting pipeline lean
Hybrid (dense + lexical) candidate generation → domain-adapted embeddings → cross-encoder rerank → grounded generation with mandatory citations and aggressive abstention → confidence-gated human review. Adaptive/multi-hop only if A3 confirms and A8 permits.

## Deployment & security posture
In-VPC or open-weights generation (no PHI egress); encryption + KMS; permission-aware retrieval with record-level ACLs; PHI redaction in ingestion and logs; full audit/lineage store; right-to-erasure handling in the index.

## Canonical failure modes (feed the weaknesses panel)
- Dense-only retrieval missing an exact contraindication or dose — silent and dangerous.
- External LLM API chosen for quality, ignoring PHI egress prohibition — unshippable.
- No abstention path → fluent wrong answers on out-of-corpus questions.
- Generic embeddings returning semantically near but clinically wrong neighbors.

## Router must still elicit (do not assume)
A3, A6, A7, A8, A9 — these genuinely vary across clinical products and wrong assumptions here produce wrong pipelines.
