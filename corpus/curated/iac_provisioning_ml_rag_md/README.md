# IaC / Provisioning for ML and RAG Systems — Markdown Bundle

**Scope.** This bundle is a practical literature-and-practice review for Infrastructure as Code (IaC), provisioning, Terraform, policy-as-code, ML/RAG infrastructure, and CI/CD patterns for infrastructure and reindex pipelines.

**Date-stamp:** 2026-05-19  
**Primary audience:** AI/ML platform engineers, RAG architects, cloud platform engineers, and technical advisors who need to justify IaC choices in interviews, design reviews, or production architecture decisions.

## Files

1. `00_executive_summary.md` — compressed advisor-level conclusions.
2. `01_iac_principles_to_terraform.md` — seven IaC principles mapped to concrete Terraform constructs.
3. `02_terraform_constructs_and_repo_patterns.md` — HCL, providers, modules, variables, outputs, lifecycle, data sources, backends, environments.
4. `03_state_environments_drift_import.md` — state, locking, workspaces vs dir-per-env, plan/apply, drift, import, moved blocks, refactoring.
5. `04_policy_as_code.md` — OPA/Conftest, Sentinel, Checkov, CI enforcement, policy layers.
6. `05_iac_for_ml_rag_stacks.md` — vector DBs, GPU pools, model endpoints, feature/artifact stores, networking, observability.
7. `06_comparative_context.md` — Terraform vs Pulumi vs AWS CDK vs CloudFormation.
8. `07_ci_cd_for_infra_and_reindex.md` — infrastructure pipelines and RAG reindex pipelines.
9. `08_decision_matrices_and_advisor_playbooks.md` — when to use which; scenario-based guidance.
10. `09_failure_modes_and_controls.md` — failure modes, risk controls, and interview-ready mitigations.
11. `10_bibliography.md` — official docs, papers, and authoritative references.

## Core thesis

For enterprise ML/RAG platforms, **Terraform remains the default advisor recommendation** when the goal is cross-cloud provisioning, broad provider coverage, modular infrastructure APIs, reviewable plans, stateful change control, and policy-gated CI/CD. Pulumi and CDK are compelling when product teams need general-purpose programming languages and richer abstraction, while CloudFormation is strongest for AWS-native shops needing fully managed AWS deployment semantics. For RAG specifically, IaC should not stop at “cloud resources”: it must provision and version the ingestion substrate, vector indexes, embedding/model endpoints, GPU/CPU pools, secrets, observability, and the reindex/cutover pipeline.
