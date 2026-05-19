# 02 — Evaluation Frameworks and Metric Definitions

## 1. Evaluation layers

A practical RAG evaluation stack should separate at least six layers:

| Layer | Question | Example metrics |
|---|---|---|
| Parser fidelity | Did parsing preserve source structure? | reading-order accuracy, table structure accuracy, heading preservation, OCR error rate, metadata coverage |
| Chunk quality | Are chunks coherent, retrievable, and citation-friendly? | chunk boundary audits, token-level evidence coverage, duplication rate, orphan heading rate |
| Retrieval quality | Did the system retrieve the right evidence? | Recall@k, Precision@k, MRR, nDCG@k, context precision, context recall |
| Context construction | Is retrieved context ranked, deduplicated, and ordered well? | contextual precision, noise sensitivity, evidence density, lost-in-middle checks |
| Generation quality | Is the answer relevant, correct, complete, concise, and useful? | answer relevance, answer correctness, factual correctness, task success |
| Grounding and attribution | Are claims supported by retrieved evidence and citations? | faithfulness, groundedness, citation precision/recall, claim support rate |

The core problem is attribution of errors. If the final answer is bad, the cause might be parsing, chunking, retrieval, reranking, prompt construction, generation, or judging. A good framework should therefore log intermediate artifacts: parsed elements, chunks, retrieved candidates, reranked candidates, final context, generated answer, cited spans, and metric rationales.

---

## 2. RAGAS

### Source base

RAGAS was introduced as a reference-free evaluation framework for RAG pipelines, with metrics intended to evaluate retrieval, generation, and their interaction ([RAGAS paper](https://arxiv.org/abs/2309.15217)). The current docs list RAG metrics including context precision, context recall, context entities recall, noise sensitivity, response relevancy, and faithfulness ([RAGAS metrics docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)).

### Main metrics

| Metric | What it measures | Inputs | Approximate formula / scoring idea | Use when |
|---|---|---|---|---|
| Context Precision | Whether relevant retrieved chunks are ranked above irrelevant chunks | `user_input`, `retrieved_contexts`, optionally `reference` or `response` | Mean of precision@k at ranks containing relevant chunks; rewards placing relevant contexts early ([RAGAS context precision docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/)) | Comparing retrievers/rerankers and context ordering |
| Context Recall | Whether the retrieved contexts cover the information needed by the reference answer | `user_input`, `retrieved_contexts`, `reference` or `reference_contexts` | Claims in the reference supported by retrieved context divided by total reference claims ([RAGAS context recall docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/)) | Checking missing evidence and top-k adequacy |
| Response Relevancy / Answer Relevancy | Whether the response addresses the user input | `user_input`, `response` | Generate artificial questions from the response, embed them, and compare to the original query ([RAGAS response relevancy docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/)) | Detecting off-topic or incomplete answers |
| Faithfulness | Whether the answer is supported by retrieved context | `response`, `retrieved_contexts` | Supported answer claims divided by total answer claims ([RAGAS faithfulness docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)) | Detecting hallucination relative to supplied context |
| Context Entities Recall | Whether important named entities from the reference appear in retrieved context | `reference`, `retrieved_contexts` | Entity overlap / entity support | Entity-heavy factual QA |
| Noise Sensitivity | Whether irrelevant retrieved context degrades answer behavior | question, response, retrieved contexts, reference | Penalizes incorrect answer claims influenced by irrelevant context | Stress-testing noisy retrieval |

### Strengths

RAGAS is useful for rapid offline experimentation because it offers a compact metric suite that can be run without fully hand-labeling every intermediate artifact. It is especially useful during chunking/retrieval experiments when you need a common score sheet across many pipeline variants.

### Limitations

RAGAS metrics are not a substitute for human labels. Faithfulness depends on claim extraction and entailment judgments; answer relevancy can miss factual correctness; context recall depends on reference quality; and context precision can reward context that is relevant to the answer but not necessarily sufficient for the user intent. For high-stakes systems, RAGAS is best used as a screening layer plus error taxonomy, not as the sole release gate.

---

## 3. ARES

### Source base

ARES evaluates RAG systems along context relevance, answer faithfulness, and answer relevance. It creates synthetic training data, fine-tunes lightweight LM judges, and uses a small set of human annotations with prediction-powered inference to mitigate judge prediction error ([ARES paper](https://arxiv.org/abs/2311.09476)).

### Core dimensions

| ARES dimension | Meaning | Closest equivalents |
|---|---|---|
| Context relevance | Whether retrieved passages are relevant to the query | RAGAS context precision / TruLens context relevance / DeepEval contextual relevancy |
| Answer faithfulness | Whether the answer is supported by the retrieved passages | RAGAS faithfulness / TruLens groundedness / DeepEval faithfulness |
| Answer relevance | Whether the answer addresses the query | RAGAS response relevancy / TruLens answer relevance / DeepEval answer relevancy |

### Evaluation pattern

ARES is more involved than a pure plug-and-play metric. It is designed for settings where you want a **domain-adapted evaluator** rather than an off-the-shelf judge. The workflow is:

1. Generate synthetic data for RAG component evaluation.
2. Train lightweight judge models for each dimension.
3. Use a smaller human-labeled set to calibrate or correct estimates using prediction-powered inference.
4. Report system-level estimates with better statistical grounding than raw judge scores.

### Strengths

ARES is attractive when you have enough infrastructure to build a reusable evaluation service, when domain shift matters, or when you want to reduce dependence on expensive frontier LLM judges. It is also conceptually strong because it explicitly admits that automated judges are imperfect and uses human labels to improve estimation.

### Limitations

ARES adds setup cost. It requires synthetic data generation, judge training, and a human-labeled calibration set. It is therefore less convenient for very early prototyping than RAGAS or DeepEval. Its value increases when the RAG application is stable enough that reusable evaluators justify the setup cost.

---

## 4. TruLens

### Source base

TruLens describes the “RAG triad”: context relevance, groundedness, and answer relevance ([TruLens RAG triad docs](https://www.trulens.org/getting_started/core_concepts/rag_triad/)). Its retrieval ground-truth guide also supports classical IR evaluation such as hit rate, NDCG@k, recall@k, and semantic similarity against ground truth ([TruLens retrieval groundtruth docs](https://www.trulens.org/getting_started/quickstarts/groundtruth_evals_for_retrieval_systems/)).

### RAG triad

| Dimension | Definition | Failure it catches |
|---|---|---|
| Context relevance | Whether each retrieved chunk is relevant to the input query | irrelevant retrieval, poor chunking, noisy top-k |
| Groundedness | Whether answer claims are supported by retrieved context | unsupported claims, hallucination, exaggeration |
| Answer relevance | Whether the response helps answer the original user input | evasive, off-topic, over-broad, or incomplete answers |

### Strengths

TruLens is best thought of as an **observability and debugging framework**. It is strong when you need to trace how a RAG app behaves over real calls, inspect failures by component, run feedback functions, and compare application versions. It is also helpful when moving from offline benchmarking to live monitoring.

### Limitations

Reference-free RAG triad metrics are useful but not definitive. A high groundedness score only means the answer is grounded in the retrieved context, not that the retrieved context is true, complete, current, or legally/clinically acceptable. Ground-truth retrieval metrics require curated expected contexts.

---

## 5. DeepEval

### Source base

DeepEval provides 50+ metrics and positions RAG metrics as evaluating retriever and generator components independently. Its docs list retriever metrics such as contextual relevancy, contextual precision, and contextual recall, plus generator metrics such as answer relevancy and faithfulness ([DeepEval metrics intro](https://deepeval.com/docs/metrics-introduction)).

### Main RAG metrics

| Metric | What it measures | Required fields | Best use |
|---|---|---|---|
| Contextual Precision | Whether relevant retrieval-context nodes are ranked above irrelevant ones; uses an LLM judge and weighted cumulative precision ([DeepEval contextual precision docs](https://deepeval.com/docs/metrics-contextual-precision)) | `input`, `actual_output`, `expected_output`, `retrieval_context` | Reranker and context ordering evaluation |
| Contextual Recall | Extent to which retrieved context aligns with the expected output ([DeepEval contextual recall docs](https://deepeval.com/docs/metrics-contextual-recall)) | `input`, `actual_output`, `expected_output`, `retrieval_context` | Detecting missing evidence |
| Contextual Relevancy | Whether retrieved contexts are relevant to the input | `input`, `retrieval_context` | Fast retriever sanity checks |
| Faithfulness | Whether the actual output is faithful to the retrieved context ([DeepEval faithfulness docs](https://deepeval.com/docs/metrics-faithfulness)) | `actual_output`, `retrieval_context` | Hallucination checks |
| Answer Relevancy | Whether the output addresses the input ([DeepEval answer relevancy docs](https://deepeval.com/docs/metrics-answer-relevancy)) | `input`, `actual_output` | End-to-end response alignment |

### Strengths

DeepEval is strong for CI/CD, unit-test-like evaluation, and component-level regression tests. It is practical when you want thresholds, reasons, and test cases that can run repeatedly as part of development. It also supports custom metrics, G-Eval-style judges, DAG-style metrics, tracing, and synthetic data tooling.

### Limitations

Like other LLM-as-judge frameworks, its scores depend on the judge model, prompt templates, threshold choices, and test-case design. It is easy to overinterpret a single scalar score. For robust use, pair DeepEval with human-reviewed goldens and statistical confidence intervals.

---

## 6. Cross-framework mapping

| Concept | RAGAS | ARES | TruLens | DeepEval | Classical IR equivalent |
|---|---|---|---|---|---|
| Retrieved context relevance | Context precision, context recall, context entities recall | Context relevance | Context relevance | Contextual precision, recall, relevancy | Precision@k, Recall@k, nDCG@k, MRR |
| Answer support by retrieved evidence | Faithfulness | Answer faithfulness | Groundedness | Faithfulness | Claim support / attribution precision |
| Answer addresses user input | Response relevancy | Answer relevance | Answer relevance | Answer relevancy | Task success / semantic relevance |
| Reference answer correctness | Factual correctness / answer correctness | Often external to core three dimensions | Ground-truth feedback functions | G-Eval/custom correctness | EM/F1, human correctness |
| Robustness to noisy context | Noise sensitivity | Can be evaluated via synthetic/adversarial data | Custom feedback functions | Custom metrics / contextual relevancy | Adversarial retrieval evaluation |
| Production monitoring | Limited by integration choices | Evaluation methodology | Strong | Strong | Observability metrics |

## 7. Practical recommendation

- Use **RAGAS** when iterating quickly on chunking, retrieval, and prompt variants.
- Use **DeepEval** when you want test cases, thresholds, and CI/CD regression checks.
- Use **TruLens** when you need tracing, observability, feedback functions, and debugging over live or logged calls.
- Use **ARES** when you need a calibrated, domain-adapted evaluator and can afford synthetic data + human calibration.
- Use **classical IR metrics** whenever you have document IDs or annotated relevant contexts; they are cheaper, more stable, and easier to interpret than LLM judges.
