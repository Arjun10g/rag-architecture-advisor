# 08 — Bibliography

## Evaluation frameworks and docs

- [RAGAS paper](https://arxiv.org/abs/2309.15217)
- [RAGAS metrics docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)
- [RAGAS context precision docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/)
- [RAGAS context recall docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/)
- [RAGAS response relevancy docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/)
- [RAGAS faithfulness docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)
- [ARES paper](https://arxiv.org/abs/2311.09476)
- [TruLens RAG triad docs](https://www.trulens.org/getting_started/core_concepts/rag_triad/)
- [TruLens retrieval groundtruth docs](https://www.trulens.org/getting_started/quickstarts/groundtruth_evals_for_retrieval_systems/)
- [DeepEval metrics intro](https://deepeval.com/docs/metrics-introduction)
- [DeepEval contextual precision docs](https://deepeval.com/docs/metrics-contextual-precision)
- [DeepEval contextual recall docs](https://deepeval.com/docs/metrics-contextual-recall)
- [DeepEval answer relevancy docs](https://deepeval.com/docs/metrics-answer-relevancy)
- [DeepEval faithfulness docs](https://deepeval.com/docs/metrics-faithfulness)

## Benchmark datasets

- [BEIR paper](https://arxiv.org/abs/2104.08663)
- [MTEB paper](https://arxiv.org/abs/2210.07316)
- [MS MARCO paper](https://arxiv.org/abs/1611.09268)
- [Natural Questions dataset](https://ai.google.com/research/NaturalQuestions)
- [Natural Questions baseline note](https://arxiv.org/abs/1901.08634)
- [HotpotQA paper](https://arxiv.org/abs/1809.09600)
- [KILT paper](https://arxiv.org/abs/2009.02252)
- [RGB paper](https://arxiv.org/abs/2309.01431)
- [CRUD-RAG paper](https://arxiv.org/abs/2401.17043)

## LLM-as-judge, RAG surveys, and related evaluation studies

- [G-Eval paper](https://arxiv.org/abs/2303.16634)
- [Judging LLM-as-a-Judge paper](https://arxiv.org/abs/2306.05685)
- [Large Language Models are not Fair Evaluators](https://arxiv.org/abs/2305.17926)
- [Position bias study](https://arxiv.org/abs/2406.07791)
- [Correctness is not Faithfulness in RAG Attributions](https://arxiv.org/abs/2412.18004)
- [RAG survey](https://arxiv.org/abs/2312.10997)
- [RAG Playground](https://arxiv.org/abs/2412.12322)
- [VERA RAG evaluation](https://arxiv.org/abs/2409.03759)

## Notes on source use

- Framework documentation changes over time. Pin framework versions and metric prompt templates in any reproducible experiment.
- Public benchmark scores are useful for initial comparison but should not replace a private domain gold set.
- LLM-as-judge papers support the use of automated judges for scalable evaluation, but also document systematic biases. Human calibration is essential for release decisions.
