# 05 — IaC for ML and RAG Stacks

## 1. ML/RAG infrastructure is not just compute

A RAG platform combines data systems, model serving, retrieval infrastructure, orchestration, observability, security, and release management. IaC should describe the stable infrastructure and the control points for changing data/model/index versions.

## 2. Reference architecture

```text
                    ┌──────────────────────────┐
                    │ CI/CD + IaC Pipeline      │
                    │ plan, policy, apply       │
                    └────────────┬─────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│ Foundation Layer                                                  │
│ VPC/VNet, private subnets, IAM, KMS, DNS, secrets, logs, metrics  │
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
┌────────────▼─────────────┐     ┌───────────▼────────────┐
│ Ingestion/Data Layer      │     │ Serving Layer           │
│ object store, queues,     │     │ model endpoints,        │
│ parsers, embedding jobs   │     │ GPU/CPU pools, gateway  │
└────────────┬─────────────┘     └───────────┬────────────┘
             │                               │
┌────────────▼─────────────┐     ┌───────────▼────────────┐
│ Retrieval Layer           │     │ Evaluation/Observability │
│ vector DB, metadata DB,   │     │ traces, RAG evals,       │
│ reranker, index aliases   │     │ latency, recall, cost    │
└──────────────────────────┘     └────────────────────────┘
```

## 3. What Terraform should manage vs what pipelines should manage

| Component | Terraform should manage | Data/ML pipeline should manage |
|---|---|---|
| Object storage | buckets, encryption, lifecycle, IAM | document objects, parsed artifacts |
| Vector DB | cluster/index resource, networking, backups, auth | vector contents, batch upserts, deletes |
| Model serving | endpoint infra, autoscaling, private networking, IAM | model artifact promotion, model card/eval approval |
| GPU pools | node pools, quotas, labels, autoscaling bounds | job scheduling, batch embedding workloads |
| Metadata DB | database, schemas if supported, backups | row-level document metadata |
| Feature store | workspace, online/offline store infra | feature definitions and materialization jobs |
| Observability | log sinks, dashboards, metrics, alerts | app-level spans, eval metrics |
| Reindexing | alias/cutover resources, temporary build infra | chunking, embeddings, index population, validation |

Advisor principle: **Terraform creates and governs the rails; ML/data pipelines move the trains.**

## 4. Provisioning vector databases

### Managed vector DB pattern

For Pinecone, Zilliz Cloud, Weaviate Cloud, Qdrant Cloud, Elastic/OpenSearch, Vespa Cloud, or cloud-native vector services, Terraform may provision:

- project/organization resources;
- indexes/collections;
- dimensions and metric type;
- pods/serverless capacity if supported;
- backups and retention;
- API keys/secrets references;
- private endpoints or allowed CIDRs;
- monitoring integrations.

Example pseudo-module:

```hcl
module "vector_index" {
  source = "../../modules/vector-index"

  name              = "advisor-rag-${var.env}-${var.index_version}"
  dimension         = 1536
  metric            = "cosine"
  env               = var.env
  replicas          = var.env == "prod" ? 3 : 1
  deletion_protection = var.env == "prod"
  private_network_id  = module.network.private_network_id
  tags              = local.tags
}
```

### Self-hosted vector DB pattern on Kubernetes

Terraform often manages:

- Kubernetes cluster/node pools;
- namespaces;
- Helm releases;
- persistent volumes/storage classes;
- service accounts;
- network policies;
- ingress/private load balancers;
- backups;
- Prometheus/Grafana dashboards.

Example Helm pattern:

```hcl
resource "kubernetes_namespace" "vector" {
  metadata {
    name = "vector-${var.env}"
  }
}

resource "helm_release" "qdrant" {
  name       = "qdrant"
  namespace  = kubernetes_namespace.vector.metadata[0].name
  repository = "https://qdrant.github.io/qdrant-helm"
  chart      = "qdrant"
  version    = var.qdrant_chart_version

  values = [templatefile("${path.module}/values/qdrant.yaml.tftpl", {
    replicas      = var.replicas
    storage_class = var.storage_class
    storage_size  = var.storage_size
  })]
}
```

## 5. GPU pools

GPU infrastructure is costly and quota-constrained. IaC should define hard bounds and scheduling labels.

### Controls

- autoscaling min/max;
- instance/GPU type allowlist;
- taints/tolerations for GPU workloads;
- labels for workload routing;
- budget/cost tags;
- quota checks;
- preemptible/spot configuration where appropriate;
- separate training, embedding, and inference pools.

### Pattern

```hcl
module "gpu_embedding_pool" {
  source = "../../modules/k8s-gpu-node-pool"

  name              = "embedding-gpu-${var.env}"
  gpu_type          = var.gpu_type
  min_nodes         = 0
  max_nodes         = var.env == "prod" ? 10 : 2
  spot_enabled      = var.env != "prod"
  workload_label    = "embedding"
  taint_key         = "workload"
  taint_value       = "embedding-gpu"
  tags              = local.tags
}
```

### Failure mode

Leaving GPU max autoscaling unconstrained can produce sudden large bills. IaC policy should block unbounded GPU pools.

## 6. Model endpoints

Model endpoints may be managed cloud services, Kubernetes deployments, Ray Serve, KServe, SageMaker, Vertex AI, Azure ML, Databricks Model Serving, or custom inference gateways.

Terraform should manage:

- endpoint resource;
- IAM/service identity;
- network/private endpoint;
- autoscaling bounds;
- model artifact reference if stable enough;
- logging and tracing;
- canary or traffic split configuration if supported;
- secrets references.

### Endpoint deployment sketch

```hcl
module "reranker_endpoint" {
  source = "../../modules/model-endpoint"

  name              = "reranker-${var.env}"
  model_artifact_uri = var.reranker_model_artifact_uri
  instance_type      = var.reranker_instance_type
  min_replicas       = 2
  max_replicas       = 8
  private_only       = true
  timeout_ms         = 2000
  tags               = local.tags
}
```

## 7. Feature stores and artifact registries

Even RAG systems often need feature stores or artifact stores when retrieval is combined with predictive models or routing models.

Terraform should manage:

- registry/workspace resources;
- storage backends;
- IAM roles;
- network access;
- retention policies;
- lifecycle policies;
- encryption;
- CI/CD identities.

## 8. Document and metadata stores

RAG systems usually need both object storage and structured metadata.

### Object storage

- raw documents;
- normalized documents;
- parsed pages/sections/tables;
- chunks;
- embedding batch outputs;
- evaluation artifacts.

### Metadata DB

- document IDs;
- chunk IDs;
- source URI;
- tenant ID;
- ACL hash/version;
- embedding model version;
- parser version;
- index version;
- tombstone/deletion status.

IaC should create the storage and access boundaries. Application migrations manage schema evolution unless the DB provider supports robust Terraform schema management.

## 9. Private networking

Private networking is central for enterprise ML/RAG because retrieved documents may contain sensitive data.

IaC should define:

- private subnets;
- private service connect/private link endpoints;
- security groups/firewalls;
- VPC peering;
- DNS zones;
- NAT/egress controls;
- network policies in Kubernetes;
- service mesh policies if used.

## 10. Observability

Provision observability alongside infrastructure:

- logs for ingestion workers and endpoints;
- traces for retrieval/generation chains;
- metrics for latency, token usage, embedding throughput, query throughput, index size, recall/eval score, GPU utilization, and queue depth;
- dashboards for platform and app teams;
- alerts for failed ingestion, stale indexes, high hallucination/failure rates, vector DB saturation, and GPU spend anomalies.

## 11. Blue-green vector index release

### Architecture

```text
current alias: advisor-search-prod -> index_v42
new build: index_v43

Build index_v43
  -> run retrieval evals
  -> shadow query test
  -> canary 5% traffic
  -> switch alias to index_v43
  -> monitor
  -> retain index_v42 for rollback window
  -> delete/tombstone index_v42 after approval
```

### Terraform role

Terraform can manage:

- index resources if provider supports them;
- alias/routing config;
- IAM permissions;
- monitoring and alerts;
- deletion protection;
- retention lifecycle.

The data pipeline should populate vectors and run evaluation.

## 12. Reindex trigger matrix

| Trigger | Infrastructure implication |
|---|---|
| embedding model upgrade | new index dimension/metric may require new index |
| chunking strategy change | full rebuild; metadata schema may change |
| parser/layout update | partial or full rebuild depending on changed documents |
| ACL model change | may require metadata reindex and permission filter audit |
| vector DB parameter change | may require new collection/index |
| tenant migration | may require namespace/index split |

## 13. Recommended module set for RAG advisor project

```text
modules/
  rag-storage
  rag-metadata-db
  rag-vector-index
  rag-embedding-workers
  rag-model-endpoint
  rag-reranker-endpoint
  rag-index-router
  rag-observability
  rag-eval-store
  rag-security-baseline
```

Each module should expose environment, owner, data classification, cost center, KMS key, network, and deletion protection controls.
