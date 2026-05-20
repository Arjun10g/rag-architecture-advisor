from __future__ import annotations

import json
import os
import time
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

try:
    import gradio as gr
except ImportError:  # pragma: no cover
    gr = None

from graph.build import build_graph
from graph.state import AdvisorState
from synth.panel import ATTRIBUTE_LABELS


if load_dotenv:
    load_dotenv()


EXAMPLE_BRIEFS = [
    "Build an internal API docs assistant over fast-moving SDK docs with strict citations, mixed markdown and code, and high exact-match terminology needs.",
    "Build a banking compliance assistant over customer policy, PCI controls, KYC procedures, and transaction runbooks where mistakes are costly and every answer needs auditability.",
    "Build a mental health therapy literature assistant for clinicians reviewing CBT studies and narrative research notes, with citation support and lower exact-match pressure than API documentation.",
    "We need a RAG system, but the domain, document type, sensitivity, update cadence, and latency requirements are not known yet.",
]

DetailResponse = tuple[str, str, list[list[Any]], str, str, str, dict[str, Any]]
ClearDetailResponse = tuple[str, str, list[list[Any]], str, str, str, str, dict[str, Any]]


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.lower().strip() in {"1", "true", "yes", "on"}


def _auth_credentials() -> tuple[str, str] | None:
    username = os.getenv("GRADIO_AUTH_USERNAME", "").strip()
    password = os.getenv("GRADIO_AUTH_PASSWORD", "").strip()
    if bool(username) != bool(password):
        raise RuntimeError("Set both GRADIO_AUTH_USERNAME and GRADIO_AUTH_PASSWORD, or neither.")
    return (username, password) if username and password else None


def _evidence_refs_text(refs: list[str]) -> str:
    return " ".join(f"[{ref}]" for ref in refs)


def _source_label(source: dict[str, Any], fallback_index: int) -> str:
    return str(source.get("evidence_label") or f"E{fallback_index}")


def _parse_elicitation_answers(value: str | None) -> dict[str, str]:
    if not value or not value.strip():
        return {}
    stripped = value.strip()
    if stripped.startswith("{"):
        parsed = json.loads(stripped)
        return {str(key): str(item) for key, item in parsed.items() if str(item).strip()}

    answers: dict[str, str] = {}
    for line in stripped.splitlines():
        if "=" not in line:
            continue
        key, answer = line.split("=", 1)
        if key.strip() and answer.strip():
            answers[key.strip()] = answer.strip()
    return answers


def _requirement_value(state: AdvisorState, attr: str) -> str | None:
    return state.requirement_vector.get(attr).value if attr in state.requirement_vector else None


def _format_topology_rationale(state: AdvisorState, topology: dict) -> str:
    drivers = []
    for attr in ("A2", "A3", "A1", "A8", "A11", "A12"):
        value = _requirement_value(state, attr)
        if value:
            drivers.append(f"{ATTRIBUTE_LABELS.get(attr, attr)} is **{value}**")
    driver_text = "; ".join(drivers)
    lines = [
        "Selected by applying the resolved requirements to the fixed topology catalog.",
    ]
    if driver_text:
        lines.append(f"Key drivers: {driver_text}.")
    lines.extend(_readable_topology_filters(topology))
    return " ".join(lines)


def _readable_topology_filters(topology: dict) -> list[str]:
    filters = (topology.get("selection") or {}).get("filters") or []
    readable_filters = []
    for item in filters:
        if "A2 high" in item:
            readable_filters.append(
                "Dense-only options were removed because exact terminology dependence is high."
            )
        elif "A12 gated" in item:
            readable_filters.append(
                "Direct-answer options were removed because the workflow requires a review gate."
            )
        elif "A8 strict" in item:
            readable_filters.append(
                "Adaptive loops were avoided unless risk justified the extra latency."
            )
    return readable_filters


def _readable_constraint(constraint: str) -> str:
    if constraint.startswith("A2 high"):
        return "High exact terminology dependence makes lexical or hybrid retrieval mandatory."
    if constraint.startswith("A4 sectoral"):
        return "Sectoral compliance requires in-boundary generation providers."
    if constraint.startswith("A5 regulated-personal"):
        return "Regulated personal data requires permission-aware retrieval and redaction."
    if constraint.startswith("A11 mandatory"):
        return "Mandatory citation needs require decision lineage logging."
    if constraint.startswith("A12 gated"):
        return "Human review requirements rule out direct-answer deployment without a review gate."
    return constraint


def _format_output(state: AdvisorState) -> str:
    output = state.draft_output or {}
    topology = output.get("topology", {})
    panel = output.get("panel", {})
    terraform = output.get("terraform", "")
    architecture_decisions = output.get("architecture_decisions") or []
    sources = output.get("sources") or []
    generated_answer = output.get("generated_answer")

    lines = [
        "## Recommendation",
        f"**Topology:** {topology.get('name', 'pending')}",
        "",
        "## Why",
    ]
    for entry in state.decision_log[:8]:
        label = ATTRIBUTE_LABELS.get(entry.attr, entry.attr)
        lines.append(f"- {label}: {entry.value} ({entry.source.replace('-', ' ')})")

    if generated_answer:
        lines.extend(["", "## Generated Advisor Summary", str(generated_answer).strip()])

    lines.extend(["", "## Strengths"])
    for item in panel.get("strengths", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Weaknesses"])
    for item in panel.get("weaknesses", []):
        lines.append(f"- {item}")

    if architecture_decisions:
        lines.extend(["", "## Architecture Decisions"])
        for decision in architecture_decisions:
            area = str(decision.get("area") or "decision").replace("_", " ").title()
            choice = decision.get("choice") or "Pending"
            evidence_refs = decision.get("evidence_refs") or []
            lines.append(f"- **{area}:** {choice}")
            if decision.get("rationale"):
                lines.append(f"  {decision['rationale']}")
            for step in decision.get("reasoning_steps") or []:
                lines.append(f"  - {step}")
            if decision.get("tradeoff"):
                lines.append(f"  Tradeoff: {decision['tradeoff']}")
            if decision.get("validation"):
                lines.append(f"  Validate: {decision['validation']}")
            if evidence_refs:
                lines.append(f"  Evidence: {_evidence_refs_text(evidence_refs[:3])}")

    if terraform:
        lines.extend(["", "## Terraform Sketch", "```hcl", terraform.strip(), "```"])

    if sources:
        lines.extend(["", "## Sources"])
        for index, source in enumerate(sources[:8], start=1):
            title = source.get("title") or "Untitled source"
            section = source.get("section") or "Unsectioned"
            evidence_label = source.get("evidence_label") or f"E{index}"
            used_by = ", ".join(source.get("used_by") or [])
            label = section if section.startswith(title) else f"{title} - {section}"
            lines.append(f"- [{evidence_label}] {label}")
            if used_by:
                lines.append(f"  Used by: {used_by}")
            if source.get("snippet"):
                lines.append(f"  Reasoning chunk: {source['snippet']}")

    return "\n".join(lines)


def _format_recommendation(state: AdvisorState) -> str:
    output = state.draft_output or {}
    topology = output.get("topology", {})
    panel = output.get("panel", {})
    generated_answer = output.get("generated_answer")
    lines = [
        f"## {topology.get('name', 'Pending')}",
        _format_topology_rationale(state, topology),
    ]

    if generated_answer:
        lines.extend(["", str(generated_answer).strip()])

    if state.pending_elicitation:
        lines.extend(["", "### Questions To Confirm"])
        for attr in state.pending_elicitation:
            lines.append(f"- {ATTRIBUTE_LABELS.get(attr, attr)}")

    strengths = panel.get("strengths", [])[:3]
    weaknesses = panel.get("weaknesses", [])[:3]
    if strengths or weaknesses:
        lines.extend(["", "### Advisor Checks"])
        for item in strengths:
            lines.append(f"- Strength: {item}")
        for item in weaknesses:
            lines.append(f"- Risk: {item}")

    return "\n".join(line for line in lines if line is not None)


def _format_architecture_decisions(state: AdvisorState) -> str:
    decisions = (state.draft_output or {}).get("architecture_decisions") or []
    if not decisions:
        return "No architecture decisions generated."

    lines = []
    for decision in decisions:
        area = str(decision.get("area") or "decision").replace("_", " ").title()
        lines.append(f"### {area}")
        lines.append(str(decision.get("choice") or "Pending"))
        if decision.get("rationale"):
            lines.extend(["", "**Why:**", str(decision["rationale"])])
        if decision.get("reasoning_steps"):
            lines.extend(["", "**Reasoning:**"])
            for step in decision["reasoning_steps"]:
                lines.append(f"- {step}")
        if decision.get("tradeoff"):
            lines.extend(["", "**Accepted Tradeoff:**", str(decision["tradeoff"])])
        if decision.get("validation"):
            lines.extend(["", "**Validation Gate:**", str(decision["validation"])])
        evidence_refs = decision.get("evidence_refs") or []
        if evidence_refs:
            lines.extend(["", "**Evidence:** " + _evidence_refs_text(evidence_refs)])
        evidence_chunks = decision.get("evidence_chunks") or []
        if evidence_chunks:
            lines.extend(["", "**Reasoning Chunks:**"])
            for chunk in evidence_chunks:
                label = chunk.get("evidence_label") or "E?"
                lines.append(
                    f"- [{label}] {chunk.get('reasoning_chunk') or chunk.get('snippet') or ''}"
                )
        lines.append("")
    return "\n".join(lines).strip()


def _source_rows(state: AdvisorState) -> list[list[Any]]:
    sources = (state.draft_output or {}).get("sources") or []
    rows: list[list[Any]] = []
    for index, source in enumerate(sources, start=1):
        rows.append(
            [
                index,
                ", ".join(source.get("used_by") or []),
                source.get("evidence_label") or f"E{index}",
                source.get("section") or "",
                source.get("snippet") or "",
            ]
        )
    return rows


def _public_reasoning_chunks(source_rows: list[list[Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for row in source_rows:
        chunks.append(
            {
                "rank": row[0],
                "used_by": row[1],
                "evidence": row[2],
                "section": row[3],
                "reasoning_chunk": row[4],
            }
        )
    return chunks


def _public_generation_status(raw_trace: dict[str, Any]) -> dict[str, Any]:
    generation = raw_trace.get("draft_output", {}).get("generation") or {}
    return {
        "status": generation.get("status"),
        "provider": generation.get("provider"),
        "model": generation.get("model"),
        "quality_issue": generation.get("quality_issue"),
    }


def _format_deployment(state: AdvisorState) -> str:
    projection = (state.draft_output or {}).get("projection") or {}
    pipeline_nodes = projection.get("pipeline_nodes") or []
    deployment_components = projection.get("deployment_components") or []
    projection_edges = projection.get("projection_edges") or []

    lines = ["## Diagram", "```mermaid", "flowchart LR"]
    if pipeline_nodes:
        lines.append("  subgraph pipeline[Pipeline]")
        for node in pipeline_nodes:
            node_id = str(node.get("id") or "").replace("-", "_")
            label = str(node.get("label") or node.get("id") or "")
            lines.append(f"    {node_id}[{label}]")
        lines.append("  end")
    if deployment_components:
        lines.append("  subgraph deployment[Deployment]")
        for component in deployment_components:
            component_id = str(component.get("id") or "").replace("-", "_")
            label = str(component.get("label") or component.get("id") or "")
            lines.append(f"    {component_id}[{label}]")
        lines.append("  end")
    for edge in projection_edges[:40]:
        source = str(edge.get("from") or "").replace("-", "_")
        target = str(edge.get("to") or "").replace("-", "_")
        lines.append(f"  {source} -.-> {target}")
    lines.extend(["```", "", "## Pipeline"])
    for node in pipeline_nodes:
        lines.append(f"{node.get('order')}. **{node.get('label')}** (`{node.get('id')}`)")

    lines.extend(["", "## Deployment Projection"])
    for component in deployment_components:
        serves = ", ".join(f"`{stage}`" for stage in component.get("serves") or [])
        controls = ", ".join(f"`{control}`" for control in component.get("controls") or [])
        lines.append(f"- **{component.get('label')}** ({component.get('pillar')})")
        lines.append(f"  Serves: {serves or 'none'}")
        lines.append(f"  Controls: {controls or 'none'}")

    if projection_edges:
        lines.extend(["", "## Projection Edges"])
        for edge in projection_edges[:24]:
            lines.append(f"- `{edge.get('from')}` -> `{edge.get('to')}`")
    return "\n".join(lines)


def _format_trace(state: AdvisorState) -> str:
    output = state.draft_output or {}
    topology = output.get("topology") or {}
    evidence_pack = output.get("evidence_pack") or {}
    decisions = output.get("architecture_decisions") or []
    panel = output.get("panel") or {}

    lines = [
        "## Advisor Reasoning Trace",
        "### 1. Interpreted the brief",
        f"- Domain prior: **{state.domain_prior or 'unknown'}**.",
    ]

    stated = [entry for entry in state.decision_log if entry.source == "stated"]
    strong = [
        entry
        for entry in state.decision_log
        if entry.source == "domain-prior" and entry.confidence >= 0.9
    ]
    if stated:
        lines.append("- User-stated signals:")
        for entry in stated:
            label = ATTRIBUTE_LABELS.get(entry.attr, entry.attr)
            lines.append(f"  - {label}: **{entry.value}**.")
    if strong:
        lines.append("- Strong prior signals:")
        for entry in strong[:6]:
            label = ATTRIBUTE_LABELS.get(entry.attr, entry.attr)
            lines.append(f"  - {label}: **{entry.value}**.")

    if state.pending_elicitation:
        pending_labels = [
            ATTRIBUTE_LABELS.get(attr, attr)
            for attr in state.pending_elicitation
        ]
        lines.append(
            "- Still uncertain: "
            + ", ".join(pending_labels)
            + ". The recommendation remains provisional until these are confirmed."
        )

    if state.hard_constraints:
        lines.extend(["", "### 2. Applied hard constraints"])
        for constraint in state.hard_constraints:
            lines.append(f"- {_readable_constraint(constraint)}")

    sources = evidence_pack.get("sources") or []
    if sources:
        lines.extend(["", "### 3. Read the literature chunks"])
        for index, source in enumerate(sources[:8], start=1):
            label = _source_label(source, index)
            used_by = ", ".join(source.get("used_by") or [])
            section = source.get("section") or "Unsectioned"
            snippet = source.get("snippet") or ""
            lines.append(f"- [{label}] {section}")
            if used_by:
                lines.append(f"  Used for: {used_by}")
            if snippet:
                lines.append(f"  Chunk reasoning: {snippet}")

    if topology:
        lines.extend(["", "### 4. Selected the topology"])
        lines.append(f"- Selected **{topology.get('name', 'pending')}**.")
        lines.append(f"- {_format_topology_rationale(state, topology)}")
        selection = topology.get("selection") or {}
        filters = selection.get("filters") or []
        readable_filters = _readable_topology_filters(topology)
        if filters and readable_filters:
            lines.append("- Filters applied:")
            for item in readable_filters:
                lines.append(f"  - {item}")

    if decisions:
        lines.extend(["", "### 5. Turned evidence into architecture decisions"])
        for decision in decisions:
            area = str(decision.get("area") or "decision").replace("_", " ").title()
            refs = _evidence_refs_text(decision.get("evidence_refs") or [])
            evidence = f" {refs}" if refs else ""
            lines.append(f"- **{area}:** {decision.get('choice', 'Pending')}{evidence}")
            if decision.get("rationale"):
                lines.append(f"  Why: {decision['rationale']}")
            if decision.get("tradeoff"):
                lines.append(f"  Tradeoff: {decision['tradeoff']}")

    panel_items = panel.get("items") or []
    if panel_items:
        lines.extend(["", "### 6. Checked user-facing tradeoffs"])
        for item in panel_items[:8]:
            refs = _evidence_refs_text(item.get("evidence_refs") or [])
            evidence = f" {refs}" if refs else ""
            lines.append(
                f"- **{item.get('label')}:** {item.get('accepted_tradeoff')}{evidence}"
            )

    if state.conflict:
        lines.extend(["", "### Unresolved conflict"])
        lines.append(state.conflict.rationale)
        for option in state.conflict.options:
            lines.append(f"- {option}")

    if state.critique:
        lines.extend(["", "### Critic check"])
        for item in state.critique:
            lines.append(f"- {item}")
    else:
        lines.extend(["", "### Critic check", "- No skeleton-level critique remained after synthesis."])
    return "\n".join(lines)


def _terraform(state: AdvisorState) -> str:
    return str((state.draft_output or {}).get("terraform") or "")


def _empty_detail_response(
    message: str,
) -> DetailResponse:
    return message, "", [], "", "", "", {}


def clear_detail_response() -> ClearDetailResponse:
    return "", "", [], "", "", "", "", {}


def advise(user_brief: str) -> tuple[str, dict[str, Any]]:
    if not user_brief.strip():
        return "Enter a brief to generate an initial advisor trace.", {}

    graph = build_graph()
    state = graph.invoke({"user_brief": user_brief})
    return _format_output(state), state.to_dict()


def advise_detailed(
    user_brief: str,
    elicitation_answers: str | None = None,
    conflict_resolution: str | None = None,
) -> DetailResponse:
    if not user_brief.strip():
        return _empty_detail_response("Enter a brief to generate an initial advisor trace.")

    graph = build_graph()
    state = graph.invoke(
        {
            "user_brief": user_brief,
            "elicitation_answers": _parse_elicitation_answers(elicitation_answers),
            "conflict_resolution": (conflict_resolution or "").strip() or None,
        }
    )
    return (
        _format_recommendation(state),
        _format_architecture_decisions(state),
        _source_rows(state),
        _format_deployment(state),
        _terraform(state),
        _format_trace(state),
        state.to_dict(),
    )


def advise_api(
    user_brief: str,
    elicitation_answers: str | None = None,
    conflict_resolution: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    (
        recommendation,
        architecture_decisions,
        source_rows,
        deployment_projection,
        terraform_sketch,
        advisor_reasoning_trace,
        raw_trace,
    ) = advise_detailed(user_brief, elicitation_answers, conflict_resolution)
    topology = raw_trace.get("draft_output", {}).get("topology") or {}
    return {
        "topology": topology.get("name"),
        "recommendation": recommendation,
        "architecture_decisions": architecture_decisions,
        "reasoning_chunks": _public_reasoning_chunks(source_rows),
        "deployment_projection": deployment_projection,
        "terraform_sketch": terraform_sketch,
        "advisor_reasoning_trace": advisor_reasoning_trace,
        "pending_questions": [
            ATTRIBUTE_LABELS.get(attr, attr)
            for attr in raw_trace.get("pending_elicitation", [])
        ],
        "generation": _public_generation_status(raw_trace),
        "runtime": {
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    }


def build_demo():
    if gr is None:
        raise RuntimeError("gradio is not installed. Install requirements.txt to run the app.")

    with gr.Blocks(title="RAG Architecture Advisor") as demo:
        show_raw_trace = _env_bool("SHOW_RAW_TRACE", False)
        gr.Markdown("# RAG Architecture Advisor")
        with gr.Row():
            brief = gr.Textbox(label="Brief", lines=8, placeholder="Describe the RAG use case...")
        with gr.Accordion("Follow-up answers", open=False):
            elicitation_answers = gr.Textbox(
                label="Elicitation answers",
                lines=4,
                placeholder='JSON like {"A7": "periodic"} or lines like A7=periodic',
            )
            conflict_resolution = gr.Textbox(
                label="Conflict resolution",
                lines=2,
                placeholder="Example: preserve_compliance",
            )
        with gr.Row():
            run = gr.Button("Advise", variant="primary")
            clear = gr.Button("Clear")
        gr.Examples(examples=EXAMPLE_BRIEFS, inputs=brief)

        with gr.Tabs():
            with gr.Tab("Recommendation"):
                recommendation = gr.Markdown(label="Recommendation")
            with gr.Tab("Architecture"):
                decisions = gr.Markdown(label="Architecture Decisions")
            with gr.Tab("Sources"):
                sources = gr.Dataframe(
                    headers=["#", "Used By", "Evidence", "Section", "Reasoning Chunk"],
                    datatype=["number", "str", "str", "str", "str"],
                    interactive=False,
                    label="Reasoning Chunks",
                )
            with gr.Tab("Deployment"):
                deployment = gr.Markdown(label="Deployment Projection")
            with gr.Tab("Terraform"):
                terraform = gr.Textbox(label="Terraform Sketch", lines=18)
            with gr.Tab("Trace"):
                trace = gr.Markdown(label="Advisor Reasoning Trace")
            if show_raw_trace:
                with gr.Tab("Raw JSON"):
                    raw_trace = gr.JSON(label="Raw Trace")
            else:
                raw_trace = gr.JSON(label="Raw Trace", visible=False)
        public_api_payload = gr.JSON(label="Public API Response", visible=False)
        public_api_trigger = gr.Button("Public API", visible=False)

        outputs = [recommendation, decisions, sources, deployment, terraform, trace, raw_trace]
        run.click(
            fn=advise_detailed,
            inputs=[brief, elicitation_answers, conflict_resolution],
            outputs=outputs,
            api_name="advise_detailed",
            api_visibility="private",
        )
        clear.click(
            fn=clear_detail_response,
            inputs=None,
            outputs=[brief, *outputs],
            api_name="clear_detail_response",
            api_visibility="private",
        )
        public_api_trigger.click(
            fn=advise_api,
            inputs=[brief, elicitation_answers, conflict_resolution],
            outputs=public_api_payload,
            api_name="advise",
            api_description="Return the public advisor response without raw graph internals.",
            api_visibility="public",
        )
    return demo


demo = build_demo() if gr else None


if __name__ == "__main__":
    if demo is None:
        sample = advise("Build an internal API docs assistant over fast-moving SDK docs.")
        print(sample[0])
        print(json.dumps(sample[1], indent=2))
    else:
        demo.launch(
            server_name=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
            server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
            share=os.getenv("GRADIO_SHARE", "false").lower() == "true",
            auth=_auth_credentials(),
        )
