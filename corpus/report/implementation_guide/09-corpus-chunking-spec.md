# Corpus Chunking Spec — Ingesting the Markdown Research Bundles

**Track A (project ingestion spec).** This defines exactly how the bundle `.md` files (the chunking bundle, the context/grounding bundle, and the other 9 folders) are turned into retrievable chunks. It supersedes the generic guidance in `03-retrieval-corpus-spec.md` for these specific files, because they share a regular, exploitable structure that a naive splitter destroys.

## 1. What these documents actually are

Every file in every folder follows the same skeleton, confirmed across the bundle:

- A single `# NN — Title` H1, optionally a `>` blockquote subtitle (`> Part of Report 02 ...`).
- `## N. Section` and `### Subsection` headings, numbered.
- Heavy use of **markdown tables** (parameter tables, failure-mode tables, decision matrices).
- Fenced blocks: ` ```mermaid `, ` ```python `, ` ```json `, ` ```yaml `, ` ```text `.
- Numbered algorithm/step lists and bulleted strength/failure lists.
- A trailing `## References` / bibliography section in most files.

This regularity is the asset. The chunker is **structure-aware and markdown-native**, not character-recursive. Generic `RecursiveCharacterTextSplitter` on these files is explicitly rejected: it splits tables mid-row, severs mermaid graphs from their captions, and orphans code from the prose that explains it — every failure mode the bundle's own `04 §1` warns about.

## 2. Core strategy: heading-scoped, structure-atomic chunking

The unit is the **`###` subsection** (or `##` section when it has no subsections), with two hard rules:

1. **Headings define boundaries.** Never split across a `##`/`###` boundary. Never merge two sibling subsections into one chunk.
2. **Structural blocks are atomic.** A markdown table, a fenced code/mermaid/json/yaml block, or a numbered algorithm list is **never split**. It travels whole, with its introducing sentence and its immediately following explanatory sentence.

This is parent–child (`05 §7`) projected onto markdown: the `##` section is the parent, its `###` subsections (and atomic blocks) are the children.

```
H1 (document)                      -> document_id, not a chunk
  ## N. Section                    -> parent node (stored, retrievable as expansion)
    ### Subsection                 -> child chunk  (the primary retrievable unit)
    | markdown table |             -> atomic child chunk (never row-split)
    ```mermaid ... ```             -> atomic child chunk (graph + caption)
    ```python ... ```              -> atomic child chunk (code + explaining sentence)
```

### Size policy (secondary to structure)

Structure wins; size only acts *within* a subsection.

| Case | Rule |
|---|---|
| Subsection ≤ 1000 tokens | one chunk, as-is |
| Subsection > 1000 tokens, prose-only | recursive split on paragraph (`\n\n`) then sentence, 150-token overlap, **never** through a table/code block |
| Subsection contains a table/code block | emit the prose as one child, each table/code block as its own atomic sibling child, all sharing the subsection's `section_path` |
| Tiny subsection < 80 tokens (e.g. a 3-line "Definition") | merge **up** into the next sibling under the same parent, never across the parent boundary |

Target child size 200–1000 tokens; parents are whole `##` sections regardless of size (used for expansion, not embedded).

## 3. Per-block-type handling

| Block type | Detection | Chunking rule | Why |
|---|---|---|---|
| Markdown table | line starts `\|`, has `\|---\|` separator | whole table = one chunk; prepend the sentence above it and the table's nearest `###` heading text | a row is meaningless without headers + caption (`05 §9`); these files are table-dense |
| `mermaid` fence | ` ```mermaid ` | whole diagram = one chunk; attach the sentence introducing it; store the diagram text verbatim in `text_source` | a severed flowchart is unretrievable and uncitable |
| `python`/`json`/`yaml`/`text` fence | ` ``` ` open/close | whole block = one chunk with its preceding explanatory sentence and the first sentence after it | code split from its explanation is the `04 §1` "answer unsupported" failure |
| Numbered algorithm list | `^\d+\.` run under an `### Algorithm` heading | keep the entire list as one chunk with its heading | steps are a single procedure, not independent facts |
| Strength/failure bullet list | `^- ` run | keep with its parent subsection prose | bullets are claims about the subsection topic |
| `## References` / bibliography | heading match | one chunk per reference cluster, not per link; tag `element_type: reference` and down-weight in retrieval | references are navigational, not answer-bearing; but keep for source-mapping |

## 4. Three text forms (applied to this corpus)

Per the metadata principle, every chunk carries three renderings:

- **`text_source`** — the raw markdown of the unit, verbatim (tables stay as pipe tables, mermaid stays as mermaid). Citable, immutable.
- **`text_for_embedding`** — `text_source` prefixed with a metadata context line so short subsections become findable:
  ```
  [Doc: 02 — Strategy Catalog] [Section: 1. Fixed-size chunking > Failure modes]
  <text_source>
  ```
- **`text_for_generation`** — rendered as a source block with `source_id`, doc title, `section_path`, and (where present) the bundle/report name, so the generator can cite at section precision.

Tables get a fourth consideration: their `text_for_embedding` is a linearized `key: value; key: value` rendering of each row (per `05 §9` header-preserving rendering) so the vector captures cell content, while `text_source` keeps the visual table for citation.

## 5. Metadata schema per chunk (this corpus)

Derived mechanically from the markdown structure — no manual tagging required:

```json
{
  "identity": {
    "chunk_id": "ctx02_01:s6:sandwich_order:c2",
    "document_id": "ctx02_01_context_construction",
    "parent_id": "ctx02_01:s6",
    "content_hash": "sha256:...",
    "namespace": "knowledge"
  },
  "structure": {
    "element_type": "table | mermaid | code | prose | algorithm | reference",
    "section_path": ["6. Ordering strategies", "Sandwich order"],
    "heading_level": 3,
    "block_language": "python"            // null for prose/table
  },
  "provenance": {
    "bundle": "context_grounding_bundle",
    "file": "01_context_construction_and_context_packing.md",
    "report": "Report 02 — RAG Design Choices ...",   // from the > blockquote
    "source_url": "<from manifest>",
    "license": "<from manifest, fail-closed>",
    "trust_tier": "primary",
    "chunker_version": "md-structure-v1",
    "embedding_model": "model@rev",
    "index_version": "corpus_2026_05_19_v1"
  },
  "temporal_authority": {
    "doc_generated": "2026-05-18",          // from bundle README
    "volatility": "volatile | stable",      // model/pricing tables -> volatile
    "contested": "consensus | contested"
  },
  "semantic_tags": {
    "domain": "chunking | context | grounding | compression | generator | ...",
    "section_tags": ["failure-mode", "parameters", "decision-matrix"]
  },
  "relationships": {
    "parent": "ctx02_01:s6",
    "previous": "ctx02_01:s6:relevance_order:c1",
    "next": "ctx02_01:s6:subquestion_grouping:c3",
    "children": []
  }
}
```

Key derivations specific to these files:

- `section_path` is built from the live `##`/`###` heading stack during the parse walk — this is the single highest-value field and it is free here because the documents are well-headed.
- `report` / `bundle` come from the `>` blockquote and the folder's `README.md` file map.
- `volatility = volatile` is auto-set for chunks whose table contains price/window columns (e.g. the generator-model snapshot in `05_generator_model_selection`), so the advisor hedges stale specifics. `02_grounding`/`04_selection` conceptual content is `stable`.
- `domain` is assigned per source folder (one of the 11), enabling the metadata-filtered retrieval the router relies on.

## 6. Ingestion algorithm

```python
def chunk_bundle_file(path, manifest_entry):
    md = read(path)
    assert manifest_entry.license and manifest_entry.trust_tier   # fail closed
    tree = parse_markdown_to_heading_tree(md)        # H1 > ## > ###
    chunks = []
    for section in tree.iter("##"):
        parent = make_parent(section)                 # stored, not embedded
        for node in section.iter_children():          # ### or atomic block
            if node.is_block():                       # table/mermaid/code
                unit = node.with_adjacent_sentences()  # intro + first follow-up
                chunks.append(make_atomic_chunk(unit, parent, section_path))
            else:                                     # prose subsection
                if tok(node) <= 1000:
                    chunks.append(make_chunk(node, parent, section_path))
                else:
                    for piece in split_prose_no_block_cross(node, 1000, 150):
                        chunks.append(make_chunk(piece, parent, section_path))
        merge_tiny_siblings_within(parent)            # < 80 tok merge up
    attach_relationships(chunks)                       # prev/next/parent
    return chunks
```

Idempotent: same file + same `chunker_version` ⇒ identical `chunk_id`s and `content_hash`es (the reproducibility contract from `05 §15`). This *is* the "repeatable provisioning" demonstration the implementation overview calls for.

## 7. Retrieval consequences (why this chunking, concretely)

| Bundle pattern | If chunked generically | With this spec |
|---|---|---|
| `02` parameter tables | rows split → half a table retrieved → wrong parameter cited | whole table + heading retrieved → correct, citable |
| `04 §2` mermaid decision tree | graph severed → unretrievable, meaningless | whole graph + intro → returns as a unit |
| `01 §5` context-assembly `python` | code without its explaining prose → unsupported answer | code + explanation bound → grounded |
| Short "Definition" subsections | embedding too sparse → never retrieved | metadata-prefixed embedding → findable |
| `05` model/pricing table | stale price stated as current | `volatility: volatile` → advisor hedges |

## 8. Ablation hook (eval ties in)

Per `04 §6` and `08-gold-set-creation-plan.md`, register the chunker as a tested factor, not a fixed choice:

```yaml
factors:
  chunker: [md_structure_v1, recursive_baseline_768]   # baseline must lose
  embedding_prefix: [none, doc+section, doc+section+tags]
  parent_expansion: [child_only, child_to_parent, automerge]
metrics: [recall@10, mrr, context_precision, citation_correctness,
          duplicate_rate, p95_latency, index_size]
gold: eval/gold/   # includes table-lookup, mermaid, code, short-def, references
```

The structure-aware chunker should beat the recursive baseline on citation-correctness and table-lookup recall; if it does not, that is a finding, not an assumption. The gold set must include table-value questions, "what does the decision tree say" questions, code-behavior questions, and short-definition lookups so each block-type rule is exercised.

## 9. Practical rules

1. Parse to a heading tree first; never regex-split raw text.
2. Headings are hard boundaries; structural blocks are atomic.
3. Always carry `section_path`; it is free here and is the top-value field.
4. Tables and mermaid keep a visual `text_source` and a linearized `text_for_embedding`.
5. Bind code/diagrams to their adjacent explanatory sentence.
6. Auto-flag price/window/version tables as `volatile`.
7. Assign `domain` per source folder for metadata-filtered retrieval.
8. Down-weight, don't drop, `## References` chunks.
9. Version the chunker; reindex blue-green on any rule change.
10. Treat the chunker as an eval factor with a recursive baseline it must beat.
