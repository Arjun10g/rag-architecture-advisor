# 06 — Offline vs Online Evaluation

## Offline evaluation

Offline evaluation uses a fixed dataset and repeatable pipeline runs. It is the right place to compare parsers, chunkers, embedders, retrievers, rerankers, prompt templates, and generation models.

### Offline metrics

| Component | Metrics |
|---|---|
| Parser | reading-order accuracy, table preservation, heading preservation, OCR quality, metadata coverage |
| Chunker | chunk coherence, overlap redundancy, orphan headings, token budget, evidence coverage |
| Retriever | Recall@k, Precision@k, MRR, nDCG@k, hit rate |
| Reranker | nDCG@k, contextual precision, top-1 evidence accuracy |
| Context builder | evidence density, duplicate context rate, lost-in-middle sensitivity |
| Generator | answer relevance, answer correctness, completeness, concision |
| Grounding | faithfulness, groundedness, citation precision/recall |
| Abstention | abstention precision/recall, false answer rate, false refusal rate |
| Robustness | noise robustness, counterfactual robustness, stale-source handling |

### Offline experimental design

When comparing chunking/parsing strategies, hold everything else fixed:

```text
parser A + chunker A + same embedder + same retriever + same reranker + same generator
parser A + chunker B + same embedder + same retriever + same reranker + same generator
parser B + chunker A + same embedder + same retriever + same reranker + same generator
```

Report:

- gold set version
- corpus snapshot
- parser version
- chunking parameters
- embedding model and dimensions
- retriever/index parameters
- reranker model
- generator model
- prompt template
- judge model and metric version
- latency and cost
- confidence intervals

### Offline failure analysis

Do not report only aggregate scores. Break failures down by:

- single-hop vs multi-hop
- answerable vs unanswerable
- table/code/PDF/transcript/plain text
- old vs new documents
- high-authority vs low-authority sources
- short vs long answers
- retrieved evidence present vs absent
- answer correct but ungrounded
- grounded but incomplete
- relevant context buried too low
- hallucination induced by distractor

---

## Online evaluation

Online evaluation measures real user behavior and production performance. It answers questions offline tests cannot: whether users trust, use, abandon, correct, escalate, or prefer the system.

### Online metrics

| Category | Metrics |
|---|---|
| Engagement | click-through, follow-up rate, session length, repeat usage |
| Task success | resolution rate, self-serve completion, escalation rate |
| User feedback | thumbs up/down, ratings, free-text feedback |
| Trust | citation clicks, source expansion, user corrections |
| Safety/reliability | hallucination reports, unsafe answer reports, false refusal reports |
| Latency/cost | p50/p95/p99 latency, cost/query, timeout rate |
| Retrieval health | empty retrieval rate, low-score retrieval rate, stale-source retrieval rate |
| Drift | query distribution shift, new topics, failure clusters |

### Online experiment types

| Method | Use | Strength | Weakness |
|---|---|---|---|
| A/B test | Compare two full systems | Measures real user impact | Needs traffic and careful guardrails |
| Interleaving | Compare retrieval rankings | More sensitive for search-like ranking | Harder for generated answers |
| Shadow evaluation | Run new pipeline without showing users | Safe pre-launch comparison | No direct user feedback |
| Canary release | Small traffic percentage | Production realism with lower risk | Requires monitoring and rollback |
| Human audit sampling | Review production conversations | High-quality failure detection | Expensive and slower |
| Continuous LLM judging | Score logs automatically | Scalable monitoring | Requires calibration and drift checks |

---

## Offline-online mismatch

Offline scores often fail to predict online success because:

- offline queries do not match real user distribution
- public benchmarks do not match domain corpus
- users care about latency, tone, and workflow completion
- online traffic contains ambiguous, underspecified, and adversarial queries
- citations may matter more for trust than final answer text
- retrieval improvements may not improve generation if context is too long/noisy
- LLM judges may reward answers users dislike

The RAG evaluation literature increasingly emphasizes multi-metric evaluation because retrieval relevance alone is insufficient. For example, RGB tests robustness abilities such as negative rejection and counterfactual robustness, not just relevance ([RGB paper](https://arxiv.org/abs/2309.01431)). RAG evaluation frameworks such as TruLens and DeepEval also split retriever and generator metrics rather than treating RAG as a black-box answer scorer ([TruLens RAG triad docs](https://www.trulens.org/getting_started/core_concepts/rag_triad/), [DeepEval metrics intro](https://deepeval.com/docs/metrics-introduction)).

---

## Production monitoring checklist

Track these continuously:

```yaml
traffic:
  - query volume
  - intent distribution
  - language distribution
  - new/unseen intents

retrieval:
  - top_k score distribution
  - empty retrieval rate
  - retrieval latency
  - stale document rate
  - authority/source distribution

generation:
  - answer length
  - refusal rate
  - citation count
  - citation coverage
  - model latency
  - token usage

quality:
  - LLM judge scores
  - human audit scores
  - user feedback
  - escalation/correction rate
  - known failure recurrence

safety:
  - PII exposure
  - policy violations
  - unsafe advice
  - hallucination reports

operations:
  - cost per query
  - p95/p99 latency
  - timeout/retry rate
  - index freshness lag
  - embedding failures
```

---

## Release gate template

A RAG release should pass:

1. **Retrieval gate**: Required-context Recall@k above threshold.
2. **Reranking gate**: nDCG@k or contextual precision above threshold.
3. **Faithfulness gate**: Claim support above threshold.
4. **Abstention gate**: False-answer rate on unanswerable questions below threshold.
5. **Citation gate**: Citation precision/recall above threshold.
6. **Robustness gate**: Noise and conflict tests pass.
7. **Latency gate**: p95/p99 latency within target.
8. **Cost gate**: cost/query within budget.
9. **Human audit gate**: SME review passes critical examples.
10. **Canary gate**: production canary shows no regression in user or safety metrics.
