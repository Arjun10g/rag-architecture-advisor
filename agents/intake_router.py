from __future__ import annotations

from graph.state import ATTRIBUTES, AdvisorState, ConflictSet, DecisionLogEntry, RequirementValue


DOMAIN_PRIORS = {
    "medical-clinical": {
        "A1": ("catastrophic", "strong"),
        "A2": ("high", "strong"),
        "A3": ("synthetic", "elicit"),
        "A4": ("sectoral", "strong"),
        "A5": ("regulated-personal", "strong"),
        "A6": ("semi-structured records + long hierarchical guidelines", "elicit"),
        "A7": ("periodic", "elicit"),
        "A8": ("strict if point-of-care, relaxed if research", "elicit"),
        "A9": ("monolingual", "elicit"),
        "A10": ("far-jargon", "strong"),
        "A11": ("mandatory", "strong"),
        "A12": ("gated", "strong"),
    },
    "financial-banking": {
        "A1": ("catastrophic", "strong"),
        "A2": ("high", "strong"),
        "A3": ("synthetic", "elicit"),
        "A4": ("sectoral", "strong"),
        "A5": ("regulated-personal", "strong"),
        "A6": ("tabular + long policy documents", "elicit"),
        "A7": ("periodic", "elicit"),
        "A8": ("strict for customer-facing, relaxed for analyst tools", "elicit"),
        "A9": ("monolingual", "elicit"),
        "A10": ("moderate-jargon", "strong"),
        "A11": ("mandatory", "strong"),
        "A12": ("advisory", "elicit"),
    },
    "technical-software": {
        "A1": ("costly", "strong"),
        "A2": ("high", "strong"),
        "A3": ("synthetic", "elicit"),
        "A4": ("none", "elicit"),
        "A5": ("public", "elicit"),
        "A6": ("code + markdown + mixed", "strong"),
        "A7": ("fast-moving", "strong"),
        "A8": ("strict", "elicit"),
        "A9": ("monolingual", "strong"),
        "A10": ("moderate-jargon", "strong"),
        "A11": ("recommended", "strong"),
        "A12": ("none/advisory", "strong"),
    },
    "psychology-mental-health": {
        "A1": ("catastrophic", "strong"),
        "A2": ("moderate", "strong"),
        "A3": ("synthetic", "strong"),
        "A4": ("privacy", "elicit"),
        "A5": ("public", "elicit"),
        "A6": ("narrative prose + long hierarchical literature", "strong"),
        "A7": ("periodic", "strong"),
        "A8": ("relaxed", "strong"),
        "A9": ("monolingual", "elicit"),
        "A10": ("far-jargon", "strong"),
        "A11": ("mandatory", "strong"),
        "A12": ("gated", "strong"),
    },
}


DOMAIN_KEYWORDS = {
    "medical-clinical": {
        "clinical": 3,
        "medical": 3,
        "patient": 3,
        "hipaa": 3,
        "hospital": 2,
        "medication": 2,
        "ehr": 2,
        "care pathway": 2,
        "chart": 1,
    },
    "financial-banking": {
        "bank": 3,
        "financial": 3,
        "pci": 3,
        "transaction": 3,
        "aml": 2,
        "kyc": 2,
        "loan": 2,
        "credit": 2,
        "card": 2,
        "chargeback": 2,
        "fraud": 1,
    },
    "technical-software": {
        "api": 3,
        "sdk": 3,
        "code": 3,
        "developer": 3,
        "runbook": 3,
        "kubernetes": 2,
        "incident": 2,
        "changelog": 2,
        "release note": 2,
        "docs": 1,
    },
    "psychology-mental-health": {
        "psychology": 3,
        "therapy": 3,
        "therapeutic": 3,
        "mental health": 3,
        "cbt": 2,
        "behavioral": 2,
        "therapist": 2,
        "counselor": 2,
        "wellbeing": 1,
    },
}


STATED_ATTRIBUTE_PATTERNS = {
    "A3": [
        ("multi-hop", ("multi-hop", "chain across", "cross-document reasoning")),
        ("lookup", ("single fact", "simple lookup", "faq lookup")),
    ],
    "A4": [
        ("sectoral", ("hipaa", "pci", "pci-dss", "ferpa", "gxp")),
        ("privacy", ("gdpr", "ccpa", "privacy law")),
        ("none", ("no compliance", "not regulated")),
    ],
    "A5": [
        ("regulated-personal", ("phi", "pii", "patient data", "customer financial", "regulated personal")),
        ("internal", ("proprietary code", "confidential internal", "private repository")),
        ("public", ("public docs", "public documentation", "public corpus")),
    ],
    "A6": [
        ("code + markdown + mixed", ("code snippets", "sdk examples", "api references")),
        ("semi-structured records + long hierarchical guidelines", ("ehr", "patient chart", "patient records")),
        ("tabular + long policy documents", ("transaction logs", "ledger", "policy manuals")),
        ("narrative prose + long hierarchical literature", ("literature", "worksheets", "therapist notes")),
    ],
    "A7": [
        ("fast-moving", ("fast-moving", "change quickly", "release notes", "changelog")),
        ("periodic", ("periodic updates", "updated monthly", "updated quarterly")),
        ("static", ("static archive", "rarely changes")),
    ],
    "A8": [
        ("strict", ("point-of-care", "in-ide", "interactive latency", "sub-second")),
        ("relaxed", ("batch", "research workflow", "offline review")),
    ],
    "A9": [
        ("multilingual", ("multilingual", "many languages")),
        ("cross-lingual", ("cross-lingual", "translate queries")),
        ("monolingual", ("english only", "single language")),
    ],
    "A11": [
        ("mandatory", ("mandatory citations", "must cite", "audit required", "regulator")),
        ("recommended", ("citation support", "source support")),
    ],
    "A12": [
        ("gated", ("human review", "clinician sees", "sign off", "approval gate")),
        ("advisory", ("advisory only", "human uses as reference")),
        ("none/advisory", ("no review", "direct answer")),
    ],
}


def detect_domain(user_brief: str) -> str | None:
    scores = score_domains(user_brief)
    domain, score = max(scores.items(), key=lambda item: item[1])
    return domain if score > 0 else None


def score_domains(user_brief: str) -> dict[str, int]:
    text = user_brief.lower()
    return {
        domain: sum(weight for keyword, weight in keywords.items() if keyword in text)
        for domain, keywords in DOMAIN_KEYWORDS.items()
    }


def resolve_requirements(state: AdvisorState) -> AdvisorState:
    _reset_router_outputs(state)
    state.domain_scores = score_domains(state.user_brief)
    domain = state.domain_prior or _select_domain(state.domain_scores)
    state.domain_prior = domain

    if not domain:
        state.pending_elicitation = list(ATTRIBUTES)
        state.decision_log.append(
            DecisionLogEntry(
                attr="domain",
                value=None,
                source="inferred",
                confidence=0.0,
                reason="No domain prior matched; router should elicit the full vector.",
            )
        )
        return state

    _apply_domain_prior(state, domain)
    _apply_stated_overrides(state)
    _apply_elicitation_answers(state)
    _apply_hard_constraints(state)
    _detect_conflicts(state)
    return state


def _reset_router_outputs(state: AdvisorState) -> None:
    state.requirement_vector = {attr: RequirementValue() for attr in ATTRIBUTES}
    state.pending_elicitation.clear()
    state.decision_log.clear()
    state.conflict = None
    state.hard_constraints.clear()


def _select_domain(scores: dict[str, int]) -> str | None:
    domain, score = max(scores.items(), key=lambda item: item[1])
    return domain if score > 0 else None


def _apply_domain_prior(state: AdvisorState, domain: str) -> None:
    for attr, (value, confidence_flag) in DOMAIN_PRIORS[domain].items():
        confidence = 0.9 if confidence_flag == "strong" else 0.55
        _set_requirement(
            state,
            attr,
            value,
            source="domain-prior",
            confidence=confidence,
            reason=f"Seeded from {domain} profile with {confidence_flag} confidence.",
        )
        if confidence_flag == "elicit":
            state.pending_elicitation.append(attr)


def _apply_stated_overrides(state: AdvisorState) -> None:
    text = state.user_brief.lower()
    for attr, rules in STATED_ATTRIBUTE_PATTERNS.items():
        for value, patterns in rules:
            if any(pattern in text for pattern in patterns):
                _set_requirement(
                    state,
                    attr,
                    value,
                    source="stated",
                    confidence=0.95,
                    reason=f"User brief explicitly indicates {attr}={value}.",
                )
                _mark_resolved(state, attr)
                break


def _apply_elicitation_answers(state: AdvisorState) -> None:
    for attr, value in state.elicitation_answers.items():
        if attr not in ATTRIBUTES or not str(value).strip():
            continue
        _set_requirement(
            state,
            attr,
            str(value).strip(),
            source="stated",
            confidence=1.0,
            reason="Resolved from explicit elicitation answer.",
        )
        _mark_resolved(state, attr)


def _apply_hard_constraints(state: AdvisorState) -> None:
    constraints = []
    if _value(state, "A2") == "high":
        constraints.append("A2 high: lexical or hybrid retrieval is mandatory.")
    if _value(state, "A4") == "sectoral":
        constraints.append("A4 sectoral: restrict generation to approved in-boundary providers.")
    if _value(state, "A5") == "regulated-personal":
        constraints.append("A5 regulated-personal: permission-aware retrieval and redaction are mandatory.")
    if _value(state, "A11") == "mandatory":
        constraints.append("A11 mandatory: citation and decision lineage logging are mandatory.")
    if _value(state, "A12") == "gated":
        constraints.append("A12 gated: direct-answer topologies must end in human review.")
    state.hard_constraints = constraints


def _detect_conflicts(state: AdvisorState) -> None:
    text = state.user_brief.lower()
    if (
        _value(state, "A4") == "sectoral"
        and _value(state, "A5") == "regulated-personal"
        and any(pattern in text for pattern in ("external api", "third-party llm", "hosted llm"))
    ):
        state.conflict = ConflictSet(
            attributes=["A4", "A5"],
            options=[
                "Use in-boundary/open-weight generation and preserve compliance.",
                "Use external hosted generation only after an explicit compliance exception.",
            ],
            rationale=(
                "The brief asks for external model use while the resolved vector requires "
                "sectoral compliance and regulated-personal data handling."
            ),
        )
        _record_conflict(state)
        return

    if _value(state, "A1") == "catastrophic" and _value(state, "A8") == "strict":
        state.conflict = ConflictSet(
            attributes=["A1", "A8"],
            options=[
                "Prioritize safety: keep reranking/review and accept higher latency.",
                "Prioritize latency: reduce stages and surface lower assurance explicitly.",
            ],
            rationale="Catastrophic answer risk pulls toward extra checks, while strict latency caps stages.",
        )
        _record_conflict(state)


def _record_conflict(state: AdvisorState) -> None:
    if not state.conflict:
        return
    state.decision_log.append(
        DecisionLogEntry(
            attr="conflict",
            value=",".join(state.conflict.attributes),
            source="inferred",
            confidence=0.8,
            reason=state.conflict.rationale,
        )
    )


def _set_requirement(
    state: AdvisorState,
    attr: str,
    value: str,
    *,
    source: str,
    confidence: float,
    reason: str,
) -> None:
    prior = state.requirement_vector.get(attr, RequirementValue())
    overrode_prior = bool(prior.value is not None and prior.value != value)
    state.requirement_vector[attr] = RequirementValue(
        value=value,
        source=source,
        confidence=confidence,
        overrode_prior=overrode_prior,
    )
    state.decision_log.append(
        DecisionLogEntry(
            attr=attr,
            value=value,
            source=source,
            confidence=confidence,
            reason=_override_reason(reason, prior.value, value) if overrode_prior else reason,
            overrode_prior=overrode_prior,
        )
    )


def _override_reason(reason: str, prior_value: str | None, value: str) -> str:
    return f"{reason} Overrides prior value {prior_value!r} with {value!r}."


def _mark_resolved(state: AdvisorState, attr: str) -> None:
    state.pending_elicitation = [pending for pending in state.pending_elicitation if pending != attr]


def _value(state: AdvisorState, attr: str) -> str | None:
    return state.requirement_vector.get(attr, RequirementValue()).value
