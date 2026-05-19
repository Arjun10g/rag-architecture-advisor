from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CORPUS = ROOT / "corpus"
MANIFEST = CORPUS / "manifest.yaml"

FOLDER_DOMAINS = {
    "rag_reference_architectures_md": "reference-architectures",
    "rag_design_choices_report_02_md": "context-grounding-compression",
    "rag_security_governance_md": "security-governance",
    "chunking_parsing_md": "chunking-parsing",
    "iac_provisioning_ml_rag_md": "iac-provisioning",
    "vector_ops_freshness_md": "vector-ops-freshness",
    "matching_retrieval_reranking_cloud_mapping_md": "matching-retrieval-cloud",
    "neural_search_matching_pipelines_reranking_md": "neural-search-reranking",
    "cost_modeling_vector_rag_md_bundle": "cost-modeling",
    "chunking_parsing_rag_evaluation_lit_review_md": "rag-evaluation",
    "rag_context_grounding_compression_md_files": "context-grounding-compression",
}


VOLATILE_HINTS = (
    "pricing",
    "cost",
    "gpu",
    "model_selection",
    "vendor",
    "cloud_platform",
    "latency_cost",
)


def read_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return path.stem.replace("_", " ").replace("-", " ").title()


def namespace_for(path: Path) -> str:
    parts = path.relative_to(CORPUS).parts
    if parts[0] == "routing":
        return "routing"
    return "knowledge"


def content_kind_for(path: Path) -> str:
    parts = path.relative_to(CORPUS).parts
    if parts[0] == "routing":
        return "routing-card"
    if parts[0] == "report":
        return "implementation-spec"
    return "research-bundle"


def domain_for(path: Path) -> str:
    rel = path.relative_to(CORPUS)
    parts = rel.parts
    if parts[0] == "routing":
        return "routing"
    if parts[0] == "report":
        return "implementation"
    if len(parts) > 1:
        return FOLDER_DOMAINS.get(parts[1], parts[1])
    return "general"


def trust_tier_for(path: Path) -> str:
    if path.name.lower().startswith("readme"):
        return "reputable"
    if "source" in path.stem or "reference" in path.stem or "bibliography" in path.stem:
        return "primary"
    return "reputable"


def volatility_for(path: Path) -> str:
    stem = path.as_posix().lower()
    return "volatile" if any(hint in stem for hint in VOLATILE_HINTS) else "stable"


def should_ingest(path: Path) -> bool:
    name = path.name.upper()
    if name in {"FULL_REPORT.MD", "FULL_COMBINED_REPORT.MD"}:
        return False
    if path.name == "README.md" and path.parent == CORPUS:
        return False
    return True


def section_tags_for(path: Path) -> list[str]:
    tags = [domain_for(path), content_kind_for(path)]
    stem = path.stem.lower()
    for keyword in (
        "evaluation",
        "chunk",
        "rerank",
        "retrieval",
        "security",
        "terraform",
        "iac",
        "cost",
        "freshness",
        "grounding",
        "citation",
        "abstention",
        "router",
    ):
        if keyword in stem or keyword in path.as_posix().lower():
            tags.append(keyword)
    return sorted(set(tags))


def build_manifest() -> dict:
    docs = []
    for path in sorted(CORPUS.rglob("*.md")):
        rel = path.relative_to(ROOT).as_posix()
        ingest = should_ingest(path)
        docs.append(
            {
                "path": rel,
                "title": read_title(path),
                "namespace": namespace_for(path),
                "content_kind": content_kind_for(path),
                "domain": domain_for(path),
                "license": "project-curated-open-research-notes",
                "trust_tier": trust_tier_for(path),
                "volatility": volatility_for(path),
                "contested": "consensus",
                "section_tags": section_tags_for(path),
                "source_url": None,
                "date": "2026-05-19",
                "ingest": ingest,
                "notes": "Excluded duplicate combined report." if not ingest else "",
            }
        )
    return {"version": "corpus_2026_05_19_v1", "documents": docs}


if __name__ == "__main__":
    manifest = build_manifest()
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    ingest_count = sum(1 for doc in manifest["documents"] if doc["ingest"])
    print(f"Wrote {MANIFEST.relative_to(ROOT)}")
    print(f"Documents: {len(manifest['documents'])}; ingest: {ingest_count}")
