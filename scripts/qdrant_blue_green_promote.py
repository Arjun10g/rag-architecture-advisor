from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience.
    load_dotenv = None

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from retrieval.vector_store import VectorStoreConfig, table_name_for_dimension
from scripts.build_vector_index import DEFAULT_INDEX_DIMENSIONS, _build_order, _parse_dimensions
from scripts.qdrant_cloud_bootstrap import _update_env


DEFAULT_ALIAS_TABLE = "rag_advisor_chunks_live"
DEFAULT_MANIFEST_DIR = "corpus/index/qdrant"


def main() -> None:
    if load_dotenv:
        load_dotenv()

    parser = argparse.ArgumentParser(
        description=(
            "Atomically point Qdrant live aliases at a verified blue/green "
            "collection set without overwriting existing collections."
        )
    )
    parser.add_argument("--target-table", default=_env("QDRANT_TARGET_TABLE", "rag_advisor_chunks"))
    parser.add_argument("--alias-table", default=_env("QDRANT_LIVE_TABLE_NAME", DEFAULT_ALIAS_TABLE))
    parser.add_argument(
        "--dimensions",
        default=_env("VECTOR_INDEX_DIMS", DEFAULT_INDEX_DIMENSIONS),
        help="Comma-separated dimensions to promote. Default: 1024,512.",
    )
    parser.add_argument("--native-dim", type=int, default=int(_env("EMBEDDING_NATIVE_DIM", "1024")))
    parser.add_argument("--manifest-dir", default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--timeout", type=int, default=int(_env("QDRANT_TIMEOUT_SECONDS", "60")))
    parser.add_argument("--write-env", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dimensions = _build_order(_parse_dimensions(args.dimensions), args.native_dim)
    client = _qdrant_client(args.timeout)
    plan = _promotion_plan(
        client=client,
        target_table=args.target_table,
        alias_table=args.alias_table,
        dimensions=dimensions,
        timeout=args.timeout,
    )
    if not args.dry_run:
        _apply_aliases(client, plan, timeout=args.timeout)

    manifest = _write_alias_manifest(
        manifest_dir=Path(args.manifest_dir),
        target_table=args.target_table,
        alias_table=args.alias_table,
        dimensions=dimensions,
        plan=plan,
        applied=not args.dry_run,
    )
    if args.write_env and not args.dry_run:
        _update_env(
            Path(".env"),
            {
                "VECTOR_STORE_BACKEND": "qdrant",
                "VECTOR_TABLE_NAME": args.alias_table,
                "QDRANT_REQUIRE_ALIASES": "true",
            },
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "applied": not args.dry_run,
                "alias_table": args.alias_table,
                "target_table": args.target_table,
                "manifest": manifest.as_posix(),
                "aliases": [
                    {
                        "dimension": item["dimension"],
                        "alias": item["alias_collection"],
                        "target": item["target_collection"],
                        "chunks": item["chunks"],
                        "previous_target": item.get("previous_target"),
                    }
                    for item in plan
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _qdrant_client(timeout: int) -> Any:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise SystemExit("qdrant-client is required; run python3 -m pip install -r requirements.txt") from exc

    config = VectorStoreConfig.from_env()
    if config.qdrant_url:
        return QdrantClient(
            url=config.qdrant_url,
            api_key=config.qdrant_api_key or None,
            prefer_grpc=config.qdrant_prefer_grpc,
            timeout=timeout,
            check_compatibility=False,
        )
    if config.qdrant_local_path:
        return QdrantClient(path=config.qdrant_local_path, timeout=timeout)
    raise SystemExit("QDRANT_URL/QDRANT_API_KEY or QDRANT_LOCAL_PATH is required.")


def _promotion_plan(
    *,
    client: Any,
    target_table: str,
    alias_table: str,
    dimensions: list[int],
    timeout: int,
) -> list[dict[str, Any]]:
    aliases = {item.alias_name: item.collection_name for item in client.get_aliases().aliases}
    plan = []
    for dimension in dimensions:
        target_collection = table_name_for_dimension(target_table, dimension)
        alias_collection = table_name_for_dimension(alias_table, dimension)
        if target_collection == alias_collection:
            raise SystemExit("Target table and alias table must be different for blue-green promotion.")
        if not client.collection_exists(target_collection):
            raise SystemExit(f"Target Qdrant collection does not exist: {target_collection}")
        if alias_collection not in aliases and client.collection_exists(alias_collection):
            raise SystemExit(
                f"{alias_collection} is an existing collection, not an alias. "
                "Choose a different --alias-table."
            )
        chunks = int(client.count(collection_name=target_collection, exact=True, timeout=timeout).count)
        if chunks <= 0:
            raise SystemExit(f"Target Qdrant collection is empty: {target_collection}")
        plan.append(
            {
                "dimension": dimension,
                "target_collection": target_collection,
                "alias_collection": alias_collection,
                "previous_target": aliases.get(alias_collection),
                "chunks": chunks,
            }
        )
    return plan


def _apply_aliases(client: Any, plan: list[dict[str, Any]], *, timeout: int) -> None:
    from qdrant_client import models

    operations = []
    for item in plan:
        alias_name = item["alias_collection"]
        previous_target = item.get("previous_target")
        target = item["target_collection"]
        if previous_target == target:
            continue
        if previous_target:
            operations.append(
                models.DeleteAliasOperation(
                    delete_alias=models.DeleteAlias(alias_name=alias_name),
                )
            )
        operations.append(
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(collection_name=target, alias_name=alias_name),
            )
        )
    if operations:
        client.update_collection_aliases(operations, timeout=timeout)


def _write_alias_manifest(
    *,
    manifest_dir: Path,
    target_table: str,
    alias_table: str,
    dimensions: list[int],
    plan: list[dict[str, Any]],
    applied: bool,
) -> Path:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "alias_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "backend": "qdrant",
                "applied": applied,
                "target_table": target_table,
                "alias_table": alias_table,
                "dimensions": dimensions,
                "aliases": plan,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    main()
