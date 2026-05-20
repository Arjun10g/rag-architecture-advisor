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
    element_type: str = ""
    url: str | None = None


@dataclass
class Finding:
    agent: str
    recommendation: str
    decisions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)


@dataclass
class ResearchLink:
    label: str
    url: str
    source_type: str
    relevance: str
    agent: str = ""


@dataclass
class ResearchApproachSummary:
    label: str
    url: str
    source_type: str
    status: str
    word_count: int
    summary: str
    approach_steps: list[str] = field(default_factory=list)
    implementation_notes: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


@dataclass
class ResearchFinding:
    agent: str
    summary: str
    status: str = "ok"
    subqueries: list[str] = field(default_factory=list)
    links: list[ResearchLink] = field(default_factory=list)
    approach_summaries: list[ResearchApproachSummary] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    duration_ms: float = 0.0


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
    deep_thinking: bool = False
    hard_constraints: list[str] = field(default_factory=list)
    agent_findings: dict[str, Finding] = field(default_factory=dict)
    research_findings: dict[str, ResearchFinding] = field(default_factory=dict)
    draft_output: dict[str, Any] | None = None
    critique: list[str] = field(default_factory=list)
    loop_count: int = 0
    graph_trace: list[str] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_input(cls, value: "AdvisorState | dict[str, Any]") -> "AdvisorState":
        if isinstance(value, AdvisorState):
            return value
        return cls(
            user_brief=str(value.get("user_brief", "")),
            domain_prior=value.get("domain_prior"),
            elicitation_answers=dict(value.get("elicitation_answers") or {}),
            conflict_resolution=value.get("conflict_resolution"),
            deep_thinking=_boolish(value.get("deep_thinking", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower().strip() in {"1", "true", "yes", "on"}
    return bool(value)
