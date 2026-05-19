from __future__ import annotations

from dataclasses import dataclass
import math
import re

from retrieval.chunking import Chunk


@dataclass
class SearchResult:
    chunk: Chunk
    score: float


class HybridRetriever:
    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks or []
        self._doc_freq = self._build_doc_freq(self.chunks)

    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        terms = _tokens(query)
        filters = filters or {}
        scored: list[SearchResult] = []
        for chunk in self.chunks:
            if namespace and chunk.metadata.get("namespace") != namespace:
                continue
            if any(str(chunk.metadata.get(key)) != str(value) for key, value in filters.items()):
                continue

            score = self._score_chunk(terms, chunk)
            if score > 0:
                scored.append(SearchResult(chunk=chunk, score=score))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    def _score_chunk(self, query_terms: list[str], chunk: Chunk) -> float:
        text = chunk.text_for_embedding.lower()
        chunk_terms = _tokens(text)
        if not query_terms or not chunk_terms:
            return 0.0

        term_counts: dict[str, int] = {}
        for term in chunk_terms:
            term_counts[term] = term_counts.get(term, 0) + 1

        score = 0.0
        total_docs = max(len(self.chunks), 1)
        for term in query_terms:
            tf = term_counts.get(term, 0)
            if not tf:
                continue
            idf = math.log((1 + total_docs) / (1 + self._doc_freq.get(term, 0))) + 1.0
            score += (1.0 + math.log(tf)) * idf

        section = " ".join(chunk.metadata.get("section_path") or []).lower()
        tags = " ".join(chunk.metadata.get("section_tags") or []).lower()
        for term in query_terms:
            if term in section:
                score += 1.5
            if term in tags:
                score += 1.0
        return score

    @staticmethod
    def _build_doc_freq(chunks: list[Chunk]) -> dict[str, int]:
        doc_freq: dict[str, int] = {}
        for chunk in chunks:
            for term in set(_tokens(chunk.text_for_embedding)):
                doc_freq[term] = doc_freq.get(term, 0) + 1
        return doc_freq


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_./-]*", text.lower())
