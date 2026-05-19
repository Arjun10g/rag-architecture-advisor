# 08 — Decision Matrices and Advisor Playbooks

## 1. Tool choice matrix

| Situation | Recommended choice | Rationale |
|---|---|---|
| Multi-cloud RAG platform | Terraform | provider breadth and neutral workflow |
| AWS-only product team | AWS CDK | high-level AWS constructs and CloudFormation deployment |
| AWS-only regulated baseline | CloudFormation / StackSets | AWS-native governance and managed stack semantics |
| Software-heavy platform SDK | Pulumi | real programming languages and package ecosystems |
| Kubernetes app manifests | Helm/GitOps, with Terraform for cluster | better continuous reconciliation for app-level resources |
| SaaS-heavy platform | Terraform | mature SaaS provider ecosystem |
| Fast experimental ML sandbox | Pulumi or Terraform modules | depends on team language preference |
| Enterprise shared modules | Terraform | stable module contracts and reviewable plans |

## 2. Environment strategy matrix

| Requirement | Best pattern |
|---|---|
| strict prod isolation | directory-per-env with separate backend/state |
| identical ephemeral preview envs | workspaces or generated env directories |
| different cloud accounts per env | directory-per-env or stack-per-env |
| app teams own app infra | platform modules consumed from app repos |
| central platform governance | infra monorepo with CODEOWNERS and policy gates |
| frequent index releases | separate release pipeline and versioned index manifests |

## 3. State-splitting matrix

| Resource type | State recommendation | Reason |
|---|---|---|
| VPC/VNet, DNS, KMS | foundation state | slow-changing, high blast radius |
| shared GPU cluster | ML platform state | expensive shared capacity |
| vector DB cluster | platform or app state depending ownership | cost and data isolation trade-off |
| app-specific index alias | app/release state | changes with RAG releases |
| model endpoint | app or platform state | depends on ownership/SLO |
| temporary embedding workers | release/build state or orchestrator | lifecycle tied to batch job |
| dashboards/alerts | same state as service or observability state | ownership-dependent |

## 4. Vector DB provisioning decision matrix

| Use case | IaC pattern |
|---|---|
| managed Pinecone/Zilliz/Qdrant/Weaviate Cloud | Terraform provider if mature; otherwise API wrapper/module with careful state handling |
| OpenSearch/Elastic vector search | Terraform for domain/deployment, index templates via provider/API pipeline |
| pgvector | Terraform for Postgres infra; migrations for extensions/schema/indexes |
| self-host Milvus/Qdrant/Weaviate | Terraform for K8s + Helm; GitOps for ongoing chart/app reconciliation if preferred |
| Vespa | Terraform for cloud/network/IAM; app package deployment via Vespa tooling/pipeline |

## 5. GPU provisioning decision matrix

| Workload | Recommended infra |
|---|---|
| batch embedding | autoscaled GPU/CPU pool, spot/preemptible if recoverable |
| low-latency reranking | stable min replicas, private endpoint, autoscaling with SLOs |
| LLM inference | dedicated inference endpoint or GPU pool, model-aware autoscaling |
| fine-tuning | isolated training pool, quotas, checkpoint storage |
| experimentation | ephemeral GPU workspaces with TTL policy |

## 6. Terraform vs data pipeline boundary

| Question | If yes | Recommended owner |
|---|---|---|
| Is it a durable cloud resource? | yes | Terraform |
| Is it a row/object/vector inside a store? | yes | data/application pipeline |
| Is it a routing alias or endpoint pointer? | yes | Terraform or release controller |
| Does it change multiple times per day? | yes | pipeline/config system, not manual Terraform unless designed for it |
| Is it security-critical access control? | yes | Terraform/policy, with app enforcement tests |

## 7. Advisor playbook: “How would you provision a production RAG platform?”

Use this answer structure:

1. Start with foundation: network, IAM, KMS, secrets, logging.
2. Add ML platform: storage, vector DB, metadata DB, queues, model endpoints, GPU pools.
3. Define Terraform modules for each platform primitive.
4. Use remote encrypted state with locking and separate states by blast radius.
5. Run CI/CD with fmt/validate/plan/policy/cost/human approval/apply.
6. Add reindex pipeline with versioned manifests, eval gates, blue-green index cutover.
7. Monitor drift, cost, latency, quality, and ACL leakage.

### Example answer

> I would use Terraform modules to provision the RAG platform primitives: storage, metadata DB, vector index, model endpoints, GPU pools, IAM, KMS, private networking, and observability. I would split state into foundation, shared ML platform, and app/index release layers so the blast radius is controlled. Every PR would run validate, plan, static scans, plan-based OPA/Sentinel policies, and cost checks. For reindexing, I would avoid overwriting the live index. I would build a new versioned index, run retrieval and generation evals, canary or shadow test it, then switch an alias or config pointer with rollback to the previous index.

## 8. Advisor playbook: “How do you handle drift?”

Strong answer:

> I schedule drift checks using `terraform plan -detailed-exitcode` from a controlled runner. When drift appears, I classify it as intentional, accidental, provider noise, or externally managed. Intentional drift becomes a code change or import. Accidental drift is reverted or reconciled. For ML/RAG, I prioritize drift detection on IAM, public endpoints, KMS, GPU pool limits, vector DB networking, and deletion protection because those are high-risk for security and cost.

## 9. Advisor playbook: “Workspaces or folders?”

Strong answer:

> I use directory-per-environment for production-grade stacks because it makes backend, account, region, and approval boundaries explicit. I use shared modules to avoid duplication. I reserve Terraform workspaces for low-blast-radius identical environments, preview stacks, or ephemeral evaluation environments where automation prevents human workspace mistakes.

## 10. Advisor playbook: “How do you handle existing manually-created infrastructure?”

Strong answer:

> I inventory resources, write matching Terraform configuration, import into the intended module address, run plan until no destructive surprises remain, add lifecycle protections for critical resources, then lock down manual changes. I do not import directly into a giant production state without a rollback plan and state backup.

## 11. Advisor playbook: “How do you justify Terraform over Pulumi/CDK?”

Strong answer:

> For this use case, Terraform is the safest default because the RAG platform spans cloud resources, Kubernetes, vector databases, model endpoints, observability, and SaaS tools. Terraform has broad provider coverage, reviewable plans, mature remote state patterns, and policy-as-code integration. I would still consider CDK for an AWS-only product team and Pulumi if the platform needs rich language-native abstractions.

## 12. Advisor playbook: “What policies matter for RAG infrastructure?”

Answer with categories:

- **Security:** private endpoints, least privilege, KMS, no public vector DB, no secrets in state/repo.
- **Privacy:** tenant/ACL metadata required, no raw prompts/docs in logs, deletion/tombstone support.
- **Cost:** GPU max bounds, vector replica limits, endpoint autoscaling caps, TTL for eval environments.
- **Reliability:** backups, deletion protection, multi-replica prod endpoints, observability required.
- **Quality release:** index promotion requires eval pass, canary, rollback pointer.

## 13. “When to use which” quick reference

| Design pressure | Choose |
|---|---|
| cross-cloud + governance | Terraform |
| AWS service velocity | AWS CDK |
| AWS-native rollback/StackSets | CloudFormation |
| rich programming abstractions | Pulumi |
| continuous K8s app reconciliation | GitOps/Argo/Flux |
| vector contents and embeddings | data pipeline/orchestrator |
| index alias and infrastructure | Terraform/release controller |
