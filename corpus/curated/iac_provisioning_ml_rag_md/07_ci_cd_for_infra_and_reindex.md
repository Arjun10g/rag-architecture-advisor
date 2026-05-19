# 07 — CI/CD for Infrastructure and RAG Reindex Pipelines

## 1. Two pipelines, not one

Production ML/RAG platforms need two related but distinct pipelines:

1. **Infrastructure pipeline:** provisions and changes cloud/platform resources.
2. **Reindex pipeline:** builds, validates, and promotes retrieval indexes when data, parser, chunker, embedding model, metadata, or vector DB settings change.

They should interact, but not be collapsed into one opaque job.

## 2. Infrastructure CI/CD pipeline

### Pull request pipeline

```text
PR opened
  -> checkout
  -> terraform fmt -check
  -> terraform init
  -> terraform validate
  -> static IaC scan
  -> terraform plan -out
  -> terraform show -json
  -> policy-as-code check
  -> cost estimate
  -> publish plan summary to PR
```

### Merge/apply pipeline

```text
merge to protected branch
  -> re-run init/validate/plan
  -> verify plan matches approved intent
  -> environment approval for prod
  -> apply saved plan
  -> smoke tests
  -> notify owners
  -> persist logs/artifacts
```

### Important controls

- Use OIDC/workload identity instead of long-lived cloud keys.
- Apply only from protected branches.
- Store plans as short-lived artifacts.
- Require manual approval for production and destructive changes.
- Separate plan role and apply role if governance requires it.
- Use remote state locking.

## 3. Plan summarization

Raw Terraform plans can be long. Generate a concise summary for reviewers:

```text
Creates: 12
Updates: 4
Deletes: 0
Replaces: 1
High-risk:
  - aws_iam_policy.ingestion_policy updated: broader S3 read scope
  - google_container_node_pool.gpu_pool max_nodes: 4 -> 12
  - vector index replica count: 1 -> 3
```

This can be implemented using plan JSON and a custom script.

## 4. Drift pipeline

Run drift detection on a schedule.

```text
nightly or weekly
  -> terraform init
  -> terraform plan -detailed-exitcode
  -> if drift detected, create issue/Slack alert
  -> attach plan summary
  -> owner classifies as intentional or accidental
```

For production ML/RAG, drift detection should be more frequent for high-risk resources such as public exposure, IAM, KMS, model endpoints, and GPU pool limits.

## 5. Reindex pipeline

### Why reindexing needs CI/CD discipline

A RAG index is a production artifact. Its quality depends on parser version, chunking strategy, embedding model, metadata schema, ACL propagation, deduplication, and vector DB parameters. Overwriting the live index in place makes rollback and evaluation difficult.

### Reindex pipeline stages

```text
1. Trigger
   - data change, parser change, chunking change, embedding model upgrade, ACL schema change

2. Plan/index spec
   - declare corpus snapshot, parser version, chunker version, embedding model, dimension, metric

3. Provision or scale build infra
   - embedding workers, queues, temporary storage, temporary index

4. Parse and chunk
   - produce normalized document/chunk artifacts

5. Embed
   - batch embeddings with retry, rate limits, cost tracking

6. Build new index
   - create index_vNext and upsert vectors

7. Validate
   - retrieval metrics, generation metrics, ACL tests, latency tests, cost estimates

8. Canary or shadow
   - send shadow queries or small traffic slice

9. Promote
   - switch alias/router from index_vCurrent to index_vNext

10. Monitor and rollback
   - watch latency, recall proxy, error rate, hallucination rate, spend

11. Retire old index
   - retain for rollback window, then delete with approval
```

## 6. Index version manifest

Each index release should have a manifest.

```yaml
index_version: advisor-rag-v43
created_at: 2026-05-19T04:00:00Z
corpus_snapshot: s3://company-rag-prod/snapshots/2026-05-19/
parser_version: doc-parser@2.1.0
chunker_version: recursive-window@1.7.3
embedding_model: text-embedding-model-v3
embedding_dimension: 1536
vector_metric: cosine
metadata_schema_version: 5
acl_schema_version: 3
evaluation_set: rag-gold-v12
promotion_status: candidate
```

The manifest should be stored with the index artifacts and referenced in deployment metadata.

## 7. Terraform and reindex boundaries

### Terraform manages

- vector index resources when provider supports them;
- index aliases/routing config;
- worker infrastructure;
- queues;
- IAM;
- storage;
- monitoring;
- feature flags or config stores if appropriate.

### Reindex pipeline manages

- parsing;
- chunking;
- embedding;
- vector upsert/delete;
- eval execution;
- candidate manifest;
- promotion decision payload.

## 8. Blue-green index deployment

```text
index_blue  = live
index_green = candidate

Build green
  -> eval green
  -> shadow compare blue vs green
  -> route 5% to green
  -> promote green to 100%
  -> blue retained for rollback
```

### Terraform sketch

```hcl
variable "active_index_version" {
  type        = string
  description = "Index version receiving production traffic"
}

resource "aws_ssm_parameter" "active_index" {
  name  = "/rag/${var.env}/active_index_version"
  type  = "String"
  value = var.active_index_version
}
```

The app reads the active index version from a config store. Terraform updates the pointer after evaluation approval. Some vector DBs support aliases directly; in that case Terraform or the provider-specific API can manage the alias.

## 9. CI/CD for model endpoints

For model serving, use similar progressive delivery:

```text
new model artifact
  -> deploy endpoint revision
  -> run offline eval
  -> shadow traffic
  -> canary
  -> promote
  -> retain old revision
```

Terraform may manage endpoint infrastructure, while the model registry/pipeline manages model version promotion. The exact split depends on the serving platform.

## 10. Approval gates

| Gate | Required evidence |
|---|---|
| infra apply | reviewed plan, passing policy, cost estimate |
| index promotion | retrieval eval, generation eval, ACL test, latency/cost result |
| model promotion | model eval, safety eval, latency/cost result |
| destructive cleanup | rollback window elapsed, backup confirmed, owner approval |

## 11. Failure handling

### Infrastructure apply failure

- Do not retry blindly.
- Inspect partial resources.
- Refresh state.
- Fix code or import partial resources.
- Re-plan before apply.

### Reindex failure

- Candidate index should not receive production traffic.
- Preserve logs and failed manifest.
- Clean temporary resources via TTL or explicit cleanup pipeline.
- Report failure stage: parse, embed, upsert, eval, canary.

### Canary failure

- Route traffic back to previous index.
- Freeze promotion.
- Compare failed queries.
- Decide whether issue is parser/chunker/embedder/index/reranker/generator.

## 12. Metrics for infra and reindex pipelines

### Infra pipeline metrics

- plan duration;
- apply duration;
- policy failures by type;
- drift count;
- failed applies;
- mean time to reconcile drift;
- number of manual console changes.

### Reindex metrics

- documents processed;
- parse failures;
- chunk count distribution;
- embedding throughput;
- embedding cost;
- vector upsert throughput;
- retrieval recall/nDCG/MRR on gold set;
- answer faithfulness/context precision if generation eval is included;
- P50/P95/P99 retrieval latency;
- index size and storage cost;
- ACL leakage test pass/fail.

## 13. Recommended pipeline architecture

```text
GitHub Actions / GitLab CI / Azure DevOps
  -> Terraform plan/apply
  -> policy checks
  -> artifact publishing

Orchestrator: Airflow / Dagster / Prefect / Argo Workflows / Step Functions
  -> parse/chunk/embed/index/evaluate/promote

Config store / feature flag / vector alias
  -> active index pointer

Observability
  -> traces, logs, eval results, index metrics
```

Keep infrastructure CI/CD and data/index orchestration connected by explicit artifacts: index manifest, evaluation report, and promotion request.
