from __future__ import annotations

import json
import os
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
        lines.append(f"- {entry.attr}: {entry.value} ({entry.source})")

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
            source_ids = decision.get("source_ids") or []
            lines.append(f"- **{area}:** {choice}")
            if decision.get("rationale"):
                lines.append(f"  {decision['rationale']}")
            if source_ids:
                citations = " ".join(f"`{source_id}`" for source_id in source_ids[:3])
                lines.append(f"  Sources: {citations}")

    if terraform:
        lines.extend(["", "## Terraform Sketch", "```hcl", terraform.strip(), "```"])

    if sources:
        lines.extend(["", "## Sources"])
        for index, source in enumerate(sources[:8], start=1):
            title = source.get("title") or "Untitled source"
            section = source.get("section") or "Unsectioned"
            source_id = source.get("source_id") or "unknown"
            used_by = ", ".join(source.get("used_by") or [])
            label = section if section.startswith(title) else f"{title} - {section}"
            lines.append(f"- [{index}] {label} (`{source_id}`)")
            if used_by:
                lines.append(f"  Used by: {used_by}")

    return "\n".join(lines)


def _format_recommendation(state: AdvisorState) -> str:
    output = state.draft_output or {}
    topology = output.get("topology", {})
    panel = output.get("panel", {})
    generated_answer = output.get("generated_answer")
    lines = [
        f"## {topology.get('name', 'Pending')}",
        topology.get("rationale", ""),
    ]

    if generated_answer:
        lines.extend(["", str(generated_answer).strip()])

    lines.extend([
        "",
        "### Requirement Vector",
    ])
    for entry in state.decision_log[:12]:
        confidence = f"{entry.confidence:.2f}"
        lines.append(f"- **{entry.attr}:** {entry.value} ({entry.source}, confidence {confidence})")

    if state.pending_elicitation:
        lines.extend(["", "### Pending Elicitation"])
        for attr in state.pending_elicitation:
            lines.append(f"- {attr}")

    lines.extend(["", "### Strengths"])
    for item in panel.get("strengths", []):
        lines.append(f"- {item}")

    lines.extend(["", "### Weaknesses"])
    for item in panel.get("weaknesses", []):
        lines.append(f"- {item}")

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
            lines.extend(["", str(decision["rationale"])])
        source_ids = decision.get("source_ids") or []
        if source_ids:
            lines.extend(["", "**Sources:** " + " ".join(f"`{source_id}`" for source_id in source_ids)])
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
                source.get("title") or "",
                source.get("section") or "",
                source.get("source_id") or "",
                source.get("source_path") or "",
            ]
        )
    return rows


def _format_deployment(state: AdvisorState) -> str:
    projection = (state.draft_output or {}).get("projection") or {}
    pipeline_nodes = projection.get("pipeline_nodes") or []
    deployment_components = projection.get("deployment_components") or []
    projection_edges = projection.get("projection_edges") or []

    lines = ["## Pipeline"]
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
    lines = ["## Decision Trace"]
    for entry in state.decision_log:
        confidence = f"{entry.confidence:.2f}"
        lines.append(f"- **{entry.attr}:** {entry.value} ({entry.source}, confidence {confidence})")
        lines.append(f"  {entry.reason}")

    if state.hard_constraints:
        lines.extend(["", "## Hard Constraints"])
        for constraint in state.hard_constraints:
            lines.append(f"- {constraint}")

    if state.conflict:
        lines.extend(["", "## Conflict"])
        lines.append(state.conflict.rationale)
        for option in state.conflict.options:
            lines.append(f"- {option}")

    if state.critique:
        lines.extend(["", "## Critique"])
        for item in state.critique:
            lines.append(f"- {item}")

    if state.graph_trace:
        lines.extend(["", "## Graph Trace"])
        for item in state.graph_trace:
            lines.append(f"- {item}")
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
) -> DetailResponse:
    if not user_brief.strip():
        return _empty_detail_response("Enter a brief to generate an initial advisor trace.")

    graph = build_graph()
    state = graph.invoke({"user_brief": user_brief})
    return (
        _format_recommendation(state),
        _format_architecture_decisions(state),
        _source_rows(state),
        _format_deployment(state),
        _terraform(state),
        _format_trace(state),
        state.to_dict(),
    )


def build_demo():
    if gr is None:
        raise RuntimeError("gradio is not installed. Install requirements.txt to run the app.")

    with gr.Blocks(title="RAG Architecture Advisor") as demo:
        gr.Markdown("# RAG Architecture Advisor")
        with gr.Row():
            brief = gr.Textbox(label="Brief", lines=8, placeholder="Describe the RAG use case...")
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
                    headers=["#", "Used By", "Title", "Section", "Source ID", "Path"],
                    datatype=["number", "str", "str", "str", "str", "str"],
                    interactive=False,
                    label="Sources",
                )
            with gr.Tab("Deployment"):
                deployment = gr.Markdown(label="Deployment Projection")
            with gr.Tab("Terraform"):
                terraform = gr.Textbox(label="Terraform Sketch", lines=18)
            with gr.Tab("Trace"):
                trace = gr.Markdown(label="Decision Trace")
            with gr.Tab("Raw JSON"):
                raw_trace = gr.JSON(label="Raw Trace")

        outputs = [recommendation, decisions, sources, deployment, terraform, trace, raw_trace]
        run.click(fn=advise_detailed, inputs=brief, outputs=outputs)
        clear.click(fn=clear_detail_response, inputs=None, outputs=[brief, *outputs])
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
        )
