# 08 — Gold Set Creation Plan

**Track A.** A methodology for building the frozen evaluation gold set. This is deliberately rigorous: the project's evaluation-rigor signal lives or dies here, and a well-constructed gold set is the rarest thing in a portfolio RAG project.

## Guiding principle

Build the gold set **backward from the question taxonomy**, not forward from the corpus. The set of questions the advisor must answer *is* the gold set. This makes the gold set and the corpus-coverage instrument the same artifact: every taxonomy cell that has no gold item is both an untested capability and a corpus gap.

## Five item types (the project needs all five — most projects have only the first)

1. **Retrieval gold.** A query + the set of corpus chunk/section IDs that *must* appear in the candidate set and/or survive rerank. Ground truth = "which sections are necessary and sufficient to answer this."
2. **Answer-faithfulness gold.** A query + the required factual claims a faithful answer must contain + claims it must *not* make + whether it should **abstain**. Ground truth includes the correct abstention decision, not just the correct answer.
3. **Routing gold.** A free-text user scenario + the correct resolved requirement vector (all 12 attributes, with `source` and any expected overrides) + whether a conflict should be detected and which attributes conflict. This is the highest-value, project-unique item type.
4. **Conflict-resolution gold.** A scenario engineered to be internally unsatisfiable + the correct Pareto set (which combinations are simultaneously satisfiable) + the correct tradeoff framing.
5. **Topology gold.** A resolved requirement vector + the correct topology from the fixed catalog + the modules the emitted Terraform must contain. Near-deterministic; flakiness here is a logic bug.

## Coverage matrix (the authoring worklist)

Construct a matrix: **attribute level (A1–A12 × their levels) × domain (the profile cards + a "novel/none" column) × decision area (retrieval / deployment / IaC)**. Every cell needs ≥1 item of the relevant type. Targets:

- Routing gold: ≥1 scenario per domain card (4+) + ≥3 hybrid/multi-domain + ≥3 novel-domain (no prior) + ≥5 single-attribute-isolation scenarios (vary one attribute, hold rest) so per-attribute accuracy is measurable, not just aggregate.
- Conflict-resolution gold: ≥1 per known tension triad (quality×latency×cost; external-model×compliance; freshness×cost) × ≥2 domains.
- Retrieval + faithfulness gold: ≥30 spanning all corpus decision areas, including ≥6 **must-abstain** items (question not answerable from corpus) and ≥6 **contested-knowledge** items.
- Topology gold: ≥1 per catalog topology × ≥2 requirement profiles that should select it.

Roughly 90–130 items total. Coverage completeness, not raw count, is the bar; an empty matrix cell is a finding.

## Authoring process

1. **Derive, don't invent.** For each matrix cell, write the scenario from the taxonomy + domain card that defines that cell. The router files and corpus are the source of truth for what "correct" means — gold answers must be traceable to them, exactly as the system's own answers must be.
2. **Dual authoring + adjudication.** Two passes write ground truth independently for a sampled subset; disagreements are adjudicated and the adjudication rule written down. Report inter-author agreement — it is the credibility number for the whole gold set.
3. **Contested items get contested ground truth.** For `contested` corpus topics, the gold answer is "present both positions and flag the disagreement," and an answer that confidently picks a side **fails** even if that side is defensible. This directly tests the honesty property the corpus design was built for.
4. **Abstention items.** Author questions that are plausibly in-domain but unanswerable from the corpus. Correct behavior = abstain with reason. These catch the most dangerous failure (confident fabrication) and are usually missing from weak gold sets.
5. **Freeze and version.** Once adjudicated, freeze under `eval/gold/` with a version tag and a changelog. The frozen set is immutable per version; changes create a new version. CI pins a version.

## Ground-truth definitions (make "correct" unambiguous)

- *Retrieval:* a ranked-relevance label per (query, section) — `required`, `helpful`, `irrelevant`. Metrics computed only against `required`/`helpful`.
- *Faithfulness:* an explicit claim checklist (must-include, must-not-include) + abstention boolean. Avoids vague "good answer" judging.
- *Routing:* the exact 12-tuple + expected `source` per attribute + expected overrides + conflict flag. Per-attribute scoring, not whole-vector pass/fail, so partial correctness is visible.
- *Topology:* exact catalog choice + required Terraform module set + "HCL must validate."

## Leakage & integrity controls

- Gold scenarios/questions never enter prompts, few-shot exemplars, or the corpus as Q/A pairs. Authoring uses corpus *content* but the gold *items* live only under `eval/gold/`.
- Volatile-fact items (model names, pricing) are tagged `volatile`: their ground truth asserts "the system hedged / cited a dated source," never a specific value. Excluded from hard CI gating; refreshed on a stated cadence.
- A small **human-scored calibration subset** (~15 items) is scored by a person; the LLM judge is run against it and judge–human agreement is reported. The judge is only trusted on axes where agreement clears a stated bar; otherwise that axis stays human-reviewed.

## Maintenance

- Stable items: effectively permanent; only re-adjudicated if the corpus's stable backbone changes.
- Volatile items: reviewed on a fixed cadence (e.g. quarterly) against current sources; a refresh bumps the gold version.
- When the corpus grows (new curated literature), add gold items for the newly covered matrix cells in the same PR — corpus growth without gold growth is treated as untested coverage and flagged in review.

## Why this is the resume signal

Most candidates show a RAG demo with no eval, or a handful of ad-hoc questions. This plan produces a versioned, coverage-driven, leakage-controlled gold set with a project-unique routing axis and explicit abstention/contested testing, gated in CI. In an interview, "how do you know it works?" has a precise, defensible answer — which is the entire reason evaluation rigor was ranked a priority.
