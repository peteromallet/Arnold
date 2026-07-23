"""Fail-closed provenance check for editable Megaplan runtimes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse


RUNTIME_PROVENANCE_RECEIPT_SCHEMA = "arnold.megaplan.runtime_provenance_receipt.v1"
_RUNTIME_IDENTITY_KEYS = (
    "import_root",
    "source_revision",
    "editable_root",
    "editable_revision",
    "direct_url",
    "pth",
    "imports",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


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
        elif any(
            Path(entry).resolve(strict=False) != expected for entry in pth_entries
        ):
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


def normalized_runtime_identity(provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Project strict provenance into the content-addressed runtime identity."""

    identity = {key: provenance.get(key) for key in _RUNTIME_IDENTITY_KEYS}
    identity["editable_revision"] = str(
        provenance.get("editable_revision") or provenance.get("source_revision") or ""
    )
    identity["content_sha256"] = _canonical_sha256(identity)
    return identity


def runtime_provenance_receipt(provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Bind one runtime observation to the interpreter that made it."""

    executable = Path(sys.executable).resolve(strict=True)
    core = {
        "schema": RUNTIME_PROVENANCE_RECEIPT_SCHEMA,
        "interpreter": {
            "executable": str(executable),
            "sha256": _sha256_file(executable),
            "prefix": str(Path(sys.prefix).resolve(strict=True)),
            "base_prefix": str(Path(sys.base_prefix).resolve(strict=True)),
        },
        "provenance": dict(provenance),
        "runtime_identity": normalized_runtime_identity(provenance),
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-root", type=Path)
    parser.add_argument("--expected-revision", default="")
    parser.add_argument("--emit-receipt", action="store_true")
    parser.add_argument("--receipt-out", type=Path)
    parser.add_argument("--identity-out", type=Path)
    args = parser.parse_args(argv)
    payload = runtime_provenance(
        expected_root=args.expected_root,
        expected_revision=args.expected_revision,
    )
    receipt = runtime_provenance_receipt(payload)
    if args.receipt_out is not None:
        _atomic_write_json(args.receipt_out, receipt)
    if args.identity_out is not None:
        _atomic_write_json(args.identity_out, receipt["runtime_identity"])
    print(json.dumps(receipt if args.emit_receipt else payload, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
