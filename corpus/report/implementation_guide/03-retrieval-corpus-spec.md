# 03 — Retrieval & Corpus Spec

**Track A.** Implements the report's own recommended default — deliberately, not novelly (resume priority #4). The point is demonstrating you know the production default and chose it on purpose.

## Chunking by content kind (`retrieval/chunking.py`)

| Content kind | Strategy | Rationale |
|---|---|---|
| Guide prose (`report/`) | recursive 400–800 tok, ~15% overlap, parent–child for long sections | report §3 default |
| Decision cards (`curated/`) | atomic — one card = one chunk, never split | a decision must be retrieved whole or it is wrong |
| Routing cards (`routing/`) | atomic — one attribute = one chunk, one domain card = one chunk | router needs the whole rule, not fragments |

## Metadata schema (every chunk)

`source`, `license`, `trust_tier` ∈ {primary, reputable, vendor-partisan}, `volatility` ∈ {stable, volatile}, `section_tags[]`, `parent_id`, `contested` ∈ {consensus, contested}, `namespace` ∈ {knowledge, routing}, `date`.

`trust_tier` and `contested` let the synthesizer present honest tradeoffs ("vendor-partisan source; contested") instead of parroting marketing. `volatility` lets answers hedge stale claims. These were design requirements from the corpus plan; they are enforced here.

## Retrieval core

- **Embeddings:** small model favored for cold-start/CPU indexing (e.g. `bge-small-en-v1.5` or `multilingual-e5-small` if multilingual corpus). Heavier models rejected because startup index build is CPU-bound on Spaces — a deliberate cold-start-vs-quality tradeoff, documented.
- **Hybrid:** dense + BM25, fused with Reciprocal Rank Fusion. Retrieve ~50 candidates.
- **Rerank:** `bge-reranker-v2-m3` cross-encoder → narrow to ~8. GPU-decorated (ZeroGPU) with a CPU fallback path (spec 04).
- **Generation:** grounded prompt, citations required, abstain on weak evidence (report §8). The advisor following its own abstention advice is intentional consistency.
- **Store:** file-based (LanceDB), two namespaces (knowledge, routing), built at startup.

## Startup build flow (`ingestion/build_index.py`)

1. Validate `manifest.yaml`; **fail closed** on missing `license`/`trust_tier`.
2. Walk `corpus/`; parse per type (markdown native; PDF via text extractor).
3. Chunk per content kind; attach metadata; embed (CPU).
4. Write both namespaces to the file store.
5. Idempotent: identical corpus → identical index. This idempotency *is* the "repeatable provisioning / environment consistency" demonstration from the IaC narrative — the same property the advisor preaches, practiced.

Cold start = clone + this build + model warm. Keep it bounded: small corpus, small embedding model, lazy-load the reranker on first query rather than at boot.

## Extensibility

Add curated literature by dropping files in `curated/` and adding manifest entries; re-run ingestion. No code change. That is the corpus-growth story and should be stated as a designed property, not an accident.
