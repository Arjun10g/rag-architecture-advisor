from __future__ import annotations

from graph.state import AdvisorState


def critique(state: AdvisorState) -> list[str]:
    gaps: list[str] = []
    if not state.draft_output:
        gaps.append("No draft output was produced.")
    if not state.decision_log:
        gaps.append("Decision log is empty.")
    return gaps

