# Gold Set

Frozen gold items live here by version. Gold scenarios/questions must not be copied
into prompts, few-shot examples, or the retrieval corpus.

## Versions

- `v0_1_seed.json` is the first deterministic seed set. It covers a small slice
  of retrieval, routing, and topology behavior so CI can catch regressions while
  the larger coverage matrix is authored.
- `v0_2_expanded.json` is the default gate. It expands retrieval coverage across
  matching, freshness, security, grounding, cost, IaC, deployment, and reference
  architecture documents, with additional routing/topology probes.

## Item Types

- `retrieval`: query plus required/helpful evidence sections. The harness reports
  recall@10, MRR@10, and nDCG@10.
- `routing`: user scenario plus expected domain and requirement-vector values.
  The harness reports domain accuracy, per-attribute accuracy, and pending
  elicitation accuracy when expected.
- `topology`: resolved requirement-vector inputs plus the expected catalog
  topology.

## Thresholds

Thresholds are stored in the gold JSON. The seed version pins the current lexical
retrieval baseline; raise those thresholds when retrieval improves rather than
editing old item semantics in place.
