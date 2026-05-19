# References and Source Pointers

This file lists primary papers, model cards, product docs, and implementation references useful for the report. Verify pricing, quotas, and exact product capabilities against official docs before final architecture decisions.

## Matching and retrieval

- BM25: Robertson and Zaragoza, “The Probabilistic Relevance Framework: BM25 and Beyond.”
- Dense Passage Retrieval: Karpukhin et al., “Dense Passage Retrieval for Open-Domain Question Answering.”
- BEIR benchmark: Thakur et al., “BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models.”
- MTEB: Muennighoff et al., “MTEB: Massive Text Embedding Benchmark.”
- SPLADE: Formal et al., “SPLADE: Sparse Lexical and Expansion Model for First Stage Ranking.”  
  https://arxiv.org/abs/2107.05720
- SPLADE v2: Formal et al., “From Distillation to Hard Negative Sampling.”  
  https://arxiv.org/abs/2109.10086
- ColBERT: Khattab and Zaharia, “ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT.”  
  https://arxiv.org/abs/2004.12832
- ColBERTv2: Santhanam et al., “ColBERTv2: Efficient and Effective Retrieval via Lightweight Late Interaction.”  
  https://arxiv.org/abs/2112.01488
- PLAID: Santhanam et al., “PLAID: An Efficient Engine for Late Interaction Retrieval.”  
  https://arxiv.org/abs/2205.09707

## Fusion

- Reciprocal Rank Fusion: Cormack, Clarke, and Buettcher, “Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods.”
- Azure AI Search hybrid search documentation.  
  https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview
- Google Vertex AI Vector Search hybrid search docs.  
  https://cloud.google.com/vertex-ai/docs/vector-search/about-hybrid-search

## Query transforms

- HyDE: Gao et al., “Precise Zero-Shot Dense Retrieval without Relevance Labels.”  
  https://arxiv.org/abs/2212.10496
- LangChain HyDE retriever docs.  
  https://docs.langchain.com/oss/javascript/integrations/retrievers/hyde
- LangChain MultiQueryRetriever docs.  
  https://reference.langchain.com/python/langchain-classic/retrievers/multi_query/MultiQueryRetriever
- Step-back prompting: Zheng et al., “Take a Step Back: Evoking Reasoning via Abstraction in Large Language Models.”  
  https://arxiv.org/abs/2310.06117
- Query decomposition for RAG literature and recent multi-hop retrieval work.  
  https://arxiv.org/abs/2507.00355
- Self-query retriever docs.  
  https://reference.langchain.com/python/langchain-classic/retrievers/self_query/base/SelfQueryRetriever
- RAG-Fusion implementation articles and evaluations.  
  https://arxiv.org/abs/2402.03367

## Adaptive and agentic retrieval

- FLARE: Jiang et al., “Active Retrieval Augmented Generation.”  
  https://arxiv.org/abs/2305.06983
- Self-RAG: Asai et al., “Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection.”  
  https://arxiv.org/abs/2310.11511
- CRAG: Yan et al., “Corrective Retrieval Augmented Generation.”  
  https://arxiv.org/abs/2401.15884
- Adaptive-RAG: Jeong et al., “Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity.”  
  https://arxiv.org/abs/2403.14403

## GraphRAG and KG-augmented retrieval

- Microsoft GraphRAG project and papers.  
  https://github.com/microsoft/graphrag
- Knowledge-graph augmented generation surveys and KG-RAG literature.
- Neo4j GraphRAG materials and implementation guides.  
  https://neo4j.com/developer-blog/
- LlamaIndex knowledge graph / property graph retrieval docs.  
  https://docs.llamaindex.ai/

## Rerankers

- BGE reranker model cards.  
  https://huggingface.co/BAAI/bge-reranker-v2-m3  
  https://huggingface.co/BAAI/bge-reranker-v2-gemma
- Mixedbread rerankers.  
  https://www.mixedbread.com/blog/mxbai-rerank-v2  
  https://www.mixedbread.com/docs
- Cohere Rerank docs.  
  https://docs.cohere.com/reference/rerank  
  https://docs.cohere.com/docs/reranking-best-practices
- Jina reranker docs.  
  https://jina.ai/reranker/  
  https://jina.ai/models/jina-reranker-v2-base-multilingual/  
  https://jina.ai/models/jina-reranker-v3/
- RankGPT / LLM reranking: Sun et al., “Is ChatGPT Good at Search? Investigating Large Language Models as Re-Ranking Agents.”  
  https://arxiv.org/abs/2304.09542
- Pairwise Ranking Prompting / PRP.  
  https://arxiv.org/abs/2306.17563
- PE-Rank and efficient listwise/pairwise LLM reranking literature.  
  https://arxiv.org/abs/2406.14848

## Cloud platform mapping

### AWS

- OpenSearch vector search.  
  https://docs.aws.amazon.com/opensearch-service/latest/developerguide/vector-search.html
- OpenSearch Serverless vector search.  
  https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-vector-search.html
- OpenSearch Serverless VPC endpoints / PrivateLink.  
  https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-vpc.html
- SageMaker Serverless Inference.  
  https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html
- AWS vector database guidance.  
  https://docs.aws.amazon.com/vector-databases/
- Aurora PostgreSQL pgvector / Aurora features.  
  https://aws.amazon.com/rds/aurora/features/
- MemoryDB vector search.  
  https://docs.aws.amazon.com/memorydb/latest/devguide/vector-search.html
- AWS KMS.  
  https://docs.aws.amazon.com/kms/
- AWS IAM.  
  https://docs.aws.amazon.com/iam/
- CloudWatch / CloudTrail.  
  https://docs.aws.amazon.com/cloudwatch/  
  https://docs.aws.amazon.com/cloudtrail/

### GCP

- Vertex AI Vector Search.  
  https://cloud.google.com/vertex-ai/docs/vector-search/
- Vertex AI hybrid search.  
  https://cloud.google.com/vertex-ai/docs/vector-search/about-hybrid-search
- Vertex AI Vector Search Private Service Connect.  
  https://cloud.google.com/vertex-ai/docs/vector-search/private-service-connect
- Vertex AI online prediction and private endpoints.  
  https://cloud.google.com/vertex-ai/docs/predictions/overview  
  https://cloud.google.com/vertex-ai/docs/predictions/private-service-connect
- AlloyDB AI vector search.  
  https://cloud.google.com/alloydb/docs/ai/perform-vector-search
- Cloud KMS.  
  https://cloud.google.com/kms/docs
- IAM and service accounts.  
  https://cloud.google.com/iam/docs
- Cloud Logging / Monitoring / Audit Logs.  
  https://cloud.google.com/logging/docs  
  https://cloud.google.com/monitoring/docs  
  https://cloud.google.com/logging/docs/audit

### Azure

- Azure AI Search vector search.  
  https://learn.microsoft.com/en-us/azure/search/vector-search-overview
- Azure AI Search hybrid search.  
  https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview
- Azure AI Search private endpoints.  
  https://learn.microsoft.com/en-us/azure/search/service-create-private-endpoint
- Azure AI Search security and encryption.  
  https://learn.microsoft.com/en-us/azure/search/search-security-overview
- Azure Machine Learning endpoints.  
  https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints
- Azure ML serverless model deployments.  
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-models-serverless
- Azure PostgreSQL vector database guidance.  
  https://learn.microsoft.com/en-us/azure/postgresql/
- Azure Key Vault.  
  https://learn.microsoft.com/en-us/azure/key-vault/
- Microsoft Entra ID / Azure RBAC.  
  https://learn.microsoft.com/en-us/azure/role-based-access-control/
- Azure Monitor / Application Insights.  
  https://learn.microsoft.com/en-us/azure/azure-monitor/

## Hugging Face Spaces

- Spaces overview.  
  https://huggingface.co/docs/hub/spaces
- Spaces storage.  
  https://huggingface.co/docs/hub/spaces-storage
- Manage Spaces with huggingface_hub.  
  https://huggingface.co/docs/huggingface_hub/en/guides/manage-spaces
- Hugging Face pricing / hardware tiers.  
  https://huggingface.co/pricing
