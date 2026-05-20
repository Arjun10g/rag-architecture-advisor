from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any

import httpx

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - required by requirements, optional for direct reuse.
    load_dotenv = None

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))

from retrieval.vector_store import (
    _create_qdrant_payload_indexes,
    _qdrant_point_id,
    _qdrant_filter,
    table_name_for_dimension,
)
from scripts.build_vector_index import DEFAULT_INDEX_DIMENSIONS, _build_order, _parse_dimensions


CLOUD_ENDPOINT = "https://api.cloud.qdrant.io"
DEFAULT_CLUSTER_NAME = "rag-architecture-advisor"
DEFAULT_KEY_NAME = "rag-advisor-write-key"
DEFAULT_MANIFEST_DIR = "corpus/index/qdrant"
DEFAULT_LANCEDB_DIR = "corpus/index/lancedb"


def main() -> None:
    if load_dotenv:
        load_dotenv()

    parser = argparse.ArgumentParser(
        description="Provision Qdrant Cloud access and upload the 1024/512 vector collections."
    )
    parser.add_argument("--cluster-name", default=_env("QDRANT_CLUSTER_NAME", DEFAULT_CLUSTER_NAME))
    parser.add_argument("--cluster-id", default=_env("QDRANT_CLUSTER_ID", ""))
    parser.add_argument("--create-cluster", action="store_true")
    parser.add_argument("--template-cluster-id", default=_env("QDRANT_TEMPLATE_CLUSTER_ID", ""))
    parser.add_argument("--account-id", default=_account_id())
    parser.add_argument("--key-name", default=_env("QDRANT_DATABASE_KEY_NAME", DEFAULT_KEY_NAME))
    parser.add_argument("--table", default=_env("VECTOR_TABLE_NAME", "chunks"))
    parser.add_argument("--source-table", default="chunks")
    parser.add_argument(
        "--dimensions",
        default=_env("VECTOR_INDEX_DIMS", DEFAULT_INDEX_DIMENSIONS),
        help="Comma-separated dimensions to upload. Default: 1024,512.",
    )
    parser.add_argument("--native-dim", type=int, default=int(_env("EMBEDDING_NATIVE_DIM", "1024")))
    parser.add_argument("--source-lancedb", default=DEFAULT_LANCEDB_DIR)
    parser.add_argument("--manifest-dir", default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--batch-size", type=int, default=int(_env("QDRANT_UPLOAD_BATCH_SIZE", "128")))
    parser.add_argument("--timeout", type=int, default=int(_env("QDRANT_TIMEOUT_SECONDS", "60")))
    parser.add_argument("--wait-timeout", type=int, default=900)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--write-env", action="store_true", help="Persist QDRANT_URL/API key in .env.")
    parser.add_argument("--no-create-key", action="store_true")
    args = parser.parse_args()

    management_key = _management_key()
    account_id = args.account_id.strip()
    if not account_id:
        raise SystemExit("QDRANT_CLOUD_ACCOUNT_ID, QDRANT_ACCOUNT_ID, or QDRANT_ID is required.")

    cluster = _select_cluster(
        account_id=account_id,
        management_key=management_key,
        cluster_id=args.cluster_id.strip(),
        cluster_name=args.cluster_name.strip(),
        create_cluster=args.create_cluster,
        template_cluster_id=args.template_cluster_id.strip(),
        timeout=args.timeout,
        wait_timeout=args.wait_timeout,
    )
    endpoint = _cluster_endpoint(cluster)
    database_key = _env("QDRANT_API_KEY", "")
    created_database_key = False
    if not database_key and not args.no_create_key:
        database_key = _create_database_key(
            account_id=account_id,
            cluster_id=str(cluster["id"]),
            management_key=management_key,
            key_name=args.key_name,
            timeout=args.timeout,
        )
        created_database_key = True
    if not database_key:
        raise SystemExit("QDRANT_API_KEY is required, or omit --no-create-key to create one.")

    dimensions = _build_order(_parse_dimensions(args.dimensions), args.native_dim)
    client = _qdrant_client(endpoint, database_key, args.timeout)
    built = _upload_from_lancedb(
        client=client,
        source_dir=Path(args.source_lancedb),
        table_base=args.table,
        source_table_base=args.source_table,
        dimensions=dimensions,
        rebuild=args.rebuild,
        batch_size=args.batch_size,
        timeout=args.timeout,
    )
    manifest = _write_manifest(
        manifest_dir=Path(args.manifest_dir),
        endpoint=endpoint,
        cluster=cluster,
        table_base=args.table,
        dimensions=dimensions,
        built=built,
    )

    if args.write_env:
        _update_env(
            Path(".env"),
            {
                "QDRANT_CLOUD_ACCOUNT_ID": account_id,
                "QDRANT_CLUSTER_ID": str(cluster["id"]),
                "QDRANT_URL": endpoint,
                "QDRANT_API_KEY": database_key,
                "VECTOR_STORE_BACKEND": "qdrant",
                "VECTOR_TABLE_NAME": args.table,
                "VECTOR_INDEX_DIMS": ",".join(str(dimension) for dimension in dimensions),
            },
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "cluster": {
                    "id": cluster.get("id"),
                    "name": cluster.get("name"),
                    "phase": (cluster.get("state") or {}).get("phase"),
                    "nodes_up": (cluster.get("state") or {}).get("nodesUp"),
                    "endpoint": endpoint,
                },
                "database_key": "created" if created_database_key else "env",
                "manifest": manifest.as_posix(),
                "indexes": built,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _account_id() -> str:
    return (
        _env("QDRANT_CLOUD_ACCOUNT_ID")
        or _env("QDRANT_ACCOUNT_ID")
        or _env("QDRANT_ID")
    )


def _management_key() -> str:
    value = (
        _env("QDRANT_CLOUD_KEY")
        or _env("QDRANT_CLOUD_API_KEY")
        or _env("QDRANT_CLOUD_MANAGEMENT_KEY")
    )
    if not value:
        raise SystemExit(
            "QDRANT_CLOUD_KEY, QDRANT_CLOUD_API_KEY, or QDRANT_CLOUD_MANAGEMENT_KEY is required."
        )
    return value


def _cloud_headers(management_key: str) -> dict[str, str]:
    return {
        "Authorization": f"apikey {management_key}",
        "Content-Type": "application/json",
    }


def _cloud_get(path: str, management_key: str, timeout: int) -> dict[str, Any]:
    response = httpx.get(
        f"{CLOUD_ENDPOINT}{path}",
        headers=_cloud_headers(management_key),
        timeout=timeout,
    )
    return _cloud_payload(response)


def _cloud_post(path: str, management_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = httpx.post(
        f"{CLOUD_ENDPOINT}{path}",
        headers=_cloud_headers(management_key),
        json=payload,
        timeout=timeout,
    )
    return _cloud_payload(response)


def _cloud_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = {"message": response.text}
    if response.is_error:
        message = payload.get("message") or payload.get("error") or response.text
        raise SystemExit(f"Qdrant Cloud API failed with {response.status_code}: {message}")
    return payload


def _select_cluster(
    *,
    account_id: str,
    management_key: str,
    cluster_id: str,
    cluster_name: str,
    create_cluster: bool,
    template_cluster_id: str,
    timeout: int,
    wait_timeout: int,
) -> dict[str, Any]:
    clusters = _cloud_get(
        f"/api/cluster/v1/accounts/{account_id}/clusters",
        management_key,
        timeout,
    ).get("items", [])
    if cluster_id:
        matches = [cluster for cluster in clusters if cluster.get("id") == cluster_id]
    else:
        matches = [cluster for cluster in clusters if cluster.get("name") == cluster_name]
        if not matches and len(clusters) == 1 and not create_cluster:
            matches = clusters
    if not matches and create_cluster:
        return _create_cluster_from_template(
            account_id=account_id,
            management_key=management_key,
            cluster_name=cluster_name,
            template_cluster_id=template_cluster_id,
            clusters=clusters,
            timeout=timeout,
            wait_timeout=wait_timeout,
        )
    if not matches:
        raise SystemExit(
            "No Qdrant cluster matched. Create one in Qdrant Cloud or pass --cluster-id. "
            "Pass --create-cluster to create a dedicated cluster intentionally."
        )
    cluster = _cloud_get(
        f"/api/cluster/v1/accounts/{account_id}/clusters/{matches[0]['id']}",
        management_key,
        timeout,
    ).get("cluster")
    if not cluster:
        raise SystemExit("Qdrant Cloud returned no cluster details.")
    phase = (cluster.get("state") or {}).get("phase", "")
    if "HEALTHY" not in phase:
        raise SystemExit(f"Qdrant cluster is not healthy yet: {phase}")
    return cluster


def _create_cluster_from_template(
    *,
    account_id: str,
    management_key: str,
    cluster_name: str,
    template_cluster_id: str,
    clusters: list[dict[str, Any]],
    timeout: int,
    wait_timeout: int,
) -> dict[str, Any]:
    if not cluster_name:
        raise SystemExit("--cluster-name is required when creating a cluster.")
    template_summary = None
    if template_cluster_id:
        template_summary = next(
            (cluster for cluster in clusters if cluster.get("id") == template_cluster_id),
            None,
        )
    if template_summary is None:
        if not clusters:
            raise SystemExit(
                "No template cluster exists. Create a first Qdrant Cloud cluster in the console "
                "or pass explicit cluster configuration after adding it to this script."
            )
        template_summary = clusters[0]

    template = _cloud_get(
        f"/api/cluster/v1/accounts/{account_id}/clusters/{template_summary['id']}",
        management_key,
        timeout,
    ).get("cluster")
    if not template:
        raise SystemExit("Qdrant Cloud returned no template cluster details.")

    config = _cluster_create_configuration(template.get("configuration") or {})
    payload = {
        "cluster": {
            "accountId": account_id,
            "name": cluster_name,
            "cloudProviderId": template.get("cloudProviderId"),
            "cloudProviderRegionId": template.get("cloudProviderRegionId"),
            "configuration": config,
            "labels": [
                {"key": "app", "value": "rag-architecture-advisor"},
                {"key": "managed-by", "value": "codex-bootstrap"},
            ],
        }
    }
    response = _cloud_post(
        f"/api/cluster/v1/accounts/{account_id}/clusters",
        management_key,
        payload,
        timeout,
    )
    created = response.get("cluster")
    if not created:
        raise SystemExit("Qdrant Cloud created no cluster response.")
    return _wait_for_cluster(
        account_id=account_id,
        management_key=management_key,
        cluster_id=created["id"],
        timeout=timeout,
        wait_timeout=wait_timeout,
    )


def _cluster_create_configuration(template_config: dict[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {
        "numberOfNodes": template_config.get("numberOfNodes", 1),
        "packageId": template_config.get("packageId"),
    }
    for key in (
        "version",
        "additionalResources",
        "clusterStorageConfiguration",
        "restartPolicy",
        "rebalanceStrategy",
        "serviceType",
    ):
        value = template_config.get(key)
        if value:
            config[key] = value
    database_config = template_config.get("databaseConfiguration") or {}
    inference = database_config.get("inference")
    if inference:
        config["databaseConfiguration"] = {"inference": inference}
    if not config["packageId"]:
        raise SystemExit("Template cluster is missing configuration.packageId.")
    return config


def _wait_for_cluster(
    *,
    account_id: str,
    management_key: str,
    cluster_id: str,
    timeout: int,
    wait_timeout: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + wait_timeout
    last_phase = ""
    while time.monotonic() < deadline:
        cluster = _cloud_get(
            f"/api/cluster/v1/accounts/{account_id}/clusters/{cluster_id}",
            management_key,
            timeout,
        ).get("cluster")
        if not cluster:
            raise SystemExit("Qdrant Cloud returned no cluster details while waiting.")
        phase = (cluster.get("state") or {}).get("phase", "")
        last_phase = phase
        if phase == "CLUSTER_PHASE_HEALTHY":
            return cluster
        if "FAILED" in phase:
            raise SystemExit(f"Qdrant cluster creation failed: {phase}")
        time.sleep(10)
    raise SystemExit(f"Timed out waiting for Qdrant cluster to become healthy; last phase={last_phase}")


def _cluster_endpoint(cluster: dict[str, Any]) -> str:
    endpoint = ((cluster.get("state") or {}).get("endpoint") or {}).get("url", "")
    if not endpoint:
        raise SystemExit("Qdrant cluster endpoint is missing.")
    return endpoint


def _create_database_key(
    *,
    account_id: str,
    cluster_id: str,
    management_key: str,
    key_name: str,
    timeout: int,
) -> str:
    payload = {
        "databaseApiKey": {
            "accountId": account_id,
            "clusterId": cluster_id,
            "name": key_name,
        }
    }
    response = _cloud_post(
        f"/api/cluster/auth/v2/accounts/{account_id}/database-api-keys",
        management_key,
        payload,
        timeout,
    )
    key = ((response.get("databaseApiKey") or response.get("database_api_key") or {}).get("key") or "")
    if not key:
        raise SystemExit("Qdrant Cloud created a database key response without a key.")
    return key


def _qdrant_client(endpoint: str, database_key: str, timeout: int) -> Any:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise SystemExit("qdrant-client is required; run python3 -m pip install -r requirements.txt") from exc
    client = QdrantClient(
        url=endpoint,
        api_key=database_key,
        prefer_grpc=False,
        timeout=timeout,
        check_compatibility=False,
    )
    _wait_for_database_key(client)
    return client


def _wait_for_database_key(client: Any, timeout_seconds: int = 180) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            client.get_collections()
            return
        except Exception as exc:
            last_error = exc
            if "403" not in str(exc) and "forbidden" not in str(exc).lower():
                raise
            time.sleep(10)
    raise SystemExit(f"Qdrant database key did not become usable before timeout: {last_error}")


def _upload_from_lancedb(
    *,
    client: Any,
    source_dir: Path,
    table_base: str,
    source_table_base: str,
    dimensions: list[int],
    rebuild: bool,
    batch_size: int,
    timeout: int,
) -> list[dict[str, Any]]:
    try:
        import lancedb
        from qdrant_client import models
    except ImportError as exc:
        raise SystemExit("lancedb and qdrant-client are required for the upload path.") from exc

    db = lancedb.connect(source_dir.as_posix())
    built = []
    for dimension in dimensions:
        collection_name = table_name_for_dimension(table_base, dimension)
        table_name = table_name_for_dimension(source_table_base, dimension)
        if rebuild and client.collection_exists(collection_name):
            client.delete_collection(collection_name=collection_name, timeout=timeout)
        if not client.collection_exists(collection_name):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
                timeout=timeout,
            )
            _create_qdrant_payload_indexes(client, collection_name, timeout)

        frame = db.open_table(table_name).to_pandas()
        expected = len(frame)
        current = int(client.count(collection_name=collection_name, exact=True, timeout=timeout).count)
        matching = _matching_collection_count(
            client,
            collection_name,
            frame,
            timeout=timeout,
        )
        if current and not (current == expected and matching == expected):
            if not rebuild:
                raise SystemExit(
                    f"Qdrant collection {collection_name} already contains {current} point(s) "
                    "or mixed payloads. Refusing to overwrite without --rebuild."
                )
            client.delete_collection(collection_name=collection_name, timeout=timeout)
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
                timeout=timeout,
            )
            _create_qdrant_payload_indexes(client, collection_name, timeout)
            current = 0
        if current != expected:
            _upload_frame_points(
                client,
                collection_name,
                frame,
                batch_size=batch_size,
                timeout=timeout,
            )
            current = int(client.count(collection_name=collection_name, exact=True, timeout=timeout).count)
        if current != expected:
            raise SystemExit(
                f"Qdrant collection {collection_name} has {current} points; expected {expected}."
            )
        built.append({"dimension": dimension, "collection": collection_name, "chunks": current})
    return built


def _matching_collection_count(
    client: Any,
    collection_name: str,
    frame: Any,
    *,
    timeout: int,
) -> int:
    first = frame.iloc[0]
    return int(
        client.count(
            collection_name=collection_name,
            count_filter=_qdrant_filter(
                None,
                {
                    "embedding_model": str(first["embedding_model"]),
                    "embedding_dimension": int(first["embedding_dimension"]),
                    "embedding_native_dimension": int(first["embedding_native_dimension"]),
                },
            ),
            exact=True,
            timeout=timeout,
        ).count
    )


def _upload_frame_points(
    client: Any,
    collection_name: str,
    frame: Any,
    *,
    batch_size: int,
    timeout: int,
) -> None:
    from qdrant_client import models

    points = []
    for row in frame.to_dict(orient="records"):
        chunk_id = str(row["chunk_id"])
        vector = _as_float_list(row.pop("vector"))
        payload = {key: _json_safe(value) for key, value in row.items()}
        points.append(
            models.PointStruct(
                id=_qdrant_point_id(chunk_id),
                vector=vector,
                payload=payload,
            )
        )
        if len(points) >= batch_size:
            client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
                timeout=timeout,
            )
            points = []
    if points:
        client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
            timeout=timeout,
        )


def _as_float_list(value: Any) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [float(item) for item in value]


def _json_safe(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _write_manifest(
    *,
    manifest_dir: Path,
    endpoint: str,
    cluster: dict[str, Any],
    table_base: str,
    dimensions: list[int],
    built: list[dict[str, Any]],
) -> Path:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "vector_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "backend": "qdrant",
                "qdrant_url": endpoint,
                "cluster_id": cluster.get("id"),
                "cluster_name": cluster.get("name"),
                "table_base": table_base,
                "dimensions": dimensions,
                "indexes": built,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _update_env(path: Path, updates: dict[str, str]) -> None:
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen = set()
    output = []
    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
