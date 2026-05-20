from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience.
    load_dotenv = None

from app import advise_api
from scripts.api_output_probe import DEFAULT_BRIEF, _validate_public_payload


REQUIRED_FILES = (
    "app.py",
    "README.md",
    ".env.example",
    "corpus/manifest.yaml",
    "scripts/api_output_probe.py",
    "scripts/hf_generation_probe.py",
    "eval/gold/v0_2_expanded.json",
    "eval/gold/v0_4_answer_quality.json",
    "eval/gold/v0_5_panel_quality.json",
)


def _check(name: str, ok: bool, detail: str, checks: list[dict[str, Any]]) -> None:
    checks.append({"name": name, "ok": ok, "detail": detail})


def _secret_present(*keys: str) -> bool:
    return any(bool(os.getenv(key, "").strip()) for key in keys)


def _nonempty_env(key: str) -> bool:
    return bool(os.getenv(key, "").strip())


def _vector_manifest_ok(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"
    dimensions = {int(value) for value in payload.get("dimensions") or []}
    indexes = payload.get("indexes") or []
    indexed_dimensions = {int(item.get("dimension")) for item in indexes if item.get("dimension")}
    required = {1024, 512}
    if not required.issubset(dimensions | indexed_dimensions):
        return False, "manifest must include 1024 and 512 dimensional indexes"
    return True, f"dimensions={sorted(dimensions | indexed_dimensions)}"


def _validate_direct_public_api() -> tuple[bool, str]:
    previous = os.environ.get("LLM_PROVIDER")
    os.environ["LLM_PROVIDER"] = "disabled"
    try:
        payload = advise_api(DEFAULT_BRIEF)
        summary = _validate_public_payload(payload)
    finally:
        if previous is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = previous
    return True, f"topology={summary['topology']} chunks={summary['reasoning_chunks']}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check release-readiness guardrails without printing secrets."
    )
    parser.add_argument("--profile", choices=["demo", "production"], default="demo")
    parser.add_argument("--require-auth", action="store_true")
    parser.add_argument("--require-vector-index", action="store_true")
    parser.add_argument("--vector-manifest", default="corpus/index/lancedb/vector_manifest.json")
    args = parser.parse_args()

    if load_dotenv:
        load_dotenv()

    checks: list[dict[str, Any]] = []
    root = Path.cwd()

    for relative in REQUIRED_FILES:
        path = root / relative
        _check(f"file:{relative}", path.exists(), "present" if path.exists() else "missing", checks)

    try:
        ok, detail = _validate_direct_public_api()
    except Exception as exc:
        ok, detail = False, str(exc)
    _check("public_api_contract", ok, detail, checks)

    provider = os.getenv("LLM_PROVIDER", "hf").strip().lower()
    _check("llm_provider_configured", provider in {"hf", "disabled"}, f"LLM_PROVIDER={provider}", checks)
    _check(
        "hf_model_configured",
        _nonempty_env("HF_INFERENCE_MODEL"),
        f"model={'set' if _nonempty_env('HF_INFERENCE_MODEL') else 'missing'}",
        checks,
    )

    retrieval_mode = os.getenv("RETRIEVAL_MODE", "lexical").strip().lower()
    known_modes = {"lexical", "dense", "hybrid", "dense_colbert", "hybrid_colbert", "colbert"}
    _check(
        "retrieval_mode",
        retrieval_mode in known_modes,
        f"RETRIEVAL_MODE={retrieval_mode}",
        checks,
    )

    if args.profile == "production":
        _check(
            "hf_token_secret",
            _secret_present("HF_TOKEN", "HF_ACCESS_TOKEN"),
            "set" if _secret_present("HF_TOKEN", "HF_ACCESS_TOKEN") else "missing",
            checks,
        )
        _check(
            "audit_log_path",
            _nonempty_env("ADVISOR_AUDIT_LOG_PATH"),
            "set" if _nonempty_env("ADVISOR_AUDIT_LOG_PATH") else "missing",
            checks,
        )
        args.require_auth = True
        if retrieval_mode != "lexical":
            args.require_vector_index = True

    if args.require_auth:
        username_set = _nonempty_env("GRADIO_AUTH_USERNAME")
        password_set = _nonempty_env("GRADIO_AUTH_PASSWORD")
        _check(
            "gradio_auth",
            username_set and password_set,
            "set" if username_set and password_set else "missing username/password pair",
            checks,
        )

    if args.require_vector_index:
        ok, detail = _vector_manifest_ok(Path(args.vector_manifest))
        _check("vector_manifest", ok, detail, checks)

    failures = [check for check in checks if not check["ok"]]
    print(
        json.dumps(
            {
                "profile": args.profile,
                "status": "ok" if not failures else "failed",
                "checks": checks,
                "failure_count": len(failures),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
