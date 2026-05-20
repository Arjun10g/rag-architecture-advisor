from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from retrieval.vector_store import table_name_for_dimension
from scripts.build_vector_index import _build_order, _parse_dimensions, _write_manifest


def main() -> None:
    dimensions = _parse_dimensions("1024,512,1024")
    if _build_order(dimensions, 1024) != [1024, 512]:
        raise AssertionError("dimension build order should keep native dim first and de-dupe")
    if table_name_for_dimension("chunks", 512) != "chunks_dim_512":
        raise AssertionError("dimension-specific table naming changed")

    out_dir = Path(tempfile.mkdtemp(prefix="rag-vector-manifest-"))
    payload = {
        "backend": "lancedb",
        "table_base": "chunks",
        "dimensions": [1024, 512],
        "indexes": [
            {"dimension": 1024, "table": "chunks_dim_1024", "chunks": 10},
            {"dimension": 512, "table": "chunks_dim_512", "chunks": 10},
        ],
    }
    _write_manifest(out_dir, payload)
    loaded = json.loads((out_dir / "vector_manifest.json").read_text(encoding="utf-8"))
    if loaded["dimensions"] != [1024, 512]:
        raise AssertionError("vector manifest did not preserve configured dimensions")

    print("vector_index_manifest_smoke=ok dimensions=1024,512")


if __name__ == "__main__":
    main()
