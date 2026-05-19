# Studies, Benchmarks, and TCO Sources

## What exists and what does not

There is no single definitive public study that gives a complete TCO answer for every RAG architecture. The best evidence base is a combination of:

1. provider pricing pages for billing truth;
2. ANN benchmark papers for recall/latency/memory tradeoffs;
3. vector algorithm papers for hardware implications;
4. industry articles on RAG cost, reranking, and serving;
5. internal workload measurements.

## Research and benchmark sources

### ANN-Benchmarks

- Purpose: compare approximate nearest neighbor algorithms across recall/latency curves.
- Use in TCO: identify algorithm families that meet recall/latency goals before costing infrastructure.
- Limitation: not a cloud bill or end-to-end RAG cost model.

### ANN-Benchmarks paper

- Purpose: benchmark methodology for in-memory ANN algorithms.
- Use in TCO: understand what recall-latency benchmark curves mean.
- Limitation: does not account for managed-service billing, labor, backups, or replicas.

### DiskANN

- Purpose: high-recall billion-scale ANN using SSD/RAM tradeoffs.
- Use in TCO: crucial when RAM cost is the main bottleneck.
- Economic insight: moving much of the index to SSD can reduce memory cost, but SSD latency, build complexity, and serving design matter.

### ScaNN

- Purpose: efficient vector similarity search through partitioning, quantization, and reordering.
- Use in TCO: relevant for high-throughput large-scale serving where partition/reorder improves efficiency.
- Economic insight: algorithmic efficiency reduces serving hardware, but may increase implementation complexity.

### SOAR for ScaNN

- Purpose: controlled redundancy for faster vector search with ScaNN.
- Use in TCO: useful when recall/latency at scale is worth additional index redundancy.
- Economic insight: redundancy can cost more storage but reduce query-time compute/latency.

### Faiss GPU and Faiss library papers

- Purpose: GPU similarity search, product quantization, and compressed indexes.
- Use in TCO: reason about brute force, GPU search, PQ, IVF, and compressed serving.
- Economic insight: compression and GPUs can trade memory, recall, and build complexity against throughput.

### NVIDIA reranking microservice article

- Purpose: explain reranking as an accuracy and cost optimization layer.
- Use in TCO: model reranking not as isolated cost but as a way to reduce LLM context waste and quality failures.

### LLM selection and vector database tuning research

- Purpose: joint optimization of RAG model selection and vector DB tuning.
- Use in TCO: supports the idea that model, retrieval, and DB choices interact.

## Cost-of-RAG analysis framework

A useful TCO study should include:

```text
1. workload definition
2. corpus size and growth
3. embedding model and dimension
4. chunking scheme
5. index algorithm/configuration
6. vector store billing model
7. read/write/freshness pattern
8. reranker policy
9. generator model and context length
10. cache policy
11. multi-tenancy/isolation model
12. observability/evaluation overhead
13. labor and on-call
14. migration/reindexing events
15. sensitivity analysis
```

## What common benchmarks omit

Most public ANN benchmarks omit:

- provider-specific read/write units;
- plan minimums;
- network egress;
- private networking;
- backups and restore;
- ACL filtering;
- multi-tenancy;
- model upgrade/reindex cost;
- cache hit rates;
- reranker and generator costs;
- engineering labor;
- incident and reliability costs.

Therefore benchmark results should inform **hardware and algorithm choices**, not replace a TCO model.

## When to use which evidence source

| Question | Best source type |
|---|---|
| Which algorithm is fastest at given recall? | ANN-Benchmarks, Faiss, ScaNN, DiskANN papers |
| Which vendor bills per read/write/storage? | Provider pricing docs |
| When does API become more expensive than GPU? | Your workload measurements + pricing formulas |
| How much does reranking cost? | Reranker provider pricing + top-k/token model |
| How much memory will HNSW need? | Vendor docs + measured index size + HNSW parameter model |
| Is DiskANN/PQ worth it? | Algorithm papers + hardware cost model |
| Does reranking save money? | End-to-end experiment measuring reduced context/retries |
| Should tenants share indexes? | Workload/security requirements + vendor isolation costs |

## Source list

- **Pinecone pricing** (provider pricing, accessed May 19, 2026): https://www.pinecone.io/pricing/ — Pricing page used for storage, read/write units, embedding and reranking examples; volatile.
- **Pinecone understand cost** (provider docs, accessed May 19, 2026): https://docs.pinecone.io/guides/manage-cost/understanding-cost — Explains cost dimensions such as storage, read units, write units and backups.
- **AWS SageMaker AI pricing** (provider pricing, accessed May 19, 2026): https://aws.amazon.com/sagemaker/ai/pricing/ — Used for representative managed GPU hourly examples such as A10G-class instances.
- **AWS EC2 Capacity Blocks pricing** (provider pricing, accessed May 19, 2026): https://aws.amazon.com/ec2/capacityblocks/pricing/ — Used for A100/H100 effective hourly-rate examples.
- **AWS EC2 P4 instance page** (provider docs, accessed May 19, 2026): https://aws.amazon.com/ec2/instance-types/p4/ — Used for spot/instance context and high-end GPU economics.
- **Google Cloud DWS pricing** (provider pricing, accessed May 19, 2026): https://cloud.google.com/products/dws/pricing — Used for representative GCP accelerator price signal.
- **Google Cloud GPU pricing** (provider pricing, accessed May 19, 2026): https://cloud.google.com/compute/gpus-pricing — GPU pricing should be calculator-confirmed by region.
- **Azure VM Linux pricing** (provider pricing, accessed May 19, 2026): https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/ — Official pricing path; exact GPU rates require calculator/region confirmation.
- **Azure AI Search pricing** (provider pricing, accessed May 19, 2026): https://azure.microsoft.com/en-us/pricing/details/search/ — Official pricing path for Azure AI Search tiers; volatile.
- **Cohere pricing** (provider pricing, accessed May 19, 2026): https://cohere.com/pricing — Used for hosted/dedicated embed and rerank pricing structures.
- **Voyage AI pricing** (provider pricing, accessed May 19, 2026): https://docs.voyageai.com/docs/pricing — Used for token-priced reranking/embedding cost structure.
- **OpenAI pricing** (provider pricing, accessed May 19, 2026): https://openai.com/api/pricing/ — Add/update directly before procurement; pricing is volatile.
- **Anthropic pricing** (provider pricing, accessed May 19, 2026): https://www.anthropic.com/pricing — Add/update directly before procurement; pricing is volatile.
- **Weaviate pricing** (provider pricing, accessed May 19, 2026): https://weaviate.io/pricing — Calculator-oriented pricing; dimensions/object counts influence cost.
- **Weaviate billing docs** (provider docs, accessed May 19, 2026): https://docs.weaviate.io/cloud/platform/billing — Used for billing model context.
- **Milvus OSS** (OSS/product docs, accessed May 19, 2026): https://milvus.io/ — Milvus OSS has no license cost; infra/ops cost dominates.
- **Milvus GitHub** (OSS repository, accessed May 19, 2026): https://github.com/milvus-io/milvus — OSS reference.
- **Zilliz pricing** (provider pricing, accessed May 19, 2026): https://zilliz.com/pricing — Managed Milvus/Zilliz pricing.
- **Zilliz understand cost** (provider docs, accessed May 19, 2026): https://docs.zilliz.com/docs/understand-cost — Explains compute, storage, transfer, index build and related costs.
- **Zilliz storage cost** (provider docs, accessed May 19, 2026): https://docs.zilliz.com/docs/storage-cost — Storage cost notes.
- **Qdrant pricing** (provider pricing, accessed May 19, 2026): https://qdrant.tech/pricing/ — Cloud resource/billing tiers.
- **Qdrant billing docs** (provider docs, accessed May 19, 2026): https://qdrant.tech/documentation/cloud-pricing-payments/ — Billing/payment details.
- **pgvector GitHub** (OSS repository, accessed May 19, 2026): https://github.com/pgvector/pgvector — pgvector cost follows underlying Postgres infra.
- **AWS OpenSearch Service pricing** (provider pricing, accessed May 19, 2026): https://aws.amazon.com/opensearch-service/pricing/ — Instance/serverless/OCU pricing; volatile.
- **Elastic hosted pricing** (provider pricing, accessed May 19, 2026): https://www.elastic.co/pricing/cloud-hosted — Hosted pricing.
- **Elastic serverless pricing** (provider pricing, accessed May 19, 2026): https://www.elastic.co/pricing/serverless-search — Ingest/search/ML VCU, storage and egress dimensions.
- **Vespa Cloud price calculator** (provider pricing, accessed May 19, 2026): https://cloud.vespa.ai/price-calculator — Resource-based pricing: vCPU, memory, disk, GPU memory, hourly.
- **LanceDB Enterprise docs** (provider docs, accessed May 19, 2026): https://docs.lancedb.com/enterprise — Enterprise/BYOC notes; public static pricing limited.
- **LanceDB GitHub** (OSS repository, accessed May 19, 2026): https://github.com/lancedb/lancedb — OSS/self-host cost follows object storage and compute.
- **Chroma pricing** (provider pricing, accessed May 19, 2026): https://www.trychroma.com/pricing — Writes, storage, query scan volume, returned network pricing.
- **Chroma cloud pricing docs** (provider docs, accessed May 19, 2026): https://docs.trychroma.com/cloud/pricing — Cloud pricing model.
- **Redis pricing** (provider pricing, accessed May 19, 2026): https://redis.io/pricing/ — Cloud tiers/minimums; volatile.
- **Redis BYOC docs** (provider docs, accessed May 19, 2026): https://redis.io/docs/latest/operate/rc/subscriptions/bring-your-own-cloud/ — BYOC billing/infrastructure split.
- **MongoDB pricing** (provider pricing, accessed May 19, 2026): https://www.mongodb.com/pricing — Atlas cluster pricing entry point.
- **MongoDB Atlas Search Node billing** (provider docs, accessed May 19, 2026): https://www.mongodb.com/docs/atlas/billing/search-node/ — Search/vector-search node billing.
- **MongoDB billing breakdown optimization** (provider docs, accessed May 19, 2026): https://www.mongodb.com/docs/atlas/billing/billing-breakdown-optimization/ — Backups/data transfer/search node billing context.
- **Vertex AI Vector Search overview** (provider docs, accessed May 19, 2026): https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/vector-search/overview — Billing dimensions and vector-size notes; pricing calculator oriented.
- **Vertex AI Vector Search update/rebuild index** (provider docs, accessed May 19, 2026): https://docs.cloud.google.com/vertex-ai/docs/vector-search/update-rebuild-index — Update/rebuild and compaction billing behavior.
- **ANN-Benchmarks** (benchmark, accessed May 19, 2026): https://ann-benchmarks.com/index.html — Recall/latency benchmark; not a cost model.
- **ANN-Benchmarks paper** (academic paper, accessed May 19, 2026): https://dl.acm.org/doi/10.1016/j.is.2019.02.006 — Benchmark methodology for ANN algorithms.
- **DiskANN paper** (academic/industry research, accessed May 19, 2026): https://www.microsoft.com/en-us/research/publication/diskann-fast-accurate-billion-point-nearest-neighbor-search-on-a-single-node/ — SSD/RAM tradeoffs for billion-scale ANN.
- **Microsoft Project Akupara / DiskANN** (research project, accessed May 19, 2026): https://www.microsoft.com/en-us/research/project/project-akupara-approximate-nearest-neighbor-search-for-large-scale-semantic-search/ — DiskANN project context.
- **Google ScaNN blog** (research blog, accessed May 19, 2026): https://research.google/blog/announcing-scann-efficient-vector-similarity-search/ — Partition/reorder/vector compression serving tradeoffs.
- **Google SOAR for ScaNN** (research blog, accessed May 19, 2026): https://research.google/blog/soar-new-algorithms-for-even-faster-vector-search-with-scann/ — Controlled redundancy for faster vector search with ScaNN.
- **Faiss GPU paper** (academic paper, accessed May 19, 2026): https://arxiv.org/abs/1702.08734 — Billion-scale similarity search with GPUs.
- **Faiss 2024 library paper** (academic paper, accessed May 19, 2026): https://arxiv.org/pdf/2401.08281 — Faiss design, compression and non-exhaustive search overview.
- **NVIDIA reranking microservice cost/accuracy article** (industry article, accessed May 19, 2026): https://developer.nvidia.com/blog/how-using-a-reranking-microservice-can-improve-accuracy-and-costs-of-information-retrieval/ — Frames reranking as end-to-end accuracy and cost lever.
- **LLM Selection and Vector Database Tuning** (academic article, accessed May 19, 2026): https://www.mdpi.com/2076-3417/15/20/10886 — Joint optimization of RAG model and vector DB tuning.

## Recommended citation practice

For any report or architecture decision record, cite provider pages like this:

```text
Provider pricing accessed on YYYY-MM-DD; rates are volatile and must be rechecked before procurement.
```

For algorithm papers, separate performance claims from cost claims:

```text
The paper supports the recall/latency/memory tradeoff. The dollar-cost implication is our inference based on current cloud pricing.
```
