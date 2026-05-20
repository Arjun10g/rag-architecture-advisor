from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.intake_router import resolve_requirements
from graph.state import AdvisorState


def main() -> None:
    conflict_state = resolve_requirements(
        AdvisorState(
            user_brief=(
                "A clinical team wants a HIPAA assistant over PHI patient records, "
                "but asks to use an external API for generation."
            )
        )
    )
    if conflict_state.domain_prior != "medical-clinical":
        raise AssertionError("clinical domain was not detected")
    if "A4 sectoral: restrict generation to approved in-boundary providers." not in conflict_state.hard_constraints:
        raise AssertionError("sectoral hard constraint missing")
    if conflict_state.conflict is None or set(conflict_state.conflict.attributes) != {"A4", "A5"}:
        raise AssertionError("external-model compliance conflict was not recorded")

    answered_state = resolve_requirements(
        AdvisorState(
            user_brief="A developer portal for public SDK docs and API references.",
            elicitation_answers={"A4": "privacy", "A5": "internal", "A8": "moderate"},
        )
    )
    if answered_state.requirement_vector["A4"].value != "privacy":
        raise AssertionError("elicitation answer did not override A4")
    if answered_state.requirement_vector["A5"].overrode_prior is not True:
        raise AssertionError("override provenance was not recorded")
    if {"A4", "A5", "A8"} & set(answered_state.pending_elicitation):
        raise AssertionError("answered attributes should not remain pending")

    print(
        "router_state_smoke=ok "
        f"constraints={len(conflict_state.hard_constraints)} "
        f"pending={len(answered_state.pending_elicitation)}"
    )


if __name__ == "__main__":
    main()
