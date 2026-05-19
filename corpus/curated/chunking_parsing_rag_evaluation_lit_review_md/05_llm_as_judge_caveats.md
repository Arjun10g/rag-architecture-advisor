# 05 — LLM-as-Judge Caveats

## Why LLM judges are useful

LLM judges are useful because RAG outputs are often open-ended. Exact match, BLEU, and ROUGE are often too brittle for responses that can be correct in many phrasings. G-Eval showed that GPT-4-style evaluators using chain-of-thought and form-filling can align better with human judgments than older automatic metrics for summarization and dialogue, while also warning that LLM evaluators can be biased toward LLM-generated text ([G-Eval paper](https://arxiv.org/abs/2303.16634)).

MT-Bench and Chatbot Arena found that strong LLM judges can approximate human preference surprisingly well, but also documented important limitations such as position bias, verbosity bias, self-enhancement bias, and limited reasoning ([Judging LLM-as-a-Judge paper](https://arxiv.org/abs/2306.05685)).

## Main caveats

| Caveat | Description | RAG-specific consequence | Mitigation |
|---|---|---|---|
| Position bias | Judges may prefer the first or second answer depending on ordering | Pairwise model comparisons become unstable | Randomize answer order; evaluate both orders; use balanced position calibration |
| Verbosity/style bias | Longer or more polished answers may score higher | Fluffy unsupported answers beat concise grounded answers | Use rubrics that separately score correctness, grounding, concision, and verbosity |
| Self-preference / model-family bias | A judge may prefer outputs from its own model family | Vendor/model comparisons are distorted | Use multiple judges; include human calibration; hide model identity |
| Agreeableness/leniency | Judges may over-accept plausible answers | Hallucinations slip through | Include adversarial negatives and strict claim-level checks |
| Reference leakage | Judge sees reference answer and rewards semantic similarity even if context did not support answer | Generator may be correct from parametric memory but not grounded | Separate correctness from groundedness; require source-span support |
| Prompt sensitivity | Metric changes when judge prompt changes | Scores are not stable across framework versions | Version prompts/templates; run regression audits |
| Data contamination | Judge may know benchmark answers | Inflated benchmark results | Use private or fresh gold sets; include temporal/freshness questions |
| Citation post-rationalization | Citation supports claim, but model may not have used it | Attribution trust is overstated | Test citation faithfulness, not only citation correctness |
| Poor domain knowledge | Judge lacks expertise in legal/medical/technical nuance | Wrong accept/reject decisions | Calibrate with SME labels; use domain-specific rubrics |
| Non-determinism | Sampling or model changes cause score variance | CI failures may be flaky | Use deterministic settings where possible; repeat and bootstrap |

## Position and fairness concerns

Research on LLM evaluators shows that answer order can strongly affect results ([Large Language Models are not Fair Evaluators](https://arxiv.org/abs/2305.17926)). Later systematic work studied position bias across many judges and tasks, finding that bias varies by judge and task and is not merely random noise ([Position bias study](https://arxiv.org/abs/2406.07791)).

### Practical debiasing checklist

- Randomize pairwise output order.
- Run pairwise comparisons in both directions.
- Use pointwise rubrics for component metrics when possible.
- Use multiple judge models for release decisions.
- Keep a human-labeled audit set.
- Track judge disagreement as a risk signal.
- Report judge model, temperature, prompt, and date/version.
- Do not compare scores across judge versions without recalibration.

## Correctness versus faithfulness

In RAG, **correctness** and **faithfulness** are different.

- Correctness: Is the answer true?
- Faithfulness: Is the answer supported by the retrieved context?
- Citation correctness: Does the cited source support the claim?
- Citation faithfulness: Did the model genuinely rely on that cited source rather than post-rationalizing?

Work on RAG attributions argues that citation correctness alone is insufficient because a model can cite a document that supports a statement even if the answer came from parametric memory or a different source ([Correctness is not Faithfulness in RAG Attributions](https://arxiv.org/abs/2412.18004)).

## Judge design for RAG

A robust RAG judge should evaluate claims, not only full answers.

### Recommended judge prompt structure

1. Extract atomic claims from the answer.
2. For each claim, identify whether it is:
   - directly supported by retrieved context
   - partially supported
   - contradicted
   - not mentioned
3. Check whether the final answer addresses the user question.
4. Check whether required caveats are included.
5. Check whether citations map to the exact claims.
6. Penalize unsupported speculation.
7. Return structured JSON with per-claim labels and reasoning.

### Recommended output schema

```json
{
  "answer_relevance": 0.0,
  "answer_correctness": 0.0,
  "faithfulness": 0.0,
  "citation_precision": 0.0,
  "citation_recall": 0.0,
  "abstention_correct": true,
  "claims": [
    {
      "claim": "...",
      "support": "supported | partial | contradicted | not_in_context",
      "source_ids": ["..."],
      "reason": "..."
    }
  ],
  "overall_reason": "..."
}
```

## Human calibration

Human labels remain the anchor for serious evaluation. Use LLM judges for scale, but calibrate them against humans.

### Calibration procedure

1. Sample 100–300 examples from the gold set.
2. Have SMEs label answer correctness, evidence support, citation quality, and abstention.
3. Run each judge metric.
4. Compute agreement, precision, recall, and calibration curves.
5. Identify false positives and false negatives.
6. Adjust rubrics, thresholds, or judge choice.
7. Repeat after major model, prompt, or corpus changes.

ARES is notable because it explicitly combines automated judge models with a smaller human-annotated set through prediction-powered inference ([ARES paper](https://arxiv.org/abs/2311.09476)).

## When LLM-as-judge is appropriate

| Use-case | Appropriate? | Notes |
|---|---|---|
| Early RAG prototyping | Yes | Use as fast directional feedback |
| Comparing chunking variants | Yes, with retrieval metrics | Pair with context recall/precision and manual audits |
| CI regression testing | Yes | Use stable judge model/version and thresholds |
| High-stakes release gate | Partially | Requires human calibration and manual audit |
| Legal/medical final correctness | Not alone | SME review required |
| User preference ranking | Yes, cautiously | Randomize order and calibrate against human preferences |
| Citation faithfulness | Only with claim-level design | Citation correctness alone is insufficient |
