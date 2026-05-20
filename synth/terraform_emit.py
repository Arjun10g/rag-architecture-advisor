from __future__ import annotations


MODULE_INPUTS = {
    "compute": (
        'enable_reranker       = contains(local.pipeline_stages, "rerank")',
        'enable_query_planner  = contains(local.pipeline_stages, "query_planner")',
    ),
    "networking": (
        "allowed_egress_domains    = var.allowed_egress_domains",
        "private_endpoints_enabled = true",
    ),
    "storage": (
        'enable_lexical_index = contains(local.pipeline_stages, "bm25")',
        'enable_review_queue  = contains(local.pipeline_stages, "review_gate")',
    ),
    "database": (
        "vector_dimensions         = var.vector_dimensions",
        "enable_blue_green_aliases = true",
        'enable_review_queue       = contains(local.pipeline_stages, "review_gate")',
    ),
    "security": (
        "kms_key_id               = var.kms_key_id",
        "audit_log_retention_days = var.audit_log_retention_days",
        'review_gate_required     = contains(local.pipeline_stages, "review_gate")',
    ),
    "monitoring": (
        "latency_slo_ms           = var.latency_slo_ms",
        "emit_latency_percentiles = true",
    ),
    "scalability": (
        "min_replicas         = var.min_replicas",
        "max_replicas         = var.max_replicas",
        "scale_on_queue_depth = true",
    ),
}


MODULE_VARIABLES = {
    "compute": (
        ("enable_reranker", "bool"),
        ("enable_query_planner", "bool"),
    ),
    "networking": (
        ("allowed_egress_domains", "list(string)"),
        ("private_endpoints_enabled", "bool"),
    ),
    "storage": (
        ("enable_lexical_index", "bool"),
        ("enable_review_queue", "bool"),
    ),
    "database": (
        ("vector_dimensions", "list(number)"),
        ("enable_blue_green_aliases", "bool"),
        ("enable_review_queue", "bool"),
    ),
    "security": (
        ("kms_key_id", "string"),
        ("audit_log_retention_days", "number"),
        ("review_gate_required", "bool"),
    ),
    "monitoring": (
        ("latency_slo_ms", "number"),
        ("emit_latency_percentiles", "bool"),
    ),
    "scalability": (
        ("min_replicas", "number"),
        ("max_replicas", "number"),
        ("scale_on_queue_depth", "bool"),
    ),
}


def _hcl_string(value: object) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _hcl_list(values: list[str] | tuple[str, ...]) -> str:
    return "[" + ", ".join(_hcl_string(value) for value in values) + "]"


def _file(path: str, body: str) -> str:
    return f"# file: {path}\n{body.strip()}\n"


def _component_ids(projection: dict) -> list[str]:
    return [component["id"] for component in projection["deployment_components"]]


def _module_block(component: dict) -> str:
    lines = [
        f'module "{component["id"]}" {{',
        f'  source          = "./modules/{component["id"]}"',
        "  environment     = var.environment",
        "  project_name    = var.project_name",
        "  region          = var.region",
        "  pipeline_stages = local.pipeline_stages",
        f'  serves          = {_hcl_list(component.get("serves") or [])}',
        f'  controls        = {_hcl_list(component.get("controls") or [])}',
    ]
    for line in MODULE_INPUTS.get(component["id"], ()):
        lines.append(f"  {line}")
    lines.append("}")
    return "\n".join(lines)


def _root_main(topology: dict, projection: dict) -> str:
    module_blocks = "\n\n".join(
        _module_block(component)
        for component in projection["deployment_components"]
    )
    return f"""
# Illustrative Terraform sketch for {topology["name"]}.
# The backend block is commented because state bucket names are environment-specific.
terraform {{
  required_version = ">= 1.6.0"

  # backend "gcs" {{
  #   bucket = "rag-advisor-terraform-state"
  #   prefix = var.environment
  # }}
}}

locals {{
  topology_key    = {_hcl_string(topology["key"])}
  topology_name   = {_hcl_string(topology["name"])}
  pipeline_stages = {_hcl_list(projection["pipeline_stages"])}
}}

{module_blocks}
"""


def _root_variables() -> str:
    return """
variable "environment" {
  type    = string
  default = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "project_name" {
  type    = string
  default = "rag-advisor"
}

variable "region" {
  type    = string
  default = "us-east1"
}

variable "allowed_egress_domains" {
  type    = list(string)
  default = []
}

variable "vector_dimensions" {
  type    = list(number)
  default = [1024, 512]
}

variable "kms_key_id" {
  type    = string
  default = "alias/rag-advisor"
}

variable "audit_log_retention_days" {
  type    = number
  default = 365
}

variable "latency_slo_ms" {
  type    = number
  default = 1500
}

variable "min_replicas" {
  type    = number
  default = 1
}

variable "max_replicas" {
  type    = number
  default = 6
}
"""


def _root_outputs(projection: dict) -> str:
    component_outputs = "\n".join(
        f"    {component_id} = module.{component_id}.summary"
        for component_id in _component_ids(projection)
    )
    return f"""
output "topology_key" {{
  value = local.topology_key
}}

output "pipeline_stages" {{
  value = local.pipeline_stages
}}

output "deployment_components" {{
  value = {{
{component_outputs}
  }}
}}
"""


def _tfvars(environment: str, *, min_replicas: int, max_replicas: int, latency_slo_ms: int) -> str:
    return f"""
environment              = {_hcl_string(environment)}
project_name             = "rag-advisor"
region                   = "us-east1"
allowed_egress_domains   = ["huggingface.co"]
vector_dimensions        = [1024, 512]
kms_key_id               = "alias/rag-advisor-{environment}"
audit_log_retention_days = 365
latency_slo_ms           = {latency_slo_ms}
min_replicas             = {min_replicas}
max_replicas             = {max_replicas}
"""


def _shared_module_variables() -> list[tuple[str, str]]:
    return [
        ("environment", "string"),
        ("project_name", "string"),
        ("region", "string"),
        ("pipeline_stages", "list(string)"),
        ("serves", "list(string)"),
        ("controls", "list(string)"),
    ]


def _module_variable_blocks(component_id: str) -> str:
    variables = [*_shared_module_variables(), *MODULE_VARIABLES.get(component_id, ())]
    return "\n\n".join(
        f'variable "{name}" {{\n  type = {kind}\n}}'
        for name, kind in variables
    )


def _module_main(component: dict) -> str:
    component_id = component["id"]
    return f"""
{_module_variable_blocks(component_id)}

locals {{
  component_id  = {_hcl_string(component_id)}
  label         = {_hcl_string(component["label"])}
  pillar        = {_hcl_string(component["pillar"])}
  resource_kind = {_hcl_string(component["resource_kind"])}
}}

# Replace this output-only placeholder with provider resources for the chosen cloud.
output "summary" {{
  value = {{
    id            = local.component_id
    label         = local.label
    pillar        = local.pillar
    resource_kind = local.resource_kind
    serves        = var.serves
    controls      = var.controls
  }}
}}
"""


def _stack_readme(topology: dict, projection: dict) -> str:
    stages = " -> ".join(projection["pipeline_stages"])
    return f"""
# RAG Terraform Sketch

Topology: {topology["name"]} ({topology["key"]})

Pipeline: {stages}

This is illustrative output from the advisor, not infrastructure applied by the
Hugging Face Space. Use `terraform fmt`, `terraform validate`, and
`terraform plan -var-file=environments/dev.tfvars` before any apply.

The sketch demonstrates declarative definitions, repeatable tfvars-driven
environments, plan review gates, commented remote state, reusable modules,
environment consistency, and auditable plan/apply history.
"""


def emit_terraform(topology: dict, projection: dict) -> str:
    sections = [
        _file("README.md", _stack_readme(topology, projection)),
        _file("main.tf", _root_main(topology, projection)),
        _file("variables.tf", _root_variables()),
        _file("outputs.tf", _root_outputs(projection)),
        _file(
            "environments/dev.tfvars",
            _tfvars("dev", min_replicas=1, max_replicas=3, latency_slo_ms=1800),
        ),
        _file(
            "environments/staging.tfvars",
            _tfvars("staging", min_replicas=2, max_replicas=6, latency_slo_ms=1500),
        ),
        _file(
            "environments/prod.tfvars",
            _tfvars("prod", min_replicas=3, max_replicas=12, latency_slo_ms=1200),
        ),
    ]
    sections.extend(
        _file(f'modules/{component["id"]}/main.tf', _module_main(component))
        for component in projection["deployment_components"]
    )
    return "\n".join(sections)
