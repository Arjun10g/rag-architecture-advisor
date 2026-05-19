# 01 — Seven IaC Principles Mapped to Terraform Constructs

## Overview

Terraform is a declarative IaC tool: configuration describes the intended infrastructure state, providers translate resource declarations into API operations, and state tracks the mapping between configuration and real-world infrastructure. The important advisor move is to translate broad IaC principles into concrete Terraform constructs.

## Principle 1 — Codify everything important

### Meaning

All infrastructure that affects security, reliability, cost, data access, model behavior, or deployment repeatability should be codified. In ML/RAG systems, that includes more than VMs and networks. It includes storage buckets, vector indexes, Kubernetes node pools, model endpoints, service accounts, IAM bindings, KMS keys, queues, secrets references, monitoring dashboards, and CI/CD roles.

### Terraform constructs

| Need | Terraform construct |
|---|---|
| Create cloud resources | `resource` blocks |
| Read existing resources | `data` blocks |
| Configure cloud/SaaS APIs | `provider` blocks |
| Reuse platform patterns | `module` blocks |
| Environment-specific settings | `variable` values and `.tfvars` |
| Export connection details | `output` blocks |
| Constrain provider versions | `required_providers` and `.terraform.lock.hcl` |

### Example

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "rag_corpus" {
  bucket = "${var.project}-${var.env}-rag-corpus"

  tags = {
    project = var.project
    env     = var.env
    owner   = var.owner
  }
}
```

### ML/RAG interpretation

Codification should cover the **RAG release surface**:

- raw document buckets;
- parsed/chunked document stores;
- embedding queues;
- vector index resources;
- index aliases or routing tables;
- embedding/model endpoints;
- reranker endpoints;
- evaluation datasets and metric stores;
- access policies for document-level ACL propagation.

### Failure mode

Codifying only “base infra” but not indexes, endpoints, and ingestion workers leads to hidden manual state. The architecture may look reproducible while the actual retrieval behavior depends on a manually configured index or model endpoint.

---

## Principle 2 — Declare desired state, not manual steps

### Meaning

The IaC configuration should describe the final intended infrastructure. Terraform decides the dependency graph and operation order. This reduces runbook fragility and makes changes reviewable.

### Terraform constructs

| Need | Terraform construct |
|---|---|
| Desired target resource shape | `resource` arguments |
| Dependency inference | references such as `aws_vpc.main.id` |
| Explicit dependency edge | `depends_on` |
| Lifecycle behavior | `lifecycle` block |
| Dynamic multiplicity | `for_each`, `count` |
| Idempotent application | `terraform plan` then `terraform apply` |

### Example

```hcl
resource "aws_kms_key" "rag" {
  description             = "KMS key for RAG platform ${var.env}"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "corpus" {
  bucket = aws_s3_bucket.rag_corpus.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.rag.arn
      sse_algorithm     = "aws:kms"
    }
  }
}
```

### ML/RAG interpretation

The target state should include runtime constraints:

- GPU pool size and autoscaling limits;
- endpoint autoscaling minimum/maximum replicas;
- vector DB pod/node class;
- storage class and backup schedule;
- private networking and egress restrictions;
- KMS-encrypted data stores;
- observability and alerting.

### Failure mode

If provisioning relies on imperative scripts after Terraform, the true system state is split across Terraform and shell scripts. That makes drift detection and rollback harder.

---

## Principle 3 — Make change reviewable

### Meaning

IaC should make infrastructure changes visible before they happen. Terraform’s `plan` is central because it shows create/update/delete operations before `apply`.

### Terraform constructs and workflow

```bash
terraform fmt -check
terraform init
terraform validate
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json
# policy checks here
terraform apply tfplan.binary
```

| Review object | Purpose |
|---|---|
| Git diff | Human review of HCL changes |
| `terraform plan` | Planned infrastructure changes |
| JSON plan | Machine-readable input for OPA/Sentinel/custom policy |
| policy result | Security/cost/compliance gate |
| apply logs | audit trail |

### ML/RAG interpretation

Plan review should catch high-cost and high-risk ML changes:

- GPU instance type increases;
- public endpoint exposure;
- disabling encryption;
- vector DB storage class changes;
- index replica count changes;
- deletion of production index or corpus bucket;
- IAM broadening for ingestion workers.

### Failure mode

Applying directly from local machines bypasses review and makes cloud changes unauditable. This is especially dangerous when one command can destroy model endpoints, vector indexes, or production data buckets.

---

## Principle 4 — Use reusable modules

### Meaning

Teams should not copy raw resource blocks everywhere. Platform teams should package safe defaults into reusable modules.

### Terraform constructs

```hcl
module "rag_vector_store" {
  source = "../../modules/vector-store"

  env                 = var.env
  project             = var.project
  private_network_id  = module.network.private_network_id
  kms_key_id          = module.security.kms_key_id
  replicas            = 3
  deletion_protection = true
}
```

### Module interface pattern

A good module should expose parameters that product teams actually need while hiding dangerous details.

| Module input | Why it matters |
|---|---|
| `env` | naming, tagging, policy branching |
| `project` | cost allocation |
| `network_id` | private deployment |
| `kms_key_id` | encryption standardization |
| `replicas` | reliability/cost tuning |
| `deletion_protection` | production safety |
| `allowed_cidr_blocks` | network access control |
| `tags`/`labels` | governance and chargeback |

### ML/RAG module catalog

- `network-foundation`
- `iam-service-account`
- `kms-key`
- `object-storage-corpus`
- `embedding-worker-queue`
- `vector-store`
- `model-endpoint`
- `gpu-node-pool`
- `evaluation-store`
- `observability-stack`
- `blue-green-index-router`

### Failure mode

A module can become a “black box” that hides too much. If teams cannot understand the blast radius of a module update, module versioning and changelogs become mandatory.

---

## Principle 5 — Separate state and environments deliberately

### Meaning

Terraform state is sensitive and operationally critical. It maps configuration to real-world objects and may contain secrets or sensitive attributes. State should be remote, encrypted, locked, access-controlled, and scoped by blast radius.

### Terraform constructs

| Need | Construct |
|---|---|
| Remote state | `backend` block or HCP Terraform workspace |
| Locking | backend-native lock, e.g. S3 + DynamoDB / cloud lock / HCP Terraform |
| Environment scoping | separate state files, directories, workspaces, or stacks |
| Cross-stack reads | `terraform_remote_state` or explicit outputs consumed by pipeline |
| Sensitive outputs | `sensitive = true` |

### Environment options

| Pattern | Good for | Risk |
|---|---|---|
| Workspaces | same config, low-difference envs | accidental workspace confusion; weak isolation if overused |
| Directory per env | strong explicitness, different env shapes | duplication unless modules are strong |
| Repository per platform layer | strong ownership boundaries | cross-repo dependency management |
| HCP/Terraform Cloud workspaces | managed remote runs, policy, audit | platform dependency and cost |

### ML/RAG interpretation

Use separate state for:

- foundation networking/security;
- shared ML platform services;
- application-specific model endpoints;
- per-index release infrastructure if index rebuilds are frequent;
- ephemeral benchmark/evaluation environments.

### Failure mode

Putting all resources into one giant state file makes plans slow and increases blast radius. Destroying or refactoring a single RAG app can accidentally affect shared networking, GPUs, or production vector DBs.

---

## Principle 6 — Enforce policy before apply

### Meaning

Policy-as-code checks should run before changes reach production. Policies should cover security, privacy, cost, reliability, and naming/ownership.

### Terraform-related policy inputs

| Input | Tools |
|---|---|
| HCL source | Checkov, tfsec-style scanners, Conftest on HCL/JSON |
| Terraform plan JSON | OPA, Sentinel, Conftest, custom scripts |
| Cloud runtime config | cloud security posture management, drift monitors |
| Kubernetes manifests | OPA Gatekeeper, Kyverno, Checkov |

### Example policies for ML/RAG

- No public vector DB endpoints in production.
- GPU node pools require max-size and budget labels.
- Corpus buckets require KMS encryption and object versioning.
- Model endpoints must be private unless explicitly approved.
- Ingestion workers cannot have wildcard read access to all document stores.
- Production index resources require deletion protection.
- Any plan deleting a production vector index requires manual approval.

### Failure mode

If policy checks only scan static HCL, they may miss computed plan values. If they only scan plan JSON, they may miss intent, comments, or module-level context. Mature teams use both source-level and plan-level checks.

---

## Principle 7 — Automate delivery and reconciliation

### Meaning

IaC should be run through consistent automation rather than ad hoc local commands. Automation provides repeatability, audit logs, policy gates, and safe approval workflows.

### Terraform workflow

```text
Pull request opened
  -> fmt / validate / static IaC scan
  -> plan against target environment
  -> convert plan to JSON
  -> policy-as-code gate
  -> human review
  -> merge
  -> apply from protected branch with environment approval
  -> post-apply tests
  -> drift schedule
```

### ML/RAG extension

RAG systems require an additional data/index release workflow:

```text
Chunking or embedding model change
  -> provision or scale embedding workers
  -> build new index version
  -> run retrieval/generation evals
  -> deploy index alias/cutover config
  -> canary traffic
  -> monitor quality/latency/cost
  -> promote or rollback
  -> tombstone old index after retention window
```

### Failure mode

Treating reindexing as a manual data job causes undocumented production behavior. The index version should be promoted like a deployable artifact, not silently overwritten in place.
