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


def _distribution() -> importlib.metadata.Distribution | None:
    try:
        return importlib.metadata.distribution("arnold")
    except importlib.metadata.PackageNotFoundError:
        return None


def _direct_url_identity() -> tuple[Path | None, dict[str, Any]]:
    distribution = _distribution()
    if distribution is None:
        return None, {}
    try:
        direct_url = distribution.read_text("direct_url.json")
        payload = json.loads(direct_url or "{}")
    except (json.JSONDecodeError, OSError):
        return None, {}
    if not bool((payload.get("dir_info") or {}).get("editable")):
        return None, payload
    parsed = urlparse(str(payload.get("url") or ""))
    if parsed.scheme != "file":
        return None, payload
    return Path(unquote(parsed.path)).resolve(), payload


def _editable_root() -> Path | None:
    root, _payload = _direct_url_identity()
    return root


def _pth_identity() -> list[dict[str, Any]]:
    """Return path-bearing ``.pth`` entries owned by the Arnold distribution."""

    distribution = _distribution()
    if distribution is None:
        return []
    records: list[dict[str, Any]] = []
    for relative in distribution.files or ():
        if not str(relative).endswith(".pth"):
            continue
        path = Path(distribution.locate_file(relative)).resolve(strict=False)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            records.append({"path": str(path), "entries": [], "readable": False})
            continue
        entries: list[str] = []
        for raw in lines:
            value = raw.strip()
            if not value or value.startswith(("#", "import ")):
                continue
            candidate = Path(value).expanduser()
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            entries.append(str(candidate.resolve(strict=False)))
        records.append({"path": str(path), "entries": entries, "readable": True})
    return records


def runtime_provenance(
    *,
    expected_root: Path | None = None,
    expected_revision: str = "",
) -> dict[str, Any]:
    import arnold
    import arnold_pipelines
    import arnold_pipelines.megaplan

    import_root = Path(arnold_pipelines.__file__).resolve().parents[1]
    editable_root, direct_url = _direct_url_identity()
    pth = _pth_identity()
    source_revision = _git_revision(import_root)
    expected = expected_root.resolve() if expected_root is not None else None
    imports = {
        "arnold": str(Path(arnold.__file__).resolve()),
        "arnold_pipelines": str(Path(arnold_pipelines.__file__).resolve()),
        "megaplan": str(Path(arnold_pipelines.megaplan.__file__).resolve()),
    }
    errors: list[str] = []
    if expected is not None and import_root != expected:
        errors.append("import_root_mismatch")
    if expected is not None and editable_root != expected:
        errors.append("editable_metadata_mismatch")
    if expected is not None:
        mismatched_imports = [
            name
            for name, value in imports.items()
            if not Path(value).is_relative_to(expected)
        ]
        if mismatched_imports:
            errors.append("module_import_root_mismatch")
        pth_entries = [
            entry
            for record in pth
            for entry in record.get("entries", [])
            if isinstance(entry, str)
        ]
        if not pth or not pth_entries:
            errors.append("editable_pth_missing")
        elif any(Path(entry).resolve(strict=False) != expected for entry in pth_entries):
            errors.append("editable_pth_mismatch")
        if any(not bool(record.get("readable")) for record in pth):
            errors.append("editable_pth_unreadable")
    if expected_revision and source_revision != expected_revision:
        errors.append("source_revision_mismatch")
    return {
        "ok": not errors,
        "errors": errors,
        "expected_root": str(expected) if expected is not None else "",
        "expected_revision": expected_revision,
        "import_root": str(import_root),
        "editable_root": str(editable_root) if editable_root is not None else "",
        "direct_url": direct_url,
        "pth": pth,
        "source_revision": source_revision,
        "runtime_revision": source_revision,
        "imports": imports,
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
