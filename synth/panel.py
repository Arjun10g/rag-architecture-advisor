from __future__ import annotations

from graph.state import AdvisorState


def build_panel(state: AdvisorState, topology: dict) -> dict:
    strengths = [
        f"{topology['name']} keeps topology selection auditable.",
        "Decision log preserves the router rationale per attribute.",
    ]
    if state.hard_constraints:
        strengths.append("Hard constraints are applied before topology quality optimization.")
    weaknesses = []
    if state.pending_elicitation:
        weaknesses.append(
            "Some attributes still need elicitation before this should be treated as final."
        )
    if state.conflict:
        weaknesses.append("A router conflict needs explicit tradeoff resolution before final deployment.")
    if not state.agent_findings:
        weaknesses.append("Specialist findings are placeholders until retrieval is wired.")
    return {"strengths": strengths, "weaknesses": weaknesses or ["No skeleton-level gaps found."]}
