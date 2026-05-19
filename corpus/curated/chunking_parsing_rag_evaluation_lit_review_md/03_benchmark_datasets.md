# 03 — Benchmark Datasets

## Dataset map

| Benchmark | Primary purpose | Typical task | Best for | Not ideal for |
|---|---|---|---|---|
| BEIR | Heterogeneous zero-shot IR | Retrieval over many domains | Testing retriever generalization | End-to-end answer quality |
| MTEB | Embedding evaluation across tasks/languages | Retrieval, reranking, clustering, STS, classification | Model selection for embeddings | Full RAG answer/citation behavior |
| MS MARCO | Web-scale passage ranking and machine reading | Passage ranking, QA, answer generation | Search-like retrieval and ranking | Private-domain provenance/citation requirements |
| Natural Questions | Open-domain QA from real queries | Long/short answer extraction | Realistic open-domain QA | Multi-hop reasoning and domain-specific corpora |
| HotpotQA | Explainable multi-hop QA | Multi-document reasoning with supporting facts | Multi-hop retrieval and evidence aggregation | Simple single-hop lookup |
| KILT | Knowledge-intensive tasks with provenance | QA, fact checking, entity linking, slot filling | Provenance-aware retrieval/generation | Non-Wikipedia enterprise corpora |
| RGB | Robustness-oriented RAG benchmark | Noise robustness, negative rejection, integration, counterfactual robustness | Stress-testing RAG failure modes | General embedding leaderboard comparisons |
| CRUD-RAG | Scenario-oriented RAG benchmark | Create, Read, Update, Delete | Evaluating broader RAG use-cases beyond QA | English-only or purely retrieval-focused testing |

---

## 1. BEIR

BEIR is a heterogeneous benchmark for zero-shot information retrieval. It was created to address narrow and homogeneous evaluation settings in neural IR and includes 18 public datasets from diverse tasks and domains ([BEIR paper](https://arxiv.org/abs/2104.08663)).

### What it measures

BEIR measures whether a retriever generalizes across domains. Typical metrics include nDCG@k, Recall@k, Precision@k, and MAP. It is not an end-to-end RAG benchmark; it does not directly evaluate answer generation, groundedness, or citation quality.

### Use BEIR when

- You are selecting a retriever or embedding model before domain-specific gold data exists.
- You want to test zero-shot generalization.
- You want a retrieval baseline including BM25, dense, sparse, late-interaction, or reranking methods.
- You need evidence that a retriever works beyond one curated dataset.

### Failure modes

- Strong BEIR performance does not guarantee good private-domain RAG.
- It does not evaluate parsing, chunking, answer generation, or abstention.
- Public benchmark contamination is possible for heavily trained embedding models.
- Domain distributions may still differ from your application.

---

## 2. MTEB

MTEB evaluates text embeddings across many task families and languages. The original paper introduced 58 datasets across 8 tasks and 112 languages, and found that no single embedding method dominated across all tasks ([MTEB paper](https://arxiv.org/abs/2210.07316)).

### What it measures

MTEB measures embedding quality across retrieval, reranking, semantic textual similarity, classification, clustering, pair classification, bitext mining, and summarization-style tasks.

### Use MTEB when

- You are choosing an embedding model.
- You care about multilingual or cross-task behavior.
- You want broader evidence than a single retrieval dataset.
- You need a first-pass shortlist before expensive domain-specific evaluation.

### Failure modes

- MTEB scores are not RAG scores.
- High STS or classification performance may not translate to retrieval under your chunking scheme.
- The benchmark usually does not test parser/layout quality, citation behavior, or answer faithfulness.

---

## 3. MS MARCO

MS MARCO is based on anonymized Bing search queries and web passages. The original dataset includes over one million questions, human-generated answers, and millions of passages extracted from Bing-retrieved web documents ([MS MARCO paper](https://arxiv.org/abs/1611.09268)).

### What it measures

MS MARCO is central for passage ranking and web-search-like retrieval. It is often used to train and evaluate dense retrievers, cross-encoders, rerankers, and passage-ranking systems.

### Use MS MARCO when

- Your use-case resembles web search or customer-search queries.
- You are evaluating passage ranking, reranking, or answer extraction.
- You need large-scale training data for retrievers or rerankers.

### Failure modes

- It is not tailored to private enterprise corpora.
- It does not guarantee grounded synthesis quality.
- Its web-query distribution differs from legal, medical, scientific, or internal-document RAG.

---

## 4. Natural Questions

Natural Questions uses real user queries and Wikipedia pages, with long and short answer annotations. The official Google dataset remains the key source, and a BERT baseline paper is a common reference point for modeling on NQ ([Natural Questions dataset](https://ai.google.com/research/NaturalQuestions), [Natural Questions baseline note](https://arxiv.org/abs/1901.08634)).

### What it measures

NQ tests open-domain question answering with realistic query phrasing and evidence in long documents.

### Use NQ when

- You want open-domain QA with realistic user queries.
- You want to evaluate long-answer and short-answer extraction.
- You need a QA benchmark that is less synthetic than templated datasets.

### Failure modes

- NQ is mostly single-source/open-domain QA, not necessarily multi-hop.
- It is Wikipedia-centric.
- It does not directly test private corpus freshness, citation policy, or document layout parsing.

---

## 5. HotpotQA

HotpotQA contains 113k Wikipedia-based question-answer pairs requiring reasoning over multiple supporting documents, and it provides sentence-level supporting facts ([HotpotQA paper](https://arxiv.org/abs/1809.09600)).

### What it measures

HotpotQA is valuable for multi-hop retrieval, evidence aggregation, explainable QA, and supporting-fact prediction.

### Use HotpotQA when

- Your RAG system must combine information from multiple chunks/documents.
- You want to evaluate decomposition, multi-query retrieval, GraphRAG, reranking, or evidence chaining.
- You care about supporting-fact recall, not only final answer accuracy.

### Failure modes

- Multi-hop questions are still constrained by dataset construction.
- Systems can exploit shortcuts unless evaluated carefully.
- A high HotpotQA score does not guarantee robustness to conflicting or outdated evidence.

---

## 6. KILT

KILT standardizes multiple knowledge-intensive language tasks over a shared Wikipedia snapshot and evaluates both downstream performance and provenance ([KILT paper](https://arxiv.org/abs/2009.02252)).

### What it measures

KILT combines task performance with provenance expectations. Tasks include open-domain QA, fact checking, slot filling, entity linking, and dialogue.

### Use KILT when

- Provenance matters.
- You want to evaluate whether a model retrieves the right source, not just answers correctly.
- You want a benchmark spanning multiple knowledge-intensive tasks.

### Failure modes

- The shared knowledge source is Wikipedia, not private enterprise knowledge.
- Provenance metrics may not capture fine-grained citation-span faithfulness.
- Custom document types such as PDFs, tables, code, or transcripts require separate parser/chunker evaluation.

---

## 7. RGB

RGB, the Retrieval-Augmented Generation Benchmark, evaluates RAG models across four abilities: noise robustness, negative rejection, information integration, and counterfactual robustness ([RGB paper](https://arxiv.org/abs/2309.01431)).

### What it measures

RGB is designed around RAG-specific failure modes:

| Ability | Meaning |
|---|---|
| Noise robustness | Can the model answer correctly when irrelevant passages are present? |
| Negative rejection | Can the model refuse or abstain when retrieved evidence is insufficient? |
| Information integration | Can the model combine multiple pieces of evidence? |
| Counterfactual robustness | Can the model resist false or conflicting retrieved information? |

### Use RGB when

- You are testing robustness, not just retrieval relevance.
- You care about abstention, contradictions, and noisy top-k.
- You want to compare generator behavior under imperfect retrieval.

### Failure modes

- It is not a full replacement for application-specific gold sets.
- It may not represent your domain's real error distribution.
- It evaluates RAG abilities but not necessarily parser/layout/chunking fidelity.

---

## 8. CRUD-RAG

CRUD-RAG is a Chinese benchmark that broadens RAG evaluation beyond QA into Create, Read, Update, and Delete scenarios ([CRUD-RAG paper](https://arxiv.org/abs/2401.17043)).

### What it measures

| Scenario | RAG meaning |
|---|---|
| Create | Generate original or varied content using retrieved knowledge |
| Read | Answer knowledge-intensive questions |
| Update | Revise or correct existing text using external evidence |
| Delete | Summarize or compress long text |

### Use CRUD-RAG when

- You want to evaluate RAG as a general application pattern, not only QA.
- You need scenario-specific insight into how retrieval affects different generation tasks.
- You care about Chinese-language RAG.

### Failure modes

- Language and domain coverage may not match your app.
- Create/update/delete tasks often require human or LLM-judge evaluation.
- It may require adaptation for English or enterprise-domain workflows.

---

## Benchmark selection cheat sheet

| Goal | Recommended benchmark(s) |
|---|---|
| Pick an embedding model | MTEB first, then private retrieval gold set |
| Pick a retriever for zero-shot robustness | BEIR |
| Evaluate search-like passage ranking | MS MARCO |
| Evaluate open-domain QA | Natural Questions |
| Evaluate multi-hop retrieval and reasoning | HotpotQA |
| Evaluate provenance across knowledge-intensive tasks | KILT |
| Evaluate robustness to noisy/conflicting retrieval | RGB |
| Evaluate broader RAG applications beyond QA | CRUD-RAG |
| Evaluate private enterprise RAG | Build a gold set; optionally calibrate with BEIR/MTEB/MS MARCO insights |
