from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.build_index import build_index
from ingestion.manifest import validate_manifest


def main() -> None:
    validation = validate_manifest("corpus/manifest.yaml")
    if not validation.ok:
        raise SystemExit("; ".join(validation.errors))

    index = build_index()
    namespace_counts = index.namespace_counts()
    element_counts = index.element_counts()

    if namespace_counts.get("routing", 0) < 7:
        raise SystemExit(f"routing namespace too small: {namespace_counts}")
    if namespace_counts.get("knowledge", 0) < 100:
        raise SystemExit(f"knowledge namespace too small: {namespace_counts}")
    if element_counts.get("table", 0) == 0:
        raise SystemExit(f"no table chunks found: {element_counts}")
    if element_counts.get("code_fence", 0) == 0:
        raise SystemExit(f"no fenced code chunks found: {element_counts}")

    print(f"manifest_docs={len(validation.data['documents'])}")
    print(f"chunks={index.count()}")
    print(f"namespaces={namespace_counts}")
    print(f"elements={element_counts}")
    print(f"domains={index.domain_counts()}")


if __name__ == "__main__":
    main()
