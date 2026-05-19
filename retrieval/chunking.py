"""Markdown-native chunking for the advisor corpus.

The important design constraint is that markdown structure is semantic: headings,
tables, fenced examples, and ordered procedures are retrieval units, not formatting
noise. This module therefore walks the markdown once to find heading-delimited
segments, tracks fenced-code state while doing so, and then emits smaller chunks
without splitting atomic blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from html import escape
from pathlib import Path
import re
from typing import Any, Iterable, Literal


# Bump this whenever chunk boundaries or text renderings change; it becomes part
# of every chunk's metadata so future indexes can be compared or rebuilt safely.
CHUNKER_VERSION = "md-structure-v3"

# These are intentionally word-count approximations. The corpus is markdown-heavy,
# and exact tokenizer counts are less important here than preserving structure.
MAX_PROSE_WORDS = 1000
PROSE_OVERLAP_WORDS = 120
MIN_TINY_WORDS = 80

# ATX headings are detected only when we are outside fenced code blocks.
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

# CommonMark allows up to three leading spaces before a fence. We capture the
# marker character and length so the closing fence must match the opening style.
FENCE_OPEN_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")

# Ordered lists can use either "1." or "1)" markers.
NUMBERED_LIST_RE = re.compile(r"^\s*\d+[\.)]\s+")

# GFM-style table separator cells can be compact ("-") or alignment-marked
# (":---", "---:", ":---:").
TABLE_CELL_SEPARATOR_RE = re.compile(r"^:?-+:?$")

ElementType = Literal[
    "prose",
    "code_fence",
    "mermaid",
    "table",
    "list",
    "reference",
    "routing_card",
    "routing_rule",
]


def _word_count(text: str) -> int:
    """Cheap token approximation used only for chunk-size heuristics."""

    return len(re.findall(r"\S+", text))


def _last_words(text: str, count: int) -> str:
    """Return the overlap tail used when splitting oversized prose."""

    words = re.findall(r"\S+", text)
    return " ".join(words[-count:])


def _slug(value: str) -> str:
    """Create stable lowercase identifiers for document and parent IDs."""

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug or "chunk"


def _xml_attr(value: str) -> str:
    """Escape SOURCE wrapper attributes while leaving markdown body text verbatim."""

    return escape(value, quote=True)


def _clean_heading(value: str) -> str:
    """Strip optional closing ATX heading markers, e.g. 'Title ##'."""

    return re.sub(r"\s+#{1,}\s*$", "", value).strip()


def _fence_open(line: str) -> tuple[str, int, str] | None:
    """Return fence marker char, marker length, and info string for open fences."""

    match = FENCE_OPEN_RE.match(line)
    if not match:
        return None
    marker = match.group(1)
    info = match.group(2).strip()
    return marker[0], len(marker), info


def _is_fence_close(line: str, fence: tuple[str, int]) -> bool:
    """Check whether a line closes the active fenced block."""

    marker_char, marker_len = fence
    stripped = line.strip()
    if not stripped or any(char != marker_char for char in stripped):
        return False
    return len(stripped) >= marker_len


def _looks_like_table_row(line: str) -> bool:
    """Return true for pipe-delimited rows, including compact one-column rows."""

    stripped = line.strip()
    return "|" in stripped and stripped.count("|") >= 1


def _is_table_separator(line: str) -> bool:
    """Return true for the delimiter row between table headers and body."""

    if not _looks_like_table_row(line):
        return False
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(TABLE_CELL_SEPARATOR_RE.match(cell) for cell in cells)


def _is_table_start(lines: list[str], index: int) -> bool:
    """Detect a markdown table by header row plus separator row."""

    return (
        index + 1 < len(lines)
        and _looks_like_table_row(lines[index])
        and _is_table_separator(lines[index + 1])
    )


def _is_numbered_list_run(lines: list[str], index: int) -> bool:
    """Return true for a run of at least three ordered-list items."""

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


@dataclass
class AtomicBlock:
    """Atomic block coordinates are zero-based inclusive offsets into Segment.lines."""

    element_type: ElementType
    start_offset: int
    end_offset: int
    language: str | None = None


@dataclass
class Segment:
    """Heading-delimited markdown segment.

    start_line/end_line are 1-based inclusive document lines.
    """

    heading: str
    heading_level: int
    section_path: list[str]
    lines: list[str]
    start_line: int
    end_line: int
    blocks: list[AtomicBlock] = field(default_factory=list)


@dataclass
class Chunk:
    """A generated retrieval unit plus the provenance needed to cite it.

    `text_original` is the raw markdown payload for citation/display.
    `text_for_embedding` is allowed to be transformed, e.g. table linearization
    and metadata prefixes. IDs are derived in `__post_init__` so callers cannot
    accidentally duplicate or drift chunk IDs.

    Treat `source_path`, `chunk_index`, and `text_for_embedding` as immutable
    after construction. This dataclass stays mutable so relationship metadata can
    be attached later, but derived IDs are not recomputed after `__post_init__`.
    """

    text_original: str
    text_for_embedding: str
    source_path: str
    chunk_index: int
    title: str
    section_path: list[str]
    element_type: ElementType
    start_line: int | None = None  # 1-based inclusive document line.
    end_line: int | None = None  # 1-based inclusive document line.
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_id: str = field(init=False)
    content_hash: str = field(init=False)
    document_id: str = field(init=False)
    parent_id: str = field(init=False)
    text_for_generation: str = field(init=False)

    def __post_init__(self) -> None:
        # Normalize the source path into a stable document identifier that is
        # safe for filenames, vector-store IDs, and citation handles.
        self.document_id = _slug(Path(self.source_path).with_suffix("").as_posix())

        # Include source path and local chunk index in the hash input so two
        # identical snippets from different files do not collapse into one ID.
        hash_input = f"{self.source_path}\n{self.chunk_index}\n{self.text_for_embedding}"
        self.content_hash = sha256(hash_input.encode("utf-8")).hexdigest()
        self.chunk_id = f"{self.document_id}:{self.chunk_index:04d}:{self.content_hash[:10]}"

        # Parent IDs are coarser section anchors used later for parent expansion;
        # they are grouping handles, not hard deduplication keys.
        self.parent_id = f"{self.document_id}:{_slug('>'.join(self.section_path[:2] or [self.title]))}"
        section = " > ".join(self.section_path)

        # Generation text is rendered as an explicit source block so downstream
        # prompts can cite by stable source ID without guessing boundaries.
        source_id_attr = _xml_attr(self.chunk_id)
        title_attr = _xml_attr(self.title)
        section_attr = _xml_attr(section)
        file_attr = _xml_attr(self.source_path)
        self.text_for_generation = (
            f"<SOURCE id=\"{source_id_attr}\" title=\"{title_attr}\" section=\"{section_attr}\" "
            f"file=\"{file_attr}\">\n{self.text_original}\n</SOURCE>"
        )

        # Mirror first-class fields into metadata for simple stores and filters.
        self.metadata = {
            **self.metadata,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "parent_id": self.parent_id,
            "content_hash": f"sha256:{self.content_hash}",
            "chunker_version": CHUNKER_VERSION,
            "source_path": self.source_path,
            "chunk_index": self.chunk_index,
            "section_path": self.section_path,
            "element_type": self.element_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }

    @property
    def text_source(self) -> str:
        """Backward-compatible alias; prefer text_original in new code."""
        return self.text_original


def _linearize_table(text: str) -> str:
    """Render markdown tables as header-preserving row text for embeddings."""

    rows = [line.strip().strip("|") for line in text.splitlines() if _looks_like_table_row(line)]
    if len(rows) < 3:
        return text
    headers = [cell.strip() for cell in rows[0].split("|")]
    rendered = []
    for row in rows[2:]:
        cells = [cell.strip() for cell in row.split("|")]
        rendered.append("; ".join(f"{header}: {cell}" for header, cell in zip(headers, cells)))
    return "\n".join(rendered) or text


def _lines_without_blocks(lines: list[str], blocks: list[AtomicBlock]) -> list[str]:
    """Remove atomic block ranges so prose can be chunked separately."""

    blocked = set()
    for block in blocks:
        blocked.update(range(block.start_offset, block.end_offset + 1))
    return [line for idx, line in enumerate(lines) if idx not in blocked]


def _nearest_context_line(lines: list[str], start: int, reverse: bool) -> str | None:
    """Find the nearest non-structural line before or after an atomic block."""

    if reverse:
        iterator: Iterable[int] = range(start, -1, -1)
    else:
        iterator = range(start, len(lines))
    for idx in iterator:
        line = lines[idx].strip()
        if (
            not line
            or line.startswith("#")
            or _fence_open(line)
            or _looks_like_table_row(line)
        ):
            continue
        return line
    return None


def _block_with_context(lines: list[str], block: AtomicBlock) -> str:
    """Render an atomic block with one nearby explanatory line when present."""

    start = block.start_offset
    end = block.end_offset
    before = _nearest_context_line(lines, start - 1, reverse=True)
    after = _nearest_context_line(lines, end + 1, reverse=False)
    parts = []
    if before:
        parts.append(before)
    parts.extend(lines[start : end + 1])
    if after:
        parts.append(after)
    return "\n".join(parts)


def _split_prose(text: str) -> list[str]:
    """Split oversized prose on paragraph boundaries with word overlap."""

    if _word_count(text) <= MAX_PROSE_WORDS:
        return [text]

    paragraphs = [paragraph for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[Chunk] = []
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


def _detect_atomic_blocks(lines: list[str]) -> list[AtomicBlock]:
    """Find tables, fenced blocks, and ordered procedures inside a segment.

    Offsets are relative to `Segment.lines`, zero-based, and inclusive.
    """

    blocks: list[AtomicBlock] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        opening_fence = _fence_open(line)
        if opening_fence:
            # A fence is always atomic. We scan forward to the matching close
            # marker and never inspect its contents for tables/headings/lists.
            marker_char, marker_len, info = opening_fence
            language = info.split(maxsplit=1)[0] if info else None
            end = index
            for candidate in range(index + 1, len(lines)):
                if _is_fence_close(lines[candidate], (marker_char, marker_len)):
                    end = candidate
                    break
            element: ElementType = "mermaid" if language == "mermaid" else "code_fence"
            blocks.append(AtomicBlock(element, index, end, language))
            index = end + 1
            continue

        if _is_table_start(lines, index):
            # Once a table header + delimiter row is found, all following table
            # rows travel together so headers are never separated from values.
            end = index + 1
            while end + 1 < len(lines) and _looks_like_table_row(lines[end + 1]):
                end += 1
            blocks.append(AtomicBlock("table", index, end))
            index = end + 1
            continue

        if _is_numbered_list_run(lines, index):
            # Treat 3+ numbered items as one procedural/list chunk. Shorter
            # numbered snippets are usually prose examples in this corpus.
            end = index
            while end + 1 < len(lines) and (
                NUMBERED_LIST_RE.match(lines[end + 1]) or not lines[end + 1].strip()
            ):
                end += 1
            blocks.append(AtomicBlock("list", index, end))
            index = end + 1
            continue

        index += 1
    return blocks


def _same_parent(left: Segment, right: Segment) -> bool:
    """Return true when two segments are siblings under the same breadcrumb."""

    return left.section_path[:-1] == right.section_path[:-1]


def _merge_tiny_segments(segments: list[Segment]) -> list[Segment]:
    """Merge very small sibling sections into the next sibling.

    This keeps sparse headings such as "Definition" from embedding as nearly
    empty chunks while still refusing to cross parent-section boundaries.
    """

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
                    heading=next_segment.heading,
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


def _document_title(lines: list[str], path: Path) -> str:
    """Find the first H1 outside fenced code; fall back to the filename."""

    fence: tuple[str, int] | None = None
    for line in lines:
        if fence:
            if _is_fence_close(line, fence):
                fence = None
            continue
        opening_fence = _fence_open(line)
        if opening_fence:
            fence = (opening_fence[0], opening_fence[1])
            continue
        match = HEADING_RE.match(line)
        if match and len(match.group(1)) == 1:
            return _clean_heading(match.group(2))
    return path.stem.replace("_", " ").replace("-", " ").title()


def _heading_segments(lines: list[str], max_heading_level: int) -> list[Segment]:
    """Build heading-delimited segments while respecting fenced code blocks.

    Coordinates emitted by this function are 1-based inclusive document lines.
    `max_heading_level` controls which headings become segment boundaries; deeper
    headings remain inside the current segment.
    """

    title = _document_title(lines, Path("document.md"))
    heading_stack: dict[int, str] = {1: title}
    current: list[str] = []
    current_path: list[str] = [title]
    current_level = 1
    current_start = 1
    segments: list[Segment] = []
    fence: tuple[str, int] | None = None

    def flush(end_line: int) -> None:
        # Emit the accumulated segment before starting a new sibling section.
        nonlocal current
        if any(line.strip() for line in current):
            segments.append(
                Segment(
                    heading=current_path[-1],
                    heading_level=current_level,
                    section_path=current_path[:],
                    lines=current[:],
                    start_line=current_start,
                    end_line=end_line,
                )
            )
        current = []

    for line_number, line in enumerate(lines, start=1):
        if fence:
            # Inside a fence, markdown-looking lines are code content. This is
            # the critical guard that prevents "# comment" from becoming a
            # heading or "1." from becoming an algorithm chunk.
            current.append(line)
            if _is_fence_close(line, fence):
                fence = None
            continue

        opening_fence = _fence_open(line)
        if opening_fence:
            # Store only the marker char and length for close matching; the info
            # string is used later when detecting atomic block language.
            fence = (opening_fence[0], opening_fence[1])
            current.append(line)
            continue

        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            heading = _clean_heading(match.group(2))
            heading_stack[level] = heading
            for stale_level in list(heading_stack):
                # Drop headings from deeper branches when we move to a sibling
                # or ancestor heading.
                if stale_level > level:
                    del heading_stack[stale_level]

            if 2 <= level <= max_heading_level:
                # H2/H3 boundaries become primary retrieval segments.
                flush(line_number - 1)
                current = [line]
                current_level = level
                current_path = [heading_stack[lvl] for lvl in sorted(heading_stack) if lvl <= level]
                current_start = line_number
                continue

            if level <= max_heading_level and level == 1:
                # The H1 is document identity, not a retrievable segment by
                # itself, so it does not enter `current`.
                continue

        current.append(line)

    flush(len(lines))
    return segments


def _make_chunk(
    path: Path,
    title: str,
    section_path: list[str],
    text_original: str,
    element_type: ElementType,
    heading_level: int,
    metadata: dict[str, Any],
    local_index: int,
    start_line: int | None = None,
    end_line: int | None = None,
    block_language: str | None = None,
) -> Chunk:
    """Create a `Chunk` with all renderings and provenance fields populated."""

    rel_path = metadata.get("path") or path.as_posix()
    source_metadata = dict(metadata)
    source_metadata.update(
        {
            "chunker_version": CHUNKER_VERSION,
            "heading_level": heading_level,
            "block_language": block_language,
        }
    )

    section = " > ".join(section_path)
    # Tables embed better after linearization, but citation uses the original
    # markdown table through `text_original`.
    embedding_body = _linearize_table(text_original) if element_type == "table" else text_original
    tags = ", ".join(source_metadata.get("section_tags") or [])
    text_for_embedding = f"[Doc: {title}] [Section: {section}] [Tags: {tags}]\n{embedding_body}"

    return Chunk(
        text_original=text_original,
        text_for_embedding=text_for_embedding,
        source_path=rel_path,
        chunk_index=local_index,
        title=title,
        section_path=section_path,
        element_type=element_type,
        start_line=start_line,
        end_line=end_line,
        metadata=source_metadata,
    )


def _attach_relationships(chunks: list[Chunk]) -> None:
    """Attach local previous/next links after all chunk IDs have been generated."""

    for index, chunk in enumerate(chunks):
        chunk.metadata["previous"] = chunks[index - 1].chunk_id if index > 0 else None
        chunk.metadata["next"] = chunks[index + 1].chunk_id if index + 1 < len(chunks) else None


def _chunk_segment(
    path: Path,
    title: str,
    segment: Segment,
    metadata: dict[str, Any],
    segment_index: int,
) -> list[Chunk]:
    """Convert one heading segment into prose chunks plus atomic block chunks."""

    if not segment.blocks:
        segment.blocks = _detect_atomic_blocks(segment.lines)
    blocks = segment.blocks
    is_reference = any("reference" in part.lower() or "bibliography" in part.lower() for part in segment.section_path)
    chunks: list[Chunk] = []

    if not blocks:
        # Simple sections stay together unless they exceed the prose size limit.
        source = "\n".join(segment.lines).strip()
        for piece_index, piece in enumerate(_split_prose(source)):
            chunks.append(
                _make_chunk(
                    path=path,
                    title=title,
                    section_path=segment.section_path,
                    text_original=piece,
                    element_type="reference" if is_reference else "prose",
                    heading_level=segment.heading_level,
                    metadata=metadata,
                    local_index=(segment_index * 1000) + piece_index,
                    start_line=segment.start_line,
                    end_line=segment.end_line,
                )
            )
        return chunks

    prose_lines = _lines_without_blocks(segment.lines, blocks)
    prose = "\n".join(prose_lines).strip()
    if prose:
        # When a section contains tables/code/lists, keep the surrounding prose
        # as its own chunk and emit each structural block separately.
        for piece_index, piece in enumerate(_split_prose(prose)):
            chunks.append(
                _make_chunk(
                    path=path,
                    title=title,
                    section_path=segment.section_path,
                    text_original=piece,
                    element_type="reference" if is_reference else "prose",
                    heading_level=segment.heading_level,
                    metadata=metadata,
                    local_index=(segment_index * 1000) + piece_index,
                    start_line=segment.start_line,
                    end_line=segment.end_line,
                )
            )

    for block_index, block in enumerate(blocks, start=1):
        # The block chunk carries one nearby line before/after when available;
        # this acts like a local caption without merging unrelated blocks.
        source = _block_with_context(segment.lines, block).strip()
        chunks.append(
            _make_chunk(
                path=path,
                title=title,
                section_path=segment.section_path,
                text_original=source,
                element_type=block.element_type,
                heading_level=segment.heading_level,
                metadata=metadata,
                local_index=(segment_index * 1000) + 500 + block_index,
                start_line=segment.start_line + block.start_offset,
                end_line=segment.start_line + block.end_offset,
                block_language=block.language,
            )
        )
    return chunks


def _chunk_structured_markdown(
    path: Path, title: str, lines: list[str], metadata: dict[str, Any]
) -> list[Chunk]:
    """Chunk regular corpus files by markdown heading structure."""

    segments = _heading_segments(lines, max_heading_level=3)
    if not segments:
        segments = [Segment(title, 1, [title], lines, 1, len(lines))]

    chunks: list[str] = []
    for segment_index, segment in enumerate(_merge_tiny_segments(segments)):
        chunks.extend(_chunk_segment(path, title, segment, metadata, segment_index))
    return chunks


def _chunk_routing_card(
    path: Path, title: str, lines: list[str], metadata: dict[str, Any]
) -> list[Chunk]:
    """Chunk router documents as rules, not free prose.

    Domain profiles are each one atomic card. The taxonomy and decision-logic
    files are split by H2 so each attribute/stage can be retrieved as a whole.
    """

    name = path.name
    if name.startswith("domain-"):
        source = "\n".join(lines).strip()
        return [
            _make_chunk(
                path=path,
                title=title,
                section_path=[title],
                text_original=source,
                element_type="routing_card",
                heading_level=1,
                metadata=metadata,
                local_index=0,
            )
        ]

    segments = _heading_segments(lines, max_heading_level=2)
    if not segments:
        segments = [Segment(title, 1, [title], lines, 1, len(lines))]

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
                text_original=source,
                element_type="routing_rule",
                heading_level=segment.heading_level,
                metadata=metadata,
                local_index=index,
                start_line=segment.start_line,
                end_line=segment.end_line,
            )
        )
    return chunks


def chunk_markdown_file(path: str | Path, metadata: dict[str, Any] | None = None) -> list[Chunk]:
    """Parse one markdown file into generated chunks.

    Routing cards intentionally use a stricter chunking path than knowledge
    corpus files: the router needs whole rules/cards, while knowledge retrieval
    benefits from subsection and atomic-block granularity.
    """

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
