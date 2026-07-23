"""Prepare and attest the vendored Shannon Bun dependency runtime.

The Python wheel intentionally ships Shannon's source manifest and lockfile,
not ``node_modules``.  Every immutable runtime must therefore materialize the
locked dependency tree after the wheel/editable install and bind that tree
into runtime provenance before it may launch a Shannon worker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping


SHANNON_DEPENDENCY_SCHEMA = "arnold.megaplan.shannon_dependencies.v1"
_INSTALL_ARGS = (
    "install",
    "--frozen-lockfile",
    "--production",
    "--ignore-scripts",
)
_REQUIRED_PACKAGES = (
    "@anthropic-ai/claude-agent-sdk",
    "commander",
    "zod",
)
_SMOKE_PROGRAM = """
await import("./index.ts");
const commander = await import("commander");
if (typeof commander.Command !== "function") {
  throw new Error("commander Command export missing");
}
process.stdout.write("shannon-index-commander-ok\\n");
""".strip()


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


def _default_vendor_root() -> Path:
    return Path(__file__).resolve().parents[1] / "vendor" / "shannon"


def _package_inventory(node_modules: Path) -> tuple[list[dict[str, str]], list[str]]:
    packages: list[dict[str, str]] = []
    errors: list[str] = []
    if not node_modules.is_dir():
        return packages, ["node_modules_missing"]
    for manifest in sorted(node_modules.rglob("package.json")):
        try:
            relative = manifest.relative_to(node_modules)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            errors.append(f"package_manifest_unreadable:{manifest}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"package_manifest_invalid:{manifest}")
            continue
        name = str(payload.get("name") or "")
        version = str(payload.get("version") or "")
        if not name or not version:
            continue
        packages.append(
            {
                "name": name,
                "version": version,
                "path": str(relative),
                "package_json_sha256": _sha256_file(manifest),
            }
        )
    packages.sort(key=lambda item: (item["name"], item["version"], item["path"]))
    if not packages:
        errors.append("dependency_inventory_empty")
    observed = {item["name"] for item in packages}
    for name in _REQUIRED_PACKAGES:
        if name not in observed:
            errors.append(f"required_package_missing:{name}")
    return packages, errors


def dependency_vector(
    vendor_root: Path | None = None,
    *,
    bun: str = "bun",
    smoke: bool = True,
) -> dict[str, Any]:
    """Return a deterministic inventory plus an executable Shannon smoke."""

    root = (vendor_root or _default_vendor_root()).resolve(strict=False)
    lockfile = root / "bun.lock"
    package_json = root / "package.json"
    index = root / "index.ts"
    errors: list[str] = []
    for label, path in (
        ("lockfile", lockfile),
        ("package_json", package_json),
        ("index", index),
    ):
        if not path.is_file():
            errors.append(f"{label}_missing")
    bun_path = shutil.which(bun)
    bun_version = ""
    if bun_path is None:
        errors.append("bun_unavailable")
    else:
        version = subprocess.run(
            [bun_path, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if version.returncode != 0:
            errors.append("bun_version_failed")
        else:
            bun_version = version.stdout.strip()

    packages, package_errors = _package_inventory(root / "node_modules")
    errors.extend(package_errors)
    smoke_result = {
        "command": ["bun", "-e", "<shannon-index-commander-smoke>"],
        "stdout": "",
        "returncode": -1,
    }
    if smoke and bun_path is not None and index.is_file():
        try:
            result = subprocess.run(
                [bun_path, "-e", _SMOKE_PROGRAM],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            errors.append("shannon_execution_smoke_failed")
        else:
            smoke_result["stdout"] = result.stdout.strip()
            smoke_result["returncode"] = result.returncode
            if (
                result.returncode != 0
                or smoke_result["stdout"] != "shannon-index-commander-ok"
            ):
                errors.append("shannon_execution_smoke_failed")
    elif smoke:
        errors.append("shannon_execution_smoke_failed")

    core = {
        "schema": SHANNON_DEPENDENCY_SCHEMA,
        "vendor_root": str(root),
        "bun_version": bun_version,
        "install_args": list(_INSTALL_ARGS),
        "lockfile_sha256": _sha256_file(lockfile) if lockfile.is_file() else "",
        "package_json_sha256": (
            _sha256_file(package_json) if package_json.is_file() else ""
        ),
        "index_sha256": _sha256_file(index) if index.is_file() else "",
        "packages": packages,
        "dependency_tree_sha256": _canonical_sha256({"packages": packages}),
        "smoke": smoke_result,
        "errors": sorted(set(errors)),
        "ready": not errors,
    }
    return {**core, "content_sha256": _canonical_sha256(core)}


def prepare_dependencies(
    vendor_root: Path | None = None,
    *,
    bun: str = "bun",
) -> dict[str, Any]:
    """Install exactly the production lockfile and return its attested vector."""

    root = (vendor_root or _default_vendor_root()).resolve(strict=False)
    bun_path = shutil.which(bun)
    if bun_path is None:
        raise RuntimeError("bun is unavailable")
    for required in ("package.json", "bun.lock", "index.ts"):
        if not (root / required).is_file():
            raise RuntimeError(f"vendored Shannon {required} is missing at {root}")
    node_modules = root / "node_modules"
    if node_modules.exists():
        if not node_modules.is_dir() or node_modules.is_symlink():
            raise RuntimeError(
                f"refusing to replace invalid Shannon dependency root: {node_modules}"
            )
        shutil.rmtree(node_modules)
    result = subprocess.run(
        [bun_path, *_INSTALL_ARGS],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "frozen Shannon dependency install failed: "
            + (result.stderr.strip() or result.stdout.strip())
        )
    vector = dependency_vector(root, bun=bun, smoke=True)
    if not vector["ready"]:
        raise RuntimeError(
            "prepared Shannon dependency runtime is not ready: "
            + ", ".join(vector["errors"])
        )
    return vector


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    target = path.resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "probe"))
    parser.add_argument("--vendor-root", type=Path)
    parser.add_argument("--receipt-out", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = (
            prepare_dependencies(args.vendor_root)
            if args.action == "prepare"
            else dependency_vector(args.vendor_root)
        )
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ready": False, "errors": [str(exc)]}, sort_keys=True))
        return 2
    if args.receipt_out is not None:
        _atomic_write_json(args.receipt_out, payload)
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
