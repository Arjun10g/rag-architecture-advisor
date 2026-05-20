from __future__ import annotations


def _served(stages: list[str], supported: set[str]) -> list[str]:
    return [stage for stage in stages if stage in supported]


def project_deployment(topology: dict) -> dict:
    stages = list(topology.get("stages") or ["parse_chunk", "embed", "vector_search", "generate"])
    if topology.get("requirements", {}).get("review_gate_required"):
        stages.append("review_gate")

    return {
        "pipeline_stages": stages,
        "deployment_components": [
            {
                "id": "compute",
                "pillar": "Compute",
                "serves": _served(stages, {"embed", "rerank", "generate", "query_planner"}),
            },
            {"id": "networking", "pillar": "Networking", "serves": stages},
            {
                "id": "storage",
                "pillar": "Storage",
                "serves": _served(stages, {"bm25", "parse_chunk", "review_gate"}),
            },
            {
                "id": "database",
                "pillar": "Databases",
                "serves": _served(stages, {"vector_search", "review_gate"}),
            },
            {"id": "security", "pillar": "Security", "serves": stages},
            {"id": "monitoring", "pillar": "Monitoring", "serves": stages},
            {"id": "scalability", "pillar": "Scalability", "serves": stages},
        ],
    }
