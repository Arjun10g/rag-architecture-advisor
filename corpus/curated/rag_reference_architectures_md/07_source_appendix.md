# Source Appendix: End-to-End RAG and File Search Architectures

Compiled: **May 2026**

This appendix lists the main sources used to construct the architecture bundle. Pricing, limits, and service features are volatile; verify these links before procurement or production design.

## OpenAI

- [OpenAI File Search guide](https://developers.openai.com/api/docs/guides/tools-file-search)
- [OpenAI Retrieval guide](https://developers.openai.com/api/docs/guides/retrieval)
- [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data)
- [OpenAI business data privacy](https://openai.com/business-data/)
- [OpenAI Responses API tools update](https://openai.com/index/new-tools-and-features-in-the-responses-api/)

## AWS

- [AWS Prescriptive Guidance: fully managed RAG with Bedrock](https://docs.aws.amazon.com/prescriptive-guidance/latest/retrieval-augmented-generation-options/rag-fully-managed-bedrock.html)
- [Amazon Bedrock Knowledge Bases user guide](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [Create a Knowledge Base in Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-create.html)
- [Retrieve and generate with Bedrock Knowledge Bases](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-retrieve.html)
- [Knowledge Base data source sync and ingestion](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html)
- [Bedrock Knowledge Bases logging](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-bases-logging.html)
- [Bedrock Knowledge Base security](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-create-security.html)
- [Bedrock Knowledge Base encryption](https://docs.aws.amazon.com/bedrock/latest/userguide/encryption-kb.html)
- [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/)
- [Amazon S3 Vectors](https://aws.amazon.com/s3/features/vectors/)
- [S3 Vectors best practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-best-practices.html)
- [AWS pattern: deploy a RAG use case with LangChain and Aurora](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/deploy-rag-use-case-on-aws.html)

## Azure

- [Azure AI Search RAG overview](https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview)
- [Azure AI Search agentic retrieval overview](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview)
- [Azure AI Search capacity planning](https://learn.microsoft.com/en-us/azure/search/search-capacity-planning)
- [Managed identities in Azure AI Search](https://learn.microsoft.com/en-us/azure/search/search-how-to-managed-identities)
- [App Service tutorial with Azure OpenAI and Azure AI Search](https://learn.microsoft.com/en-us/azure/app-service/tutorial-ai-openai-search-dotnet)
- [Secure multitenant RAG on Azure](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/secure-multitenant-rag)
- [Azure semantic ranker enable/disable guidance](https://learn.microsoft.com/en-us/azure/search/semantic-how-to-enable-disable)
- [Azure agentic retrieval billing/enablement guidance](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-enable-disable?tabs=portal)
- [Azure OpenAI pricing](https://azure.microsoft.com/en-us/pricing/details/azure-openai/)
- [Azure AI Search pricing](https://azure.microsoft.com/en-us/pricing/details/search/)
- [Monitor Azure AI Search](https://learn.microsoft.com/en-us/azure/search/monitor-azure-cognitive-search)
- [Monitor Azure AI Search queries](https://learn.microsoft.com/en-us/azure/search/search-monitor-queries)
- [Monitor Azure AI Search indexers](https://learn.microsoft.com/en-us/azure/search/search-monitor-indexers)
- [Azure OpenAI quotas and limits](https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits)

## Google Cloud

- [Google Cloud RAG with Vertex AI Vector Search](https://docs.cloud.google.com/architecture/gen-ai-rag-vertex-ai-vector-search)
- [Google Cloud RAG-capable gen AI app using Vertex AI and AlloyDB](https://docs.cloud.google.com/architecture/rag-capable-gen-ai-app-using-vertex-ai)
- [Google Cloud private-connectivity RAG architecture](https://docs.cloud.google.com/architecture/private-connectivity-rag-capable-gen-ai)
- [Vertex AI RAG Engine with Vector Search](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/use-vertexai-vector-search)
- [Vertex AI RAG Engine billing](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/rag-engine-billing)
- [Google Cloud Vector Search performance blog](https://cloud.google.com/blog/products/ai-machine-learning/build-fast-and-scalable-ai-applications-with-vertex-ai)
- [Lightricks Cloud SQL vector case study](https://cloud.google.com/blog/products/databases/lightricks-delivers-dynamic-search-with-cloud-sql-vector-support)
- [Spanner vector search best practices](https://docs.cloud.google.com/spanner/docs/vector-search-best-practices)

## LangChain / LangSmith

- [LangChain RAG docs](https://docs.langchain.com/oss/python/langchain/rag)
- [LangSmith docs](https://docs.langchain.com/langsmith/home)
- [LangSmith observability](https://docs.langchain.com/langsmith/observability)
- [LangSmith deployment](https://docs.langchain.com/langsmith/deployment)
- [LangSmith self-hosted](https://docs.langchain.com/langsmith/self-hosted)
- [LangSmith CI/CD pipeline example](https://docs.langchain.com/langsmith/cicd-pipeline-example)
- [LangSmith RAG evaluation tutorial](https://docs.langchain.com/langsmith/evaluate-rag-tutorial)

## LlamaIndex

- [LlamaIndex framework docs](https://developers.llamaindex.ai/python/framework/)
- [LlamaIndex production RAG guide](https://developers.llamaindex.ai/python/framework/optimizing/production_rag/)
- [LlamaIndex observability docs](https://developers.llamaindex.ai/python/framework/module_guides/observability/)
- [LlamaAgents production multi-agent blog](https://www.llamaindex.ai/blog/introducing-llama-agents-a-powerful-framework-for-building-production-multi-agent-ai-systems)
- [Observability in agentic document workflows](https://www.llamaindex.ai/blog/observability-in-agentic-document-workflows)


## Notes on evidence quality

- Official vendor documentation is strongest for architecture, limits, and security controls.
- Pricing pages are volatile and should be rechecked before financial modeling.
- Engineering blogs and case studies are useful but may describe narrow workloads.
- Published vector-search latency should not be treated as full answer latency.
- Framework documentation is strongest for orchestration and observability patterns, not for backend-specific performance claims.
