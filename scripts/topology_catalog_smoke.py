from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from graph.state import ATTRIBUTES, RequirementValue
from synth.projection import project_deployment
from synth.topology import select_topology


def vector(**values: str) -> dict[str, RequirementValue]:
    result = {attr: RequirementValue() for attr in ATTRIBUTES}
    for attr, value in values.items():
        result[attr] = RequirementValue(value=value, source="smoke", confidence=1.0)
    return result


def main() -> None:
    selected = select_topology(
        vector(A1="catastrophic", A2="high", A3="synthetic", A11="mandatory", A12="gated")
    )
    if selected["key"] != "two_stage_hybrid_rerank":
        raise AssertionError(f"expected two_stage_hybrid_rerank, got {selected['key']}")
    if "single_stage_hybrid" in selected["selection"]["candidate_keys"]:
        raise AssertionError("gated review should remove direct-answer hybrid topology")
    if not selected["requirements"]["review_gate_required"]:
        raise AssertionError("A12 gated should mark review gate as required")

    projection = project_deployment(selected)
    if "review_gate" not in projection["pipeline_stages"]:
        raise AssertionError("deployment projection did not include review gate")
    pillars = {component["pillar"] for component in projection["deployment_components"]}
    expected_pillars = {
        "Compute",
        "Networking",
        "Storage",
        "Databases",
        "Security",
        "Monitoring",
        "Scalability",
    }
    if pillars != expected_pillars:
        raise AssertionError(f"pillar coverage changed: {pillars}")

    adaptive = select_topology(vector(A1="minor", A2="high", A3="multi-hop"))
    if adaptive["key"] != "adaptive_agentic":
        raise AssertionError("multi-hop should select adaptive/agentic topology")

    print(
        "topology_catalog_smoke=ok "
        f"selected={selected['key']} stages={len(projection['pipeline_stages'])}"
    )


if __name__ == "__main__":
    main()
