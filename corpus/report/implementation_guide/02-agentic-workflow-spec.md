# 02 — Agentic Workflow Spec

**Track A.** The LangGraph state machine. This is resume priority #1; the engineering depth and the README narrative concentrate here. Consumes `routing/01-router-decision-logic.md` as the router's behavior contract.

## Shared state (`graph/state.py`)

A single typed object threaded through every node:

- `user_brief: str`
- `requirement_vector: dict[Attr, Level]` — A1–A12, nullable until resolved
- `decision_log: list[Entry]` — per attribute: value, source ∈ {stated, inferred, domain-prior, hybrid-conservative, conflict-resolved}, confidence, overrode_prior?
- `domain_prior: str | None`
- `pending_elicitation: list[Attr]`
- `conflict: ConflictSet | None`
- `agent_findings: dict[agent, Finding]`
- `draft_output: Output | None`
- `critique: list[Gap]`
- `loop_count: int` (cap 2; hard stop)

The `decision_log` is a first-class output, surfaced in the UI and exported. It is the artifact that answers "why did it recommend X here but not there?" — the entire defensibility of the project.

## Nodes (`graph/nodes.py`)

1. **Intake / Router.** Implements Stages 1–5 of the router decision logic: domain detection → apply prior from the routing namespace → identify `pending_elicitation` → (after elicitation returns) hard-constraint enforcement → conflict detection. Emits the resolved `requirement_vector` + `decision_log`.
2. **Elicitation.** Renders one batched question set for all `pending_elicitation` attributes; maps answers to levels; writes overrides to the log. Returns to Router.
3. **Conflict / Pareto.** When `conflict` is set: compute the satisfiable set, present the explicit tradeoff (grounded), take the user's choice, record `conflict-resolved` entries. Returns to Router for final emit.
4. **Specialist agents (parallel fan-out).** Uniform contract: `(requirement_vector, focus_question) -> Finding{recommendation, decisions[], open_questions[], source_ids[]}`. Each retrieves from the **knowledge** namespace only, section-filtered to its concern. Run concurrently; joined at the synthesizer (barrier).
5. **Synthesizer.** Track B handoff: requirement vector → topology selection → deployment projection → Terraform emit → strengths/weaknesses panel. Spec 05.
6. **Critic.** Checks `draft_output` for unsupported claims, missing pillars, requirement violations. Emits `critique` gaps or passes through. Bounded by `loop_count`.

## Edges (`graph/edges.py`)

- After Router: conditional → `elicit` if `pending_elicitation` non-empty → `conflict` if `conflict` set → else fan-out to specialists.
- Router → {4 specialists}: parallel; barrier-joined at Synthesizer.
- After Critic: conditional → `revise` (back to Router with `critique`) vs `finalize`, gated by `loop_count < 2`.

This shape — conditional elicitation loop + parallel fan-out + bounded reflection + typed state with an audit log — is the diagram you put at the top of the README and walk through in interviews.

## Router → Synthesizer handoff contract

The synthesizer receives **only** the resolved `requirement_vector` + `decision_log`. It never re-reads `user_brief` or re-derives requirements. Single source of truth for "what the user needs" is the router; single source of truth for "what design satisfies it" is the synthesizer. This clean seam is itself a systems-design talking point.

## Failure handling

- Elicitation loop and reflection loop both hard-capped; on cap, proceed with best-available vector and flag residual uncertainty in the output rather than looping forever.
- Specialist agent failure (retrieval empty / model error): the agent returns a `Finding` with an explicit `open_questions` entry rather than throwing; the synthesizer surfaces the gap instead of silently omitting it. Graceful degradation is a deliberate, stated property.
