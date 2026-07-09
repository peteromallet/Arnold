#!/usr/bin/env python3
"""Validate the final Megaplan native-representation conformance ledger."""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. Install with: pip install pyyaml")


EXPECTED_SCHEMA = "arnold.megaplan_native_representation.conformance.v1"
EXPECTED_TARGET_REPORT = "docs/arnold/megaplan-native-representation-report.md"
EXPECTED_TRACEABILITY = "docs/arnold/megaplan-native-representation-traceability.yaml"
EXPECTED_EVIDENCE_BUNDLE = "docs/arnold/megaplan-native-representation-evidence.yaml"
EXPECTED_EVIDENCE_SCHEMA = "arnold.megaplan_native_representation.evidence_bundle.v1"
VALID_STATUSES = {"implemented", "deferred"}
REQUIRED_ROW_FIELDS = {"id", "status", "semantic_carrier", "proof_categories", "proof_artifacts"}
IMPLEMENTED_REQUIRED_ROW_FIELDS = {"carrier_evidence"}
DEFERRED_REQUIRED_ROW_FIELDS = {"downstream_owner", "blocking_proof", "reason"}
IMPLEMENTED_SEMANTIC_CARRIERS = {
    "canonical_source",
    "declared_policy",
    "audited_pure_phase_body",
}
DEFERRED_SEMANTIC_CARRIERS = {"explicit_deferral"}
CANONICAL_SOURCE_SUFFIXES = {".pypeline"}
PURE_PHASE_BODY_SUFFIXES = {".py"}
POLICY_CARRIER_SUFFIXES = {".pypeline", ".py", ".yaml", ".yml", ".json", ".md"}
APPROVED_IMPLEMENTED_EVIDENCE_KINDS = {"source_checker"}
BOUNDARY_RECEIPT_REQUIRED_EFFECTS = {"receipt", "authority"}
BOUNDARY_PHASE_RESULT_REQUIRED_EFFECTS = {"state_history", "phase_result"}
BOUNDARY_SEMANTIC_HEALTH_STATUS = "healthy"


@dataclass(frozen=True)
class EvidenceSourceSpan:
    path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class CarrierCheckerEvidence:
    row_id: str
    semantic_carrier: str
    kind: str
    checker: str
    carrier_path: str
    carrier_sha256: str
    proof_artifact_path: str
    proof_artifact_sha256: str
    source_span: EvidenceSourceSpan | None
    policy_object: str | None


@dataclass(frozen=True)
class BoundaryContractEvidence:
    row_id: str
    contract_id: str
    covered_effects: tuple[str, ...]
    contract_path: str
    contract_sha256: str
    source_span: EvidenceSourceSpan | None
    policy_object: str | None


@dataclass(frozen=True)
class BoundaryReceiptEvidence:
    row_id: str
    contract_id: str
    covered_effects: tuple[str, ...]
    receipt_path: str
    receipt_sha256: str


@dataclass(frozen=True)
class BoundarySemanticHealthEvidence:
    row_id: str
    contract_id: str
    covered_effects: tuple[str, ...]
    proof_artifact_path: str
    proof_artifact_sha256: str
    status: str


@dataclass(frozen=True)
class BoundaryPhaseResultEvidence:
    row_id: str
    contract_id: str
    covered_effects: tuple[str, ...]
    phase_result_path: str
    phase_result_sha256: str


@dataclass(frozen=True)
class EvidenceBundle:
    schema: str
    records: tuple[CarrierCheckerEvidence, ...]
    boundary_contract_records: tuple[BoundaryContractEvidence, ...]
    boundary_receipt_records: tuple[BoundaryReceiptEvidence, ...]
    boundary_semantic_health_records: tuple[BoundarySemanticHealthEvidence, ...]
    boundary_phase_result_records: tuple[BoundaryPhaseResultEvidence, ...]


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


def _label_list(value: Any, *, field: str, row_id: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"row {row_id!r} field {field!r} must be a list[str]")
    if not value:
        raise ValueError(f"row {row_id!r} field {field!r} must not be empty")
    labels: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"row {row_id!r} field {field!r} must contain non-empty strings")
        labels.append(item.strip())
    return labels


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


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _require_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ValueError(f"evidence_bundle {field} must be a sha256:<hex> string")
    digest = value.removeprefix("sha256:")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"evidence_bundle {field} must be a sha256:<hex> string")
    return value


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"evidence_bundle {field} must be a non-empty string")
    return value.strip()


def _parse_source_span(value: Any) -> EvidenceSourceSpan:
    if not isinstance(value, dict):
        raise ValueError("evidence_bundle source_span must be a mapping")
    path = value.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("evidence_bundle source_span.path must be a non-empty string")
    normalized_path = _normalize_repo_path(path, field="source_span.path", row_id="<evidence>")
    start_line = value.get("start_line")
    end_line = value.get("end_line")
    if not isinstance(start_line, int) or start_line < 1:
        raise ValueError("evidence_bundle source_span.start_line must be an integer >= 1")
    if not isinstance(end_line, int) or end_line < start_line:
        raise ValueError("evidence_bundle source_span.end_line must be an integer >= start_line")
    return EvidenceSourceSpan(
        path=normalized_path,
        start_line=start_line,
        end_line=end_line,
    )


def _is_historical_conformance_report(path: str) -> bool:
    candidate = Path(path)
    if candidate.parent != Path("docs/arnold"):
        return False
    name = candidate.name
    return "conformance-report" in name or name == "megaplan-native-representation-report.md"


def _parse_evidence_record(value: Any) -> CarrierCheckerEvidence:
    if not isinstance(value, dict):
        raise ValueError("evidence_bundle records entries must be mappings")
    row_id = value.get("row_id")
    if not isinstance(row_id, str) or not row_id.strip():
        raise ValueError("evidence_bundle row_id must be a non-empty string")
    semantic_carrier = value.get("semantic_carrier")
    if not isinstance(semantic_carrier, str) or not semantic_carrier.strip():
        raise ValueError(f"evidence_bundle row {row_id!r} semantic_carrier must be a non-empty string")
    kind = value.get("kind")
    if not isinstance(kind, str) or kind not in APPROVED_IMPLEMENTED_EVIDENCE_KINDS:
        raise ValueError(
            f"evidence_bundle row {row_id!r} kind must be one of "
            f"{sorted(APPROVED_IMPLEMENTED_EVIDENCE_KINDS)}"
        )
    checker = value.get("checker")
    if not isinstance(checker, str) or not checker.strip():
        raise ValueError(f"evidence_bundle row {row_id!r} checker must be a non-empty string")
    carrier_path = _normalize_repo_path(
        value.get("carrier_path"),
        field="carrier_path",
        row_id=row_id,
    )
    proof_artifact_path = _normalize_repo_path(
        value.get("proof_artifact_path"),
        field="proof_artifact_path",
        row_id=row_id,
    )
    if _is_historical_conformance_report(carrier_path):
        raise ValueError(
            f"evidence_bundle row {row_id!r} carrier_path {carrier_path!r} cannot use a "
            "historical conformance report as authority"
        )
    if _is_historical_conformance_report(proof_artifact_path):
        raise ValueError(
            f"evidence_bundle row {row_id!r} proof_artifact_path {proof_artifact_path!r} cannot "
            "use a historical conformance report as authority"
        )
    carrier_sha256 = _require_sha256(
        value.get("carrier_sha256"),
        field=f"rows[{row_id}].carrier_sha256",
    )
    proof_artifact_sha256 = _require_sha256(
        value.get("proof_artifact_sha256"),
        field=f"rows[{row_id}].proof_artifact_sha256",
    )
    source_span_value = value.get("source_span")
    source_span = _parse_source_span(source_span_value) if source_span_value is not None else None
    policy_object_value = value.get("policy_object")
    if policy_object_value is not None and (
        not isinstance(policy_object_value, str) or not policy_object_value.strip()
    ):
        raise ValueError(f"evidence_bundle row {row_id!r} policy_object must be a non-empty string")
    policy_object = policy_object_value.strip() if isinstance(policy_object_value, str) else None
    if source_span is None and policy_object is None:
        raise ValueError(
            f"evidence_bundle row {row_id!r} must include source_span or policy_object"
        )
    if semantic_carrier != "declared_policy" and source_span is None:
        raise ValueError(
            f"evidence_bundle row {row_id!r} carrier {semantic_carrier!r} requires source_span"
        )
    if source_span is not None and source_span.path != carrier_path:
        raise ValueError(
            f"evidence_bundle row {row_id!r} source_span.path {source_span.path!r} must match "
            f"carrier_path {carrier_path!r}"
        )
    return CarrierCheckerEvidence(
        row_id=row_id,
        semantic_carrier=semantic_carrier,
        kind=kind,
        checker=checker.strip(),
        carrier_path=carrier_path,
        carrier_sha256=carrier_sha256,
        proof_artifact_path=proof_artifact_path,
        proof_artifact_sha256=proof_artifact_sha256,
        source_span=source_span,
        policy_object=policy_object,
    )


def _parse_boundary_covered_effects(value: Any, *, row_id: str, contract_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(
            f"evidence_bundle row {row_id!r} contract {contract_id!r} covered_effects must be "
            "a non-empty list[str]"
        )
    effects: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"evidence_bundle row {row_id!r} contract {contract_id!r} covered_effects must "
                "contain non-empty strings"
            )
        effect = item.strip()
        if effect not in effects:
            effects.append(effect)
    return tuple(effects)


def _parse_boundary_contract_record(value: Any) -> BoundaryContractEvidence:
    if not isinstance(value, dict):
        raise ValueError("evidence_bundle boundary_contract_records entries must be mappings")
    row_id = _require_non_empty_string(value.get("row_id"), field="boundary_contract_records.row_id")
    contract_id = _require_non_empty_string(
        value.get("contract_id"),
        field=f"boundary_contract_records[{row_id}].contract_id",
    )
    covered_effects = _parse_boundary_covered_effects(
        value.get("covered_effects"),
        row_id=row_id,
        contract_id=contract_id,
    )
    contract_path = _normalize_repo_path(
        value.get("contract_path"),
        field="contract_path",
        row_id=row_id,
    )
    if _is_historical_conformance_report(contract_path):
        raise ValueError(
            f"evidence_bundle row {row_id!r} contract {contract_id!r} contract_path "
            f"{contract_path!r} cannot use a historical conformance report as authority"
        )
    contract_sha256 = _require_sha256(
        value.get("contract_sha256"),
        field=f"boundary_contract_records[{row_id}].contract_sha256",
    )
    source_span_value = value.get("source_span")
    source_span = _parse_source_span(source_span_value) if source_span_value is not None else None
    policy_object_value = value.get("policy_object")
    if policy_object_value is not None and (
        not isinstance(policy_object_value, str) or not policy_object_value.strip()
    ):
        raise ValueError(
            f"evidence_bundle row {row_id!r} contract {contract_id!r} policy_object must be a "
            "non-empty string"
        )
    policy_object = policy_object_value.strip() if isinstance(policy_object_value, str) else None
    if source_span is None and policy_object is None:
        raise ValueError(
            f"evidence_bundle row {row_id!r} contract {contract_id!r} must include source_span "
            "or policy_object"
        )
    if source_span is not None and source_span.path != contract_path:
        raise ValueError(
            f"evidence_bundle row {row_id!r} contract {contract_id!r} source_span.path "
            f"{source_span.path!r} must match contract_path {contract_path!r}"
        )
    return BoundaryContractEvidence(
        row_id=row_id,
        contract_id=contract_id,
        covered_effects=covered_effects,
        contract_path=contract_path,
        contract_sha256=contract_sha256,
        source_span=source_span,
        policy_object=policy_object,
    )


def _parse_boundary_receipt_record(value: Any) -> BoundaryReceiptEvidence:
    if not isinstance(value, dict):
        raise ValueError("evidence_bundle boundary_receipt_records entries must be mappings")
    row_id = _require_non_empty_string(value.get("row_id"), field="boundary_receipt_records.row_id")
    contract_id = _require_non_empty_string(
        value.get("contract_id"),
        field=f"boundary_receipt_records[{row_id}].contract_id",
    )
    covered_effects = _parse_boundary_covered_effects(
        value.get("covered_effects"),
        row_id=row_id,
        contract_id=contract_id,
    )
    receipt_path = _normalize_repo_path(
        value.get("receipt_path"),
        field="receipt_path",
        row_id=row_id,
    )
    if _is_historical_conformance_report(receipt_path):
        raise ValueError(
            f"evidence_bundle row {row_id!r} contract {contract_id!r} receipt_path "
            f"{receipt_path!r} cannot use a historical conformance report as authority"
        )
    receipt_sha256 = _require_sha256(
        value.get("receipt_sha256"),
        field=f"boundary_receipt_records[{row_id}].receipt_sha256",
    )
    return BoundaryReceiptEvidence(
        row_id=row_id,
        contract_id=contract_id,
        covered_effects=covered_effects,
        receipt_path=receipt_path,
        receipt_sha256=receipt_sha256,
    )


def _parse_boundary_semantic_health_record(value: Any) -> BoundarySemanticHealthEvidence:
    if not isinstance(value, dict):
        raise ValueError("evidence_bundle boundary_semantic_health_records entries must be mappings")
    row_id = _require_non_empty_string(
        value.get("row_id"),
        field="boundary_semantic_health_records.row_id",
    )
    contract_id = _require_non_empty_string(
        value.get("contract_id"),
        field=f"boundary_semantic_health_records[{row_id}].contract_id",
    )
    covered_effects = _parse_boundary_covered_effects(
        value.get("covered_effects"),
        row_id=row_id,
        contract_id=contract_id,
    )
    proof_artifact_path = _normalize_repo_path(
        value.get("proof_artifact_path"),
        field="proof_artifact_path",
        row_id=row_id,
    )
    if _is_historical_conformance_report(proof_artifact_path):
        raise ValueError(
            f"evidence_bundle row {row_id!r} contract {contract_id!r} proof_artifact_path "
            f"{proof_artifact_path!r} cannot use a historical conformance report as authority"
        )
    proof_artifact_sha256 = _require_sha256(
        value.get("proof_artifact_sha256"),
        field=f"boundary_semantic_health_records[{row_id}].proof_artifact_sha256",
    )
    status = _require_non_empty_string(
        value.get("status"),
        field=f"boundary_semantic_health_records[{row_id}].status",
    )
    return BoundarySemanticHealthEvidence(
        row_id=row_id,
        contract_id=contract_id,
        covered_effects=covered_effects,
        proof_artifact_path=proof_artifact_path,
        proof_artifact_sha256=proof_artifact_sha256,
        status=status,
    )


def _parse_boundary_phase_result_record(value: Any) -> BoundaryPhaseResultEvidence:
    if not isinstance(value, dict):
        raise ValueError("evidence_bundle boundary_phase_result_records entries must be mappings")
    row_id = _require_non_empty_string(
        value.get("row_id"),
        field="boundary_phase_result_records.row_id",
    )
    contract_id = _require_non_empty_string(
        value.get("contract_id"),
        field=f"boundary_phase_result_records[{row_id}].contract_id",
    )
    covered_effects = _parse_boundary_covered_effects(
        value.get("covered_effects"),
        row_id=row_id,
        contract_id=contract_id,
    )
    phase_result_path = _normalize_repo_path(
        value.get("phase_result_path"),
        field="phase_result_path",
        row_id=row_id,
    )
    if _is_historical_conformance_report(phase_result_path):
        raise ValueError(
            f"evidence_bundle row {row_id!r} contract {contract_id!r} phase_result_path "
            f"{phase_result_path!r} cannot use a historical conformance report as authority"
        )
    phase_result_sha256 = _require_sha256(
        value.get("phase_result_sha256"),
        field=f"boundary_phase_result_records[{row_id}].phase_result_sha256",
    )
    return BoundaryPhaseResultEvidence(
        row_id=row_id,
        contract_id=contract_id,
        covered_effects=covered_effects,
        phase_result_path=phase_result_path,
        phase_result_sha256=phase_result_sha256,
    )


def _load_evidence_bundle(path: Path) -> EvidenceBundle:
    payload = _load_yaml(path)
    schema = payload.get("schema")
    if schema != EXPECTED_EVIDENCE_SCHEMA:
        raise ValueError(f"evidence_bundle schema must be {EXPECTED_EVIDENCE_SCHEMA!r}")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("evidence_bundle records must be a list")
    boundary_contract_records = payload.get("boundary_contract_records", [])
    if not isinstance(boundary_contract_records, list):
        raise ValueError("evidence_bundle boundary_contract_records must be a list")
    boundary_receipt_records = payload.get("boundary_receipt_records", [])
    if not isinstance(boundary_receipt_records, list):
        raise ValueError("evidence_bundle boundary_receipt_records must be a list")
    boundary_semantic_health_records = payload.get("boundary_semantic_health_records", [])
    if not isinstance(boundary_semantic_health_records, list):
        raise ValueError("evidence_bundle boundary_semantic_health_records must be a list")
    boundary_phase_result_records = payload.get("boundary_phase_result_records", [])
    if not isinstance(boundary_phase_result_records, list):
        raise ValueError("evidence_bundle boundary_phase_result_records must be a list")
    return EvidenceBundle(
        schema=schema,
        records=tuple(_parse_evidence_record(record) for record in records),
        boundary_contract_records=tuple(
            _parse_boundary_contract_record(record) for record in boundary_contract_records
        ),
        boundary_receipt_records=tuple(
            _parse_boundary_receipt_record(record) for record in boundary_receipt_records
        ),
        boundary_semantic_health_records=tuple(
            _parse_boundary_semantic_health_record(record)
            for record in boundary_semantic_health_records
        ),
        boundary_phase_result_records=tuple(
            _parse_boundary_phase_result_record(record) for record in boundary_phase_result_records
        ),
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
            "canonical_source": set(CANONICAL_SOURCE_SUFFIXES),
            "audited_pure_phase_body": set(PURE_PHASE_BODY_SUFFIXES),
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


def _validate_boundary_path_hash(path: str, expected_sha256: str, *, repo_root: Path) -> bool:
    target = repo_root / path
    return target.is_file() and _sha256(target) == expected_sha256


def _coherent_boundary_contract_record(
    records: list[BoundaryContractEvidence],
    *,
    required_effects: set[str],
    allowed_effects: set[str],
    repo_root: Path,
) -> bool:
    for record in records:
        covered_effects = set(record.covered_effects)
        if not covered_effects <= allowed_effects:
            continue
        if not required_effects <= covered_effects:
            continue
        if not _validate_boundary_path_hash(
            record.contract_path,
            record.contract_sha256,
            repo_root=repo_root,
        ):
            continue
        return True
    return False


def _coherent_boundary_receipt_record(
    records: list[BoundaryReceiptEvidence],
    *,
    required_effects: set[str],
    allowed_effects: set[str],
    repo_root: Path,
) -> bool:
    for record in records:
        covered_effects = set(record.covered_effects)
        if not covered_effects <= allowed_effects:
            continue
        if not required_effects <= covered_effects:
            continue
        if not _validate_boundary_path_hash(
            record.receipt_path,
            record.receipt_sha256,
            repo_root=repo_root,
        ):
            continue
        return True
    return False


def _coherent_boundary_semantic_health_record(
    records: list[BoundarySemanticHealthEvidence],
    *,
    required_effects: set[str],
    allowed_effects: set[str],
    repo_root: Path,
) -> bool:
    for record in records:
        covered_effects = set(record.covered_effects)
        if not covered_effects <= allowed_effects:
            continue
        if not required_effects <= covered_effects:
            continue
        if record.status != BOUNDARY_SEMANTIC_HEALTH_STATUS:
            continue
        if not _validate_boundary_path_hash(
            record.proof_artifact_path,
            record.proof_artifact_sha256,
            repo_root=repo_root,
        ):
            continue
        return True
    return False


def _coherent_boundary_phase_result_record(
    records: list[BoundaryPhaseResultEvidence],
    *,
    required_effects: set[str],
    allowed_effects: set[str],
    repo_root: Path,
) -> bool:
    for record in records:
        covered_effects = set(record.covered_effects)
        if not covered_effects <= allowed_effects:
            continue
        if not required_effects <= covered_effects:
            continue
        if not _validate_boundary_path_hash(
            record.phase_result_path,
            record.phase_result_sha256,
            repo_root=repo_root,
        ):
            continue
        return True
    return False


def validate_conformance_ledger(
    *,
    repo_root: Path,
    conformance_path: Path,
    traceability_path: Path,
    evidence_bundle_path: Path | None = None,
) -> list[str]:
    """Return validation errors for a final conformance YAML ledger."""
    errors: list[str] = []
    try:
        conformance = _load_yaml(conformance_path)
        traceability = _load_yaml(traceability_path)
        evidence_bundle = _load_evidence_bundle(
            evidence_bundle_path
            if evidence_bundle_path is not None
            else repo_root / EXPECTED_EVIDENCE_BUNDLE
        )
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
        required_row_fields = _string_set_from_contract(
            machine_report,
            "required_row_fields",
            fallback=REQUIRED_ROW_FIELDS,
        )
        implemented_required_row_fields = _string_set_from_contract(
            machine_report,
            "implemented_required_row_fields",
            fallback=IMPLEMENTED_REQUIRED_ROW_FIELDS,
        )
        deferred_required_row_fields = _string_set_from_contract(
            machine_report,
            "deferred_required_row_fields",
            fallback=DEFERRED_REQUIRED_ROW_FIELDS,
        )
        carrier_suffixes = _suffix_contract(machine_report)
    except ValueError as exc:
        return [str(exc)]

    records_by_row_id: dict[str, list[CarrierCheckerEvidence]] = {}
    for record in evidence_bundle.records:
        records_by_row_id.setdefault(record.row_id, []).append(record)
    boundary_contract_records_by_key: dict[tuple[str, str], list[BoundaryContractEvidence]] = {}
    for record in evidence_bundle.boundary_contract_records:
        boundary_contract_records_by_key.setdefault((record.row_id, record.contract_id), []).append(record)
    boundary_receipt_records_by_key: dict[tuple[str, str], list[BoundaryReceiptEvidence]] = {}
    for record in evidence_bundle.boundary_receipt_records:
        boundary_receipt_records_by_key.setdefault((record.row_id, record.contract_id), []).append(record)
    boundary_semantic_health_records_by_key: dict[
        tuple[str, str], list[BoundarySemanticHealthEvidence]
    ] = {}
    for record in evidence_bundle.boundary_semantic_health_records:
        boundary_semantic_health_records_by_key.setdefault(
            (record.row_id, record.contract_id),
            [],
        ).append(record)
    boundary_phase_result_records_by_key: dict[
        tuple[str, str], list[BoundaryPhaseResultEvidence]
    ] = {}
    for record in evidence_bundle.boundary_phase_result_records:
        boundary_phase_result_records_by_key.setdefault(
            (record.row_id, record.contract_id),
            [],
        ).append(record)

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
    expected_ids = []
    traceability_proof_categories: dict[str, list[str]] = {}
    traceability_boundary_effects: dict[str, tuple[str, ...]] = {}
    traceability_boundary_contract_ids: dict[str, tuple[str, ...]] = {}
    allowed_proof_categories: set[str] = set()
    raw_boundary_effect_values = traceability.get("boundary_effect_values", [])
    if not isinstance(raw_boundary_effect_values, list) or not all(
        isinstance(item, str) and item.strip() for item in raw_boundary_effect_values
    ):
        errors.append("traceability boundary_effect_values must be a list[str]")
        allowed_boundary_effects: set[str] = set()
    else:
        allowed_boundary_effects = {item.strip() for item in raw_boundary_effect_values}
    for row in trace_rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        row_id = row["id"]
        expected_ids.append(row_id)
        try:
            proof_categories = _label_list(
                row.get("proof_artifacts"),
                field="traceability.proof_artifacts",
                row_id=row_id,
            )
        except ValueError as exc:
            errors.append(str(exc))
            proof_categories = []
        traceability_proof_categories[row_id] = proof_categories
        allowed_proof_categories.update(proof_categories)
        boundary_effects_value = row.get("boundary_effects_required")
        boundary_contract_ids_value = row.get("boundary_contract_ids")
        if boundary_effects_value is None:
            if boundary_contract_ids_value is not None:
                errors.append(
                    f"traceability row {row_id!r} boundary_contract_ids requires "
                    "boundary_effects_required"
                )
            continue
        try:
            boundary_effects = tuple(
                _label_list(
                    boundary_effects_value,
                    field="boundary_effects_required",
                    row_id=row_id,
                )
            )
            unknown_effects = sorted(set(boundary_effects) - allowed_boundary_effects)
            if unknown_effects:
                errors.append(
                    f"traceability row {row_id!r} boundary_effects_required contains unknown "
                    f"effects: {', '.join(unknown_effects)}"
                )
            traceability_boundary_effects[row_id] = boundary_effects
        except ValueError as exc:
            errors.append(str(exc))
            boundary_effects = ()
        try:
            contract_ids = tuple(
                _label_list(
                    boundary_contract_ids_value,
                    field="boundary_contract_ids",
                    row_id=row_id,
                )
            )
            traceability_boundary_contract_ids[row_id] = contract_ids
        except ValueError as exc:
            errors.append(str(exc))

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

        missing = sorted(required_row_fields - set(row))
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
            proof_categories = _label_list(
                row.get("proof_categories"),
                field="proof_categories",
                row_id=row_id,
            )
            unknown_categories = sorted(set(proof_categories) - allowed_proof_categories)
            if unknown_categories:
                errors.append(
                    f"row {row_id!r} proof_categories contains unknown labels: "
                    f"{', '.join(unknown_categories)}"
                )
            expected_categories = set(traceability_proof_categories.get(row_id, []))
            missing_categories = sorted(expected_categories - set(proof_categories))
            if missing_categories:
                errors.append(
                    f"row {row_id!r} proof_categories missing traceability labels: "
                    f"{', '.join(missing_categories)}"
                )
        except ValueError as exc:
            errors.append(str(exc))

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
            missing_deferred = sorted(deferred_required_row_fields - set(row))
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
            missing_implemented = sorted(implemented_required_row_fields - set(row))
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
                matching_records = records_by_row_id.get(row_id, [])
                if not matching_records:
                    errors.append(
                        f"row {row_id!r} implemented rows require current checker evidence in "
                        f"{evidence_bundle_path or (repo_root / EXPECTED_EVIDENCE_BUNDLE)}"
                    )
                for carrier_path in carrier_paths:
                    if _is_historical_conformance_report(carrier_path):
                        errors.append(
                            f"row {row_id!r} carrier_evidence path {carrier_path!r} cannot use a "
                            "historical conformance report as authority"
                        )
                        continue
                    path_records = [
                        record
                        for record in matching_records
                        if record.semantic_carrier == carrier and record.carrier_path == carrier_path
                    ]
                    if not path_records:
                        errors.append(
                            f"row {row_id!r} carrier_evidence path {carrier_path!r} lacks matching "
                            "current checker evidence"
                        )
                        continue
                    row_proof_paths = set(proof_paths)
                    matched = False
                    for record in path_records:
                        if record.proof_artifact_path not in row_proof_paths:
                            continue
                        carrier_target = repo_root / record.carrier_path
                        proof_target = repo_root / record.proof_artifact_path
                        if _sha256(carrier_target) != record.carrier_sha256:
                            continue
                        if _sha256(proof_target) != record.proof_artifact_sha256:
                            continue
                        matched = True
                        break
                    if not matched:
                        errors.append(
                            f"row {row_id!r} carrier_evidence path {carrier_path!r} lacks current "
                            "checker evidence with matching hashes and proof artifacts"
                        )
                required_boundary_effects = set(traceability_boundary_effects.get(row_id, ()))
                if required_boundary_effects:
                    contract_ids = traceability_boundary_contract_ids.get(row_id, ())
                    if not contract_ids:
                        errors.append(
                            f"row {row_id!r} traceability metadata must declare boundary_contract_ids"
                        )
                    receipt_effects = required_boundary_effects & BOUNDARY_RECEIPT_REQUIRED_EFFECTS
                    phase_result_effects = (
                        required_boundary_effects & BOUNDARY_PHASE_RESULT_REQUIRED_EFFECTS
                    )
                    for contract_id in contract_ids:
                        key = (row_id, contract_id)
                        if not _coherent_boundary_contract_record(
                            boundary_contract_records_by_key.get(key, []),
                            required_effects=required_boundary_effects,
                            allowed_effects=allowed_boundary_effects,
                            repo_root=repo_root,
                        ):
                            errors.append(
                                f"row {row_id!r} contract {contract_id!r} lacks coherent "
                                "boundary contract evidence"
                            )
                        if not _coherent_boundary_semantic_health_record(
                            boundary_semantic_health_records_by_key.get(key, []),
                            required_effects=required_boundary_effects,
                            allowed_effects=allowed_boundary_effects,
                            repo_root=repo_root,
                        ):
                            errors.append(
                                f"row {row_id!r} contract {contract_id!r} lacks coherent "
                                "boundary semantic-health evidence"
                            )
                        if receipt_effects and not _coherent_boundary_receipt_record(
                            boundary_receipt_records_by_key.get(key, []),
                            required_effects=receipt_effects,
                            allowed_effects=allowed_boundary_effects,
                            repo_root=repo_root,
                        ):
                            errors.append(
                                f"row {row_id!r} contract {contract_id!r} lacks coherent "
                                "boundary receipt evidence"
                            )
                        if phase_result_effects and not _coherent_boundary_phase_result_record(
                            boundary_phase_result_records_by_key.get(key, []),
                            required_effects=phase_result_effects,
                            allowed_effects=allowed_boundary_effects,
                            repo_root=repo_root,
                        ):
                            errors.append(
                                f"row {row_id!r} contract {contract_id!r} lacks coherent "
                                "boundary phase/result evidence"
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
    parser.add_argument(
        "--evidence-bundle",
        default=EXPECTED_EVIDENCE_BUNDLE,
        help="Path to megaplan-native-representation-evidence.yaml",
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
    evidence_bundle_path = Path(args.evidence_bundle)
    if not evidence_bundle_path.is_absolute():
        evidence_bundle_path = repo_root / evidence_bundle_path

    errors = validate_conformance_ledger(
        repo_root=repo_root,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated {conformance_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
