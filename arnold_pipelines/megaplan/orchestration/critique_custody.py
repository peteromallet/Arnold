"""Fail-closed custody for critique findings across planning stages.

The model-facing critique schema is not an authority boundary.  This module
materializes every flagged finding as a stable flag, writes an immutable
production receipt, joins every receipt to explicit resolution evidence, and
binds the resulting clearance to the exact finalized task graph.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan._core import (
    atomic_write_json,
    configured_robustness,
    latest_plan_path,
    load_flag_registry,
    now_utc,
    read_json,
    sha256_file,
    workflow_includes_step,
)
from arnold_pipelines.megaplan.flags import synthesize_critique_flags
from arnold_pipelines.megaplan.orchestration.task_feasibility import task_contract_hash
from arnold_pipelines.megaplan.types import PlanState


CUSTODY_SCHEMA_VERSION = "megaplan-critique-custody-v1"
CLEARANCE_SCHEMA_VERSION = "megaplan-critique-clearance-v1"
FINAL_BINDING_SCHEMA_VERSION = "megaplan-finalize-critique-binding-v1"
_PLACEHOLDER_FLAG_IDS = {"", "FLAG-000", "UNKNOWN", "N/A"}
_ALLOWED_FINDING_KEYS = {
    "detail",
    "flagged",
    "category",
    "severity_hint",
    "evidence",
    "finding_id",
}


class CritiqueCustodyError(ValueError):
    """One or more custody invariants failed."""

    def __init__(self, code: str, issues: Sequence[str]) -> None:
        self.code = code
        self.issues = tuple(str(issue) for issue in issues)
        super().__init__(f"{code}: " + "; ".join(self.issues))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _stable_finding_id(flag: Mapping[str, Any]) -> str:
    identity = {
        "source_check_id": flag.get("source_check_id"),
        "concern": str(flag.get("concern") or "").strip(),
        "category": flag.get("category"),
        "severity_hint": flag.get("severity_hint"),
        "evidence": str(flag.get("evidence") or "").strip(),
    }
    return "CF-" + hashlib.sha256(_canonical_bytes(identity)).hexdigest()[:20].upper()


def canonical_critique_flag_id(flag: Mapping[str, Any]) -> str:
    """Return the reducer-owned identity for a normalized critique finding."""
    return _stable_finding_id(flag)


def _normalize_flag_ids(payload: dict[str, Any]) -> None:
    flags = payload.get("flags")
    if not isinstance(flags, list):
        raise CritiqueCustodyError("critique_flags_malformed", ["flags must be an array"])
    producer_id_counts: dict[str, int] = {}
    for raw_flag in flags:
        if isinstance(raw_flag, dict) and isinstance(raw_flag.get("id"), str):
            producer_id = raw_flag["id"].strip()
            producer_id_counts[producer_id] = producer_id_counts.get(producer_id, 0) + 1
    seen: dict[str, int] = {}
    remapped: dict[str, set[str]] = {}
    issues: list[str] = []
    for index, raw_flag in enumerate(flags):
        if not isinstance(raw_flag, dict):
            issues.append(f"flags[{index}] is not an object")
            continue
        producer_id = raw_flag.get("id")
        if not isinstance(producer_id, str):
            issues.append(f"flags[{index}].id is not a string")
            continue
        for field in ("concern", "category", "severity_hint", "evidence"):
            value = raw_flag.get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(f"flags[{index}].{field} must be a non-empty string")
        canonical_id = producer_id.strip()
        reducer_must_own_id = (
            canonical_id.upper() in _PLACEHOLDER_FLAG_IDS
            or producer_id_counts.get(canonical_id, 0) > 1
        )
        if reducer_must_own_id:
            canonical_id = canonical_critique_flag_id(raw_flag)
            if producer_id.strip() and "producer_flag_id" not in raw_flag:
                raw_flag["producer_flag_id"] = producer_id.strip()
            raw_flag["id"] = canonical_id
        if not canonical_id:
            issues.append(f"flags[{index}].id is empty")
            continue
        remapped.setdefault(producer_id.strip(), set()).add(canonical_id)
        if canonical_id in seen:
            issues.append(
                f"duplicate canonical flag id {canonical_id!r} at "
                f"flags[{seen[canonical_id]}] and flags[{index}]"
            )
        seen[canonical_id] = index
    if issues:
        raise CritiqueCustodyError("critique_finding_identity_invalid", issues)
    for key in ("verified_flag_ids", "disputed_flag_ids"):
        values = payload.get(key)
        if isinstance(values, list):
            normalized_values: list[Any] = []
            for value in values:
                candidates = remapped.get(value, set())
                if len(candidates) > 1:
                    raise CritiqueCustodyError(
                        "critique_finding_reference_ambiguous",
                        [f"{key} local id {value!r} maps to {sorted(candidates)!r}"],
                    )
                normalized_values.append(next(iter(candidates)) if candidates else value)
            payload[key] = normalized_values


def prepare_critique_payload(
    payload: dict[str, Any],
    *,
    expected_check_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """Materialize and validate the canonical finding set before persistence."""
    synthesize_critique_flags(payload)
    issues: list[str] = []
    checks = payload.get("checks")
    if not isinstance(checks, list):
        raise CritiqueCustodyError("critique_checks_malformed", ["checks must be an array"])
    expected = list(expected_check_ids)
    observed: list[str] = []
    flagged_findings: list[tuple[str, str]] = []
    for check_index, check in enumerate(checks):
        if not isinstance(check, dict):
            issues.append(f"checks[{check_index}] is not an object")
            continue
        check_id = check.get("id")
        if not isinstance(check_id, str) or not check_id:
            issues.append(f"checks[{check_index}].id is missing")
            continue
        observed.append(check_id)
        findings = check.get("findings")
        if not isinstance(findings, list):
            issues.append(f"check {check_id!r} findings is not an array")
            continue
        seen_details: set[str] = set()
        for finding_index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                issues.append(f"check {check_id!r} finding {finding_index} is not an object")
                continue
            unknown = sorted(set(finding) - _ALLOWED_FINDING_KEYS)
            if unknown:
                issues.append(
                    f"check {check_id!r} finding {finding_index} has unknown fields {unknown!r}"
                )
            detail = finding.get("detail")
            if not isinstance(detail, str) or not detail.strip():
                issues.append(f"check {check_id!r} finding {finding_index} has empty detail")
                continue
            if not isinstance(finding.get("flagged"), bool):
                issues.append(f"check {check_id!r} finding {finding_index} has non-boolean flagged")
                continue
            normalized_detail = " ".join(detail.split())
            if normalized_detail in seen_details:
                issues.append(f"check {check_id!r} contains duplicate finding {normalized_detail!r}")
            seen_details.add(normalized_detail)
            if finding["flagged"]:
                flagged_findings.append((check_id, detail.strip()))
    if len(observed) != len(set(observed)):
        issues.append("critique contains duplicate check ids")
    if set(observed) != set(expected) or len(observed) != len(expected):
        issues.append(f"expected checks {expected!r}, observed {observed!r}")
    if issues:
        raise CritiqueCustodyError("critique_findings_malformed", issues)

    _normalize_flag_ids(payload)
    flags = payload["flags"]
    coverage_issues: list[str] = []
    for check_id, detail in flagged_findings:
        matches = [
            flag
            for flag in flags
            if isinstance(flag, dict)
            and flag.get("source_check_id") == check_id
            and str(flag.get("evidence") or "").strip() == detail
        ]
        if len(matches) != 1:
            coverage_issues.append(
                f"flagged finding from {check_id!r} maps to {len(matches)} top-level flags: {detail!r}"
            )
    if coverage_issues:
        raise CritiqueCustodyError("critique_finding_mapping_invalid", coverage_issues)
    return flags


def write_critique_production_receipt(
    plan_dir: Path,
    state: PlanState,
    payload: dict[str, Any],
    *,
    expected_check_ids: Sequence[str],
) -> dict[str, Any]:
    """Persist immutable custody evidence for one canonical critique artifact."""
    flags = prepare_critique_payload(payload, expected_check_ids=expected_check_ids)
    iteration = int(state["iteration"])
    critique_name = f"critique_v{iteration}.json"
    critique_path = plan_dir / critique_name
    if not critique_path.exists():
        raise CritiqueCustodyError(
            "critique_artifact_missing",
            [f"{critique_name} must be persisted before its custody receipt"],
        )
    plan_path = latest_plan_path(plan_dir, state)
    findings: list[dict[str, Any]] = []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        finding_id = _stable_finding_id(flag)
        findings.append(
            {
                "finding_id": finding_id,
                "flag_id": flag["id"],
                "source_check_id": flag.get("source_check_id"),
                "category": flag.get("category"),
                "producer_category": flag.get("producer_category", flag.get("category")),
                "severity_hint": flag.get("severity_hint"),
                "producer_severity": flag.get("producer_severity", flag.get("severity_hint")),
                "blocking": flag.get("severity_hint") != "likely-minor",
                "concern": flag.get("concern", ""),
                "evidence": flag.get("evidence", ""),
                "evidence_digest": _digest(flag.get("evidence", "")),
            }
        )
    raw_candidates = [
        plan_dir / f"critique_raw_v{iteration}.txt",
        *sorted(plan_dir.glob(f"critique_check_*_producer_v{iteration}.json")),
        *sorted(plan_dir.glob(f"critique_check_*_raw_v{iteration}.txt")),
    ]
    raw_sources = [
        {"artifact": path.name, "sha256": sha256_file(path)}
        for path in raw_candidates
        if path.exists() and path.is_file()
    ]
    if findings and not raw_sources:
        raise CritiqueCustodyError(
            "critique_raw_evidence_missing",
            ["substantive findings require at least one persisted producer/raw source"],
        )
    receipt = {
        "schema_version": CUSTODY_SCHEMA_VERSION,
        "iteration": iteration,
        "produced_at": now_utc(),
        "plan_artifact": plan_path.name,
        "plan_sha256": sha256_file(plan_path),
        "critique_artifact": critique_name,
        "critique_sha256": sha256_file(critique_path),
        "critique_payload_digest": _digest(payload),
        "raw_sources": raw_sources,
        "expected_check_ids": list(expected_check_ids),
        "finding_count": len(findings),
        "finding_ids": [finding["finding_id"] for finding in findings],
        "flag_ids": [finding["flag_id"] for finding in findings],
        "findings": findings,
        "normalization": {
            "flagged_check_findings": sum(
                1
                for check in payload.get("checks", [])
                if isinstance(check, dict)
                for finding in check.get("findings", [])
                if isinstance(finding, dict) and finding.get("flagged") is True
            ),
            "canonical_flags": len(findings),
            "loss_count": 0,
        },
        "admitted": True,
    }
    receipt["receipt_digest"] = _digest(receipt)
    atomic_write_json(plan_dir / f"critique_custody_v{iteration}.json", receipt)
    return receipt


def _validate_production_receipt(plan_dir: Path, receipt: Mapping[str, Any]) -> None:
    issues: list[str] = []
    if receipt.get("schema_version") != CUSTODY_SCHEMA_VERSION or receipt.get("admitted") is not True:
        issues.append("unsupported or non-admitted production receipt")
    unsigned_receipt = dict(receipt)
    stored_receipt_digest = unsigned_receipt.pop("receipt_digest", None)
    if stored_receipt_digest != _digest(unsigned_receipt):
        issues.append("production receipt digest mismatch")
    for field in ("plan_artifact", "critique_artifact"):
        name = receipt.get(field)
        if not isinstance(name, str) or not name or Path(name).name != name:
            issues.append(f"{field} is not a safe artifact basename")
    plan_name = receipt.get("plan_artifact")
    if isinstance(plan_name, str):
        plan_path = plan_dir / plan_name
        if not plan_path.exists():
            issues.append(f"missing source plan artifact {plan_name}")
        elif receipt.get("plan_sha256") != sha256_file(plan_path):
            issues.append(f"source plan artifact hash mismatch for {plan_name}")
    critique_name = receipt.get("critique_artifact")
    if isinstance(critique_name, str):
        critique_path = plan_dir / critique_name
        if not critique_path.exists():
            issues.append(f"missing critique artifact {critique_name}")
        elif receipt.get("critique_sha256") != sha256_file(critique_path):
            issues.append(f"critique artifact hash mismatch for {critique_name}")
        else:
            critique = read_json(critique_path)
            if receipt.get("critique_payload_digest") != _digest(critique):
                issues.append(f"critique payload digest mismatch for {critique_name}")
            payload_ids = [
                flag.get("id")
                for flag in critique.get("flags", [])
                if isinstance(flag, dict)
            ]
            if payload_ids != receipt.get("flag_ids"):
                issues.append(f"critique flags do not match receipt for {critique_name}")
            expected_findings = [
                {
                    "finding_id": _stable_finding_id(flag),
                    "flag_id": flag.get("id"),
                    "source_check_id": flag.get("source_check_id"),
                    "category": flag.get("category"),
                    "producer_category": flag.get("producer_category", flag.get("category")),
                    "severity_hint": flag.get("severity_hint"),
                    "producer_severity": flag.get("producer_severity", flag.get("severity_hint")),
                    "blocking": flag.get("severity_hint") != "likely-minor",
                    "concern": flag.get("concern", ""),
                    "evidence": flag.get("evidence", ""),
                    "evidence_digest": _digest(flag.get("evidence", "")),
                }
                for flag in critique.get("flags", [])
                if isinstance(flag, dict)
            ]
            if expected_findings != receipt.get("findings"):
                issues.append(f"critique finding content does not match receipt for {critique_name}")
    raw_sources = receipt.get("raw_sources")
    if not isinstance(raw_sources, list):
        issues.append("receipt raw_sources is not an array")
    else:
        for source in raw_sources:
            if not isinstance(source, Mapping):
                issues.append("raw source row is not an object")
                continue
            name = source.get("artifact")
            if not isinstance(name, str) or Path(name).name != name or not (plan_dir / name).exists():
                issues.append(f"raw source artifact is missing or unsafe: {name!r}")
            elif source.get("sha256") != sha256_file(plan_dir / name):
                issues.append(f"raw source hash mismatch for {name}")
    findings = receipt.get("findings")
    if not isinstance(findings, list):
        issues.append("receipt findings is not an array")
    else:
        finding_ids = [item.get("finding_id") for item in findings if isinstance(item, dict)]
        flag_ids = [item.get("flag_id") for item in findings if isinstance(item, dict)]
        if len(finding_ids) != len(findings) or len(set(finding_ids)) != len(finding_ids):
            issues.append("receipt finding identities are missing or duplicated")
        if len(flag_ids) != len(findings) or len(set(flag_ids)) != len(flag_ids):
            issues.append("receipt flag mappings are missing or duplicated")
        if finding_ids != receipt.get("finding_ids") or flag_ids != receipt.get("flag_ids"):
            issues.append("receipt summary ids differ from finding rows")
        if receipt.get("finding_count") != len(findings):
            issues.append("receipt finding_count differs from finding rows")
    if receipt.get("normalization", {}).get("loss_count") != 0:
        issues.append("receipt reports lossy normalization")
    if issues:
        raise CritiqueCustodyError("critique_custody_receipt_invalid", issues)


def validate_gate_input_custody(plan_dir: Path, state: PlanState) -> dict[str, Any]:
    """Prove the latest critique and registry agree before gate dispatch."""
    iteration = int(state["iteration"])
    path = plan_dir / f"critique_custody_v{iteration}.json"
    if not path.exists():
        raise CritiqueCustodyError(
            "critique_custody_missing",
            [f"gate requires {path.name}; rerun critique"],
        )
    receipt = read_json(path)
    _validate_production_receipt(plan_dir, receipt)
    registry = load_flag_registry(plan_dir)
    registry_ids = {
        flag.get("id")
        for flag in registry.get("flags", [])
        if isinstance(flag, dict)
    }
    missing = [flag_id for flag_id in receipt.get("flag_ids", []) if flag_id not in registry_ids]
    if missing:
        raise CritiqueCustodyError(
            "critique_registry_mapping_missing",
            [f"receipt flags missing from registry: {missing!r}"],
        )
    return {
        "schema_version": CUSTODY_SCHEMA_VERSION,
        "receipt": path.name,
        "receipt_sha256": sha256_file(path),
        "finding_count": receipt["finding_count"],
        "finding_ids": receipt["finding_ids"],
        "flag_ids": receipt["flag_ids"],
        "loss_count": 0,
        "admitted": True,
    }


def _receipt_paths(plan_dir: Path) -> list[Path]:
    def iteration(path: Path) -> int:
        match = re.fullmatch(r"critique_custody_v(\d+)\.json", path.name)
        return int(match.group(1)) if match else -1

    return sorted(plan_dir.glob("critique_custody_v*.json"), key=iteration)


def _validated_plan_lineage(
    plan_dir: Path,
    state: PlanState,
) -> dict[str, tuple[int, str]]:
    """Return the exact, ordered plan lineage or fail closed on drift."""
    records = state.get("plan_versions")
    if not isinstance(records, list) or not records:
        raise CritiqueCustodyError(
            "critique_plan_lineage_invalid",
            ["plan_versions must be a non-empty array"],
        )
    lineage: dict[str, tuple[int, str]] = {}
    issues: list[str] = []
    previous_version = -1
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            issues.append(f"plan version row {index} is not an object")
            continue
        name = record.get("file")
        version = record.get("version")
        declared_sha = record.get("hash")
        if not isinstance(name, str) or not name or Path(name).name != name:
            issues.append(f"plan version row {index} has an unsafe artifact reference")
            continue
        if name in lineage:
            issues.append(f"plan lineage repeats artifact {name}")
            continue
        if not isinstance(version, int) or version <= previous_version:
            issues.append(f"plan lineage version is not strictly increasing at {name}")
        else:
            previous_version = version
        path = plan_dir / name
        if not path.exists():
            issues.append(f"plan lineage artifact is missing: {name}")
            continue
        actual_sha = sha256_file(path)
        if not isinstance(declared_sha, str) or declared_sha != actual_sha:
            issues.append(f"plan lineage hash mismatch for {name}")
            continue
        lineage[name] = (index, actual_sha)
    if issues:
        raise CritiqueCustodyError("critique_plan_lineage_invalid", issues)
    return lineage


def _resolution_for_finding(
    flag: Mapping[str, Any],
    finding: Mapping[str, Any],
    *,
    current_plan_name: str,
    source_plan_name: str,
    plan_lineage: Mapping[str, tuple[int, str]],
    gate_expected: bool,
) -> dict[str, Any]:
    flag_id = str(finding.get("flag_id"))
    status = flag.get("status")
    resolution = flag.get("resolution") if isinstance(flag.get("resolution"), dict) else {}
    gate_resolution = (
        flag.get("gate_resolution") if isinstance(flag.get("gate_resolution"), dict) else {}
    )
    addressed_plan_name = flag.get("addressed_in")
    source_plan = plan_lineage.get(source_plan_name)
    addressed_plan = (
        plan_lineage.get(addressed_plan_name)
        if isinstance(addressed_plan_name, str)
        else None
    )
    current_plan = plan_lineage.get(current_plan_name)
    plan_mutated_on_current_lineage = bool(
        source_plan is not None
        and addressed_plan is not None
        and current_plan is not None
        and source_plan[0] < addressed_plan[0] <= current_plan[0]
    )
    fixed_claim = (
        resolution.get("kind") == "fixed"
        and isinstance(resolution.get("claim"), str)
        and bool(resolution["claim"].strip())
        and isinstance(resolution.get("where"), str)
        and bool(resolution["where"].strip())
        and plan_mutated_on_current_lineage
    )
    if status == "verified" and fixed_claim:
        assert addressed_plan is not None
        return {
            "finding_id": finding["finding_id"],
            "flag_id": flag_id,
            "disposition": "verified_plan_mutation",
            "plan_artifact": addressed_plan_name,
            "plan_sha256": addressed_plan[1],
            "evidence": gate_resolution.get("evidence") or flag.get("verify_rationale") or resolution.get("claim"),
        }
    if status == "gate_disputed" and gate_expected:
        evidence = gate_resolution.get("evidence")
        if isinstance(evidence, str) and evidence.strip():
            return {
                "finding_id": finding["finding_id"],
                "flag_id": flag_id,
                "disposition": "invalidated_with_evidence",
                "evidence": evidence,
            }
    if status == "accepted_tradeoff" and finding.get("blocking") is False:
        rationale = gate_resolution.get("rationale")
        if isinstance(rationale, str) and rationale.strip():
            return {
                "finding_id": finding["finding_id"],
                "flag_id": flag_id,
                "disposition": "minor_tradeoff",
                "evidence": rationale,
            }
    if status == "addressed" and not gate_expected and fixed_claim:
        assert addressed_plan is not None
        return {
            "finding_id": finding["finding_id"],
            "flag_id": flag_id,
            "disposition": "plan_mutation_light_workflow",
            "plan_artifact": addressed_plan_name,
            "plan_sha256": addressed_plan[1],
            "evidence": resolution.get("claim"),
        }
    raise CritiqueCustodyError(
        "critique_finding_unresolved",
        [
            f"finding {finding.get('finding_id')} / flag {flag_id} remains {status!r}; "
            "it needs a traceable plan mutation plus verification, or an evidence-backed invalidation"
        ],
    )


def write_critique_clearance(plan_dir: Path, state: PlanState) -> dict[str, Any]:
    """Join every production receipt to current resolution evidence."""
    receipt_paths = _receipt_paths(plan_dir)
    robustness = configured_robustness(state)
    critique_expected = workflow_includes_step(robustness, "critique")
    gate_expected = workflow_includes_step(robustness, "gate")
    if critique_expected and not receipt_paths:
        raise CritiqueCustodyError(
            "critique_custody_missing",
            ["workflow includes critique but has no production receipt"],
        )
    current_plan = latest_plan_path(plan_dir, state)
    plan_lineage = _validated_plan_lineage(plan_dir, state)
    current_plan_sha = plan_lineage[current_plan.name][1]
    registry = load_flag_registry(plan_dir)
    by_id = {
        str(flag.get("id")): flag
        for flag in registry.get("flags", [])
        if isinstance(flag, dict) and flag.get("id")
    }
    identities: dict[str, str] = {}
    resolutions: list[dict[str, Any]] = []
    source_receipts: list[dict[str, Any]] = []
    latest_occurrences: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for path in receipt_paths:
        receipt = read_json(path)
        _validate_production_receipt(plan_dir, receipt)
        source_receipts.append({"artifact": path.name, "sha256": sha256_file(path)})
        for finding in receipt.get("findings", []):
            flag_id = str(finding.get("flag_id"))
            finding_id = str(finding.get("finding_id"))
            prior_identity = identities.get(flag_id)
            if prior_identity is not None and prior_identity != finding_id:
                raise CritiqueCustodyError(
                    "critique_finding_identity_reused",
                    [f"flag {flag_id!r} changed identity from {prior_identity} to {finding_id}"],
                )
            identities[flag_id] = finding_id
            # Later critique rounds supersede the occurrence context for the
            # same stable finding. A finding that recurs on the current plan
            # cannot be cleared using an older plan mutation receipt.
            latest_occurrences[finding_id] = (finding, receipt)
    for finding, receipt in latest_occurrences.values():
        finding_id = str(finding.get("finding_id"))
        flag_id = str(finding.get("flag_id"))
        flag = by_id.get(flag_id)
        if flag is None:
            raise CritiqueCustodyError(
                "critique_registry_mapping_missing",
                [f"finding {finding_id} has no registry flag {flag_id!r}"],
            )
        resolutions.append(
            _resolution_for_finding(
                flag,
                finding,
                current_plan_name=current_plan.name,
                source_plan_name=str(receipt.get("plan_artifact")),
                plan_lineage=plan_lineage,
                gate_expected=gate_expected,
            )
        )
    clearance = {
        "schema_version": CLEARANCE_SCHEMA_VERSION,
        "produced_at": now_utc(),
        "workflow": {
            "robustness": robustness,
            "critique_expected": critique_expected,
            "gate_expected": gate_expected,
        },
        "source_receipts": source_receipts,
        "plan_artifact": current_plan.name,
        "plan_sha256": current_plan_sha,
        "finding_count": len(resolutions),
        "finding_ids": [item["finding_id"] for item in resolutions],
        "resolutions": resolutions,
        "admitted": True,
    }
    clearance["clearance_digest"] = _digest(clearance)
    atomic_write_json(plan_dir / "critique_clearance.json", clearance)
    return clearance


def bind_finalize_custody(
    plan_dir: Path,
    payload: dict[str, Any],
    clearance: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind current clearance to the exact post-mutation finalized graph."""
    clearance_path = plan_dir / "critique_clearance.json"
    if not clearance_path.exists():
        raise CritiqueCustodyError("critique_clearance_missing", [clearance_path.name])
    validate_finalize_resolution_coverage(payload, clearance)
    binding = {
        "schema_version": FINAL_BINDING_SCHEMA_VERSION,
        "clearance_artifact": clearance_path.name,
        "clearance_sha256": sha256_file(clearance_path),
        "clearance_digest": clearance.get("clearance_digest"),
        "plan_artifact": clearance.get("plan_artifact"),
        "plan_sha256": clearance.get("plan_sha256"),
        "finding_count": clearance.get("finding_count"),
        "finding_ids": clearance.get("finding_ids", []),
        "task_contract_hash": task_contract_hash(payload),
        "resolution_coverage_digest": _digest(payload.get("critique_resolution_coverage", [])),
        "revalidated_at": now_utc(),
    }
    payload["critique_custody"] = binding
    return binding


def validate_finalize_resolution_coverage(
    payload: Mapping[str, Any],
    clearance: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Require an exact typed finding-to-final-task join from the finalizer."""
    expected_ids = clearance.get("finding_ids", [])
    if not isinstance(expected_ids, list) or any(not isinstance(item, str) for item in expected_ids):
        raise CritiqueCustodyError(
            "critique_clearance_invalid",
            ["clearance finding_ids must be an array of strings"],
        )
    raw_rows = payload.get("critique_resolution_coverage", [])
    if not isinstance(raw_rows, list):
        raise CritiqueCustodyError(
            "finalize_critique_coverage_invalid",
            ["critique_resolution_coverage must be an array"],
        )
    task_ids = {
        task.get("id")
        for task in payload.get("tasks", [])
        if isinstance(task, Mapping) and isinstance(task.get("id"), str)
    }
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    observed: list[str] = []
    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, Mapping):
            issues.append(f"coverage row {index} is not an object")
            continue
        finding_id = raw_row.get("finding_id")
        mapped_tasks = raw_row.get("task_ids")
        evidence = raw_row.get("resolution_evidence")
        if not isinstance(finding_id, str) or not finding_id:
            issues.append(f"coverage row {index} has no finding_id")
            continue
        observed.append(finding_id)
        if (
            not isinstance(mapped_tasks, list)
            or not mapped_tasks
            or any(not isinstance(task_id, str) or task_id not in task_ids for task_id in mapped_tasks)
            or len(set(mapped_tasks)) != len(mapped_tasks)
        ):
            issues.append(f"finding {finding_id} has missing, duplicate, or unknown task_ids")
        if not isinstance(evidence, str) or not evidence.strip():
            issues.append(f"finding {finding_id} has no resolution_evidence")
        rows.append(dict(raw_row))
    if len(observed) != len(set(observed)):
        issues.append("critique_resolution_coverage contains duplicate finding ids")
    if set(observed) != set(expected_ids) or len(observed) != len(expected_ids):
        issues.append(f"coverage expected findings {expected_ids!r}, observed {observed!r}")
    if issues:
        raise CritiqueCustodyError("finalize_critique_coverage_invalid", issues)
    return rows


def assert_finalize_custody(
    plan_dir: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Reject execution when v2 custody or exact graph evidence is missing."""
    if payload.get("task_contract_version") != 2:
        return None
    binding = payload.get("critique_custody")
    if not isinstance(binding, Mapping):
        raise CritiqueCustodyError(
            "finalize_critique_custody_missing",
            ["task_contract_version=2 requires critique_custody"],
        )
    issues: list[str] = []
    if binding.get("schema_version") != FINAL_BINDING_SCHEMA_VERSION:
        issues.append("unsupported finalize custody binding")
    if binding.get("task_contract_hash") != task_contract_hash(payload):
        issues.append("finalized graph hash differs from critique custody binding")
    if binding.get("resolution_coverage_digest") != _digest(
        payload.get("critique_resolution_coverage", [])
    ):
        issues.append("finalizer finding-to-task coverage differs from custody binding")
    clearance_name = binding.get("clearance_artifact")
    if not isinstance(clearance_name, str) or Path(clearance_name).name != clearance_name:
        issues.append("invalid clearance artifact reference")
    else:
        clearance_path = plan_dir / clearance_name
        if not clearance_path.exists():
            issues.append(f"missing clearance artifact {clearance_name}")
        elif binding.get("clearance_sha256") != sha256_file(clearance_path):
            issues.append("clearance artifact hash mismatch")
        else:
            clearance = read_json(clearance_path)
            if clearance.get("admitted") is not True:
                issues.append("clearance is not admitted")
            unsigned_clearance = dict(clearance)
            stored_clearance_digest = unsigned_clearance.pop("clearance_digest", None)
            if stored_clearance_digest != _digest(unsigned_clearance):
                issues.append("clearance content digest mismatch")
            if binding.get("clearance_digest") != clearance.get("clearance_digest"):
                issues.append("clearance digest mismatch")
            if binding.get("finding_count") != clearance.get("finding_count"):
                issues.append("binding finding_count differs from clearance")
            if binding.get("finding_ids") != clearance.get("finding_ids"):
                issues.append("binding finding_ids differ from clearance")
            try:
                validate_finalize_resolution_coverage(payload, clearance)
            except CritiqueCustodyError as error:
                issues.extend(error.issues)
            resolution_ids = [
                row.get("finding_id")
                for row in clearance.get("resolutions", [])
                if isinstance(row, Mapping)
            ]
            if resolution_ids != clearance.get("finding_ids"):
                issues.append("clearance resolution rows differ from finding ids")
            for resolution in clearance.get("resolutions", []):
                if not isinstance(resolution, Mapping):
                    issues.append("clearance resolution row is malformed")
                    continue
                plan_artifact = resolution.get("plan_artifact")
                if plan_artifact is None:
                    continue
                if (
                    not isinstance(plan_artifact, str)
                    or Path(plan_artifact).name != plan_artifact
                ):
                    issues.append("clearance resolution plan artifact is unsafe")
                    continue
                resolution_plan = plan_dir / plan_artifact
                if (
                    not resolution_plan.exists()
                    or resolution.get("plan_sha256") != sha256_file(resolution_plan)
                ):
                    issues.append(
                        f"clearance resolution plan hash mismatch for {plan_artifact}"
                    )
            for source in clearance.get("source_receipts", []):
                if not isinstance(source, Mapping):
                    issues.append("clearance source receipt row is malformed")
                    continue
                source_name = source.get("artifact")
                if not isinstance(source_name, str) or Path(source_name).name != source_name:
                    issues.append("clearance source receipt reference is unsafe")
                    continue
                source_path = plan_dir / source_name
                if not source_path.exists() or source.get("sha256") != sha256_file(source_path):
                    issues.append(f"clearance source receipt mismatch for {source_name}")
                    continue
                try:
                    _validate_production_receipt(plan_dir, read_json(source_path))
                except CritiqueCustodyError as error:
                    issues.extend(error.issues)
            plan_name = clearance.get("plan_artifact")
            if not isinstance(plan_name, str) or not (plan_dir / plan_name).exists():
                issues.append("clearance plan artifact is missing")
            elif clearance.get("plan_sha256") != sha256_file(plan_dir / plan_name):
                issues.append("clearance plan hash mismatch")
    if issues:
        raise CritiqueCustodyError("finalize_critique_custody_invalid", issues)
    return dict(binding)


__all__ = [
    "CritiqueCustodyError",
    "assert_finalize_custody",
    "bind_finalize_custody",
    "prepare_critique_payload",
    "validate_gate_input_custody",
    "validate_finalize_resolution_coverage",
    "write_critique_clearance",
    "write_critique_production_receipt",
]
