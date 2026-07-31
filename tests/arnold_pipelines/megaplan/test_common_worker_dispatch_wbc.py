from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from arnold_pipelines.megaplan.custody.common_worker_dispatch import (
    COMMON_WORKER_DISPATCH_SURFACE,
    COMMON_WORKER_DISPATCH_WRITER_ID,
    CommonWorkerDispatchSpec,
    PostLaunchIndeterminateError,
)
from arnold_pipelines.megaplan.custody.controlled_writer_registry import Cohort, ControlledWriter, _clear_registry, register_writer
from arnold_pipelines.megaplan.custody.phase_wbc import activate_phase_wbc
from arnold_pipelines.megaplan.custody.worker_dispatch_wbc import build_worker_dispatch_spec
from arnold_pipelines.megaplan.custody.contracts import CustodyLease, CustodyTargetKey
from arnold_pipelines.megaplan.custody.outbox import OutboxRecord, OutboxRecordStatus, OutboxRecordType
from arnold_pipelines.megaplan.custody.wbc_runtime import (
    ActionBoundaryDeniedError,
    AttemptArtifact,
    ExactSourceRecord,
    ExactSourceLookupError,
    ImmutableAttemptArtifacts,
    PromotionMode,
    WbcRuntimeProducerFacade,
)
from arnold_pipelines.megaplan.handlers import shared as shared_handlers
from arnold_pipelines.megaplan.workers import _impl as worker_impl
from arnold_pipelines.run_authority import CapabilityGrant, CoordinatorFence


TARGET = CustodyTargetKey("phase", "plan", "dispatch", "worker", "common", "common-dispatch")
CAPABILITY = "megaplan.task.dispatch"
GRANT = CapabilityGrant(
    grant_id="grant-T13",
    run_id="run-T13",
    run_revision="rev-T13",
    coordinator_attempt_id="coord-T13",
    fence_token=9,
    subject_ids=(TARGET.subject_id,),
    capabilities=(CAPABILITY,),
    evidence_ids=("evidence-T13",),
)
FENCE = CoordinatorFence("run-T13", "rev-T13", "coord-T13", 9)


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
            writer_id=COMMON_WORKER_DISPATCH_WRITER_ID,
            surface_name=COMMON_WORKER_DISPATCH_SURFACE,
            cohort=Cohort.ACTIVE,
            contract_ids=(TARGET.contract_id,),
            source_file="arnold_pipelines/megaplan/workers/_impl.py",
            function_name="run_step_with_worker",
            required_wbc_phases=("start", "terminal"),
            action_kind="dispatch",
        )
    )


def _lease(*, epoch: int = 5, grant_id: str = GRANT.grant_id) -> CustodyLease:
    return CustodyLease(
        lease_id="lease-T13",
        target_key=TARGET,
        owner=("runtime-host", "4321", "boot-1"),
        epoch=epoch,
        acquired_at="2026-07-20T00:00:00+00:00",
        expires_at="2999-01-01T00:00:00+00:00",
        fence_token=str(FENCE.token),
        status="active",
        run_authority_grant_id=grant_id,
        wbc_attempt_reference="wbc-T13",
    )


def _record(*, version: str = "source.v1", grant_id: str = GRANT.grant_id) -> OutboxRecord:
    return OutboxRecord(
        outbox_id="outbox-T13",
        lease_id="lease-T13",
        record_type=OutboxRecordType.LEASE_ACQUIRE,
        status=OutboxRecordStatus.PENDING,
        occurred_at="2026-07-20T00:00:00+00:00",
        idempotency_key="idem-T13-outbox",
        wbc_attempt_reference="wbc-T13",
        run_authority_grant_id=grant_id,
        coordinator_fence_token=FENCE.token,
        custody_epoch=5,
        payload={"schema_version": version, "target_digest": TARGET.target_digest},
    )


def _context(
    action_type: str,
    *,
    grant: CapabilityGrant | None = GRANT,
    fence: CoordinatorFence | None = FENCE,
    expected_epoch: int = 5,
    lease_id: str = "lease-T13",
    wbc_reference: str = "wbc-T13",
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


def _identity(attempt_id: str) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-T13",
        run_id="run-T13",
        graph_revision="graph-T13",
        step_id="plan",
        invocation_id="inv-T13",
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
        provenance=AttemptProvenance(actor_id="actor-T13", tool_id="tool-T13"),
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
                artifact_id="artifact-T13",
                artifact_kind="dispatch",
                version="artifact.v1",
                locator="memory://artifact-T13",
                metadata={"family": "common-dispatch"},
            ),
        ),
        metadata={"family": "common-dispatch"},
    )


def _facade(tmp_path: Path) -> tuple[SqliteAttemptLedgerStore, WbcRuntimeProducerFacade]:
    store = SqliteAttemptLedgerStore(tmp_path / "attempt-ledger.sqlite3")
    facade = WbcRuntimeProducerFacade(
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
        promotion_mode=PromotionMode.ACTION_OFF,
        enforcement_enabled=True,
    )
    return store, facade


def _worker() -> worker_impl.WorkerResult:
    return worker_impl.WorkerResult(
        payload={"success": True},
        raw_output="ok",
        duration_ms=12,
        cost_usd=0.0,
        session_id="session-T13",
        worker_channel="codex_cli",
    )


def _spec(
    facade: WbcRuntimeProducerFacade,
    attempt_id: str,
    *,
    start_context: ActionBoundaryContext | None = None,
    success_context: ActionBoundaryContext | None = None,
    failure_context: ActionBoundaryContext | None = None,
    certificate: Any = None,
) -> CommonWorkerDispatchSpec:
    return CommonWorkerDispatchSpec(
        facade=facade,
        attempt_id=attempt_id,
        start_event=_event(
            attempt_id=attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key=f"{attempt_id}:start",
        ),
        success_event_factory=lambda _result: _event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key=f"{attempt_id}:complete",
            outcome=AttemptOutcome.SUCCEEDED,
            payload={"phase": "plan", "status": "completed"},
        ),
        failure_event_factory=lambda exc: _event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.FAILED,
            idempotency_key=f"{attempt_id}:failed",
            outcome=AttemptOutcome.FAILED,
            payload={"detail": str(exc)},
        ),
        indeterminate_event_factory=lambda exc: _event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.FAILED,
            idempotency_key=f"{attempt_id}:indeterminate",
            outcome=AttemptOutcome.INDETERMINATE,
            payload={"detail": str(exc), "indeterminate": True},
        ),
        start_action_context=start_context or _context("dispatch"),
        success_action_context=success_context or _context("completion"),
        failure_action_context=failure_context or _context("completion"),
        artifacts=_artifacts(attempt_id),
        post_dispatch_certificate=certificate,
    )


def test_run_step_with_worker_commits_wbc_start_before_provider_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _register_writer()
    attempt_id = "13131313-1313-4313-8313-131313131313"
    store, facade = _facade(tmp_path)
    seen = {"called": 0}

    def fake_legacy(*args: Any, **kwargs: Any) -> tuple[worker_impl.WorkerResult, str, str, bool]:
        del args, kwargs
        seen["called"] += 1
        events = store.read_events(attempt_id)
        assert [event.event_type for event in events] == [AttemptEventType.STARTED]
        assert store.start_verified(attempt_id).status == GateStatus.VERIFIED
        return _worker(), "codex", "persistent", False

    monkeypatch.setattr(worker_impl, "_run_step_with_worker_legacy", fake_legacy)
    worker, agent, mode, refreshed = worker_impl.run_step_with_worker(
        "plan",
        {},
        tmp_path,
        argparse.Namespace(),
        root=tmp_path,
        wbc_dispatch=_spec(facade, attempt_id),
    )

    assert seen["called"] == 1
    assert (agent, mode, refreshed) == ("codex", "persistent", False)
    assert worker.auth_metadata is not None
    assert worker.auth_metadata["wbc_dispatch"]["start_event_sequence"] == 1
    assert worker.auth_metadata["wbc_dispatch"]["terminal_event_sequence"] == 2
    assert [event.event_type for event in store.read_events(attempt_id)] == [
        AttemptEventType.STARTED,
        AttemptEventType.COMPLETED,
    ]
    assert store.terminal_or_indeterminate_verified(attempt_id).status == GateStatus.VERIFIED


def test_run_step_with_worker_blocks_before_dispatch_when_action_validator_denies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _register_writer()
    attempt_id = "14141414-1414-4414-8414-141414141414"
    store, facade = _facade(tmp_path)
    called = {"legacy": False}

    def fake_legacy(*args: Any, **kwargs: Any) -> tuple[worker_impl.WorkerResult, str, str, bool]:
        del args, kwargs
        called["legacy"] = True
        return _worker(), "codex", "persistent", False

    monkeypatch.setattr(worker_impl, "_run_step_with_worker_legacy", fake_legacy)

    with pytest.raises(ActionBoundaryDeniedError):
        worker_impl.run_step_with_worker(
            "plan",
            {},
            tmp_path,
            argparse.Namespace(),
            root=tmp_path,
            wbc_dispatch=_spec(facade, attempt_id, start_context=_context("dispatch", grant=None)),
        )

    assert not called["legacy"]
    assert store.read_events(attempt_id) == []


def test_run_step_with_worker_records_indeterminate_terminal_when_post_launch_certification_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_writer()
    attempt_id = "15151515-1515-4515-8515-151515151515"
    store, facade = _facade(tmp_path)

    def fake_legacy(*args: Any, **kwargs: Any) -> tuple[worker_impl.WorkerResult, str, str, bool]:
        del args, kwargs
        return _worker(), "codex", "persistent", False

    monkeypatch.setattr(worker_impl, "_run_step_with_worker_legacy", fake_legacy)

    with pytest.raises(PostLaunchIndeterminateError) as caught:
        worker_impl.run_step_with_worker(
            "plan",
            {},
            tmp_path,
            argparse.Namespace(),
            root=tmp_path,
            wbc_dispatch=_spec(
                facade,
                attempt_id,
                certificate=lambda _result: (_ for _ in ()).throw(RuntimeError("receipt append unavailable")),
            ),
        )

    assert caught.value.terminal_result.authoritative_reread is not None
    assert caught.value.terminal_result.authoritative_reread.terminal_gate is not None
    assert caught.value.terminal_result.authoritative_reread.terminal_gate.status == GateStatus.VERIFIED
    events = store.read_events(attempt_id)
    assert [event.event_type for event in events] == [AttemptEventType.STARTED, AttemptEventType.FAILED]
    assert events[-1].outcome == AttemptOutcome.INDETERMINATE


def test_run_worker_passes_wbc_dispatch_to_run_step_with_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _register_writer()
    _store, facade = _facade(tmp_path)
    dispatch_spec = _spec(facade, "16161616-1616-4616-8616-161616161616")
    captured: dict[str, Any] = {}

    @contextmanager
    def fake_phase_result_guard(_plan_dir: Path):
        yield

    def fake_run_step_with_worker(*args: Any, **kwargs: Any) -> tuple[worker_impl.WorkerResult, str, str, bool]:
        captured["wbc_dispatch"] = kwargs.get("wbc_dispatch")
        return _worker(), "codex", "persistent", False

    def fake_set_active_step(current_state: dict[str, Any], *args: Any, **kwargs: Any) -> str:
        del args, kwargs
        current_state["active_step"] = {"run_id": "run-T13"}
        return "run-T13"

    monkeypatch.setattr(shared_handlers, "apply_profile_expansion", lambda *args, **kwargs: None)
    monkeypatch.setattr(shared_handlers, "set_active_step", fake_set_active_step)
    monkeypatch.setattr(shared_handlers, "save_state_merge_meta", lambda *args, **kwargs: None)
    monkeypatch.setattr(shared_handlers, "phase_result_guard", fake_phase_result_guard)
    monkeypatch.setattr(shared_handlers.worker_module, "run_step_with_worker", fake_run_step_with_worker)

    state = {
        "config": {"project_dir": str(tmp_path)},
        "meta": {"current_invocation_id": "inv-T13"},
        "name": "plan-T13",
        "iteration": 1,
    }
    worker, agent, mode, refreshed = shared_handlers._run_worker(
        "plan",
        state,  # type: ignore[arg-type]
        tmp_path,
        argparse.Namespace(),
        root=tmp_path,
        resolved=("codex", "persistent", False, "gpt-5.5"),
        wbc_dispatch=dispatch_spec,
    )

    assert captured["wbc_dispatch"] is dispatch_spec
    assert (worker.session_id, agent, mode, refreshed) == ("session-T13", "codex", "persistent", False)


def test_auto_phase_worker_dispatch_rejects_stale_exact_source_before_provider_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "name": "plan-T18",
        "iteration": 2,
        "config": {"project_dir": str(tmp_path)},
        "meta": {"current_invocation_id": "inv-T18"},
        "active_step": {"run_id": "run-T18"},
    }
    activate_phase_wbc(
        state=state,  # type: ignore[arg-type]
        plan_dir=tmp_path,
        step="review",
        agent="reviewer",
    )
    spec = build_worker_dispatch_spec(
        plan_dir=tmp_path,
        state=state,  # type: ignore[arg-type]
        step="critique_evaluator",
        phase_step="review",
        agent="claude",
        selected_spec="claude:claude-sonnet-4-6:high",
        route_kind="subprocess",
        attempt_index=1,
        configured_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        attempted_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        failed_attempt_reasons=("availability",),
        fallback_trigger="availability",
    )
    assert spec is not None

    state["meta"]["current_invocation_id"] = "inv-T18-stale"
    state["active_step"].pop("_phase_wbc", None)
    activate_phase_wbc(
        state=state,  # type: ignore[arg-type]
        plan_dir=tmp_path,
        step="review",
        agent="reviewer",
    )
    called = {"dispatch": False}

    def _dispatch(_start: Any) -> worker_impl.WorkerResult:
        called["dispatch"] = True
        return _worker()

    with pytest.raises(ExactSourceLookupError):
        spec.run(_dispatch)

    assert not called["dispatch"]


def test_run_step_with_worker_enriches_wbc_metadata_with_worker_and_fallback_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "name": "plan-T18",
        "iteration": 3,
        "config": {"project_dir": str(tmp_path)},
        "meta": {"current_invocation_id": "inv-T18-meta"},
        "active_step": {"run_id": "run-T18-meta"},
    }
    activate_phase_wbc(
        state=state,  # type: ignore[arg-type]
        plan_dir=tmp_path,
        step="review",
        agent="reviewer",
    )
    spec = build_worker_dispatch_spec(
        plan_dir=tmp_path,
        state=state,  # type: ignore[arg-type]
        step="review",
        agent="claude",
        selected_spec="claude:claude-sonnet-4-6:high",
        route_kind="direct",
        attempt_index=1,
        configured_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        attempted_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        failed_attempt_reasons=("availability",),
        fallback_trigger="availability",
    )
    assert spec is not None

    def fake_legacy(*args: Any, **kwargs: Any) -> tuple[worker_impl.WorkerResult, str, str, bool]:
        del args, kwargs
        worker = _worker()
        worker.worker_channel = "shannon_stream"
        worker.auth_channel = "api_key"
        worker.auth_metadata = {
            "worker_channel": "shannon_stream",
            "auth_channel": "api_key",
            "session_strategy": "clear",
        }
        return worker, "claude", "persistent", True

    monkeypatch.setattr(worker_impl, "_run_step_with_worker_legacy", fake_legacy)
    worker, _agent, _mode, _refreshed = worker_impl.run_step_with_worker(
        "review",
        state,  # type: ignore[arg-type]
        tmp_path,
        argparse.Namespace(),
        root=tmp_path,
        wbc_dispatch=spec,
        ledger_configured_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        ledger_attempt_index=1,
        ledger_attempted_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        ledger_failed_attempt_reasons=("availability",),
        ledger_fallback_trigger="availability",
    )

    assert worker.auth_metadata is not None
    evidence = worker.auth_metadata["wbc_dispatch"]
    assert evidence["expected_source_version"].endswith(":direct:review:claude:claude-sonnet-4-6:high:1")
    assert evidence["route_kind"] == "direct"
    assert evidence["selected_spec"] == "claude:claude-sonnet-4-6:high"
    assert evidence["configured_specs"] == ["codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"]
    assert evidence["failed_attempt_reasons"] == ["availability"]
    assert evidence["fallback_trigger"] == "availability"
    assert evidence["worker_channel"] == "shannon_stream"
    assert evidence["auth_channel"] == "api_key"
