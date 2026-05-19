from __future__ import annotations

from graph.nodes import critic_node, router_node, specialist_node, synthesizer_node
from graph.state import AdvisorState


class AdvisorGraph:
    """Small runnable graph facade until LangGraph wiring lands in P5."""

    def invoke(self, initial: AdvisorState | dict) -> AdvisorState:
        state = AdvisorState.from_input(initial)
        state = router_node(state)
        state = specialist_node(state)
        state = synthesizer_node(state)
        state = critic_node(state)
        return state


def build_graph() -> AdvisorGraph:
    return AdvisorGraph()

