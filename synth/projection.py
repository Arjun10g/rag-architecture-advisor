from __future__ import annotations


STAGE_LABELS = {
    "query_planner": "Query planner",
    "parse_chunk": "Parse and chunk",
    "embed": "Embedding service",
    "vector_search": "Vector search",
    "bm25": "Lexical index",
    "rerank": "Reranker",
    "generate": "Generator",
    "review_gate": "Human review gate",
}


COMPONENT_CATALOG = {
    "compute": {
        "label": "Inference and orchestration services",
        "pillar": "Compute",
        "resource_kind": "model_endpoint",
        "controls": ("batching", "request_timeout", "model_version_pin"),
    },
    "networking": {
        "label": "Private networking and egress",
        "pillar": "Networking",
        "resource_kind": "network_boundary",
        "controls": ("private_endpoint", "egress_allowlist", "service_to_service_auth"),
    },
    "storage": {
        "label": "Corpus, lexical, and artifact storage",
        "pillar": "Storage",
        "resource_kind": "object_store_and_lexical_index",
        "controls": ("versioned_buckets", "lifecycle_policy", "index_artifact_manifest"),
    },
    "database": {
        "label": "Vector database and metadata filters",
        "pillar": "Databases",
        "resource_kind": "vector_database",
        "controls": ("metadata_filtering", "blue_green_alias", "backup_policy"),
    },
    "security": {
        "label": "IAM, KMS, RBAC, and policy gates",
        "pillar": "Security",
        "resource_kind": "identity_and_key_management",
        "controls": ("least_privilege_iam", "kms_encryption", "acl_aware_retrieval"),
    },
    "monitoring": {
        "label": "Metrics, tracing, and audit lineage",
        "pillar": "Monitoring",
        "resource_kind": "observability",
        "controls": ("p50_p95_p99_latency", "retrieval_quality_metrics", "audit_lineage"),
    },
    "scalability": {
        "label": "Autoscaling and rollout controls",
        "pillar": "Scalability",
        "resource_kind": "autoscaling_policy",
        "controls": ("queue_depth_scaling", "canary_rollout", "capacity_budget"),
    },
}


STAGE_COMPONENT_MAP = {
    "query_planner": ("compute", "networking", "security", "monitoring", "scalability"),
    "parse_chunk": ("storage", "networking", "security", "monitoring"),
    "embed": ("compute", "networking", "security", "monitoring", "scalability"),
    "vector_search": ("database", "networking", "security", "monitoring", "scalability"),
    "bm25": ("storage", "networking", "security", "monitoring", "scalability"),
    "rerank": ("compute", "networking", "security", "monitoring", "scalability"),
    "generate": ("compute", "networking", "security", "monitoring", "scalability"),
    "review_gate": ("storage", "database", "security", "monitoring"),
}


def _pipeline_nodes(stages: list[str]) -> list[dict]:
    return [
        {
            "id": stage,
            "label": STAGE_LABELS.get(stage, stage.replace("_", " ").title()),
            "order": index,
        }
        for index, stage in enumerate(stages, start=1)
    ]


def _component_ids() -> list[str]:
    return list(COMPONENT_CATALOG)


def _served(stages: list[str], component_id: str) -> list[str]:
    return [
        stage
        for stage in stages
        if component_id in STAGE_COMPONENT_MAP.get(stage, ())
    ]


def _component_controls(component_id: str, topology: dict) -> list[str]:
    controls = list(COMPONENT_CATALOG[component_id]["controls"])
    requirements = topology.get("requirements", {})
    if requirements.get("lexical_required") and component_id == "storage":
        controls.append("lexical_index_required")
    if requirements.get("review_gate_required") and component_id in {
        "database",
        "security",
        "storage",
    }:
        controls.append("review_queue_required")
    if requirements.get("audit_log_required") and component_id in {"monitoring", "security", "storage"}:
        controls.append("audit_log_required")
    return controls


def _component_record(component_id: str, stages: list[str], topology: dict) -> dict:
    catalog_entry = COMPONENT_CATALOG[component_id]
    return {
        "id": component_id,
        "label": catalog_entry["label"],
        "pillar": catalog_entry["pillar"],
        "resource_kind": catalog_entry["resource_kind"],
        "serves": _served(stages, component_id),
        "controls": _component_controls(component_id, topology),
    }


def _projection_edges(stages: list[str]) -> list[dict]:
    edges = []
    for stage in stages:
        for component_id in STAGE_COMPONENT_MAP.get(stage, ()):
            edges.append({"from": stage, "to": component_id, "kind": "serves"})
    return edges


def project_deployment(topology: dict) -> dict:
    stages = list(topology.get("stages") or ["parse_chunk", "embed", "vector_search", "generate"])
    if topology.get("requirements", {}).get("review_gate_required"):
        stages.append("review_gate")

    deployment_components = [
        _component_record(component_id, stages, topology)
        for component_id in _component_ids()
    ]
    return {
        "pipeline_stages": stages,
        "pipeline_nodes": _pipeline_nodes(stages),
        "deployment_components": deployment_components,
        "projection_edges": _projection_edges(stages),
    }
