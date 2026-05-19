# 02 — Terraform Constructs and Repository Patterns

## 1. HCL and file structure

Terraform uses HCL. The configuration is typically split across several `.tf` files in a root module. Terraform loads all `.tf` files in the directory together, so filenames are for human organization, not execution order.

Recommended root-module structure:

```text
environments/
  dev/
    main.tf
    providers.tf
    variables.tf
    outputs.tf
    backend.tf
    dev.tfvars
  staging/
    main.tf
    providers.tf
    variables.tf
    outputs.tf
    backend.tf
    staging.tfvars
  prod/
    main.tf
    providers.tf
    variables.tf
    outputs.tf
    backend.tf
    prod.tfvars

modules/
  network/
  kms/
  object-storage/
  vector-store/
  gpu-pool/
  model-endpoint/
  observability/
```

Alternative monorepo structure by platform layer:

```text
infra/
  00-foundation/
    prod/
    staging/
  10-shared-ml-platform/
    prod/
    staging/
  20-rag-apps/
    advisor-app/
      prod/
      staging/
  modules/
```

Use this when the foundation layer should have a different approval path from app-specific infrastructure.

## 2. Providers

Providers are plugins that map Terraform resources and data sources to cloud or SaaS APIs. For an ML/RAG stack, common providers include:

| Provider | Typical use |
|---|---|
| `hashicorp/aws` | VPC, IAM, S3, EKS, SageMaker, OpenSearch, Bedrock-related IAM/networking |
| `hashicorp/google` | VPC, GKE, Vertex AI, Cloud Storage, IAM |
| `hashicorp/azurerm` | VNet, AKS, Azure ML, Key Vault, Storage, Cognitive Services/OpenAI resources |
| `hashicorp/kubernetes` | namespaces, service accounts, deployments, config maps |
| `hashicorp/helm` | Helm chart installs for Milvus, Weaviate, Qdrant, observability |
| vendor providers | Pinecone, Databricks, Snowflake, Confluent, Grafana, Datadog, etc. |

Provider version constraints belong in the `terraform` block:

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}
```

Commit `.terraform.lock.hcl` so automation uses consistent provider versions.

## 3. Variables, locals, and outputs

### Variables

Variables are module inputs. In production modules, use types, descriptions, validation, and safe defaults.

```hcl
variable "env" {
  description = "Deployment environment"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be dev, staging, or prod."
  }
}

variable "gpu_node_count_max" {
  description = "Maximum GPU nodes for autoscaling"
  type        = number
  default     = 2

  validation {
    condition     = var.gpu_node_count_max <= 10
    error_message = "GPU max size must be <= 10 unless the module is explicitly changed."
  }
}
```

### Locals

Locals centralize derived values.

```hcl
locals {
  common_tags = {
    project     = var.project
    env         = var.env
    managed_by  = "terraform"
    cost_center = var.cost_center
  }
}
```

### Outputs

Outputs expose values to humans, downstream modules, or automation.

```hcl
output "embedding_queue_url" {
  value       = aws_sqs_queue.embedding.url
  description = "Queue used by embedding workers"
}

output "db_password" {
  value     = random_password.db.result
  sensitive = true
}
```

Avoid outputting secrets when a secrets manager reference can be output instead.

## 4. Modules

A module is a reusable package of Terraform configuration. A root module calls child modules.

### Good module design principles

- Expose stable, intention-revealing inputs.
- Hide provider-specific boilerplate where useful.
- Do not hide critical blast-radius settings.
- Include outputs that downstream stacks actually need.
- Version shared modules by Git tag or registry version.
- Include examples and a minimal test plan.

### Example module call

```hcl
module "embedding_endpoint" {
  source = "git::ssh://git@github.com/org/platform-modules.git//model-endpoint?ref=v1.4.2"

  name                 = "embedding-${var.env}"
  env                  = var.env
  model_name           = "text-embedding-model"
  min_replicas         = 2
  max_replicas         = 10
  private_network_id   = module.network.private_network_id
  kms_key_id           = module.kms.key_id
  log_retention_days   = 30
  request_timeout_ms   = 3000
  tags                 = local.common_tags
}
```

## 5. Data sources

Data sources read existing infrastructure. They are useful when foundation resources are managed by another team or stack.

```hcl
data "aws_vpc" "shared" {
  tags = {
    Name = "shared-prod-vpc"
  }
}

resource "aws_security_group" "model_endpoint" {
  name   = "model-endpoint-${var.env}"
  vpc_id = data.aws_vpc.shared.id
}
```

### Caution

Data sources can hide dependencies. If the upstream resource changes unexpectedly, a downstream plan can change too. Use explicit remote-state outputs or a service catalog when strict contracts are needed.

## 6. Lifecycle controls

Lifecycle settings change how Terraform treats resources.

```hcl
resource "aws_opensearch_domain" "vector_search" {
  domain_name = "rag-${var.env}"

  lifecycle {
    prevent_destroy = true
  }
}
```

Useful lifecycle settings:

| Setting | Use case | Caution |
|---|---|---|
| `prevent_destroy` | protect prod DBs, vector indexes, buckets | can block legitimate teardown; requires deliberate override |
| `create_before_destroy` | replace without downtime | not all resources support simultaneous duplicates |
| `ignore_changes` | tolerate external autoscaler fields | can mask drift if abused |
| `replace_triggered_by` | force replacement when dependency changes | can cause expensive rebuilds |

## 7. Naming and tagging

Every ML/RAG resource should carry labels/tags that support ownership, environment scoping, cost allocation, and incident triage.

Recommended tags:

```hcl
locals {
  tags = {
    managed_by      = "terraform"
    project         = var.project
    service         = var.service
    env             = var.env
    owner           = var.owner
    data_class      = var.data_class
    cost_center     = var.cost_center
    model_family    = var.model_family
    index_version   = var.index_version
  }
}
```

For static foundation resources, `index_version` may not apply. For RAG release resources, it is critical.

## 8. Terraform repo patterns

### Pattern A — app repo owns app infra

```text
app/
  src/
  Dockerfile
  infra/
    main.tf
    variables.tf
    prod.tfvars
```

Good for small teams and simple stacks. Risk: weak platform governance.

### Pattern B — central infra monorepo

```text
platform-infra/
  modules/
  environments/
  policies/
  pipelines/
```

Good for platform teams and enterprise governance. Risk: bottlenecks if every small app change needs central approval.

### Pattern C — platform modules + app-owned envs

```text
platform-modules/
  modules/vector-store
  modules/model-endpoint

rag-advisor-app/
  infra/prod/main.tf  # calls platform modules
```

Often the best compromise: central modules encode guardrails; product teams own app-specific composition.

## 9. Suggested structure for RAG platform modules

```text
modules/
  rag-foundation/
    network.tf
    kms.tf
    iam.tf
    outputs.tf
  vector-store/
    main.tf
    variables.tf
    outputs.tf
  model-endpoint/
    main.tf
    autoscaling.tf
    monitoring.tf
  ingestion-workers/
    queues.tf
    worker_pool.tf
    iam.tf
  reindex-release/
    index_blue.tf
    index_green.tf
    routing_alias.tf
    validation_hooks.tf
```

The reindex module is unusual but valuable: it treats retrieval index versions as deployable infrastructure.
