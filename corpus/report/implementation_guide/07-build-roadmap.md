# 07 — Build Roadmap

**Track A.** Phases ordered so the resume-priority work (orchestration, then IaC, then eval) gets built and documented first and deepest. Each phase lists the prior artifact it consumes and its exit criterion.

### P0 — Skeleton
Repo per spec 01, Gradio "hello" on a ZeroGPU Space, PRO Dev Mode working.
*Exit:* Space deploys green; SSH iteration works.

### P1 — Corpus & ingestion
Consumes: the 13 report files, `corpus/routing/*`, manifest.
Build `ingestion/` per spec 03: manifest fail-closed, per-content-kind chunking, two namespaces, idempotent startup build.
*Exit:* identical corpus → identical index; manifest validation rejects a doc missing license.

### P2 — Retrieval core
Hybrid + RRF + lazy reranker per spec 03; smoke-test against known report content.
*Exit:* known-answer queries return the correct section in top-8.

### P3 — LLM provider abstraction
`llm/provider.py`: Inference Providers serverless default (keyless), optional user key.
*Exit:* generation works with no key; key path switches provider.

### P4 — Router (priority #1 begins)
Consumes: `routing/00`, `routing/01`, `routing/domain-*`.
Implement Stages 1–6: domain detection → prior → bounded elicitation → hard constraints → conflict/Pareto → emit vector + decision log. Single specialist agent end-to-end first.
*Exit:* a scenario produces a correct, fully-logged requirement vector; an injected conflict triggers the Pareto presentation.

### P5 — Full graph (priority #1 core)
Consumes: spec 02.
Wire LangGraph: conditional elicitation loop, parallel specialist fan-out, bounded critic. All four specialists.
*Exit:* end-to-end run from free-text brief to draft output with a clean router→synthesizer seam; loops are provably bounded.

### P6 — Track B synthesizer (priority #2)
Consumes: spec 05.
Topology selection (fixed catalog, hard-constraint-first), the two linked diagrams, Terraform emit, strengths/weaknesses panel.
*Exit:* emitted HCL passes `terraform validate`; all 7 pillars present in the deployment diagram; panel is use-case-relative (cites the user's stated requirements).

### P7 — Eval & CI (priority #3)
Consumes: spec 06, the frozen gold set (spec 08).
Four-axis harness; GitHub Actions gate; judge calibration.
*Exit:* CI gate runs on PR and fails on a seeded regression in each axis.

### P8 — Degradation & polish
Quota-exhaustion ladder (spec 04) implemented and demonstrated; architecture-led README with the orchestration diagram, two-track note, degradation story, and a CI-gate screenshot; license/manifest audit; curated literature loaded.
*Exit:* forced ZeroGPU exhaustion degrades visibly instead of failing; README leads with orchestration + IaC.

## Critical-path note

P4→P5→P6 is the spine and where most time and documentation go. P1–P3 are enablers — keep them lean; do not gold-plate retrieval (priority #4). P7 can be scaffolded early (gold set authoring runs in parallel from P1) but gated last.
