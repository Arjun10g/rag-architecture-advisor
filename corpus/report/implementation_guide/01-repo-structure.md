# 01 — Repository Structure

**Track A.** Defines the directory layout and, critically, how the three markdown bodies (knowledge corpus, routing cards, generated specs) are organized and ingested differently.

```
repo/
  app.py                     # Gradio entrypoint (ZeroGPU-compatible)
  graph/
    state.py                 # typed shared state (the requirement vector + log)
    nodes.py                 # router, resolver, specialists, synthesizer, critic
    edges.py                 # conditional + parallel + bounded-reflection wiring
    build.py                 # assembles + compiles the LangGraph
  agents/
    intake_router.py         # Stages 1–5 of router decision logic
    specialists.py           # parallel retrieval agents (uniform contract)
    synthesizer.py           # Track B output assembly
    critic.py                # bounded reflection
  retrieval/
    chunking.py              # per-content-kind strategies
    index.py                 # hybrid (dense+BM25) + RRF
    rerank.py                # cross-encoder, ZeroGPU-decorated + CPU fallback
    store.py                 # file-based vector store wrapper
  ingestion/
    build_index.py           # startup: corpus -> index (idempotent)
    manifest.py              # validates per-doc metadata
  synth/
    topology.py              # requirement vector -> pipeline topology
    projection.py            # pipeline -> deployment diagram (the "link")
    terraform_emit.py        # Terraform module tree generator
    panel.py                 # use-case-relative strengths/weaknesses
  llm/
    provider.py              # pluggable: Inference Providers default + key path
  eval/
    gold/                    # frozen gold set (see gold-set plan)
    harness.py               # retrieval + faithfulness + routing metrics
  corpus/
    report/                  # the 13 guide md files
    curated/                 # gathered literature (md/pdf/txt)
    routing/                 # the router cards (taxonomy, logic, domain-*)
    manifest.yaml            # per-doc: title, source_url, license,
                             #   trust_tier, volatility, section_tags, domain
  infra/                     # Track B sample output the tool itself documents (meta)
  .github/workflows/eval.yml # CI eval gate
  README.md                  # architecture-led; diagram + two-track note up top
```

## Three markdown bodies, ingested differently

1. **Knowledge corpus** (`corpus/report/`, `corpus/curated/`) — prose + atomic decision cards. Chunked per content kind (spec 03). Retrieved by specialist agents to ground recommendations.
2. **Routing cards** (`corpus/routing/`) — the taxonomy, decision logic, domain priors. Ingested as a **separate retrieval namespace**, chunked atomically (one attribute = one chunk, one domain card = one chunk). The router retrieves only from this namespace; specialists retrieve only from the knowledge namespace. Keeping namespaces separate prevents the router's own logic from polluting answer grounding and vice versa.
3. **Generated specs / output** (`synth/` templates, `infra/`) — not ingested; these are program logic and product output.

## Manifest is mandatory

`corpus/manifest.yaml` must have an entry per document. Ingestion **fails closed** if any doc lacks `license` or `trust_tier`. This enforces the open-source posture and the source-quality contract from the corpus plan, and makes "is the corpus enough / clean" a checkable property rather than a hope.
