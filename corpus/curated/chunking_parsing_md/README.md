# Chunking & Parsing Methods for Document Processing and NLP

This folder contains a detailed Markdown literature review and implementation guide for chunking and parsing methods used in document processing, retrieval-augmented generation (RAG), semantic search, and NLP pipelines.

The report is split into modular files so you can copy sections directly into a paper, technical design document, or implementation plan.

## File map

| File | Purpose |
|---|---|
| `01_literature_review.md` | Narrative literature review covering the evolution from text segmentation to modern RAG chunking. |
| `02_strategy_catalog_parameters_failure_modes.md` | Detailed catalog of fixed, recursive, sentence-window, semantic, proposition, late chunking, parent-child, and layout-aware strategies with parameters and failure modes. |
| `03_document_type_specific_parsing.md` | Parsing and chunking guidance for code/AST, tables/spreadsheets, PDFs/layout-rich documents, and transcripts. |
| `04_selection_framework_and_decision_matrix.md` | Practical decision matrix for choosing a chunking/parsing strategy by corpus type, retrieval objective, latency budget, and failure mode. |
| `05_implementation_blueprints.md` | Implementation recipes, parameter defaults, evaluation harnesses, pseudocode, and ablation plans. |
| `06_bibliography.md` | Consolidated bibliography with primary papers, framework docs, and practical resources. |

## Core thesis

There is no universally best chunking method. Chunking and parsing are **interface design problems** between raw documents, embedding models, retrieval indices, rerankers, and generators. The right strategy depends on five interacting variables:

1. **Document structure**: prose, code, table, PDF, transcript, or mixed layout.
2. **Answer granularity**: atomic fact lookup, local explanation, multi-hop synthesis, or full-document reasoning.
3. **Retrieval budget**: top-k size, context window, reranker cost, and generation context limits.
4. **Embedding behavior**: context length, sensitivity to boundary cuts, language coverage, and whether late pooling is possible.
5. **Operational constraints**: ingestion cost, update frequency, index size, latency, traceability, and provenance requirements.

The strongest practical default is:

> Start with a simple recursive or structure-aware baseline, evaluate on an in-domain gold set, preserve native document structure wherever it carries meaning, then escalate to semantic/proposition/late/hierarchical chunking only when your measured failure mode justifies the added cost.

## Suggested reading order

Read `01_literature_review.md` first if you want the conceptual framing. Use `02_strategy_catalog_parameters_failure_modes.md` as the operational reference. Use `04_selection_framework_and_decision_matrix.md` when designing a pipeline. Use `05_implementation_blueprints.md` when turning the report into experiments or code.
