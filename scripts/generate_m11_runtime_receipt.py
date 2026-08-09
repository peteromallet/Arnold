#!/usr/bin/env python3
"""Generate a strict, promotion-gated M11 runtime receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan.cloud.runtime_provenance import (
    m11_bound_runtime_identity,
)

CANDIDATE_SCHEMA = "m11.runtime-candidate.v1"
RECEIPT_SCHEMA = "m11.runtime-receipt.v1"
REQUIRED_COMPONENTS = {
    "interpreter": "interpreter",
    "editable_root": "editable_checkout",
    "pth": "pth_files",
    "import_roots": "imports",
    "source_lineage": "source_lineage",
    "process_command": "supervisor_command",
    "systemd_wrapper": "wrappers",
    "target_marker": "target_marker",
}
REQUIRED_CANDIDATE_FIELDS = (
    "repo_root",
    "revision",
    "interpreter",
    "interpreter_sha256",
    "pth_hashes",
    "import_paths",
    "supervisor_python",
    "supervisor_argv",
    "wrapper_dir",
    "wrapper_hashes",
    "target_marker_path",
    "target_marker_sha256",
    "target_fields",
)


class RuntimeReceiptError(ValueError):
    """Candidate or observed runtime did not satisfy the strict tuple."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def candidate_digest(candidate: Mapping[str, Any]) -> str:
    return _digest({
        key: value for key, value in candidate.items()
        if key != "candidate_sha256"
    })


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise RuntimeReceiptError(f"candidate_field_invalid:{field}")
    return value


def validate_candidate(candidate: Mapping[str, Any]) -> None:
    if candidate.get("schema") != CANDIDATE_SCHEMA:
        raise RuntimeReceiptError("candidate_schema_invalid")
    missing = [
        field for field in REQUIRED_CANDIDATE_FIELDS
        if candidate.get(field) in (None, "", [], {})
    ]
    if missing:
        raise RuntimeReceiptError("candidate_fields_missing:" + ",".join(missing))
    for field in ("pth_hashes", "import_paths", "wrapper_hashes", "target_fields"):
        _require_mapping(candidate.get(field), field)
    if candidate.get("promotion_status") != "promoted":
        raise RuntimeReceiptError("candidate_not_promoted")
    expected_digest = candidate_digest(candidate)
    if candidate.get("candidate_sha256") != expected_digest:
        raise RuntimeReceiptError("candidate_digest_mismatch")
    argv = candidate.get("supervisor_argv")
    if not isinstance(argv, list) or len(argv) < 2:
        raise RuntimeReceiptError("candidate_field_invalid:supervisor_argv")
    if "-P" not in argv:
        raise RuntimeReceiptError("supervisor_safe_path_flag_missing")
    if Path(str(argv[0])).resolve(strict=False) != Path(
        str(candidate["supervisor_python"])
    ).resolve(strict=False):
        raise RuntimeReceiptError("supervisor_python_argv_mismatch")


def build_runtime_receipt(
    candidate: Mapping[str, Any],
    *,
    identity_builder: Callable[..., dict[str, Any]] = m11_bound_runtime_identity,
) -> dict[str, Any]:
    """Validate a promoted candidate against the live runtime and emit a receipt."""
    validate_candidate(candidate)
    argv = [str(value) for value in candidate["supervisor_argv"]]
    identity = identity_builder(
        expected_root=Path(str(candidate["repo_root"])),
        expected_revision=str(candidate["revision"]),
        expected_interpreter=Path(str(candidate["interpreter"])),
        expected_interpreter_sha256=str(candidate["interpreter_sha256"]),
        expected_pth_hashes={
            str(path): str(digest)
            for path, digest in candidate["pth_hashes"].items()
        },
        expected_import_paths={
            str(name): str(path)
            for name, path in candidate["import_paths"].items()
        },
        supervisor_python=Path(str(candidate["supervisor_python"])),
        supervisor_argv=argv,
        expected_supervisor_argv=argv,
        wrapper_dir=Path(str(candidate["wrapper_dir"])),
        expected_wrapper_hashes={
            str(path): str(digest)
            for path, digest in candidate["wrapper_hashes"].items()
        },
        target_marker_path=Path(str(candidate["target_marker_path"])),
        expected_target_marker_sha256=str(candidate["target_marker_sha256"]),
        expected_target_fields=dict(candidate["target_fields"]),
        strict=True,
    )
    if identity.get("schema") != "arnold.megaplan.m11_bound_runtime_identity.v1":
        raise RuntimeReceiptError("runtime_identity_schema_invalid")
    if identity.get("valid") is not True:
        errors = identity.get("errors")
        detail = ",".join(str(value) for value in errors) if isinstance(errors, list) else ""
        raise RuntimeReceiptError("runtime_identity_invalid:" + detail)

    observed = identity.get("components")
    if not isinstance(observed, dict):
        raise RuntimeReceiptError("runtime_components_missing")
    components: dict[str, dict[str, Any]] = {}
    for receipt_name, identity_name in REQUIRED_COMPONENTS.items():
        row = observed.get(identity_name)
        if not isinstance(row, dict) or row.get("ok") is not True:
            raise RuntimeReceiptError(f"runtime_component_invalid:{identity_name}")
        components[receipt_name] = {
            "ok": True,
            "evidence_sha256": _digest(row),
        }
    components["runtime_provenance_receipt"] = {
        "ok": True,
        "evidence_sha256": _digest(identity),
    }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "valid": True,
        "candidate_sha256": candidate["candidate_sha256"],
        "runtime_identity_sha256": identity.get("content_sha256"),
        "components": components,
    }
    receipt["content_sha256"] = _digest(receipt)
    return receipt


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
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        if not isinstance(candidate, dict):
            raise RuntimeReceiptError("candidate_not_object")
        receipt = build_runtime_receipt(candidate)
        _write_atomic(args.output, receipt)
    except (OSError, json.JSONDecodeError, RuntimeReceiptError) as exc:
        parser.exit(2, f"runtime receipt rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
