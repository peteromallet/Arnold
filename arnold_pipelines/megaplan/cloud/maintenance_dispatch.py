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

from pathlib import Path
from typing import Callable, Mapping, TypeVar

from arnold_pipelines.megaplan.receipts import schema, writer

#: The only runtime model that may certify a successful maintenance action.
MAINTENANCE_REQUIRED_RUNTIME_MODEL = "gpt-5.6-sol"

_ProcessT = TypeVar("_ProcessT")


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
    initialized = writer.initialize_dispatch_receipt(Path(plan_dir), receipt)
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
    "MAINTENANCE_REQUIRED_RUNTIME_MODEL",
    "MaintenanceModelEnforcementError",
    "attach_maintenance_shadow_to_receipt",
    "direct_write_bypass_finding",
    "finalize_maintenance_dispatch_receipt",
    "initialize_and_launch_maintenance_dispatch",
    "prepare_maintenance_dispatch_receipt",
    "record_maintenance_started",
]
