from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.export_terraform import generate_bundle, split_bundle, write_bundle


def main() -> None:
    bundle = generate_bundle("Build an internal API docs assistant over fast-moving SDK docs.")
    files = split_bundle(bundle)
    if "main.tf" not in files or "modules/database/main.tf" not in files:
        raise AssertionError("export bundle is missing required Terraform files")

    out_dir = Path(tempfile.mkdtemp(prefix="rag-advisor-tf-"))
    try:
        written = write_bundle(bundle, out_dir)
        for relative_path in ["main.tf", "variables.tf", "modules/database/main.tf"]:
            if not (out_dir / relative_path).exists():
                raise AssertionError(f"export did not write {relative_path}")
        print(f"terraform_export_smoke=ok files={len(written)} out={out_dir}")
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
