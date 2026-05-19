# 04 — Policy-as-Code for Terraform and ML/RAG Infrastructure

## 1. Why policy-as-code is mandatory for ML/RAG

ML/RAG systems touch sensitive data, expensive compute, and user-facing model behavior. Manual review alone is not enough. Policy-as-code turns security, compliance, reliability, and cost rules into executable checks that run before apply.

## 2. Policy layers

A mature IaC workflow usually uses multiple policy layers:

| Layer | Input | Example tools | Catches |
|---|---|---|---|
| Static IaC scanning | `.tf`, YAML, JSON | Checkov, tfsec-style scanners | insecure defaults, public buckets, weak encryption |
| Plan-based policy | `terraform show -json` | OPA, Conftest, Sentinel | actual create/update/delete actions |
| Runtime/cloud posture | cloud APIs | CSPM, cloud config rules | manual drift and runtime exposure |
| Kubernetes admission | manifests/admission requests | OPA Gatekeeper, Kyverno | invalid workloads before scheduling |
| CI/CD authorization | pipeline context | OPA/Cedar/custom | who can apply what and when |

Static scans are fast and useful, but plan checks see the actual proposed changes.

## 3. OPA and Conftest

OPA uses Rego policies. Conftest is a CLI commonly used to test structured config files against OPA/Rego policies.

### Terraform plan workflow

```bash
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json
conftest test tfplan.json --policy policy/terraform
```

### Example Rego policy: block public vector DB exposure

```rego
package terraform.security

deny[msg] {
  rc := input.resource_changes[_]
  rc.type == "aws_security_group_rule"
  rc.change.actions[_] != "delete"
  after := rc.change.after
  after.type == "ingress"
  after.cidr_blocks[_] == "0.0.0.0/0"
  contains(lower(after.description), "vector")
  msg := sprintf("Public ingress is not allowed for vector DB rule: %s", [rc.address])
}
```

### Example Rego policy: require KMS encryption on corpus buckets

```rego
package terraform.rag

denied_bucket[bucket] {
  bucket := input.resource_changes[_]
  bucket.type == "aws_s3_bucket"
  bucket.change.actions[_] == "create"
  not has_encryption(bucket.address)
}

has_encryption(bucket_addr) {
  enc := input.resource_changes[_]
  enc.type == "aws_s3_bucket_server_side_encryption_configuration"
  startswith(enc.address, replace(bucket_addr, "aws_s3_bucket", "aws_s3_bucket_server_side_encryption_configuration"))
}

deny[msg] {
  b := denied_bucket[_]
  msg := sprintf("Corpus bucket must have KMS encryption: %s", [b.address])
}
```

This simplified example illustrates the pattern. Real policies need to account for modules, naming conventions, resource references, and provider-specific fields.

## 4. Sentinel

Sentinel is HashiCorp's policy-as-code framework used with HCP Terraform/Terraform Enterprise. It is commonly used to enforce policies at the Terraform run phase.

### Sentinel policy tiers

| Enforcement level | Use case |
|---|---|
| advisory | warn but do not block |
| soft mandatory | block unless an authorized override approves |
| hard mandatory | block with no override |

### Good Sentinel use cases

- production applies require approved VCS branch;
- resources must carry owner/cost tags;
- production storage cannot be publicly readable;
- deletion of stateful resources requires manual approval;
- GPU instance families above a threshold require platform approval;
- networking must use private endpoints for model/vector services.

## 5. Checkov

Checkov scans IaC for misconfigurations across Terraform, CloudFormation, Kubernetes, Helm, Dockerfiles, GitHub Actions, and more. It is useful early in PRs because it can scan source before a full plan is available.

### Example workflow

```bash
checkov -d . --framework terraform
```

### Good Checkov use cases

- encryption requirements;
- public bucket exposure;
- security group exposure;
- IAM policy risks;
- missing logging;
- Kubernetes pod security settings;
- secrets in config;
- common cloud security baselines.

## 6. Policy patterns for ML/RAG

### Security policies

| Policy | Why |
|---|---|
| Vector DBs and model endpoints must be private in prod | prevent data/model exposure |
| Corpus and chunk stores must use KMS encryption | protect sensitive documents |
| Ingestion workers must have least-privilege IAM | prevent broad document access |
| Secrets must be referenced from secret managers | avoid state/repo leakage |
| Public egress from embedding workers restricted | reduce exfiltration and prompt-injection callback risk |

### Privacy policies

| Policy | Why |
|---|---|
| PII-bearing datasets require approved storage class | compliance |
| logs cannot include raw documents or prompts by default | privacy and security |
| index namespaces must include tenant isolation field | permission-aware retrieval |
| deletion/tombstone resources must exist for right-to-erasure workflows | legal and operational correctness |

### Cost policies

| Policy | Why |
|---|---|
| GPU node pools require max size | cap runaway autoscaling |
| expensive instance families require approval | budget control |
| vector DB replicas above threshold require approval | storage/query cost control |
| prod-like evaluation environments must auto-expire | avoid idle benchmark spend |

### Reliability policies

| Policy | Why |
|---|---|
| production vector DB requires backups | recovery |
| prod model endpoint min replicas >= 2 | availability |
| critical resources require deletion protection | avoid accidental destroy |
| observability must be enabled | incident response |
| private DNS and health checks required | reliable routing |

## 7. CI/CD enforcement pattern

```text
Pull request
  -> terraform fmt/validate
  -> Checkov static scan
  -> terraform plan
  -> terraform show -json
  -> OPA/Conftest or Sentinel policy check
  -> cost estimation
  -> human review
  -> merge
  -> protected apply with environment approval
```

## 8. Policy severity matrix

| Severity | Example | Enforcement |
|---|---|---|
| Low | missing optional tag | warning/advisory |
| Medium | missing cost center | block in prod, warn in dev |
| High | public model endpoint | hard block in prod |
| Critical | deleting production corpus bucket | hard block + break-glass process |

## 9. LLM-era IaC policy caveats

LLMs can generate Terraform quickly, but generated IaC often:

- omits provider version constraints;
- uses insecure defaults;
- lacks lifecycle protections;
- hardcodes secrets or backend values;
- misunderstands provider-specific fields;
- creates resources without cost controls;
- ignores state/import implications.

Policy-as-code is therefore an important guardrail for AI-assisted infrastructure generation.

## 10. Example GitHub Actions sketch

```yaml
name: terraform-pr
on:
  pull_request:
    paths:
      - "infra/**"
      - "modules/**"
      - "policy/**"

jobs:
  plan:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - name: Terraform fmt
        run: terraform -chdir=infra/prod fmt -check
      - name: Terraform init
        run: terraform -chdir=infra/prod init
      - name: Terraform validate
        run: terraform -chdir=infra/prod validate
      - name: Static IaC scan
        run: checkov -d infra/prod --framework terraform
      - name: Plan
        run: terraform -chdir=infra/prod plan -out=tfplan.binary
      - name: Export plan JSON
        run: terraform -chdir=infra/prod show -json tfplan.binary > tfplan.json
      - name: Policy check
        run: conftest test infra/prod/tfplan.json --policy policy/terraform
```
