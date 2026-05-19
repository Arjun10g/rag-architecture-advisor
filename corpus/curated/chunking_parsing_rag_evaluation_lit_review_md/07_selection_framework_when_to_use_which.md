# 07 — Selection Framework: When to Use Which

## Framework selection

| Situation | Best starting point | Why |
|---|---|---|
| Rapid RAG prototyping | RAGAS | Fast metric suite for retrieval/generation/faithfulness |
| CI/CD regression tests | DeepEval | Test cases, thresholds, reasons, component-level evals |
| Production tracing and observability | TruLens | RAG triad plus instrumentation and feedback functions |
| Calibrated domain-specific automated evaluation | ARES | Synthetic data + lightweight judges + human calibration |
| Retriever-only benchmark | BEIR/MS MARCO/custom qrels | Stable classical IR metrics |
| Embedding model selection | MTEB + private retrieval set | Broad embedding signal plus domain validation |
| Multi-hop retrieval | HotpotQA/custom multi-hop set | Supporting facts and multi-document reasoning |
| Provenance-aware tasks | KILT/custom citation gold set | Evaluates source provenance, not only answer |
| Robustness to noisy/conflicting context | RGB/custom adversarial set | Tests negative rejection, integration, counterfactuals |
| Scenario-based RAG beyond QA | CRUD-RAG/custom task set | Create/read/update/delete patterns |

---

## Metric selection by question

| Evaluation question | Metrics |
|---|---|
| Did we retrieve the right evidence? | Recall@k, hit rate, context recall, reference-context recall |
| Did we rank the best evidence high? | nDCG@k, MRR, context precision, contextual precision |
| Did irrelevant context enter the prompt? | context precision, contextual relevancy, noise sensitivity |
| Did the generator use the evidence? | faithfulness, groundedness, claim support |
| Is the answer correct? | answer correctness, factual correctness, human rubric score |
| Is the answer useful and on-topic? | answer relevance, response relevancy, task success |
| Are citations correct? | citation precision/recall, source-span support |
| Did the model abstain correctly? | abstention precision/recall, false answer rate |
| Does it handle conflicts? | conflict resolution accuracy, freshness/source authority accuracy |
| Does it work for users? | online satisfaction, resolution, escalation, correction rate |

---

## Chunking/parsing evaluation matrix

| Change being tested | Primary metric | Secondary metric | Required gold labels |
|---|---|---|---|
| Fixed vs recursive chunking | Recall@k | faithfulness, answer correctness | reference contexts |
| Sentence-window retrieval | contextual precision | answer completeness | reference contexts + reference answer |
| Parent-child retrieval | Recall@k and evidence density | cost/latency, answer correctness | required + useful contexts |
| Layout-aware PDF parsing | citation/source-span accuracy | parser audit, answer correctness | page/span-level evidence |
| Table parsing | cell/header accuracy | table QA accuracy | table cell references |
| Code/AST chunking | code context recall | task success / pass rate | file/function/class labels |
| Transcript speaker chunking | speaker-attributed evidence recall | answer correctness | speaker/time labels |
| Late chunking | Recall@k for long-doc references | cost/latency | cross-chunk evidence labels |

---

## Benchmark-first workflow

1. **Start broad**: use MTEB/BEIR/MS MARCO to shortlist embedding and retrieval models.
2. **Build private gold set**: 100–300 examples minimum for serious iteration.
3. **Ablate chunking/parsing**: keep retriever/generator fixed while changing chunking/parser variants.
4. **Add generation metrics**: RAGAS/DeepEval/TruLens triad metrics.
5. **Add robustness tests**: unanswerable, stale, conflicting, distractor, multi-hop.
6. **Calibrate judges**: compare automated scores with human labels.
7. **Move to production monitoring**: TruLens/DeepEval-style tracing plus online metrics.
8. **Maintain evals as data changes**: refresh gold set with new documents, intents, and failure modes.

---

## What to use by maturity stage

| Stage | Evaluation stack |
|---|---|
| Prototype | 20–50 smoke tests + RAGAS/DeepEval + manual review |
| Retrieval tuning | BEIR/MTEB/MS MARCO for model shortlist + private qrels + Recall@k/nDCG@k |
| RAG tuning | Private gold set + context precision/recall + faithfulness + answer relevance |
| Pre-release | Blind gold set + human audit + robustness suite + confidence intervals |
| Production | Tracing/observability + online metrics + human audit sampling + drift monitoring |
| High-stakes | SME review + calibrated judges + locked corpora/index versions + formal release gate |

---

## Common bad evaluation patterns

| Anti-pattern | Why it fails | Better alternative |
|---|---|---|
| Only measuring final answer correctness | Hides retrieval and grounding failures | Separate retrieval, grounding, and generation metrics |
| Only using LLM-as-judge | Judge bias and model drift | Calibrate against human labels |
| Only using public benchmarks | Domain mismatch | Build private gold set |
| Comparing top-k without token budget control | Smaller chunks get unfair advantage | Compare equal context budgets |
| Ignoring unanswerable questions | Model learns to always answer | Include negative and abstention cases |
| Ignoring stale/conflicting sources | Looks good on static corpora | Add freshness and conflict cases |
| No parser/chunker versioning | Results are irreproducible | Version parser, chunker, corpus, index |
| Using one aggregate score | Masks severe subgroup failures | Report breakdowns by query/document type |
