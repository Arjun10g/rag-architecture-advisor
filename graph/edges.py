from __future__ import annotations


MAX_REFLECTION_LOOPS = 2
SPECIALIST_NAMES = ("retrieval", "security", "cloud_iac", "evaluation")


def should_elicit(pending_elicitation: list[str]) -> bool:
    return bool(pending_elicitation)


def should_resolve_conflict(conflict: object | None) -> bool:
    return conflict is not None


def should_reflect(critique: list[str], loop_count: int) -> bool:
    return bool(critique) and loop_count < MAX_REFLECTION_LOOPS

