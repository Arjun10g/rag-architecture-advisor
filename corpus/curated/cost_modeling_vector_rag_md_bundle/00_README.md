# Cost Modeling for Vector Search and RAG Systems

This bundle turns the cost-modeling report into focused Markdown files. It is designed for interview preparation, architecture decision records, procurement modeling, and RAG platform planning.

**Date-stamp:** pricing pages and provider references in this bundle should be treated as volatile and were compiled/accessed around **May 19, 2026**. Always re-check official pricing pages before procurement.

## Files

1. `01_executive_summary.md` — main conclusions and decision frame.
2. `02_cost_model_formulas.md` — reusable formulas for API, self-host, storage, reranking, and TCO.
3. `03_api_vs_self_host_gpu_crossover.md` — crossover math and worked examples.
4. `04_gpu_capacity_purchase_modes.md` — on-demand, reserved, spot, capacity blocks, and managed dedicated endpoints.
5. `05_managed_vector_store_billing.md` — vendor-by-vendor billing dimensions.
6. `06_reranker_cost_modeling.md` — cross-encoder and LLM reranking cost models.
7. `07_where_cost_concentrates.md` — practical cost centers across RAG pipelines.
8. `08_storage_dimension_replication.md` — vector footprint, replicas, metadata, indexes, backups, and egress.
9. `09_scenario_models.md` — worked workload models and sensitivity tables.
10. `10_vendor_pricing_snapshot.md` — pricing snapshot with caveats.
11. `11_studies_benchmarks_tco_sources.md` — research, benchmarks, and cost-of-RAG/TCO source map.
12. `12_decision_playbooks.md` — when to use API vs self-host, managed vs OSS, rerank vs no rerank.
13. `sources.json` — structured source list.

## Core framing

The right cost model is not a single line item. It is:

```text
Total Cost = Embedding + Index Build/Update + Search Serving + Reranking + Generation + Storage + Network + Observability + Ops/Labor + Amortized Training
```

The main mistake is comparing a token-priced API to a GPU hourly rate without accounting for utilization, failover headroom, queueing, observability, patching, and labor.

## Pricing volatility warning

Provider prices can change after the date-stamp. Treat all numeric examples as **worked modeling examples**, not procurement quotes.
