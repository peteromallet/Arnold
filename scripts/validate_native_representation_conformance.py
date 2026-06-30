#!/usr/bin/env python3
"""Validate the final Megaplan native-representation conformance ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. Install with: pip install pyyaml")


EXPECTED_SCHEMA = "arnold.megaplan_native_representation.conformance.v1"
EXPECTED_TARGET_REPORT = "docs/arnold/megaplan-native-representation-report.md"
EXPECTED_TRACEABILITY = "docs/arnold/megaplan-native-representation-traceability.yaml"
VALID_STATUSES = {"implemented", "deferred"}
REQUIRED_ROW_FIELDS = {"id", "status", "semantic_carrier", "proof_artifacts"}
IMPLEMENTED_REQUIRED_ROW_FIELDS = {"carrier_evidence"}
DEFERRED_REQUIRED_ROW_FIELDS = {"downstream_owner", "blocking_proof", "reason"}
IMPLEMENTED_SEMANTIC_CARRIERS = {
    "canonical_source",
    "declared_policy",
    "audited_pure_phase_body",
}
DEFERRED_SEMANTIC_CARRIERS = {"explicit_deferral"}
CODE_CARRIER_SUFFIXES = {".py"}
POLICY_CARRIER_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".md"}


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing file: {path}") from None
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def _normalize_repo_path(raw: str, *, field: str, row_id: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"row {row_id!r} field {field!r} must contain non-empty paths")
    text = raw.strip().replace("\\", "/")
    if text.startswith("/"):
        raise ValueError(f"row {row_id!r} field {field!r} path {text!r} must be repo-relative")
    parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError(f"row {row_id!r} field {field!r} path {text!r} escapes repo root")
        parts.append(part)
    if not parts:
        raise ValueError(f"row {row_id!r} field {field!r} path must not resolve to repo root")
    return "/".join(parts)


def _string_list(value: Any, *, field: str, row_id: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"row {row_id!r} field {field!r} must be a list[str]")
    if not value:
        raise ValueError(f"row {row_id!r} field {field!r} must not be empty")
    normalized: list[str] = []
    for item in value:
        normalized.append(_normalize_repo_path(item, field=field, row_id=row_id))
    return normalized


def _validate_paths_exist(paths: list[str], *, repo_root: Path, field: str, row_id: str) -> None:
    for path in paths:
        target = repo_root / path
        if not target.is_file():
            raise ValueError(f"row {row_id!r} field {field!r} path does not exist: {path}")


def _validate_carrier_evidence_shape(
    paths: list[str],
    *,
    carrier: str,
    row_id: str,
    suffixes: dict[str, set[str]],
) -> None:
    allowed = suffixes.get(carrier)
    if allowed is None:
        return
    for path in paths:
        suffix = Path(path).suffix
        if suffix not in allowed:
            raise ValueError(
                f"row {row_id!r} carrier_evidence path {path!r} has suffix "
                f"{suffix!r}; {carrier} requires one of {sorted(allowed)}"
            )


def _machine_report_contract(traceability: dict[str, Any]) -> dict[str, Any]:
    gate = traceability.get("final_conformance_gate")
    if not isinstance(gate, dict):
        raise ValueError("traceability missing final_conformance_gate mapping")
    report = gate.get("machine_readable_report")
    if not isinstance(report, dict):
        raise ValueError("traceability missing final_conformance_gate.machine_readable_report mapping")
    return report


def _traceability_target_report(traceability: dict[str, Any]) -> str:
    target_report = traceability.get("target_report", EXPECTED_TARGET_REPORT)
    if not isinstance(target_report, str) or not target_report.strip():
        raise ValueError("traceability target_report must be a non-empty string")
    return target_report.strip()


def _string_set_from_contract(
    contract: dict[str, Any],
    key: str,
    *,
    fallback: set[str],
) -> set[str]:
    value = contract.get(key)
    if value is None:
        return set(fallback)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"machine_readable_report.{key} must be a list[str]")
    return set(value)


def _suffix_contract(contract: dict[str, Any]) -> dict[str, set[str]]:
    raw = contract.get("carrier_evidence_suffixes")
    if raw is None:
        return {
            "canonical_source": set(CODE_CARRIER_SUFFIXES),
            "audited_pure_phase_body": set(CODE_CARRIER_SUFFIXES),
            "declared_policy": set(POLICY_CARRIER_SUFFIXES),
        }
    if not isinstance(raw, dict):
        raise ValueError("machine_readable_report.carrier_evidence_suffixes must be a mapping")
    suffixes: dict[str, set[str]] = {}
    for carrier, values in raw.items():
        if not isinstance(carrier, str):
            raise ValueError("machine_readable_report.carrier_evidence_suffixes keys must be strings")
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError(
                f"machine_readable_report.carrier_evidence_suffixes.{carrier} must be a list[str]"
            )
        suffixes[carrier] = set(values)
    return suffixes


def validate_conformance_ledger(
    *,
    repo_root: Path,
    conformance_path: Path,
    traceability_path: Path,
) -> list[str]:
    """Return validation errors for a final conformance YAML ledger."""
    errors: list[str] = []
    try:
        conformance = _load_yaml(conformance_path)
        traceability = _load_yaml(traceability_path)
        machine_report = _machine_report_contract(traceability)
        expected_target_report = _traceability_target_report(traceability)
        valid_statuses = _string_set_from_contract(
            machine_report,
            "row_status_values",
            fallback=VALID_STATUSES,
        )
        implemented_carriers = _string_set_from_contract(
            machine_report,
            "implemented_semantic_carriers",
            fallback=IMPLEMENTED_SEMANTIC_CARRIERS,
        )
        deferred_carriers = _string_set_from_contract(
            machine_report,
            "deferred_semantic_carriers",
            fallback=DEFERRED_SEMANTIC_CARRIERS,
        )
        carrier_suffixes = _suffix_contract(machine_report)
    except ValueError as exc:
        return [str(exc)]

    expected_schema = machine_report.get("schema", EXPECTED_SCHEMA)
    if conformance.get("schema") != expected_schema:
        errors.append(f"schema must be {expected_schema!r}")
    if conformance.get("target_report") != expected_target_report:
        errors.append(f"target_report must be {expected_target_report!r}")
    if conformance.get("traceability") != EXPECTED_TRACEABILITY:
        errors.append(f"traceability must be {EXPECTED_TRACEABILITY!r}")

    trace_rows = traceability.get("rows")
    if not isinstance(trace_rows, list):
        errors.append("traceability rows must be a list")
        trace_rows = []
    expected_ids = [
        row.get("id")
        for row in trace_rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    ]

    rows = conformance.get("rows")
    if not isinstance(rows, list):
        errors.append("rows must be a list")
        rows = []
    seen_ids: set[str] = set()
    actual_ids: list[str] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"rows[{index}] must be a mapping")
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            errors.append(f"rows[{index}] must have a non-empty string id")
            continue
        actual_ids.append(row_id)
        if row_id in seen_ids:
            errors.append(f"duplicate row id {row_id!r}")
        seen_ids.add(row_id)

        missing = sorted(REQUIRED_ROW_FIELDS - set(row))
        if missing:
            errors.append(f"row {row_id!r} missing required fields: {', '.join(missing)}")

        status = row.get("status")
        if status not in valid_statuses:
            errors.append(f"row {row_id!r} status must be one of {sorted(valid_statuses)}")
        carrier = row.get("semantic_carrier")
        if not isinstance(carrier, str) or not carrier.strip():
            errors.append(f"row {row_id!r} semantic_carrier must be a non-empty string")
        elif status == "implemented" and carrier not in implemented_carriers:
            errors.append(
                f"row {row_id!r} implemented semantic_carrier must be one of "
                f"{sorted(implemented_carriers)}"
            )
        elif status == "deferred" and carrier not in deferred_carriers:
            errors.append(
                f"row {row_id!r} deferred semantic_carrier must be one of "
                f"{sorted(deferred_carriers)}"
            )

        try:
            proof_paths = _string_list(row.get("proof_artifacts"), field="proof_artifacts", row_id=row_id)
            _validate_paths_exist(
                proof_paths,
                repo_root=repo_root,
                field="proof_artifacts",
                row_id=row_id,
            )
        except ValueError as exc:
            errors.append(str(exc))

        if status == "deferred":
            missing_deferred = sorted(DEFERRED_REQUIRED_ROW_FIELDS - set(row))
            if missing_deferred:
                errors.append(
                    f"row {row_id!r} missing deferred fields: {', '.join(missing_deferred)}"
                )
            for field in ("downstream_owner", "reason"):
                value = row.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"row {row_id!r} {field} must be a non-empty string")
            try:
                blocking_paths = _string_list(
                    row.get("blocking_proof"),
                    field="blocking_proof",
                    row_id=row_id,
                )
                _validate_paths_exist(
                    blocking_paths,
                    repo_root=repo_root,
                    field="blocking_proof",
                    row_id=row_id,
                )
            except ValueError as exc:
                errors.append(str(exc))
        elif status == "implemented":
            missing_implemented = sorted(IMPLEMENTED_REQUIRED_ROW_FIELDS - set(row))
            if missing_implemented:
                errors.append(
                    f"row {row_id!r} missing implemented fields: {', '.join(missing_implemented)}"
                )
            try:
                carrier_paths = _string_list(
                    row.get("carrier_evidence"),
                    field="carrier_evidence",
                    row_id=row_id,
                )
                _validate_paths_exist(
                    carrier_paths,
                    repo_root=repo_root,
                    field="carrier_evidence",
                    row_id=row_id,
                )
                _validate_carrier_evidence_shape(
                    carrier_paths,
                    carrier=carrier,
                    row_id=row_id,
                    suffixes=carrier_suffixes,
                )
            except ValueError as exc:
                errors.append(str(exc))

    if actual_ids != expected_ids:
        errors.append(
            "rows must cover every traceability id in order; "
            f"expected {expected_ids}, got {actual_ids}"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--conformance",
        default=EXPECTED_TRACEABILITY.replace("traceability", "conformance"),
        help="Path to megaplan-native-representation-conformance.yaml",
    )
    parser.add_argument(
        "--traceability",
        default=EXPECTED_TRACEABILITY,
        help="Path to megaplan-native-representation-traceability.yaml",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    conformance_path = Path(args.conformance)
    if not conformance_path.is_absolute():
        conformance_path = repo_root / conformance_path
    traceability_path = Path(args.traceability)
    if not traceability_path.is_absolute():
        traceability_path = repo_root / traceability_path

    errors = validate_conformance_ledger(
        repo_root=repo_root,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated {conformance_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
