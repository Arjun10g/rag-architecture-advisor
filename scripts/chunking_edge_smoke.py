from __future__ import annotations

from pathlib import Path
import sys
import tempfile

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from retrieval.chunking import Chunk, chunk_markdown_file


FIXTURE = """# Edge Fixture

## Good Section

Intro sentence.
This section deliberately has enough ordinary prose to avoid the tiny-section merge rule.
That keeps the fenced Python sample under Good Section, which makes the regression sharper.
The important behavior is that markdown-looking lines inside the fence remain code content,
not section boundaries, not algorithm lists, and not router-style structural metadata.
Several extra words are here on purpose: parser tests should be boring, explicit, and
resistant to unrelated threshold changes. This paragraph pushes the section beyond the
minimum tiny-merge cutoff while staying semantically disposable, so if the section path
changes later we know the fence-state parser changed rather than the merge heuristic.

```python
# Not A Heading
1. not an algorithm
## Not A Section
```

After the code block.

## Next Section ##

| Only |
|-|
| value |

1) first
2) second
3) third

~~~text
### Not A Heading Either
~~~
"""


def main() -> None:
    path = Path(tempfile.gettempdir()) / "chunking_edge_fixture.md"
    path.write_text(FIXTURE, encoding="utf-8")
    chunks = chunk_markdown_file(
        path,
        metadata={
            "path": "corpus/edge/chunking_edge_fixture.md",
            "namespace": "knowledge",
            "section_tags": ["edge"],
        },
    )

    section_paths = [" > ".join(chunk.metadata["section_path"]) for chunk in chunks]
    joined_sections = "\n".join(section_paths)
    if "Not A Heading" in joined_sections or "Not A Section" in joined_sections:
        raise SystemExit(f"fenced code was parsed as headings: {section_paths}")
    if "Next Section ##" in joined_sections:
        raise SystemExit(f"closing heading markers were not stripped: {section_paths}")

    element_counts = {}
    for chunk in chunks:
        element = chunk.metadata["element_type"]
        element_counts[element] = element_counts.get(element, 0) + 1

    if element_counts.get("code_fence") != 2:
        raise SystemExit(f"expected two fenced code chunks: {element_counts}")
    if element_counts.get("table") != 1:
        raise SystemExit(f"expected compact one-column table chunk: {element_counts}")
    if element_counts.get("list") != 1:
        raise SystemExit(f"expected 1) numbered list as list chunk: {element_counts}")

    caller_metadata = {"caller": "kept"}
    direct = Chunk(
        text_original="raw body",
        text_for_embedding="raw body",
        source_path='corpus/edge/"odd<path>.md',
        chunk_index=0,
        title='A "quoted" <title>',
        section_path=['A "quoted" <title>'],
        element_type="prose",
        metadata=caller_metadata,
    )
    if caller_metadata != {"caller": "kept"}:
        raise SystemExit(f"direct Chunk mutated caller metadata: {caller_metadata}")
    if "&quot;quoted&quot;" not in direct.text_for_generation or "&lt;title&gt;" not in direct.text_for_generation:
        raise SystemExit(f"SOURCE attributes were not escaped: {direct.text_for_generation}")

    print(f"sections={section_paths}")
    print(f"elements={element_counts}")


if __name__ == "__main__":
    main()
