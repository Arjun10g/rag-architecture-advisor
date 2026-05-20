from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_dir = Path(tempfile.mkdtemp(prefix="rag-vector-manifest-"))
    audit_dir = root / ".readiness-audit"
    audit_path = audit_dir / "advisor-audit.jsonl"
    try:
        import lancedb
    except ImportError:
        lancedb = None

    if lancedb is None:
        print("production_config_smoke=skipped missing_lancedb")
        return

    db = lancedb.connect(manifest_dir.as_posix())
    db.create_table(
        "chunks_dim_1024",
        data=[{"chunk_id": "smoke-1024", "vector": [0.0] * 1024}],
        mode="overwrite",
    )
    db.create_table(
        "chunks_dim_512",
        data=[{"chunk_id": "smoke-512", "vector": [0.0] * 512}],
        mode="overwrite",
    )

    manifest = manifest_dir / "vector_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "backend": "lancedb",
                "dimensions": [1024, 512],
                "indexes": [
                    {"dimension": 1024, "table": "chunks_dim_1024", "chunks": 1},
                    {"dimension": 512, "table": "chunks_dim_512", "chunks": 1},
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "ADVISOR_AUDIT_LOG_PATH": str(audit_path),
            "ADVISOR_AUDIT_FAILURE_MODE": "fail",
            "ADVISOR_CONCURRENCY_LIMIT": "2",
            "ADVISOR_QUEUE_MAX_SIZE": "32",
            "ALLOW_ANONYMOUS_PUBLIC": "false",
            "DEEP_LATENCY_SLO_P50_MS": "25000",
            "DEEP_LATENCY_SLO_P99_MS": "35000",
            "DEEP_RESEARCH_MAX_FULL_TEXT_LINKS": "4",
            "DEEP_THINKING_ENABLED": "true",
            "GRADIO_AUTH_PASSWORD": "smoke-password",
            "GRADIO_AUTH_USERNAME": "smoke-user",
            "HF_TOKEN": env.get("HF_TOKEN") or "smoke-token",
            "LATENCY_SLO_P50_MS": "12000",
            "LATENCY_SLO_P99_MS": "20000",
            "LLM_PROVIDER": "disabled",
            "MAX_BRIEF_CHARS": "4000",
            "MAX_CONFLICT_CHARS": "1000",
            "MAX_ELICITATION_CHARS": "2000",
            "METRICS_AUTH_TOKEN": "smoke-metrics-token",
            "PUBLIC_ACCESS_MODE": "authenticated",
            "QDRANT_REQUIRE_ALIASES": "false",
            "RATE_LIMIT_ENABLED": "true",
            "RATE_LIMIT_ADVISOR_DEEP_MAX_REQUESTS": "6",
            "RATE_LIMIT_ADVISOR_DEEP_WINDOW_SECONDS": "300",
            "RATE_LIMIT_MAX_REQUESTS": "100",
            "RATE_LIMIT_WINDOW_SECONDS": "60",
            "RETRIEVAL_MODE": "hybrid",
            "SHOW_RAW_TRACE": "false",
            "SPECIALIST_SHARED_DENSE_QUERY": "true",
            "VECTOR_STORE_BACKEND": "lancedb",
        }
    )
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/production_readiness_check.py",
                "--profile",
                "production",
                "--vector-manifest",
                str(manifest),
            ],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(exc.stdout)
        print(exc.stderr, file=sys.stderr)
        raise
    finally:
        shutil.rmtree(manifest_dir, ignore_errors=True)
        shutil.rmtree(audit_dir, ignore_errors=True)

    payload = json.loads(completed.stdout)
    if payload.get("status") != "ok":
        raise AssertionError(completed.stdout)
    print("production_config_smoke=ok")


if __name__ == "__main__":
    main()
