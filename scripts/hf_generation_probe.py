from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience.
    load_dotenv = None

from agents.synthesizer import _answer_quality_issue
from graph.build import build_graph


DEFAULT_BRIEF = (
    "Build an internal API docs assistant over fast-moving SDK docs with strict "
    "citations, mixed markdown and code, and high exact-match terminology needs."
)

EVIDENCE_REF_RE = re.compile(r"\[E\d+\]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe the configured HF generation path without printing secrets."
    )
    parser.add_argument("--brief", default=DEFAULT_BRIEF, help="Brief to send through the graph.")
    parser.add_argument(
        "--allow-unavailable",
        action="store_true",
        help="Exit zero when provider access is unavailable and deterministic fallback is used.",
    )
    parser.add_argument(
        "--allow-guarded",
        action="store_true",
        help="Exit zero when the model output is rejected by the generation guard.",
    )
    args = parser.parse_args()

    if load_dotenv:
        load_dotenv()
    os.environ.setdefault("LLM_PROVIDER", "hf")

    state = build_graph().invoke({"user_brief": args.brief})
    output = state.draft_output or {}
    generation = output.get("generation") or {}
    answer = str(output.get("generated_answer") or "")
    quality_issue = _answer_quality_issue(answer)
    evidence_refs = sorted(set(EVIDENCE_REF_RE.findall(answer)))

    result = {
        "status": generation.get("status"),
        "provider": generation.get("provider"),
        "model": generation.get("model"),
        "reason": generation.get("reason"),
        "topology": (output.get("topology") or {}).get("name"),
        "evidence_refs": evidence_refs[:8],
        "answer_chars": len(answer),
        "quality_issue": quality_issue,
        "answer_preview": "\n".join(answer.splitlines()[:12]),
    }
    print(json.dumps(result, indent=2, sort_keys=True))

    if quality_issue:
        raise SystemExit(f"Displayed answer failed quality guard: {quality_issue}")
    if generation.get("status") == "fallback" and not args.allow_unavailable:
        raise SystemExit("HF provider unavailable; rerun with --allow-unavailable to accept fallback.")
    if generation.get("status") == "guarded_fallback" and not args.allow_guarded:
        raise SystemExit("HF output was rejected by the guard; rerun with --allow-guarded to accept this.")


if __name__ == "__main__":
    main()
