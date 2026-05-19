# 02 — Strategy Catalog: Parameters, Failure Modes, and Use Cases

This file is the operational catalog. Each strategy is described in terms of algorithm, parameters, implementation choices, failure modes, best-fit use cases, and evaluation signals.

## 1. Fixed-size chunking

### Definition

Fixed-size chunking splits text into uniform spans by character count, word count, sentence count, or token count. Optional overlap duplicates a trailing part of one chunk at the start of the next chunk to reduce boundary loss.

### Algorithm

1. Normalize or extract text.
2. Choose a length function: characters, whitespace tokens, model tokens, words, or sentences.
3. Slide a window of size `chunk_size` through the text.
4. Move by `chunk_size - overlap`.
5. Attach document metadata to each chunk.

### Core parameters

| Parameter | Meaning | Typical effect |
|---|---|---|
| `chunk_size` | Maximum unit length. | Larger chunks improve context but dilute embeddings; smaller chunks improve precision but can fragment evidence. |
| `chunk_overlap` | Amount repeated between adjacent chunks. | Reduces boundary loss but increases index size and duplicate retrieval. |
| `length_function` | Characters, tokens, words, or sentences. | Token-aware splitting better matches embedding/generator limits. |
| `stride` | Window movement size. | Smaller stride means more overlap and more chunks. |
| `metadata_policy` | Page, section, title, position, source path, timestamp. | Crucial for citation and reconstruction. |

### Strengths

- Very simple.
- Cheap and deterministic.
- Good ablation baseline.
- Works acceptably on homogeneous prose.
- Easy to update incrementally.

### Failure modes

| Failure mode | Description | Symptom |
|---|---|---|
| Boundary amputation | A fact, sentence, table row, function, or heading is split across chunks. | Retriever returns partial evidence; generator hallucinates missing part. |
| Embedding dilution | Large chunk contains too many unrelated concepts. | Relevant chunk has lower similarity than a smaller unrelated chunk. |
| Duplicate retrieval | Overlap causes near-duplicate chunks to fill top-k. | Reranker or generator sees redundant context. |
| Structure blindness | Ignores titles, tables, code syntax, page layout, speaker turns. | Correct text exists but lacks necessary context. |
| Token mismatch | Character length does not map cleanly to model tokens. | Chunk unexpectedly exceeds embedding or generation limits. |

### When to use

Use fixed chunking when you need a cheap baseline, the corpus is plain prose, latency and ingestion cost matter, or you are running a factorial ablation. Do not use it as the only strategy for tables, code, layout-heavy PDFs, or transcripts unless a controlled evaluation shows it works.

### Evaluation signals

- Recall@k improves when chunk size increases, then may plateau.
- Precision@k often improves when chunk size decreases.
- Duplicate rate increases with overlap.
- Answer faithfulness may fall when chunks are too small.
- Context utilization may fall when chunks are too large.

## 2. Recursive chunking

### Definition

Recursive chunking attempts to preserve natural boundaries by trying a list of separators in order. It first splits by larger units such as paragraphs; if chunks are still too large, it recursively tries smaller units such as lines, spaces, and characters.

### Algorithm

1. Choose ordered separators, for example: paragraph break, newline, space, empty string.
2. Attempt to split the document using the first separator.
3. If pieces exceed the target size, recursively split those pieces using the next separator.
4. Merge pieces into chunks up to `chunk_size`, applying overlap if configured.
5. Preserve metadata.

### Core parameters

| Parameter | Meaning | Notes |
|---|---|---|
| `separators` | Ordered list of split boundaries. | Should be customized for Markdown, HTML, code, Chinese/Japanese/Thai, legal docs, etc. |
| `chunk_size` | Target maximum length. | Should usually be token-aware for embedding/generation. |
| `chunk_overlap` | Overlap between chunks. | Useful for prose; dangerous if it creates duplicate-heavy retrieval. |
| `keep_separator` | Whether separators remain in chunks. | Keeping headers or delimiters can preserve context. |
| `is_separator_regex` | Whether separators are regex patterns. | Useful for section numbering and heading patterns. |

### Strengths

- Better than fixed chunking for ordinary prose.
- Still cheap and deterministic.
- Easy to reason about.
- Common framework support.
- Good default baseline for RAG.

### Failure modes

| Failure mode | Description | Mitigation |
|---|---|---|
| Separator mismatch | Default separators do not match the corpus. | Customize separators by document type. |
| Header loss | Section titles become separated from body text. | Attach heading metadata or use layout/Markdown-aware parsing. |
| Bad language assumptions | Whitespace-based splitting fails for languages without spaces. | Add language-specific punctuation and zero-width separator rules. |
| Non-text structure blindness | Tables/code/layout are treated as plain text. | Use specialized parser before recursive splitting. |
| Overlap inflation | Large overlap bloats index. | Measure duplicate top-k and index size. |

### When to use

Use recursive chunking as the default first-line strategy for plain text, Markdown-like documents, wiki pages, manuals, documentation, policies, and long prose where headings/paragraphs are meaningful but specialized structure is limited.

## 3. Sentence-window chunking

### Definition

Sentence-window chunking indexes small units—often individual sentences—but stores surrounding sentences as metadata. At retrieval time, the system retrieves the precise sentence and then expands it into a local window for generation.

### Algorithm

1. Parse text into sentences.
2. Create one node per sentence or small sentence group.
3. For each node, store previous and next `n` sentences in metadata.
4. Embed only the target sentence or target sentence plus selected metadata, depending on configuration.
5. Retrieve sentence-level nodes.
6. Replace retrieved nodes with their windowed context before generation.

### Core parameters

| Parameter | Meaning | Typical effect |
|---|---|---|
| `sentence_splitter` | Rule-based or model-based sentence segmentation. | Errors propagate directly into retrieval units. |
| `window_size` | Number of sentences before/after retrieved sentence. | Larger windows improve context but add tokens. |
| `embed_policy` | Whether to embed only the sentence or include context. | Sentence-only is precise; sentence+window may improve context-sensitive matching. |
| `metadata_replacement_policy` | Whether retrieved sentence is replaced by expanded window for LLM input. | Required for generation context benefits. |
| `prev_next_relations` | Links among adjacent sentence nodes. | Enables expansion and graph-like traversal. |

### Strengths

- High retrieval precision.
- Good evidence localization.
- Local context available without embedding large chunks.
- Useful for citation-sensitive QA.

### Failure modes

| Failure mode | Description | Symptom |
|---|---|---|
| Sentence splitter error | Abbreviations, headings, OCR text, or transcripts break sentence parsing. | Chunks are unnatural or incomplete. |
| Window too small | Answer depends on context outside the window. | Generator lacks needed premise. |
| Window too large | Sentence precision is lost at generation time. | Context includes distractors. |
| Metadata not injected | Framework stores window metadata but LLM receives only sentence. | No improvement despite correct retrieval. |
| Cross-section leakage | Window crosses section boundary incorrectly. | Context mixes unrelated topics. |

### When to use

Use sentence-window chunking when you need precise evidence retrieval but the generator needs a small amount of neighboring context. It is especially useful for policy documents, academic papers, documentation, legal clauses, and support articles where sentence-level facts are meaningful.

## 4. Semantic chunking

### Definition

Semantic chunking groups adjacent sentences or paragraphs based on semantic similarity. Boundaries are inserted when the semantic relationship between neighboring units drops below a threshold or crosses a percentile breakpoint.

### Algorithm

1. Split document into candidate units, typically sentences.
2. Optionally group each sentence with a buffer of neighboring sentences.
3. Embed each unit or buffered unit.
4. Compute similarity or distance between adjacent units.
5. Insert breakpoints where distance is high or similarity is low.
6. Merge units into semantically coherent chunks, optionally enforcing a max size.

### Core parameters

| Parameter | Meaning | Notes |
|---|---|---|
| `embedding_model` | Model used to estimate boundary similarity. | Boundary quality depends heavily on this model. |
| `buffer_size` | Number of adjacent sentences included when embedding candidate units. | Smooths noisy sentence-level similarity. |
| `breakpoint_threshold` | Distance or similarity cutoff. | The most sensitive parameter. |
| `breakpoint_percentile` | Percentile of dissimilarity used as cut threshold. | More portable than an absolute similarity threshold. |
| `max_chunk_size` | Hard upper bound. | Prevents huge segments. |
| `min_chunk_size` | Hard lower bound. | Prevents tiny fragments. |

### Strengths

- Boundary decisions reflect content rather than length alone.
- Can improve topic coherence.
- Useful when documents contain natural topical sections that are not reliably marked by headings.

### Failure modes

| Failure mode | Description | Mitigation |
|---|---|---|
| Threshold instability | Slight parameter changes produce different boundaries. | Tune on validation set; inspect boundary histograms. |
| Embedding mismatch | Boundary model does not match retrieval model or domain. | Use same or domain-adapted embedding model. |
| Over-merging | Subtle topic shifts are missed. | Lower threshold or add max chunk size. |
| Over-splitting | Noisy sentence embeddings create too many chunks. | Increase buffer or min chunk size. |
| High preprocessing cost | Requires embedding pass before final indexing. | Cache boundary embeddings. |

### When to use

Use semantic chunking when documents are prose-heavy, topic shifts are not reliably marked, and fixed/recursive chunking creates mixed-topic chunks or splits coherent sections. Avoid it as a default for tables, code, and scanned PDFs unless parsing has already converted them into reliable text segments.

## 5. Proposition chunking

### Definition

Proposition chunking rewrites source text into atomic, self-contained factual statements and indexes those statements. The retrieved proposition is typically linked back to its parent source passage.

### Algorithm

1. Split source documents into manageable passages.
2. Use an LLM or structured extractor to generate atomic propositions.
3. Filter or validate propositions for self-containment and fidelity.
4. Embed propositions as retrieval units.
5. Store parent passage, document, page, and span metadata.
6. Retrieve propositions.
7. Optionally expand retrieved propositions to parent chunks for generation.

### Core parameters

| Parameter | Meaning | Notes |
|---|---|---|
| `base_chunk_size` | Size of source passage used for proposition extraction. | Too large increases extraction omissions; too small loses context. |
| `proposition_prompt` | Instructions for atomic extraction. | Determines granularity and self-containment. |
| `max_propositions_per_chunk` | Extraction cap. | Prevents explosion. |
| `deduplication_policy` | Removes repeated propositions. | Needed for overlapping base chunks. |
| `parent_link_policy` | How proposition maps back to source. | Crucial for citations. |
| `validation_policy` | Human, LLM, or rule-based check. | Reduces hallucinated propositions. |

### Strengths

- Very strong for atomic fact retrieval.
- Reduces embedding dilution.
- Makes implicit pronouns or references explicit.
- Can improve prompt efficiency by retrieving compact facts.

### Failure modes

| Failure mode | Description | Symptom |
|---|---|---|
| Extraction hallucination | Proposition states something not supported. | Retrieved evidence is false despite source being correct. |
| Discourse loss | Atomic facts omit qualifiers, exceptions, or dependencies. | Generator overgeneralizes. |
| Index explosion | Many propositions per source chunk. | Higher cost and latency. |
| Provenance ambiguity | Proposition cannot be mapped to exact source span. | Weak citations. |
| Over-atomization | A relation requiring multiple facts is split too aggressively. | Multi-hop synthesis worsens. |

### When to use

Use proposition chunking for fact-dense corpora, definitions, compliance rules, scientific claims, knowledge bases, product specs, and entity-attribute lookup. Avoid using it alone for narrative, procedural, argumentative, or highly context-dependent documents unless parent expansion is included.

## 6. Late chunking

### Definition

Late chunking embeds a long document first and then pools contextualized token embeddings into chunk vectors after the transformer has processed the full context. This differs from ordinary chunking, where chunks are split first and embedded independently.

### Algorithm

1. Tokenize a long document or long span.
2. Run a long-context embedding model over the full sequence.
3. Retain token-level contextual embeddings.
4. Define chunk spans after the model pass.
5. Pool token embeddings for each span to create chunk vectors.
6. Index span-level vectors with source metadata.

### Core parameters

| Parameter | Meaning | Notes |
|---|---|---|
| `long_context_embedder` | Embedding model that can process long inputs. | Core requirement. |
| `span_size` | Token span used for chunk vectors. | Can be smaller than ordinary chunk size because context is inherited. |
| `pooling_method` | Mean pooling, weighted pooling, etc. | Must match model assumptions. |
| `document_window` | How much source text is embedded at once. | Limited by model context and memory. |
| `boundary_policy` | How spans are selected. | Can be fixed, sentence-aware, or section-aware. |

### Strengths

- Handles context-dependent local mentions.
- Improves embeddings for spans with pronouns, ellipsis, or earlier definitions.
- Can retain retrieval precision while using document-level context.

### Failure modes

| Failure mode | Description | Symptom |
|---|---|---|
| Model incompatibility | Embedding model does not expose useful token embeddings or long context. | Cannot implement or gets weak vectors. |
| High compute/memory | Long-document embedding is expensive. | Ingestion bottleneck. |
| Truncation loss | Full needed context exceeds model limit. | Late chunking fails silently. |
| Pooling mismatch | Mean pooling over bad spans blurs meaning. | Retrieval quality unstable. |
| Limited benefit on self-contained chunks | If chunks already contain all needed context, added cost is wasted. | No measurable gain over recursive baseline. |

### When to use

Use late chunking for long documents where independent chunk embeddings fail because local spans depend on earlier context: legal documents, academic papers, technical manuals, narrative reports, and documents with heavy cross-reference.

## 7. Parent-child and hierarchical chunking

### Definition

Parent-child chunking indexes small child chunks but returns larger parent chunks or sections to the generator. Hierarchical chunking generalizes this to multiple levels: document, section, paragraph, sentence.

### Algorithm

1. Parse the document into parent units, such as sections.
2. Split each parent into child chunks, such as paragraphs or sentences.
3. Embed child chunks.
4. Store parent-child relationships.
5. Retrieve children.
6. Replace or augment retrieved children with parent context.
7. Optionally merge nearby siblings.

### Core parameters

| Parameter | Meaning | Notes |
|---|---|---|
| `parent_size` | Size of returned context. | Too large adds noise; too small loses synthesis context. |
| `child_size` | Size of indexed unit. | Smaller improves precision but increases node count. |
| `child_overlap` | Overlap among child chunks. | Reduces boundary loss but can duplicate retrieval. |
| `merge_threshold` | Number/fraction of child hits needed before returning parent. | Used in automerging retrievers. |
| `hierarchy_levels` | Section/paragraph/sentence levels. | More levels increase flexibility and complexity. |

### Strengths

- Balances retrieval precision and generation context.
- Useful for long documents and section-level answers.
- Preserves provenance relationships.
- Can reduce prompt fragmentation.

### Failure modes

| Failure mode | Description | Symptom |
|---|---|---|
| Parent noise | Retrieved child expands to a large irrelevant parent. | Generator sees distractors. |
| Relationship bugs | Parent-child metadata is missing or wrong. | Retrieved evidence cannot be expanded. |
| Over-merging | Too many siblings are merged. | Context budget wasted. |
| Under-merging | Related child hits remain isolated. | Answer lacks full context. |
| Update complexity | Parent and child indices must stay synchronized. | Stale or inconsistent retrieval. |

### When to use

Use parent-child retrieval when exact matches are local but answers require larger context. Examples include manuals, policy sections, contracts, academic articles, and technical documentation.

## 8. Layout-aware chunking

### Definition

Layout-aware chunking parses documents into typed visual or structural elements before chunking. Units may include titles, narrative text, tables, list items, figures, captions, page breaks, or bounding-box-defined regions.

### Algorithm

1. Detect document type.
2. Partition document into elements using parser/OCR/layout model.
3. Preserve element metadata: type, page, coordinates, section, order.
4. Chunk by element, title, page, or custom grouping.
5. Keep tables separate or chunk them with table-specific logic.
6. Attach citation metadata.

### Core parameters

| Parameter | Meaning | Notes |
|---|---|---|
| `partition_strategy` | Fast text extraction, OCR-only, high-resolution layout inference. | Determines cost and quality. |
| `chunking_strategy` | Basic, by-title, by-page, custom element grouping. | Determines semantic and layout preservation. |
| `max_characters` | Hard chunk cap. | Prevents oversized chunks. |
| `new_after_n_chars` | Soft chunk cap. | Encourages manageable chunk sizes. |
| `combine_text_under_n_chars` | Merges tiny elements. | Prevents header-only chunks. |
| `include_page_breaks` | Page boundary preservation. | Important for citations and forms. |
| `table_handling` | Extract table as HTML, CSV, markdown, or structured rows. | Critical for tabular QA. |

### Strengths

- Preserves document structure.
- Enables page-accurate citations.
- Handles multi-column and visually rich documents better than raw text splitting.
- Can preserve tables and titles.

### Failure modes

| Failure mode | Description | Mitigation |
|---|---|---|
| OCR noise | Text is incorrectly recognized. | Use OCR confidence, human audit, preprocessing. |
| Reading-order error | Multi-column or floating elements are sequenced incorrectly. | Layout model, manual sampling, visual QA. |
| Title misclassification | Body text is treated as title or vice versa. | Tune parser and postprocess headings. |
| Table fragmentation | Table split into unrelated text blocks. | Use table-specific extraction. |
| Page artifact | Header/footer repeated in chunks. | Remove boilerplate by page position. |

### When to use

Use layout-aware chunking for PDFs, scanned documents, contracts, invoices, forms, slide decks, annual reports, scientific PDFs, brochures, and any document where visual structure affects meaning.

## 9. Comparative strategy summary

| Strategy | Best for | Avoid when | Cost | Main risk |
|---|---|---|---|---|
| Fixed | Baselines, simple prose | Structured docs | Low | Arbitrary splits |
| Recursive | General prose | Tables/code/layout without parsing | Low-medium | Separator mismatch |
| Sentence-window | Precise evidence + local context | Long-range dependencies | Medium | Window too small/large |
| Semantic | Topic-aware prose segmentation | Noisy or structured text | Medium-high | Threshold instability |
| Proposition | Atomic fact retrieval | Narrative/procedural docs alone | High | Extraction drift |
| Late chunking | Context-dependent spans | Short/simple chunks | High | Compute/memory cost |
| Parent-child | Precision retrieval + broad synthesis | Very tight context budgets | Medium-high | Parent noise |
| Layout-aware | PDFs/forms/reports | Plain text only | Medium-high | OCR/layout errors |
