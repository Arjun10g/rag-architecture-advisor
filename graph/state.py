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
class SourceRef:
    source_id: str
    title: str
    section: str
    source_path: str
    score: float
    snippet: str = ""


@dataclass
class Finding:
    agent: str
    recommendation: str
    decisions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)


@dataclass
class AdvisorState:
    user_brief: str
    requirement_vector: dict[str, RequirementValue] = field(
        default_factory=lambda: {attr: RequirementValue() for attr in ATTRIBUTES}
    )
    decision_log: list[DecisionLogEntry] = field(default_factory=list)
    domain_prior: str | None = None
    domain_scores: dict[str, int] = field(default_factory=dict)
    pending_elicitation: list[str] = field(default_factory=list)
    elicitation_answers: dict[str, str] = field(default_factory=dict)
    conflict: ConflictSet | None = None
    conflict_resolution: str | None = None
    hard_constraints: list[str] = field(default_factory=list)
    agent_findings: dict[str, Finding] = field(default_factory=dict)
    draft_output: dict[str, Any] | None = None
    critique: list[str] = field(default_factory=list)
    loop_count: int = 0

    @classmethod
    def from_input(cls, value: "AdvisorState | dict[str, Any]") -> "AdvisorState":
        if isinstance(value, AdvisorState):
            return value
        return cls(
            user_brief=str(value.get("user_brief", "")),
            domain_prior=value.get("domain_prior"),
            elicitation_answers=dict(value.get("elicitation_answers") or {}),
            conflict_resolution=value.get("conflict_resolution"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
