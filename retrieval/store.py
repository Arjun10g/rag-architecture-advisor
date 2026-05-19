from __future__ import annotations

from pathlib import Path
from collections import Counter

from retrieval.chunking import Chunk


class FileChunkStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.chunks: list[Chunk] = []

    def add(self, chunks: list[Chunk]) -> None:
        self.chunks.extend(chunks)

    def count(self) -> int:
        return len(self.chunks)

    def counts_by(self, metadata_key: str) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for chunk in self.chunks:
            value = chunk.metadata.get(metadata_key)
            counter[str(value or "unknown")] += 1
        return dict(sorted(counter.items()))

    def namespace_counts(self) -> dict[str, int]:
        return self.counts_by("namespace")

    def element_counts(self) -> dict[str, int]:
        return self.counts_by("element_type")

    def domain_counts(self) -> dict[str, int]:
        return self.counts_by("domain")
