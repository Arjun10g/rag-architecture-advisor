# 04 — HF Spaces Deployment Spec

**Track A.** The actual deployment of *this project* under the $9 PRO subscription. Verified constraints, not assumptions.

## Hardware & budget reality

- $9/mo = HF PRO. Unlocks ZeroGPU hardware for Spaces, 20× Inference Provider credits, ~25 min/day H200 ZeroGPU compute, Dev Mode, 1TB private storage.
- ZeroGPU is **Gradio SDK only**, PyTorch only. The whole app is therefore Gradio — consistent with the original plan.
- Dedicated Inference Endpoints are a separate hourly product and are **not used** — they would break the budget.
- Persistent storage is a paid add-on and is **not used** — index is rebuilt at startup.

## GPU usage pattern (`@spaces.GPU`)

Only two operations are GPU-worthy and decorated:

- **Rerank** — cross-encoder over ~50 candidates. Lazy-loaded on first query.
- **Generation** — only if running an open model in-Space; default path sends generation to serverless Inference Providers instead, conserving ZeroGPU quota for rerank.

Embedding the user's short query and the startup index build run on CPU (the Space's multi-core CPU is adequate; indexing must not consume the daily GPU minutes).

## Quota-exhaustion graceful degradation (build this deliberately)

A portfolio piece gets bursty traffic; ~25 GPU-min/day will exhaust. The system degrades, it does not fail:

| State | Generation | Rerank | UI signal |
|---|---|---|---|
| Normal | Inference Providers (serverless) | ZeroGPU cross-encoder | none |
| ZeroGPU exhausted | Inference Providers (unchanged) | CPU cross-encoder (slower) or score-fusion-only | "running in reduced-latency mode" |
| Provider credits exhausted | optional user key if supplied, else queued/notice | CPU | "set an API key for full speed" |

This degradation ladder is the project's own scalability story made concrete — document it in the README; it is an interview asset, not an embarrassment.

## Cold start sequence

clone repo → validate manifest → build index (CPU) → start Gradio → lazy-load reranker on first request. Keep bounded via small corpus + small embedding model + lazy reranker. Document expected cold-start time honestly in the README.

## Secrets & config

- Optional user LLM API keys: entered in the UI at runtime (never persisted) or set as Space secrets for the maintainer demo.
- No PII handling needed — the corpus is public technical literature; state this explicitly so the security story stays scoped.

## Iteration

Use PRO Dev Mode (SSH / VS Code into the Space) for fast iteration instead of rebuild-per-change. Note the 10-ZeroGPU-Space cap on a personal PRO account — irrelevant for one project but worth knowing if you fork demos.
