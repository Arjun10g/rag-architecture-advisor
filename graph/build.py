from __future__ import annotations

from graph.edges import should_elicit, should_reflect, should_resolve_conflict
from graph.nodes import (
    conflict_node,
    critic_node,
    elicitation_node,
    revise_node,
    router_node,
    specialist_node,
    synthesizer_node,
)
from graph.state import AdvisorState


class AdvisorGraph:
    """Runnable graph facade with explicit bounded control-flow decisions."""

    def invoke(self, initial: AdvisorState | dict) -> AdvisorState:
        state = AdvisorState.from_input(initial)
        state = router_node(state)

        if should_elicit(state.pending_elicitation):
            state = elicitation_node(state)

        if should_resolve_conflict(state.conflict):
            state = conflict_node(state)

        state = specialist_node(state)
        state = synthesizer_node(state)
        state = critic_node(state)
        while should_reflect(state.critique, state.loop_count):
            state = revise_node(state)
            state = synthesizer_node(state)
            state = critic_node(state)
        return state


def build_graph() -> AdvisorGraph:
    return AdvisorGraph()
