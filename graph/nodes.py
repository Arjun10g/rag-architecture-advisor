from __future__ import annotations

from agents.critic import critique
from agents.intake_router import resolve_requirements
from agents.specialists import run_specialists
from agents.synthesizer import synthesize
from graph.state import AdvisorState, DecisionLogEntry


def router_node(state: AdvisorState) -> AdvisorState:
    state.graph_trace.append("router:start")
    return resolve_requirements(state)


def elicitation_node(state: AdvisorState) -> AdvisorState:
    if state.pending_elicitation:
        pending = ",".join(state.pending_elicitation)
        state.graph_trace.append(f"elicitation:pending:{pending}")
    else:
        state.graph_trace.append("elicitation:complete")
    return state


def conflict_node(state: AdvisorState) -> AdvisorState:
    if not state.conflict:
        state.graph_trace.append("conflict:none")
        return state

    if state.conflict_resolution:
        state.decision_log.append(
            DecisionLogEntry(
                attr="conflict_resolution",
                value=state.conflict_resolution,
                source="conflict-resolved",
                confidence=1.0,
                reason="User supplied an explicit conflict-resolution choice.",
            )
        )
        state.graph_trace.append(f"conflict:resolved:{state.conflict_resolution}")
        state.conflict = None
        return state

    state.graph_trace.append("conflict:unresolved")
    return state


def specialist_node(state: AdvisorState) -> AdvisorState:
    state.graph_trace.append("specialists:start")
    state.agent_findings = run_specialists(state)
    state.graph_trace.append("specialists:complete")
    return state


def synthesizer_node(state: AdvisorState) -> AdvisorState:
    state.graph_trace.append("synthesizer:start")
    state.draft_output = synthesize(state)
    state.graph_trace.append("synthesizer:complete")
    return state


def critic_node(state: AdvisorState) -> AdvisorState:
    state.graph_trace.append("critic:start")
    state.critique = critique(state)
    state.graph_trace.append("critic:complete")
    return state


def revise_node(state: AdvisorState) -> AdvisorState:
    state.loop_count += 1
    state.graph_trace.append(f"revise:loop:{state.loop_count}")
    return state
