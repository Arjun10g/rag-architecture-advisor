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
The detailed UI also accepts follow-up answers for pending attributes and an
explicit conflict-resolution value, then reruns the same graph with those values.

## Data Storage

- Source documents are committed as markdown under `corpus/curated/`,
  `corpus/report/`, and `corpus/routing/`.
- `corpus/manifest.yaml` is the authoritative catalog. It stores document path,
  namespace, domain, trust tier, tags, and ingest flags.
- At app startup, `ingestion/build_index.py` reads the manifest and chunks the
  markdown into an in-memory `FileChunkStore`; the default lexical retriever does
  not require a persistent database.
- Deployment-grade dense retrieval now has an optional LanceDB backend. Set
  `VECTOR_STORE_BACKEND=lancedb` to read/write a persisted vector table under
  `VECTOR_INDEX_DIR` while keeping the lexical path available as the safe default.
- Optional generated artifacts are ignored: `.cache/` for embedding/vector
  caches, `corpus/index/` for future local indexes, and `eval/results/` for
  ablation outputs.
- Hugging Face Spaces receives the committed corpus and app files. GCP is only
  used for heavier offline ablations, and temporary eval VMs are deleted after
  use.

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
python3 scripts/router_state_smoke.py
python3 scripts/graph_flow_smoke.py
python3 scripts/specialist_fanout_smoke.py
python3 scripts/topology_catalog_smoke.py
python3 scripts/terraform_emit_smoke.py
python3 scripts/terraform_export_smoke.py
python3 scripts/vector_store_smoke.py
python3 scripts/vector_index_manifest_smoke.py
python3 scripts/llm_provider_smoke.py
python3 scripts/app_formatting_smoke.py
python3 scripts/audit_log_smoke.py
python3 eval/harness.py --gate
python3 eval/harness.py --gold eval/gold/v0_4_answer_quality.json --gate
python3 eval/harness.py --gold eval/gold/v0_5_panel_quality.json --gate
LLM_PROVIDER=disabled python3 -c "from graph.build import build_graph; s = build_graph().invoke({'user_brief': 'internal API docs assistant'}); print(s.domain_prior)"
```

The answer and panel gates check that final recommendations include structured
architecture decisions, detailed why/tradeoff/validation reasoning, reasoning
chunks instead of file-path-only source display, required source families,
citation coverage metrics, and requirement-specific strengths/weaknesses.

Export the advisor's illustrative Terraform bundle to real files with:

```bash
python3 scripts/export_terraform.py --out infra/generated/latest
python3 scripts/export_terraform.py --out infra/generated/latest --validate  # runs Terraform if installed
```

## LLM Generation

Structured topology, architecture decisions, citations, and Terraform sketches are
deterministic. The optional LLM layer writes the narrative advisor summary from
those already-grounded fields. By default it uses Hugging Face Inference
Providers:

```bash
LLM_PROVIDER=hf
HF_INFERENCE_PROVIDER=auto
HF_INFERENCE_MODEL=meta-llama/Llama-3.3-70B-Instruct
```

Set `LLM_PROVIDER=disabled` for no-network deterministic output. If
`huggingface_hub`, the model endpoint, or provider access is unavailable, the app
falls back to a deterministic generated summary and records the reason in
`draft_output.generation`.
The default is a larger Llama instruct model for stronger narrative synthesis;
you can swap `HF_INFERENCE_MODEL` to any model your Hugging Face token can access.
To verify the configured provider path without printing secrets:

```bash
python3 scripts/hf_generation_probe.py
```

The probe fails if the displayed answer leaks raw corpus IDs, file paths, router
trace markers, or raw attribute codes. If the provider is unavailable, the app
uses deterministic fallback and records the reason in `draft_output.generation`.

For Gradio clients, use the public `/advise` endpoint. It returns the advisor
answer, architecture decisions, reasoning chunks, deployment projection,
Terraform sketch, public reasoning trace, and generation status without the raw
graph state:

```bash
python3 scripts/api_output_probe.py --url http://127.0.0.1:7860
```

The detailed UI/debug response includes an `audit_record` in raw JSON. Set
`ADVISOR_AUDIT_LOG_PATH=/path/to/advisor-audit.jsonl` to persist those records in
deployment.

## Retrieval Modes

The default `RETRIEVAL_MODE=lexical` path is dependency-light and used by CI. For
dense retrieval experiments, copy `.env.example` into `.env`, install
`requirements.txt`, and switch to `RETRIEVAL_MODE=dense` or `RETRIEVAL_MODE=hybrid`.

Use `VECTOR_STORE_BACKEND=memory` for quick local experiments. Use LanceDB for
actual deployment or repeatable dense evaluation. The build command stores both
1024- and 512-dimensional Matryoshka indexes by default as separate tables
(`chunks_dim_1024` and `chunks_dim_512`), so switching `EMBEDDING_DIM` does not
force a rebuild. The build also writes
`corpus/index/lancedb/vector_manifest.json` so deployment can verify which
tables and dimensions are present:

```bash
python3 scripts/build_vector_index.py --backend lancedb --dimensions 1024,512 --rebuild
```

Then run with:

```bash
RETRIEVAL_MODE=hybrid
VECTOR_STORE_BACKEND=lancedb
VECTOR_INDEX_DIR=corpus/index/lancedb
EMBEDDING_DIM=1024  # or 512 to select chunks_dim_512
```

The dense path uses `mixedbread-ai/mxbai-embed-large-v1`, a 1024-dimensional
Matryoshka-capable embedding model. Run the dimension ablation after dependencies
and model access are available:

```bash
python3 scripts/embedding_dim_ablation.py --gold eval/gold/v0_2_expanded.json --dimensions 1024,768,512,384,256
```

Current recommendation from the local/GPU ablations:

- Keep `RETRIEVAL_MODE=lexical` for CI, Spaces startup safety, and no-download local smoke tests.
- Use `RETRIEVAL_MODE=hybrid` with `EMBEDDING_DIM=1024` as the best quality profile when the embedding model is cached.
- Use `RETRIEVAL_MODE=dense` with `EMBEDDING_DIM=512` for the fastest dense-only profile with minimal quality loss.

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
