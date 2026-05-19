from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class ManifestValidation:
    ok: bool
    errors: list[str]
    data: dict


def load_manifest(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {"documents": []}
    text = path.read_text(encoding="utf-8")
    if text.strip().startswith(("{", "[")):
        return json.loads(text)
    if yaml is None:
        if text.strip() in {"", "documents: []"}:
            return {"documents": []}
        raise RuntimeError("pyyaml is required to parse non-empty corpus manifests.")
    return yaml.safe_load(text) or {"documents": []}


def validate_manifest(path: str | Path) -> ManifestValidation:
    data = load_manifest(path)
    errors: list[str] = []
    seen_paths: set[str] = set()
    for idx, doc in enumerate(data.get("documents", []), start=1):
        doc_path = doc.get("path")
        if not doc_path:
            errors.append(f"documents[{idx}] is missing path")
        elif doc_path in seen_paths:
            errors.append(f"documents[{idx}] duplicates path {doc_path}")
        else:
            seen_paths.add(doc_path)
        if not doc.get("license"):
            errors.append(f"documents[{idx}] is missing license")
        if not doc.get("trust_tier"):
            errors.append(f"documents[{idx}] is missing trust_tier")
        if not doc.get("namespace"):
            errors.append(f"documents[{idx}] is missing namespace")
    return ManifestValidation(ok=not errors, errors=errors, data=data)


def manifest_by_path(path: str | Path) -> dict[str, dict]:
    data = load_manifest(path)
    return {doc["path"]: doc for doc in data.get("documents", []) if doc.get("path")}
