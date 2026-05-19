# 06 — Bibliography and Source Notes

This bibliography consolidates the main source families used in the report: primary papers, benchmark/comparative studies, framework documentation, and parser/model references.

## 1. Foundational text segmentation

### TextTiling

- Hearst, M. A. (1997). *TextTiling: Segmenting Text into Multi-paragraph Subtopic Passages*. Computational Linguistics.
- URL: https://aclanthology.org/J97-1003.pdf
- Relevance: Foundational lexical-cohesion approach to topical text segmentation. Useful historical baseline for modern semantic chunking.

## 2. Modern RAG chunking and segmentation studies

### Document Segmentation Matters for Retrieval-Augmented Generation

- URL: https://aclanthology.org/2025.findings-acl.422.pdf
- Relevance: Directly evaluates segmentation/chunking strategies for RAG. Important evidence that fixed-size chunking is a strong baseline but content-aware/proposition-style segmentation can improve retrieval across datasets.

### Large-scale cross-domain chunking study

- URL: https://arxiv.org/abs/2603.06976
- Relevance: Evaluates chunking approaches across multiple domains and highlights tradeoffs between retrieval quality, index size, and latency. Useful for practical method selection.

### Dense X Retrieval: What Retrieval Granularity Should We Use?

- URL: https://arxiv.org/abs/2312.06648
- Relevance: Introduces proposition-level retrieval. Central source for proposition chunking and atomic fact indexing.

### Late Chunking

- URL: https://arxiv.org/pdf/2409.04701
- Relevance: Introduces or formalizes late chunking: embed long context first, then pool token spans into chunk vectors. Important for context-dependent long-document retrieval.

### Controlled code chunking study for retrieval-augmented code completion

- URL: https://arxiv.org/pdf/2605.04763
- Relevance: Strong evidence that code chunking requires empirical testing. Highlights that function-level chunking can underperform and that sliding-window/cAST strategies may dominate the Pareto frontier.

## 3. Document-type-specific chunking and parsing

### Spreadsheet/Table Chunking

- URL: https://arxiv.org/html/2605.00318v1
- Relevance: Motivates row/header-preserving spreadsheet/table chunking and shows why naive recursive text splitting loses table structure.

### Meeting transcript and dialogue segmentation

- URL: https://aclanthology.org/2023.acl-long.837.pdf
- Relevance: Useful for transcript and meeting QA, where answer spans may cross speaker turns and consecutive dialogue segments.

### Speech-native / transcript retrieval work

- URL: https://arxiv.org/html/2505.17326v1
- Relevance: Discusses retrieval over speech/transcript-like sources and the importance of VAD, diarization, and segmentation quality.

## 4. Layout-aware document understanding

### LayoutLM

- URL: https://arxiv.org/abs/1912.13318
- Relevance: Foundational model showing that document layout and text jointly matter for document understanding.

### DocLLM

- URL: https://arxiv.org/abs/2401.00908
- Relevance: Modern document understanding model emphasizing layout-aware processing for visually rich documents.

### Additional layout model reference

- URL: https://arxiv.org/abs/2012.14740
- Relevance: Follow-up layout-aware document AI work; useful background for why PDF parsing should preserve spatial structure.

## 5. Framework and implementation documentation

### LangChain RecursiveCharacterTextSplitter

- URL: https://docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter
- Relevance: Practical recursive chunking implementation and separator logic.

### LangChain ParentDocumentRetriever

- URL: https://reference.langchain.com/python/langchain-classic/retrievers/parent_document_retriever
- URL: https://reference.langchain.com/python/langchain-classic/retrievers/parent_document_retriever/ParentDocumentRetriever
- Relevance: Practical parent-child retrieval pattern: retrieve small chunks, return larger parent documents.

### LlamaIndex SentenceWindowNodeParser

- URL: https://developers.llamaindex.ai/python/framework-api-reference/node_parsers/sentence_window/
- Relevance: Practical sentence-window implementation with window metadata.

### LlamaIndex SemanticSplitterNodeParser

- URL: https://developers.llamaindex.ai/python/framework-api-reference/node_parsers/semantic_splitter/
- Relevance: Practical semantic splitter implementation using embedding-based breakpoints.

### LlamaIndex Hierarchical Node Parsers

- URL: https://developers.llamaindex.ai/python/framework/module_guides/loading/node_parsers/modules/
- URL: https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/node_parser/relational/hierarchical.py
- Relevance: Hierarchical node parsing, parent/child relations, and automerging-style retrieval patterns.

### LlamaIndex Dense X Retrieval Pack

- URL: https://developers.llamaindex.ai/python/framework-api-reference/packs/dense_x_retrieval/
- Relevance: Practical proposition retrieval implementation linked to Dense X Retrieval.

### LlamaIndex CodeSplitter

- URL: https://developers.llamaindex.ai/python/examples/node_parsers/code_splitter_chunking/
- Relevance: Practical code-aware splitting example.

### Unstructured chunking and partitioning

- URL: https://docs.unstructured.io/open-source/core-functionality/chunking
- URL: https://docs.unstructured.io/open-source/core-functionality/partitioning
- URL: https://docs.unstructured.io/api-reference/legacy-api/partition/chunking
- Relevance: Practical layout-aware and element-aware parsing/chunking for PDFs, tables, and heterogeneous documents.

### Tree-sitter

- URL: https://tree-sitter.github.io/tree-sitter/
- Relevance: Incremental parsing system used for AST-aware code chunking across many programming languages.

## 6. Adjacent evaluation and benchmark sources useful for chunking studies

Although the main report focuses on chunking and parsing, chunking methods should be evaluated with retrieval and RAG benchmarks. The following sources are useful when designing a chunking evaluation.

### BEIR

- URL: https://arxiv.org/abs/2104.08663
- Relevance: Heterogeneous retrieval benchmark suite. Useful for retriever selection and zero-shot retrieval comparisons.

### MTEB

- URL: https://aclanthology.org/2023.eacl-main.148/
- Relevance: Broad embedding benchmark. Useful when selecting embedding models before chunking ablations.

### MS MARCO

- URL: https://arxiv.org/abs/1611.09268
- Relevance: Web passage ranking and QA benchmark. Useful for passage retrieval baselines.

### Natural Questions

- URL: https://aclanthology.org/anthology-files/pdf/Q/Q19/Q19-1026.pdf
- Relevance: Open-domain QA with real search queries and long/short answer annotations.

### HotpotQA

- URL: https://aclanthology.org/D18-1259/
- Relevance: Multi-hop QA with supporting facts; useful for evaluating chunking strategies under distributed evidence.

### KILT

- URL: https://arxiv.org/abs/2009.02252
- Relevance: Knowledge-intensive tasks with provenance over a shared Wikipedia snapshot.

### RGB

- URL: https://ojs.aaai.org/index.php/AAAI/article/view/29728/31250
- Relevance: RAG robustness benchmark covering noise robustness, negative rejection, information integration, and counterfactual robustness.

### CRUD-RAG

- URL: https://arxiv.org/abs/2401.17043
- Relevance: RAG benchmark organized around Create, Read, Update, Delete scenarios; useful for knowledge lifecycle evaluation.

## 7. Source interpretation notes

1. Framework documentation is best used for implementation parameters and default behavior, not for universal performance claims.
2. Academic papers are best used for controlled comparisons, but many are domain-specific.
3. Public retrieval benchmarks often underrepresent enterprise PDFs, spreadsheets, transcripts, and code repositories.
4. Claims about “best chunk size” should be treated skeptically unless tied to a specific corpus, retriever, model, and metric.
5. For production systems, benchmark retrieval metrics must be paired with latency, index size, ingestion cost, citation accuracy, and human error analysis.

## 8. Recommended citation clusters by topic

| Topic | Primary sources |
|---|---|
| Classical segmentation | TextTiling |
| General RAG segmentation | Document Segmentation Matters; large-scale cross-domain chunking study |
| Proposition chunking | Dense X Retrieval; LlamaIndex Dense X Retrieval Pack |
| Late chunking | Late Chunking paper |
| Recursive chunking | LangChain RecursiveCharacterTextSplitter docs |
| Sentence-window | LlamaIndex SentenceWindowNodeParser docs |
| Parent-child | LangChain ParentDocumentRetriever; LlamaIndex hierarchical parser docs |
| Layout-aware parsing | Unstructured docs; LayoutLM; DocLLM |
| Code chunking | Tree-sitter; LlamaIndex CodeSplitter; controlled code chunking study |
| Table chunking | Spreadsheet/table chunking paper; Unstructured table partitioning docs |
| Transcript chunking | Meeting transcript QA and speech/transcript retrieval papers |
