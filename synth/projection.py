from __future__ import annotations


def project_deployment(topology: dict) -> dict:
    stages = ["parse_chunk", "embed", "vector_search", "rerank", "generate"]
    if "hybrid" in topology.get("key", ""):
        stages.insert(3, "bm25")
    if topology.get("key") == "adaptive_agentic":
        stages.insert(0, "query_planner")

    return {
        "pipeline_stages": stages,
        "deployment_components": [
            {"id": "compute", "pillar": "Compute", "serves": ["embed", "rerank", "generate"]},
            {"id": "networking", "pillar": "Networking", "serves": stages},
            {"id": "storage", "pillar": "Storage", "serves": ["bm25", "parse_chunk"]},
            {"id": "database", "pillar": "Databases", "serves": ["vector_search"]},
            {"id": "security", "pillar": "Security", "serves": stages},
            {"id": "monitoring", "pillar": "Monitoring", "serves": stages},
            {"id": "scalability", "pillar": "Scalability", "serves": stages},
        ],
    }

