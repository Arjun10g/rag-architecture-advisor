# Router Decision Logic

**Role in system:** defines how the router turns a user's free-text situation into a complete, defensible requirement vector over the attribute taxonomy — which is then handed to the pipeline/deployment synthesizer. This is the orchestration showpiece; the value is in *how it reasons*, not in any lookup.

The router never outputs a pipeline. It outputs a **resolved requirement vector** (one level per attribute A1–A12) plus a **decision log** (per attribute: value, source, confidence, and whether a domain prior was overridden). The synthesizer consumes the vector; the decision log is what makes every downstream recommendation auditable and is itself a stated resume signal.

---

## Stage 1 — Domain detection

Three cases:

1. **Stated explicitly** ("we're a clinical documentation tool"): load the matching domain profile card as the prior.
2. **Inferable with confidence** (corpus described as "patient records and treatment guidelines"): infer the domain, load its card, but mark inferred attributes at lower confidence so Stage 3 confirms them.
3. **Ambiguous or hybrid** ("legal-tech doing medical billing", or no domain signal): do **not** force a single card. Go to the hybrid/novel path below.

Domain detection only ever selects a **prior**. It never finalizes any attribute.

## Stage 2 — Apply the prior

From the selected domain card, populate A1–A12 with the card's prior values and the card's per-attribute confidence flag (`strong` = rarely varies within the domain; `elicit` = high variance within the domain, must be confirmed). Strong priors are provisional defaults; `elicit` priors are placeholders only.

## Stage 3 — Targeted elicitation (bounded)

For every attribute flagged `elicit`, and every attribute the prior could not set, ask the user — **batched into one question set, never one at a time**, and never asking what was already stated or is safely inferable. Map raw answers back onto attribute levels. Stated user information **always overrides** the domain prior; every override is written to the decision log with both values. This override-and-log behavior is the defensible core: the router has opinions (priors) but the user's reality wins, visibly.

## Stage 4 — Conflict detection and resolution (the agentic core)

After Stages 2–3 the requirement vector may be internally unsatisfiable. The router checks for known tension triads, the dominant ones being:

- **quality × latency × cost** — high A1 wants reranking/adaptive; strict A8 forbids stages; low budget forbids GPU rerank.
- **external-model quality × compliance** — best generator is an external API; A4 `sectoral` forbids external egress.
- **freshness × cost** — fast-moving A7 wants frequent reindex; reindex is expensive at scale.

When a conflict is detected the router does **not** silently pick. It:

1. identifies the minimal conflicting attribute set,
2. determines which combinations *are* simultaneously satisfiable (the Pareto set — typically "any two of three"),
3. presents the user the explicit tradeoff: each satisfiable option, what it achieves, what it sacrifices, grounded in the guide corpus,
4. takes the user's choice (or their priority ranking) and records the resolution in the decision log.

This negotiation — detect, find the Pareto set, present honestly, record — is what distinguishes an agentic router from a lookup. It is the single most interview-defensible behavior in the system.

## Stage 5 — Hard-constraint enforcement

Some attribute levels are **non-negotiable filters**, not preferences, and are applied before any quality optimization:

- A4 `sectoral` with no-external-egress → generator restricted to in-VPC/open-weights, full stop.
- A2 `high` → lexical/hybrid mandatory; dense-only topologies removed from the candidate set.
- A12 `gated` → the pipeline must terminate in a review stage; direct-answer topologies removed.

Hard constraints shrink the topology candidate set first; quality attributes choose within what remains. This ordering is deliberate and should be stated as such.

## Stage 6 — Emit

Output the resolved requirement vector + the decision log. Handoff to the synthesizer, which selects the pipeline topology and projects it onto the deployment diagram. Nothing downstream re-derives requirements; the router is the single source of truth for *what the user needs*.

---

## Hybrid / multi-domain path

When two or more domain priors apply (Stage 1 case 3):

- Take the **union** of attributes.
- Where priors disagree, resolve **conservatively**: for the safety/compliance family (A1, A4, A5, A11, A12) take the **stricter** level; for the rest, mark `elicit` and confirm in Stage 3.
- Rationale: under-protecting a regulated sub-domain is unrecoverable; over-protecting is merely suboptimal and gets relaxed by explicit user input. The asymmetry of harm dictates the asymmetry of defaults.

## Novel / unknown domain path

When no card applies:

- Skip Stages 1–2 entirely. There is no prior; that is fine.
- Run Stage 3 over the **full** attribute set (every attribute is `elicit`).
- Proceed normally from Stage 4.
- This is why attribute-decomposition beats domain lookup: the router degrades gracefully to pure first-principles elicitation for any vertical it has never seen. State this explicitly — it is the architecture's strongest generalization claim.

## Abstention / out-of-scope

The router abstains (and says so) rather than guessing when:

- the request is outside the system's scope (e.g., generator fine-tuning, non-RAG architectures, specific legal compliance advice),
- a hard-constraint attribute (A4/A5) is unknown and the user cannot supply it — an unshippable design must not be recommended as if shippable.

Abstention here mirrors the grounding/abstention principle the system recommends to others: the advisor follows its own advice, which is a deliberate consistency worth pointing out.

---

## Confidence and logging contract

Every attribute in the emitted vector carries: `value`, `source` ∈ {stated, inferred, domain-prior, hybrid-conservative, conflict-resolved}, `confidence`, `overrode_prior?`. The decision log is a first-class output, surfaced in the UI and exported with the recommendation. It is what lets an interviewer ask "why did it recommend reranking here but not there?" and get a grounded, traceable answer — which is the entire point of the project.
