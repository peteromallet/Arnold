from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arnold.workflow.attempt_ledger_store import GateStatus, PostTerminalAppendError, SqliteAttemptLedgerStore
from arnold.workflow.boundary_evidence import BoundaryReceipt
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)
from arnold_pipelines.megaplan.custody.action_validator import ActionBoundaryContext
from arnold_pipelines.megaplan.custody.controlled_writer_registry import Cohort, ControlledWriter, _clear_registry, register_writer
from arnold_pipelines.megaplan.custody.contracts import CustodyLease, CustodyTargetKey
from arnold_pipelines.megaplan.custody.fake_prep_to_plan_adapter import (
    FakePrepToPlanAdapter,
    FakePrepToPlanDispatchResult,
    PREP_TO_PLAN_SURFACE,
    PREP_TO_PLAN_WRITER_ID,
)
from arnold_pipelines.megaplan.custody.outbox import OutboxRecord, OutboxRecordStatus, OutboxRecordType
from arnold_pipelines.megaplan.custody.wbc_runtime import (
    ActionBoundaryDeniedError,
    AttemptArtifact,
    ExactSourceLookupError,
    ExactSourceRecord,
    ImmutableAttemptArtifacts,
    PromotionMode,
    WbcRuntimeProducerFacade,
)
from arnold_pipelines.megaplan.workflows.boundary_contracts import prep_to_plan
from arnold_pipelines.run_authority import CapabilityGrant, CoordinatorFence


TARGET = CustodyTargetKey(
    "phase",
    "prep-phase",
    "dispatch",
    "boundary",
    prep_to_plan.boundary_id,
    prep_to_plan.boundary_id,
)
CAPABILITY = "megaplan.task.dispatch"
GRANT = CapabilityGrant(
    grant_id="grant-T12",
    run_id="run-T12",
    run_revision="rev-T12",
    coordinator_attempt_id="coord-T12",
    fence_token=4,
    subject_ids=(TARGET.subject_id,),
    capabilities=(CAPABILITY,),
    evidence_ids=("evidence-T12",),
)
FENCE = CoordinatorFence("run-T12", "rev-T12", "coord-T12", 4)


@dataclass
class FakeLeaseStore:
    leases: tuple[CustodyLease, ...]

    def current_lease(self, lease_id: str) -> CustodyLease | None:
        for lease in self.leases:
            if lease.lease_id == lease_id:
                return lease
        return None

    def find_by_target_key(
        self,
        subject_type: str,
        subject_id: str,
        action: str,
        target_kind: str,
        target_id: str,
        contract_id: str,
    ) -> tuple[CustodyLease, ...]:
        return tuple(
            lease
            for lease in self.leases
            if lease.target_key is not None
            and lease.target_key.subject_type == subject_type
            and lease.target_key.subject_id == subject_id
            and lease.target_key.action == action
            and lease.target_key.target_kind == target_kind
            and lease.target_key.target_id == target_id
            and lease.target_key.contract_id == contract_id
        )


@dataclass
class FakeOutbox:
    records: tuple[OutboxRecord, ...]

    def list_records(self) -> tuple[OutboxRecord, ...]:
        return self.records


@pytest.fixture(autouse=True)
def _reset_writer_registry() -> None:
    _clear_registry()
    yield
    _clear_registry()


def _register_writer() -> None:
    register_writer(
        ControlledWriter(
            writer_id=PREP_TO_PLAN_WRITER_ID,
            surface_name=PREP_TO_PLAN_SURFACE,
            cohort=Cohort.ACTIVE,
            contract_ids=(prep_to_plan.boundary_id,),
            source_file="arnold_pipelines/megaplan/custody/fake_prep_to_plan_adapter.py",
            function_name="FakePrepToPlanAdapter.run",
            required_wbc_phases=("start", "terminal"),
            action_kind="dispatch",
        )
    )


def _lease(*, epoch: int = 5, grant_id: str = GRANT.grant_id) -> CustodyLease:
    return CustodyLease(
        lease_id="lease-T12",
        target_key=TARGET,
        owner=("runtime-host", "4321", "boot-1"),
        epoch=epoch,
        acquired_at="2026-07-20T00:00:00+00:00",
        expires_at="2999-01-01T00:00:00+00:00",
        fence_token=str(FENCE.token),
        status="active",
        run_authority_grant_id=grant_id,
        wbc_attempt_reference="wbc-T12",
    )


def _record(*, version: str = "source.v1", grant_id: str = GRANT.grant_id) -> OutboxRecord:
    return OutboxRecord(
        outbox_id="outbox-T12",
        lease_id="lease-T12",
        record_type=OutboxRecordType.LEASE_ACQUIRE,
        status=OutboxRecordStatus.PENDING,
        occurred_at="2026-07-20T00:00:00+00:00",
        idempotency_key="idem-T12-outbox",
        wbc_attempt_reference="wbc-T12",
        run_authority_grant_id=grant_id,
        coordinator_fence_token=FENCE.token,
        custody_epoch=5,
        payload={
            "schema_version": version,
            "target_digest": TARGET.target_digest,
        },
    )


def _identity(attempt_id: str) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-T12",
        run_id="run-T12",
        graph_revision="graph-T12",
        step_id="prep",
        invocation_id="inv-T12",
        attempt_ordinal=1,
        attempt_id=attempt_id,
    )


def _event(
    *,
    attempt_id: str,
    sequence: int,
    event_type: AttemptEventType,
    idempotency_key: str,
    outcome: AttemptOutcome | None = None,
) -> LedgerEvent:
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=_identity(attempt_id),
        provenance=AttemptProvenance(actor_id="actor-T12", tool_id="tool-T12"),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.MEGAPLAN_PHASE, adapter_version="1"),
        versions=VersionSet(code_version="source.v1", config_version="cfg.v1", template_version="tmpl.v1"),
        grant_ref=GrantRef(grant_id=GRANT.grant_id),
        sequence=sequence,
        causal_predecessor_sequence=max(sequence - 1, 0),
        append_position=sequence,
        occurred_at=f"2026-07-20T00:00:0{sequence}+00:00",
        observed_at=f"2026-07-20T00:00:0{sequence}+00:00",
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
        payload={"sequence": sequence, "boundary_id": prep_to_plan.boundary_id},
    )


def _artifacts(attempt_id: str) -> ImmutableAttemptArtifacts:
    return ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        artifacts=(
            AttemptArtifact(
                artifact_id="artifact-T12",
                artifact_kind="boundary_receipt",
                version="artifact.v1",
                locator="memory://artifact-T12",
                metadata={"sha256": "abc123"},
            ),
        ),
        metadata={"boundary_id": prep_to_plan.boundary_id},
    )


def _context(
    action_type: str,
    *,
    grant: CapabilityGrant | None = GRANT,
    fence: CoordinatorFence | None = FENCE,
    expected_epoch: int = 5,
    lease_id: str = "lease-T12",
    wbc_reference: str = "wbc-T12",
) -> ActionBoundaryContext:
    return ActionBoundaryContext(
        action_type=action_type,  # type: ignore[arg-type]
        target=TARGET,
        run_authority_grant_id=GRANT.grant_id,
        coordinator_fence_token=FENCE.token,
        wbc_attempt_reference=wbc_reference,
        owner_host="runtime-host",
        owner_pid="4321",
        owner_boot_id="boot-1",
        expected_custody_epoch=expected_epoch,
        expected_lease_id=lease_id,
        run_authority_grant=grant,
        coordinator_fence=fence,
        required_capability=CAPABILITY,
        required_wbc_evidence_version="source.v1",
    )


def _facade(
    tmp_path: Path,
    *,
    source_version: str = "source.v1",
    lease_store: FakeLeaseStore | None = None,
    outbox: FakeOutbox | None = None,
    promotion_mode: PromotionMode = PromotionMode.ACTION_OFF,
) -> tuple[SqliteAttemptLedgerStore, WbcRuntimeProducerFacade]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = SqliteAttemptLedgerStore(tmp_path / "attempt-ledger.sqlite3")
    facade = WbcRuntimeProducerFacade(
        store,
        source_lookup=lambda key: ExactSourceRecord(
            lookup_key=key,
            version=source_version,
            source_uri=f"git+file:///repo#{source_version}",
            observed_at="2026-07-20T00:00:00+00:00",
            metadata={"key": key},
        ),
        lease_store=lease_store or FakeLeaseStore((_lease(),)),
        outbox=outbox or FakeOutbox((_record(),)),
        promotion_mode=promotion_mode,
        enforcement_enabled=True,
    )
    return store, facade


def test_fake_prep_to_plan_adapter_runs_start_before_dispatch_and_terminal_reread(tmp_path: Path) -> None:
    _register_writer()
    attempt_id = "12121212-1212-4212-8212-121212121212"
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    for artifact_name in ("research.md", "brief.md"):
        (plan_dir / artifact_name).write_text(f"{artifact_name}\n", encoding="utf-8")
    store, facade = _facade(tmp_path)
    adapter = FakePrepToPlanAdapter(plan_dir=plan_dir, project_dir=project_dir, facade=facade)
    artifacts = _artifacts(attempt_id)
    dispatched: list[str] = []

    def _dispatch(start_result: Any) -> FakePrepToPlanDispatchResult:
        dispatched.append("called")
        assert start_result.authoritative_reread is not None
        assert start_result.authoritative_reread.started_gate is not None
        assert start_result.authoritative_reread.started_gate.status == GateStatus.VERIFIED
        events = store.read_events(attempt_id)
        assert [event.event_type for event in events] == [AttemptEventType.STARTED]
        assert events[0].payload["__wbc_runtime__"]["promotion_mode"] == PromotionMode.ACTION_OFF.value
        receipt = adapter.build_receipt(
            invocation_id="inv-T12",
            details={"writer_id": PREP_TO_PLAN_WRITER_ID},
        )
        return FakePrepToPlanDispatchResult(receipt=receipt, user_payload={"dispatch": "plan"})

    result = adapter.run(
        attempt_id=attempt_id,
        start_event=_event(
            attempt_id=attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key="idem-start",
        ),
        complete_event=_event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-complete",
            outcome=AttemptOutcome.SUCCEEDED,
        ),
        dispatch=_dispatch,
        start_action_context=_context("dispatch"),
        completion_action_context=_context("completion"),
        artifacts=artifacts,
    )

    assert dispatched == ["called"]
    assert result.reserve.authoritative_reread is not None
    assert result.start.authoritative_reread is not None
    assert result.complete.authoritative_reread is not None
    assert result.complete.authoritative_reread.terminal_gate is not None
    assert result.complete.authoritative_reread.terminal_gate.status == GateStatus.VERIFIED
    assert result.complete.authoritative_reread.verified_event is not None
    assert result.complete.authoritative_reread.verified_event.sequence == 2
    assert result.complete.append_result is not None
    assert result.complete.append_result.event.causal_predecessor_sequence == 1
    assert [event.sequence for event in result.complete.authoritative_reread.events] == [1, 2]
    assert result.persisted_receipt["boundary_id"] == prep_to_plan.boundary_id
    assert result.persisted_receipt["artifact_refs"] == ("research.md", "brief.md")
    assert result.start.append_result is not None
    assert result.start.append_result.event.payload["__wbc_runtime__"]["source_record"]["version"] == "source.v1"

    with pytest.raises(PostTerminalAppendError):
        facade.complete_attempt(
            attempt_id=attempt_id,
            event=_event(
                attempt_id=attempt_id,
                sequence=3,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="idem-complete-duplicate",
                outcome=AttemptOutcome.SUCCEEDED,
            ),
            writer_id=PREP_TO_PLAN_WRITER_ID,
            surface_name=PREP_TO_PLAN_SURFACE,
            source_lookup_key="prep_to_plan:complete",
            expected_source_version="source.v1",
            action_context=_context("completion"),
            artifacts=artifacts,
        )


@pytest.mark.parametrize(
    ("case", "build_adapter", "build_start_context", "build_start_event", "expected_exception", "match"),
    [
        (
            "missing_grant",
            lambda tmp_path: _facade(tmp_path),
            lambda: _context("dispatch", grant=None),
            lambda attempt_id: _event(
                attempt_id=attempt_id,
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-start-missing-grant",
            ),
            ActionBoundaryDeniedError,
            "blocked_missing_grant",
        ),
        (
            "missing_fence",
            lambda tmp_path: _facade(tmp_path),
            lambda: _context("dispatch", fence=None),
            lambda attempt_id: _event(
                attempt_id=attempt_id,
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-start-missing-fence",
            ),
            ActionBoundaryDeniedError,
            "blocked_fence_mismatch",
        ),
        (
            "missing_lease",
            lambda tmp_path: _facade(tmp_path, lease_store=FakeLeaseStore(())),
            lambda: _context("dispatch"),
            lambda attempt_id: _event(
                attempt_id=attempt_id,
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-start-missing-lease",
            ),
            ActionBoundaryDeniedError,
            "blocked_no_lease",
        ),
        (
            "stale_epoch",
            lambda tmp_path: _facade(tmp_path, lease_store=FakeLeaseStore((_lease(epoch=6),))),
            lambda: _context("dispatch", expected_epoch=5),
            lambda attempt_id: _event(
                attempt_id=attempt_id,
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-start-stale-epoch",
            ),
            ActionBoundaryDeniedError,
            "blocked_stale_epoch",
        ),
        (
            "stale_source",
            lambda tmp_path: _facade(tmp_path, source_version="source.v0"),
            lambda: _context("dispatch"),
            lambda attempt_id: _event(
                attempt_id=attempt_id,
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-start-stale-source",
            ),
            ExactSourceLookupError,
            "expected 'source.v1', observed 'source.v0'",
        ),
        (
            "stale_lifecycle_identity",
            lambda tmp_path: _facade(tmp_path),
            lambda: _context("dispatch"),
            lambda _attempt_id: _event(
                attempt_id="99999999-9999-4999-8999-999999999999",
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-start-stale-lifecycle",
            ),
            ValueError,
            "does not match event attempt",
        ),
    ],
)
def test_fake_prep_to_plan_adapter_blocks_before_dispatch_on_stale_identity_inputs(
    tmp_path: Path,
    case: str,
    build_adapter: Any,
    build_start_context: Any,
    build_start_event: Any,
    expected_exception: type[Exception],
    match: str,
) -> None:
    _register_writer()
    attempt_id = "34343434-3434-4434-8434-343434343434"
    plan_dir = tmp_path / f"plan-{case}"
    project_dir = tmp_path / f"project-{case}"
    plan_dir.mkdir()
    project_dir.mkdir()
    store, facade = build_adapter(tmp_path / case)
    adapter = FakePrepToPlanAdapter(plan_dir=plan_dir, project_dir=project_dir, facade=facade)
    invoked: list[str] = []

    def _dispatch(_start_result: Any) -> FakePrepToPlanDispatchResult:
        invoked.append("called")
        return FakePrepToPlanDispatchResult(
            receipt=adapter.build_receipt(invocation_id="inv-T12-negative"),
            user_payload={"case": case},
        )

    with pytest.raises(expected_exception, match=match):
        adapter.run(
            attempt_id=attempt_id,
            start_event=build_start_event(attempt_id),
            complete_event=_event(
                attempt_id=attempt_id,
                sequence=2,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key=f"idem-complete-{case}",
                outcome=AttemptOutcome.SUCCEEDED,
            ),
            dispatch=_dispatch,
            start_action_context=build_start_context(),
            completion_action_context=_context("completion"),
            artifacts=_artifacts(attempt_id),
        )

    assert invoked == []
    assert store.read_events(attempt_id) == []
    assert not (plan_dir / "boundary_receipts" / f"{prep_to_plan.boundary_id}.json").exists()
