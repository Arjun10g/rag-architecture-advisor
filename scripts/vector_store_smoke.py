from __future__ import annotations

from pathlib import Path
import sys
import tempfile

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))


class FakeEmbedder:
    def encode(self, texts: list[str], *, is_query: bool, dimension: int) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def main() -> None:
    try:
        import lancedb
    except ImportError:
        print("vector_store_smoke=skipped missing_lancedb")
        return

    from retrieval.chunking import Chunk
    from retrieval.embeddings import EmbeddingConfig
    from retrieval.vector_store import (
        LanceDBVectorIndex,
        QdrantVectorIndex,
        _qdrant_point_id,
        _row_for_chunk,
        table_name_for_dimension,
    )

    embedding_config = EmbeddingConfig(
        model_name="smoke-test-model",
        native_dimension=2,
        dimensions=(2,),
    )
    chunks = [
        Chunk(
            text_original="Hybrid retrieval notes",
            text_for_embedding="Hybrid retrieval notes",
            source_path="corpus/demo.md",
            chunk_index=0,
            title="Demo",
            section_path=["Demo"],
            element_type="prose",
            metadata={"namespace": "knowledge", "domain": "retrieval"},
        ),
        Chunk(
            text_original="Routing notes",
            text_for_embedding="Routing notes",
            source_path="corpus/routing.md",
            chunk_index=0,
            title="Routing",
            section_path=["Routing"],
            element_type="prose",
            metadata={"namespace": "routing", "domain": "routing"},
        ),
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        db = lancedb.connect(temp_dir)
        table_name = table_name_for_dimension("chunks", 2)
        table = db.create_table(
            table_name,
            data=[
                _row_for_chunk(chunks[0], [1.0, 0.0], embedding_config, 2),
                _row_for_chunk(chunks[1], [0.0, 1.0], embedding_config, 2),
            ],
        )

        index = LanceDBVectorIndex(chunks, table, FakeEmbedder(), 2, table_name=table_name)
        if index.table_name != "chunks_dim_2":
            raise SystemExit("dimension-specific LanceDB table name was not preserved")
        results = index.search(
            "hybrid",
            top_k=1,
            namespace="knowledge",
            filters={"domain": "retrieval"},
        )
        if not results or results[0].chunk.chunk_id != chunks[0].chunk_id:
            raise SystemExit("LanceDB adapter returned the wrong chunk")

    try:
        from qdrant_client import QdrantClient, models
    except ImportError:
        print("vector_store_smoke=skipped missing_qdrant_client")
        return

    client = QdrantClient(location=":memory:")
    collection_name = table_name_for_dimension("chunks", 2)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE),
    )
    points = []
    for chunk, vector in ((chunks[0], [1.0, 0.0]), (chunks[1], [0.0, 1.0])):
        row = _row_for_chunk(chunk, vector, embedding_config, 2)
        row.pop("vector", None)
        points.append(
            models.PointStruct(
                id=_qdrant_point_id(chunk.chunk_id),
                vector=vector,
                payload=row,
            )
        )
    client.upsert(collection_name=collection_name, points=points, wait=True)

    qdrant_index = QdrantVectorIndex(
        chunks,
        client,
        FakeEmbedder(),
        2,
        collection_name=collection_name,
    )
    results = qdrant_index.search(
        "hybrid",
        top_k=1,
        namespace="knowledge",
        filters={"domain": "retrieval"},
    )
    if not results or results[0].chunk.chunk_id != chunks[0].chunk_id:
        raise SystemExit("Qdrant adapter returned the wrong chunk")

    print("vector_store_smoke=ok")


if __name__ == "__main__":
    main()
