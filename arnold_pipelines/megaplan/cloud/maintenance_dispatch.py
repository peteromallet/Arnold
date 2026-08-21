"""Strict dispatch-receipt adapter for model-backed maintenance actions.

Maintenance actions that launch a model-backed subprocess must prove, at the
receipt level, that the runtime that actually executed is the sanctioned
maintenance model (``gpt-5.6-sol``).  This module wraps the generic dispatch
writer rather than tightening it: non-maintenance dispatch keeps using the
generic ``arnold_pipelines.megaplan.receipts.writer`` API unchanged, while
maintenance call sites use this stricter adapter.

Rules enforced here:

* the resolved runtime model is recorded at the subprocess-start transition,
  the moment launch returns and the model identity is known;
* a maintenance action may only finalize as ``succeeded`` when
  ``resolved_runtime_model == gpt-5.6-sol`` — anything else (missing, stale,
  configured-only, or a conflicting pin) is rejected before the generic writer
  can certify success.

The required-model contract lives in the adapter, not in the generic writer,
so receipts for non-maintenance dispatch stay reusable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, TypeVar

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator, model_validator

from arnold_pipelines.megaplan.receipts import schema, writer

#: The only runtime model that may certify a successful maintenance action.
MAINTENANCE_REQUIRED_RUNTIME_MODEL = "gpt-5.6-sol"

_ProcessT = TypeVar("_ProcessT")
class ReceiptKind(str, Enum):
    """Closed maintenance receipt discriminators."""

    REPORT = "report"
    EFFECT = "effect"
    UNKNOWN = "unknown"


class ReceiptStatus(str, Enum):
    """Known lifecycle states; unknown states remain indeterminate."""

    INITIALIZED = "initialized"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    INDETERMINATE = "indeterminate"
    UNKNOWN = "unknown"


class ReceiptIdentity(BaseModel):
    """Immutable canonical coordinates shared by receipt kinds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence_id: StrictStr | None = None
    request_id: StrictStr | None = None
    request_digest: StrictStr | None = None
    immutable_evidence_id: StrictStr | None = None
    immutable_evidence_digest: StrictStr | None = None
    effect_id: StrictStr | None = None
    effect_digest: StrictStr | None = None
    effect_class: StrictStr | None = None

    @field_validator(
        "occurrence_id",
        "request_id",
        "request_digest",
        "immutable_evidence_id",
        "immutable_evidence_digest",
        "effect_id",
        "effect_digest",
        "effect_class",
    )
    @classmethod
    def _nonempty_when_present(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("receipt identity coordinates must be non-empty")
        return value


class ReportReceipt(BaseModel):
    """Diagnostic receipt; it never certifies or carries an effect."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["report"] = "report"
    status: ReceiptStatus
    identity: ReceiptIdentity
    report_id: StrictStr
    detail: StrictStr | None = None
    returncode: int | None = None

    @field_validator("report_id")
    @classmethod
    def _report_id_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("report_id must be non-empty")
        return value

    @model_validator(mode="after")
    def _reject_effect_coordinates(self) -> ReportReceipt:
        if any(
            getattr(self.identity, field) is not None
            for field in ("effect_id", "effect_digest", "effect_class")
        ):
            raise ValueError("report receipts cannot carry effect coordinates")
        return self


class EffectReceipt(BaseModel):
    """Effect lifecycle receipt with all immutable adoption coordinates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["effect"] = "effect"
    status: ReceiptStatus
    identity: ReceiptIdentity
    effect_id: StrictStr
    effect_digest: StrictStr
    effect_class: StrictStr
    receipt_id: StrictStr

    @field_validator(
        "effect_id",
        "effect_digest",
        "effect_class",
        "receipt_id",
    )
    @classmethod
    def _effect_fields_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("effect receipt coordinates must be non-empty")
        return value

    @model_validator(mode="after")
    def _identity_is_exact(self) -> EffectReceipt:
        if (
            self.identity.effect_id != self.effect_id
            or self.identity.effect_digest != self.effect_digest
            or self.identity.effect_class != self.effect_class
        ):
            raise ValueError("effect receipt identity coordinates disagree")
        for field in (
            "occurrence_id",
            "request_id",
            "request_digest",
            "immutable_evidence_id",
            "immutable_evidence_digest",
        ):
            if getattr(self.identity, field) is None:
                raise ValueError(f"effect receipt requires {field}")
        return self


class UnknownReceipt(BaseModel):
    """Typed representation of an unknown kind/status; never adoptable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: StrictStr
    status: StrictStr
    reason: StrictStr


MaintenanceReceipt = ReportReceipt | EffectReceipt


class ReceiptAdoptionState(str, Enum):
    """Fail-closed result states for typed receipt reconciliation."""

    REPORT_ONLY = "report_only"
    ADOPTED = "adopted"
    INDETERMINATE = "indeterminate"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ReceiptAdoption:
    """Side-effect-free result of exact receipt identity reconciliation."""

    state: ReceiptAdoptionState
    reasons: tuple[str, ...] = ()
    prior_terminal: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "reasons": list(self.reasons),
            "prior_terminal": (
                dict(self.prior_terminal) if self.prior_terminal is not None else None
            ),
        }


def parse_maintenance_receipt(value: object) -> MaintenanceReceipt | UnknownReceipt:
    """Decode one receipt without coercing report and effect kinds."""
    if not isinstance(value, Mapping):
        return UnknownReceipt(
            kind=type(value).__name__,
            status="unknown",
            reason="receipt is not a mapping",
        )


    kind = str(value.get("kind") or "")
    status = str(value.get("status") or "")
    if kind not in {ReceiptKind.REPORT.value, ReceiptKind.EFFECT.value}:
        return UnknownReceipt(
            kind=kind or "unknown",
            status=status or "unknown",
            reason="unknown receipt kind",
        )
    try:
        if kind == ReceiptKind.REPORT.value:
            return ReportReceipt.model_validate(value)
        return EffectReceipt.model_validate(value)
    except (TypeError, ValueError) as exc:
        return UnknownReceipt(
            kind=kind,
            status=status or "unknown",
            reason=f"invalid {kind} receipt: {exc}",
        )
def initialize_maintenance_dispatch_receipt(
    plan_dir: Path,
    receipt: schema.AutomaticDispatchReceipt,
) -> schema.AutomaticDispatchReceipt:
    """Centralized durable initialization for maintenance dispatch."""
    return writer.initialize_dispatch_receipt(Path(plan_dir), receipt)


def route_allowlisted_effect(*args: Any, **kwargs: Any) -> Any:
    """Route effects only through the canonical recovery allowlist seam."""
    from arnold_pipelines.megaplan.cloud.maintenance_recovery import (
        route_allowlisted_effect as _route_allowlisted_effect,
    )

    return _route_allowlisted_effect(*args, **kwargs)


def _identity_mismatches(
    actual: ReceiptIdentity,
    expected: ReceiptIdentity,
    *,
    require_effect: bool,
) -> tuple[str, ...]:
    mismatches: list[str] = []
    for field in (
        "occurrence_id",
        "request_id",
        "request_digest",
        "immutable_evidence_id",
        "immutable_evidence_digest",
    ):
        if getattr(actual, field) != getattr(expected, field):
            mismatches.append(f"{field}_mismatch")
    if require_effect:
        for field in ("effect_id", "effect_digest", "effect_class"):
            actual_value = getattr(actual, field)
            expected_value = getattr(expected, field)
            if actual_value is None or expected_value is None:
                mismatches.append(f"{field}_missing")
            elif actual_value != expected_value:
                mismatches.append(f"{field}_mismatch")
    return tuple(mismatches)


def reconcile_typed_maintenance_receipt(
    receipt: MaintenanceReceipt | UnknownReceipt | None,
    *,
    expected: ReceiptIdentity,
    prior_terminal: Mapping[str, Any] | None = None,
) -> ReceiptAdoption:
    """Reconcile report/effect receipts using exact canonical identities.

    This function never appends, launches, routes, or writes state.  A report
    receipt can only produce ``report_only``; an effect receipt is adoptable
    only when all four immutable identity groups and the effect class match.
    """
    if receipt is None:
        return ReceiptAdoption(
            ReceiptAdoptionState.INDETERMINATE,
            ("missing_receipt",),
        )
    if isinstance(receipt, UnknownReceipt):
        return ReceiptAdoption(
            ReceiptAdoptionState.INDETERMINATE,
            ("unknown_receipt_kind_or_status",),
        )
    if receipt.status in {ReceiptStatus.UNKNOWN, ReceiptStatus.INDETERMINATE}:
        return ReceiptAdoption(
            ReceiptAdoptionState.INDETERMINATE,
            ("unknown_or_indeterminate_status",),
        )
    if isinstance(receipt, ReportReceipt):
        if any(
            getattr(expected, field) is not None
            for field in ("effect_id", "effect_digest", "effect_class")
        ):
            return ReceiptAdoption(
                ReceiptAdoptionState.REJECTED,
                ("cross_kind_receipt",),
            )
        mismatches = _identity_mismatches(
            receipt.identity, expected, require_effect=False
        )
        if mismatches:
            return ReceiptAdoption(ReceiptAdoptionState.REJECTED, mismatches)
        return ReceiptAdoption(ReceiptAdoptionState.REPORT_ONLY)
    mismatches = _identity_mismatches(
        receipt.identity, expected, require_effect=True
    )
    if mismatches:
        return ReceiptAdoption(ReceiptAdoptionState.REJECTED, mismatches)
    if receipt.status not in {
        ReceiptStatus.SUCCEEDED,
        ReceiptStatus.FAILED,
        ReceiptStatus.BLOCKED,
    }:
        return ReceiptAdoption(
            ReceiptAdoptionState.INDETERMINATE,
            ("effect_not_terminal",),
        )
    return ReceiptAdoption(ReceiptAdoptionState.ADOPTED, prior_terminal=prior_terminal)

def failed_session_receipt_allows_rearm(
    receipt: ReportReceipt | EffectReceipt | UnknownReceipt | None,
    *,
    expected: ReceiptIdentity,
) -> bool:
    """Consume, but do not validate, T2.4's failed-session receipt.

    Only the failed status and exact occurrence/evidence identity are used.
    Return-code/status honesty remains solely owned by T2.4.
    """
    if receipt is None or isinstance(receipt, UnknownReceipt):
        return False
    if receipt.status is not ReceiptStatus.FAILED:
        return False
    result = reconcile_typed_maintenance_receipt(receipt, expected=expected)
    return result.state in {
        ReceiptAdoptionState.REPORT_ONLY,
        ReceiptAdoptionState.ADOPTED,
    }


def reconcile_effect_receipt(
    receipt: EffectReceipt | ReportReceipt | UnknownReceipt | None,
    *,
    expected: ReceiptIdentity,
    ledger: Any | None = None,
    prior_terminal: Mapping[str, Any] | None = None,
) -> ReceiptAdoption:
    """Adopt one exact effect receipt without appending or redriving.

    The optional lookup is the existing canonical ledger seam.  It is
    intentionally read-only; this adapter never creates a receipt ledger or
    writes a terminal projection.
    """
    if ledger is not None and prior_terminal is None:
        lookup = getattr(ledger, "lookup_maintenance_event", None)
        if not callable(lookup):
            return ReceiptAdoption(
                ReceiptAdoptionState.INDETERMINATE,
                ("canonical_ledger_lookup_unavailable",),
            )
        try:
            prior_terminal = (
                lookup(receipt.receipt_id)
                if isinstance(receipt, EffectReceipt)
                else None
            )
        except Exception:
            return ReceiptAdoption(
                ReceiptAdoptionState.INDETERMINATE,
                ("canonical_ledger_lookup_failed",),
            )
        if prior_terminal is None:
            return ReceiptAdoption(
                ReceiptAdoptionState.INDETERMINATE,
                ("effect_not_in_canonical_ledger",),
            )
    return reconcile_typed_maintenance_receipt(
        receipt,
        expected=expected,
        prior_terminal=prior_terminal,
    )


adopt_effect_receipt = reconcile_effect_receipt


# Adapter-specific names are intentionally local to this module.  They make
# the discriminated boundary explicit without changing the canonical receipt
# package or its exports.
MaintenanceReportReceipt = ReportReceipt
MaintenanceEffectReceipt = EffectReceipt
ReceiptIdentityMismatch = ReceiptAdoption


class MaintenanceModelEnforcementError(RuntimeError):
    """A maintenance action's resolved runtime model cannot certify success.

    Carries the truthful in-memory receipt state so callers can surface the
    rejection without inventing a runtime model identity.
    """

    def __init__(
        self,
        message: str,
        *,
        receipt: schema.AutomaticDispatchReceipt,
    ) -> None:
        super().__init__(message)
        self.receipt = receipt


def _required_model(receipt: schema.AutomaticDispatchReceipt) -> str:
    required = receipt.get("required_runtime_model")
    return required or MAINTENANCE_REQUIRED_RUNTIME_MODEL


def prepare_maintenance_dispatch_receipt(
    *,
    action: str,
    configured_model: str | None = None,
    dispatch_id: str | None = None,
    created_at_utc: str | None = None,
) -> schema.AutomaticDispatchReceipt:
    """Prepare a dispatch receipt for a model-backed maintenance action.

    Reuses :func:`writer.prepare_dispatch_receipt` and then marks the receipt
    as maintenance-bound with the required runtime model.  No I/O is performed.
    """
    receipt = writer.prepare_dispatch_receipt(
        action=action,
        configured_model=configured_model,
        dispatch_id=dispatch_id,
        created_at_utc=created_at_utc,
    )
    receipt["maintenance"] = True
    receipt["required_runtime_model"] = MAINTENANCE_REQUIRED_RUNTIME_MODEL
    return receipt


def record_maintenance_started(
    plan_dir: Path,
    receipt: schema.AutomaticDispatchReceipt,
    *,
    resolved_runtime_model: str | None = None,
) -> schema.AutomaticDispatchReceipt:
    """Record subprocess start and the resolved runtime model as soon as known.

    This is the subprocess-start transition: the resolved model is written
    durably alongside ``subprocess_started=True`` so later finalization can be
    checked against it.
    """
    return writer.record_dispatch_started(
        plan_dir,
        receipt,
        resolved_runtime_model=resolved_runtime_model,
    )


def finalize_maintenance_dispatch_receipt(
    plan_dir: Path,
    receipt: schema.AutomaticDispatchReceipt,
    *,
    outcome: schema.DispatchOutcome,
    resolved_runtime_model: str | None = None,
    mutation_facts: Mapping[str, bool | None] | None = None,
    detail: str | None = None,
) -> schema.AutomaticDispatchReceipt:
    """Finalize a maintenance dispatch, rejecting success without ``gpt-5.6-sol``.

    A ``succeeded`` outcome is rejected unless the resolved runtime model
    equals :data:`MAINTENANCE_REQUIRED_RUNTIME_MODEL`.  The generic writer is
    then delegated to for the durable transition.
    """
    if outcome == "succeeded":
        effective_model = (
            resolved_runtime_model
            if resolved_runtime_model is not None
            else receipt.get("resolved_runtime_model")
        )
        if effective_model != _required_model(receipt):
            raise MaintenanceModelEnforcementError(
                "maintenance success requires resolved_runtime_model == "
                f"{_required_model(receipt)!r}, got {effective_model!r}",
                receipt=receipt,
            )
    return writer.finalize_dispatch_receipt(
        plan_dir,
        receipt,
        outcome=outcome,
        resolved_runtime_model=resolved_runtime_model,
        mutation_facts=mutation_facts,
        detail=detail,
    )


def initialize_and_launch_maintenance_dispatch(
    plan_dir: Path,
    receipt: schema.AutomaticDispatchReceipt,
    launch: Callable[[], _ProcessT],
    *,
    resolved_runtime_model: str | None = None,
) -> tuple[schema.AutomaticDispatchReceipt, _ProcessT]:
    """Initialize durably, launch once, then record start plus the resolved model.

    Mirrors :func:`writer.initialize_and_launch_dispatch` while recording the
    resolved runtime model at the subprocess-start transition, the moment it is
    known to the caller.
    """
    initialized = initialize_maintenance_dispatch_receipt(Path(plan_dir), receipt)
    try:
        process = launch()
    except Exception as exc:
        writer.finalize_dispatch_receipt(
            Path(plan_dir),
            initialized,
            outcome="blocked",
            detail=f"subprocess launch failed: {exc}",
        )
        raise
    started = record_maintenance_started(
        Path(plan_dir),
        initialized,
        resolved_runtime_model=resolved_runtime_model,
    )
    return started, process


# ──────────────────────────────────────────────────────────────────────────────
class DispatchReceiptState(str, Enum):
    """Closed states for the generic subprocess dispatch receipt."""

    REQUESTED = "requested"
    STARTED = "started"
    TERMINAL = "terminal"
    INDETERMINATE = "indeterminate"
    ADOPTED = "adopted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ReceiptReconciliation:
    """Typed fail-closed reconciliation of a subprocess dispatch."""

    state: DispatchReceiptState
    reasons: tuple[str, ...] = ()
    outcome: str | None = None
    subprocess_started: bool = False
    progress_proven: bool = False
    request_receipt_ref: str | None = None
    effect_receipt_ref: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "reasons": list(self.reasons),
            "outcome": self.outcome,
            "subprocess_started": self.subprocess_started,
            "progress_proven": self.progress_proven,
            "request_receipt_ref": self.request_receipt_ref,
            "effect_receipt_ref": self.effect_receipt_ref,
        }


def _receipt_ref_text(receipt: Mapping[str, Any] | None) -> str | None:
    if not isinstance(receipt, Mapping):
        return None
    for key in ("request_ref", "effect_ref", "receipt_ref", "locator", "request_id"):
        value = receipt.get(key)
        if value:
            return str(value)
    return None


def _effect_receipt_adopted(effect_receipt: Mapping[str, Any] | None) -> bool:
    if not isinstance(effect_receipt, Mapping):
        return False
    return bool(
        effect_receipt.get("reservation_id") or effect_receipt.get("effect_outcome")
    )


def _request_receipt_rejected(request_receipt: Mapping[str, Any] | None) -> bool:
    if not isinstance(request_receipt, Mapping):
        return False
    values = {
        str(request_receipt.get(key) or "").strip().lower()
        for key in ("decision", "outcome", "status")
    }
    return bool(values & {"rejected", "blocked"})


def _request_receipt_accepted(request_receipt: Mapping[str, Any] | None) -> bool:
    if not isinstance(request_receipt, Mapping):
        return False
    values = {
        str(request_receipt.get(key) or "").strip().lower()
        for key in ("decision", "outcome", "status")
    }
    return bool(values & {"accepted", "joined"})


def reconcile_automatic_dispatch_receipt(
    receipt: schema.AutomaticDispatchReceipt | None,
    *,
    request_receipt: Mapping[str, Any] | None = None,
    effect_receipt: Mapping[str, Any] | None = None,
    sidecar_present: bool = False,
    process_present: bool | None = None,
    local_success: bool = False,
    terminal_status_label: str | None = None,
    later_progress_evidence: bool = False,
    required_runtime_model: str | None = None,
    expected_fence: str | None = None,
) -> ReceiptReconciliation:
    """Reconcile the generic subprocess receipt without inferring completion."""
    reasons: list[str] = []
    for side in (request_receipt, effect_receipt):
        if (
            expected_fence is not None
            and isinstance(side, Mapping)
            and (side.get("fencing_token") or side.get("fence")) is not None
            and str(side.get("fencing_token") or side.get("fence"))
            != str(expected_fence)
        ):
            reasons.append("stale_fence")
    outcome = str(receipt.get("outcome") or "") if receipt else ""
    started = bool(receipt.get("subprocess_started")) if receipt else False
    request_ref = _receipt_ref_text(request_receipt)
    effect_ref = _receipt_ref_text(effect_receipt)
    if _effect_receipt_adopted(effect_receipt) and outcome not in {
        "succeeded",
        "failed",
        "blocked",
    }:
        return ReceiptReconciliation(
            DispatchReceiptState.ADOPTED,
            tuple(dict.fromkeys([*reasons, "effect_receipt_adopted"])),
            outcome or None,
            started,
            later_progress_evidence,
            request_ref,
            effect_ref,
        )
    if receipt is None or not receipt:
        if _request_receipt_rejected(request_receipt):
            return ReceiptReconciliation(
                DispatchReceiptState.REJECTED,
                tuple(dict.fromkeys([*reasons, "request_receipt_rejected"])),
                request_receipt_ref=request_ref,
                effect_receipt_ref=effect_ref,
            )
        if _request_receipt_accepted(request_receipt):
            return ReceiptReconciliation(
                DispatchReceiptState.REQUESTED,
                tuple(dict.fromkeys([*reasons, "requested_without_dispatch_receipt"])),
                request_receipt_ref=request_ref,
                effect_receipt_ref=effect_ref,
            )
        return ReceiptReconciliation(
            DispatchReceiptState.INDETERMINATE,
            tuple(dict.fromkeys([*reasons, "missing_receipt"])),
            request_receipt_ref=request_ref,
            effect_receipt_ref=effect_ref,
        )
    common = dict(
        subprocess_started=started,
        progress_proven=later_progress_evidence,
        request_receipt_ref=request_ref,
        effect_receipt_ref=effect_ref,
    )
    if outcome == "succeeded":
        if (
            required_runtime_model is not None
            and receipt.get("resolved_runtime_model") != required_runtime_model
        ):
            reasons.append("success_model_unproven")
        if not started:
            reasons.append("success_without_started")
        if not isinstance(receipt.get("mutation_facts"), Mapping):
            reasons.append("success_mutation_facts_missing")
        return ReceiptReconciliation(
            DispatchReceiptState.INDETERMINATE if reasons else DispatchReceiptState.TERMINAL,
            tuple(dict.fromkeys(reasons)),
            outcome,
            **common,
        )
    if outcome in {"failed", "blocked"}:
        return ReceiptReconciliation(DispatchReceiptState.TERMINAL, tuple(reasons), outcome, **common)
    if outcome == "indeterminate":
        return ReceiptReconciliation(
            DispatchReceiptState.INDETERMINATE,
            tuple(dict.fromkeys([*reasons, "indeterminate_outcome"])),
            outcome,
            **common,
        )
    if outcome == "running":
        if sidecar_present or local_success or terminal_status_label is not None:
            reasons.append("unproven_terminal_claimed")
        if process_present is False:
            reasons.append("process_exited_without_terminal_receipt")
        return ReceiptReconciliation(
            DispatchReceiptState.INDETERMINATE if reasons else DispatchReceiptState.STARTED,
            tuple(dict.fromkeys(reasons)),
            outcome,
            **common,
        )
    if outcome == "initialized":
        if sidecar_present or local_success or terminal_status_label is not None or process_present:
            reasons.append("unproven_terminal_claimed")
        return ReceiptReconciliation(
            DispatchReceiptState.INDETERMINATE if reasons else DispatchReceiptState.REQUESTED,
            tuple(dict.fromkeys(reasons)),
            outcome,
            **common,
        )
    return ReceiptReconciliation(
        DispatchReceiptState.INDETERMINATE,
        tuple(dict.fromkeys([*reasons, "unknown_outcome"])),
        outcome or None,
        **common,
    )


def reconcile_maintenance_receipt(
    receipt: MaintenanceReceipt | UnknownReceipt | schema.AutomaticDispatchReceipt | None,
    *,
    expected: ReceiptIdentity | None = None,
    prior_terminal: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> ReceiptAdoption | ReceiptReconciliation:
    """Route typed maintenance receipts or legacy dispatch receipts.

    Typed report/effect receipts require ``expected`` and never share an
    adoption path.  The generic subprocess receipt remains available only for
    the existing dispatch lifecycle adapter.
    """
    if receipt is None:
        if expected is None:
            return reconcile_automatic_dispatch_receipt(receipt, **kwargs)
        return reconcile_typed_maintenance_receipt(
            receipt, expected=expected, prior_terminal=prior_terminal
        )
    if isinstance(receipt, (ReportReceipt, EffectReceipt, UnknownReceipt)):
        if expected is None:
            return ReceiptAdoption(
                ReceiptAdoptionState.INDETERMINATE,
                ("missing_expected_identity",),
            )
        return reconcile_typed_maintenance_receipt(
            receipt, expected=expected, prior_terminal=prior_terminal
        )
    return reconcile_automatic_dispatch_receipt(receipt, **kwargs)
# M2 (T18): non-authorizing Maintenance shadow data on dispatch receipts
# ──────────────────────────────────────────────────────────────────────────────
#
# These helpers attach coherent-envelope identity and the shared shadow
# comparison to maintenance dispatch receipts as READ-ONLY data.  Authorization
# stays exclusively with the existing Run Authority / Custody / WBC gates (the
# generic receipt writer and the model-enforcement checks above); a shadow pass
# can never authorize an effect.  Stale or incoherent Maintenance evidence is
# serialized as non-dispatchable, and any attempted direct plan/chain write
# returns the typed M7 bypass finding with zero writer invocations.


def attach_maintenance_shadow_to_receipt(
    receipt: schema.AutomaticDispatchReceipt,
    *,
    envelope: Any | None = None,
    comparison: Any | None = None,
) -> schema.AutomaticDispatchReceipt:
    """Attach Maintenance shadow data to *receipt* without touching authority.

    * When neither ``envelope`` nor ``comparison`` is supplied the receipt is
      returned unchanged.
    * Otherwise a ``maintenance_shadow`` key is added with the envelope
      digest, the comparison bucket/reasons/digest, and the fail-closed
      derived ``dispatchable``/``green``/``terminal`` flags.  The flags are
      derived by the shared comparator and can NEVER be True for stale or
      incoherent evidence; the receipt's own authorization fields
      (``maintenance``, ``required_runtime_model``, subprocess state) are
      never modified by this function.
    """
    if envelope is None and comparison is None:
        return receipt
    if comparison is None:
        from arnold_pipelines.megaplan.maintenance.shadow import compare_shadow

        comparison = compare_shadow(
            {
                "green": False,
                "dispatchable": False,
                "terminal": False,
            },
            envelope,
        )
    shadow: dict[str, Any] = {
        "schema_version": 1,
        "envelope_digest": comparison.envelope_digest,
        "bucket": comparison.bucket.value,
        "reasons": list(comparison.reasons),
        "comparison_digest": comparison.digest,
        "green": comparison.green,
        "dispatchable": comparison.dispatchable,
        "terminal": comparison.terminal,
        "envelope_eligible": comparison.envelope_eligible,
        "cross_environment": comparison.cross_environment,
        "stale_projection": comparison.stale_projection,
        "digest_mismatch": comparison.digest_mismatch,
        "missing_denominator": comparison.missing_denominator,
        "denominator": comparison.denominator,
        "covered_count": comparison.covered_count,
        "coverage": comparison.coverage,
        "shadow_authorizes": False,
    }
    updated = dict(receipt)
    updated["maintenance_shadow"] = shadow
    return updated

def direct_write_bypass_finding(
    kind: str,
    request: str,
    *,
    finding_id: str | None = None,
) -> Any:
    """Return the typed M7 bypass finding for a direct plan/chain write attempt.

    ``kind`` is ``"plan"`` or ``"chain"``.  The finding names the M7
    controlled-writer-inventory seam, is data-only, and guarantees zero
    invocations of ``write_plan_state`` / ``save_chain_state`` /
    ``TransitionWriter`` / raw plan/chain writers.  Maintenance code never
    calls a plan/chain truth writer directly — an attempted direct write is
    routed here and returns the inert finding instead.
    """
    from arnold_pipelines.megaplan.maintenance.boundaries import (
        chain_write_finding,
        plan_write_finding,
    )

    if kind == "plan":
        return plan_write_finding(request, finding_id=finding_id)
    if kind == "chain":
        return chain_write_finding(request, finding_id=finding_id)
    raise ValueError(f"direct write kind must be 'plan' or 'chain', got {kind!r}")


__all__ = [
    "DispatchReceiptState",
    "failed_session_receipt_allows_rearm",
    "EffectReceipt",
    "MAINTENANCE_REQUIRED_RUNTIME_MODEL",
    "MaintenanceEffectReceipt",
    "MaintenanceModelEnforcementError",
    "MaintenanceReportReceipt",
    "ReceiptAdoption",
    "ReceiptAdoptionState",
    "ReceiptIdentity",
    "ReceiptIdentityMismatch",
    "ReceiptKind",
    "ReceiptReconciliation",
    "ReceiptStatus",
    "ReportReceipt",
    "UnknownReceipt",
    "attach_maintenance_shadow_to_receipt",
    "direct_write_bypass_finding",
    "finalize_maintenance_dispatch_receipt",
    "initialize_and_launch_maintenance_dispatch",
    "initialize_maintenance_dispatch_receipt",
    "parse_maintenance_receipt",
    "prepare_maintenance_dispatch_receipt",
    "reconcile_automatic_dispatch_receipt",
    "reconcile_maintenance_receipt",
    "reconcile_typed_maintenance_receipt",
    "record_maintenance_started",
    "route_allowlisted_effect",
    "adopt_effect_receipt",
    "reconcile_effect_receipt",
]
