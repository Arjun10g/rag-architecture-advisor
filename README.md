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

Deep-thinking mode adds a parallel research pass before synthesis. It runs four
agent roles over the local literature corpus and curated public references:
literature review, agent-framework review, community implementation review, and
Hugging Face/Spaces review. By default it fetches the full text of selected
public references, extracts the approach, implementation notes, and limitations,
and shows those summaries in the Research tab. The public API returns the same
summaries and links without raw corpus IDs or file paths.

## Data Storage

- Source documents are committed as markdown under `corpus/curated/`,
  `corpus/report/`, and `corpus/routing/`.
- `corpus/manifest.yaml` is the authoritative catalog. It stores document path,
  namespace, domain, trust tier, tags, and ingest flags.
- At app startup, `ingestion/build_index.py` reads the manifest and chunks the
  markdown into an in-memory `FileChunkStore`; the default lexical retriever does
  not require a persistent database.
- Deployment-grade dense retrieval now supports LanceDB and Qdrant. Set
  `VECTOR_STORE_BACKEND=qdrant` for a managed Qdrant cluster, or
  `VECTOR_STORE_BACKEND=lancedb` to read/write a persisted local vector table
  under `VECTOR_INDEX_DIR`, while keeping the lexical path available as the safe
  default.
- Optional generated artifacts are ignored: `.cache/` for embedding/vector
  caches, `corpus/index/` for future local indexes, and `eval/results/` for
  ablation outputs.
- Hugging Face Spaces receives the committed corpus and app files. GCP is only
  used for heavier offline ablations, and temporary eval VMs are deleted after
  use.

## Skeleton Status

- `app.py` provides the Gradio entrypoint.
- `graph/` contains the typed state and graph runner.
- `agents/` contains router, specialist, deep-research, synthesizer, and critic stubs.
- `retrieval/` and `ingestion/` contain the P1/P2 ingestion and retrieval placeholders.
- `synth/` contains the topology, projection, Terraform, and panel placeholders.
- `corpus/` is the target normalized corpus layout for P1.

## Local Smoke Run

```bash
python3 -m compileall app.py graph agents retrieval ingestion synth llm eval scripts
python3 scripts/router_state_smoke.py
python3 scripts/graph_flow_smoke.py
python3 scripts/deep_research_smoke.py
python3 scripts/deep_research_full_text_smoke.py
python3 scripts/specialist_fanout_smoke.py
python3 scripts/topology_catalog_smoke.py
python3 scripts/terraform_emit_smoke.py
python3 scripts/terraform_export_smoke.py
python3 scripts/vector_store_smoke.py
python3 scripts/vector_index_manifest_smoke.py
python3 scripts/llm_provider_smoke.py
python3 scripts/rate_limit_smoke.py
python3 scripts/app_formatting_smoke.py
python3 scripts/audit_log_smoke.py
python3 scripts/production_readiness_check.py --profile demo
python3 scripts/production_config_smoke.py
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
python3 scripts/api_output_probe.py --url http://127.0.0.1:7860 --runs 3
python3 scripts/api_output_probe.py --url http://127.0.0.1:7860 --deep-thinking
python3 scripts/api_output_probe.py --url http://127.0.0.1:7860 --deep-thinking --require-full-text
python3 scripts/api_output_probe.py --url http://127.0.0.1:7860 --runs 5 --slo-from-env
```

The detailed UI/debug response includes an `audit_record` in raw JSON. Set
`ADVISOR_AUDIT_LOG_PATH=/path/to/advisor-audit.jsonl` to persist those records in
deployment.

## Production Readiness

The public API and deployed Space are suitable for controlled beta once secrets
are configured. Before treating an environment as production, run:

```bash
python3 scripts/production_readiness_check.py --profile production
python3 scripts/public_surface_probe.py --url https://<space-or-host>/
python3 scripts/api_output_probe.py --url https://<space-or-host>/ --runs 5 --slo-from-env
python3 scripts/load_probe.py --url https://<space-or-host>/ --requests 6 --concurrency 3 --slo-from-env
python3 scripts/hf_generation_probe.py
python3 scripts/qdrant_blue_green_promote.py --target-table rag_advisor_chunks --alias-table rag_advisor_chunks_live --dry-run
```

Run the deep-thinking probe only in authenticated or internal profiles where
`DEEP_THINKING_ENABLED=true`.

Production settings to verify:

- Set `HF_TOKEN`, `LLM_PROVIDER=hf`, and `HF_INFERENCE_MODEL` as deployment
  secrets/variables. The probes never print token values.
- For public anonymous access, set `PUBLIC_ACCESS_MODE=anonymous`,
  `ALLOW_ANONYMOUS_PUBLIC=true`, and `DEEP_THINKING_ENABLED=false`. For private
  beta, use `PUBLIC_ACCESS_MODE=authenticated` with `GRADIO_AUTH_USERNAME` and
  `GRADIO_AUTH_PASSWORD`, or `PUBLIC_ACCESS_MODE=gateway` only when a real
  authenticated gateway is in front of the app.
- Set `RATE_LIMIT_ENABLED=true` and `RATE_LIMIT_PER_IDENTITY=true` with
  `RATE_LIMIT_ADVISOR_MAX_REQUESTS`, `RATE_LIMIT_MAX_REQUESTS`, and
  `RATE_LIMIT_WINDOW_SECONDS`; keep separate deep-mode limits with
  `RATE_LIMIT_ADVISOR_DEEP_MAX_REQUESTS` and
  `RATE_LIMIT_ADVISOR_DEEP_WINDOW_SECONDS`. Set `EXTERNAL_RATE_LIMITING=true`
  only when an upstream gateway enforces the limit.
- Set `ADVISOR_REQUEST_LOG_PATH`, `ADVISOR_ALERT_LOG_PATH`, and
  `ADVISOR_USAGE_COUNTER_PATH` to persistent storage. Configure
  `REQUEST_ALERT_MAX_REQUESTS`, `REQUEST_ALERT_LATENCY_MS`,
  `DAILY_REQUEST_BUDGET`, and `MONTHLY_REQUEST_BUDGET` as app-level spend and
  abuse caps. Also set provider/platform billing caps where the host supports
  them.
- Set `ADVISOR_CONCURRENCY_LIMIT` and `ADVISOR_QUEUE_MAX_SIZE` for the chosen
  hardware. CPU-basic Spaces should stay conservative and must pass
  `load_probe.py` before public traffic is increased.
- Set `MAX_BRIEF_CHARS`, `MAX_ELICITATION_CHARS`, `MAX_CONFLICT_CHARS`,
  `LLM_MAX_TOKENS`, and `DEEP_RESEARCH_MAX_FULL_TEXT_LINKS` to bounded public
  values before enabling public traffic.
- Keep `SHOW_RAW_TRACE=false` so debug JSON is hidden in the UI. The public
  `/advise` endpoint never returns the raw graph state.
- Set `ADVISOR_AUDIT_LOG_PATH` to a persistent log sink or mounted volume, for
  example `/data/advisor-audit.jsonl` on a persistent Space.
- Set `ADVISOR_AUDIT_FAILURE_MODE=fail` in production. Leave it as `warn` only
  for local/demo runs where missing storage should not block iteration.
- For dense/hybrid production retrieval, use Qdrant collections
  `rag_advisor_chunks_dim_1024` and `rag_advisor_chunks_dim_512`, then set
  `RETRIEVAL_MODE=hybrid`, `VECTOR_STORE_BACKEND=qdrant`,
  `VECTOR_TABLE_NAME=rag_advisor_chunks_live`, and `EMBEDDING_DIM=1024` or
  `512`. Promote `rag_advisor_chunks_live_dim_1024` and
  `rag_advisor_chunks_live_dim_512` as aliases so future reindexes can switch
  blue/green targets without changing app configuration. The LanceDB index
  remains useful as a local build artifact and fallback.
- On Hugging Face Spaces, set `EMBEDDING_PROVIDER=hf` so query embeddings run on
  HF feature extraction instead of `cpu-basic`. Set `PREWARM_RETRIEVER=true` to
  pay embedding setup during startup instead of on the first request.
- Keep `LATENCY_SLO_P50_MS=12000` and `LATENCY_SLO_P99_MS=20000` as the standard
  hosted hybrid/Qdrant SLO. Deep-thinking/full-text mode uses
  `DEEP_LATENCY_SLO_P50_MS=25000` and `DEEP_LATENCY_SLO_P99_MS=35000`.
- If hosted Llama latency misses the SLO, set `ADVISOR_LATENCY_PROFILE=fast` to
  use the deterministic grounded narrative while preserving retrieval,
  citations, deployment projection, and audit output.
- Keep the deep-thinking smoke green before launch. It checks that the parallel
  research agents return literature, framework, GitHub, Medium, and Hugging Face
  references without exposing internal source identifiers.
- Keep `DEEP_RESEARCH_FULL_TEXT=true` in production so deep mode reads and
  summarizes selected full public references. Use `DEEP_RESEARCH_MAX_FULL_TEXT_LINKS`,
  fetch timeout, and cache settings to bound latency and network risk. Keep
  `DEEP_RESEARCH_RETRIEVAL_MODE=lexical` unless you explicitly want the research
  sidecar to spend dense-query latency; the main advisor retrieval can still run
  as `RETRIEVAL_MODE=hybrid`.
- Use `/health` for uptime checks. Use `/metrics` only with `METRICS_AUTH_TOKEN`
  or `OPERATIONS_TOKEN`; it exposes request counts, p50/p95/p99 latency, the
  last graph timing breakdown, and error counts.

Anonymous public launch mode used by the hosted Space:

```bash
PUBLIC_ACCESS_MODE=anonymous
ALLOW_ANONYMOUS_PUBLIC=true
DEEP_THINKING_ENABLED=false
METRICS_AUTH_TOKEN=<set as secret>
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_IDENTITY=true
TRUST_PROXY_HEADERS=true
RATE_LIMIT_ADVISOR_MAX_REQUESTS=8
RATE_LIMIT_MAX_REQUESTS=8
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_GLOBAL_MAX_REQUESTS=60
RATE_LIMIT_GLOBAL_WINDOW_SECONDS=60
ADVISOR_REQUEST_LOG_PATH=/data/advisor-requests.jsonl
ADVISOR_ALERT_LOG_PATH=/data/advisor-alerts.jsonl
ADVISOR_USAGE_COUNTER_PATH=/data/advisor-usage.json
DAILY_REQUEST_BUDGET=250
MONTHLY_REQUEST_BUDGET=3000
REQUEST_ALERT_MAX_REQUESTS=50
REQUEST_ALERT_LATENCY_MS=20000
ADVISOR_CONCURRENCY_LIMIT=2
ADVISOR_QUEUE_MAX_SIZE=32
```

Rollback path:

```bash
python3 scripts/qdrant_blue_green_promote.py \
  --target-table <previous_physical_table_base> \
  --alias-table rag_advisor_chunks_live \
  --dimensions 1024,512 \
  --write-env
```

For an application rollback, redeploy the previous Git commit or switch the Space
runtime back to the previous Space revision, then run `public_surface_probe.py`,
`api_output_probe.py`, and `load_probe.py` again.

## Retrieval Modes

The default `RETRIEVAL_MODE=lexical` path is dependency-light and used by CI. For
dense retrieval experiments, copy `.env.example` into `.env`, install
`requirements.txt`, and switch to `RETRIEVAL_MODE=dense` or `RETRIEVAL_MODE=hybrid`.

Use `VECTOR_STORE_BACKEND=memory` for quick local experiments. Use Qdrant for a
managed deployment, or LanceDB for local repeatable dense evaluation. Both paths
store 1024- and 512-dimensional Matryoshka indexes by default as separate
tables/collections, so switching `EMBEDDING_DIM` does not force a rebuild.

For LanceDB:

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

For Qdrant Cloud, provide `QDRANT_CLOUD_KEY` plus `QDRANT_CLOUD_ACCOUNT_ID`
or `QDRANT_ID`, then bootstrap isolated advisor collections without overwriting
existing cluster data:

```bash
python3 scripts/qdrant_cloud_bootstrap.py \
  --cluster-name bankmind \
  --table rag_advisor_chunks \
  --source-table chunks \
  --write-env \
  --dimensions 1024,512
```

This creates or verifies `rag_advisor_chunks_dim_1024` and
`rag_advisor_chunks_dim_512`, writes `corpus/index/qdrant/vector_manifest.json`,
and sets `VECTOR_STORE_BACKEND=qdrant`, `QDRANT_URL`, `QDRANT_API_KEY`, and
`VECTOR_TABLE_NAME=rag_advisor_chunks` in `.env`. Existing non-matching
collections are refused unless `--rebuild` is explicitly passed.

Promote those physical collections behind stable live aliases before serving
production traffic:

```bash
python3 scripts/qdrant_blue_green_promote.py \
  --target-table rag_advisor_chunks \
  --alias-table rag_advisor_chunks_live \
  --dimensions 1024,512 \
  --write-env
```

After promotion, run the app with `VECTOR_TABLE_NAME=rag_advisor_chunks_live` and
`QDRANT_REQUIRE_ALIASES=true`. A future reindex can upload
`rag_advisor_chunks_next_dim_1024` and `rag_advisor_chunks_next_dim_512`, smoke
them, then rerun the promotion command with `--target-table rag_advisor_chunks_next`.

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
