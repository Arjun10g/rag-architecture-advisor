# 06 — Comparative Context: Terraform vs Pulumi vs AWS CDK vs CloudFormation

## 1. Summary table

| Tool | Primary model | Language | State model | Best fit | Main caveat |
|---|---|---|---|---|---|
| Terraform | declarative IaC with providers | HCL / JSON | Terraform state backend | cross-cloud, SaaS, standardized platform modules | state management and HCL abstraction limits |
| Pulumi | general-purpose language IaC | TypeScript, Python, Go, C#, Java, YAML | Pulumi state backend/self-managed | software-engineering-heavy teams, complex abstractions | language/runtime complexity and smaller ecosystem in some areas |
| AWS CDK | code that synthesizes CloudFormation | TypeScript, Python, Java, C#, Go, JS | CloudFormation stacks | AWS-native app teams wanting high-level constructs | AWS-centric and generated templates can be opaque |
| CloudFormation | AWS-native declarative templates | YAML/JSON | AWS-managed stack state | AWS-only, managed rollback/change sets/StackSets | AWS-only and verbose for complex abstractions |

## 2. Terraform

### Strengths

- Broad provider ecosystem across cloud, SaaS, Kubernetes, databases, observability, and security tools.
- Mature module ecosystem.
- Strong plan/apply workflow.
- Remote backend and locking patterns.
- Cross-cloud neutrality.
- Works well as a platform contract between central platform teams and product teams.

### Weaknesses

- State must be managed carefully.
- HCL is less expressive than general-purpose languages.
- Provider behavior can vary in quality.
- Large monolithic states become slow and risky.
- Some cloud-native features lag behind provider support.

### Best use cases

- enterprise platform engineering;
- multi-cloud ML/RAG stacks;
- regulated environments needing reviewable plans;
- teams that want reusable modules and policy gates;
- provisioning both cloud and SaaS dependencies.

## 3. Pulumi

### Strengths

- Uses general-purpose languages.
- Better for complex abstractions, loops, classes, packages, unit tests, and shared libraries.
- Can be more natural for software engineers.
- Supports multiple clouds and Kubernetes.

### Weaknesses

- Language runtime and dependency management add complexity.
- Review diffs can be less immediately readable than HCL for some infra reviewers.
- Team must standardize language, packaging, and testing conventions.
- Some organizations prefer declarative HCL for governance and audit simplicity.

### Best use cases

- engineering teams with strong TypeScript/Python/Go practices;
- infrastructure that needs rich programmatic abstraction;
- platform products exposed as internal SDKs;
- app teams that want infra and app logic in the same language.

### ML/RAG angle

Pulumi can be attractive when ML platform resources are generated from higher-level specs, for example:

```text
for each tenant:
  create namespace/index
  create quota policy
  create service identity
  create dashboard
```

Terraform can do this too with `for_each`, but Pulumi may be easier when the logic becomes library-like.

## 4. AWS CDK

### Strengths

- High-level AWS constructs.
- Uses common languages.
- Synthesizes to CloudFormation, so AWS manages stack deployment and rollback.
- Strong for serverless and AWS-native application stacks.
- Construct ecosystem can encode secure defaults.

### Weaknesses

- AWS-centric.
- Generated CloudFormation can be large and opaque.
- Multi-cloud support requires separate tools.
- Construct defaults are helpful but can surprise teams if not understood.

### Best use cases

- AWS-only organizations;
- product teams building serverless/data/ML applications on AWS;
- teams wanting CloudFormation semantics but better developer ergonomics.

### ML/RAG angle

AWS CDK is strong if the RAG stack is AWS-native: S3, Lambda/ECS/EKS, SageMaker, Bedrock-related integrations, OpenSearch, IAM, EventBridge, Step Functions. The advisor can justify CDK when AWS service integration velocity matters more than cross-cloud portability.

## 5. CloudFormation

### Strengths

- AWS-native.
- Managed stack state.
- Change sets and rollback semantics.
- StackSets for multi-account/region deployment.
- Deep AWS integration.

### Weaknesses

- AWS-only.
- YAML/JSON can become verbose.
- Less ergonomic module abstraction than Terraform modules or CDK constructs.
- Non-AWS SaaS resources require custom resources or separate tooling.

### Best use cases

- AWS-only regulated environments;
- organizations already standardized on CloudFormation;
- infrastructure that needs AWS-native stack-level rollback and drift support;
- baseline account provisioning and guardrails.

## 6. Decision criteria

| Criterion | Terraform | Pulumi | AWS CDK | CloudFormation |
|---|---:|---:|---:|---:|
| Cross-cloud | Excellent | Excellent | Weak | None |
| AWS-native depth | Good | Good | Excellent | Excellent |
| SaaS provider coverage | Excellent | Good | Limited | Limited/custom |
| Declarative reviewability | Excellent | Medium | Medium | Good |
| General-purpose language | No | Yes | Yes | No |
| Managed AWS rollback | No | No, unless targeting CFN | Yes via CFN | Yes |
| Module/construct ecosystem | Excellent | Good | Excellent for AWS | Medium |
| State complexity | Medium | Medium | AWS-managed CFN | AWS-managed CFN |
| Policy integration | Strong | Good | AWS/third-party | AWS/third-party |
| Enterprise platform standardization | Excellent | Good | Good for AWS | Good for AWS |

## 7. Advisor scripts

### When recommending Terraform

> I would choose Terraform because this platform spans cloud resources, Kubernetes, vector databases, model endpoints, observability, and SaaS integrations. Terraform gives us provider breadth, a clear plan/apply workflow, reusable modules, remote state with locking, and mature policy-as-code gates. For ML/RAG, I would split state by foundation, shared ML platform, and app/index release layers to control blast radius.

### When recommending Pulumi

> I would consider Pulumi if the team wants infrastructure APIs expressed as real software libraries, especially if the platform has complex generation logic across tenants, models, or environments. The trade-off is that we need stronger language/runtime standards and careful review conventions.

### When recommending AWS CDK

> I would choose AWS CDK for an AWS-only product team that benefits from high-level constructs and CloudFormation-backed deployments. It is especially compelling for AWS-native RAG stacks using S3, OpenSearch, SageMaker/Bedrock integrations, ECS/EKS, Lambda, and Step Functions.

### When recommending CloudFormation

> I would use CloudFormation when the organization is AWS-only and values AWS-managed stack state, change sets, rollback, and StackSets over cross-cloud portability. For complex app teams, I would usually prefer CDK on top of CloudFormation rather than raw YAML.

## 8. Hybrid patterns

Many enterprises use hybrid IaC:

```text
Terraform
  account/bootstrap, networking, IAM, Kubernetes, SaaS integrations

Helm/Kustomize
  Kubernetes application resources

CloudFormation/CDK
  AWS-native app stacks owned by product teams

GitOps controller
  continuous Kubernetes reconciliation

Data pipeline orchestrator
  index builds, embeddings, validation, cutover
```

Hybrid is acceptable when ownership boundaries are clear. It is dangerous when two tools manage the same resource.

## 9. Selection rule

- **Default:** Terraform.
- **AWS-only app team:** CDK or CloudFormation.
- **Programming-language-first platform:** Pulumi.
- **Kubernetes app delivery:** Terraform for cluster/foundation; Helm/GitOps for app manifests.
- **RAG reindex contents:** pipeline/orchestrator, not Terraform; Terraform manages durable infra and routing controls.
