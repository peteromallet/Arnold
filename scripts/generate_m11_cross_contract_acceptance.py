#!/usr/bin/env python3
"""Generate M11 cross-contract acceptance evidence.

Step 9: produces the deterministic aggregate M11 acceptance report with
content hash, runtime vectors, prerequisite status, predecessor joins,
route/canary/genuine-block/recovery/audit refs, and one typed outcome
for partial state.

Usage:
    python scripts/generate_m11_cross_contract_acceptance.py \\
        --owner T9 \\
        --artifacts evidence/manifest.json \\
        --out evidence/m11-cross-contract-acceptance.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Direct script execution places ``scripts/`` rather than the repository root
# on sys.path. Anchor source-checkout invocation to the repository whose
# evidence is being generated; module invocation remains unchanged.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from arnold_pipelines.megaplan.orchestration.m11_acceptance import (
    PREDECESSOR_FAMILIES,
    PrerequisiteRecord,
    PrerequisiteStatus,
    m11_debt_gate,
    schema_descriptor,
)
from arnold_pipelines.megaplan.orchestration.m11_predecessor_wrappers import (
    validate_wrapper,
)
from scripts.generate_m11_no_debt import NoDebtError, validate_no_debt_receipt


_FAMILY_PATHS: dict[str, Path] = {
    "m10_handoff": Path("evidence/m10-handoff.json"),
    "c_family": Path("evidence/C-family.json"),
    "m5_family": Path("evidence/M5-family.json"),
    "a7_family": Path("evidence/A7-family.json"),
    "audit": Path("evidence/m11-genuine-block-candidate/manifest.json"),
    "wbc": Path("evidence/wbc-boundary-inventory.json"),
    "genuine_block": Path("evidence/genuine-block.json"),
    "recovery": Path("evidence/m11-recovery-latency-ledger.json"),
    "route": Path("evidence/m11-recovery-topology-surfaces.json"),
    "no_debt": Path("evidence/no-debt.json"),
    "runtime": Path("evidence/runtime.json"),
}

_WRAPPER_FAMILIES = {
    "m10_handoff": "m10_handoff",
    "c_family": "m10_c01_c20",
    "m5_family": "m5",
    "a7_family": "a7",
}

_REQUIRED_AUDIT_CYCLES = (
    "20260727T183804.052936Z",
    "20260727T194726.076432Z",
    "20260727T200106.626010Z",
    "20260727T204730.361503Z",
)
_REQUIRED_AUDIT_FILES = (
    "operator-prompt.txt",
    "operator-result.json",
    "operator-transcript.jsonl",
    "output-schema.json",
    "report.json",
    "report.md",
)
_SHA256_LENGTH = len("sha256:") + 64


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file, returning {} on any failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# Fields excluded from content hash (transient / non-deterministic).
_CONTENT_HASH_EXCLUDE: frozenset[str] = frozenset({"content_hash", "generated_at", "schema_descriptor"})


def _compute_content_hash(report: dict[str, Any]) -> str:
    """Compute SHA-256 content hash over the report, excluding transient fields."""
    payload = {k: v for k, v in report.items() if k not in _CONTENT_HASH_EXCLUDE}
    return _sha256_hex(_canonical_json_bytes(payload))


def _file_sha256(path: Path) -> str:
    try:
        return _sha256_hex(path.read_bytes())
    except OSError:
        return ""


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _SHA256_LENGTH
        and value.startswith("sha256:")
        and all(char in "0123456789abcdef" for char in value[7:])
    )


def _result(
    family: str,
    path: Path,
    *,
    passed: bool,
    failures: list[dict[str, Any]],
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "family": family,
        "path": path.as_posix(),
        "file_sha256": _file_sha256(path),
        "passed": bool(passed and not failures),
        "failures": failures,
        "data": data or {},
    }


def _validate_predecessor_wrapper(
    repo_root: Path, family: str, path: Path
) -> dict[str, Any]:
    full_path = repo_root / path
    data = _load_json(full_path)
    failures = validate_wrapper(data, repo_root=repo_root) if data else [{
        "kind": "artifact_missing_or_invalid_json",
        "detail": f"{path} is missing or invalid JSON",
    }]
    expected_family = _WRAPPER_FAMILIES[family]
    if data.get("family") != expected_family:
        failures.append({
            "kind": "wrapper_family_mismatch",
            "expected": expected_family,
            "actual": data.get("family"),
        })
    if data.get("status") != "satisfied":
        failures.append({
            "kind": "wrapper_not_satisfied",
            "actual": data.get("status"),
        })
    return _result(
        family, full_path, passed=not failures, failures=failures, data=data
    )


def _validate_predecessor_manifest(
    repo_root: Path,
    manifest_path: Path,
    wrapper_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    full_path = manifest_path if manifest_path.is_absolute() else repo_root / manifest_path
    data = _load_json(full_path)
    failures: list[dict[str, Any]] = []
    if data.get("schema") != "m11.predecessor-artifact-manifest.v1":
        failures.append({"kind": "manifest_schema_mismatch"})
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        failures.append({"kind": "manifest_artifacts_missing"})
        artifacts = {}
    for family, result in wrapper_results.items():
        wrapper_digest = result["data"].get("content_sha256")
        if artifacts.get(family) != wrapper_digest:
            failures.append({
                "kind": "manifest_wrapper_digest_mismatch",
                "family": family,
                "expected": wrapper_digest,
                "actual": artifacts.get(family),
            })
    return _result(
        "predecessor_manifest",
        full_path,
        passed=not failures,
        failures=failures,
        data=data,
    )


def _validate_route(repo_root: Path, path: Path) -> dict[str, Any]:
    full_path = repo_root / path
    data = _load_json(full_path)
    failures: list[dict[str, Any]] = []
    closure = data.get("closure")
    manifest = data.get("route_closure_manifest")
    if data.get("baseline_kind") != "final_route_authority_closure":
        failures.append({"kind": "route_schema_or_baseline_mismatch"})
    if not isinstance(closure, dict):
        failures.append({"kind": "route_closure_missing"})
        closure = {}
    required_true = (
        "closure_complete", "exact_set_equal", "manifest_complete"
    )
    for field in required_true:
        if closure.get(field) is not True:
            failures.append({"kind": "route_gate_not_true", "field": field})
    for field in ("unplanned_count", "planned_pending_count"):
        if closure.get(field) != 0:
            failures.append({
                "kind": "route_open_surfaces",
                "field": field,
                "actual": closure.get(field),
            })
    if not isinstance(manifest, dict) or not manifest:
        failures.append({"kind": "route_manifest_empty"})
        manifest = {}
    if closure.get("manifest_surface_count") != len(manifest):
        failures.append({"kind": "route_manifest_count_mismatch"})
    forbidden = {"label", "liveness", "wbc_receipt", "rebuildable_projection"}
    for surface_id, row in manifest.items():
        proof = row.get("zero_authority_proof", {}) if isinstance(row, dict) else {}
        if (
            row.get("surface_id") != surface_id
            or row.get("closure_state") != "closed"
            or not _is_sha256(row.get("content_hash"))
            or proof.get("complete") is not True
            or set(proof.get("forbids", [])) != forbidden
        ):
            failures.append({
                "kind": "route_surface_invalid",
                "surface_id": surface_id,
            })
    return _result("route", full_path, passed=not failures, failures=failures, data=data)


def _validate_wbc(repo_root: Path, path: Path) -> dict[str, Any]:
    full_path = repo_root / path
    data = _load_json(full_path)
    failures: list[dict[str, Any]] = []
    meta = data.get("meta", {})
    if meta.get("schema") != "m6.wbc-boundary-inventory.v1":
        failures.append({"kind": "wbc_schema_mismatch"})
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        failures.append({"kind": "wbc_rows_empty"})
        rows = []
    if meta.get("row_count") != len(rows):
        failures.append({"kind": "wbc_row_count_mismatch"})
    expected_content_hash = hashlib.sha256(
        json.dumps(rows, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    if meta.get("content_hash") != expected_content_hash:
        failures.append({
            "kind": "wbc_content_hash_mismatch",
            "expected": expected_content_hash,
            "actual": meta.get("content_hash"),
        })
    unmatched = data.get("unmatched_categories", {})
    deny_rows = data.get("default_deny_rows")
    if not isinstance(unmatched, dict):
        failures.append({"kind": "wbc_unmatched_categories_invalid"})
        unmatched = {}
    if not isinstance(deny_rows, list):
        failures.append({"kind": "wbc_default_deny_rows_invalid"})
        deny_rows = []

    # Default-deny is a valid, intentional closure for a non-authoritative
    # discovered surface.  It is not an unresolved candidate.  Make the
    # disposition machine-verifiable rather than requiring the impossible
    # condition that discovery find no candidates.
    deny_targets: dict[str, list[dict[str, Any]]] = {}
    invalid_denies: list[dict[str, Any]] = []
    for index, deny in enumerate(deny_rows):
        if not isinstance(deny, dict):
            invalid_denies.append({"index": index, "reason": "not_object"})
            continue
        target = deny.get("target_path")
        valid = (
            deny.get("row_kind") == "default_deny"
            and isinstance(target, str)
            and bool(target)
            and isinstance(deny.get("target_type"), str)
            and bool(deny.get("target_type"))
            and deny.get("access") == "denied"
            and isinstance(deny.get("reason"), str)
            and bool(deny.get("reason").strip())
            and isinstance(deny.get("owner"), str)
            and deny.get("owner") not in {"", "UNKNOWN"}
            and isinstance(deny.get("mitigation"), str)
            and bool(deny.get("mitigation").strip())
        )
        if not valid:
            invalid_denies.append({"index": index, "target_path": target})
            continue
        if deny.get("target_type") == "runtime_module":
            deny_targets.setdefault(target, []).append(deny)
    if invalid_denies:
        failures.append({
            "kind": "wbc_default_deny_disposition_invalid",
            "count": len(invalid_denies),
            "examples": invalid_denies[:5],
        })

    static_rows = unmatched.get("unmatched_static", [])
    if not isinstance(static_rows, list):
        failures.append({"kind": "wbc_unmatched_static_invalid"})
        static_rows = []
    uncovered_static: list[str] = []
    duplicate_static_denies: list[str] = []
    for entry in static_rows:
        target = entry.get("module_path") if isinstance(entry, dict) else None
        matching = deny_targets.get(target, []) if isinstance(target, str) else []
        if not matching:
            uncovered_static.append(str(target))
        elif len(matching) != 1:
            duplicate_static_denies.append(str(target))
    if uncovered_static:
        failures.append({
            "kind": "wbc_static_surface_without_default_deny",
            "count": len(uncovered_static),
            "examples": uncovered_static[:5],
        })
    if duplicate_static_denies:
        failures.append({
            "kind": "wbc_static_surface_duplicate_default_deny",
            "count": len(duplicate_static_denies),
            "examples": duplicate_static_denies[:5],
        })

    # Other unmatched categories are real gaps unless the row itself carries
    # an explicit, evidence-bound non-authoritative disposition.  The old M6
    # UNKNOWN runtime sentinel and declared contracts with no matrix entry do
    # not meet this bar.
    unresolved: dict[str, int] = {}
    for category, entries in unmatched.items():
        if category == "unmatched_static":
            continue
        if not isinstance(entries, list):
            failures.append({
                "kind": "wbc_unmatched_category_invalid",
                "category": category,
            })
            continue
        category_unresolved = 0
        for entry in entries:
            disposition = entry.get("disposition") if isinstance(entry, dict) else None
            explicitly_closed = (
                isinstance(disposition, dict)
                and disposition.get("status") == "closed_non_authoritative"
                and disposition.get("access") == "denied"
                and isinstance(disposition.get("owner"), str)
                and disposition.get("owner") not in {"", "UNKNOWN"}
                and _is_sha256(disposition.get("evidence_sha256"))
                and isinstance(disposition.get("reason"), str)
                and bool(disposition.get("reason").strip())
            )
            if not explicitly_closed:
                category_unresolved += 1
        if category_unresolved:
            unresolved[category] = category_unresolved
    if unresolved:
        failures.append({"kind": "wbc_unresolved_rows", "counts": unresolved})

    if meta.get("default_deny_count") != len(deny_rows):
        failures.append({
            "kind": "wbc_default_deny_count_mismatch",
            "claimed": meta.get("default_deny_count"),
            "actual": len(deny_rows),
        })
    actual_unmatched = sum(
        len(entries)
        for entries in unmatched.values()
        if isinstance(entries, list)
    )
    if meta.get("unmatched_total_count") != actual_unmatched:
        failures.append({
            "kind": "wbc_unmatched_total_count_mismatch",
            "claimed": meta.get("unmatched_total_count"),
            "actual": actual_unmatched,
        })

    assertions = data.get("current_state_assertions")
    if not isinstance(assertions, dict):
        failures.append({"kind": "wbc_current_state_assertions_missing"})
    else:
        for assertion_id in ("front_half_producers", "execute_batch_producers"):
            assertion = assertions.get(assertion_id)
            if not isinstance(assertion, dict) or assertion.get("count_matches") is not True:
                failures.append({
                    "kind": "wbc_current_state_assertion_failed",
                    "assertion": assertion_id,
                    "expected": assertion.get("expected_count") if isinstance(assertion, dict) else None,
                    "actual": assertion.get("actual_count") if isinstance(assertion, dict) else None,
                    "missing": assertion.get("missing") if isinstance(assertion, dict) else None,
                })
    return _result("wbc", full_path, passed=not failures, failures=failures, data=data)


def _validate_genuine_block(repo_root: Path, path: Path) -> dict[str, Any]:
    full_path = repo_root / path
    data = _load_json(full_path)
    failures: list[dict[str, Any]] = []
    if data.get("schema") != "m11.genuine-block-receipt.v1":
        failures.append({"kind": "genuine_block_schema_mismatch"})
    if data.get("status") not in {"accepted_repair", "typed_escalation"}:
        failures.append({
            "kind": "genuine_block_terminal_outcome_missing",
            "actual": data.get("status"),
        })
    occurrence = data.get("occurrence")
    if not isinstance(occurrence, dict) or not _is_sha256(occurrence.get("digest")):
        failures.append({"kind": "genuine_block_occurrence_unbound"})
    verifier = data.get("independent_verifier")
    if not isinstance(verifier, dict) or verifier.get("accepted") is not True:
        failures.append({"kind": "genuine_block_verifier_missing"})
    checks = verifier.get("checks", {}) if isinstance(verifier, dict) else {}
    for slot in ("five_minute", "one_hour", "three_hour"):
        if not isinstance(checks.get(slot), dict) or checks[slot].get("passed") is not True:
            failures.append({
                "kind": "genuine_block_verifier_slot_missing",
                "slot": slot,
            })
    if data.get("projection_agreement") is not True:
        failures.append({"kind": "genuine_block_projection_disagreement"})
    return _result(
        "genuine_block", full_path, passed=not failures, failures=failures, data=data
    )


def _latency_value(row: dict[str, Any]) -> float | None:
    for key in ("latency_seconds", "eligible_to_terminal_seconds"):
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _nearest_rank_p95(values: list[float]) -> float:
    ordered = sorted(values)
    rank = max(1, (95 * len(ordered) + 99) // 100)
    return ordered[rank - 1]


def _validate_recovery(repo_root: Path, path: Path) -> dict[str, Any]:
    full_path = repo_root / path
    data = _load_json(full_path)
    failures: list[dict[str, Any]] = []
    if data.get("schema_version") != 1 or data.get("milestone") != "M11":
        failures.append({"kind": "recovery_schema_mismatch"})
    rows = data.get("latency_ledger_rows")
    if not isinstance(rows, list) or not rows:
        failures.append({"kind": "recovery_latency_rows_empty"})
        rows = []
    values: list[float] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append({"kind": "recovery_row_invalid", "index": index})
            continue
        row_id = row.get("occurrence_id")
        latency = _latency_value(row)
        receipt = row.get("terminal_receipt_sha256")
        if not isinstance(row_id, str) or not row_id or row_id in seen:
            failures.append({"kind": "recovery_occurrence_invalid", "index": index})
        else:
            seen.add(row_id)
        if latency is None or latency < 0:
            failures.append({"kind": "recovery_latency_invalid", "index": index})
        else:
            values.append(latency)
        if not _is_sha256(receipt):
            failures.append({"kind": "recovery_receipt_unbound", "index": index})
        if row.get("eligible") is not True:
            failures.append({"kind": "recovery_row_not_eligible", "index": index})
        if row.get("terminal_outcome") not in {"accepted_repair", "typed_escalation"}:
            failures.append({"kind": "recovery_terminal_outcome_invalid", "index": index})
    minimum = data.get("minimum_cohort_size")
    if not isinstance(minimum, int) or minimum < 1 or len(rows) < minimum:
        failures.append({
            "kind": "recovery_sample_insufficient",
            "minimum": minimum,
            "actual": len(rows),
        })
    for field in ("sample_count", "total_rows", "eligible_rows"):
        if data.get(field) != len(rows):
            failures.append({
                "kind": "recovery_claimed_count_mismatch",
                "field": field,
                "claimed": data.get(field),
                "actual": len(rows),
            })
    if values:
        computed_p95 = _nearest_rank_p95(values)
        if data.get("p95_seconds") != computed_p95:
            failures.append({
                "kind": "recovery_p95_mismatch",
                "claimed": data.get("p95_seconds"),
                "actual": computed_p95,
            })
        threshold = data.get("slo_threshold_seconds")
        if not isinstance(threshold, (int, float)) or computed_p95 >= float(threshold):
            failures.append({"kind": "recovery_slo_not_met"})
    if data.get("slo_met") is not True:
        failures.append({"kind": "recovery_slo_claim_not_true"})
    return _result(
        "recovery", full_path, passed=not failures, failures=failures, data=data
    )


def _validate_no_debt(repo_root: Path, path: Path) -> dict[str, Any]:
    full_path = repo_root / path
    data = _load_json(full_path)
    failures: list[dict[str, Any]] = []
    try:
        data = validate_no_debt_receipt(data)
    except NoDebtError as exc:
        failures.append({
            "kind": "no_debt_receipt_invalid",
            "detail": str(exc),
        })
    return _result(
        "no_debt", full_path, passed=not failures, failures=failures, data=data
    )


def _validate_runtime_file(repo_root: Path, path: Path) -> dict[str, Any]:
    full_path = repo_root / path
    data = _load_json(full_path)
    failures: list[dict[str, Any]] = []
    if data.get("schema") != "m11.runtime-evidence.v1":
        failures.append({"kind": "runtime_schema_mismatch"})
    if data.get("valid") is not True:
        failures.append({"kind": "runtime_not_valid"})
    components = data.get("components")
    required = {
        "interpreter", "editable_root", "pth", "import_roots",
        "source_lineage", "process_command", "systemd_wrapper",
        "target_marker", "runtime_provenance_receipt",
    }
    if not isinstance(components, dict):
        failures.append({"kind": "runtime_components_missing"})
        components = {}
    for component in sorted(required):
        row = components.get(component)
        if (
            not isinstance(row, dict)
            or row.get("ok") is not True
            or not _is_sha256(row.get("evidence_sha256"))
        ):
            failures.append({
                "kind": "runtime_component_invalid",
                "component": component,
            })
    return _result(
        "runtime", full_path, passed=not failures, failures=failures, data=data
    )


def _validate_audit(
    repo_root: Path, manifest_path: Path, audit_root: Path
) -> dict[str, Any]:
    full_manifest = repo_root / manifest_path
    manifest = _load_json(full_manifest)
    failures: list[dict[str, Any]] = []
    cited = {
        row.get("cycle_id"): row
        for row in manifest.get("audit_cycle_trees", [])
        if isinstance(row, dict)
    }
    cycle_receipts: list[dict[str, Any]] = []
    for cycle_id in _REQUIRED_AUDIT_CYCLES:
        cycle_path = audit_root / cycle_id
        files: list[dict[str, str]] = []
        for filename in _REQUIRED_AUDIT_FILES:
            path = cycle_path / filename
            digest = _file_sha256(path)
            if not digest:
                failures.append({
                    "kind": "audit_file_missing",
                    "cycle_id": cycle_id,
                    "filename": filename,
                })
            files.append({"filename": filename, "sha256": digest})
        digest = _sha256_hex(_canonical_json_bytes({
            "cycle_id": cycle_id, "files": files
        }))
        cited_row = cited.get(cycle_id)
        if not cited_row:
            failures.append({
                "kind": "audit_cycle_not_cited",
                "cycle_id": cycle_id,
            })
        elif (
            cited_row.get("is_complete") is not True
            or cited_row.get("provenance_digest") != digest
        ):
            failures.append({
                "kind": "audit_cycle_digest_or_status_mismatch",
                "cycle_id": cycle_id,
                "expected": digest,
                "actual": cited_row.get("provenance_digest"),
            })
        cycle_receipts.append({
            "cycle_id": cycle_id,
            "provenance_digest": digest,
            "files": files,
        })
    data = {"manifest": manifest, "cycle_receipts": cycle_receipts}
    return _result(
        "audit", full_manifest, passed=not failures, failures=failures, data=data
    )


def _validate_forced_completion(
    repo_root: Path, plan_dir: Path, acceptance_receipt_path: Path
) -> dict[str, Any]:
    forced_path = plan_dir / "operator_forced_chain_completion.json"
    if not forced_path.is_absolute():
        forced_path = repo_root / forced_path
    forced = _load_json(forced_path)
    receipt_path = (
        acceptance_receipt_path
        if acceptance_receipt_path.is_absolute()
        else repo_root / acceptance_receipt_path
    )
    receipt = _load_json(receipt_path)
    failures: list[dict[str, Any]] = []
    if forced:
        if receipt.get("schema") != "m11.acceptance-receipt.v1":
            failures.append({"kind": "forced_done_without_acceptance_receipt"})
        if receipt.get("decision") != "accepted":
            failures.append({"kind": "acceptance_receipt_not_accepted"})
        if receipt.get("forced_completion_sha256") != _file_sha256(forced_path):
            failures.append({"kind": "acceptance_receipt_forced_digest_mismatch"})
        if receipt.get("independent_verifier") is not True:
            failures.append({"kind": "acceptance_receipt_not_independent"})
    return _result(
        "forced_completion_guard",
        forced_path,
        passed=not failures,
        failures=failures,
        data={"forced_completion": forced, "acceptance_receipt": receipt},
    )


def _normalize_available_artifacts(
    manifest: dict[str, Any],
) -> dict[str, str | None]:
    """Extract artifact availability from a manifest or direct mapping."""
    available: dict[str, str | None] = {}
    for family_name in PREDECESSOR_FAMILIES:
        value = manifest.get(family_name)
        if value is None:
            available[family_name] = None
        elif isinstance(value, str):
            available[family_name] = value
        elif isinstance(value, dict):
            available[family_name] = str(value.get("digest") or value.get("path") or "")
        else:
            available[family_name] = str(value)
    return available


def _try_runtime_vectors() -> dict[str, Any]:
    """Attempt to produce M11 runtime vectors; fail gracefully if unavailable."""
    try:
        from arnold_pipelines.megaplan.cloud.runtime_provenance import (
            m11_bound_runtime_identity,
        )
        identity = m11_bound_runtime_identity()
        if identity.get("valid", False):
            return {
                "available": True,
                "schema": identity.get("schema", ""),
                "content_sha256": identity.get("content_sha256", ""),
                "components": {
                    k: {"ok": v.get("ok", False)}
                    for k, v in identity.get("components", {}).items()
                },
            }
        else:
            return {
                "available": True,
                "schema": identity.get("schema", ""),
                "content_sha256": identity.get("content_sha256", ""),
                "valid": False,
                "errors": identity.get("errors", []),
            }
    except Exception:
        return {"available": False, "error": "runtime_provenance unavailable"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate M11 cross-contract acceptance evidence"
    )
    parser.add_argument("--owner", default="T9", help="Task ID owning this aggregate")
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path("evidence/m11-predecessor-artifacts.json"),
        help="Content-addressed predecessor wrapper manifest",
    )
    parser.add_argument(
        "--digests",
        type=Path,
        help="Path to a JSON file mapping family → expected digest",
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        help="Path to a JSON file mapping family → current schedule phase",
    )
    parser.add_argument(
        "--c01-c20",
        type=Path,
        default=Path("evidence/m10-c01-c20-conformance.json"),
        help="Path to M10 C01-C20 conformance evidence",
    )
    parser.add_argument(
        "--f01-f17",
        type=Path,
        default=Path("evidence/m10-f01-f17-fault-matrix.json"),
        help="Path to F01-F17 fault-matrix evidence",
    )
    parser.add_argument(
        "--m5",
        type=Path,
        default=Path("evidence/m5-evidence.json"),
        help="Path to M5 evidence",
    )
    parser.add_argument(
        "--a7",
        type=Path,
        default=Path("evidence/a7-evidence.json"),
        help="Path to A7 evidence",
    )
    parser.add_argument(
        "--audit-trees",
        type=Path,
        default=Path("evidence/m11-genuine-block-candidate/manifest.json"),
        help="Path to audit-cycle trees manifest",
    )
    parser.add_argument(
        "--recovery-ledger",
        type=Path,
        default=Path("evidence/m11-recovery-latency-ledger.json"),
        help="Path to recovery latency ledger",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("evidence/m11-cross-contract-acceptance.json"),
        help="Output path for the acceptance report",
    )
    parser.add_argument(
        "--audit-root",
        type=Path,
        default=Path("/workspace/audit-reports"),
    )
    parser.add_argument(
        "--plan-dir",
        type=Path,
        default=Path(
            ".megaplan/plans/m11-cross-contract-acceptance-20260728-1035"
        ),
    )
    parser.add_argument(
        "--acceptance-receipt",
        type=Path,
        default=Path("evidence/m11-acceptance-receipt.json"),
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    wrapper_results = {
        family: _validate_predecessor_wrapper(repo_root, family, _FAMILY_PATHS[family])
        for family in _WRAPPER_FAMILIES
    }
    manifest_result = _validate_predecessor_manifest(
        repo_root, args.artifacts, wrapper_results
    )
    artifact_results: dict[str, dict[str, Any]] = {
        **wrapper_results,
        "route": _validate_route(repo_root, _FAMILY_PATHS["route"]),
        "wbc": _validate_wbc(repo_root, _FAMILY_PATHS["wbc"]),
        "genuine_block": _validate_genuine_block(
            repo_root, _FAMILY_PATHS["genuine_block"]
        ),
        "recovery": _validate_recovery(repo_root, _FAMILY_PATHS["recovery"]),
        "no_debt": _validate_no_debt(repo_root, _FAMILY_PATHS["no_debt"]),
        "runtime": _validate_runtime_file(repo_root, _FAMILY_PATHS["runtime"]),
        "audit": _validate_audit(
            repo_root, _FAMILY_PATHS["audit"], args.audit_root
        ),
    }
    forced_guard = _validate_forced_completion(
        repo_root, args.plan_dir, args.acceptance_receipt
    )

    records: list[PrerequisiteRecord] = []
    for family in PREDECESSOR_FAMILIES:
        result = artifact_results[family]
        records.append(PrerequisiteRecord(
            owner=args.owner,
            artifact=result["path"],
            digest=result["file_sha256"],
            expected_class=family,
            next_action=(
                "" if result["passed"]
                else f"resolve {family} validation failures"
            ),
            status=(
                PrerequisiteStatus.SATISFIED
                if result["passed"]
                else PrerequisiteStatus.BLOCKED
            ),
            detail=(
                f"{family} content and hashes validated"
                if result["passed"]
                else json.dumps(result["failures"], sort_keys=True)
            ),
        ))

    predecessor_results = [
        adapter
        for family in _WRAPPER_FAMILIES
        for adapter in wrapper_results[family]["data"].get("adapter_results", [])
    ]

    runtime_vectors = _try_runtime_vectors()

    # ── Debt gate (Step 5) ─────────────────────────────────────────────
    all_evidence_parts: list[dict[str, Any]] = [
        {r.expected_class: r.to_dict() for r in records},
        {"predecessor_adapters": predecessor_results},
        {
            "artifact_validation": {
                family: {
                    "passed": result["passed"],
                    "failures": result["failures"],
                }
                for family, result in artifact_results.items()
            }
        },
    ]
    evidence_text = json.dumps(all_evidence_parts, indent=2, sort_keys=True)
    debt_gate_result = m11_debt_gate(evidence_text=evidence_text)

    # ── Typed outcome ──────────────────────────────────────────────────
    all_satisfied = all(
        r.status is PrerequisiteStatus.SATISFIED for r in records
    )
    all_predecessors_passed = (
        all(result["passed"] for result in wrapper_results.values())
        and manifest_result["passed"]
    )
    audit_passed = artifact_results["audit"]["passed"]
    debt_passed = (
        debt_gate_result["passed"] and artifact_results["no_debt"]["passed"]
    )
    runtime_available = runtime_vectors.get("available", False)
    runtime_valid = runtime_vectors.get("valid", False)
    runtime_ok = (
        runtime_available
        and runtime_valid
        and artifact_results["runtime"]["passed"]
    )
    forced_guard_ok = forced_guard["passed"]

    typed_outcome = "complete" if (
        all_satisfied and all_predecessors_passed and audit_passed
        and debt_passed and runtime_ok and forced_guard_ok
    ) else "m11_prerequisite_incomplete"

    # ── Content hash ───────────────────────────────────────────────────
    generated_at = datetime.now(timezone.utc).isoformat()

    # Build report skeleton
    status_counts: dict[str, int] = {}
    for r in records:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

    refs: dict[str, Any] = {
        "route": _FAMILY_PATHS["route"].as_posix(),
        "canary": "evidence/m9-idle-canary-evidence.json",
        "genuine_block": _FAMILY_PATHS["genuine_block"].as_posix(),
        "recovery": _FAMILY_PATHS["recovery"].as_posix(),
        "audit": _FAMILY_PATHS["audit"].as_posix(),
        "runtime": _FAMILY_PATHS["runtime"].as_posix(),
        "no_debt": _FAMILY_PATHS["no_debt"].as_posix(),
        "predecessor_manifest": manifest_result["path"],
        "acceptance_receipt": args.acceptance_receipt.as_posix(),
    }

    report: dict[str, Any] = {
        "schema": "m11.cross_contract_acceptance.v1",
        "schema_descriptor": schema_descriptor(),
        "owner": args.owner,
        "generated_at": generated_at,
        "typed_outcome": typed_outcome,
        "runtime_vectors": runtime_vectors,
        "prerequisite_records": [r.to_dict() for r in records],
        "predecessor_adapter_results": predecessor_results,
        "artifact_validation": {
            family: {
                key: value for key, value in result.items() if key != "data"
            }
            for family, result in artifact_results.items()
        },
        "predecessor_manifest_validation": {
            key: value for key, value in manifest_result.items() if key != "data"
        },
        "forced_completion_guard": {
            key: value for key, value in forced_guard.items() if key != "data"
        },
        "audit_recovery_result": {
            "passed": (
                artifact_results["audit"]["passed"]
                and artifact_results["recovery"]["passed"]
            ),
            "audit_failures": artifact_results["audit"]["failures"],
            "recovery_failures": artifact_results["recovery"]["failures"],
        },
        "debt_gate": debt_gate_result,
        "refs": refs,
        "summary": {
            "total_families": len(PREDECESSOR_FAMILIES),
            "status_counts": status_counts,
            "all_satisfied": all_satisfied,
            "all_predecessors_passed": all_predecessors_passed,
            "audit_passed": audit_passed,
            "debt_gate_passed": debt_passed,
            "runtime_vectors_ok": runtime_ok,
            "forced_completion_guard_passed": forced_guard_ok,
            "blockers": [
                r.to_dict()
                for r in records
                if r.status in (PrerequisiteStatus.BLOCKED, PrerequisiteStatus.EXPIRED)
            ] + (
                [] if manifest_result["passed"] else [{
                    "expected_class": "predecessor_manifest",
                    "artifact": manifest_result["path"],
                    "detail": manifest_result["failures"],
                }]
            ) + (
                [] if forced_guard_ok else [{
                    "expected_class": "forced_completion_guard",
                    "artifact": forced_guard["path"],
                    "detail": forced_guard["failures"],
                }]
            ),
        },
    }

    # Compute and inject content hash
    report["content_hash"] = _compute_content_hash(report)

    # ── Write output ───────────────────────────────────────────────────
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"M11 acceptance report written to {args.out}")
    print(f"  Families: {report['summary']['total_families']}")
    print(f"  Statuses: {status_counts}")
    print(f"  Typed outcome: {typed_outcome}")
    print(f"  Content hash: {report['content_hash'][:24]}...")

    return 0 if typed_outcome == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
