#!/usr/bin/env python3
"""Build the deterministic M11 production-audit cycle-tree manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA = "m11.audit-cycle-trees.v1"
SUBSTITUTION_SCHEMA = "m11.audit-cycle-substitution.v1"
REQUIRED_CYCLES = (
    "20260727T183804.052936Z",
    "20260727T194726.076432Z",
    "20260727T200106.626010Z",
    "20260727T204730.361503Z",
)
REQUIRED_FILES = (
    "operator-prompt.txt",
    "operator-result.json",
    "operator-transcript.jsonl",
    "output-schema.json",
    "report.json",
    "report.md",
)


class AuditManifestError(ValueError):
    """Audit evidence or substitution authorization is invalid."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def substitution_digest(value: Mapping[str, Any]) -> str:
    return _digest({
        key: item for key, item in value.items()
        if key != "content_sha256"
    })


def inspect_cycle(audit_root: Path, cycle_id: str) -> dict[str, Any]:
    cycle_root = audit_root / cycle_id
    files: list[dict[str, str]] = []
    missing: list[str] = []
    for filename in REQUIRED_FILES:
        path = cycle_root / filename
        if path.is_file():
            files.append({"filename": filename, "sha256": _file_digest(path)})
        else:
            missing.append(filename)
    complete = not missing
    provenance_digest = _digest({
        "cycle_id": cycle_id,
        "files": files,
    }) if complete else ""
    tree_core = {
        "cycle_id": cycle_id,
        "files": files,
        "missing_files": missing,
        "is_complete": complete,
    }
    return {
        **tree_core,
        "provenance_digest": provenance_digest,
        "cycle_tree_sha256": _digest(tree_core),
    }


def _commit_is_ancestor(repo_root: Path, revision: str) -> bool:
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        return False
    result = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", revision, "HEAD"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _validate_substitution(
    substitution: Mapping[str, Any],
    *,
    missing_cycle: Mapping[str, Any],
    audit_root: Path,
    repo_root: Path,
    commit_verifier: Callable[[Path, str], bool],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if substitution.get("schema") != SUBSTITUTION_SCHEMA:
        raise AuditManifestError("substitution_schema_invalid")
    if substitution.get("content_sha256") != substitution_digest(substitution):
        raise AuditManifestError("substitution_digest_mismatch")
    if substitution.get("missing_cycle_id") != missing_cycle["cycle_id"]:
        raise AuditManifestError("substitution_missing_cycle_id_mismatch")
    if substitution.get("missing_cycle_sha256") != missing_cycle["cycle_tree_sha256"]:
        raise AuditManifestError("substitution_missing_cycle_digest_mismatch")
    reason = substitution.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise AuditManifestError("substitution_reason_missing")
    authority = substitution.get("authority")
    if (
        not isinstance(authority, dict)
        or not isinstance(authority.get("actor"), str)
        or not authority["actor"].strip()
        or not isinstance(authority.get("receipt_sha256"), str)
        or len(authority["receipt_sha256"]) != 71
        or not authority["receipt_sha256"].startswith("sha256:")
    ):
        raise AuditManifestError("substitution_authority_invalid")
    revision = substitution.get("source_commit")
    if not isinstance(revision, str) or not commit_verifier(repo_root, revision):
        raise AuditManifestError("substitution_not_committed")
    replacement_id = substitution.get("replacement_cycle_id")
    if (
        not isinstance(replacement_id, str)
        or not replacement_id
        or replacement_id in REQUIRED_CYCLES
    ):
        raise AuditManifestError("substitution_replacement_cycle_invalid")
    replacement = inspect_cycle(audit_root, replacement_id)
    if replacement["is_complete"] is not True:
        raise AuditManifestError(
            "substitution_replacement_incomplete:"
            + ",".join(replacement["missing_files"])
        )
    return dict(substitution), replacement


def build_manifest(
    audit_root: Path,
    *,
    repo_root: Path,
    substitution: Mapping[str, Any] | None = None,
    commit_verifier: Callable[[Path, str], bool] = _commit_is_ancestor,
) -> dict[str, Any]:
    cycles = [inspect_cycle(audit_root, cycle_id) for cycle_id in REQUIRED_CYCLES]
    incomplete = [cycle for cycle in cycles if not cycle["is_complete"]]
    substitutions: list[dict[str, Any]] = []
    effective_cycles = list(cycles)
    if substitution is not None:
        if len(incomplete) != 1:
            raise AuditManifestError("substitution_requires_exactly_one_incomplete_cycle")
        record, replacement = _validate_substitution(
            substitution,
            missing_cycle=incomplete[0],
            audit_root=audit_root,
            repo_root=repo_root,
            commit_verifier=commit_verifier,
        )
        substitutions.append({
            "authorization": record,
            "replacement": replacement,
        })
        effective_cycles = [
            replacement if cycle["cycle_id"] == incomplete[0]["cycle_id"] else cycle
            for cycle in cycles
        ]
    complete = all(cycle["is_complete"] for cycle in effective_cycles)
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "required_cycle_ids": list(REQUIRED_CYCLES),
        "required_files": list(REQUIRED_FILES),
        "audit_cycle_trees": cycles,
        "substitutions": substitutions,
        "effective_cycle_trees": effective_cycles,
        "complete": complete,
        "incomplete_cycle_ids": [
            cycle["cycle_id"] for cycle in effective_cycles
            if not cycle["is_complete"]
        ],
    }
    manifest["content_sha256"] = _digest(manifest)
    return manifest


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, default=Path("/workspace/audit-reports"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/m11-audit-cycle-trees.json"),
    )
    parser.add_argument("--substitution", type=Path)
    args = parser.parse_args(argv)
    try:
        substitution = (
            json.loads(args.substitution.read_text(encoding="utf-8"))
            if args.substitution else None
        )
        if substitution is not None and not isinstance(substitution, dict):
            raise AuditManifestError("substitution_not_object")
        manifest = build_manifest(
            args.audit_root,
            repo_root=args.repo_root,
            substitution=substitution,
        )
        _write_atomic(args.output, manifest)
    except (OSError, json.JSONDecodeError, AuditManifestError) as exc:
        parser.exit(2, f"audit manifest rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
