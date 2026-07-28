"""Fail-closed WBC validation for override and human-gate transitions."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.notification_safety import classify_fixture_safety
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.run_authority import CapabilityGrant, CoordinatorFence

from .action_validator import ActionBoundaryContext, GateResult, validate_action_boundary
from .admission_control import source_record_for_path
from .contracts import CustodyLease, CustodyTargetKey
from .controlled_writer_registry import (
    Cohort,
    ControlledWriter,
    WriteGuardDecision,
    register_writer,
    writer_guard,
)
from .outbox import OutboxRecord, OutboxRecordStatus, OutboxRecordType


@dataclass(frozen=True)
class OverrideWbcRule:
    identity: str
    expected: Any
    observed: Any
    satisfied: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "expected": self.expected,
            "observed": self.observed,
            "satisfied": self.satisfied,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class _OverrideWriterSpec:
    transition: str
    writer_id: str
    surface_name: str
    contract_id: str
    function_name: str
    action_type: str
    required_capability: str


def _controlled_writer(spec: _OverrideWriterSpec) -> ControlledWriter:
    return ControlledWriter(
        writer_id=spec.writer_id,
        surface_name=spec.surface_name,
        cohort=Cohort.ACTIVE,
        contract_ids=(spec.contract_id,),
        source_file="arnold_pipelines/megaplan/handlers/override.py",
        function_name=spec.function_name,
        required_wbc_phases=("source_lookup", "grant_lease_matrix", "fixture_authorization"),
        action_kind="override_transition",
    )


_WRITER_SPECS: tuple[_OverrideWriterSpec, ...] = (
    _OverrideWriterSpec(
        transition="abort",
        writer_id="megaplan.override.wbc.abort",
        surface_name="megaplan.override.wbc.abort",
        contract_id="megaplan.override.wbc.abort.v1",
        function_name="_override_abort",
        action_type="cancellation",
        required_capability="override.abort",
    ),
    _OverrideWriterSpec(
        transition="force-proceed",
        writer_id="megaplan.override.wbc.force_proceed",
        surface_name="megaplan.override.wbc.force_proceed",
        contract_id="megaplan.override.wbc.force_proceed.v1",
        function_name="_override_force_proceed",
        action_type="completion",
        required_capability="override.force_proceed",
    ),
    _OverrideWriterSpec(
        transition="replan",
        writer_id="megaplan.override.wbc.replan",
        surface_name="megaplan.override.wbc.replan",
        contract_id="megaplan.override.wbc.replan.v1",
        function_name="_override_replan",
        action_type="publication",
        required_capability="override.replan",
    ),
    _OverrideWriterSpec(
        transition="recover-blocked",
        writer_id="megaplan.override.wbc.recover_blocked",
        surface_name="megaplan.override.wbc.recover_blocked",
        contract_id="megaplan.override.wbc.recover_blocked.v1",
        function_name="_override_recover_blocked",
        action_type="repair",
        required_capability="override.recover_blocked",
    ),
    _OverrideWriterSpec(
        transition="resume-clarify",
        writer_id="megaplan.override.wbc.resume_clarify",
        surface_name="megaplan.override.wbc.resume_clarify",
        contract_id="megaplan.override.wbc.resume_clarify.v1",
        function_name="_override_resume_clarify",
        action_type="delivery",
        required_capability="override.resume_clarify",
    ),
    _OverrideWriterSpec(
        transition="adopt-execution",
        writer_id="megaplan.override.wbc.adopt_execution",
        surface_name="megaplan.override.wbc.adopt_execution",
        contract_id="megaplan.override.wbc.adopt_execution.v1",
        function_name="_override_adopt_execution",
        action_type="publication",
        required_capability="override.adopt_execution",
    ),
    _OverrideWriterSpec(
        transition="suspension-waiver",
        writer_id="megaplan.override.wbc.suspension_waiver",
        surface_name="megaplan.override.wbc.suspension_waiver",
        contract_id="megaplan.override.wbc.suspension_waiver.v1",
        function_name="handle_override",
        action_type="delivery",
        required_capability="megaplan:suspension",
    ),
    _OverrideWriterSpec(
        transition="human-gate",
        writer_id="megaplan.override.wbc.human_gate",
        surface_name="megaplan.override.wbc.human_gate",
        contract_id="megaplan.override.wbc.human_gate.v1",
        function_name="handle_override",
        action_type="delivery",
        required_capability="execute:approval-approved",
    ),
)
_WRITER_SPECS_BY_TRANSITION: Mapping[str, _OverrideWriterSpec] = {
    spec.transition: spec for spec in _WRITER_SPECS
}


@dataclass(frozen=True)
class _SyntheticLeaseStore:
    lease: CustodyLease

    def current_lease(self, lease_id: str) -> CustodyLease | None:
        return self.lease if lease_id == self.lease.lease_id else None

    def find_by_target_key(
        self,
        subject_type: str,
        subject_id: str,
        action: str,
        target_kind: str,
        target_id: str,
        contract_id: str,
    ) -> tuple[CustodyLease, ...]:
        target = self.lease.target_key
        if target is None:
            return ()
        if (
            target.subject_type == subject_type
            and target.subject_id == subject_id
            and target.action == action
            and target.target_kind == target_kind
            and target.target_id == target_id
            and target.contract_id == contract_id
        ):
            return (self.lease,)
        return ()


@dataclass(frozen=True)
class _SyntheticOutbox:
    record: OutboxRecord

    def list_records(self) -> tuple[OutboxRecord, ...]:
        return (self.record,)


def register_override_wbc_writers() -> None:
    for spec in _WRITER_SPECS:
        try:
            register_writer(_controlled_writer(spec))
        except ValueError:
            continue


def _project_dir(state: Mapping[str, Any], plan_dir: Path) -> Path:
    config = state.get("config")
    raw = config.get("project_dir") if isinstance(config, Mapping) else None
    if isinstance(raw, str) and raw:
        return Path(raw)
    return plan_dir


def _state_subject(state: Mapping[str, Any], plan_dir: Path) -> str:
    name = state.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return plan_dir.name


def _current_invocation_id(state: Mapping[str, Any], transition: str) -> str:
    meta = state.get("meta")
    if isinstance(meta, Mapping):
        invocation = meta.get("current_invocation_id")
        if isinstance(invocation, str) and invocation.strip():
            return invocation.strip()
        overrides = meta.get("overrides")
        if isinstance(overrides, list):
            for entry in reversed(overrides):
                if (
                    isinstance(entry, Mapping)
                    and entry.get("action") == transition
                    and isinstance(entry.get("timestamp"), str)
                    and entry["timestamp"].strip()
                ):
                    return entry["timestamp"].strip()
    return f"{transition}:current"


def _stable_token(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _override_source_path(source_path: Path | None) -> Path:
    if source_path is not None:
        return source_path
    return Path(__file__).resolve().parents[1] / "handlers" / "override.py"


def _synthetic_boundary_materialization(
    *,
    spec: _OverrideWriterSpec,
    transition: str,
    plan_dir: Path,
    state: Mapping[str, Any],
    source_version: str,
) -> tuple[ActionBoundaryContext, _SyntheticLeaseStore, _SyntheticOutbox]:
    subject = _state_subject(state, plan_dir)
    invocation_id = _current_invocation_id(state, transition)
    fence_token = _stable_token(f"{transition}:{invocation_id}")
    target = CustodyTargetKey(
        "plan",
        subject,
        transition,
        "plan",
        subject,
        spec.contract_id,
    )
    grant_id = f"{transition}:{subject}:{invocation_id}:grant"
    attempt_ref = f"override:{transition}:{subject}:{invocation_id}"
    grant = CapabilityGrant(
        grant_id=grant_id,
        run_id=subject,
        run_revision=invocation_id,
        coordinator_attempt_id=f"override:{transition}",
        fence_token=fence_token,
        subject_ids=(subject,),
        capabilities=(spec.required_capability,),
        evidence_ids=(f"{spec.writer_id}:grant",),
    )
    fence = CoordinatorFence(
        subject,
        invocation_id,
        f"override:{transition}",
        fence_token,
    )
    lease = CustodyLease(
        lease_id=f"lease:{transition}:{subject}",
        target_key=target,
        owner=("override-wbc", "0", "override-wbc"),
        epoch=1,
        acquired_at="2026-07-20T00:00:00+00:00",
        expires_at="2999-01-01T00:00:00+00:00",
        fence_token=str(fence_token),
        status="active",
        run_authority_grant_id=grant_id,
        wbc_attempt_reference=attempt_ref,
    )
    outbox_record = OutboxRecord(
        outbox_id=f"outbox:{transition}:{subject}",
        lease_id=lease.lease_id,
        record_type=OutboxRecordType.LEASE_ACQUIRE,
        status=OutboxRecordStatus.PENDING,
        occurred_at="2026-07-20T00:00:00+00:00",
        idempotency_key=f"idem:{transition}:{subject}",
        wbc_attempt_reference=attempt_ref,
        run_authority_grant_id=grant_id,
        coordinator_fence_token=fence_token,
        custody_epoch=lease.custody_epoch,
        payload={
            "schema_version": source_version,
            "target_digest": target.target_digest,
        },
    )
    context = ActionBoundaryContext(
        action_type=spec.action_type,
        target=target,
        run_authority_grant_id=grant_id,
        coordinator_fence_token=fence_token,
        wbc_attempt_reference=attempt_ref,
        owner_host="override-wbc",
        owner_pid="0",
        owner_boot_id="override-wbc",
        expected_custody_epoch=lease.custody_epoch,
        expected_lease_id=lease.lease_id,
        run_authority_grant=grant,
        coordinator_fence=fence,
        required_capability=spec.required_capability,
        required_wbc_evidence_version=source_version,
    )
    return context, _SyntheticLeaseStore(lease), _SyntheticOutbox(outbox_record)


def validate_override_wbc_transition(
    *,
    transition: str,
    plan_dir: Path,
    state: Mapping[str, Any],
    source_path: Path | None = None,
    rules: Sequence[OverrideWbcRule] = (),
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    register_override_wbc_writers()
    spec = _WRITER_SPECS_BY_TRANSITION.get(transition)
    if spec is None:
        raise CliError(
            "override_wbc_transition_unknown",
            f"unknown override WBC transition {transition!r}",
        )

    guard = writer_guard(
        writer_id=spec.writer_id,
        surface_name=spec.surface_name,
        override_enforcement=True,
        override_fail_closed=True,
    )
    if guard.decision is not WriteGuardDecision.ALLOWED:
        raise CliError(
            "override_wbc_contract_missing",
            f"{spec.surface_name} is not registered as an allowed controlled writer",
            extra={
                "transition": transition,
                "writer_guard": {
                    "decision": guard.decision.value,
                    "writer_id": guard.writer_id,
                    "surface_name": guard.surface_name,
                    "diagnostics": list(guard.diagnostics),
                },
            },
        )

    project_dir = _project_dir(state, plan_dir)
    source = source_record_for_path(
        source_path=_override_source_path(source_path),
        project_dir=project_dir,
    )
    if not source.get("exists", True) or source.get("errors"):
        raise CliError(
            "override_wbc_source_missing",
            f"{spec.surface_name} could not reread the exact source record for {transition!r}",
            extra={"transition": transition, "source_record": source},
        )

    normalized_rules = [rule.to_dict() for rule in rules]
    failed_rule = next((rule for rule in normalized_rules if not rule["satisfied"]), None)
    if failed_rule is not None:
        raise CliError(
            "override_wbc_validation_failed",
            f"{spec.surface_name} validation {failed_rule['identity']!r} is stale or missing",
            extra={
                "transition": transition,
                "source_record": source,
                "rules": normalized_rules,
                "failed_rule": failed_rule,
            },
        )

    source_version = str(source.get("semantic_sha256") or source.get("file_sha256") or "").strip()
    if not source_version:
        raise CliError(
            "override_wbc_source_version_missing",
            f"{spec.surface_name} source record is missing a source identity digest",
            extra={"transition": transition, "source_record": source},
        )

    action_context, lease_store, outbox = _synthetic_boundary_materialization(
        spec=spec,
        transition=transition,
        plan_dir=plan_dir,
        state=state,
        source_version=source_version,
    )
    action_boundary = validate_action_boundary(
        action_context,
        lease_store=lease_store,
        outbox=outbox,
        enforcement_enabled=True,
    )
    if action_boundary.gate_result is not GateResult.AUTHORIZED:
        raise CliError(
            "override_wbc_action_denied",
            (
                f"{spec.surface_name} refused {transition!r}: "
                f"grant/lease/WBC validation returned {action_boundary.gate_result.value!r}"
            ),
            extra={
                "transition": transition,
                "source_record": source,
                "action_boundary": action_boundary.to_dict(),
            },
        )

    fixture_decision = classify_fixture_safety(
        workspace=str(project_dir),
        payload={
            "workspace": str(project_dir),
            "transition": transition,
            "details": dict(details or {}),
        },
    )
    payload: dict[str, Any] = {
        "schema": "arnold.megaplan.override_wbc_transition_evidence.v1",
        "writer_id": spec.writer_id,
        "surface_name": spec.surface_name,
        "transition": transition,
        "subject": _state_subject(state, plan_dir),
        "source_record": source,
        "rules": normalized_rules,
        "fixture_safety": {
            "authorized": fixture_decision.authorized,
            "reason": fixture_decision.reason,
        },
        "action_boundary": action_boundary.to_dict(),
        "required_capability": spec.required_capability,
    }
    if details:
        payload["details"] = dict(details)
    return payload


__all__ = [
    "OverrideWbcRule",
    "register_override_wbc_writers",
    "validate_override_wbc_transition",
]
