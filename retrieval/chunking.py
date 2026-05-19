from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import re
from typing import Iterable


CHUNKER_VERSION = "md-structure-v1"
MAX_PROSE_WORDS = 1000
PROSE_OVERLAP_WORDS = 120
MIN_TINY_WORDS = 80

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
NUMBERED_LIST_RE = re.compile(r"^\s*\d+\.\s+")


@dataclass
class Chunk:
    chunk_id: str
    text_source: str
    text_for_embedding: str
    text_for_generation: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Segment:
    heading_level: int
    section_path: list[str]
    lines: list[str]
    start_line: int
    end_line: int


@dataclass
class AtomicBlock:
    element_type: str
    start: int
    end: int
    language: str | None = None


def chunk_markdown_file(path: str | Path, metadata: dict | None = None) -> list[Chunk]:
    path = Path(path)
    doc_metadata = dict(metadata or {})
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = _document_title(lines, path)

    if doc_metadata.get("content_kind") == "routing-card":
        chunks = _chunk_routing_card(path, title, lines, doc_metadata)
    else:
        chunks = _chunk_structured_markdown(path, title, lines, doc_metadata)

    _attach_relationships(chunks)
    return chunks


def _chunk_routing_card(path: Path, title: str, lines: list[str], metadata: dict) -> list[Chunk]:
    name = path.name
    if name.startswith("domain-"):
        source = "\n".join(lines).strip()
        return [
            _make_chunk(
                path=path,
                title=title,
                section_path=[title],
                text_source=source,
                element_type="routing_card",
                heading_level=1,
                metadata=metadata,
                local_index=0,
            )
        ]

    segments = _heading_segments(lines, max_heading_level=2)
    if not segments:
        segments = [Segment(1, [title], lines, 1, len(lines))]

    chunks: list[Chunk] = []
    for index, segment in enumerate(segments):
        source = "\n".join(segment.lines).strip()
        if not source:
            continue
        chunks.append(
            _make_chunk(
                path=path,
                title=title,
                section_path=segment.section_path,
                text_source=source,
                element_type="routing_rule",
                heading_level=segment.heading_level,
                metadata=metadata,
                local_index=index,
                line_start=segment.start_line,
                line_end=segment.end_line,
            )
        )
    return chunks


def _chunk_structured_markdown(
    path: Path, title: str, lines: list[str], metadata: dict
) -> list[Chunk]:
    segments = _heading_segments(lines, max_heading_level=3)
    if not segments:
        segments = [Segment(1, [title], lines, 1, len(lines))]

    chunks: list[Chunk] = []
    for segment_index, segment in enumerate(_merge_tiny_segments(segments)):
        chunks.extend(_chunk_segment(path, title, segment, metadata, segment_index))
    return chunks


def _heading_segments(lines: list[str], max_heading_level: int) -> list[Segment]:
    title = _document_title(lines, Path("document.md"))
    heading_stack: dict[int, str] = {1: title}
    current: list[str] = []
    current_path: list[str] = [title]
    current_level = 1
    current_start = 1
    segments: list[Segment] = []

    def flush(end_line: int) -> None:
        nonlocal current
        if any(line.strip() for line in current):
            segments.append(
                Segment(
                    heading_level=current_level,
                    section_path=current_path[:],
                    lines=current[:],
                    start_line=current_start,
                    end_line=end_line,
                )
            )
        current = []

    for line_number, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            heading = match.group(2).strip()
            heading_stack[level] = heading
            for stale_level in list(heading_stack):
                if stale_level > level:
                    del heading_stack[stale_level]

            if 2 <= level <= max_heading_level:
                flush(line_number - 1)
                current = [line]
                current_level = level
                current_path = [heading_stack[lvl] for lvl in sorted(heading_stack) if lvl <= level]
                current_start = line_number
                continue

            if level <= max_heading_level and level == 1:
                continue

        current.append(line)

    flush(len(lines))
    return segments


def _merge_tiny_segments(segments: list[Segment]) -> list[Segment]:
    if len(segments) < 2:
        return segments

    merged: list[Segment] = []
    index = 0
    while index < len(segments):
        segment = segments[index]
        words = _word_count("\n".join(segment.lines))
        can_merge_forward = (
            words < MIN_TINY_WORDS
            and index + 1 < len(segments)
            and _same_parent(segment, segments[index + 1])
        )
        if can_merge_forward:
            next_segment = segments[index + 1]
            merged.append(
                Segment(
                    heading_level=next_segment.heading_level,
                    section_path=next_segment.section_path,
                    lines=segment.lines + [""] + next_segment.lines,
                    start_line=segment.start_line,
                    end_line=next_segment.end_line,
                )
            )
            index += 2
        else:
            merged.append(segment)
            index += 1
    return merged


def _same_parent(left: Segment, right: Segment) -> bool:
    return left.section_path[:-1] == right.section_path[:-1]


def _chunk_segment(
    path: Path,
    title: str,
    segment: Segment,
    metadata: dict,
    segment_index: int,
) -> list[Chunk]:
    blocks = _detect_atomic_blocks(segment.lines)
    is_reference = any("reference" in part.lower() or "bibliography" in part.lower() for part in segment.section_path)
    chunks: list[Chunk] = []

    if not blocks:
        source = "\n".join(segment.lines).strip()
        for piece_index, piece in enumerate(_split_prose(source)):
            chunks.append(
                _make_chunk(
                    path=path,
                    title=title,
                    section_path=segment.section_path,
                    text_source=piece,
                    element_type="reference" if is_reference else "prose",
                    heading_level=segment.heading_level,
                    metadata=metadata,
                    local_index=(segment_index * 1000) + piece_index,
                    line_start=segment.start_line,
                    line_end=segment.end_line,
                )
            )
        return chunks

    prose_lines = _lines_without_blocks(segment.lines, blocks)
    prose = "\n".join(prose_lines).strip()
    if prose:
        for piece_index, piece in enumerate(_split_prose(prose)):
            chunks.append(
                _make_chunk(
                    path=path,
                    title=title,
                    section_path=segment.section_path,
                    text_source=piece,
                    element_type="reference" if is_reference else "prose",
                    heading_level=segment.heading_level,
                    metadata=metadata,
                    local_index=(segment_index * 1000) + piece_index,
                    line_start=segment.start_line,
                    line_end=segment.end_line,
                )
            )

    for block_index, block in enumerate(blocks, start=1):
        source = _block_with_context(segment.lines, block).strip()
        chunks.append(
            _make_chunk(
                path=path,
                title=title,
                section_path=segment.section_path,
                text_source=source,
                element_type=block.element_type,
                heading_level=segment.heading_level,
                metadata=metadata,
                local_index=(segment_index * 1000) + 500 + block_index,
                line_start=segment.start_line + block.start,
                line_end=segment.start_line + block.end,
                block_language=block.language,
            )
        )
    return chunks


def _detect_atomic_blocks(lines: list[str]) -> list[AtomicBlock]:
    blocks: list[AtomicBlock] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            language = stripped.removeprefix("```").strip() or None
            end = index
            for candidate in range(index + 1, len(lines)):
                if lines[candidate].strip().startswith("```"):
                    end = candidate
                    break
            element = "mermaid" if language == "mermaid" else "code"
            blocks.append(AtomicBlock(element, index, end, language))
            index = end + 1
            continue

        if _is_table_start(lines, index):
            end = index + 1
            while end + 1 < len(lines) and _looks_like_table_row(lines[end + 1]):
                end += 1
            blocks.append(AtomicBlock("table", index, end))
            index = end + 1
            continue

        if _is_numbered_list_run(lines, index):
            end = index
            while end + 1 < len(lines) and (
                NUMBERED_LIST_RE.match(lines[end + 1]) or not lines[end + 1].strip()
            ):
                end += 1
            blocks.append(AtomicBlock("algorithm", index, end))
            index = end + 1
            continue

        index += 1
    return blocks


def _is_table_start(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and _looks_like_table_row(lines[index])
        and TABLE_SEPARATOR_RE.match(lines[index + 1]) is not None
    )


def _looks_like_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_numbered_list_run(lines: list[str], index: int) -> bool:
    if not NUMBERED_LIST_RE.match(lines[index]):
        return False
    count = 1
    cursor = index + 1
    while cursor < len(lines):
        if NUMBERED_LIST_RE.match(lines[cursor]):
            count += 1
        elif lines[cursor].strip():
            break
        cursor += 1
    return count >= 3


def _lines_without_blocks(lines: list[str], blocks: list[AtomicBlock]) -> list[str]:
    blocked = set()
    for block in blocks:
        blocked.update(range(block.start, block.end + 1))
    return [line for idx, line in enumerate(lines) if idx not in blocked]


def _block_with_context(lines: list[str], block: AtomicBlock) -> str:
    start = block.start
    end = block.end
    before = _nearest_context_line(lines, start - 1, reverse=True)
    after = _nearest_context_line(lines, end + 1, reverse=False)
    parts = []
    if before:
        parts.append(before)
    parts.extend(lines[start : end + 1])
    if after:
        parts.append(after)
    return "\n".join(parts)


def _nearest_context_line(lines: list[str], start: int, reverse: bool) -> str | None:
    if reverse:
        iterator: Iterable[int] = range(start, -1, -1)
    else:
        iterator = range(start, len(lines))
    for idx in iterator:
        line = lines[idx].strip()
        if not line or line.startswith("#") or line.startswith("```") or _looks_like_table_row(line):
            continue
        return line
    return None


def _split_prose(text: str) -> list[str]:
    if _word_count(text) <= MAX_PROSE_WORDS:
        return [text]

    paragraphs = [paragraph for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for paragraph in paragraphs:
        words = _word_count(paragraph)
        if current and current_words + words > MAX_PROSE_WORDS:
            chunks.append("\n\n".join(current).strip())
            overlap = _last_words(chunks[-1], PROSE_OVERLAP_WORDS)
            current = [overlap] if overlap else []
            current_words = _word_count(overlap)
        current.append(paragraph)
        current_words += words

    if current:
        chunks.append("\n\n".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _make_chunk(
    path: Path,
    title: str,
    section_path: list[str],
    text_source: str,
    element_type: str,
    heading_level: int,
    metadata: dict,
    local_index: int,
    line_start: int | None = None,
    line_end: int | None = None,
    block_language: str | None = None,
) -> Chunk:
    rel_path = metadata.get("path") or path.as_posix()
    document_id = _slug(Path(rel_path).with_suffix("").as_posix())
    content_hash = sha256(text_source.encode("utf-8")).hexdigest()
    chunk_id = f"{document_id}:{local_index:04d}:{content_hash[:10]}"
    parent_id = f"{document_id}:{_slug('>'.join(section_path[:2] or [title]))}"
    source_metadata = dict(metadata)
    source_metadata.update(
        {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "parent_id": parent_id,
            "content_hash": f"sha256:{content_hash}",
            "chunker_version": CHUNKER_VERSION,
            "section_path": section_path,
            "heading_level": heading_level,
            "element_type": element_type,
            "block_language": block_language,
            "line_start": line_start,
            "line_end": line_end,
        }
    )

    section = " > ".join(section_path)
    embedding_body = _linearize_table(text_source) if element_type == "table" else text_source
    tags = ", ".join(source_metadata.get("section_tags") or [])
    text_for_embedding = f"[Doc: {title}] [Section: {section}] [Tags: {tags}]\n{embedding_body}"
    text_for_generation = (
        f"<SOURCE id=\"{chunk_id}\" title=\"{title}\" section=\"{section}\" "
        f"file=\"{rel_path}\">\n{text_source}\n</SOURCE>"
    )

    return Chunk(
        chunk_id=chunk_id,
        text_source=text_source,
        text_for_embedding=text_for_embedding,
        text_for_generation=text_for_generation,
        metadata=source_metadata,
    )


def _attach_relationships(chunks: list[Chunk]) -> None:
    for index, chunk in enumerate(chunks):
        chunk.metadata["previous"] = chunks[index - 1].chunk_id if index > 0 else None
        chunk.metadata["next"] = chunks[index + 1].chunk_id if index + 1 < len(chunks) else None


def _linearize_table(text: str) -> str:
    rows = [line.strip().strip("|") for line in text.splitlines() if _looks_like_table_row(line)]
    if len(rows) < 3:
        return text
    headers = [cell.strip() for cell in rows[0].split("|")]
    rendered = []
    for row in rows[2:]:
        cells = [cell.strip() for cell in row.split("|")]
        rendered.append("; ".join(f"{header}: {cell}" for header, cell in zip(headers, cells)))
    return "\n".join(rendered) or text


def _document_title(lines: list[str], path: Path) -> str:
    for line in lines:
        match = HEADING_RE.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2).strip()
    return path.stem.replace("_", " ").replace("-", " ").title()


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _last_words(text: str, count: int) -> str:
    words = re.findall(r"\S+", text)
    return " ".join(words[-count:])


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug or "chunk"
