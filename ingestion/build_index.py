from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.manifest import manifest_by_path, validate_manifest
from retrieval.chunking import chunk_markdown_file
from retrieval.store import FileChunkStore


def build_index(corpus_dir: str = "corpus", manifest_path: str = "corpus/manifest.yaml") -> FileChunkStore:
    validation = validate_manifest(manifest_path)
    if not validation.ok:
        raise ValueError("; ".join(validation.errors))

    store = FileChunkStore(".cache/index")
    manifest = manifest_by_path(manifest_path)
    for relative_path, entry in sorted(manifest.items()):
        if entry.get("ingest") is False:
            continue
        path = Path(relative_path)
        if not path.exists():
            raise FileNotFoundError(relative_path)
        store.add(chunk_markdown_file(path, metadata=entry))
    return store


if __name__ == "__main__":
    index = build_index()
    print(f"Indexed {index.count()} chunks")
    print(f"Namespaces: {index.namespace_counts()}")
    print(f"Elements: {index.element_counts()}")
