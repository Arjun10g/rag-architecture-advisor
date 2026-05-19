# 07 — References

This file collects the main sources used for the Markdown report bundle. It emphasizes primary papers, official documentation, and model/vendor docs.

## Foundational RAG and retrieval evaluation

1. Lewis et al. **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks**. NeurIPS 2020.  
   https://arxiv.org/abs/2005.11401

2. Thakur et al. **BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models**. 2021.  
   https://arxiv.org/abs/2104.08663

## Sparse and learned sparse retrieval

3. Formal et al. **SPLADE: Sparse Lexical and Expansion Model for First Stage Ranking**. SIGIR 2021.  
   https://arxiv.org/abs/2107.05720

4. Formal et al. **SPLADE v2: Sparse Lexical and Expansion Model for Information Retrieval**. 2021.  
   https://arxiv.org/abs/2109.10086

## Late interaction

5. Khattab and Zaharia. **ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT**. 2020.  
   https://arxiv.org/abs/2004.12832

6. Santhanam et al. **ColBERTv2: Efficient and Effective Retrieval via Lightweight Late Interaction**. 2021.  
   https://arxiv.org/abs/2112.01488

7. Santhanam et al. **PLAID: An Efficient Engine for Late Interaction Retrieval**. 2022.  
   https://arxiv.org/abs/2205.09707

## Fusion and hybrid retrieval

8. Microsoft Azure AI Search. **Hybrid search overview**.  
   https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview

9. Rackauckas. **RAG-Fusion: a New Take on Retrieval-Augmented Generation**. 2024.  
   https://arxiv.org/abs/2402.03367

## Query transforms

10. Gao et al. **Precise Zero-Shot Dense Retrieval without Relevance Labels** / HyDE.  
    https://arxiv.org/abs/2212.10496

11. LangChain docs. **HyDE retriever**.  
    https://docs.langchain.com/oss/javascript/integrations/retrievers/hyde

12. LangChain docs. **MultiQueryRetriever**.  
    https://reference.langchain.com/python/langchain-classic/retrievers/multi_query/MultiQueryRetriever

13. Zheng et al. **Take a Step Back: Evoking Reasoning via Abstraction in Large Language Models**. 2023.  
    https://arxiv.org/abs/2310.06117

14. LangChain docs. **SelfQueryRetriever**.  
    https://reference.langchain.com/python/langchain-classic/retrievers/self_query/base/SelfQueryRetriever

15. MongoDB docs. **Self-query retrieval with Atlas Vector Search and LangChain**.  
    https://www.mongodb.com/docs/atlas/ai-integrations/langchain/self-query-retrieval/

## Adaptive and agentic retrieval

16. Asai et al. **Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection**. 2023.  
    https://arxiv.org/abs/2310.11511

17. Yan et al. **Corrective Retrieval Augmented Generation**. 2024.  
    https://arxiv.org/abs/2401.15884

18. Jiang et al. **Active Retrieval Augmented Generation** / FLARE. 2023.  
    https://arxiv.org/abs/2305.06983

19. Jeong et al. **Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity**. 2024.  
    https://arxiv.org/abs/2403.14403

20. Yalavarthi. **Open-Source Reproduction and Explainability Analysis of CRAG**. 2026.  
    https://arxiv.org/abs/2603.16169

## GraphRAG and KG-augmented retrieval

21. Edge et al. **From Local to Global: A Graph RAG Approach to Query-Focused Summarization**. 2024.  
    https://arxiv.org/abs/2404.16130

22. Guo et al. **LightRAG: Simple and Fast Retrieval-Augmented Generation**. 2024.  
    https://arxiv.org/abs/2410.05779

23. Fan et al. **MiniRAG: Towards Extremely Simple Retrieval-Augmented Generation**. 2025.  
    https://arxiv.org/abs/2501.06713

## Rerankers and LLM ranking

24. BAAI. **bge-reranker-v2-m3 model card**.  
    https://huggingface.co/BAAI/bge-reranker-v2-m3

25. BAAI. **bge-reranker-v2-gemma model card**.  
    https://huggingface.co/BAAI/bge-reranker-v2-gemma

26. Mixedbread. **mxbai-rerank-v2 blog/model announcement**.  
    https://www.mixedbread.com/blog/mxbai-rerank-v2

27. Cohere. **Rerank API docs**.  
    https://docs.cohere.com/reference/rerank

28. Cohere. **Reranking best practices**.  
    https://docs.cohere.com/docs/reranking-best-practices

29. Jina AI. **jina-reranker-v2-base-multilingual model page**.  
    https://jina.ai/models/jina-reranker-v2-base-multilingual/

30. Jina AI. **jina-reranker-v3 model page**.  
    https://jina.ai/models/jina-reranker-v3/

31. Wang et al. **jina-reranker-v3: Last but Not Late Interaction for Document Reranking**. 2025.  
    https://arxiv.org/abs/2509.25085

32. Sun et al. **Is ChatGPT Good at Search? Investigating Large Language Models as Re-Ranking Agents** / RankGPT. 2023.  
    https://arxiv.org/abs/2306.17563

33. Pradeep et al. **RankZephyr: Effective and Robust Zero-Shot Listwise Reranking is a Breeze!** 2023.  
    https://arxiv.org/abs/2312.02724

34. Sharifymoghaddam et al. **RankLLM: A Python Package for Reranking with LLMs**. 2025.  
    https://arxiv.org/abs/2505.19284

## Additional studies and useful recent work

35. EasyRAG for network operations, including sparse retrieval + LLM reranking pattern.  
    https://arxiv.org/abs/2410.10315

36. LongRAG for long-context QA and RAG limitations.  
    https://arxiv.org/abs/2410.18050

37. MapReduce-style context use for lost-in-the-middle mitigation.  
    https://arxiv.org/abs/2412.15271

## Official docs mentioned in the broader report context

38. Google Cloud Vertex AI Vector Search hybrid search.  
    https://docs.cloud.google.com/vertex-ai/docs/vector-search/about-hybrid-search

39. Azure AI Search vector search overview.  
    https://learn.microsoft.com/en-us/azure/search/vector-search-overview

40. AWS OpenSearch Serverless vector search.  
    https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-vector-search.html
