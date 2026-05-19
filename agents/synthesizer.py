from __future__ import annotations

from graph.state import AdvisorState
from synth.panel import build_panel
from synth.projection import project_deployment
from synth.terraform_emit import emit_terraform
from synth.topology import select_topology


def synthesize(state: AdvisorState) -> dict:
    topology = select_topology(state.requirement_vector)
    projection = project_deployment(topology)
    return {
        "topology": topology,
        "projection": projection,
        "terraform": emit_terraform(topology, projection),
        "panel": build_panel(state, topology),
    }

