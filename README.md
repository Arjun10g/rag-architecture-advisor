---
title: RAG Architecture Advisor
sdk: gradio
app_file: app.py
pinned: false
colorFrom: blue
colorTo: green
---

# RAG Architecture Advisor

An agentic RAG architecture advisor that maps a user's situation to a defensible requirement vector, retrieves from a curated RAG architecture corpus, and emits a pipeline recommendation with deployment and IaC guidance.

## Runtime Shape

Track A is this application: a Gradio app on Hugging Face Spaces, backed by a LangGraph-style state machine, startup-built retrieval index, and bounded reflection.

Track B is what the app produces: selected RAG topology, linked pipeline and deployment views, Terraform module sketch, strengths/weaknesses, and the decision log.

## Skeleton Status

- `app.py` provides the Gradio entrypoint.
- `graph/` contains the typed state and graph runner.
- `agents/` contains router, specialist, synthesizer, and critic stubs.
- `retrieval/` and `ingestion/` contain the P1/P2 ingestion and retrieval placeholders.
- `synth/` contains the topology, projection, Terraform, and panel placeholders.
- `corpus/` is the target normalized corpus layout for P1.

## Local Smoke Run

```bash
python3 -m compileall app.py graph agents retrieval ingestion synth llm eval scripts
python3 eval/harness.py --gate
python3 -c "from graph.build import build_graph; s = build_graph().invoke({'user_brief': 'internal API docs assistant'}); print(s.domain_prior)"
```

## Retrieval Modes

The default `RETRIEVAL_MODE=lexical` path is dependency-light and used by CI. For
dense retrieval experiments, copy `.env.example` into `.env`, install
`requirements.txt`, and switch to `RETRIEVAL_MODE=dense` or `RETRIEVAL_MODE=hybrid`.

The dense path uses `mixedbread-ai/mxbai-embed-large-v1`, a 1024-dimensional
Matryoshka-capable embedding model. Run the dimension ablation after dependencies
and model access are available:

```bash
python3 scripts/embedding_dim_ablation.py --gold eval/gold/v0_2_expanded.json --dimensions 1024,768,512,384,256
```

Compare lexical, dense, hybrid, and ColBERT-reranked strategies across both gold
sets with:

```bash
python3 scripts/retrieval_strategy_ablation.py --gold eval/gold/v0_1_seed.json,eval/gold/v0_2_expanded.json
```

The ColBERT strategies require the optional VM/local install:

```bash
python3 -m pip install "rerankers[transformers]"
```

When dependencies are installed:

```bash
python3 app.py
```
