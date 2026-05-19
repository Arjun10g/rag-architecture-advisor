from __future__ import annotations

from graph.state import ATTRIBUTES, AdvisorState, DecisionLogEntry, RequirementValue


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


def detect_domain(user_brief: str) -> str | None:
    text = user_brief.lower()
    if any(word in text for word in ("clinical", "medical", "patient", "hipaa")):
        return "medical-clinical"
    if any(word in text for word in ("bank", "financial", "pci", "transaction")):
        return "financial-banking"
    if any(word in text for word in ("api", "sdk", "code", "developer", "runbook")):
        return "technical-software"
    if any(word in text for word in ("psychology", "therapy", "therapeutic", "mental health")):
        return "psychology-mental-health"
    return None


def resolve_requirements(state: AdvisorState) -> AdvisorState:
    domain = state.domain_prior or detect_domain(state.user_brief)
    state.domain_prior = domain
    state.pending_elicitation.clear()

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

    for attr, (value, confidence_flag) in DOMAIN_PRIORS[domain].items():
        confidence = 0.9 if confidence_flag == "strong" else 0.55
        state.requirement_vector[attr] = RequirementValue(
            value=value,
            source="domain-prior",
            confidence=confidence,
        )
        if confidence_flag == "elicit":
            state.pending_elicitation.append(attr)
        state.decision_log.append(
            DecisionLogEntry(
                attr=attr,
                value=value,
                source="domain-prior",
                confidence=confidence,
                reason=f"Seeded from {domain} profile.",
            )
        )

    return state

