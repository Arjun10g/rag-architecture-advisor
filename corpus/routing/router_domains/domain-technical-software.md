# Domain Profile — Technical / Software Engineering

**Scope:** developer documentation Q&A, internal engineering knowledge bases, API/SDK assistants, codebase and incident/runbook retrieval. **Not** general IT helpdesk for non-technical staff (different, lower-precision profile).

**Defining attributes:** A2 high · A6 code/mixed · A7 fast-moving. Exactness of symbols, code-shaped corpus, and rapid version churn together define this profile and separate it from generic enterprise knowledge.

## Prior vector

| Attr | Prior | Confidence | Why |
|---|---|---|---|
| A1 cost of wrong | costly | strong | A wrong API/config answer breaks builds and wastes engineer time — costly but rarely catastrophic; no human-life stakes. Grounding + citations; abstention recommended, gate not required. |
| A2 exact-match | high | strong | Function names, flags, error codes, version strings are token-exact. Hybrid mandatory; dense-only disqualified. |
| A3 query complexity | synthetic | elicit | "How do I configure X with Y" is multi-hop; single-symbol lookup is not. Confirm. |
| A4 compliance | none → privacy if internal proprietary code | elicit | Public docs: none. Proprietary internal code: confidentiality, possibly no external egress. Confirm. |
| A5 sensitivity | public for docs, internal for proprietary code | elicit | Drives whether external LLM APIs are permissible. |
| A6 corpus structure | code + markdown + mixed | strong | AST-aware/code-aware chunking; layout-aware for docs. Naive fixed-size chunking destroys code units. |
| A7 freshness | fast-moving | strong | Versioned APIs deprecate fast → version-tagged chunks, recency/version-filtered retrieval, frequent reindex. |
| A8 latency | strict (in-IDE/interactive) | elicit | Often interactive but batch doc-search exists — confirm. |
| A9 multilinguality | monolingual (English-dominant) | strong | Technical corpora are overwhelmingly English; rarely the constraint. |
| A10 jargon drift | moderate-jargon | strong | Technical terms drift moderately; code tokens benefit from lexical weight more than embedding adaptation. |
| A11 auditability | recommended | strong | Helpful for trust ("which doc/version said this") but not regulator-mandated. |
| A12 human-in-loop | none/advisory | strong | Engineers verify by running code; an autonomous advisory answer is acceptable. |

## Resulting pipeline lean
Hybrid (lexical-weighted) candidate generation → code/version-aware chunking → rerank → grounded generation with version-tagged citations → abstain on out-of-version questions. Frequent incremental reindex. Adaptive retrieval only if A3 confirms multi-hop config queries.

## Deployment & security posture
External LLM API generally acceptable for public docs; switch to in-VPC/open-weights if A5 resolves to proprietary code. Lightweight audit (source + version). Reindex pipeline is the operationally heavy component — versioned, incremental, blue-green.

## Canonical failure modes
- Stale answers citing deprecated APIs with full confidence — the dominant failure here (A7 mishandled).
- Dense-only retrieval missing exact symbol/flag matches.
- Fixed-size chunking splitting functions/config blocks into useless fragments.
- Treating proprietary code as public and sending it to an external API.

## Router must still elicit
A3, A4, A5, A8 — the public-docs vs proprietary-internal-code split changes compliance, sensitivity, and deployment substantially while leaving the precision/freshness spine intact.
