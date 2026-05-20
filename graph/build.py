from __future__ import annotations

import time

from graph.edges import should_elicit, should_reflect, should_resolve_conflict
from graph.nodes import (
    conflict_node,
    critic_node,
    elicitation_node,
    revise_node,
    research_node,
    router_node,
    specialist_node,
    synthesizer_node,
)
from graph.state import AdvisorState


class AdvisorGraph:
    """Runnable graph facade with explicit bounded control-flow decisions."""

    def invoke(self, initial: AdvisorState | dict) -> AdvisorState:
        started = time.perf_counter()
        state = AdvisorState.from_input(initial)
        state = _time_node(state, "router", router_node)

        if should_elicit(state.pending_elicitation):
            state = _time_node(state, "elicitation", elicitation_node)

        if should_resolve_conflict(state.conflict):
            state = _time_node(state, "conflict", conflict_node)

        state = _time_node(state, "specialists", specialist_node)
        state = _time_node(state, "research", research_node)
        state = _time_node(state, "synthesizer", synthesizer_node)
        state = _time_node(state, "critic", critic_node)
        while should_reflect(state.critique, state.loop_count):
            state = _time_node(state, "revise", revise_node, accumulate=True)
            state = _time_node(state, "synthesizer", synthesizer_node, accumulate=True)
            state = _time_node(state, "critic", critic_node, accumulate=True)
        state.timings_ms["graph_total"] = round((time.perf_counter() - started) * 1000, 2)
        return state


def build_graph() -> AdvisorGraph:
    return AdvisorGraph()


def _time_node(
    state: AdvisorState,
    key: str,
    fn,
    *,
    accumulate: bool = False,
) -> AdvisorState:
    started = time.perf_counter()
    next_state = fn(state)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    if accumulate:
        next_state.timings_ms[key] = round(next_state.timings_ms.get(key, 0.0) + elapsed, 2)
    else:
        next_state.timings_ms[key] = elapsed
    return next_state
