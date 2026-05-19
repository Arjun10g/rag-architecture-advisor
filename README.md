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
python3 -m compileall app.py graph agents retrieval ingestion synth llm eval
python3 eval/harness.py --gate
python3 -c "from graph.build import build_graph; s = build_graph().invoke({'user_brief': 'internal API docs assistant'}); print(s.domain_prior)"
```

When dependencies are installed:

```bash
python3 app.py
```
