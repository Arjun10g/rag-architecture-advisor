from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

os.environ["LLM_PROVIDER"] = "disabled"
os.environ["PREWARM_RETRIEVER"] = "false"
os.environ["RETRIEVAL_MODE"] = "lexical"
os.environ["VECTOR_STORE_BACKEND"] = "memory"

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from graph.build import build_graph


def main() -> None:
    out = Path(tempfile.mkdtemp(prefix="rag-audit-")) / "advisor-audit.jsonl"
    previous_audit = os.environ.get("ADVISOR_AUDIT_LOG_PATH")
    previous_provider = os.environ.get("LLM_PROVIDER")
    os.environ["ADVISOR_AUDIT_LOG_PATH"] = str(out)
    os.environ["LLM_PROVIDER"] = "disabled"
    try:
        state = build_graph().invoke({"user_brief": "Build an internal API docs assistant."})
    finally:
        if previous_audit is None:
            os.environ.pop("ADVISOR_AUDIT_LOG_PATH", None)
        else:
            os.environ["ADVISOR_AUDIT_LOG_PATH"] = previous_audit
        if previous_provider is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = previous_provider

    if not out.exists():
        raise AssertionError("audit log was not written")
    record = json.loads(out.read_text(encoding="utf-8").strip().splitlines()[-1])
    if record["event"] != "advisor_synthesis":
        raise AssertionError("audit event name changed")
    if record["topology_key"] != (state.draft_output or {}).get("topology", {}).get("key"):
        raise AssertionError("audit topology does not match draft output")
    if not record.get("source_ids"):
        raise AssertionError("audit record should include source IDs")

    print(f"audit_log_smoke=ok path={out}")


if __name__ == "__main__":
    main()
