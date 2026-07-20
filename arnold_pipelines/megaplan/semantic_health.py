"""Read-only semantic health inspection for declared Megaplan boundaries.

Loads the boundary contract registry, current state/history,
``phase_result.json``, step receipts, and ``boundary_receipts/`` from a
plan directory, then returns :class:`SemanticFinding` records for:

* missing required artifacts
* missing state/history effects
* missing boundary receipts
* stale phase result / state observations
* missing authority records

This module is intentionally read-only: it does not compute product
routes, next steps, or routing predicates, and it never mutates runtime
contracts.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Any

from arnold.workflow.boundary_evidence import (
    BoundaryReceipt,
    FindingSeverity,
    SemanticFinding,
)
from arnold.workflow.diagnostics import DiagnosticCode
from arnold_pipelines.megaplan.orchestration.override_authority import (
    override_authority_transition_is_active,
    validate_override_authority_record,
)
from arnold_pipelines.megaplan.workflows.boundary_contracts import (
    BOUNDARY_CONTRACTS,
    contract_satisfies_profile,
    diff_contracts,
    get_profile_by_kind,
    get_template_by_id,
)

log = logging.getLogger(__name__)

# ── phase → expected PlanCurrentState mapping ──────────────────────────
# After a phase completes, state.json current_state should be one of these.
_PHASE_TO_EXPECTED_STATE: dict[str, str] = {
    "prep": "prepped",
    "plan": "planned",
    "critique": "critiqued",
    "gate": "gated",
    "revise": "planned",  # revise completes → returns to plan/critique loop
}

# Execute is a multi-state phase: mid-flight boundaries (checkpoint, blocked,
# partial failure) keep ``current_phase == "execute"`` while terminal boundaries
# (no-review terminal) land in ``done`` or ``awaiting_human_verify``. A single
# post-phase ``current_state`` value is therefore not meaningful, so execute is
# intentionally absent from ``_PHASE_TO_EXPECTED_STATE``; the execute-specific
# terminal check (``_check_execute_terminal_state``) validates the accepted
# terminal set instead.
_EXECUTE_PHASE = "execute"
_EXECUTE_TERMINAL_STATES = {"done", "awaiting_human_verify"}
_EXECUTE_TERMINAL_BOUNDARY_IDS = {"execute_no_review_terminal"}
_EXECUTE_APPROVAL_BOUNDARY_IDS = {"execute_approval"}
_EXECUTE_AGGREGATE_BOUNDARY_IDS = {"execute_aggregate_promotion"}
_EXECUTE_CHECKPOINT_BOUNDARY_IDS = {"execute_batch_checkpoint", "execute_partial_failure"}
_REVIEW_CHILD_OUTPUTS_BOUNDARY_ID = "review_child_outputs"
_REVIEW_REDUCER_PROMOTION_BOUNDARY_ID = "review_reducer_promotion"
_REVIEW_REWORK_EFFECTS_BOUNDARY_ID = "review_rework_effects"
_REVIEW_HUMAN_VERIFICATION_BOUNDARY_ID = "review_human_verification"
_FINALIZE_ARTIFACTS_BOUNDARY_ID = "finalize_artifacts"
_FINALIZE_FALLBACK_BOUNDARY_ID = "finalize_fallback"
_FINAL_PROJECTION_BOUNDARY_ID = "final_projection"
_REVIEW_CURRENT_STATES = {"executed", "reviewed", "done", "awaiting_human_verify"}
_NATIVE_REVIEW_ROUTE_SIGNATURES = frozenset(
    {
        ("execute-batches", "default", "review-fan-in"),
        ("review-fan-in", "rework", "review-rework-execute-batches"),
        ("review-rework-execute-batches", "default", "review-rework-fan-in"),
    }
)
_REVIEW_CHILD_TRACE_DETAIL_KEYS = (
    "child_receipt_refs",
    "child_receipts",
    "child_trace_refs",
    "child_output_refs",
)

# ── public API ─────────────────────────────────────────────────────────


def inspect_semantic_health(plan_dir: Path) -> list[SemanticFinding]:
    """Run read-only health checks for all five S2 front-half boundaries.

    Returns a (possibly empty) list of :class:`SemanticFinding` records.
    Never raises — degenerate or missing plan-dir state produces findings
    instead.
    """
    findings: list[SemanticFinding] = []

    if not plan_dir.is_dir():
        findings.append(
            SemanticFinding(
                finding_id="SH-plan-dir-missing",
                boundary_id="*",
                description=f"plan directory does not exist: {plan_dir}",
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                details={"plan_dir": str(plan_dir)},
            )
        )
        return findings

    state = _load_state_json(plan_dir)
    history = _load_history(state)
    phase_result = _load_phase_result(plan_dir)

    for contract in BOUNDARY_CONTRACTS:
        findings.extend(
            _inspect_contract(
                plan_dir=plan_dir,
                contract=contract,
                state=state,
                history=history,
                phase_result=phase_result,
            )
        )

    return findings


# ── per-contract inspection ────────────────────────────────────────────


def _inspect_contract(
    *,
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
    history: list[dict[str, Any]],
    phase_result: dict[str, Any] | None,
) -> list[SemanticFinding]:
    """Run all health checks for a single BoundaryContract."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id
    phase = contract.phase.value if contract.phase else None

    # --- missing required artifacts ---
    findings.extend(_check_required_artifacts(plan_dir, contract))

    # --- missing state / history effects ---
    findings.extend(_check_state_effects(contract, state, history))

    # --- missing boundary receipt ---
    findings.extend(_check_boundary_receipt(plan_dir, contract))

    # --- stale phase result ---
    findings.extend(_check_phase_result(contract, phase_result))

    # --- stale state observations ---
    findings.extend(_check_state_observations(contract, state, phase))

    # --- missing authority records ---
    findings.extend(_check_authority_records(plan_dir, contract))

    # --- override authority receipt / evidence integrity ---
    findings.extend(_check_override_authority(plan_dir=plan_dir, contract=contract, state=state))

    # --- execute-phase read-only semantics (S4) ---
    findings.extend(_check_execute_semantics(plan_dir=plan_dir, contract=contract, state=state))

    # --- review/finalize read-only semantics (S5) ---
    findings.extend(
        _check_review_finalize_semantics(
            plan_dir=plan_dir,
            contract=contract,
            state=state,
            history=history,
        )
    )

    # --- profile/template metadata compliance ---
    findings.extend(
        _check_profile_template_metadata(contract)
    )

    return findings


# ── individual checks ──────────────────────────────────────────────────


def _check_required_artifacts(
    plan_dir: Path,
    contract: Any,
) -> list[SemanticFinding]:
    """Check that every required artifact file exists in *plan_dir*."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id

    for artifact in contract.required_artifacts:
        artifact_path = plan_dir / artifact
        if not artifact_path.is_file():
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-missing-artifact-{artifact}",
                    boundary_id=bid,
                    description=(
                        f"required artifact '{artifact}' is missing from "
                        f"plan directory for boundary '{bid}'"
                    ),
                    severity=FindingSeverity.ERROR,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                    contract_ref=bid,
                    details={
                        "missing_artifact": artifact,
                        "plan_dir": str(plan_dir),
                    },
                )
            )
    return findings


def _check_state_effects(
    contract: Any,
    state: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> list[SemanticFinding]:
    """Check that state.json and history reflect the expected boundary effects."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id
    phase = contract.phase.value if contract.phase else None

    if state is None:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-state-missing",
                boundary_id=bid,
                description=(
                    f"state.json is missing or unreadable; cannot verify "
                    f"boundary '{bid}' state effects"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=bid,
            )
        )
        return findings

    # --- check expected_state_delta keys ---
    for key, expected_value in contract.expected_state_delta.items():
        actual_value = state.get(key)
        if actual_value != expected_value:
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-state-delta-{key}",
                    boundary_id=bid,
                    description=(
                        f"state.json key '{key}' expected '{expected_value}' "
                        f"but got '{actual_value}' for boundary '{bid}'"
                    ),
                    severity=FindingSeverity.WARNING,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                    contract_ref=bid,
                    details={
                        "expected_key": key,
                        "expected_value": expected_value,
                        "actual_value": actual_value,
                    },
                )
            )

    # --- check PlanCurrentState against phase mapping ---
    if phase and phase in _PHASE_TO_EXPECTED_STATE:
        expected_cs = _PHASE_TO_EXPECTED_STATE[phase]
        actual_cs = state.get("current_state")
        if actual_cs != expected_cs:
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-current-state",
                    boundary_id=bid,
                    description=(
                        f"expected current_state '{expected_cs}' after "
                        f"phase '{phase}' but got '{actual_cs}' for "
                        f"boundary '{bid}'"
                    ),
                    severity=FindingSeverity.WARNING,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                    contract_ref=bid,
                    details={
                        "expected_current_state": expected_cs,
                        "actual_current_state": actual_cs,
                    },
                )
            )

    # --- check expected history entry ---
    if contract.expected_history_entry:
        found = any(
            isinstance(h, dict)
            and h.get("step") == phase
            and h.get("result") in ("success", None)
            for h in history
        )
        if not found:
            # Also try matching by the expected_history_entry string
            found_by_entry = any(
                isinstance(h, dict)
                and _history_matches_entry(h, contract.expected_history_entry)
                for h in history
            )
            if not found_by_entry:
                findings.append(
                    SemanticFinding(
                        finding_id=f"SH-{bid}-history-entry",
                        boundary_id=bid,
                        description=(
                            f"expected history entry "
                            f"'{contract.expected_history_entry}' not found "
                            f"for boundary '{bid}'"
                        ),
                        severity=FindingSeverity.WARNING,
                        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                        contract_ref=bid,
                        details={
                            "expected_history_entry": (
                                contract.expected_history_entry
                            ),
                            "history_length": len(history),
                        },
                    )
                )

    return findings


def _history_matches_entry(
    entry: dict[str, Any],
    expected: str,
) -> bool:
    """Check if a history entry matches an expected entry name.

    The expected value may be a step name like ``prep_completed`` or
    ``plan_completed``.  We match loosely: the entry's ``step`` field
    should be a prefix of the expected string (e.g. ``prep`` matches
    ``prep_completed``).
    """
    step = entry.get("step")
    if not isinstance(step, str):
        return False
    # e.g. expected="prep_completed" → step prefix "prep"
    prefix = expected.split("_")[0] if "_" in expected else expected
    return step == prefix or expected.startswith(step + "_")


def _check_boundary_receipt(
    plan_dir: Path,
    contract: Any,
) -> list[SemanticFinding]:
    """Check that a durable boundary receipt exists for *contract*."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id

    if not contract.receipt_required:
        return findings

    receipt_path = plan_dir / "boundary_receipts" / f"{bid}.json"
    if not receipt_path.is_file():
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-receipt-missing",
                boundary_id=bid,
                description=(
                    f"boundary receipt is missing for '{bid}' "
                    f"(expected at {receipt_path})"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=bid,
                evidence_ref=str(receipt_path),
            )
        )
    else:
        # Receipt exists — check it can be deserialized
        try:
            raw = json.loads(receipt_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("boundary_id") != bid:
                findings.append(
                    SemanticFinding(
                        finding_id=f"SH-{bid}-receipt-malformed",
                        boundary_id=bid,
                        description=(
                            f"boundary receipt at {receipt_path} is "
                            f"malformed or has wrong boundary_id"
                        ),
                        severity=FindingSeverity.ERROR,
                        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                        contract_ref=bid,
                        evidence_ref=str(receipt_path),
                    )
                )
        except (json.JSONDecodeError, OSError) as exc:
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-receipt-unreadable",
                    boundary_id=bid,
                    description=(
                        f"boundary receipt at {receipt_path} could not be "
                        f"read: {exc}"
                    ),
                    severity=FindingSeverity.ERROR,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                    contract_ref=bid,
                    evidence_ref=str(receipt_path),
                    details={"error": str(exc)},
                )
            )

    return findings


def _check_phase_result(
    contract: Any,
    phase_result: dict[str, Any] | None,
) -> list[SemanticFinding]:
    """Check that phase_result.json exists and is not stale."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id
    phase = contract.phase.value if contract.phase else None

    if not contract.phase_result_required:
        return findings

    if phase_result is None:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-phase-result-missing",
                boundary_id=bid,
                description=(
                    f"phase_result.json is missing for boundary '{bid}'"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=bid,
            )
        )
        return findings

    # Check phase matches
    recorded_phase = phase_result.get("phase")
    if recorded_phase != phase:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-phase-result-stale-phase",
                boundary_id=bid,
                description=(
                    f"phase_result.json records phase '{recorded_phase}' "
                    f"but boundary '{bid}' expects phase '{phase}'"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=bid,
                details={
                    "expected_phase": phase,
                    "recorded_phase": recorded_phase,
                },
            )
        )

    # Check exit_kind is success (warning if not)
    exit_kind = phase_result.get("exit_kind")
    if exit_kind and exit_kind != "success":
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-phase-result-non-success",
                boundary_id=bid,
                description=(
                    f"phase_result.json for boundary '{bid}' has "
                    f"exit_kind='{exit_kind}' (expected 'success')"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=bid,
                details={"exit_kind": exit_kind},
            )
        )

    return findings


def _check_state_observations(
    contract: Any,
    state: dict[str, Any] | None,
    phase: str | None,
) -> list[SemanticFinding]:
    """Check for stale state observations vs contract expectations."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id

    if state is None or phase is None:
        return findings

    # Check iteration is non-zero
    iteration = state.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-state-stale-iteration",
                boundary_id=bid,
                description=(
                    f"state.json iteration is {iteration!r} for boundary "
                    f"'{bid}'; expected >= 1"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=bid,
                details={"iteration": iteration},
            )
        )

    # Check that state has a created_at timestamp
    created_at = state.get("created_at")
    if not created_at:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-state-missing-created-at",
                boundary_id=bid,
                description=(
                    f"state.json is missing 'created_at' for boundary '{bid}'"
                ),
                severity=FindingSeverity.INFO,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=bid,
            )
        )

    return findings


def _check_authority_records(
    plan_dir: Path,
    contract: Any,
) -> list[SemanticFinding]:
    """Check that authority records exist when required by the contract."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id

    if not contract.authority_required:
        return findings

    receipt_path = plan_dir / "boundary_receipts" / f"{bid}.json"
    if not receipt_path.is_file():
        # Receipt missing is reported by _check_boundary_receipt
        return findings

    try:
        raw = json.loads(receipt_path.read_text(encoding="utf-8"))
        authority_records = raw.get("authority_records")
        if not authority_records or (
            isinstance(authority_records, list) and len(authority_records) == 0
        ):
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-authority-missing",
                    boundary_id=bid,
                    description=(
                        f"authority_records are required but missing or "
                        f"empty in boundary receipt for '{bid}'"
                    ),
                    severity=FindingSeverity.ERROR,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                    contract_ref=bid,
                    evidence_ref=str(receipt_path),
                )
            )
    except (json.JSONDecodeError, OSError):
        # Already reported by _check_boundary_receipt
        pass

    return findings


# ── profile/template metadata compliance ───────────────────────────────


def _check_profile_template_metadata(
    contract: Any,
) -> list[SemanticFinding]:
    """Derive expectations from declared profile/template metadata.

    When a contract declares ``profile_kind`` or ``template_ref`` in its
    ``details`` mapping, this check validates the contract against the
    referenced profile and template.  It generates:

    * **profile-satisfaction** findings when a declared profile is not
      satisfied (missing required fields).
    * **template-compatibility** findings when a declared template ref
      is not structurally compatible with the contract.

    This is intentionally read-only — it never mutates contracts, state,
    or runtime registries.
    """
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id
    details = getattr(contract, "details", {}) or {}

    profile_kind = details.get("profile_kind")
    template_ref = details.get("template_ref")

    # ── profile satisfaction check ──────────────────────────────────
    if isinstance(profile_kind, str) and profile_kind:
        profile = get_profile_by_kind(profile_kind)
        if profile is None:
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-profile-kind-unknown",
                    boundary_id=bid,
                    description=(
                        f"contract '{bid}' declares profile_kind "
                        f"'{profile_kind}' which is not a registered profile"
                    ),
                    severity=FindingSeverity.ERROR,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                    contract_ref=bid,
                    details={"profile_kind": profile_kind},
                )
            )
        else:
            satisfied, missing_keys = contract_satisfies_profile(
                contract, profile
            )
            if not satisfied:
                findings.append(
                    SemanticFinding(
                        finding_id=f"SH-{bid}-profile-unsatisfied",
                        boundary_id=bid,
                        description=(
                            f"contract '{bid}' does not satisfy its declared "
                            f"profile '{profile_kind}': missing required "
                            f"fields {sorted(missing_keys)}"
                        ),
                        severity=FindingSeverity.ERROR,
                        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                        contract_ref=bid,
                        details={
                            "profile_kind": profile_kind,
                            "missing_fields": sorted(missing_keys),
                        },
                    )
                )

    # ── template compatibility check ────────────────────────────────
    if isinstance(template_ref, str) and template_ref:
        template = get_template_by_id(template_ref)
        if template is None:
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-template-ref-unknown",
                    boundary_id=bid,
                    description=(
                        f"contract '{bid}' declares template_ref "
                        f"'{template_ref}' which is not a registered "
                        f"typed boundary template"
                    ),
                    severity=FindingSeverity.ERROR,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                    contract_ref=bid,
                    details={"template_ref": template_ref},
                )
            )
        else:
            diff = diff_contracts(template, contract)
            if not diff.get("matching"):
                findings.append(
                    SemanticFinding(
                        finding_id=f"SH-{bid}-template-mismatch",
                        boundary_id=bid,
                        description=(
                            f"contract '{bid}' deviates from its declared "
                            f"template '{template_ref}': "
                            f"{len(diff.get('field_diffs', {}))} field diffs, "
                            f"{len(diff.get('detail_diffs', {}))} detail diffs"
                            f"{', plus artifact diffs' if diff.get('artifact_diffs') else ''}"
                        ),
                        severity=FindingSeverity.WARNING,
                        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                        contract_ref=bid,
                        details={
                            "template_ref": template_ref,
                            "field_diffs": {
                                k: list(v)
                                for k, v in diff.get("field_diffs", {}).items()
                            },
                            "detail_diffs": {
                                k: list(v)
                                for k, v in diff.get("detail_diffs", {}).items()
                            },
                            **(
                                {"artifact_diffs": diff["artifact_diffs"]}
                                if diff.get("artifact_diffs")
                                else {}
                            ),
                        },
                    )
                )

    return findings


def _check_override_authority(
    *,
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
) -> list[SemanticFinding]:
    """Validate override authority receipts only when their transition is active."""
    transition = contract.details.get("authority_transition")
    if not isinstance(transition, str) or not transition:
        return []

    bid = contract.boundary_id
    receipt = _load_receipt(plan_dir, bid)
    receipt_present = receipt is not None
    if not override_authority_transition_is_active(
        contract, state=state, receipt_present=receipt_present
    ):
        return []

    if receipt is None:
        return [
            SemanticFinding(
                finding_id=f"SH-{bid}-receipt-missing",
                boundary_id=bid,
                description=(
                    f"override authority transition '{transition}' is active but "
                    f"boundary receipt '{bid}' is missing"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=bid,
                evidence_ref=str(plan_dir / "boundary_receipts" / f"{bid}.json"),
            )
        ]

    authority_records = receipt.get("authority_records")
    if authority_records is None:
        return []
    if not isinstance(authority_records, list):
        return [
            SemanticFinding(
                finding_id=f"SH-{bid}-authority-records-invalid",
                boundary_id=bid,
                description=(
                    f"override authority receipt '{bid}' must store authority_records "
                    "as a list"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=bid,
                details={"actual_type": type(authority_records).__name__},
            )
        ]
    if not authority_records:
        return []

    findings: list[SemanticFinding] = []
    for index, record in enumerate(authority_records):
        if not isinstance(record, Mapping):
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-authority-record-{index}-invalid",
                    boundary_id=bid,
                    description=(
                        f"override authority receipt '{bid}' contains a non-mapping "
                        f"authority record at index {index}"
                    ),
                    severity=FindingSeverity.ERROR,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                    contract_ref=bid,
                )
            )
            continue
        issues = validate_override_authority_record(
            plan_dir=plan_dir,
            state=state,
            contract=contract,
            record=record,
        )
        for issue in issues:
            diagnostic_code = (
                DiagnosticCode.BOUNDARY_EVIDENCE_MISSING
                if issue.severity == "missing"
                else DiagnosticCode.BOUNDARY_EVIDENCE_STALE
            )
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-authority-{issue.code}-{index}",
                    boundary_id=bid,
                    description=issue.message,
                    severity=FindingSeverity.ERROR,
                    diagnostic_code=diagnostic_code,
                    contract_ref=bid,
                    details=dict(issue.details),
                )
            )
    return findings


# ── execute-phase read-only semantics (S4) ─────────────────────────────


def _check_execute_semantics(
    *,
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
) -> list[SemanticFinding]:
    """Read-only execute-phase boundary checks (S4).

    Observational only — never routes execution. Each finding fires only when
    its trigger evidence is present, so a plan that has not reached execute
    (or a clean execute plan) produces no spurious findings.
    """
    phase = contract.phase.value if contract.phase else None
    if phase != _EXECUTE_PHASE:
        return []
    bid = contract.boundary_id
    findings: list[SemanticFinding] = []

    if bid in _EXECUTE_CHECKPOINT_BOUNDARY_IDS:
        findings.extend(_check_execute_checkpoint(plan_dir, contract))
    if bid in _EXECUTE_APPROVAL_BOUNDARY_IDS:
        findings.extend(_check_execute_approval_authority(plan_dir, contract, state))
    if bid in _EXECUTE_AGGREGATE_BOUNDARY_IDS:
        findings.extend(_check_execute_aggregate_promotion(plan_dir, contract))
    if bid in _EXECUTE_TERMINAL_BOUNDARY_IDS:
        findings.extend(_check_execute_terminal_state(contract, state))

    return findings


def _load_receipt(plan_dir: Path, bid: str) -> dict[str, Any] | None:
    """Load a boundary receipt JSON, returning None when absent/unreadable."""
    receipt_path = plan_dir / "boundary_receipts" / f"{bid}.json"
    if not receipt_path.is_file():
        return None
    try:
        raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) else None


def _check_execute_checkpoint(
    plan_dir: Path,
    contract: Any,
) -> list[SemanticFinding]:
    """Stale-checkpoint and missing side-effect ref checks (read-only).

    A checkpoint-family receipt is stale when it records a ``batch_index`` for
    which no corresponding batch artifact exists on disk, or references a
    ``child_trace_path``/side-effect ref that is missing.
    """
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id
    receipt = _load_receipt(plan_dir, bid)
    if receipt is None:
        return findings

    from arnold_pipelines.megaplan._core import batch_artifact_index, list_batch_artifacts

    on_disk = {batch_artifact_index(p) for p in list_batch_artifacts(plan_dir)}
    on_disk.discard(None)

    recorded_index = receipt.get("batch_index")
    if isinstance(recorded_index, int) and on_disk and recorded_index not in on_disk:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-stale-checkpoint",
                boundary_id=bid,
                description=(
                    f"execute boundary '{bid}' records batch_index "
                    f"{recorded_index} but no batch artifact for that index "
                    f"exists on disk (found indices: {sorted(on_disk)})"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=bid,
                details={
                    "recorded_batch_index": recorded_index,
                    "on_disk_indices": sorted(i for i in on_disk if i is not None),
                },
            )
        )

    child_ref = receipt.get("child_trace_path")
    if isinstance(child_ref, str) and child_ref:
        if not (plan_dir / child_ref).exists():
            findings.append(
                SemanticFinding(
                    finding_id=f"SH-{bid}-missing-side-effect-ref",
                    boundary_id=bid,
                    description=(
                        f"execute boundary '{bid}' references side-effect "
                        f"ref '{child_ref}' which is missing from the plan dir"
                    ),
                    severity=FindingSeverity.WARNING,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                    contract_ref=bid,
                    details={"missing_side_effect_ref": child_ref},
                )
            )

    return findings


def _check_execute_approval_authority(
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
) -> list[SemanticFinding]:
    """Missing/stale approval authority vs ``state.meta.current_invocation_id``."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id
    receipt = _load_receipt(plan_dir, bid)
    if receipt is None:
        return findings

    meta = state.get("meta") if isinstance(state, dict) else None
    current_invocation = (
        meta.get("current_invocation_id") if isinstance(meta, dict) else None
    )
    receipt_invocation = receipt.get("invocation_id")

    if current_invocation and receipt_invocation and receipt_invocation != current_invocation:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-stale-approval-authority",
                boundary_id=bid,
                description=(
                    f"approval authority for '{bid}' records invocation_id "
                    f"'{receipt_invocation}' but state.meta.current_invocation_id "
                    f"is '{current_invocation}' (stale approval)"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=bid,
                details={
                    "receipt_invocation_id": receipt_invocation,
                    "current_invocation_id": current_invocation,
                },
            )
        )
    elif current_invocation and not receipt_invocation:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-missing-approval-authority",
                boundary_id=bid,
                description=(
                    f"approval receipt for '{bid}' is missing invocation_id "
                    f"authority while state.meta.current_invocation_id is set"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=bid,
                details={"current_invocation_id": current_invocation},
            )
        )

    return findings


def _check_execute_aggregate_promotion(
    plan_dir: Path,
    contract: Any,
) -> list[SemanticFinding]:
    """Child output without reducer promotion / promotion without child evidence."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id
    receipt = _load_receipt(plan_dir, bid)

    from arnold_pipelines.megaplan._core import list_batch_artifacts

    child_artifacts = list_batch_artifacts(plan_dir)
    has_child_evidence = bool(child_artifacts)
    promotion_present = bool(receipt and receipt.get("reducer_promotion"))

    if has_child_evidence and not promotion_present:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-child-output-without-promotion",
                boundary_id=bid,
                description=(
                    f"execute child batch outputs exist for '{bid}' but no "
                    f"reducer promotion receipt is present"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=bid,
                details={"child_batch_count": len(child_artifacts)},
            )
        )
    elif promotion_present and not has_child_evidence:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-promotion-without-child-evidence",
                boundary_id=bid,
                description=(
                    f"execute boundary '{bid}' records reducer promotion but "
                    f"no child batch artifacts exist to support it"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=bid,
                details={"child_batch_count": 0},
            )
        )

    return findings


def _check_execute_terminal_state(
    contract: Any,
    state: dict[str, Any] | None,
) -> list[SemanticFinding]:
    """Validate no-review terminal lands in an accepted execute terminal state."""
    findings: list[SemanticFinding] = []
    bid = contract.boundary_id
    if state is None:
        return findings
    actual_cs = state.get("current_state")
    if actual_cs is not None and actual_cs not in _EXECUTE_TERMINAL_STATES:
        findings.append(
            SemanticFinding(
                finding_id=f"SH-{bid}-terminal-state",
                boundary_id=bid,
                description=(
                    f"execute no-review terminal boundary '{bid}' expects "
                    f"current_state in {sorted(_EXECUTE_TERMINAL_STATES)} but "
                    f"got '{actual_cs}'"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=bid,
                details={
                    "accepted_terminal_states": sorted(_EXECUTE_TERMINAL_STATES),
                    "actual_current_state": actual_cs,
                },
            )
        )
    return findings


# ── review/finalize read-only semantics (S5) ───────────────────────────


def _check_review_finalize_semantics(
    *,
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> list[SemanticFinding]:
    bid = contract.boundary_id
    if bid == _REVIEW_CHILD_OUTPUTS_BOUNDARY_ID:
        return _check_review_child_outputs(plan_dir, contract, state, history)
    if bid == _REVIEW_REDUCER_PROMOTION_BOUNDARY_ID:
        return _check_review_reducer_promotion(plan_dir, contract, state, history)
    if bid == _REVIEW_REWORK_EFFECTS_BOUNDARY_ID:
        return _check_review_rework_effects(plan_dir, contract, state, history)
    if bid == _REVIEW_HUMAN_VERIFICATION_BOUNDARY_ID:
        return _check_review_human_verification(plan_dir, contract, state, history)
    if bid == _FINALIZE_ARTIFACTS_BOUNDARY_ID:
        return _check_finalize_artifacts(plan_dir, contract)
    if bid == _FINALIZE_FALLBACK_BOUNDARY_ID:
        return _check_finalize_fallback(plan_dir, contract, state)
    if bid == _FINAL_PROJECTION_BOUNDARY_ID:
        return _check_final_projection(plan_dir, contract, state, history)
    return []


@lru_cache(maxsize=1)
def _native_review_finalize_topology() -> dict[str, Any]:
    from arnold.workflow.source_compiler import lower_workflow_file
    from arnold_pipelines.megaplan.workflows import planning
    from arnold_pipelines.megaplan.workflows.components import (
        FINALIZE_POLICY,
        REVIEW_POLICY,
    )

    lowered = lower_workflow_file(planning.AUTHORING_SOURCE_PATH)
    route_signatures = frozenset(
        (route.source, route.label, route.target)
        for route in lowered.routes
        if route.label != "else"
    )
    review_surface = REVIEW_POLICY.metadata.get("route_surface")
    finalize_surface = FINALIZE_POLICY.metadata.get("route_surface")
    return {
        "route_signatures": route_signatures,
        "review_surface": review_surface if isinstance(review_surface, Mapping) else None,
        "finalize_surface": finalize_surface if isinstance(finalize_surface, Mapping) else None,
    }


def _review_surface_visible() -> bool:
    topology = _native_review_finalize_topology()
    review_surface = topology["review_surface"]
    if not isinstance(review_surface, Mapping):
        return False
    fan_in_contract = review_surface.get("fan_in_contract")
    rework_cycle = review_surface.get("rework_cycle")
    if not isinstance(fan_in_contract, Mapping) or not isinstance(rework_cycle, Mapping):
        return False
    if fan_in_contract.get("fan_in_ref") != "review-fan-in":
        return False
    if fan_in_contract.get("reducer_ref") != "SOURCE_REVIEW":
        return False
    if rework_cycle.get("target_ref") != "execute":
        return False
    return _NATIVE_REVIEW_ROUTE_SIGNATURES.issubset(topology["route_signatures"])


def _finalize_surface_visible() -> bool:
    topology = _native_review_finalize_topology()
    finalize_surface = topology["finalize_surface"]
    if not isinstance(finalize_surface, Mapping):
        return False
    fallback_routes = finalize_surface.get("fallback_routes")
    projection_routes = finalize_surface.get("final_projection_routes")
    if not isinstance(fallback_routes, Mapping) or not isinstance(projection_routes, Mapping):
        return False
    fallback = fallback_routes.get("plan_contract_revise_needed")
    revise_projection = projection_routes.get("revise_fallback")
    execute_projection = projection_routes.get("execute")
    if not isinstance(fallback, Mapping):
        return False
    if not isinstance(revise_projection, Mapping) or not isinstance(execute_projection, Mapping):
        return False
    return (
        fallback.get("route_signal") == "revise"
        and fallback.get("target_ref") == "revise"
        and revise_projection.get("route_signal") == "revise"
        and revise_projection.get("target_ref") == "revise"
        and execute_projection.get("target_ref") == "execute"
    )


def _load_plan_meta(plan_dir: Path, state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return None
    try:
        from arnold_pipelines.megaplan._core import latest_plan_meta_path, read_json

        meta_path = latest_plan_meta_path(plan_dir, state)
        loaded = read_json(meta_path)
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def _history_contains_step(history: list[dict[str, Any]], step: str) -> bool:
    return any(entry.get("step") == step for entry in history if isinstance(entry, dict))


def _review_or_finalize_evidence_present(
    *,
    plan_dir: Path,
    state: dict[str, Any] | None,
    history: list[dict[str, Any]],
    artifact_name: str,
    receipt_boundary_id: str,
    phase: str,
) -> bool:
    receipt = _load_receipt(plan_dir, receipt_boundary_id)
    if receipt is not None:
        return True
    if (plan_dir / artifact_name).exists():
        return True
    if isinstance(state, dict):
        if state.get("current_phase") == phase:
            return True
        current_state = state.get("current_state")
        if phase == "review" and current_state in _REVIEW_CURRENT_STATES:
            return True
        if phase == "finalize" and current_state in {"gated", "finalized", "done", "awaiting_human_verify"}:
            return True
    return _history_contains_step(history, phase)


def _child_receipt_refs(receipt: dict[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for ref in receipt.get("artifact_refs", ()):
        if isinstance(ref, str) and ref.startswith("review/"):
            refs.append(ref)
    details = receipt.get("details")
    if isinstance(details, Mapping):
        for key in _REVIEW_CHILD_TRACE_DETAIL_KEYS:
            value = details.get(key)
            if isinstance(value, (list, tuple)):
                refs.extend(str(item) for item in value if isinstance(item, str) and item)
        child_count = details.get("child_count")
        if isinstance(child_count, int) and child_count > 0 and not refs:
            refs.append(f"child_count:{child_count}")
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return tuple(deduped)


def _receipt_state_value(receipt: dict[str, Any], key: str) -> Any:
    state_observation = receipt.get("state_observation")
    if isinstance(state_observation, Mapping):
        return state_observation.get(key)
    return None


def _check_review_child_outputs(
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> list[SemanticFinding]:
    findings: list[SemanticFinding] = []
    if not _review_or_finalize_evidence_present(
        plan_dir=plan_dir,
        state=state,
        history=history,
        artifact_name="review.json",
        receipt_boundary_id=contract.boundary_id,
        phase="review",
    ):
        return findings
    receipt = _load_receipt(plan_dir, contract.boundary_id)
    if receipt is None:
        return findings
    child_refs = _child_receipt_refs(receipt)
    if not child_refs:
        findings.append(
            SemanticFinding(
                finding_id="SH-review_child_outputs-missing-child-receipts",
                boundary_id=contract.boundary_id,
                description=(
                    "review child outputs boundary recorded completion without "
                    "any visible child receipt or child trace refs"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=contract.boundary_id,
                evidence_ref=str(plan_dir / "boundary_receipts" / f"{contract.boundary_id}.json"),
            )
        )
    if not _review_surface_visible():
        findings.append(
            SemanticFinding(
                finding_id="SH-review_child_outputs-native-reducer-route-missing",
                boundary_id=contract.boundary_id,
                description=(
                    "review child outputs cannot be treated as complete because "
                    "the native review fan-in/rework topology is not visibly declared"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
                contract_ref=contract.boundary_id,
                details={"required_routes": sorted(_NATIVE_REVIEW_ROUTE_SIGNATURES)},
            )
        )
    return findings


def _check_review_reducer_promotion(
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> list[SemanticFinding]:
    findings: list[SemanticFinding] = []
    child_receipt = _load_receipt(plan_dir, _REVIEW_CHILD_OUTPUTS_BOUNDARY_ID)
    child_refs = _child_receipt_refs(child_receipt) if child_receipt is not None else ()
    if child_refs and _load_receipt(plan_dir, contract.boundary_id) is None:
        findings.append(
            SemanticFinding(
                finding_id="SH-review_reducer_promotion-missing-reducer-receipt",
                boundary_id=contract.boundary_id,
                description=(
                    "review child receipts are present but no reducer promotion "
                    "receipt records the native review fan-in result"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=contract.boundary_id,
                details={"child_receipt_refs": list(child_refs)},
            )
        )
    if _review_or_finalize_evidence_present(
        plan_dir=plan_dir,
        state=state,
        history=history,
        artifact_name="review.json",
        receipt_boundary_id=contract.boundary_id,
        phase="review",
    ) and _load_receipt(plan_dir, contract.boundary_id) is not None and not _review_surface_visible():
        findings.append(
            SemanticFinding(
                finding_id="SH-review_reducer_promotion-native-reducer-route-missing",
                boundary_id=contract.boundary_id,
                description=(
                    "review reducer promotion receipt cannot prove completion "
                    "without a visible native review fan-in and rework route"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
                contract_ref=contract.boundary_id,
            )
        )
    return findings


def _check_review_rework_effects(
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> list[SemanticFinding]:
    if not _review_or_finalize_evidence_present(
        plan_dir=plan_dir,
        state=state,
        history=history,
        artifact_name="review.json",
        receipt_boundary_id=contract.boundary_id,
        phase="review",
    ):
        return []
    if _load_receipt(plan_dir, contract.boundary_id) is None or _review_surface_visible():
        return []
    return [
        SemanticFinding(
            finding_id="SH-review_rework_effects-native-rework-route-missing",
            boundary_id=contract.boundary_id,
            description=(
                "review rework effects receipt cannot be considered complete "
                "without the visible native execute/review rework cycle"
            ),
            severity=FindingSeverity.ERROR,
            diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
            contract_ref=contract.boundary_id,
        )
    ]


def _check_review_human_verification(
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> list[SemanticFinding]:
    findings: list[SemanticFinding] = []
    if not _review_or_finalize_evidence_present(
        plan_dir=plan_dir,
        state=state,
        history=history,
        artifact_name="review.json",
        receipt_boundary_id=contract.boundary_id,
        phase="review",
    ):
        return findings
    current_state = state.get("current_state") if isinstance(state, dict) else None
    receipt = _load_receipt(plan_dir, contract.boundary_id)
    if receipt is None and current_state != "awaiting_human_verify":
        return findings
    verifications_path = plan_dir / "human_verifications.json"
    if not verifications_path.is_file():
        findings.append(
            SemanticFinding(
                finding_id="SH-review_human_verification-human-authority-missing",
                boundary_id=contract.boundary_id,
                description=(
                    "review human-verification boundary lacks human_verifications.json "
                    "authority evidence"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=contract.boundary_id,
                evidence_ref=str(verifications_path),
            )
        )
        return findings
    plan_meta = _load_plan_meta(plan_dir, state)
    if plan_meta is None:
        return findings
    try:
        from arnold_pipelines.megaplan.handlers.verifiability import (
            get_human_verification_status,
        )

        hv_status = get_human_verification_status(plan_dir, plan_meta)
    except Exception:
        return findings
    if hv_status.get("semantics") != "latest_verdict":
        findings.append(
            SemanticFinding(
                finding_id="SH-review_human_verification-human-authority-stale",
                boundary_id=contract.boundary_id,
                description=(
                    "review human-verification evidence is present but does not "
                    "declare latest_verdict semantics"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=contract.boundary_id,
                details={"semantics": hv_status.get("semantics")},
            )
        )
    return findings


def _check_finalize_artifacts(
    plan_dir: Path,
    contract: Any,
) -> list[SemanticFinding]:
    findings: list[SemanticFinding] = []
    receipt = _load_receipt(plan_dir, contract.boundary_id)
    if receipt is None:
        return findings
    finalize_json = plan_dir / "finalize.json"
    if not finalize_json.is_file():
        return findings
    details = receipt.get("details")
    recorded_hash = details.get("artifact_hash") if isinstance(details, Mapping) else None
    if isinstance(recorded_hash, str) and recorded_hash:
        try:
            from arnold_pipelines.megaplan._core import sha256_file

            current_hash = sha256_file(finalize_json)
        except Exception:
            current_hash = None
        if current_hash and current_hash != recorded_hash:
            findings.append(
                SemanticFinding(
                    finding_id="SH-finalize_artifacts-stale-artifact-hash",
                    boundary_id=contract.boundary_id,
                    description=(
                        "finalize artifacts receipt hash does not match the current "
                        "finalize.json payload"
                    ),
                    severity=FindingSeverity.WARNING,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                    contract_ref=contract.boundary_id,
                    evidence_ref=str(finalize_json),
                    details={
                        "recorded_hash": recorded_hash,
                        "current_hash": current_hash,
                    },
                )
            )
    artifact_refs = receipt.get("artifact_refs")
    if isinstance(artifact_refs, list):
        missing_refs = [
            ref for ref in contract.required_artifacts if ref not in artifact_refs
        ]
        if missing_refs:
            findings.append(
                SemanticFinding(
                    finding_id="SH-finalize_artifacts-stale-artifact-refs",
                    boundary_id=contract.boundary_id,
                    description=(
                        "finalize artifacts receipt is missing one or more canonical "
                        "artifact refs"
                    ),
                    severity=FindingSeverity.WARNING,
                    diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                    contract_ref=contract.boundary_id,
                    details={"missing_artifact_refs": missing_refs},
                )
            )
    return findings


def _final_projection_implies_revise_fallback(
    plan_dir: Path,
    state: dict[str, Any] | None,
) -> bool:
    receipt = _load_receipt(plan_dir, _FINAL_PROJECTION_BOUNDARY_ID)
    if receipt is not None:
        if _receipt_state_value(receipt, "next_step") == "revise":
            return True
        if _receipt_state_value(receipt, "current_state") == "critiqued":
            return True
    if isinstance(state, dict) and state.get("current_state") == "critiqued":
        return True
    return False


def _check_finalize_fallback(
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
) -> list[SemanticFinding]:
    findings: list[SemanticFinding] = []
    fallback_receipt = _load_receipt(plan_dir, contract.boundary_id)
    fallback_artifact = plan_dir / "finalize_revise_feedback.json"
    fallback_needed = fallback_artifact.exists() or _final_projection_implies_revise_fallback(plan_dir, state)
    if fallback_needed and fallback_receipt is None:
        findings.append(
            SemanticFinding(
                finding_id="SH-finalize_fallback-missing-fallback-receipt",
                boundary_id=contract.boundary_id,
                description=(
                    "finalize revise-fallback evidence exists but no finalize "
                    "fallback receipt was recorded"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
                contract_ref=contract.boundary_id,
            )
        )
    if fallback_receipt is not None and not _finalize_surface_visible():
        findings.append(
            SemanticFinding(
                finding_id="SH-finalize_fallback-native-fallback-route-missing",
                boundary_id=contract.boundary_id,
                description=(
                    "finalize fallback receipt cannot prove completion without a "
                    "visible native fallback route and projection surface"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
                contract_ref=contract.boundary_id,
            )
        )
    return findings


def _expected_final_projection_cases() -> tuple[dict[str, Any], ...]:
    from arnold_pipelines.megaplan._core.topology import STAGE_TO_STATE

    finalize_surface = _native_review_finalize_topology()["finalize_surface"]
    if not isinstance(finalize_surface, Mapping):
        return ()
    projection_routes = finalize_surface.get("final_projection_routes")
    if not isinstance(projection_routes, Mapping):
        return ()
    cases: list[dict[str, Any]] = []
    for case_name, route in projection_routes.items():
        if not isinstance(route, Mapping):
            continue
        state_value = route.get("terminal_state")
        if not isinstance(state_value, str) or not state_value:
            projected_phase = route.get("projected_phase")
            if isinstance(projected_phase, str):
                state_value = STAGE_TO_STATE.get(projected_phase)
        if not isinstance(state_value, str) or not state_value:
            continue
        cases.append(
            {
                "case_name": case_name,
                "state": state_value,
                "next_step": route.get("target_ref"),
                "route_signal": route.get("route_signal"),
            }
        )
    return tuple(cases)


def _check_final_projection(
    plan_dir: Path,
    contract: Any,
    state: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> list[SemanticFinding]:
    findings: list[SemanticFinding] = []
    if not _review_or_finalize_evidence_present(
        plan_dir=plan_dir,
        state=state,
        history=history,
        artifact_name="finalize.json",
        receipt_boundary_id=contract.boundary_id,
        phase="finalize",
    ):
        return findings
    receipt = _load_receipt(plan_dir, contract.boundary_id)
    if receipt is None:
        return findings
    if not _finalize_surface_visible():
        findings.append(
            SemanticFinding(
                finding_id="SH-final_projection-native-fallback-route-missing",
                boundary_id=contract.boundary_id,
                description=(
                    "final projection receipt cannot prove completion without the "
                    "visible finalize fallback/projection route surface"
                ),
                severity=FindingSeverity.ERROR,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
                contract_ref=contract.boundary_id,
            )
        )
    current_state = state.get("current_state") if isinstance(state, dict) else None
    observed_state = _receipt_state_value(receipt, "current_state")
    if isinstance(current_state, str) and isinstance(observed_state, str) and current_state != observed_state:
        findings.append(
            SemanticFinding(
                finding_id="SH-final_projection-state-history-drift",
                boundary_id=contract.boundary_id,
                description=(
                    "final projection receipt state observation no longer matches "
                    "state.json"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=contract.boundary_id,
                details={
                    "receipt_current_state": observed_state,
                    "state_json_current_state": current_state,
                },
            )
        )
        return findings
    observed_next_step = _receipt_state_value(receipt, "next_step")
    valid_cases = _expected_final_projection_cases()
    if valid_cases and not any(
        case["state"] == current_state and case["next_step"] == observed_next_step
        for case in valid_cases
    ):
        findings.append(
            SemanticFinding(
                finding_id="SH-final_projection-state-history-drift",
                boundary_id=contract.boundary_id,
                description=(
                    "final projection state/next_step do not match any visible "
                    "finalize projection case"
                ),
                severity=FindingSeverity.WARNING,
                diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
                contract_ref=contract.boundary_id,
                details={
                    "current_state": current_state,
                    "observed_next_step": observed_next_step,
                    "expected_cases": [
                        {
                            "case_name": case["case_name"],
                            "state": case["state"],
                            "next_step": case["next_step"],
                        }
                        for case in valid_cases
                    ],
                },
            )
        )
    return findings


# ── plan-dir loading helpers ───────────────────────────────────────────


def _load_state_json(plan_dir: Path) -> dict[str, Any] | None:
    """Load state.json from *plan_dir*, returning None on any failure."""
    state_path = plan_dir / "state.json"
    if not state_path.is_file():
        return None
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
        return None
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to load state.json from %s: %s", plan_dir, exc)
        return None


def _load_history(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract the history list from loaded state."""
    if state is None:
        return []
    history = state.get("history")
    if isinstance(history, list):
        return [h for h in history if isinstance(h, dict)]
    return []


def _load_phase_result(plan_dir: Path) -> dict[str, Any] | None:
    """Load phase_result.json from *plan_dir*, returning None on any failure."""
    pr_path = plan_dir / "phase_result.json"
    if not pr_path.is_file():
        return None
    try:
        raw = json.loads(pr_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
        return None
    except (json.JSONDecodeError, OSError) as exc:
        log.warning(
            "Failed to load phase_result.json from %s: %s", plan_dir, exc
        )
        return None


__all__ = [
    "inspect_semantic_health",
]
