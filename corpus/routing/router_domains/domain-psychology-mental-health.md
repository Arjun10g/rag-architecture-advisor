# Domain Profile — Psychology / Mental Health

**Scope:** clinical psychology literature retrieval, therapeutic-modality reference, practitioner-facing knowledge support, research synthesis. **Critical boundary:** this profile is for *practitioner/research support*, **not** an end-user-facing mental-health chatbot giving advice to people in distress — that is out of scope for this advisor and the router should abstain on it (see router decision logic, abstention).

**Defining attributes:** A1 catastrophic (via misapplied clinical guidance) · A10 far-jargon · A3 synthetic. Distinct from medical/clinical in that the corpus is narrative/literature-heavy rather than coded records, so A2 is lower and A6 differs.

## Prior vector

| Attr | Prior | Confidence | Why |
|---|---|---|---|
| A1 cost of wrong | catastrophic | strong | Misapplied therapeutic/diagnostic guidance can cause real harm even practitioner-mediated. Grounding, citations, abstention, confidence gating. |
| A2 exact-match | moderate | strong | DSM/ICD codes and instrument names matter, but reasoning is more conceptual than identifier-exact → hybrid still advised but lexical weight lower than medical/banking. |
| A3 query complexity | synthetic | strong | Questions synthesize across modalities, evidence bases, populations — multi-hop/synthetic by nature. Favors adaptive retrieval if latency allows. |
| A4 compliance | privacy → sectoral if patient data present | elicit | Literature-only: privacy-tier. Anything touching patient/case data: sectoral (HIPAA-equivalent). Confirm presence of patient data — this is the pivotal question. |
| A5 sensitivity | public (literature) → regulated-personal (case data) | elicit | Same pivot as A4; drives redaction and egress rules. |
| A6 corpus structure | narrative prose + long hierarchical literature | strong | Recursive/sentence-window + parent-child chunking; not record-structured. |
| A7 freshness | periodic | strong | Evidence bases evolve over years, not days. |
| A8 latency | relaxed | strong | Practitioner research/reference use is rarely point-of-care interactive. |
| A9 multilinguality | monolingual | elicit | Often English literature; international practice may differ. |
| A10 jargon drift | far-jargon | strong | Clinical-psych terminology is far from general text → instruction/domain-adapted embeddings. |
| A11 auditability | mandatory | strong | Evidence-based practice requires every claim traceable to its study/guideline. |
| A12 human-in-loop | gated | strong | A practitioner must always mediate; the system supports judgement, never replaces it — pipeline ends in practitioner-facing evidence presentation, not autonomous answer. |

## Resulting pipeline lean
Hybrid (moderate lexical weight) → domain-adapted embeddings → rerank → grounded synthesis with mandatory study/guideline citations and strong abstention → practitioner-mediated presentation. Adaptive/multi-hop retrieval favored (A3 strong, A8 relaxed — the conflict triad does not bind here, so quality can be maximized).

## Deployment & security posture
Literature-only: external LLM API acceptable, light audit. Case-data present: in-VPC/open-weights, redaction, permission-aware retrieval, full audit — i.e. it collapses toward the medical/clinical posture. The A4/A5 pivot is the single most consequential elicitation in this domain.

## Canonical failure modes
- The scope boundary failure: answering as if it were an end-user therapy chatbot — must abstain.
- No abstention → confident synthesis on thin/contested evidence (common in psychology literature).
- Treating contested findings as settled — the corpus must carry the contested-vs-consensus tag and the answer must reflect it.
- Generic embeddings conflating distinct therapeutic constructs that are linguistically similar.

## Router must still elicit
A4, A5, A9 — and explicitly confirm the scope boundary (practitioner/research support vs end-user advice) before proceeding at all.
