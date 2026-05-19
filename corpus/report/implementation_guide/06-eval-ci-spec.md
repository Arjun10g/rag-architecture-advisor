# 06 — Evaluation & CI Spec

**Track A.** Resume priority #3. The point is that ML systems are treated as systems: measured and regression-gated. Consumes the frozen gold set (see `08-gold-set-creation-plan.md`).

## Four eval axes (this project has one most others lack)

1. **Retrieval quality** — does the right corpus section reach the candidate set / survive rerank? Metrics: recall@k, MRR, nDCG@10. Run over retrieval gold items.
2. **Answer faithfulness** — is the answer grounded in retrieved context, with correct citations, and does it abstain when evidence is weak? Metrics: faithfulness/groundedness score, citation-correctness, abstention-correctness. `ragas` or a lightweight custom scorer.
3. **Routing correctness** — *unique to this project.* Given a scenario, does the router produce the correct resolved requirement vector (and correctly flag conflicts)? Metric: per-attribute exact-match against the gold vector + conflict-detection precision/recall. This axis is the strongest differentiator in the eval suite — call it out explicitly.
4. **Topology correctness** — given the gold requirement vector, does the synthesizer select the gold-correct topology and emit a structurally valid Terraform tree (all 7 modules, parseable HCL)?

## CI gate (`.github/workflows/eval.yml`)

GitHub Actions on every push to main and every PR. Thresholds (tune after baseline, then freeze):

- recall@10 ≥ target, MRR ≥ target
- faithfulness ≥ target, abstention-correctness ≥ target
- routing per-attribute accuracy ≥ target
- topology-correctness ≥ target; emitted HCL must `terraform validate` clean

PR fails if any axis regresses past threshold. The gate being visible in the repo is itself the resume signal — a screenshot of the passing/failing check goes in the README.

## Practices

- **No leakage:** gold items never appear in prompts, few-shot, or the corpus as Q/A pairs.
- **LLM-as-judge** only for faithfulness/answer-quality, calibrated against a human-scored subset; report judge–human agreement so the metric is trusted, not assumed.
- **Volatile items** (model names, pricing) are tagged in the gold set and excluded from hard gating — they assert "the system hedged appropriately," not a specific stale value.
- **Determinism where possible:** routing and topology axes are largely rule-driven, so they should be near-deterministic; flakiness there indicates a logic bug, not eval noise.
