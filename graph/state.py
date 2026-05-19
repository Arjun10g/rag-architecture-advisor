from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ATTRIBUTES = tuple(f"A{i}" for i in range(1, 13))


@dataclass
class RequirementValue:
    value: str | None = None
    source: str = "unset"
    confidence: float = 0.0
    overrode_prior: bool = False


@dataclass
class DecisionLogEntry:
    attr: str
    value: str | None
    source: str
    confidence: float
    reason: str
    overrode_prior: bool = False


@dataclass
class ConflictSet:
    attributes: list[str]
    options: list[str]
    rationale: str


@dataclass
class Finding:
    agent: str
    recommendation: str
    decisions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)


@dataclass
class AdvisorState:
    user_brief: str
    requirement_vector: dict[str, RequirementValue] = field(
        default_factory=lambda: {attr: RequirementValue() for attr in ATTRIBUTES}
    )
    decision_log: list[DecisionLogEntry] = field(default_factory=list)
    domain_prior: str | None = None
    pending_elicitation: list[str] = field(default_factory=list)
    conflict: ConflictSet | None = None
    agent_findings: dict[str, Finding] = field(default_factory=dict)
    draft_output: dict[str, Any] | None = None
    critique: list[str] = field(default_factory=list)
    loop_count: int = 0

    @classmethod
    def from_input(cls, value: "AdvisorState | dict[str, Any]") -> "AdvisorState":
        if isinstance(value, AdvisorState):
            return value
        return cls(user_brief=str(value.get("user_brief", "")))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

