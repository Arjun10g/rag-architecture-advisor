from __future__ import annotations

from dataclasses import dataclass
import math
import re

from retrieval.chunking import Chunk


@dataclass
class SearchResult:
    chunk: Chunk
    score: float


@dataclass
class QueryFeatures:
    raw: str
    terms: list[str]
    important_terms: list[str]
    phrases: list[str]


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "over",
    "should",
    "so",
    "the",
    "to",
    "what",
    "where",
    "which",
    "with",
}


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    k: int = 60,
    weights: list[float] | None = None,
) -> list[tuple[str, float]]:
    weights = weights or [1.0] * len(rankings)
    scores: dict[str, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def _bm25_weight(tf: int, idf: float, doc_len: int, avg_doc_len: float) -> float:
    k1 = 1.4
    b = 0.75
    length_norm = 1 - b + b * (doc_len / max(avg_doc_len, 1.0))
    return idf * ((tf * (k1 + 1)) / (tf + k1 * length_norm))


def _query_features(query: str) -> QueryFeatures:
    terms = _tokens(query)
    important_terms = [term for term in terms if term not in STOPWORDS and len(term) > 1]
    return QueryFeatures(
        raw=query,
        terms=terms,
        important_terms=important_terms,
        phrases=_phrases(important_terms),
    )


def _phrases(terms: list[str]) -> list[str]:
    phrases: list[str] = []
    max_window = min(5, len(terms))
    for window in range(max_window, 1, -1):
        for start in range(0, len(terms) - window + 1):
            phrase = " ".join(terms[start : start + window])
            if phrase not in phrases:
                phrases.append(phrase)
    return phrases


def _field_token_boost(terms: list[str], field: str, weight: float) -> float:
    field_terms = set(_tokens(field))
    return weight * sum(1 for term in terms if term in field_terms)


def _field_coverage_boost(terms: list[str], field: str, weight: float) -> float:
    if not terms:
        return 0.0
    field_terms = set(_tokens(field))
    coverage = sum(1 for term in set(terms) if term in field_terms) / len(set(terms))
    return weight * coverage * coverage


def _phrase_boost(phrases: list[str], field: str, weight: float) -> float:
    if not phrases:
        return 0.0
    normalized = _normalize_phrase_field(field)
    score = 0.0
    for phrase in phrases:
        if phrase in normalized:
            score += weight * (phrase.count(" ") + 1)
    return score


def _ordered_query_boost(terms: list[str], field: str, weight: float) -> float:
    field_terms = _tokens(field)
    if len(terms) < 2 or not field_terms:
        return 0.0
    cursor = 0
    matched = 0
    for term in terms:
        try:
            offset = field_terms[cursor:].index(term)
        except ValueError:
            continue
        cursor += offset + 1
        matched += 1
    if matched < 2:
        return 0.0
    return weight * (matched / len(set(terms)))


def _looks_like_source_query(query: QueryFeatures) -> bool:
    source_terms = {"bibliography", "citation", "citations", "reference", "references", "source", "sources"}
    return any(term in source_terms for term in query.terms)


def _heading_intent_boost(query: QueryFeatures, leaf_section: str, section: str) -> float:
    section_text = _normalize_phrase_field(section)
    leaf_text = _normalize_phrase_field(leaf_section)
    terms = set(query.terms)
    boost = 0.0

    if "when" in terms and ("use" in terms or "right" in terms) and "when to use" in section_text:
        boost += 80.0
    if {"module", "terraform"} <= terms and "module set" in leaf_text:
        boost += 55.0
    if "fanout" in terms and "fanout" in leaf_text:
        boost += 55.0
    decision_terms = {"choose", "decision", "select", "selection", "strategy"}
    if terms & decision_terms and {"decision", "rule"} <= set(_tokens(section_text)):
        boost += 55.0
    if terms & {"choose", "strategy"} and (
        "selection framework" in section_text or "decision matrix" in section_text
    ):
        boost += 45.0
    if terms & {"matrix", "route", "routing"} and "routing matrix" in section_text:
        boost += 65.0
    if "default" in terms and "default" in leaf_text:
        boost += 35.0

    return boost


def _normalize_phrase_field(value: str) -> str:
    return " ".join(_tokens(value))


def _normalize_token(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str) -> list[str]:
    normalized = text.lower().replace("_", " ").replace("-", " ").replace("/", " ")
    return [_normalize_token(token) for token in re.findall(r"[a-z0-9][a-z0-9.]*", normalized)]


class HybridRetriever:
    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks or []
        self._doc_freq = self._build_doc_freq(self.chunks)
        self._avg_doc_len = self._average_doc_length(self.chunks)

    def search(
        self,
        query: str,
        top_k: int = 8,
        namespace: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        query_features = _query_features(query)
        filters = filters or {}
        scored: list[SearchResult] = []
        for chunk in self.chunks:
            if namespace and chunk.metadata.get("namespace") != namespace:
                continue
            if any(str(chunk.metadata.get(key)) != str(value) for key, value in filters.items()):
                continue

            score = self._score_chunk(query_features, chunk)
            if score > 0:
                scored.append(SearchResult(chunk=chunk, score=score))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    def _score_chunk(self, query: QueryFeatures, chunk: Chunk) -> float:
        text = chunk.text_for_embedding.lower()
        chunk_terms = _tokens(text)
        if not query.terms or not chunk_terms:
            return 0.0

        term_counts: dict[str, int] = {}
        for term in chunk_terms:
            term_counts[term] = term_counts.get(term, 0) + 1

        score = 0.0
        total_docs = max(len(self.chunks), 1)
        doc_len = len(chunk_terms)
        for term in query.terms:
            tf = term_counts.get(term, 0)
            if not tf:
                continue
            idf = math.log((1 + total_docs) / (1 + self._doc_freq.get(term, 0))) + 1.0
            score += _bm25_weight(tf=tf, idf=idf, doc_len=doc_len, avg_doc_len=self._avg_doc_len)

        section_parts = [str(part) for part in chunk.metadata.get("section_path") or []]
        section = " ".join(section_parts).lower()
        leaf_section = section_parts[-1].lower() if section_parts else ""
        source_path = str(chunk.metadata.get("source_path") or chunk.source_path).lower()
        title = chunk.title.lower()
        tags = " ".join(chunk.metadata.get("section_tags") or []).lower()
        domain = str(chunk.metadata.get("domain") or "").lower()
        compact_metadata = " ".join([title, section, tags, domain, source_path.replace("_", " ")])
        full_text = f"{compact_metadata}\n{text}"

        score += _field_token_boost(query.important_terms, leaf_section, weight=4.0)
        score += _field_token_boost(query.important_terms, section, weight=2.8)
        score += _field_token_boost(query.important_terms, title, weight=1.6)
        score += _field_token_boost(query.important_terms, tags, weight=1.1)
        score += _field_token_boost(query.important_terms, domain.replace("-", " "), weight=0.9)
        score += _field_token_boost(query.important_terms, source_path.replace("_", " "), weight=0.4)
        score += _field_coverage_boost(query.important_terms, leaf_section, weight=9.0)
        score += _field_coverage_boost(query.important_terms, section, weight=7.0)
        score += _field_coverage_boost(query.important_terms, compact_metadata, weight=3.0)
        score += _phrase_boost(query.phrases, leaf_section, weight=16.0)
        score += _phrase_boost(query.phrases, section, weight=12.0)
        score += _phrase_boost(query.phrases, title, weight=6.0)
        score += _phrase_boost(query.phrases, full_text, weight=2.0)
        score += _ordered_query_boost(query.important_terms, section, weight=6.0)
        score += _heading_intent_boost(query, leaf_section, section)

        element_type = str(chunk.metadata.get("element_type") or "")
        if element_type == "reference" and not _looks_like_source_query(query):
            score *= 0.7

        return score

    @staticmethod
    def _build_doc_freq(chunks: list[Chunk]) -> dict[str, int]:
        doc_freq: dict[str, int] = {}
        for chunk in chunks:
            for term in set(_tokens(chunk.text_for_embedding)):
                doc_freq[term] = doc_freq.get(term, 0) + 1
        return doc_freq

    @staticmethod
    def _average_doc_length(chunks: list[Chunk]) -> float:
        lengths = [len(_tokens(chunk.text_for_embedding)) for chunk in chunks]
        return sum(lengths) / len(lengths) if lengths else 1.0
