from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from importlib.machinery import SourcelessFileLoader
from pathlib import Path
import sys
import textwrap
from types import ModuleType
from typing import Any

import pytest

_ATTEMPT_LEDGER_MODULE = "arnold.workflow.attempt_ledger_store"
_WRITER_REGISTRY_MODULE = "arnold_pipelines.megaplan.custody.controlled_writer_registry"


def _install_controlled_writer_registry_shim() -> None:
    existing = sys.modules.get(_WRITER_REGISTRY_MODULE)
    if existing is not None and hasattr(existing, "register_writer"):
        return

    class Cohort(StrEnum):
        ACTIVE = "active"
        SHADOW = "shadow"
        REPORT_ONLY = "report_only"

    class WriteGuardDecision(StrEnum):
        ALLOWED = "allowed"
        SHADOW_PASS = "shadow_pass"
        REPORT_ONLY = "report_only"
        DENIED = "denied"
        UNREGISTERED = "unregistered"

    @dataclass(frozen=True)
    class ControlledWriter:
        writer_id: str
        surface_name: str
        cohort: Cohort = Cohort.ACTIVE
        contract_ids: tuple[str, ...] = ()
        source_file: str = ""
        function_name: str = ""
        required_wbc_phases: tuple[str, ...] = ()
        action_kind: str = ""

    @dataclass(frozen=True)
    class WriteGuardResult:
        decision: WriteGuardDecision
        writer: ControlledWriter | None = None
        diagnostics: tuple[str, ...] = ()

        @property
        def allowed(self) -> bool:
            return self.decision == WriteGuardDecision.ALLOWED

        @property
        def denied(self) -> bool:
            return self.decision in {WriteGuardDecision.DENIED, WriteGuardDecision.UNREGISTERED}

    registry_by_id: dict[str, ControlledWriter] = {}

    def _clear_registry() -> None:
        registry_by_id.clear()

    def register_writer(writer: ControlledWriter) -> ControlledWriter:
        registry_by_id[writer.writer_id] = writer
        return writer

    def deregister_writer(writer_id: str) -> bool:
        return registry_by_id.pop(writer_id, None) is not None

    def get_writer(writer_id: str) -> ControlledWriter | None:
        return registry_by_id.get(writer_id)

    def get_writer_by_surface(surface_name: str) -> ControlledWriter | None:
        matches = [writer for writer in registry_by_id.values() if writer.surface_name == surface_name]
        if len(matches) != 1:
            return None
        return matches[0]

    def writer_guard(
        writer_id: str | None = None,
        *,
        surface_name: str | None = None,
        **_kwargs: Any,
    ) -> WriteGuardResult:
        writer = None
        if writer_id:
            writer = get_writer(writer_id)
        if writer is None and surface_name:
            writer = get_writer_by_surface(surface_name)
        if writer is None:
            return WriteGuardResult(WriteGuardDecision.UNREGISTERED)
        if writer.cohort == Cohort.ACTIVE:
            return WriteGuardResult(WriteGuardDecision.ALLOWED, writer=writer)
        if writer.cohort == Cohort.SHADOW:
            return WriteGuardResult(WriteGuardDecision.SHADOW_PASS, writer=writer)
        return WriteGuardResult(WriteGuardDecision.REPORT_ONLY, writer=writer)

    module = ModuleType(_WRITER_REGISTRY_MODULE)
    module.__dict__.update(
        {
            "COHORTS": tuple(item.value for item in Cohort),
            "WRITER_REGISTRY_SCHEMA_VERSION": 1,
            "WRITE_GUARD_DECISIONS": tuple(item.value for item in WriteGuardDecision),
            "Cohort": Cohort,
            "ControlledWriter": ControlledWriter,
            "WriteGuardDecision": WriteGuardDecision,
            "WriteGuardResult": WriteGuardResult,
            "_clear_registry": _clear_registry,
            "deregister_writer": deregister_writer,
            "get_writer": get_writer,
            "get_writer_by_surface": get_writer_by_surface,
            "guard_all": lambda *args, **kwargs: tuple(),
            "list_active_writers": lambda: tuple(
                writer for writer in registry_by_id.values() if writer.cohort == Cohort.ACTIVE
            ),
            "list_authority_increasing_writers": lambda: tuple(registry_by_id.values()),
            "list_report_only_writers": lambda: tuple(
                writer for writer in registry_by_id.values() if writer.cohort == Cohort.REPORT_ONLY
            ),
            "list_shadow_writers": lambda: tuple(
                writer for writer in registry_by_id.values() if writer.cohort == Cohort.SHADOW
            ),
            "list_writers": lambda: tuple(registry_by_id.values()),
            "register_writer": register_writer,
            "writer_guard": writer_guard,
        }
    )
    sys.modules[_WRITER_REGISTRY_MODULE] = module


_install_controlled_writer_registry_shim()


def _load_attempt_ledger_store_from_pyc() -> None:
    existing = sys.modules.get(_ATTEMPT_LEDGER_MODULE)
    if existing is not None and hasattr(existing, "SqliteAttemptLedgerStore"):
        return
    pyc_path = (
        Path(__file__).resolve().parents[2]
        / "arnold"
        / "workflow"
        / "__pycache__"
        / f"attempt_ledger_store.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc"
    )
    loader = SourcelessFileLoader(_ATTEMPT_LEDGER_MODULE, str(pyc_path))
    module = ModuleType(_ATTEMPT_LEDGER_MODULE)
    module.__file__ = str(pyc_path)
    module.__loader__ = loader
    module.__package__ = "arnold.workflow"
    sys.modules[_ATTEMPT_LEDGER_MODULE] = module
    code = loader.get_code(_ATTEMPT_LEDGER_MODULE)
    if code is None:
        raise ModuleNotFoundError(f"could not load recovered attempt ledger store module {pyc_path}")
    exec(code, module.__dict__)


_load_attempt_ledger_store_from_pyc()

from arnold.workflow.attempt_ledger_store import (
    GateStatus,
    PostTerminalAppendError,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.boundary_conformance import (
    ConformanceViolationKind,
    WorkflowBoundarySpec,
    verify_boundary_conformance,
)
from arnold.workflow.boundary_evidence import BoundaryContract
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
from arnold_pipelines.megaplan.cloud.repair_revalidation import revalidate_repair_target
from arnold_pipelines.megaplan.custody.action_validator import (
    ActionBoundaryContext,
    GateResult,
    validate_action_boundary,
)
from arnold_pipelines.megaplan.custody.controlled_writer_registry import (
    Cohort,
    ControlledWriter,
    _clear_registry,
    register_writer,
)
from arnold_pipelines.megaplan.custody.contracts import CustodyLease, CustodyTargetKey
from arnold_pipelines.megaplan.custody.fake_prep_to_plan_adapter import (
    FakePrepToPlanAdapter,
    FakePrepToPlanDispatchResult,
    PREP_TO_PLAN_SURFACE,
    PREP_TO_PLAN_WRITER_ID,
)
from arnold_pipelines.megaplan.custody.outbox import (
    OutboxRecord,
    OutboxRecordStatus,
    OutboxRecordType,
)
from arnold_pipelines.megaplan.custody.wbc_runtime import (
    ActionBoundaryDeniedError,
    AttemptArtifact,
    ExactSourceLookupError,
    ExactSourceRecord,
    ImmutableAttemptArtifacts,
    PromotionMode,
    WbcRuntimeProducerFacade,
)
from arnold_pipelines.megaplan.execute.aggregation import _build_aggregate_execution_payload
from arnold_pipelines.megaplan.execute.wbc import (
    EXECUTE_DISPATCH_WBC_KEY,
    EXECUTE_PARENT_CUSTODY_KEY,
    EXECUTE_TRANSITION_WBC_KEY,
)
from arnold_pipelines.megaplan.resident.managed_child_custody import (
    managed_child_delivery_projection,
)
from arnold_pipelines.megaplan.workflows.boundary_contracts import prep_to_plan
from arnold_pipelines.run_authority import CapabilityGrant, CoordinatorFence
from tools import generate_wbc_boundary_inventory as inventory_tool


RUNTIME_TARGET = CustodyTargetKey(
    "task",
    "T32-runtime",
    "dispatch",
    "task",
    "T32-runtime",
    "contract-T32-runtime",
)
RUNTIME_CAPABILITY = "megaplan.task.dispatch"
RUNTIME_GRANT = CapabilityGrant(
    grant_id="grant-T32-runtime",
    run_id="run-T32-runtime",
    run_revision="rev-T32-runtime",
    coordinator_attempt_id="coord-T32-runtime",
    fence_token=32,
    subject_ids=(RUNTIME_TARGET.subject_id,),
    capabilities=(RUNTIME_CAPABILITY,),
    evidence_ids=("evidence-T32-runtime",),
)
RUNTIME_FENCE = CoordinatorFence(
    "run-T32-runtime",
    "rev-T32-runtime",
    "coord-T32-runtime",
    32,
)

PREP_TARGET = CustodyTargetKey(
    "phase",
    "prep-phase",
    "dispatch",
    "boundary",
    prep_to_plan.boundary_id,
    prep_to_plan.boundary_id,
)
PREP_CAPABILITY = "megaplan.task.dispatch"
PREP_GRANT = CapabilityGrant(
    grant_id="grant-T32-prep",
    run_id="run-T32-prep",
    run_revision="rev-T32-prep",
    coordinator_attempt_id="coord-T32-prep",
    fence_token=12,
    subject_ids=(PREP_TARGET.subject_id,),
    capabilities=(PREP_CAPABILITY,),
    evidence_ids=("evidence-T32-prep",),
)
PREP_FENCE = CoordinatorFence("run-T32-prep", "rev-T32-prep", "coord-T32-prep", 12)


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


def _runtime_register_writer() -> None:
    register_writer(
        ControlledWriter(
            writer_id="runtime.writer",
            surface_name="runtime.producer",
            cohort=Cohort.ACTIVE,
            contract_ids=(RUNTIME_TARGET.contract_id,),
            source_file="tests/m8/test_wbc_acceptance_suites.py",
            function_name="test_runtime_acceptance_suite_proves_core_wbc_invariants",
            required_wbc_phases=("start", "terminal"),
            action_kind="dispatch",
        )
    )


def _prep_register_writer() -> None:
    register_writer(
        ControlledWriter(
            writer_id=PREP_TO_PLAN_WRITER_ID,
            surface_name=PREP_TO_PLAN_SURFACE,
            cohort=Cohort.ACTIVE,
            contract_ids=(prep_to_plan.boundary_id,),
            source_file="tests/m8/test_wbc_acceptance_suites.py",
            function_name="test_fake_adapter_acceptance_spike_requires_exact_identity",
            required_wbc_phases=("start", "terminal"),
            action_kind="dispatch",
        )
    )


def _runtime_lease(*, epoch: int = 5, grant_id: str = RUNTIME_GRANT.grant_id) -> CustodyLease:
    return CustodyLease(
        lease_id="lease-T32-runtime",
        target_key=RUNTIME_TARGET,
        owner=("runtime-host", "4321", "boot-1"),
        epoch=epoch,
        acquired_at="2026-07-20T00:00:00+00:00",
        expires_at="2999-01-01T00:00:00+00:00",
        fence_token=str(RUNTIME_FENCE.token),
        status="active",
        run_authority_grant_id=grant_id,
        wbc_attempt_reference="wbc-T32-runtime",
    )


def _runtime_record(*, version: str = "source.v1") -> OutboxRecord:
    return OutboxRecord(
        outbox_id="outbox-T32-runtime",
        lease_id="lease-T32-runtime",
        record_type=OutboxRecordType.LEASE_ACQUIRE,
        status=OutboxRecordStatus.PENDING,
        occurred_at="2026-07-20T00:00:00+00:00",
        idempotency_key="idem-T32-runtime-outbox",
        wbc_attempt_reference="wbc-T32-runtime",
        run_authority_grant_id=RUNTIME_GRANT.grant_id,
        coordinator_fence_token=RUNTIME_FENCE.token,
        custody_epoch=5,
        payload={"schema_version": version, "target_digest": RUNTIME_TARGET.target_digest},
    )


def _runtime_context(
    action_type: str,
    *,
    grant: CapabilityGrant | None = RUNTIME_GRANT,
    fence: CoordinatorFence | None = RUNTIME_FENCE,
    expected_epoch: int = 5,
    required_wbc_evidence_version: str = "source.v1",
) -> ActionBoundaryContext:
    return ActionBoundaryContext(
        action_type=action_type,  # type: ignore[arg-type]
        target=RUNTIME_TARGET,
        run_authority_grant_id=RUNTIME_GRANT.grant_id,
        coordinator_fence_token=RUNTIME_FENCE.token,
        wbc_attempt_reference="wbc-T32-runtime",
        owner_host="runtime-host",
        owner_pid="4321",
        owner_boot_id="boot-1",
        expected_custody_epoch=expected_epoch,
        expected_lease_id="lease-T32-runtime",
        run_authority_grant=grant,
        coordinator_fence=fence,
        required_capability=RUNTIME_CAPABILITY,
        required_wbc_evidence_version=required_wbc_evidence_version,
    )


def _runtime_identity(attempt_id: str) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-T32-runtime",
        run_id="run-T32-runtime",
        graph_revision="graph-T32-runtime",
        step_id="step-T32-runtime",
        invocation_id="inv-T32-runtime",
        attempt_ordinal=1,
        attempt_id=attempt_id,
    )


def _runtime_event(
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
        identity=_runtime_identity(attempt_id),
        provenance=AttemptProvenance(actor_id="actor-T32-runtime", tool_id="tool-T32-runtime"),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.MEGAPLAN_PHASE, adapter_version="1"),
        versions=VersionSet(
            code_version="source.v1",
            config_version="cfg.v1",
            template_version="tmpl.v1",
        ),
        grant_ref=GrantRef(grant_id=RUNTIME_GRANT.grant_id),
        sequence=sequence,
        causal_predecessor_sequence=max(sequence - 1, 0),
        append_position=sequence,
        occurred_at=f"2026-07-20T00:00:0{sequence}+00:00",
        observed_at=f"2026-07-20T00:00:0{sequence}+00:00",
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
        payload=payload or {"sequence": sequence},
    )


def _runtime_artifacts(attempt_id: str) -> ImmutableAttemptArtifacts:
    return ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        artifacts=(
            AttemptArtifact(
                artifact_id="artifact-T32-runtime",
                artifact_kind="attempt_receipt",
                version="artifact.v1",
                locator="memory://artifact-T32-runtime",
                metadata={"sha256": "abc123"},
            ),
        ),
        metadata={"family": "acceptance"},
    )


def _runtime_facade(
    tmp_path: Path,
    *,
    source_version: str = "source.v1",
    lease_store: FakeLeaseStore | None = None,
    outbox: FakeOutbox | None = None,
) -> tuple[SqliteAttemptLedgerStore, WbcRuntimeProducerFacade]:
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
        lease_store=lease_store or FakeLeaseStore((_runtime_lease(),)),
        outbox=outbox or FakeOutbox((_runtime_record(),)),
        promotion_mode=PromotionMode.ACTION_OFF,
        enforcement_enabled=True,
    )
    return store, facade


def _prep_lease(*, epoch: int = 5) -> CustodyLease:
    return CustodyLease(
        lease_id="lease-T32-prep",
        target_key=PREP_TARGET,
        owner=("runtime-host", "4321", "boot-1"),
        epoch=epoch,
        acquired_at="2026-07-20T00:00:00+00:00",
        expires_at="2999-01-01T00:00:00+00:00",
        fence_token=str(PREP_FENCE.token),
        status="active",
        run_authority_grant_id=PREP_GRANT.grant_id,
        wbc_attempt_reference="wbc-T32-prep",
    )


def _prep_record(*, version: str = "source.v1") -> OutboxRecord:
    return OutboxRecord(
        outbox_id="outbox-T32-prep",
        lease_id="lease-T32-prep",
        record_type=OutboxRecordType.LEASE_ACQUIRE,
        status=OutboxRecordStatus.PENDING,
        occurred_at="2026-07-20T00:00:00+00:00",
        idempotency_key="idem-T32-prep-outbox",
        wbc_attempt_reference="wbc-T32-prep",
        run_authority_grant_id=PREP_GRANT.grant_id,
        coordinator_fence_token=PREP_FENCE.token,
        custody_epoch=5,
        payload={"schema_version": version, "target_digest": PREP_TARGET.target_digest},
    )


def _prep_context(
    action_type: str,
    *,
    grant: CapabilityGrant | None = PREP_GRANT,
    fence: CoordinatorFence | None = PREP_FENCE,
    expected_epoch: int = 5,
) -> ActionBoundaryContext:
    return ActionBoundaryContext(
        action_type=action_type,  # type: ignore[arg-type]
        target=PREP_TARGET,
        run_authority_grant_id=PREP_GRANT.grant_id,
        coordinator_fence_token=PREP_FENCE.token,
        wbc_attempt_reference="wbc-T32-prep",
        owner_host="runtime-host",
        owner_pid="4321",
        owner_boot_id="boot-1",
        expected_custody_epoch=expected_epoch,
        expected_lease_id="lease-T32-prep",
        run_authority_grant=grant,
        coordinator_fence=fence,
        required_capability=PREP_CAPABILITY,
        required_wbc_evidence_version="source.v1",
    )


def _prep_event(
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
        identity=AttemptIdentity(
            workflow_id="wf-T32-prep",
            run_id="run-T32-prep",
            graph_revision="graph-T32-prep",
            step_id="prep",
            invocation_id="inv-T32-prep",
            attempt_ordinal=1,
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(actor_id="actor-T32-prep", tool_id="tool-T32-prep"),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.MEGAPLAN_PHASE, adapter_version="1"),
        versions=VersionSet(
            code_version="source.v1",
            config_version="cfg.v1",
            template_version="tmpl.v1",
        ),
        grant_ref=GrantRef(grant_id=PREP_GRANT.grant_id),
        sequence=sequence,
        causal_predecessor_sequence=max(sequence - 1, 0),
        append_position=sequence,
        occurred_at=f"2026-07-20T00:00:0{sequence}+00:00",
        observed_at=f"2026-07-20T00:00:0{sequence}+00:00",
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
        payload={"sequence": sequence, "boundary_id": prep_to_plan.boundary_id},
    )


def _prep_artifacts(attempt_id: str) -> ImmutableAttemptArtifacts:
    return ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        artifacts=(
            AttemptArtifact(
                artifact_id="artifact-T32-prep",
                artifact_kind="boundary_receipt",
                version="artifact.v1",
                locator="memory://artifact-T32-prep",
                metadata={"sha256": "def456"},
            ),
        ),
        metadata={"boundary_id": prep_to_plan.boundary_id},
    )


def _prep_facade(tmp_path: Path, *, source_version: str = "source.v1") -> tuple[SqliteAttemptLedgerStore, WbcRuntimeProducerFacade]:
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
        lease_store=FakeLeaseStore((_prep_lease(),)),
        outbox=FakeOutbox((_prep_record(),)),
        promotion_mode=PromotionMode.ACTION_OFF,
        enforcement_enabled=True,
    )
    return store, facade


def _module_scan_from_source(source: str, *, module_path: str = "synthetic/runtime_module.py") -> inventory_tool.ModuleScan:
    parsed = inventory_tool._parse_module_ast(textwrap.dedent(source))
    surface_types = tuple(
        inventory_tool._classify_module_surfaces(
            module_path,
            parsed["classes"],
            parsed["functions"],
            parsed["imports"],
            parsed["docstring"],
        )
    )
    return inventory_tool.ModuleScan(
        module_path=module_path,
        category="synthetic",
        owner=inventory_tool._owner_for_path(module_path),
        surface_types=surface_types,
        is_authority=inventory_tool._is_authority_surface(surface_types),
        classes=parsed["classes"],
        functions=parsed["functions"],
        imports=parsed["imports"],
        docstring_summary=parsed["docstring"],
        calls=parsed["calls"],
        try_scans=parsed["try_scans"],
        text_hits=parsed["text_hits"],
    )


def _boundary_contract(boundary_id: str, *, receipt_required: bool) -> BoundaryContract:
    return BoundaryContract(
        boundary_id=boundary_id,
        workflow_id="arnold.workflow",
        required_artifacts=(),
        expected_state_delta={"status": "done"},
        phase_result_required=False,
        receipt_required=receipt_required,
    )


def _batch_payload(boundary_id: str, attempt_id: str) -> dict[str, object]:
    return {
        "output": boundary_id,
        "commands_run": [f"pytest {boundary_id}"],
        "files_changed": [f"{boundary_id}.py"],
        "task_updates": [],
        "sense_check_acknowledgments": [],
        EXECUTE_DISPATCH_WBC_KEY: {
            "schema_version": 1,
            "attempt_id": attempt_id,
            "writer_id": "megaplan.execute.dispatch_wbc",
            "surface_name": "megaplan.execute.dispatch_wbc",
            "dispatch_id": f"dispatch:{attempt_id}",
            "plan_revision": "revision-1",
            "fence_token": 3,
            "prerequisite_digest": f"prereq:{attempt_id}",
            "worker_id": f"worker:{attempt_id}",
            "expected_source_version": f"source:{attempt_id}",
            "start_source_lookup_key": f"execute-batch:{attempt_id}:start",
            "terminal_source_lookup_key": f"execute-batch:{attempt_id}:complete",
            "verified_start_sequence": 1,
            "verified_terminal_sequence": 2,
            "verified_reread": True,
        },
        EXECUTE_TRANSITION_WBC_KEY: {
            "schema_version": 1,
            "dispatch_attempt_id": attempt_id,
            "dispatch_id": f"dispatch:{attempt_id}",
            "plan_revision": "revision-1",
            "fence_token": 3,
            "boundary_id": boundary_id,
            "receipt_path": f"boundary_receipts/{boundary_id}.json",
            "transition": "execute",
            "result": "success",
            "batch_number": 1,
            "batches_total": 1,
            "receipt_reread_verified": True,
        },
    }


def _repair_target(*, state: str = "gated", cursor: int = 20, pid: str = "200") -> dict[str, object]:
    return {
        "target_id": "session:plan",
        "plan_state": {"current_state": state, "fingerprint": f"plan-{state}"},
        "chain_state": {
            "current_plan_name": "plan",
            "last_state": state,
            "fingerprint": f"chain-{state}",
        },
        "event_cursors": {"line_count": cursor, "mtime": float(cursor)},
        "active_step_heartbeat": {
            "active": True,
            "phase": "finalize",
            "attempt": 1,
            "worker_pid": pid,
            "pid_live": True,
        },
        "tmux_process": {"session_live": True, "live_status": "alive"},
    }


def _repair_identity(*, attempt_number: int = 1, fence_token: str = "fence-1") -> dict[str, object]:
    return {
        "environment_id": "/workspace/demo",
        "session_id": "demo",
        "chain_id": "/workspace/demo/chain.yaml",
        "plan_revision": "sha256:plan-rev-1",
        "phase": "finalize",
        "task_id": "T32",
        "attempt_number": attempt_number,
        "failure_kind": "quality_gate_blocked",
        "blocker_digest": "blocker:v1:demo",
        "coordinator_fence_token": fence_token,
    }


def test_runtime_acceptance_suite_proves_core_wbc_invariants(tmp_path: Path) -> None:
    _runtime_register_writer()
    attempt_id = "32323232-3232-4232-8232-323232323232"
    store, facade = _runtime_facade(tmp_path)
    artifacts = _runtime_artifacts(attempt_id)

    facade.reserve_attempt(
        attempt_id=attempt_id,
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="dispatch:start",
        expected_source_version="source.v1",
        action_context=_runtime_context("dispatch"),
        artifacts=artifacts,
    )
    start = facade.start_attempt(
        attempt_id=attempt_id,
        event=_runtime_event(
            attempt_id=attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key="idem-start",
        ),
        writer_id="runtime.writer",
        surface_name="runtime.producer",
        source_lookup_key="dispatch:start",
        expected_source_version="source.v1",
        action_context=_runtime_context("dispatch"),
        artifacts=artifacts,
    )
    complete = facade.complete_attempt(
        attempt_id=attempt_id,
        event=_runtime_event(
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
        action_context=_runtime_context("completion"),
        artifacts=artifacts,
    )

    assert start.authoritative_reread is not None
    assert start.authoritative_reread.started_gate is not None
    assert start.authoritative_reread.started_gate.status == GateStatus.VERIFIED
    assert complete.authoritative_reread is not None
    assert complete.authoritative_reread.terminal_gate is not None
    assert complete.authoritative_reread.terminal_gate.status == GateStatus.VERIFIED
    assert [event.sequence for event in complete.authoritative_reread.events] == [1, 2]
    assert complete.append_result is not None
    assert complete.append_result.event.causal_predecessor_sequence == 1
    runtime_payload = complete.append_result.event.payload["__wbc_runtime__"]
    assert runtime_payload["source_record"]["version"] == "source.v1"
    assert runtime_payload["artifacts"]["artifacts"][0]["artifact_id"] == "artifact-T32-runtime"

    with pytest.raises(PostTerminalAppendError):
        facade.complete_attempt(
            attempt_id=attempt_id,
            event=_runtime_event(
                attempt_id=attempt_id,
                sequence=3,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="idem-complete-duplicate",
                outcome=AttemptOutcome.SUCCEEDED,
            ),
            writer_id="runtime.writer",
            surface_name="runtime.producer",
            source_lookup_key="dispatch:complete",
            expected_source_version="source.v1",
            action_context=_runtime_context("completion"),
            artifacts=artifacts,
        )

    stale_store, stale_facade = _runtime_facade(tmp_path / "stale", source_version="source.v0")
    with pytest.raises(ExactSourceLookupError, match="expected 'source.v1', observed 'source.v0'"):
        stale_facade.start_attempt(
            attempt_id="43434343-4343-4434-8434-434343434343",
            event=_runtime_event(
                attempt_id="43434343-4343-4434-8434-434343434343",
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-stale-start",
            ),
            writer_id="runtime.writer",
            surface_name="runtime.producer",
            source_lookup_key="dispatch:start",
            expected_source_version="source.v1",
            action_context=_runtime_context("dispatch"),
            artifacts=_runtime_artifacts("43434343-4343-4434-8434-434343434343"),
        )
    assert store.read_events(attempt_id)[-1].event_type == AttemptEventType.COMPLETED
    assert stale_store.read_events("43434343-4343-4434-8434-434343434343") == []


@pytest.mark.parametrize(
    ("case", "context", "lease_store", "outbox", "expected_gate"),
    [
        (
            "authorized",
            lambda: _runtime_context("dispatch"),
            lambda: FakeLeaseStore((_runtime_lease(),)),
            lambda: FakeOutbox((_runtime_record(),)),
            GateResult.AUTHORIZED,
        ),
        (
            "missing_grant",
            lambda: _runtime_context("dispatch", grant=None),
            lambda: FakeLeaseStore((_runtime_lease(),)),
            lambda: FakeOutbox((_runtime_record(),)),
            GateResult.BLOCKED_MISSING_GRANT,
        ),
        (
            "missing_fence",
            lambda: _runtime_context("dispatch", fence=None),
            lambda: FakeLeaseStore((_runtime_lease(),)),
            lambda: FakeOutbox((_runtime_record(),)),
            GateResult.BLOCKED_FENCE_MISMATCH,
        ),
        (
            "missing_lease",
            lambda: _runtime_context("dispatch"),
            lambda: FakeLeaseStore(()),
            lambda: FakeOutbox((_runtime_record(),)),
            GateResult.BLOCKED_NO_LEASE,
        ),
        (
            "stale_epoch",
            lambda: _runtime_context("dispatch", expected_epoch=4),
            lambda: FakeLeaseStore((_runtime_lease(epoch=5),)),
            lambda: FakeOutbox((_runtime_record(),)),
            GateResult.BLOCKED_STALE_EPOCH,
        ),
        (
            "version_mismatch",
            lambda: _runtime_context("dispatch", required_wbc_evidence_version="source.v2"),
            lambda: FakeLeaseStore((_runtime_lease(),)),
            lambda: FakeOutbox((_runtime_record(version="source.v1"),)),
            GateResult.BLOCKED_WBC_VERSION_MISMATCH,
        ),
    ],
)
def test_validator_acceptance_matrix_covers_grant_lease_gaps(
    case: str,
    context,
    lease_store,
    outbox,
    expected_gate: GateResult,
) -> None:
    result = validate_action_boundary(
        context(),
        lease_store=lease_store(),
        outbox=outbox(),
        enforcement_enabled=True,
    )

    assert result.gate_result == expected_gate, case


def test_fake_adapter_acceptance_spike_requires_exact_identity(tmp_path: Path) -> None:
    _prep_register_writer()
    attempt_id = "54545454-5454-4454-8454-545454545454"
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (plan_dir / "research.md").write_text("research\n", encoding="utf-8")
    (plan_dir / "brief.md").write_text("brief\n", encoding="utf-8")
    store, facade = _prep_facade(tmp_path / "positive")
    adapter = FakePrepToPlanAdapter(plan_dir=plan_dir, project_dir=project_dir, facade=facade)
    dispatched: list[str] = []

    def _dispatch(start_result):
        dispatched.append("called")
        assert start_result.authoritative_reread is not None
        assert start_result.authoritative_reread.started_gate is not None
        assert start_result.authoritative_reread.started_gate.status == GateStatus.VERIFIED
        assert [event.event_type for event in store.read_events(attempt_id)] == [AttemptEventType.STARTED]
        receipt = adapter.build_receipt(
            invocation_id="inv-T32-prep",
            details={"writer_id": PREP_TO_PLAN_WRITER_ID},
        )
        return FakePrepToPlanDispatchResult(receipt=receipt, user_payload={"dispatch": "plan"})

    result = adapter.run(
        attempt_id=attempt_id,
        start_event=_prep_event(
            attempt_id=attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key="idem-prep-start",
        ),
        complete_event=_prep_event(
            attempt_id=attempt_id,
            sequence=2,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-prep-complete",
            outcome=AttemptOutcome.SUCCEEDED,
        ),
        dispatch=_dispatch,
        start_action_context=_prep_context("dispatch"),
        completion_action_context=_prep_context("completion"),
        artifacts=_prep_artifacts(attempt_id),
    )

    assert dispatched == ["called"]
    assert result.complete.authoritative_reread is not None
    assert result.complete.authoritative_reread.terminal_gate is not None
    assert result.complete.authoritative_reread.terminal_gate.status == GateStatus.VERIFIED
    assert result.persisted_receipt["boundary_id"] == prep_to_plan.boundary_id

    stale_store, stale_facade = _prep_facade(tmp_path / "negative")
    stale_adapter = FakePrepToPlanAdapter(
        plan_dir=tmp_path / "negative-plan",
        project_dir=tmp_path / "negative-project",
        facade=stale_facade,
    )
    (tmp_path / "negative-plan").mkdir()
    (tmp_path / "negative-project").mkdir()
    invoked: list[str] = []

    def _should_not_run(_start_result):
        invoked.append("called")
        return FakePrepToPlanDispatchResult(
            receipt=stale_adapter.build_receipt(invocation_id="inv-T32-negative")
        )

    with pytest.raises(ValueError, match="does not match event attempt"):
        stale_adapter.run(
            attempt_id=attempt_id,
            start_event=_prep_event(
                attempt_id="99999999-9999-4999-8999-999999999999",
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-prep-mismatch",
            ),
            complete_event=_prep_event(
                attempt_id=attempt_id,
                sequence=2,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="idem-prep-negative-complete",
                outcome=AttemptOutcome.SUCCEEDED,
            ),
            dispatch=_should_not_run,
            start_action_context=_prep_context("dispatch"),
            completion_action_context=_prep_context("completion"),
            artifacts=_prep_artifacts(attempt_id),
        )

    assert invoked == []
    assert stale_store.read_events(attempt_id) == []

    with pytest.raises(ActionBoundaryDeniedError, match="blocked_missing_grant"):
        stale_adapter.run(
            attempt_id=attempt_id,
            start_event=_prep_event(
                attempt_id=attempt_id,
                sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="idem-prep-no-grant",
            ),
            complete_event=_prep_event(
                attempt_id=attempt_id,
                sequence=2,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="idem-prep-no-grant-complete",
                outcome=AttemptOutcome.SUCCEEDED,
            ),
            dispatch=_should_not_run,
            start_action_context=_prep_context("dispatch", grant=None),
            completion_action_context=_prep_context("completion"),
            artifacts=_prep_artifacts(attempt_id),
        )


def test_inventory_acceptance_suite_proves_bypass_detection_and_support_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    wrapper_path = repo_root / "wrappers" / "producer.sh"
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_path.write_text("python emit_boundary.py || true\n", encoding="utf-8")
    monkeypatch.setattr(inventory_tool, "REPO_ROOT", repo_root)
    scan = _module_scan_from_source(
        """
        def emit_required_wbc_write(runtime, plan_dir):
            try:
                runtime.append_event("attempt-started")
            except Exception:
                pass

            # warn-and-continue path
            runtime.append_event("warn-path")

            # best-effort append path
            runtime.append_event("best-effort-path")

            # emit without raising
            runtime.append_event("without-raising-path")

            expected_source_version = "HEAD"
            latest_state = load_chain_state(plan_dir)
            runtime.append_event("latest-source-path")
        """,
        module_path="synthetic/required_write.py",
    )
    candidates = inventory_tool._discover_bypass_candidates(
        [scan],
        [{"path": "wrappers/producer.sh"}],
    )
    candidate_types = {
        row["candidate_type"]
        for row in candidates
        if row["module_path"] in {"synthetic/required_write.py", "wrappers/producer.sh"}
    }
    assert candidate_types >= {
        "broad_exception",
        "warn_and_continue",
        "best_effort",
        "without_raising",
        "mutable_alias_overwrite",
        "implicit_latest_lookup",
        "shell_or_true",
    }

    support_row = {
        "boundary_id": "execute_batch_checkpoint",
        "declared_support_status": "supported",
        "producer_path": "arnold_pipelines/megaplan/execute/batch.py",
        "exception_metadata": {
            "implementation_commit": "abc123",
            "positive_test": "tests/m8/test_wbc_acceptance_suites.py",
            "negative_bypass_test": "tests/m8/test_wbc_acceptance_suites.py",
        },
    }
    supported_gate = inventory_tool._build_support_gate(
        boundary_rows=[{"boundary_id": "execute_batch_checkpoint"}],
        producer_call_sites=[{"boundary_ids": ["execute_batch_checkpoint"]}],
        writer_registrations=[{"boundary_ids": ["execute_batch_checkpoint"]}],
        runtime_trace_digests=[{"boundary_ids": ["execute_batch_checkpoint"]}],
    )
    supported_status, supported_verification = inventory_tool._compute_manifest_support_status(
        support_row,
        support_gate=supported_gate,
        bypass_candidates=[],
    )
    assert supported_status == "supported"
    assert supported_verification["evidence_flags"]["exact_set_equality"] is True

    degraded_status, degraded_verification = inventory_tool._compute_manifest_support_status(
        {**support_row, "exception_metadata": {}},
        support_gate=inventory_tool._build_support_gate(
            boundary_rows=[{"boundary_id": "execute_batch_checkpoint"}],
            producer_call_sites=[{"boundary_ids": ["execute_batch_checkpoint"]}],
            writer_registrations=[],
            runtime_trace_digests=[],
        ),
        bypass_candidates=[],
    )
    assert degraded_status == "partial"
    assert "implementation commit" in degraded_verification["missing_requirements"]
    assert "exact declaration/static/writer/runtime set equality" in degraded_verification["missing_requirements"]


def test_boundary_parent_custody_and_receipt_acceptance_suite() -> None:
    optional_spec = WorkflowBoundarySpec(
        boundary_id="b.optional",
        contract=_boundary_contract("b.optional", receipt_required=False),
        receipt=None,
    )
    optional_result = verify_boundary_conformance("arnold.workflow", {"b.optional": optional_spec})
    assert optional_result.conformant is True

    required_spec = WorkflowBoundarySpec(
        boundary_id="b.required",
        contract=_boundary_contract("b.required", receipt_required=True),
        receipt=None,
    )
    required_result = verify_boundary_conformance("arnold.workflow", {"b.required": required_spec})
    assert ConformanceViolationKind.RECEIPT_REQUIRED_BUT_MISSING in {
        violation.kind for violation in required_result.violations
    }

    conflict_free = _build_aggregate_execution_payload(
        [_batch_payload("execute_batch_checkpoint", "attempt-ok")],
        completed_batches=1,
        total_batches=1,
        mode="code",
    )
    assert conflict_free["execute_wbc"]["all_dispatch_verified"] is True
    assert conflict_free["execute_wbc"]["all_transition_verified"] is True

    payload = _batch_payload("execute_aggregate_promotion", "attempt-conflict")
    payload[EXECUTE_PARENT_CUSTODY_KEY] = {
        "accepted_subject_ids": ["attempt-conflict"],
        "active_repair_subject_ids": ["attempt-conflict"],
    }
    conflicted = _build_aggregate_execution_payload(
        [payload],
        completed_batches=1,
        total_batches=1,
        mode="code",
    )
    assert conflicted[EXECUTE_PARENT_CUSTODY_KEY]["conflict_free"] is False
    assert any("execute parent custody conflict" in issue for issue in conflicted["deviations"])

    delivery_projection = managed_child_delivery_projection(
        {
            "run_id": "child-run",
            "aggregation": {
                "key": "agg-1",
                "role": "worker_child",
                "delivery_owner_run_id": "parent-run",
                "delivery_target_source_record_id": "src-parent",
            },
            "completion_delivery": {
                "status": "suppressed",
                "reply_target": {"source_record_id": "src-reply"},
            },
        }
    )
    assert delivery_projection["delivery_owner_run_id"] == "parent-run"
    assert delivery_projection["parent_owned_delivery"] is True


def test_repair_acceptance_suite_quarantines_identity_gaps() -> None:
    before = _repair_target()
    after = _repair_target()
    before["repair_identity"] = _repair_identity(attempt_number=1, fence_token="fence-1")
    after["repair_identity"] = _repair_identity(attempt_number=2, fence_token="fence-2")

    mismatched = revalidate_repair_target(before, after, session_health="alive")
    assert mismatched.repair_receipt_quarantined is True
    assert mismatched.recovery_verified is False
    assert mismatched.superseded is True

    after_same = _repair_target()
    after_same["repair_identity"] = _repair_identity(attempt_number=1, fence_token="fence-1")
    matched = revalidate_repair_target(before, after_same, session_health="alive")
    assert matched.repair_receipt_quarantined is False
    assert matched.recovery_verified is True
