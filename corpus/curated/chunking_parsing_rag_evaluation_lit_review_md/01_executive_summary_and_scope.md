# 01 — Executive Summary and Scope

## Executive summary

RAG evaluation is not one metric. It is a layered measurement problem. A RAG system can fail because the parser flattened a table incorrectly, the chunker severed a definition from its heading, the retriever found semantically similar but non-answering passages, the reranker ranked distracting context first, the generator ignored the evidence, or the evaluation judge rewarded plausible prose. For this reason, the literature increasingly separates **retrieval quality**, **context quality**, **answer quality**, **faithfulness/groundedness**, **citation behavior**, and **user-level outcomes**.

The major RAG evaluation frameworks converge on a similar core triad:

- **Context/retrieval relevance**: whether the retrieved chunks are useful for answering the query.
- **Groundedness/faithfulness**: whether the answer's claims are supported by retrieved evidence.
- **Answer relevance/correctness**: whether the final response addresses the user query and is factually correct.

RAGAS formalized reference-free and reference-aware RAG metrics such as context precision, context recall, response relevancy, and faithfulness ([RAGAS paper](https://arxiv.org/abs/2309.15217), [RAGAS metrics docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)). ARES introduced an automated evaluation system that creates synthetic data, trains lightweight LM judges, and uses a small amount of human annotation with prediction-powered inference to estimate context relevance, answer faithfulness, and answer relevance ([ARES paper](https://arxiv.org/abs/2311.09476)). TruLens operationalizes a practical “RAG triad” of context relevance, groundedness, and answer relevance, while also supporting ground-truth retrieval metrics such as hit rate, NDCG@k, and recall@k ([TruLens RAG triad docs](https://www.trulens.org/getting_started/core_concepts/rag_triad/), [TruLens retrieval groundtruth docs](https://www.trulens.org/getting_started/quickstarts/groundtruth_evals_for_retrieval_systems/)). DeepEval packages RAG metrics into a testing/CI-friendly interface with contextual precision, contextual recall, contextual relevancy, answer relevancy, and faithfulness ([DeepEval metrics intro](https://deepeval.com/docs/metrics-introduction)).

The benchmark landscape is split between **retrieval benchmarks** and **RAG/end-task benchmarks**. BEIR is best for zero-shot retrieval robustness across heterogeneous domains ([BEIR paper](https://arxiv.org/abs/2104.08663)). MTEB is best for comparing embedding models across retrieval, classification, clustering, reranking, STS, and multilingual tasks ([MTEB paper](https://arxiv.org/abs/2210.07316)). MS MARCO is useful for web-search-like passage ranking and answer generation from real search queries ([MS MARCO paper](https://arxiv.org/abs/1611.09268)). Natural Questions is useful for open-domain QA with real Google queries and long/short answers ([Natural Questions dataset](https://ai.google.com/research/NaturalQuestions)). HotpotQA is useful for multi-hop retrieval and supporting-fact evaluation ([HotpotQA paper](https://arxiv.org/abs/1809.09600)). KILT is useful when provenance matters because multiple knowledge-intensive tasks share a common Wikipedia snapshot ([KILT paper](https://arxiv.org/abs/2009.02252)). RGB and CRUD-RAG are more explicitly RAG-oriented: RGB probes noise robustness, negative rejection, information integration, and counterfactual robustness; CRUD-RAG tests create/read/update/delete-style RAG scenarios ([RGB paper](https://arxiv.org/abs/2309.01431), [CRUD-RAG paper](https://arxiv.org/abs/2401.17043)).

The hardest methodological issue is **gold-set construction**. Public benchmarks are useful for model comparison, but domain RAG systems need a custom gold set with representative queries, reference answers, supporting evidence IDs, unanswerable questions, adversarial near-misses, outdated/conflicting evidence cases, multi-hop cases, and user-intent categories. A gold set should label not only the final answer but also the expected retrieved contexts, required evidence, permitted answer forms, citation granularity, and abstention behavior.

LLM-as-judge methods are useful but should not be treated as ground truth. G-Eval showed that GPT-4-style judges can correlate better with human judgments than older automatic metrics, but also warned about evaluator bias toward LLM-generated text ([G-Eval paper](https://arxiv.org/abs/2303.16634)). MT-Bench/Chatbot Arena work found strong LLM judges can match human preference agreement surprisingly well, while still suffering from position, verbosity, self-enhancement, and reasoning limitations ([Judging LLM-as-a-Judge paper](https://arxiv.org/abs/2306.05685)). Other work shows order sensitivity and fairness problems in LLM judges ([Large Language Models are not Fair Evaluators](https://arxiv.org/abs/2305.17926), [Position bias study](https://arxiv.org/abs/2406.07791)). For attributed RAG, a separate caveat is that citation correctness is not identical to citation faithfulness: a cited document can support a claim even when the model did not genuinely rely on it ([Correctness is not Faithfulness in RAG Attributions](https://arxiv.org/abs/2412.18004)).

## Scope

This bundle covers:

- Metric definitions for RAGAS, ARES, TruLens, and DeepEval.
- Benchmark dataset selection for retrieval, embeddings, QA, multi-hop QA, provenance, robustness, and scenario-based RAG.
- Gold-set construction for private/domain RAG.
- LLM-as-judge caveats and calibration.
- Offline versus online evaluation.
- Practical “when to use which” guidance.

It deliberately treats chunking and parsing as part of evaluation because chunking/parsing changes the basic unit of retrieval and attribution. A retrieval metric over bad chunks can look strong while the generated answer remains unusable, and a generator metric can hide parser failures if the model reconstructs missing context from parametric memory.
