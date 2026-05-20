from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from graph.state import ATTRIBUTES, RequirementValue
from synth.projection import project_deployment
from synth.terraform_emit import emit_terraform
from synth.topology import select_topology


def vector(**values: str) -> dict[str, RequirementValue]:
    result = {attr: RequirementValue() for attr in ATTRIBUTES}
    for attr, value in values.items():
        result[attr] = RequirementValue(value=value, source="smoke", confidence=1.0)
    return result


def main() -> None:
    topology = select_topology(
        vector(A1="catastrophic", A2="high", A3="synthetic", A11="mandatory", A12="gated")
    )
    projection = project_deployment(topology)
    terraform = emit_terraform(topology, projection)

    required_files = [
        "README.md",
        "main.tf",
        "variables.tf",
        "outputs.tf",
        "environments/dev.tfvars",
        "environments/staging.tfvars",
        "environments/prod.tfvars",
    ]
    required_files.extend(
        f"modules/{component['id']}/main.tf"
        for component in projection["deployment_components"]
    )
    for path in required_files:
        if f"# file: {path}" not in terraform:
            raise AssertionError(f"terraform sketch missing {path}")

    for component in projection["deployment_components"]:
        module_id = component["id"]
        if f'module "{module_id}"' not in terraform:
            raise AssertionError(f"root module block missing {module_id}")

    required_terms = [
        "terraform plan -var-file=environments/dev.tfvars",
        "vector_dimensions        = [1024, 512]",
        "review_queue_required",
        "p50_p95_p99_latency",
        "blue_green_alias",
    ]
    for term in required_terms:
        if term not in terraform:
            raise AssertionError(f"terraform sketch missing {term}")

    if terraform.count("{") != terraform.count("}"):
        raise AssertionError("terraform sketch has unbalanced braces")

    print(
        "terraform_emit_smoke=ok "
        f"files={len(required_files)} components={len(projection['deployment_components'])}"
    )


if __name__ == "__main__":
    main()
