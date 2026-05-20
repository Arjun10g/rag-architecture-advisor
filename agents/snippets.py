from __future__ import annotations

import re


RAW_CORPUS_PATH_RE = re.compile(r"\bcorpus/(?:[^\s`),;]+)?")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MARKDOWN_PREFIX_RE = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")
TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{1,}:?\s*(?:\|\s*:?-{1,}:?\s*)+\|?$")


def display_snippet(
    text: str,
    *,
    limit: int = 220,
    section: str = "",
    element_type: str = "",
) -> str:
    """Create a short, prose-only evidence summary for public output."""
    prose_lines: list[str] = []
    saw_table = element_type.lower().strip() == "table"
    inside_fence = False

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("```", "~~~")):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        if _is_table_line(stripped):
            saw_table = True
            continue
        if _is_low_signal_line(stripped):
            continue
        cleaned = _clean_inline(stripped)
        if cleaned:
            prose_lines.append(cleaned)

    compact = " ".join(prose_lines)
    if compact:
        return _shorten(compact, limit)
    if saw_table:
        return _table_summary(section, limit)
    return _shorten(_clean_inline(" ".join(text.split())), limit)


def _is_table_line(line: str) -> bool:
    if TABLE_SEPARATOR_RE.match(line):
        return True
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _is_low_signal_line(line: str) -> bool:
    lower = line.lower()
    return (
        line in {"---"}
        or line.startswith("#")
        or lower.startswith(("source:", "sources:", "references:", "bibliography"))
        or lower.startswith(("http://", "https://"))
    )


def _clean_inline(text: str) -> str:
    text = RAW_CORPUS_PATH_RE.sub("the curated corpus", text)
    text = re.sub(r"\\\[[^\]]+\\\]", "", text)
    text = re.sub(r"\$[^$]+\$", "", text)
    text = MARKDOWN_LINK_RE.sub(r"\1", text)
    text = MARKDOWN_PREFIX_RE.sub("", text)
    text = text.replace("`", "")
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _table_summary(section: str, limit: int) -> str:
    subject = _clean_inline(section.split(">")[-1] if section else "").strip(" .")
    if subject:
        summary = (
            f"The retrieved table summarizes {subject.lower()} using comparison fields "
            "such as latency, retrieval quality, cost, citations, recall, or operational notes."
        )
    else:
        summary = (
            "The retrieved table compares architecture options using operational fields "
            "such as latency, retrieval quality, cost, citations, recall, or notes."
        )
    return _shorten(summary, limit)


def _shorten(text: str, limit: int) -> str:
    compact = _clean_inline(text)
    if len(compact) <= limit:
        return compact
    boundary = compact.rfind(". ", 0, limit - 3)
    if boundary >= max(60, limit // 2):
        return compact[: boundary + 1]
    boundary = compact.rfind("; ", 0, limit - 3)
    if boundary >= max(60, limit // 2):
        return compact[: boundary + 1].rstrip()
    boundary = compact.rfind(" ", 0, limit - 3)
    if boundary < max(40, limit // 3):
        boundary = limit - 3
    return f"{compact[:boundary].rstrip()}..."
