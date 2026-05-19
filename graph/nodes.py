from __future__ import annotations

from agents.critic import critique
from agents.intake_router import resolve_requirements
from agents.specialists import run_specialists
from agents.synthesizer import synthesize
from graph.state import AdvisorState


def router_node(state: AdvisorState) -> AdvisorState:
    return resolve_requirements(state)


def specialist_node(state: AdvisorState) -> AdvisorState:
    state.agent_findings = run_specialists(state)
    return state


def synthesizer_node(state: AdvisorState) -> AdvisorState:
    state.draft_output = synthesize(state)
    return state


def critic_node(state: AdvisorState) -> AdvisorState:
    state.critique = critique(state)
    return state

