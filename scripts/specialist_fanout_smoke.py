from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.specialists import run_specialists
from graph.edges import SPECIALIST_NAMES
from graph.state import AdvisorState
from retrieval.chunking import Chunk
from retrieval.index import SearchResult


def fake_retrieve(
    query: str,
    namespace: str,
    top_k: int,
    filters: dict[str, str] | None,
) -> list[SearchResult]:
    if "permission aware" in query:
        raise RuntimeError("simulated security retrieval outage")

    chunk = Chunk(
        text_original=f"Evidence for {query}",
        text_for_embedding=f"Evidence for {query}",
        source_path="corpus/curated/smoke.md",
        chunk_index=0,
        title="Smoke",
        section_path=["Smoke", query.split()[-1]],
        element_type="prose",
        metadata={"namespace": namespace, "domain": "smoke"},
    )
    return [SearchResult(chunk=chunk, score=1.0)]


def main() -> None:
    state = AdvisorState(
        user_brief="Build an internal API docs assistant.",
        pending_elicitation=["A4"],
    )
    findings = run_specialists(state, retrieve_fn=fake_retrieve)

    if tuple(findings) != SPECIALIST_NAMES:
        raise AssertionError(f"specialist order changed: {tuple(findings)}")
    if findings["security"].sources:
        raise AssertionError("failed specialist should not fabricate sources")
    if not any("retrieval failed" in item for item in findings["security"].open_questions):
        raise AssertionError("failed specialist did not expose an explicit gap")
    for name in ("retrieval", "cloud_iac", "evaluation"):
        if not findings[name].sources:
            raise AssertionError(f"{name} specialist returned no sources")

    print(f"specialist_fanout_smoke=ok agents={len(findings)}")


if __name__ == "__main__":
    main()
