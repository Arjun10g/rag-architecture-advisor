from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from retrieval.service import retrieve


def main() -> None:
    knowledge = retrieve("hybrid retrieval reranker production default", namespace="knowledge", top_k=5)
    routing = retrieve("A2 exact-match terminology dependence", namespace="routing", top_k=5)

    if not knowledge:
        raise SystemExit("knowledge retrieval returned no results")
    if not routing:
        raise SystemExit("routing retrieval returned no results")
    if any(result.chunk.metadata.get("namespace") != "knowledge" for result in knowledge):
        raise SystemExit("knowledge search leaked non-knowledge chunks")
    if any(result.chunk.metadata.get("namespace") != "routing" for result in routing):
        raise SystemExit("routing search leaked non-routing chunks")

    print("knowledge_top=" + knowledge[0].chunk.chunk_id)
    print("knowledge_section=" + " > ".join(knowledge[0].chunk.metadata["section_path"]))
    print("routing_top=" + routing[0].chunk.chunk_id)
    print("routing_section=" + " > ".join(routing[0].chunk.metadata["section_path"]))


if __name__ == "__main__":
    main()
