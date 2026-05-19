# Domain Profile — TEMPLATE

Copy this file to `domain-<name>.md` and fill it in. The template enforces the contract the router depends on: every card must supply a prior + confidence for all twelve attributes, name its defining attributes, and list its failure modes. A card that asserts `strong` on an attribute that actually varies within the domain is a bug — when unsure, mark `elicit`.

**Scope:** one or two sentences. State explicitly what is IN and what is OUT (the out-of-scope boundary is as important as the in-scope definition — see psychology card for why).

**Defining attributes:** the 2–3 attributes whose levels make this domain *this* domain. If a case lacks these, domain detection probably mis-fired.

## Prior vector

| Attr | Prior | Confidence | Why |
|---|---|---|---|
| A1 cost of wrong | tolerable / costly / catastrophic | strong / elicit | one-line justification |
| A2 exact-match | low / moderate / high | strong / elicit | |
| A3 query complexity | lookup / synthetic / multi-hop | strong / elicit | |
| A4 compliance | none / privacy / sectoral | strong / elicit | |
| A5 sensitivity | public / internal / regulated-personal | strong / elicit | |
| A6 corpus structure | prose / hierarchical / records / code / tabular / mixed | strong / elicit | |
| A7 freshness | static / periodic / fast-moving | strong / elicit | |
| A8 latency | strict / moderate / relaxed | strong / elicit | |
| A9 multilinguality | monolingual / cross-lingual / multilingual | strong / elicit | |
| A10 jargon drift | near-general / moderate-jargon / far-jargon | strong / elicit | |
| A11 auditability | none / recommended / mandatory | strong / elicit | |
| A12 human-in-loop | none / advisory / gated | strong / elicit | |

**Confidence rule:** `strong` = this attribute almost never varies within the domain, safe as a default. `elicit` = high within-domain variance, the router MUST confirm it in Stage 3. Bias toward `elicit` when unsure; a wrong `strong` prior silently produces a wrong pipeline.

## Resulting pipeline lean
One paragraph: the topology shape and key components that the strong priors imply. Note which choices are contingent on `elicit` attributes.

## Deployment & security posture
One paragraph: what A4/A5/A11/A12 imply for the deployment diagram (egress, encryption, isolation, audit, review).

## Canonical failure modes
Bullet list of the specific, named ways pipelines fail in THIS domain. This feeds the strengths/weaknesses panel directly — collect these deliberately (postmortems, anti-patterns), they do not fall out of how-to content.

## Router must still elicit
List the `elicit` attributes and the single pivotal question that most changes this domain's recommendation. Every card should be able to name its one most consequential elicitation.
