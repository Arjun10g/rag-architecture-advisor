# 09 — Failure Modes and Controls

## 1. Terraform state corruption or loss

### Failure mode

State is deleted, corrupted, overwritten, or edited incorrectly.

### Impact

Terraform may attempt to recreate existing resources, fail to manage resources, or lose track of critical infrastructure.

### Controls

- remote backend;
- encryption;
- versioning;
- state locking;
- restricted access;
- state backups before migrations;
- avoid manual state edits;
- use `moved` blocks for refactors.

## 2. Concurrent applies

### Failure mode

Two users or pipelines run `apply` simultaneously.

### Impact

Race conditions, inconsistent state, partial updates.

### Controls

- backend locking;
- managed run queue;
- apply only through CI/CD;
- environment-level deployment concurrency limits.

## 3. Wrong environment apply

### Failure mode

A developer applies dev-intended changes to production or uses the wrong workspace.

### Impact

Production outage or data loss.

### Controls

- directory-per-environment for prod;
- visible backend keys;
- protected branches;
- environment approvals;
- separate cloud accounts/projects/subscriptions;
- CI-only production applies;
- workspace naming guard policies.

## 4. Destructive plan missed in review

### Failure mode

A plan includes delete/replace operations that reviewers miss.

### Impact

Destroyed vector indexes, buckets, databases, endpoints, or GPU clusters.

### Controls

- plan summary bot;
- hard policy on deletes for prod;
- `prevent_destroy` for critical resources;
- manual approval for replacements;
- backups and rollback plans.

## 5. Provider upgrade changes behavior

### Failure mode

Provider version changes introduce changed defaults or diff behavior.

### Impact

Unexpected plan changes or replacements.

### Controls

- version constraints;
- commit provider lock file;
- test provider upgrades in lower env;
- changelog review;
- separate dependency upgrade PRs.

## 6. Module update has hidden blast radius

### Failure mode

A shared module changes in a way that impacts many consuming stacks.

### Impact

Widespread infra changes.

### Controls

- version modules by tag;
- semantic versioning;
- changelog;
- module integration tests;
- staged rollout;
- CODEOWNERS;
- generated plan for each affected environment.

## 7. Policy gaps

### Failure mode

Policies scan HCL but not plan, or plan but not runtime.

### Impact

Insecure resources pass CI.

### Controls

- combine static and plan checks;
- runtime drift/cloud posture checks;
- policy test suite;
- break-glass logging;
- recurring policy review.

## 8. Public exposure of ML/RAG services

### Failure mode

Vector DB, model endpoint, metadata DB, or dashboard becomes public.

### Impact

Data leakage, model abuse, compliance incidents.

### Controls

- private endpoint modules;
- security group/firewall policies;
- no `0.0.0.0/0` ingress in prod;
- network policy;
- runtime scanners;
- endpoint inventory.

## 9. GPU cost runaway

### Failure mode

Autoscaling GPU node pool or model endpoint scales without budget guardrails.

### Impact

Large unexpected cost.

### Controls

- max nodes/replicas required;
- budget alerts;
- cost policy gates;
- workload quotas;
- TTL for experimental environments;
- spot/preemptible for recoverable batch jobs.

## 10. Secret leakage through state or plan

### Failure mode

Secrets are stored in Terraform state, plan files, logs, or outputs.

### Impact

Credential exposure.

### Controls

- secrets manager references;
- avoid hardcoded backend credentials;
- sensitive outputs;
- restricted plan artifact retention;
- state encryption;
- secret scanning in repos;
- short-lived credentials/OIDC.

## 11. Reindex overwrites live index

### Failure mode

A pipeline writes new vectors into the production index in place.

### Impact

No rollback, degraded retrieval, inconsistent query behavior.

### Controls

- versioned index names;
- blue-green index deployment;
- candidate evaluation;
- canary/shadow traffic;
- alias switch;
- retention window for previous index.

## 12. ACL leakage in retrieval

### Failure mode

Index metadata lacks correct tenant/document permissions, or retrieval does not filter by ACL.

### Impact

Users retrieve unauthorized documents.

### Controls

- include tenant/ACL fields in metadata schema;
- IaC policy requiring tenant isolation configuration;
- ACL eval tests in reindex pipeline;
- query-time permission filters;
- audit logs;
- right-to-erasure/tombstone pipeline.

## 13. Incomplete import

### Failure mode

Existing resources are imported without dependencies or matching config.

### Impact

Terraform wants to replace resources or leaves hidden manual dependencies.

### Controls

- inventory first;
- import dependencies;
- plan until stable;
- use data sources only intentionally;
- state backup;
- review by resource owner.

## 14. Overusing `ignore_changes`

### Failure mode

`ignore_changes` hides real drift.

### Impact

Terraform no longer enforces intended state.

### Controls

- allow only for fields owned by external controllers;
- comment every ignore;
- policy flagging broad ignores;
- runtime drift checks for ignored critical fields.

## 15. Mixing IaC tools on the same resource

### Failure mode

Terraform, CloudFormation, Helm, GitOps, or manual scripts all manage overlapping resources.

### Impact

Fight loops, unexpected drift, broken deployments.

### Controls

- explicit ownership map;
- labels/tags with manager;
- one tool per resource;
- clean handoff/import process;
- documentation in module README.

## 16. Provider cannot manage vector DB feature fully

### Failure mode

Terraform provider lacks a vector DB feature such as aliases, serverless config, backups, or index parameters.

### Impact

Manual or script-managed gaps.

### Controls

- separate durable infra from data-plane actions;
- use provider for supported resources;
- use API calls in release pipeline for unsupported data-plane operations;
- store resulting manifest;
- avoid pretending unsupported operations are managed by Terraform.

## 17. Observability omitted

### Failure mode

Infrastructure is deployed without dashboards, alerts, or traces.

### Impact

Slow incident response and no quality/cost feedback.

### Controls

- observability module required;
- policy requiring log/metric settings;
- RAG-specific dashboards;
- alerts for stale index, high latency, failed ingestion, high GPU spend, retrieval quality regression.

## 18. Practical control checklist

For every production ML/RAG Terraform stack, verify:

- [ ] remote encrypted state;
- [ ] locking enabled;
- [ ] separate prod state;
- [ ] provider versions constrained and lock file committed;
- [ ] modules versioned;
- [ ] `prevent_destroy` on critical stores/indexes;
- [ ] plan generated in CI;
- [ ] static and plan policy checks;
- [ ] cost checks for GPUs/vector DBs;
- [ ] private endpoints for model/vector services;
- [ ] KMS encryption for storage;
- [ ] least-privilege IAM;
- [ ] drift detection;
- [ ] reindex pipeline uses versioned index and rollback;
- [ ] logs/metrics/traces/dashboards present.
