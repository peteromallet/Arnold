"""Read-only semantic health inspection for S2 front-half boundaries.

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
from arnold_pipelines.megaplan.workflows.boundary_contracts import (
    BOUNDARY_CONTRACTS,
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

    # --- execute-phase read-only semantics (S4) ---
    findings.extend(_check_execute_semantics(plan_dir=plan_dir, contract=contract, state=state))

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
