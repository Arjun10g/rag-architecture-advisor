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
    manifest = manifest_dir / "vector_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "backend": "lancedb",
                "dimensions": [1024, 512],
                "indexes": [
                    {"dimension": 1024, "table": "chunks_dim_1024", "chunks": 10},
                    {"dimension": 512, "table": "chunks_dim_512", "chunks": 10},
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
            "DEEP_LATENCY_SLO_P50_MS": "25000",
            "DEEP_LATENCY_SLO_P99_MS": "35000",
            "GRADIO_AUTH_PASSWORD": "smoke-password",
            "GRADIO_AUTH_USERNAME": "smoke-user",
            "HF_TOKEN": env.get("HF_TOKEN") or "smoke-token",
            "LATENCY_SLO_P50_MS": "10000",
            "LATENCY_SLO_P99_MS": "15000",
            "LLM_PROVIDER": "disabled",
            "RATE_LIMIT_ENABLED": "true",
            "RATE_LIMIT_MAX_REQUESTS": "100",
            "RATE_LIMIT_WINDOW_SECONDS": "60",
            "RETRIEVAL_MODE": "hybrid",
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
    finally:
        shutil.rmtree(manifest_dir, ignore_errors=True)
        shutil.rmtree(audit_dir, ignore_errors=True)

    payload = json.loads(completed.stdout)
    if payload.get("status") != "ok":
        raise AssertionError(completed.stdout)
    print("production_config_smoke=ok")


if __name__ == "__main__":
    main()
