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


def _format_output(state: AdvisorState) -> str:
    output = state.draft_output or {}
    topology = output.get("topology", {})
    panel = output.get("panel", {})
    terraform = output.get("terraform", "")
    sources = output.get("sources") or []

    lines = [
        "## Recommendation",
        f"**Topology:** {topology.get('name', 'pending')}",
        "",
        "## Why",
    ]
    for entry in state.decision_log[:8]:
        lines.append(f"- {entry.attr}: {entry.value} ({entry.source})")

    lines.extend(["", "## Strengths"])
    for item in panel.get("strengths", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Weaknesses"])
    for item in panel.get("weaknesses", []):
        lines.append(f"- {item}")

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


def advise(user_brief: str) -> tuple[str, dict[str, Any]]:
    if not user_brief.strip():
        return "Enter a brief to generate an initial advisor trace.", {}

    graph = build_graph()
    state = graph.invoke({"user_brief": user_brief})
    return _format_output(state), state.to_dict()


def build_demo():
    if gr is None:
        raise RuntimeError("gradio is not installed. Install requirements.txt to run the app.")

    with gr.Blocks(title="RAG Architecture Advisor") as demo:
        gr.Markdown("# RAG Architecture Advisor")
        brief = gr.Textbox(label="Brief", lines=8, placeholder="Describe the RAG use case...")
        run = gr.Button("Advise", variant="primary")
        output = gr.Markdown(label="Output")
        trace = gr.JSON(label="Decision Trace")
        run.click(fn=advise, inputs=brief, outputs=[output, trace])
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
