from __future__ import annotations

from dataclasses import asdict

from graph.state import AdvisorState
from synth.panel import build_panel
from synth.projection import project_deployment
from synth.terraform_emit import emit_terraform
from synth.topology import select_topology


def _collect_sources(state: AdvisorState) -> list[dict]:
    sources: dict[str, dict] = {}
    for finding in state.agent_findings.values():
        for source in finding.sources:
            record = sources.setdefault(source.source_id, asdict(source) | {"used_by": []})
            if finding.agent not in record["used_by"]:
                record["used_by"].append(finding.agent)
    return list(sources.values())


def synthesize(state: AdvisorState) -> dict:
    topology = select_topology(state.requirement_vector)
    projection = project_deployment(topology)
    return {
        "topology": topology,
        "projection": projection,
        "terraform": emit_terraform(topology, projection),
        "panel": build_panel(state, topology),
        "sources": _collect_sources(state),
    }
