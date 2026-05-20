from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from graph.build import build_graph


DEFAULT_SCENARIO = (
    "Build an internal API docs assistant over fast-moving SDK docs with strict "
    "citations, mixed markdown and code, and high exact-match terminology needs."
)


def split_bundle(bundle: str) -> dict[str, str]:
    files: dict[str, list[str]] = {}
    current_path: str | None = None
    for line in bundle.splitlines():
        if line.startswith("# file: "):
            current_path = line.removeprefix("# file: ").strip()
            files[current_path] = []
            continue
        if current_path is not None:
            files[current_path].append(line)
    return {path: "\n".join(lines).strip() + "\n" for path, lines in files.items()}


def write_bundle(bundle: str, out_dir: Path) -> list[Path]:
    written: list[Path] = []
    for relative_path, content in split_bundle(bundle).items():
        target = out_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


def maybe_validate(out_dir: Path) -> str:
    terraform = shutil.which("terraform")
    if terraform is None:
        return "skipped missing_terraform"
    subprocess.run([terraform, "fmt", "-recursive", "-check"], cwd=out_dir, check=True)
    subprocess.run([terraform, "init", "-backend=false"], cwd=out_dir, check=True)
    subprocess.run([terraform, "validate"], cwd=out_dir, check=True)
    return "ok"


def generate_bundle(scenario: str) -> str:
    previous_provider = os.environ.get("LLM_PROVIDER")
    os.environ["LLM_PROVIDER"] = "disabled"
    try:
        state = build_graph().invoke({"user_brief": scenario})
    finally:
        if previous_provider is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = previous_provider
    return str((state.draft_output or {}).get("terraform") or "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export advisor Terraform sketch to files.")
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO)
    parser.add_argument("--out", default="infra/generated/latest")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out)
    bundle = generate_bundle(args.scenario)
    written = write_bundle(bundle, out_dir)
    validation = maybe_validate(out_dir) if args.validate else "not_requested"
    print(
        "terraform_export=ok "
        f"out={out_dir} files={len(written)} validation={validation}"
    )


if __name__ == "__main__":
    main()
