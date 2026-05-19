# Domain Profile — Financial / Banking

**Scope:** retail/commercial banking knowledge, regulatory & policy retrieval, transaction/account Q&A, financial research and advisory support. **Not** open consumer fintech marketing chat (lower-stakes profile).

**Defining attributes:** A4 sectoral (PCI-DSS / regional banking regulation) · A11 mandatory · A2 high. The combination of regulator-facing auditability and exact identifiers is what makes this profile distinct from generic enterprise knowledge.

## Prior vector

| Attr | Prior | Confidence | Why |
|---|---|---|---|
| A1 cost of wrong | catastrophic | strong | Wrong financial/regulatory answers carry monetary and legal liability. Forces grounding, citations, abstention, reranking. |
| A2 exact-match | high | strong | Account numbers, transaction IDs, regulatory clause references, product codes are token-exact. Hybrid mandatory. |
| A3 query complexity | synthetic | elicit | Policy interpretation is multi-hop; balance/lookup is not. Confirm. |
| A4 compliance | sectoral (PCI-DSS, banking regs, often data-residency) | strong | Frequently forces in-region, in-VPC processing; external egress often disallowed. |
| A5 sensitivity | regulated-personal (financial PII) | strong | Redaction, permission-aware retrieval, strict tenant isolation. |
| A6 corpus structure | tabular + long policy/regulatory documents | elicit | Statements/ledgers vs policy PDFs change parsing — confirm the mix. |
| A7 freshness | periodic, fast-moving for regulatory feeds | elicit | Product terms vs regulatory updates differ — confirm which dominates. |
| A8 latency | strict for customer-facing, relaxed for analyst tools | elicit | High variance; never assume. |
| A9 multilinguality | monolingual | elicit | Global banks are multilingual; regional ones often not. |
| A10 jargon drift | moderate-jargon | strong | Financial terminology drifts from general text but less than clinical/legal — moderate embedding adaptation. |
| A11 auditability | mandatory | strong | Regulator-facing; every answer must be traceable to source policy/clause. |
| A12 human-in-loop | gated for advisory, advisory for internal lookup | elicit | Depends on whether output is acted on financially — confirm. |

## Resulting pipeline lean
Hybrid candidate generation → rerank → grounded generation with mandatory citations to specific policy/clause → abstention on out-of-policy questions → review gate where output drives financial action. Tenant isolation enforced at retrieval.

## Deployment & security posture
In-region/in-VPC processing with data-residency controls; encryption + KMS; strict multi-tenant isolation (separate index or row-level, not just metadata filter); financial-PII redaction; immutable audit/decision log for regulator inspection.

## Canonical failure modes
- Metadata-filter-only multi-tenancy → cross-tenant leakage of financial records.
- Answer without clause-level citation → fails regulator audit even if correct.
- Ignoring data residency → unshippable in regulated jurisdictions.
- Dense-only retrieval missing an exact regulatory clause reference.

## Router must still elicit
A3, A6, A7, A8, A9, A12 — banking spans customer-facing, internal, and analyst use with very different requirements; the prior fixes only the regulatory/precision spine.
