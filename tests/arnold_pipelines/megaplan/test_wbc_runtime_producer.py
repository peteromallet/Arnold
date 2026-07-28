from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from arnold.workflow.attempt_ledger_store import GateStatus, SqliteAttemptLedgerStore
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
from arnold_pipelines.megaplan.custody.compatibility import validate_rollback_safety
from arnold_pipelines.megaplan.custody.controlled_writer_registry import Cohort, ControlledWriter, _clear_registry, register_writer
from arnold_pipelines.megaplan.custody.contracts import CustodyLease, CustodyTargetKey
from arnold_pipelines.megaplan.custody.outbox import OutboxRecord, OutboxRecordStatus, OutboxRecordType
from arnold_pipelines.megaplan.custody.wbc_runtime import (
    AttemptArtifact,
    ExactSourceLookupError,
    ExactSourceRecord,
    ImmutableAttemptArtifacts,
    PromotionMode,
    RuntimeOperation,
    WbcRuntimeProducerFacade,
    WriterGuardError,
)
from arnold_pipelines.run_authority import CapabilityGrant, CoordinatorFence


TARGET = CustodyTargetKey("task", "T7", "dispatch", "task", "T7", "contract-T7")
CAPABILITY = "megaplan.task.dispatch"
GRANT = CapabilityGrant(
    grant_id="grant-T7",
    run_id="run-T7",
    run_revision="rev-T7",
    coordinator_attempt_id="coord-T7",
    fence_token=11,
    subject_ids=(TARGET.subject_id,),
    capabilities=(CAPABILITY,),
    evidence_ids=("evidence-1",),
)
FENCE = CoordinatorFence("run-T7", "rev-T7", "coord-T7", 11)


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


def _lease(*, epoch: int = 5, grant_id: str = GRANT.grant_id) -> CustodyLease:
    return CustodyLease(
        lease_id="lease-T7",
        target_key=TARGET,
        owner=("runtime-host", "4321", "boot-1"),
        epoch=epoch,
        acquired_at="2026-07-20T00:00:00+00:00",
        expires_at="2999-01-01T00:00:00+00:00",
        fence_token=str(FENCE.token),
        status="active",
        run_authority_grant_id=grant_id,
        wbc_attempt_reference="wbc-T7",
    )


def _record(*, version: str = "source.v1", grant_id: str = GRANT.grant_id) -> OutboxRecord:
    return OutboxRecord(
        outbox_id="outbox-T7",
        lease_id="lease-T7",
        record_type=OutboxRecordType.LEASE_ACQUIRE,
        status=OutboxRecordStatus.PENDING,
        occurred_at="2026-07-20T00:00:00+00:00",
        idempotency_key="idem-T7-outbox",
        wbc_attempt_reference="wbc-T7",
        run_authority_grant_id=grant_id,
        coordinator_fence_token=FENCE.token,
        custody_epoch=5,
        payload={
            "schema_version": version,
            "target_digest": TARGET.target_digest,
        },
    )


def _register_writer(*, writer_id: str = "runtime.writer", surface_name: str = "runtime.producer") -> None:
    register_writer(
        ControlledWriter(
            writer_id=writer_id,
            surface_name=surface_name,
            cohort=Cohort.ACTIVE,
            contract_ids=(TARGET.contract_id,),
            source_file="arnold_pipelines/megaplan/custody/wbc_runtime.py",
            function_name="WbcRuntimeProducerFacade",
            required_wbc_phases=("start", "terminal"),
            action_kind="dispatch",
        )
    )


def _context(action_type: str, *, wbc_reference: str = "wbc-T7") -> ActionBoundaryContext:
    return ActionBoundaryContext(
        action_type=action_type,  # type: ignore[arg-type]
        target=TARGET,
        run_authority_grant_id=GRANT.grant_id,
        coordinator_fence_token=FENCE.token,
        wbc_attempt_reference=wbc_reference,
        owner_host="runtime-host",
        owner_pid="4321",
        owner_boot_id="boot-1",
        expected_custody_epoch=5,
        expected_lease_id="lease-T7",
        run_authority_grant=GRANT,
        coordinator_fence=FENCE,
        required_capability=CAPABILITY,
        required_wbc_evidence_version="source.v1",
    )


def _identity(attempt_id: str) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-T7",
        run_id="run-T7",
        graph_revision="graph-T7",
        step_id="step-T7",
        invocation_id="inv-T7",
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
    payload: dict[str, object] | None = None,
) -> LedgerEvent:
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=_identity(attempt_id),
        provenance=AttemptProvenance(actor_id="actor-T7", tool_id="tool-T7"),
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
        payload=payload or {"sequence": sequence},
    )


def _artifacts(attempt_id: str) -> ImmutableAttemptArtifacts:
    return ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        artifacts=(
            AttemptArtifact(
                artifact_id="artifact-T7",
                artifact_kind="attempt_receipt",
                version="artifact.v1",
                locator="memory://artifact-T7",
                metadata={"sha256": "abc123"},
            ),
        ),
        metadata={"family": "common-dispatch"},
    )


def _facade(
    tmp_path: Path,
    *,
    promotion_mode: PromotionMode = PromotionMode.ACTION_OFF,
    rollback_validator=None,
) -> WbcRuntimeProducerFacade:
    store = SqliteAttemptLedgerStore(tmp_path / "attempt-ledger.sqlite3")
    return WbcRuntimeProducerFacade(
        store,
        source_lookup=lambda key: ExactSourceRecord(
            lookup_key=key,
            version="source.v1",
            source_uri="git+file:///repo#source.v1",
            observed_at="2026-07-20T00:00:00+00:00",
            metadata={"key": key},
        ),
        lease_store=FakeLeaseStore((_lease(),)),
        outbox=FakeOutbox((_record(),)),
        promotion_mode=promotion_mode,
        enforcement_enabled=True,
        rollback_validator=rollback_validator,
    )


def test_runtime_facade_reserve_start_complete_and_reread(tmp_path: Path) -> None:
    _register_writer()
    attempt_id = "11111111-1111-4111-8111-111111111111"
    artifacts = _artifacts(attempt_id)
    facade = _facade(tmp_path)

    reserve = facade.reserve_attempt(
        attempt_id=attempt_id,
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="dispatch:start",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    start = facade.start_attempt(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key="idem-start",
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="dispatch:start",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    complete = facade.complete_attempt(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-complete",
            outcome=AttemptOutcome.SUCCEEDED,
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="dispatch:complete",
        expected_source_version="source.v1",
        action_context=_context("completion"),
        artifacts=artifacts,
    )

    assert reserve.operation == RuntimeOperation.RESERVE
    assert start.authoritative_reread is not None
    assert start.authoritative_reread.started_gate is not None
    assert start.authoritative_reread.started_gate.status == GateStatus.VERIFIED
    assert complete.authoritative_reread is not None
    assert complete.authoritative_reread.terminal_gate is not None
    assert complete.authoritative_reread.terminal_gate.status == GateStatus.VERIFIED
    assert [event.sequence for event in complete.authoritative_reread.events] == [1, 2]
    runtime_payload = complete.authoritative_reread.events[-1].payload["__wbc_runtime__"]
    assert runtime_payload["source_record"]["version"] == "source.v1"
    assert runtime_payload["artifacts"]["artifacts"][0]["artifact_id"] == "artifact-T7"


def test_runtime_facade_blocks_stale_source_lookup_before_append(tmp_path: Path) -> None:
    _register_writer()
    attempt_id = "22222222-2222-4222-8222-222222222222"
    store = SqliteAttemptLedgerStore(tmp_path / "attempt-ledger.sqlite3")
    facade = WbcRuntimeProducerFacade(
        store,
        source_lookup=lambda key: ExactSourceRecord(lookup_key=key, version="source.v0"),
        lease_store=FakeLeaseStore((_lease(),)),
        outbox=FakeOutbox((_record(),)),
        enforcement_enabled=True,
    )

    with pytest.raises(ExactSourceLookupError, match="expected 'source.v1', observed 'source.v0'"):
        facade.start_attempt(
            attempt_id=attempt_id,
            event=_event(
                attempt_id=attempt_id,
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-start",
            ),
            writer_id="runtime.writer",
            surface_name="runtime.producer",
            source_lookup_key="dispatch:start",
            expected_source_version="source.v1",
            action_context=_context("dispatch"),
            artifacts=_artifacts(attempt_id),
        )

    assert store.read_events(attempt_id) == []


def test_runtime_facade_action_off_keeps_real_external_effects_suppressed(tmp_path: Path) -> None:
    _register_writer()
    attempt_id = "33333333-3333-4333-8333-333333333333"
    facade = _facade(tmp_path, promotion_mode=PromotionMode.ACTION_OFF)
    artifacts = _artifacts(attempt_id)
    facade.start_attempt(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key="idem-start",
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="effects:start",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    intent = facade.record_effect_intent(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
            idempotency_key="idem-intent",
            payload={"effect": "publish"},
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="effects:intent",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    observed: list[str] = []

    def _effect_executor(**_: object) -> None:
        observed.append("executed")

    outcome = facade.record_effect_outcome(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=3,
            event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            idempotency_key="idem-outcome",
            payload={"effect": "publish", "outcome": "shadow"},
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="effects:outcome",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
        effect_executor=_effect_executor,
        intent_event=intent.append_result.event if intent.append_result is not None else None,
    )

    assert observed == []
    assert not outcome.external_effect_executed
    assert outcome.diagnostics["effect_execution"] == "suppressed by action-off/observe mode"
    assert [event.event_type for event in outcome.authoritative_reread.events] == [
        AttemptEventType.STARTED,
        AttemptEventType.EXTERNAL_EFFECT_INTENT,
        AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
    ]


def test_runtime_facade_promote_mode_requires_verified_intent_reread(tmp_path: Path) -> None:
    _register_writer()
    attempt_id = "33333333-3333-4333-8333-333333333334"
    facade = _facade(tmp_path, promotion_mode=PromotionMode.PROMOTE)
    artifacts = _artifacts(attempt_id)
    facade.start_attempt(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key="idem-start",
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="effects:start",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    facade.record_effect_intent(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
            idempotency_key="idem-intent",
            payload={"effect": "publish"},
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="effects:intent",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    observed: list[str] = []

    def _effect_executor(**_: object) -> None:
        observed.append("executed")

    outcome = facade.record_effect_outcome(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=3,
            event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            idempotency_key="idem-outcome",
            payload={"effect": "publish", "outcome": "shadow"},
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="effects:outcome",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
        effect_executor=_effect_executor,
        intent_event=None,
    )

    assert observed == []
    assert outcome.promotion_mode == PromotionMode.ACTION_OFF
    assert outcome.external_effect_executed is False
    assert "missing authoritative reread" in outcome.diagnostics["effect_execution"]
    assert outcome.diagnostics["requested_promotion_mode"] == PromotionMode.PROMOTE.value
    assert outcome.append_result is not None
    runtime_payload = outcome.append_result.event.payload["__wbc_runtime__"]
    assert runtime_payload["promotion_mode"] == PromotionMode.ACTION_OFF.value


def test_runtime_facade_promote_mode_respects_rollback_enforcement(tmp_path: Path) -> None:
    _register_writer()
    attempt_id = "33333333-3333-4333-8333-333333333335"
    rollback_validation = validate_rollback_safety(
        exact_identity_gaps=("dispatch:start",),
        reread_gaps=("attempt:33333333-3333-4333-8333-333333333335",),
        owner_claims={"execute_approval": ("run_authority", "wbc")},
        historical_adapter_ids=("legacy-chain-state-reader",),
    )
    facade = _facade(
        tmp_path,
        promotion_mode=PromotionMode.PROMOTE,
        rollback_validator=lambda: rollback_validation,
    )
    artifacts = _artifacts(attempt_id)
    facade.start_attempt(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key="idem-start",
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="effects:start",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    intent = facade.record_effect_intent(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
            idempotency_key="idem-intent",
            payload={"effect": "publish"},
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="effects:intent",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    observed: list[str] = []

    def _effect_executor(**_: object) -> None:
        observed.append("executed")

    outcome = facade.record_effect_outcome(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=3,
            event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            idempotency_key="idem-outcome",
            payload={"effect": "publish", "outcome": "shadow"},
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="effects:outcome",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
        effect_executor=_effect_executor,
        intent_event=intent.append_result.event if intent.append_result is not None else None,
    )

    assert observed == []
    assert outcome.promotion_mode == PromotionMode.ACTION_OFF
    assert outcome.external_effect_executed is False
    assert outcome.rollback_validation is not None
    assert outcome.rollback_validation.safe is False
    assert outcome.rollback_validation.adopter_promotion_enabled is False
    assert outcome.rollback_validation.real_effects_enabled is False
    assert outcome.rollback_validation.exact_identity_gaps == ("dispatch:start",)
    assert outcome.rollback_validation.reread_gaps == (
        "attempt:33333333-3333-4333-8333-333333333335",
    )
    assert outcome.rollback_validation.non_unique_owner_conflicts == (
        "execute_approval:run_authority,wbc",
    )
    assert outcome.rollback_validation.historical_read_only_adapters == (
        "legacy-chain-state-reader",
    )
    assert "read-only historical adapters still active" in outcome.diagnostics["effect_execution"]


def test_runtime_facade_suspend_resume_retry_cancel_and_authoritative_reread(tmp_path: Path) -> None:
    _register_writer()
    attempt_id = "44444444-4444-4444-8444-444444444444"
    facade = _facade(tmp_path)
    artifacts = _artifacts(attempt_id)
    facade.start_attempt(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key="idem-start",
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="lifecycle:start",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    facade.suspend_attempt(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.SUSPENDED,
            idempotency_key="idem-suspend",
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="lifecycle:suspend",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    facade.resume_attempt(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=3,
            event_type=AttemptEventType.RESUMED,
            idempotency_key="idem-resume",
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="lifecycle:resume",
        expected_source_version="source.v1",
        action_context=_context("dispatch"),
        artifacts=artifacts,
    )
    facade.schedule_retry(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=4,
            event_type=AttemptEventType.RETRY_SCHEDULED,
            idempotency_key="idem-retry",
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="lifecycle:retry",
        expected_source_version="source.v1",
        action_context=_context("repair"),
        artifacts=artifacts,
    )
    cancelled = facade.cancel_attempt(
        attempt_id=attempt_id,
        event=_event(
            attempt_id=attempt_id,
            sequence=5,
            event_type=AttemptEventType.CANCELLED,
            idempotency_key="idem-cancel",
            outcome=AttemptOutcome.CANCELLED,
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="lifecycle:cancel",
        expected_source_version="source.v1",
        action_context=_context("cancellation"),
        artifacts=artifacts,
    )
    reread = facade.authoritative_reread(
        attempt_id=attempt_id,
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="lifecycle:reread",
        expected_source_version="source.v1",
        action_context=_context("cancellation"),
        verify_event=cancelled.append_result.event if cancelled.append_result is not None else None,
    )

    assert [event.sequence for event in reread.authoritative_reread.events] == [1, 2, 3, 4, 5]
    assert reread.authoritative_reread.terminal_gate is not None
    assert reread.authoritative_reread.terminal_gate.status == GateStatus.VERIFIED
    assert reread.authoritative_reread.verified_event is not None
    assert reread.authoritative_reread.verified_event.idempotency_key == "idem-cancel"


def test_runtime_facade_fails_closed_for_unregistered_writer(tmp_path: Path) -> None:
    facade = _facade(tmp_path)

    with pytest.raises(WriterGuardError, match="is not authorized"):
        facade.reserve_attempt(
            attempt_id="attempt-runtime-unregistered",
            writer_id="missing.writer",
            surface_name="runtime.producer",
            source_lookup_key="dispatch:start",
            expected_source_version="source.v1",
            action_context=_context("dispatch"),
        )
