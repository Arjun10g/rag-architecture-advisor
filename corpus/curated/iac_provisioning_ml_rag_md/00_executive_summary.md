# 00 — Executive Summary

## Why IaC matters for ML/RAG systems

RAG and ML platforms have more moving parts than a conventional web service: object storage, databases, vector indexes, embedding workers, GPU inference pools, model endpoints, metadata stores, feature stores, CI/CD, secrets, IAM, private networking, observability, and evaluation/reindex workflows. Without IaC, those components become a set of hand-built cloud resources whose state is hard to reproduce, audit, secure, or cost-control.

The important shift is this: **IaC is not just infrastructure automation; it is the control plane for repeatability, governance, and platform evolution.** In a RAG system, chunking changes, embedding model upgrades, index parameter changes, and reranker swaps all require infrastructure-level coordination. The IaC layer should therefore describe not only networking and compute, but also the versioned resources that allow safe ingestion, indexing, validation, and cutover.

## Advisor recommendation

Use **Terraform** as the baseline recommendation when the organization needs:

- multi-cloud or cloud-neutral provisioning;
- mature provider ecosystem;
- strong review workflow through `terraform plan`;
- reusable platform modules;
- remote state, locking, and controlled applies;
- policy-as-code gates across AWS/GCP/Azure/Kubernetes/SaaS resources;
- CI/CD integration with GitHub Actions, GitLab CI, Azure DevOps, Jenkins, or Terraform Cloud/HCP Terraform.

Use **Pulumi** when the platform team strongly prefers general-purpose programming languages, unit-testable abstractions, loops/classes/packages, and code-native component libraries. Use **AWS CDK** when the stack is AWS-only and the team wants high-level AWS constructs that synthesize to CloudFormation. Use **CloudFormation** when AWS-native managed semantics, change sets, rollbacks, StackSets, and service-level AWS governance are more important than cross-cloud portability.

## The seven IaC principles used in this report

This report organizes IaC around seven principles:

1. **Codify everything important.** Infrastructure, IAM, network, runtime, data stores, model endpoints, and index resources should be represented as code.
2. **Declare desired state.** The configuration should describe the target state, not a sequence of manual commands.
3. **Make change reviewable.** Every material change should be visible in version control and in a plan/diff before apply.
4. **Use reusable modules.** Platform teams should expose safe, parameterized modules rather than copying raw resources across teams.
5. **Separate state and environments deliberately.** State must be remote, locked, encrypted, and scoped to the blast radius of each environment or stack.
6. **Enforce policy before apply.** Security, cost, privacy, and reliability policies should fail early in CI/CD.
7. **Automate delivery and reconciliation.** Plans, applies, drift checks, imports, and reindex cutovers should be automated with approval gates.

## Key design conclusion for ML/RAG

A production RAG platform should usually split IaC into **three layers**:

```text
Layer 1 — Foundation
  network, IAM, KMS, secrets, DNS, private endpoints, logs, monitoring

Layer 2 — ML/RAG platform services
  object storage, queues, vector DB, metadata DB, model endpoints, GPU pools,
  artifact registry, feature store, evaluation store

Layer 3 — Dataset/index release pipelines
  embedding job infra, index build resources, blue-green index aliases,
  retrieval evaluation, canary traffic, rollback hooks
```

Layer 1 changes rarely and should be tightly governed. Layer 2 changes moderately often and should be modular. Layer 3 changes frequently and should be CI/CD-driven because it tracks data/model/index versions rather than static infrastructure alone.

## What interviewers usually want to hear

A strong answer does not simply say “we use Terraform.” It explains:

- how state is stored, locked, encrypted, and isolated;
- how environments are separated;
- how modules define safe platform primitives;
- how `plan` output is reviewed and policy-checked;
- how drift is detected and reconciled;
- how existing resources are imported safely;
- how ML-specific resources such as vector DBs, GPU pools, and model endpoints are represented;
- how index rebuilds are deployed without downtime.

## One-line advisor position

**Terraform + remote state + modules + policy gates + CI/CD is the default enterprise pattern; ML/RAG adds a second release problem: versioned data/index/model infrastructure must be deployed with the same discipline as application infrastructure.**
