from __future__ import annotations


def emit_terraform(topology: dict, projection: dict) -> str:
    modules = "\n".join(
        f'module "{component["id"]}" {{\n  source = "./modules/{component["id"]}"\n}}'
        for component in projection["deployment_components"]
    )
    return f"""# Illustrative Terraform sketch for {topology["name"]}
terraform {{
  required_version = ">= 1.6.0"
}}

{modules}
"""

