# 00 — Implementation Overview

**Project:** an agentic RAG Architecture Advisor — a RAG system that recommends RAG pipelines and their cloud/IaC deployment, grounded in a curated corpus, deployed on Hugging Face Spaces. Self-referential by design: it implements the best-practice pipeline it recommends.

## Locked decisions (do not relitigate during build)

| Area | Decision |
|---|---|
| Orchestration | LangGraph state machine (conditional routing, parallel fan-out, bounded reflection) |
| Routing | Attribute-decomposition (12-attribute taxonomy); domains are priors, not lookups |
| LLM | Pluggable: open-weights via HF Inference Providers (serverless) default; optional user API key. **Not** dedicated Inference Endpoints |
| UI / hardware | Gradio SDK on ZeroGPU (the constraint the $9 PRO unlocks) |
| Index | Built at container startup from bundled corpus; ephemeral; no paid persistent storage |
| Degradation | ZeroGPU quota exhausted → fall back to serverless generation + CPU rerank, with visible status |
| Embedding model | Smaller model favored for cold-start/CPU indexing speed |

## The two-track separation (structural — keep these apart everywhere)

**Track A — the advisor's own system and deployment.** How *this project* is built and runs: LangGraph graph, retrieval core, Gradio app, HF Spaces $9 deployment. Specs 01–04, 06, 07.

**Track B — the cloud/IaC knowledge the advisor emits to users.** What the advisor *outputs*: the two linked diagrams (pipeline + deployment), the Terraform module sketch, the strengths/weaknesses panel. Spec 05. This is product output, not project infrastructure. Conflating A and B is the most common way this plan goes incoherent — every file states which track it belongs to.

## System map (Track A runtime)

```
User free-text need
   │
   ▼
Intake / Router  ── elicit (bounded loop) ──┐
   │  attribute resolution (taxonomy)        │
   │  conflict detection → Pareto present ───┘
   ▼  emits: resolved requirement vector + decision log
Specialist retrieval agents (parallel) ── hybrid+rerank over corpus
   ▼
Synthesizer ── selects topology, projects to deployment, builds panel  (Track B output)
   ▼
Critic / reflection (bounded) ── gaps → back to Router
   ▼
Two linked diagrams + Terraform sketch + strengths/weaknesses panel + decision log
```

## Resume priority ordering (drives build sequence and where depth goes)

1. Agent orchestration / routing — the LangGraph graph + attribute router is the showpiece
2. Cloud + IaC — the Track B emitter (Terraform + linked deployment diagram)
3. Evaluation rigor — gold set + retrieval/faithfulness/routing metrics in CI
4. Retrieval — the documented best-practice default, implemented deliberately, not novel

The build roadmap (07) sequences work in this order. The README leads with 1 and 2.

## Inputs already produced (feed the build)

- `routing/00-routing-attribute-taxonomy.md` — the 12 attributes (router spine)
- `routing/01-router-decision-logic.md` — router algorithm + conflict/Pareto + abstention
- `routing/domain-*.md` — domain priors + template
- The 13-file guide report + curated literature — the knowledge corpus

These are not re-derived; the specs below consume them as-is.
