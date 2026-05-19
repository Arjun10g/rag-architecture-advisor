# Chunking, Parsing, and RAG Evaluation Literature Review

This Markdown bundle turns the second report into a reusable reference package. It focuses on how to evaluate retrieval-augmented generation systems while keeping chunking and parsing decisions visible as first-class experimental factors.

## Files

| File | Purpose |
|---|---|
| `01_executive_summary_and_scope.md` | High-level takeaways and evaluation framing. |
| `02_evaluation_frameworks_metric_definitions.md` | Metric definitions and comparison for RAGAS, ARES, TruLens, and DeepEval. |
| `03_benchmark_datasets.md` | Dataset catalog for BEIR, MTEB, MS MARCO, Natural Questions, HotpotQA, KILT, RGB, and CRUD-RAG. |
| `04_gold_set_construction_methodology.md` | Methodology for building domain-specific gold sets, including relevance labels, references, citations, and negative cases. |
| `05_llm_as_judge_caveats.md` | Judge-model risks, biases, calibration methods, and audit procedures. |
| `06_offline_vs_online_evaluation.md` | Offline/online split, CI evaluation, dashboards, A/B tests, interleaving, and monitoring. |
| `07_selection_framework_when_to_use_which.md` | Practical decision matrix for choosing metrics, frameworks, and benchmarks. |
| `08_bibliography.md` | Full source list with paper/doc links. |

## How to use this bundle

Use this as a design document for a RAG evaluation stack. For a publishable or enterprise-grade experiment, treat chunking, parsing, retrieval, reranking, generation, and evaluation as separate factors. The central warning is that an end-to-end answer score alone cannot tell you whether failures came from parsing, chunking, retrieval, context ordering, answer synthesis, citation behavior, or judge-model error.

## Recommended evaluation spine

1. **Parser fidelity**: Did the pipeline preserve titles, sections, tables, reading order, code structure, speaker turns, and metadata?
2. **Chunk quality**: Are chunks coherent, retrievable, and small enough for citation while preserving enough context?
3. **Retriever quality**: Are relevant chunks found and ranked high enough?
4. **Generator quality**: Is the answer correct, relevant, complete, and grounded in the retrieved context?
5. **Attribution quality**: Do cited sources actually support the claims, and did the model genuinely use them?
6. **User impact**: Does the system reduce time-to-answer, escalation rate, abandoned sessions, corrections, and user dissatisfaction?

## Core sources

Primary sources include the RAGAS paper and docs, ARES paper, TruLens docs, DeepEval docs, BEIR, MTEB, MS MARCO, HotpotQA, KILT, RGB, CRUD-RAG, and LLM-as-judge literature. See `08_bibliography.md`.

Generated on 2026-05-19.
