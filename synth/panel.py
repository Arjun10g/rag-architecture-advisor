from __future__ import annotations

from graph.state import AdvisorState


def build_panel(state: AdvisorState, topology: dict) -> dict:
    strengths = [
        f"{topology['name']} keeps topology selection auditable.",
        "Decision log preserves the router rationale per attribute.",
    ]
    weaknesses = []
    if state.pending_elicitation:
        weaknesses.append(
            "Some attributes still need elicitation before this should be treated as final."
        )
    if not state.agent_findings:
        weaknesses.append("Specialist findings are placeholders until retrieval is wired.")
    return {"strengths": strengths, "weaknesses": weaknesses or ["No skeleton-level gaps found."]}

