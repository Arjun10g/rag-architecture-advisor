# 01 — Literature Review: Chunking & Parsing Methods for Document Processing and NLP

## 1. Problem definition

Chunking is the act of converting long source material into smaller retrieval, indexing, or processing units. Parsing is the upstream act of turning a document into structured content before chunking: text blocks, sections, titles, tables, rows, code symbols, speaker turns, timestamps, page elements, bounding boxes, or syntax trees. In modern retrieval-augmented generation (RAG), chunking and parsing are not merely preprocessing utilities. They determine what the retriever can retrieve, what the reranker can rank, what the generator can ground its answer in, and what the evaluator can attribute.

A useful way to frame the problem is that chunking defines the **statistical support** available to downstream retrieval. A chunk that is too small may be precise but under-contextualized; a chunk that is too large may contain the answer but dilute the embedding signal. A chunk that ignores document structure may split a table row from its header, a function body from its signature, a legal clause from its section title, or a transcript answer from the speaker turn that resolves it. The retrieval failure then looks like a model failure, even though the actual causal factor is a representation failure created at ingestion time.

For document processing and NLP, chunking usually serves one or more of the following purposes:

- **Indexing**: convert source content into units that can be embedded, searched, filtered, and reranked.
- **Context construction**: choose the unit size that will later be placed into an LLM context window.
- **Evidence attribution**: preserve enough provenance to cite source pages, rows, functions, or turns.
- **Compression**: reduce long documents into semantically meaningful units before summarization or QA.
- **Incremental update**: make document changes re-indexable without reprocessing the entire corpus.
- **Evaluation**: produce units that can be judged against gold evidence spans or support labels.

The literature has moved from classical linear text segmentation toward hybrid document-aware strategies. Early NLP segmentation methods, such as TextTiling, attempted to infer topical boundaries from lexical cohesion. Contemporary RAG chunking inherits that goal but must also satisfy embedding-model behavior, vector index constraints, LLM context limits, citation needs, and operational ingestion requirements.

## 2. Historical arc: from text segmentation to retrieval-aware chunking

### 2.1 Classical topic segmentation

Classical text segmentation methods divide documents into topically coherent units. TextTiling is one of the canonical early methods: it identifies subtopic shifts by observing changes in lexical cohesion across adjacent blocks. This line of work treated segmentation as a discourse and topical-structure problem, often independent of a downstream generative model.

Modern chunking is related but not identical. A topical segment may be ideal for human reading but too large for dense retrieval. Conversely, a fixed 256-token segment may be index-efficient but semantically incomplete. The modern problem is therefore not just “find natural topic boundaries,” but “find units that optimize retrieval, grounding, and synthesis under operational constraints.”

### 2.2 Fixed and recursive chunking as engineering baselines

The simplest strategy is fixed-size chunking: split text into fixed character, word, sentence, or token windows with optional overlap. This remains the most common baseline because it is cheap, predictable, and easy to ablate. Recursive chunking improves on fixed chunking by attempting larger natural separators first—paragraphs, line breaks, spaces—and only falling back to smaller units when size constraints are violated. LangChain’s RecursiveCharacterTextSplitter popularized this engineering pattern for RAG systems.

The important lesson from recent studies is that fixed-size chunking is not always a weak baseline. In several retrieval settings, especially where documents are homogeneous and answer-bearing text is locally dense, fixed or recursive chunking can perform surprisingly well. Its weaknesses become more visible when answers depend on headings, tables, code structure, multi-hop evidence, pronouns, or layout.

### 2.3 Content-aware and semantic chunking

Semantic chunking tries to detect boundaries using embeddings or semantic similarity. Instead of splitting every `n` tokens, it compares adjacent sentences or sentence groups and inserts a split when semantic similarity drops below a threshold or when a percentile-based breakpoint is reached. This approach is attractive because it aligns chunk boundaries with content shifts rather than arbitrary length limits.

Recent work such as *Document Segmentation Matters for Retrieval-Augmented Generation* and cross-domain chunking studies suggests that content-aware segmentation can improve retrieval over naive fixed windows, but results are not uniform. Semantic chunking introduces new tuning problems: embedding model choice, similarity threshold, sentence buffer size, language segmentation, and cost of pre-embedding for boundary detection. It can also over-merge subtly shifting topics or over-split noisy text.

### 2.4 Proposition-level indexing

Dense X Retrieval introduced the idea of indexing propositions rather than ordinary passages. A proposition is an atomic, self-contained expression of a fact. The intuition is that retrieval often fails because chunks contain multiple facts, unclear pronouns, or irrelevant surrounding material. If an LLM rewrites each passage into self-contained propositions, dense retrieval can match queries to the exact fact more directly.

This is a major conceptual shift: the retrieval unit is no longer a literal source span, but a derived semantic representation. That can improve fact recall and reduce prompt waste, but it adds extraction cost and potential transformation error. Proposition chunking is best understood as **semantic normalization before retrieval**. It is especially useful for fact-dense corpora, compliance rules, entity-attribute lookup, and knowledge bases. It is less obviously ideal for narrative, argumentative, or procedural documents where the meaning depends on discourse flow.

### 2.5 Late chunking

Late chunking reverses the usual ordering. In ordinary chunking, we split first and embed each chunk independently. In late chunking, a long-context embedding model first processes the whole document or long span, and chunk vectors are produced afterward by pooling contextualized token embeddings over desired chunk spans. The benefit is that local chunk embeddings can inherit document-level context.

This matters when local text is context-dependent: pronouns, abbreviated references, section-local definitions, or named entities introduced earlier. Standard chunking may embed “this method” or “the former approach” without the antecedent. Late chunking can create a vector that reflects the wider document context. The cost is higher memory and compute, plus dependency on compatible long-context embedding architectures.

### 2.6 Hierarchical and parent-child retrieval

Parent-child strategies separate the retrieval unit from the generation unit. Small child chunks are embedded and searched because they produce sharper retrieval signals; larger parent chunks or parent documents are returned to the generator because they preserve enough context for synthesis. LlamaIndex hierarchical node parsers and LangChain’s ParentDocumentRetriever are common implementations of this pattern.

This approach is a practical compromise between precision and context. It is useful when a query should match a small span but the answer requires a larger surrounding section. However, parent expansion can also reintroduce irrelevant content, increasing context-window cost and potentially hurting grounded generation.

### 2.7 Layout-aware parsing

For PDFs, forms, invoices, scanned documents, reports, and multi-column pages, plain text splitting is often the wrong abstraction. Layout-aware parsing first extracts typed elements: titles, paragraphs, list items, tables, images, page breaks, and sometimes bounding boxes. Chunking can then preserve page boundaries, section titles, table boundaries, or element groups.

Layout-aware models such as LayoutLM and DocLLM show why visual structure matters at the model level. Practical tools such as Unstructured operationalize this by partitioning documents into elements and offering chunking strategies such as `by_title` and `by_page`. In such documents, the biggest failure mode is often not chunk size; it is broken reading order, lost table context, OCR error, or title misclassification.

### 2.8 Structure-aware parsing for code, tables, and transcripts

Document-type-specific chunking has become increasingly important.

For **code**, syntax matters. Splitting in the middle of a function, class, import block, or docstring can destroy meaning. AST-aware parsing with tools like Tree-sitter can preserve syntactic units, but recent controlled code-RAG evidence shows that naive function-level chunking is not automatically superior. Sliding-window and AST-derived strategies can be stronger than function-only chunks, especially when cross-file context matters.

For **tables**, row and header structure matters. Flattening a table into plain text can separate values from headers or merge unrelated rows. Structure-aware table chunking preserves rows, key-value relationships, column headers, and sheet/table boundaries.

For **transcripts**, speaker turns and time matter. A relevant answer may depend on a question in one turn, an answer in the next, and clarification several turns later. Transcript chunking should preserve speaker labels, timestamps, and adjacent-turn context. ASR and diarization errors become part of the parsing problem.

## 3. Key empirical findings from the recent literature

### 3.1 Fixed baselines remain important

Multiple recent studies keep fixed or recursive splitting as a baseline because it is cheap and competitive. This is important methodologically: any proposed chunking method should be compared against fixed and recursive baselines under the same embedding model, retriever, reranker, top-k, and context budget.

Practical implication: do not adopt semantic, proposition, or late chunking without an ablation. The added complexity must beat a simple baseline on the actual target workload.

### 3.2 Content-aware segmentation often helps, but not universally

Studies comparing segmentation strategies generally find that content-aware methods can improve retrieval when boundary quality matters. Paragraph grouping, semantic splitting, and proposition-level indexing can help because they reduce arbitrary boundary cuts and improve semantic coherence. However, the gains depend on domain, task, retriever, and evaluation metric. Chunking interacts with embedding model behavior; the same segmentation may behave differently with BM25, dense retrieval, hybrid retrieval, ColBERT-style late interaction, or reranking.

Practical implication: evaluate chunking as part of the full retrieval stack, not as an isolated preprocessing choice.

### 3.3 Smaller chunks improve precision but can damage recall and cost

Small chunks tend to produce cleaner retrieval hits and less distractor content. But they increase index size, top-k fragmentation, duplication under overlap, and risk of losing needed context. They may also require parent expansion or post-retrieval merging to be useful for generation.

Practical implication: the optimal chunk size is not just a retrieval metric optimum. It must be selected relative to context construction and generator behavior.

### 3.4 Propositions are powerful for atomic facts

Proposition chunking is especially relevant when the retrieval target is an atomic statement. It can make chunks self-contained, reduce pronoun ambiguity, and avoid retrieving long passages for one fact. The tradeoff is that it uses an LLM to transform source text, which introduces cost, latency, and possible semantic drift.

Practical implication: use proposition indexing for fact-dense retrieval, but preserve links back to original source spans and evaluate extraction correctness.

### 3.5 Late chunking is targeted at context-dependent spans

Late chunking directly addresses a weakness of independent chunk embeddings: a chunk’s vector cannot encode information outside the chunk. When a passage depends on earlier definitions or antecedents, late chunking can help. But it requires long-context embedding and higher preprocessing cost.

Practical implication: late chunking is not a default replacement for recursive chunking. It is a specialized tool for long documents where local spans need global context.

### 3.6 Parsing failures often dominate chunk-size failures

In tables, PDFs, code, and transcripts, the main failure often occurs before chunking. If the parser destroys structure, the chunker cannot recover it. Examples include broken PDF reading order, table headers detached from rows, code symbols split from dependencies, or transcript turns stripped of speakers.

Practical implication: for structured or semi-structured documents, choose the parser before choosing the chunk size.

## 4. Conceptual axes for comparing methods

A useful literature review should not only list methods; it should place them along meaningful axes.

### 4.1 Boundary source

- **Length-derived**: fixed token/character windows.
- **Separator-derived**: recursive paragraph/sentence/separator splits.
- **Semantic-derived**: embedding similarity or topic shifts.
- **LLM-derived**: proposition extraction or document rewriting.
- **Structure-derived**: AST, table rows, layout elements, speaker turns.
- **Model-derived**: late chunking from contextualized token embeddings.

### 4.2 Retrieval unit versus generation unit

- Same unit: retrieve a chunk and pass that exact chunk to the generator.
- Small-to-large: retrieve children, pass parents.
- Derived-to-source: retrieve propositions, pass original parent source.
- Layout-to-text: retrieve element chunks, pass reconstructed page/section context.

### 4.3 Provenance fidelity

- High: literal source spans with page/line/row/function metadata.
- Medium: merged source chunks with preserved metadata ranges.
- Low: generated propositions or summaries unless back-linked to exact source spans.

### 4.4 Cost profile

- Low: fixed, recursive.
- Medium: sentence-window, parent-child, layout-aware text partitioning.
- High: semantic boundary detection, proposition extraction, OCR-heavy layout parsing, late chunking.

### 4.5 Failure target

Each advanced method is best understood as a response to a specific failure:

| Failure target | Method response |
|---|---|
| Arbitrary boundary cuts | Recursive, semantic, paragraph grouping |
| Missing local context | Sentence-window, parent-child |
| Atomic fact buried in long chunk | Proposition chunking |
| Pronouns/definitions outside local span | Late chunking |
| Table/header separation | Table-aware parsing |
| Code syntax fragmentation | AST-aware parsing |
| PDF reading-order/layout errors | Layout-aware parsing |
| Speaker/time ambiguity | Transcript-aware parsing |

## 5. What the literature does not yet settle

The evidence base is improving but still incomplete.

First, many results are domain-specific. Wikipedia QA, web passage ranking, code completion, spreadsheet retrieval, and meeting transcript QA are different problems. A method that improves one may not transfer.

Second, public benchmarks underrepresent enterprise document types. Many real RAG systems operate over contracts, PDFs, presentations, tickets, wiki pages, logs, spreadsheets, policies, meeting transcripts, and code repositories. These often need custom gold sets.

Third, there is limited controlled evidence for some widely used framework patterns. Sentence-window and parent-child retrieval are intuitively strong and practically useful, but fewer published cross-domain studies isolate them compared with fixed, semantic, proposition, late, and code-aware chunking.

Fourth, many studies report retrieval metrics but not full end-to-end answer quality, citation faithfulness, latency, index growth, ingestion cost, or update complexity. For production systems, these operational metrics are not optional.

## 6. Synthesis

The strongest synthesis is conditional:

- Use **recursive chunking** as the first baseline for ordinary prose.
- Use **layout-aware parsing** before chunking for PDFs, forms, reports, and scanned documents.
- Use **row/header-preserving chunking** for tables and spreadsheets.
- Use **AST-aware or sliding-window code chunking** for code repositories, but do not assume function-only chunks are optimal.
- Use **sentence-window** when exact evidence is sentence-level but generation needs local context.
- Use **parent-child** when retrieval benefits from small chunks but generation needs larger context.
- Use **semantic chunking** when topic boundaries are visibly harming retrieval.
- Use **proposition chunking** when atomic fact recall is the bottleneck.
- Use **late chunking** when local spans are context-dependent and long-context embedding is affordable.

In other words, chunking should be selected by diagnosed failure mode, not by popularity.
