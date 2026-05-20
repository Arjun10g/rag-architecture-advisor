from __future__ import annotations

from pathlib import Path
import sys
import tempfile

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.qdrant_blue_green_promote import _apply_aliases, _promotion_plan


def main() -> None:
    try:
        from qdrant_client import QdrantClient, models
    except ImportError:
        print("qdrant_alias_smoke=skipped missing_qdrant_client")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        client = QdrantClient(path=temp_dir)
        for name in ("chunks_blue_dim_1024", "chunks_blue_dim_512", "chunks_green_dim_1024", "chunks_green_dim_512"):
            dimension = 1024 if name.endswith("1024") else 512
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )
            client.upsert(
                collection_name=name,
                points=[
                    models.PointStruct(
                        id=1,
                        vector=[0.0] * dimension,
                        payload={"chunk_id": f"{name}-1"},
                    )
                ],
                wait=True,
            )

        blue = _promotion_plan(
            client=client,
            target_table="chunks_blue",
            alias_table="chunks_live",
            dimensions=[1024, 512],
            timeout=30,
        )
        _apply_aliases(client, blue, timeout=30)
        aliases = {item.alias_name: item.collection_name for item in client.get_aliases().aliases}
        if aliases.get("chunks_live_dim_1024") != "chunks_blue_dim_1024":
            raise AssertionError("blue alias was not created")

        green = _promotion_plan(
            client=client,
            target_table="chunks_green",
            alias_table="chunks_live",
            dimensions=[1024, 512],
            timeout=30,
        )
        _apply_aliases(client, green, timeout=30)
        aliases = {item.alias_name: item.collection_name for item in client.get_aliases().aliases}
        if aliases.get("chunks_live_dim_1024") != "chunks_green_dim_1024":
            raise AssertionError("green alias was not promoted")
        if aliases.get("chunks_live_dim_512") != "chunks_green_dim_512":
            raise AssertionError("512 alias was not promoted")

    print("qdrant_alias_smoke=ok")


if __name__ == "__main__":
    main()
