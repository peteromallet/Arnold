"""Content-addressed runtime promotion receipts for chain admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.types import CliError


PROMOTION_RECEIPT_SCHEMA = "arnold.megaplan.runtime_promotion_receipt.v1"
PROMOTION_RECEIPT_ERROR = "invalid_runtime_promotion_receipt"


def _content_sha256(payload: Mapping[str, Any]) -> str:
    content = dict(payload)
    content.pop("content_sha256", None)
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def promotion_receipt_report(
    path: Path,
    *,
    expected_milestone: str,
    expected_semantic_sha256: str,
) -> dict[str, Any]:
    """Verify a receipt and return bounded identity evidence."""

    resolved = path.expanduser().resolve(strict=False)
    report: dict[str, Any] = {
        "schema": PROMOTION_RECEIPT_SCHEMA,
        "path": str(resolved),
        "exists": resolved.is_file(),
        "valid": False,
        "content_sha256": "",
        "errors": [],
    }
    if not resolved.is_file():
        report["errors"] = ["promotion_receipt_missing"]
        return report
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        report["errors"] = [f"promotion_receipt_unreadable:{type(exc).__name__}"]
        return report
    if not isinstance(payload, Mapping):
        report["errors"] = ["promotion_receipt_not_object"]
        return report

    errors: list[str] = []
    computed = _content_sha256(payload)
    declared = str(payload.get("content_sha256") or "")
    if payload.get("schema") != PROMOTION_RECEIPT_SCHEMA:
        errors.append("promotion_receipt_schema_mismatch")
    if not declared or declared != computed:
        errors.append("promotion_receipt_content_hash_mismatch")

    source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
    target = payload.get("target") if isinstance(payload.get("target"), Mapping) else {}
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), Mapping) else {}
    tests = payload.get("tests") if isinstance(payload.get("tests"), Mapping) else {}
    milestone = payload.get("milestone") if isinstance(payload.get("milestone"), Mapping) else {}
    source_revision = str(source.get("revision") or "")
    target_revision = str(target.get("revision") or "")
    runtime_revision = str(runtime.get("source_revision") or "")
    import_root = str(runtime.get("import_root") or "")
    expected_root = str(runtime.get("expected_root") or "")
    imports = runtime.get("imports") if isinstance(runtime.get("imports"), Mapping) else {}

    if len(source_revision) != 40:
        errors.append("promotion_receipt_source_revision_invalid")
    if len(target_revision) != 40 or not target.get("branch"):
        errors.append("promotion_receipt_target_identity_invalid")
    if runtime_revision != target_revision:
        errors.append("promotion_receipt_runtime_revision_mismatch")
    if not import_root or import_root != expected_root:
        errors.append("promotion_receipt_runtime_root_mismatch")
    for name in ("arnold_pipelines", "megaplan"):
        imported = str(imports.get(name) or "")
        if not imported or not imported.startswith(import_root.rstrip("/") + "/"):
            errors.append(f"promotion_receipt_import_mismatch:{name}")
    if tests.get("exit_code") != 0 or tests.get("result") != "passed" or not tests.get("command"):
        errors.append("promotion_receipt_tests_not_passed")
    for field, value in (
        ("created_at", payload.get("created_at")),
        ("promoted_at", payload.get("promoted_at")),
        ("runtime.attested_at", runtime.get("attested_at")),
        ("tests.completed_at", tests.get("completed_at")),
    ):
        if not value:
            errors.append(f"promotion_receipt_timestamp_missing:{field}")
    if milestone.get("label") != expected_milestone:
        errors.append("promotion_receipt_milestone_mismatch")
    if milestone.get("semantic_sha256") != expected_semantic_sha256:
        errors.append("promotion_receipt_semantic_identity_mismatch")

    report.update(
        {
            "valid": not errors,
            "content_sha256": computed,
            "declared_content_sha256": declared,
            "source_revision": source_revision,
            "target_branch": str(target.get("branch") or ""),
            "target_revision": target_revision,
            "runtime_import_root": import_root,
            "milestone": str(milestone.get("label") or ""),
            "semantic_sha256": str(milestone.get("semantic_sha256") or ""),
            "tests_command": str(tests.get("command") or ""),
            "tests_result": str(tests.get("result") or ""),
            "errors": errors,
        }
    )
    return report


def verify_promotion_receipt(
    path: Path,
    *,
    expected_milestone: str,
    expected_semantic_sha256: str,
) -> dict[str, Any]:
    report = promotion_receipt_report(
        path,
        expected_milestone=expected_milestone,
        expected_semantic_sha256=expected_semantic_sha256,
    )
    if not report["valid"]:
        raise CliError(
            PROMOTION_RECEIPT_ERROR,
            f"Runtime promotion receipt is invalid: {report['errors']}",
            extra={"promotion_receipt": report},
        )
    return report

