# 03 — State, Environments, Drift, Import, and Refactoring

## 1. Terraform state

Terraform state records the mapping between configuration and real infrastructure. It is the reason Terraform can tell whether a resource already exists, needs to be updated, or should be destroyed. For production systems, local state is not sufficient.

## 2. Remote backends

Use a remote backend for team workflows. Backend options include S3, GCS, Azure Storage, Consul, PostgreSQL, Kubernetes, and HCP Terraform/Terraform Enterprise.

### Backend requirements

| Requirement | Why it matters |
|---|---|
| Remote storage | shared team access and CI/CD execution |
| Locking | prevents simultaneous applies corrupting state |
| Encryption | state can contain sensitive values |
| Versioning | recovery from accidental corruption or deletion |
| Access control | least privilege for plan/apply roles |
| Audit logs | incident and compliance evidence |

### Example S3 backend

```hcl
terraform {
  backend "s3" {
    bucket         = "company-terraform-state-prod"
    key            = "rag-platform/prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-state-locks"
    encrypt        = true
  }
}
```

For production, avoid hardcoding credentials. Use workload identity, OIDC, environment variables, or the CI provider's cloud auth integration.

## 3. State locking

Locking prevents concurrent state mutations. Without locking, two applies can race, causing broken or inconsistent state.

### Common locking patterns

| Backend | Locking pattern |
|---|---|
| S3 | DynamoDB lock table or native backend-supported locking depending on version/config |
| GCS | generation-based locking behavior |
| AzureRM | blob lease locking |
| HCP Terraform | managed run queue and state locking |
| Consul | Consul locks |

## 4. State blast-radius design

A common mistake is putting the entire platform into one state file. State should be split by ownership, lifecycle, and blast radius.

### Recommended split for ML/RAG

```text
state: foundation-prod
  VPC/VNet, subnets, private DNS, KMS, core IAM, base observability

state: ml-platform-prod
  shared model registry, shared vector DB cluster, GPU node pools, queues

state: rag-app-prod
  app-specific indexes, endpoint routes, app IAM, app dashboards

state: rag-index-release-prod-v2026-05-19
  temporary build resources, index version, validation artifacts, cutover hooks
```

## 5. Workspaces vs directory-per-environment

### Workspaces

Terraform workspaces allow multiple state instances for the same configuration directory.

Best for:

- same topology across environments;
- ephemeral review environments;
- simple dev/staging/prod differences;
- small teams with strong automation.

Avoid for:

- significantly different production topology;
- teams likely to run commands locally and forget the selected workspace;
- high-blast-radius infrastructure.

### Directory-per-environment

Directory-per-environment makes separation explicit.

```text
environments/
  dev/
  staging/
  prod/
```

Best for:

- strict production controls;
- different backend keys per environment;
- different providers/regions/accounts;
- environment-specific approval gates.

Risk: duplication. Mitigate with shared modules.

### Advisor recommendation

For enterprise ML/RAG systems, prefer **directory-per-environment plus shared modules** for stable infrastructure. Use **workspaces** for ephemeral preview stacks, temporary evaluation environments, or simple duplicated environments where the blast radius is small.

## 6. Plan/apply workflow

### Basic flow

```bash
terraform fmt -check
terraform init
terraform validate
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json
terraform apply tfplan.binary
```

### Why save the plan file?

Saving the plan ensures the reviewed plan is the exact plan being applied. This matters when policies and human approvals depend on the proposed changes.

### Production apply rules

- Never apply from a developer laptop to production.
- Apply only from CI/CD, Terraform Cloud, or another controlled runner.
- Require approval when plan includes `delete`, `replace`, public exposure, IAM broadening, KMS changes, GPU quota increases, or production data store changes.
- Store plan and apply logs.

## 7. Drift detection

Drift happens when the real infrastructure differs from Terraform state/configuration. Causes include manual console edits, external controllers, provider defaults, cloud-side changes, or resources modified by another IaC tool.

### Drift detection commands

```bash
terraform plan -detailed-exitcode
```

Common exit-code convention:

- `0`: no changes;
- `1`: error;
- `2`: changes present.

### Drift workflow

```text
scheduled drift job
  -> terraform init
  -> terraform plan -detailed-exitcode
  -> if exit 2: notify owners
  -> classify drift as intentional, accidental, or provider noise
  -> reconcile via code change, import, or manual rollback
```

### ML/RAG drift examples

| Drift | Risk |
|---|---|
| GPU autoscaling max manually increased | surprise cost spike |
| vector DB changed to public endpoint | data exposure |
| model endpoint min replicas reduced | latency/SLO regression |
| bucket encryption disabled | compliance violation |
| IAM wildcard added | data exfiltration risk |
| index deletion protection disabled | accidental data loss |

## 8. Importing existing resources

Terraform import brings existing infrastructure under Terraform state management. It does not automatically write perfect configuration for every resource; the configuration must match reality.

### Safe import sequence

```text
1. Inventory existing resources.
2. Decide target module/resource addresses.
3. Write Terraform config matching current resource attributes.
4. Run import into a non-prod/test state first when possible.
5. Run plan and reduce unexpected diffs.
6. Add lifecycle protections for critical resources.
7. Peer review and merge.
8. Lock down manual changes after import.
```

### Example import

```bash
terraform import aws_s3_bucket.rag_corpus my-existing-rag-corpus-bucket
terraform plan
```

### Import failure modes

| Failure | Explanation | Mitigation |
|---|---|---|
| configuration mismatch | Terraform wants to replace imported resource | align config to actual attributes before apply |
| importing into wrong address | state maps object to wrong module/resource | use `terraform state mv` carefully |
| hidden dependencies | imported resource relies on unmanaged IAM/networking | import dependencies or use data sources deliberately |
| provider defaults | plan shows changes due to default handling | pin explicit values where important |

## 9. Refactoring state

When renaming resources or moving them into modules, avoid destroy/recreate. Use moved blocks or `terraform state mv`.

### Moved block example

```hcl
moved {
  from = aws_s3_bucket.corpus
  to   = module.object_storage.aws_s3_bucket.corpus
}
```

Moved blocks make refactors reviewable in code.

## 10. State security

State may include sensitive information. Controls:

- encrypt backend storage;
- restrict backend access to CI/CD roles and platform admins;
- avoid storing secrets in resources when secret references can be used;
- mark outputs `sensitive = true`;
- do not commit `.terraform/`, local state, or plan files;
- use separate state for high-sensitivity stacks;
- rotate credentials if state leakage is suspected.

## 11. State and reindex pipelines

Do not keep every historical index version in the same long-lived state forever unless needed. For blue-green index release, use one of these patterns:

| Pattern | Description | Good for |
|---|---|---|
| persistent dual index resources | blue and green resources stay in config | simple, controlled prod cutovers |
| versioned index resource | index name includes version | auditable releases |
| ephemeral build state | temporary state creates build infra, then output handed to app state | large batch builds |
| external data artifact + Terraform alias | index built by data pipeline, Terraform manages routing/alias | clean separation of infra and data plane |

Advisor rule: **Terraform should manage durable infrastructure and routing/cutover resources; data pipelines should build the index contents.** The boundary depends on provider support.
