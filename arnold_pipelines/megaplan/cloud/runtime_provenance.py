"""Fail-closed provenance check for editable Megaplan runtimes."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


def _git_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _editable_root() -> Path | None:
    try:
        direct_url = importlib.metadata.distribution("arnold").read_text("direct_url.json")
        payload = json.loads(direct_url or "{}")
    except (importlib.metadata.PackageNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not bool((payload.get("dir_info") or {}).get("editable")):
        return None
    parsed = urlparse(str(payload.get("url") or ""))
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path)).resolve()


def runtime_provenance(
    *,
    expected_root: Path | None = None,
    expected_revision: str = "",
) -> dict[str, Any]:
    import arnold
    import arnold_pipelines
    import arnold_pipelines.megaplan

    import_root = Path(arnold_pipelines.__file__).resolve().parents[1]
    editable_root = _editable_root()
    source_revision = _git_revision(import_root)
    expected = expected_root.resolve() if expected_root is not None else None
    errors: list[str] = []
    if expected is not None and import_root != expected:
        errors.append("import_root_mismatch")
    if expected is not None and editable_root != expected:
        errors.append("editable_metadata_mismatch")
    if expected_revision and source_revision != expected_revision:
        errors.append("source_revision_mismatch")
    return {
        "ok": not errors,
        "errors": errors,
        "expected_root": str(expected) if expected is not None else "",
        "expected_revision": expected_revision,
        "import_root": str(import_root),
        "editable_root": str(editable_root) if editable_root is not None else "",
        "source_revision": source_revision,
        "runtime_revision": source_revision,
        "imports": {
            "arnold": str(Path(arnold.__file__).resolve()),
            "arnold_pipelines": str(Path(arnold_pipelines.__file__).resolve()),
            "megaplan": str(Path(arnold_pipelines.megaplan.__file__).resolve()),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-root", type=Path)
    parser.add_argument("--expected-revision", default="")
    args = parser.parse_args(argv)
    payload = runtime_provenance(
        expected_root=args.expected_root,
        expected_revision=args.expected_revision,
    )
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
