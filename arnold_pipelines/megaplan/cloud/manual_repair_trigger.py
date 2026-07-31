"""Fail-closed operator trigger for one canonical blocked-plan repair.

This command is intentionally narrower than the watchdog.  It resolves one
cloud session through the normal current-target resolver, verifies the exact
frozen plan/evidence cursor supplied by the operator, enqueues the same repair
request shape used by terminal lifecycle handling, and delegates to the
canonical ``simple_fixer`` through the repair delegation shim.

It never edits plan or chain state, and a deterministic receipt prevents the
same evidence cursor from being manually dispatched twice.

M7 shadow validation is wired into ``trigger_once`` before delegation
so that stale-authority paths are diagnosed before the fixer is invoked.
Production enforcement is always disabled.

Legacy ``/usr/local/bin/arnold-repair-trigger`` and
``ARNOLD_MANUAL_REPAIR_TRIGGER_BIN`` authority have been retired in favour
of typed simple_fixer delegation with append-only queue evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.cloud import feature_flags, repair_requests
from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.cloud.simple_fixer import SimpleFixerOccurrence
from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import (
    RepairDelegation,
    delegate_to_simple_fixer,
    emit_zero_authority_rejection,
)
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyTargetKey,
    F01_REPAIR_OCCURRENCE_FIELDS,
    build_custody_target_key,
)

# ── M7 shadow validator import (enforcement always disabled) ────────────────
try:
    from arnold_pipelines.megaplan.custody.action_validator import (
        validate_action_boundary_simple,
    )
    _M7_VALIDATOR_AVAILABLE = True
except ImportError:
    _M7_VALIDATOR_AVAILABLE = False


RECEIPT_SCHEMA = "arnold-manual-repair-trigger-v1"
RECEIPT_DIR_NAME = "manual-triggers"
ALLOWED_PLAN_STATES = frozenset({"blocked", "failed"})
ALLOWED_HISTORY_FAILURE_RESULTS = frozenset({"blocked", "error", "failed"})


class ManualRepairTriggerError(RuntimeError):
    """The requested one-shot repair could not be dispatched safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManualRepairTriggerError(f"required JSON is unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise ManualRepairTriggerError(f"required JSON is not an object: {path}")
    return payload


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ManualRepairTriggerError(f"cannot fingerprint plan state: {path}") from exc


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _blocked_task_id(metadata: Mapping[str, Any]) -> str:
    for key in ("blocked_task_ids", "task_ids"):
        values = metadata.get(key)
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            for value in values:
                task_id = _text(value)
                if task_id:
                    return task_id
    return ""


def _evidence_cursor(state: Mapping[str, Any], failure: Mapping[str, Any]) -> dict[str, Any]:
    candidates = (
        failure.get("evidence_cursor"),
        _mapping(failure.get("metadata")).get("evidence_cursor"),
        _mapping(state.get("resume_cursor")).get("evidence_cursor"),
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return dict(candidate)
    history = state.get("history")
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)) or not history:
        return {}
    latest = history[-1]
    if not isinstance(latest, Mapping):
        return {}
    failure_phase = _text(failure.get("phase"))
    history_phase = _text(latest.get("step"))
    history_result = _text(latest.get("result"))
    artifact_hash = _text(latest.get("artifact_hash"))
    if (
        not failure_phase
        or history_phase != failure_phase
        or history_result not in ALLOWED_HISTORY_FAILURE_RESULTS
        or not artifact_hash
    ):
        return {}
    return {
        "history_index": len(history) - 1,
        "review_artifact_hash": artifact_hash,
    }


def _receipt_id(*, session: str, plan: str, history_index: int, artifact_hash: str) -> str:
    encoded = json.dumps(
        [session, plan, history_index, artifact_hash],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any], *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as exc:
            raise ManualRepairTriggerError(
                f"manual trigger receipt already exists for this evidence cursor: {path}"
            ) from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, sort_keys=True)
            handle.write("\n")
        return

    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _build_manual_trigger_occurrence_target(
    *,
    session: str,
    plan: str,
    workspace: str,
    remote_spec: str,
    run_kind: str,
    expected_history_index: int,
    expected_artifact_hash: str,
    failure_kind: str,
    phase_or_step: str,
    blocked_task_id: str,
) -> CustodyTargetKey | None:
    """Build a :class:`CustodyTargetKey` from the manual trigger context.

    Returns ``None`` when the exact F01 tuple cannot be satisfied — this is
    the boundary at which ``manual_repair_trigger_rejected`` is emitted.
    Authority is never derived from labels, liveness, WBC receipts, or
    rebuildable projections.
    """
    fields: dict[str, str] = {}
    for name in F01_REPAIR_OCCURRENCE_FIELDS:
        fields[name] = ""
    fields["environment"] = (workspace or "manual-trigger").strip()
    fields["session"] = (session or "").strip()
    fields["chain"] = (remote_spec or plan or "").strip()
    fields["plan_revision"] = (plan or "").strip()
    fields["phase"] = (phase_or_step or "").strip()
    fields["task"] = (blocked_task_id or "").strip()
    fields["attempt"] = str(expected_history_index).strip()
    fields["normalized_failure_kind"] = (failure_kind or "terminal_blocked").strip()
    fields["blocker_or_phase_result_hash"] = (expected_artifact_hash or "").strip()
    fields["fence"] = str(expected_history_index).strip()
    return build_custody_target_key(**fields)


# ── M7 shadow validator helper (T15) ────────────────────────────────────────


def _shadow_validate_manual_trigger_boundary(
    *,
    session: str,
    plan: str,
    expected_history_index: int,
    expected_artifact_hash: str,
    request_id: str,
) -> dict[str, Any]:
    """Run the M7 shadow validator before manual repair trigger dispatch (non-blocking).

    Builds a best-effort ``CustodyTargetKey`` from the manual trigger context,
    calls ``validate_action_boundary_simple`` with ``action_type=\"repair\"``,
    and returns typed conflict/fence/reconcile diagnostics.  Never raises —
    all errors are captured as diagnostic metadata.

    Production enforcement is always disabled; this is a shadow-only call.
    """
    if not _M7_VALIDATOR_AVAILABLE:
        return {
            "m7_validator_available": False,
            "reason": "action_validator module not importable",
        }

    import hashlib as _hashlib

    try:
        target_dict = {
            "environment": "manual-trigger",
            "session": session or "unknown",
            "chain": plan or "unknown",
            "plan_revision": plan or "unknown",
            "phase": "manual_trigger",
            "task": request_id or "unknown",
            "attempt": str(expected_history_index),
            "normalized_failure_kind": "manual_trigger",
            "blocker_or_phase_result_hash": _hashlib.sha256(
                f"{session}:{plan}:{expected_artifact_hash}".encode("utf-8")
            ).hexdigest()[:16],
            "fence": str(expected_history_index),
        }

        result = validate_action_boundary_simple(
            action_type="repair",
            target=target_dict,
            run_authority_grant_id="manual_repair_trigger",
            coordinator_fence_token=expected_history_index,
            wbc_attempt_reference=request_id,
        )

        typed_events: list[dict[str, Any]] = []
        for check in result.checks:
            outcome = check.outcome.value
            if outcome == "conflict":
                typed_events.append({
                    "event_type": "conflict",
                    "source": check.source,
                    "detail": check.detail,
                    "observed_at": check.observed_at,
                })
            elif outcome == "fenced":
                typed_events.append({
                    "event_type": "fence",
                    "source": check.source,
                    "detail": check.detail,
                    "observed_at": check.observed_at,
                })
            elif outcome in ("stale", "expired"):
                typed_events.append({
                    "event_type": "reconcile",
                    "source": check.source,
                    "detail": check.detail,
                    "observed_at": check.observed_at,
                })

        return {
            "m7_validator_available": True,
            "gate_result": result.gate_result.value,
            "enforcement_enabled": result.enforcement_enabled,
            "shadow_mode": result.is_shadow,
            "typed_events": typed_events,
            "checks_summary": {
                c.source: c.outcome.value for c in result.checks
            },
            "validated_at": result.validated_at,
        }
    except Exception as exc:
        return {
            "m7_validator_available": True,
            "error": f"{type(exc).__name__}: {exc}",
            "typed_events": [],
        }


def trigger_once(
    *,
    session: str,
    plan: str,
    expected_history_index: int,
    expected_artifact_hash: str,
    marker_dir: Path,
    queue_root: Path,
    repair_data_dir: Path | None = None,
    target_resolver: Callable[..., dict[str, Any]] = resolve_current_target,
) -> dict[str, Any]:
    """Validate, enqueue, and delegate one exact canonical repair request.

    Builds a typed ``RepairDelegation`` with ``caller_kind=\"operator_trigger\"``
    and delegates to the canonical ``simple_fixer`` through the repair
    delegation shim.  When an exact-occurrence identity cannot be
    constructed the function emits ``manual_repair_trigger_rejected``
    and preserves the append-only queue evidence receipt.

    Legacy subprocess dispatch and env-var override authority have been
    retired; all trigger paths now flow through the delegation shim.
    """

    session = _text(session)
    plan = _text(plan)
    artifact_hash = _text(expected_artifact_hash)
    if not session or not plan or expected_history_index < 0 or not artifact_hash:
        raise ManualRepairTriggerError(
            "session, plan, non-negative history index, and artifact hash are required"
        )
    if not feature_flags.mutation_authorized(feature_flags.MUTATION_PATH_L1):
        raise ManualRepairTriggerError(
            "L1 mutation is not authorized; set invocation-scoped ARNOLD_AUTONOMY=1 and "
            "ARNOLD_REPAIR_TRIGGER_ENABLED=1"
        )

    queue_root = repair_requests.validate_queue_root(queue_root)
    target = target_resolver(
        session,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )
    current_refs = _mapping(target.get("current_refs"))
    evidence_state = _mapping(target.get("evidence_state"))
    stale_evidence = target.get("stale_evidence")
    if target.get("target_session") != session:
        raise ManualRepairTriggerError("resolver target session disagrees with the requested session")
    if target.get("authoritative_source") != "chain_state":
        raise ManualRepairTriggerError("current target is not chain-state authoritative")
    if evidence_state.get("mutation_eligible") is not True:
        raise ManualRepairTriggerError("current-target evidence is not mutation eligible")
    if isinstance(stale_evidence, list) and stale_evidence:
        raise ManualRepairTriggerError("current-target resolver reported stale evidence")
    if _text(current_refs.get("current_plan_name")) != plan:
        raise ManualRepairTriggerError("requested plan is not the resolver's current plan")

    plan_summary = _mapping(target.get("plan_state"))
    plan_path = Path(_text(plan_summary.get("path")))
    if not plan_path.is_absolute() or plan_path.name != "state.json":
        raise ManualRepairTriggerError("resolver did not provide an absolute plan state path")
    if _sha256_file(plan_path) != _text(plan_summary.get("fingerprint")):
        raise ManualRepairTriggerError("plan state changed after current-target resolution")
    state = _read_json_object(plan_path)
    if _text(state.get("name")) != plan:
        raise ManualRepairTriggerError("plan state identity disagrees with the requested plan")
    current_state = _text(state.get("current_state"))
    if current_state not in ALLOWED_PLAN_STATES:
        raise ManualRepairTriggerError(f"plan state {current_state!r} is not repair-trigger eligible")
    failure = _mapping(state.get("latest_failure"))
    if not failure:
        raise ManualRepairTriggerError("blocked plan has no latest_failure evidence")
    cursor = _evidence_cursor(state, failure)
    observed_index = cursor.get("history_index")
    observed_hash = _text(cursor.get("review_artifact_hash"))
    if observed_index != expected_history_index or observed_hash != artifact_hash:
        raise ManualRepairTriggerError("frozen evidence cursor does not match current plan state")

    workspace = Path(_text(current_refs.get("workspace")))
    remote_spec = _text(current_refs.get("remote_spec"))
    run_kind = _text(current_refs.get("run_kind")) or "chain"
    if not workspace.is_absolute() or not workspace.is_dir():
        raise ManualRepairTriggerError("resolver workspace is unavailable")
    metadata = _mapping(failure.get("metadata"))
    configured_profile = _text(_mapping(state.get("config")).get("profile"))
    phase_or_step = _text(failure.get("phase"))
    problem_signature = {
        "failure_kind": _text(failure.get("kind")) or "terminal_blocked",
        "current_state": current_state,
        "phase_or_step": phase_or_step,
        "milestone_or_plan": plan,
        "gate_recommendation": _text(failure.get("suggested_action")),
        "blocked_task_id": _blocked_task_id(metadata) or f"phase:{phase_or_step}",
    }
    root_cause_hint = _text(failure.get("message")) or "plan entered a blocked terminal state"
    request_id = repair_requests.request_id_for(
        session=session,
        problem_signature=problem_signature,
        root_cause_hint=root_cause_hint,
    )
    receipt_id = _receipt_id(
        session=session,
        plan=plan,
        history_index=expected_history_index,
        artifact_hash=artifact_hash,
    )
    receipt_path = queue_root / RECEIPT_DIR_NAME / f"{receipt_id}.json"
    started_at = _utc_now()
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "status": "dispatching",
        "started_at": started_at,
        "session": session,
        "plan": plan,
        "evidence_cursor": {
            "history_index": expected_history_index,
            "review_artifact_hash": artifact_hash,
        },
        "plan_state_fingerprint": _text(plan_summary.get("fingerprint")),
        "request_id": request_id,
        "queue_root": str(queue_root),
        "delegation_target": "simple_fixer",
    }
    _write_json_atomic(receipt_path, receipt, exclusive=True)

    try:
        repair_target = {
            "plan_dir": str(plan_path.parent),
            "plan_name": plan,
            "workspace_path": str(workspace),
            "remote_spec": remote_spec,
            "evidence_cursor": dict(cursor),
            "recovery_contract": {
                "preserve_configured_profile": True,
                "required_cursor_advance": True,
                "forbid_standalone_completion": True,
                "success_requires": (
                    "the canonical plan must advance beyond the frozen evidence cursor"
                ),
            },
        }
        if configured_profile:
            repair_target["configured_profile"] = configured_profile
        queued = repair_requests.enqueue_repair_request(
            queue_root=queue_root,
            marker_dir=marker_dir,
            session=session,
            source="manual_terminal_failure_retrigger",
            workspace=workspace,
            run_kind=run_kind,
            target=repair_target,
            problem_signature=problem_signature,
            root_cause_hint=root_cause_hint,
        )
        queued_request = _mapping(queued.get("request"))
        if _text(queued_request.get("request_id")) != request_id:
            raise ManualRepairTriggerError("canonical queue returned a different request identity")
        if queued.get("status") not in {"queued", "coalesced"}:
            raise ManualRepairTriggerError(f"repair request was not accepted: {queued.get('status')}")

        # ── M7 shadow validation before delegation (T15) ────────────────────
        m7_shadow = _shadow_validate_manual_trigger_boundary(
            session=session,
            plan=plan,
            expected_history_index=expected_history_index,
            expected_artifact_hash=artifact_hash,
            request_id=request_id,
        )
        receipt["m7_shadow_validation"] = m7_shadow

        # ── Build delegation and delegate to simple_fixer ──────────────────
        occurrence_target = _build_manual_trigger_occurrence_target(
            session=session,
            plan=plan,
            workspace=str(workspace),
            remote_spec=remote_spec,
            run_kind=run_kind,
            expected_history_index=expected_history_index,
            expected_artifact_hash=artifact_hash,
            failure_kind=problem_signature["failure_kind"],
            phase_or_step=phase_or_step,
            blocked_task_id=problem_signature["blocked_task_id"],
        )

        if occurrence_target is None:
            # Cannot satisfy the exact F01 tuple — emit a typed rejection
            # that preserves the append-only queue evidence receipt.
            rejection = emit_zero_authority_rejection(
                "operator_trigger",
                request_id,
                reason=(
                    "manual repair trigger cannot build exact-occurrence "
                    "identity from available context; all ten F01 fields "
                    "must be non-empty"
                ),
            )
            receipt.update(
                {
                    "status": "manual_repair_trigger_rejected",
                    "completed_at": _utc_now(),
                    "request_status": queued.get("status"),
                    "request_path": queued.get("path"),
                    "delegation_outcome": "manual_repair_trigger_rejected",
                    "delegation_evidence": rejection.evidence,
                }
            )
            _write_json_atomic(receipt_path, receipt)
            raise ManualRepairTriggerError(
                f"manual repair trigger rejected: cannot build exact-occurrence "
                f"identity; receipt: {receipt_path}"
            )

        delegation = RepairDelegation(
            caller_kind="operator_trigger",
            caller_id=request_id,
            target=occurrence_target,
        )

        # The mutation action for the simple_fixer is the trigger
        # dispatch itself — it records the queued request and advances
        # the occurrence state.
        def _trigger_mutation(occ: SimpleFixerOccurrence) -> str:
            return occ.occurrence_fingerprint

        delegation_result = delegate_to_simple_fixer(
            delegation,
            queue_dir=str(queue_root),
            mutate=_trigger_mutation,
            actor="manual_repair_trigger",
            request_id=request_id,
            session_id=session,
            kind="immediate_trigger",
            verifier_slot="",
        )

        dispatched = delegation_result.delegated
        receipt.update(
            {
                "status": "dispatched" if dispatched else "dispatch_failed",
                "completed_at": _utc_now(),
                "request_status": queued.get("status"),
                "request_path": queued.get("path"),
                "delegation_outcome": delegation_result.outcome,
                "simple_fixer_outcome": delegation_result.simple_fixer_outcome,
                "delegation_evidence": delegation_result.evidence,
            }
        )
        _write_json_atomic(receipt_path, receipt)
        if not dispatched:
            raise ManualRepairTriggerError(
                f"canonical trigger did not establish a dispatch; "
                f"delegation outcome: {delegation_result.outcome}; "
                f"receipt: {receipt_path}"
            )
    except Exception as exc:
        if receipt.get("status") == "dispatching":
            receipt.update(
                {
                    "status": "dispatch_failed",
                    "completed_at": _utc_now(),
                    "error_kind": type(exc).__name__,
                }
            )
            _write_json_atomic(receipt_path, receipt)
        raise

    return {
        "status": "dispatched",
        "session": session,
        "plan": plan,
        "request_id": request_id,
        "delegation_outcome": receipt.get("delegation_outcome", ""),
        "simple_fixer_outcome": receipt.get("simple_fixer_outcome", ""),
        "occurrence_fingerprint": (
            receipt.get("delegation_evidence", {}).get("occurrence_fingerprint", "")
        ),
        "receipt_path": str(receipt_path),
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--expected-history-index", type=int, required=True)
    parser.add_argument("--expected-artifact-hash", required=True)
    parser.add_argument(
        "--marker-dir",
        type=Path,
        default=Path(
            os.getenv("CLOUD_WATCHDOG_MARKER_DIR", "/workspace/.megaplan/cloud-sessions")
        ),
    )
    parser.add_argument(
        "--queue-root",
        type=Path,
        default=Path(
            os.getenv("ARNOLD_REPAIR_QUEUE_ROOT", "/workspace/.megaplan/repair-queue")
        ),
    )
    parser.add_argument(
        "--repair-data-dir",
        type=Path,
        default=(Path(value) if (value := os.getenv("CLOUD_WATCHDOG_REPAIR_DATA_DIR")) else None),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = trigger_once(
            session=args.session,
            plan=args.plan,
            expected_history_index=args.expected_history_index,
            expected_artifact_hash=args.expected_artifact_hash,
            marker_dir=args.marker_dir,
            queue_root=args.queue_root,
            repair_data_dir=args.repair_data_dir,
        )
    except ManualRepairTriggerError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
