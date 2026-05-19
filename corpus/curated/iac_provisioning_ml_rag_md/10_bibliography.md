# 10 — Bibliography and Source Notes

Date-stamp: 2026-05-19

This report prioritizes official documentation for tool behavior and authoritative cloud/platform references. URLs are included so the bundle can be used as a working advisor reference.

## Terraform and HashiCorp

1. HashiCorp Developer — Terraform Language Documentation.  
   https://developer.hashicorp.com/terraform/language

2. HashiCorp Developer — Terraform Providers.  
   https://developer.hashicorp.com/terraform/language/providers

3. HashiCorp Developer — Terraform Modules.  
   https://developer.hashicorp.com/terraform/language/modules

4. HashiCorp Developer — Terraform State.  
   https://developer.hashicorp.com/terraform/language/state

5. HashiCorp Developer — Backend block configuration overview.  
   https://developer.hashicorp.com/terraform/language/backend

6. HashiCorp Developer — State locking.  
   https://developer.hashicorp.com/terraform/language/state/locking

7. HashiCorp Developer — Backends: State Storage and Locking.  
   https://developer.hashicorp.com/terraform/language/state/backends

8. HashiCorp Developer — Terraform Workspaces.  
   https://developer.hashicorp.com/terraform/language/state/workspaces

9. HashiCorp Developer — `terraform plan` command.  
   https://developer.hashicorp.com/terraform/cli/commands/plan

10. HashiCorp Developer — `terraform apply` command.  
    https://developer.hashicorp.com/terraform/cli/commands/apply

11. HashiCorp Developer — `terraform import` command.  
    https://developer.hashicorp.com/terraform/cli/commands/import

12. HashiCorp Developer — Sentinel documentation.  
    https://developer.hashicorp.com/sentinel/docs

## Policy-as-code

13. Open Policy Agent — Terraform integration/tutorial.  
    https://www.openpolicyagent.org/docs/terraform

14. Conftest documentation.  
    https://www.conftest.dev/

15. Checkov documentation — What is Checkov?  
    https://www.checkov.io/1.Welcome/What%20is%20Checkov.html

16. Open Policy Agent — CI/CD use case.  
    https://www.openpolicyagent.org/docs/latest/cicd/

## Comparative IaC tools

17. Pulumi Docs — Infrastructure as Code.  
    https://www.pulumi.com/docs/iac/

18. AWS Documentation — What is the AWS CDK?  
    https://docs.aws.amazon.com/cdk/v2/guide/home.html

19. AWS Documentation — What is CloudFormation?  
    https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html

20. AWS CloudFormation — Change sets.  
    https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html

21. AWS CloudFormation — Drift detection.  
    https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html

## ML/RAG infrastructure references

22. Google Cloud — Run GPUs in GKE Standard node pools.  
    https://cloud.google.com/kubernetes-engine/docs/how-to/gpus

23. AWS SageMaker Documentation — Real-time inference endpoints.  
    https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html

24. Google Cloud Vertex AI — Deploy a model to an endpoint.  
    https://cloud.google.com/vertex-ai/docs/general/deployment

25. Azure Machine Learning — Compute targets and compute clusters.  
    https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-target

26. Kubernetes Documentation — Managing resources for containers.  
    https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/

27. Helm Documentation.  
    https://helm.sh/docs/

28. Argo CD Documentation.  
    https://argo-cd.readthedocs.io/

29. Flux Documentation.  
    https://fluxcd.io/flux/

## Vector DB and retrieval infrastructure references

30. Pinecone Documentation.  
    https://docs.pinecone.io/

31. Weaviate Documentation.  
    https://weaviate.io/developers/weaviate

32. Qdrant Documentation.  
    https://qdrant.tech/documentation/

33. Milvus Documentation.  
    https://milvus.io/docs

34. Elasticsearch Vector Search Documentation.  
    https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html

35. OpenSearch Vector Search Documentation.  
    https://opensearch.org/docs/latest/search-plugins/knn/index/

36. PostgreSQL pgvector.  
    https://github.com/pgvector/pgvector

## CI/CD and platform engineering references

37. GitHub Actions — OpenID Connect.  
    https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/about-security-hardening-with-openid-connect

38. GitLab CI/CD Pipelines.  
    https://docs.gitlab.com/ci/pipelines/

39. Azure DevOps Pipelines.  
    https://learn.microsoft.com/en-us/azure/devops/pipelines/

40. Google Cloud — Workload Identity Federation.  
    https://cloud.google.com/iam/docs/workload-identity-federation

41. AWS IAM — OIDC federation.  
    https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html

## Research and background papers useful for advisor framing

42. Morris, Kief. *Infrastructure as Code: Dynamic Systems for the Cloud Age*. O'Reilly.  
    Book reference for IaC principles and practice.

43. Humble, Jez and Farley, David. *Continuous Delivery*. Addison-Wesley.  
    Background for automated deployment pipelines and release discipline.

44. Burns, Brendan et al. “Borg, Omega, and Kubernetes.” ACM Queue, 2016.  
    Background for declarative infrastructure and reconciliation loops.

45. Google SRE Book — Service Level Objectives and release engineering chapters.  
    https://sre.google/sre-book/table-of-contents/

## Notes on source use

- Terraform behavior should be checked against the current HashiCorp version in use. This bundle uses the docs available on 2026-05-19.
- Provider-specific resources change quickly. Always verify Terraform provider resources and arguments against the current provider docs before implementation.
- Vector database Terraform support varies substantially by vendor and maturity. If a provider lacks support for aliases, collections, backups, or private networking, use Terraform for durable infrastructure and a controlled release pipeline/API call for the unsupported data-plane operation.
