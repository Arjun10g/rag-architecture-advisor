# 04 — Gold-Set Construction Methodology

## Why public benchmarks are not enough

Public benchmarks help compare models, but they rarely match a real RAG application. A private RAG system has its own corpus, document types, user intents, update frequency, compliance constraints, citation requirements, and abstention policy. Public benchmarks also usually do not evaluate parser fidelity, chunk boundaries, table preservation, code scope, transcript speaker turns, or document freshness.

A domain gold set should therefore define **what a good system should retrieve, cite, and answer** for representative user needs.

---

## Gold-set object model

Each evaluation item should contain more than a question and answer.

```yaml
id: unique-question-id
query: user-facing question
query_type: factual | procedural | comparison | synthesis | multi-hop | summarization | update | refusal
domain: policy | legal | scientific | support | code | finance | etc.
source_documents:
  - doc_id
  - version
  - date
  - section
  - page_or_span
reference_contexts:
  - chunk_id
  - span_start
  - span_end
  - relevance_label: required | useful | background | distractor | harmful
reference_answer: expected answer or answer rubric
acceptable_variants:
  - alternate wording
must_cite:
  - doc_id / page / section / span
should_abstain: true/false
abstention_reason: insufficient evidence | conflicting evidence | out of scope | unsafe | stale source
expected_claims:
  - claim text
  - supporting source span
  - required: true/false
negative_contexts:
  - plausible but wrong chunk
  - outdated chunk
  - semantically similar distractor
metadata:
  difficulty: easy | medium | hard
  hop_count: 1 | 2 | 3+
  freshness_sensitive: true/false
  parser_sensitive: true/false
  chunking_sensitive: true/false
```

This object model makes it possible to evaluate retrieval, generation, citation, and abstention separately.

---

## Query sampling strategy

A good gold set should be stratified. Do not build only easy FAQ questions.

| Query category | Purpose | Example |
|---|---|---|
| Head queries | High-frequency user needs | “What is the refund policy?” |
| Tail queries | Rare but important issues | “What happens if refund is requested after partial service delivery?” |
| Procedural queries | Steps and workflow | “How do I escalate a failed invoice sync?” |
| Comparison queries | Distinguish similar entities | “Which plan supports SSO but not SCIM?” |
| Multi-hop queries | Combine sources | “Which customers affected by policy X also use feature Y?” |
| Table queries | Test structured data | “What is the threshold in row 4 for enterprise accounts?” |
| Code queries | Test AST/scope retrieval | “Where is retry logic implemented for ingestion failures?” |
| Transcript queries | Test speaker/time context | “What did Maya commit to after the pricing discussion?” |
| Negative/unanswerable | Test abstention | “What is the 2027 pricing plan?” when corpus lacks it |
| Conflict/freshness | Test source adjudication | Old policy says 30 days, new policy says 14 days |
| Adversarial distractor | Test robustness | Semantically similar but wrong product/version |

---

## Evidence labeling

For RAG, relevance should be graded rather than binary.

| Label | Meaning | Retrieval use | Generation use |
|---|---|---|---|
| Required | Answer cannot be correct without this evidence | Must be retrieved | Must support one or more claims |
| Useful | Helps answer but not strictly required | Should be retrieved | Can enrich answer |
| Background | Topically related but not answer-bearing | Optional | Should not dominate |
| Distractor | Similar but not useful | Should be ranked low | Should be ignored |
| Harmful | Outdated, false, conflicting, or unsafe | Should be excluded or flagged | Should not be used without caveat |

Graded labels support nDCG@k and richer error analysis than binary recall.

---

## Reference answer construction

Reference answers should be written as rubrics, not only exact strings.

### Good reference answer fields

- **Minimal correct answer**: The shortest acceptable answer.
- **Complete answer**: A fuller answer with important conditions.
- **Required claims**: Atomic claims that must appear.
- **Forbidden claims**: Common hallucinations or outdated statements.
- **Citation requirements**: Which claims need which sources.
- **Abstention criteria**: When the system should say it cannot answer.
- **Style constraints**: Desired length, tone, format, or table output.

This prevents metrics from penalizing correct alternate wording and makes LLM judges easier to calibrate.

---

## Building the set

### Step 1 — Corpus profiling

Document the corpus before sampling:

- document types: PDFs, Markdown, HTML, code, tables, transcripts, emails
- parser used
- chunking strategy
- versioning/freshness metadata
- source authority hierarchy
- sensitive or regulated categories
- expected user intents

### Step 2 — Candidate query generation

Use a mix of:

- production logs, if available
- SME-authored questions
- synthetic generation from documents
- failure-driven questions from bug reports
- benchmark-inspired templates
- adversarial variations

Synthetic generation is useful for coverage, but it should be reviewed by humans before becoming a gold item.

### Step 3 — Human review

Subject-matter experts should verify:

- the question is realistic
- the reference evidence is correct
- the answer is complete
- the item is not ambiguous
- negative cases truly require abstention
- citations point to exact support spans

### Step 4 — Inter-annotator agreement

Have at least two annotators label a subset. Measure agreement for:

- answer correctness labels
- required evidence spans
- relevance grades
- abstention decisions
- citation support

Disagreements should be adjudicated and converted into rubric improvements.

### Step 5 — Split into eval sets

Use separate sets:

| Split | Purpose |
|---|---|
| Development set | Used repeatedly while tuning chunking, retrieval, prompts |
| Regression set | Stable CI suite to catch known failures |
| Blind test set | Held out for final comparisons |
| Stress set | Adversarial, conflict, freshness, and unanswerable items |
| Online audit set | Sampled from real production traffic and human-reviewed |

Never tune prompts, chunk sizes, or rerankers directly on the blind test set.

---

## Metrics enabled by a good gold set

| Gold labels available | Metrics unlocked |
|---|---|
| reference answer only | answer correctness, semantic similarity, RAGAS context recall via answer claims |
| reference contexts | Recall@k, Precision@k, nDCG@k, MRR, context recall |
| graded relevance | nDCG@k, graded context precision, evidence density |
| source spans | citation precision/recall, claim support, token-level evidence IoU |
| unanswerable labels | abstention precision/recall, false answer rate |
| conflict/freshness labels | source adjudication accuracy, stale-source error rate |
| per-claim support | faithfulness, groundedness, attribution quality |

---

## Evaluating chunking and parsing inside the gold set

Add flags for parser-sensitive and chunking-sensitive items.

| Failure | Gold-set indicator |
|---|---|
| Heading detached from body | required source includes heading + paragraph |
| Table flattened incorrectly | required source is a cell/header relation |
| Code scope lost | required source includes function/class and parent context |
| Transcript speaker lost | required source includes speaker identity |
| Multi-page PDF table split | required source spans pages |
| Chunk too small | answer requires neighboring chunk |
| Chunk too large | retrieval brings excessive irrelevant context |

This makes chunking and parsing measurable rather than anecdotal.

---

## Minimum viable gold-set sizes

| Stage | Suggested size | Purpose |
|---|---:|---|
| Smoke test | 20–50 | Catch obvious regressions |
| Development set | 100–300 | Compare chunking/retrieval/prompt variants |
| Domain release gate | 300–1,000 | Stable offline score with confidence intervals |
| High-stakes domain | 1,000+ plus ongoing audit | Reliability, subgroup analysis, rare failures |

The exact size depends on domain risk and query diversity. A small high-quality set is better than a large noisy synthetic set, but a tiny set cannot detect regressions reliably.

---

## Statistical reporting

Always report:

- mean score
- confidence interval or bootstrap interval
- per-category breakdown
- error counts by failure mode
- cost and latency
- judge model and version
- prompt/template version
- corpus version
- chunking and parser version

Without versioning, RAG evaluation becomes irreproducible.
