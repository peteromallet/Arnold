"""Backend protocol and journal-backed execution backend for manifests."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Protocol

from arnold.kernel import (
    BudgetRelease,
    BudgetReservation,
    BudgetSettlement,
    BudgetExceeded,
    ControlBinding,
    ControlTarget,
    ControlTransition,
    EffectDescriptor,
    EffectKind,
    EventEnvelope,
    EventFamily,
    FileBackedArtifactStore,
    GeneratedArtifactProvenance,
    GovernorBudget,
    GovernorState,
    ManifestReference,
    NDJsonEventJournal,
    ReplayReference,
    fold_effect_ledger,
    fold_governor_state,
    fulfillment_payload,
    intent_payload,
    node_budget_policy,
    release_payload,
    require_idempotency_policy,
    reservation_payload,
    settlement_payload,
    workflow_identity_from_manifest,
)
from arnold.kernel.artifacts import ArtifactBinding, ProvenanceParent
from arnold.kernel.effect_ledger import derive_effect_idempotency_key
from arnold.manifest import (
    CompensationPolicy,
    ControlTransitionSlot,
    EscalationPolicy,
    ManifestCursor,
    TopologyOverlaySlot,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
)

from arnold.execution.compensation import (
    CompensationStep,
    build_compensation_steps,
    compensation_already_started,
    compensation_completed_payload,
    compensation_policy_for_node,
    compensation_run_idempotency_key,
    compensation_scope_stack,
    compensation_started_payload,
    compensation_step_payload,
)
from arnold.execution.escalation import (
    escalation_already_routed,
    escalation_policy_for_node,
    escalation_routed_payload,
    should_escalate,
)
from arnold.execution.topology import (
    collect_declared_overlays,
    collect_declared_transitions,
    control_transition_from_projection,
    dispatch_control_transition,
    dispatch_topology_overlay,
    project_control_transitions,
)
from arnold.execution.observability import (
    ExecutionLogger,
    build_health_snapshot,
    build_progress_report,
    routing_snapshot,
    snapshot_to_dict,
)
from arnold.execution.registries import ExecutionRegistries
from arnold.execution.result import ExecutionDiagnostic, ExecutionResult, ExecutionState
from arnold.execution.routing import project_routing_state
from arnold.execution.state import RouteCoordinate, RoutingState
from arnold.execution.state_store import (
    BudgetSnapshot,
    FileStateStore,
    JournalPointer,
    RoutingSnapshot,
    RunCheckpoint,
    StateStore,
)
from arnold.workflow.native_wbc import begin_native_wbc_attempt


class ExecutionBackend(Protocol):
    """Backend seam used by :func:`arnold.execution.run`."""

    def run_manifest(
        self,
        manifest: WorkflowManifest,
        *,
        artifact_root: Path,
        registries: ExecutionRegistries,
        resume_cursor: ManifestCursor | None = None,
        state_store: StateStore | None = None,
        logger: ExecutionLogger | None = None,
    ) -> ExecutionResult:
        """Run or resume a compiled workflow manifest."""


class SkeletalBackend:
    """Minimal backend that returns a completed result without executing nodes."""

    def run_manifest(
        self,
        manifest: WorkflowManifest,
        *,
        artifact_root: Path,
        registries: ExecutionRegistries,
        resume_cursor: ManifestCursor | None = None,
        state_store: StateStore | None = None,
        logger: ExecutionLogger | None = None,
    ) -> ExecutionResult:
        del registries, state_store, logger
        return ExecutionResult(
            state=ExecutionState.COMPLETED,
            manifest_id=manifest.id,
            manifest_hash=manifest.manifest_hash or "",
            artifact_root=artifact_root,
            resume_cursor=resume_cursor,
        )


class NodeState(StrEnum):
    """Possible per-coordinate execution outcomes."""

    COMPLETED = "completed"
    FAILED = "failed"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class ArtifactSpec:
    """Artifact to be written by the backend during node execution."""

    artifact_id: str
    content: bytes
    content_type_id: str
    extension: str
    provenance: GeneratedArtifactProvenance | None = None


@dataclass
class NodeOutcome:
    """Outcome returned by backend node-execution hooks."""

    state: NodeState = NodeState.COMPLETED
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    branch_edge_id: str | None = None
    suspension_route_id: str | None = None
    artifacts: tuple[ArtifactSpec, ...] = ();
    actual_cost: float = 0.0
    actual_seconds: float = 0.0
    actual_tokens: int = 0
    control_signals: tuple[Mapping[str, Any] | ControlTransition, ...] = ()


@dataclass
class ExecutionContext:
    """Context passed to backend execution hooks."""

    coordinate: RouteCoordinate
    scope_stack: tuple[str, ...]
    outputs: Mapping[RouteCoordinate, Mapping[str, Any]]
    resume_payload: Mapping[str, Any] = field(default_factory=dict)


class LocalJournalBackend:
    """Journal-backed backend that executes manifests through the backend seam.

    The runner loop is product-neutral: it derives runnable state from the
    manifest plus journal events, calls overridable hooks for concrete behavior,
    and records every lifecycle event to the append-only NDJSON journal.
    """

    def __init__(
        self,
        *,
        run_id: str | None = None,
        reentry_id: str | None = None,
        init_ts: datetime | None = None,
        resume_payload: Mapping[str, Any] | None = None,
        initial_scope_stack: tuple[str, ...] | None = None,
        state_store: StateStore | None = None,
        logger: ExecutionLogger | None = None,
    ) -> None:
        self._external_run_id = run_id
        self._external_reentry_id = reentry_id
        self._external_init_ts = init_ts
        self._resume_payload = dict(resume_payload or {})
        self._initial_scope_stack = initial_scope_stack
        self._state_store = state_store
        self._logger = logger or ExecutionLogger()
        self._wbc_attempt = None

    # ------------------------------------------------------------------
    # Pluggable hooks (subclass-friendly)
    # ------------------------------------------------------------------

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _monotonic(self) -> float:
        return time.monotonic()

    def _create_artifact_store(self, root: Path) -> FileBackedArtifactStore:
        return FileBackedArtifactStore(root)

    def _make_run_id(self) -> str:
        if self._external_run_id:
            return self._external_run_id
        return "run:" + uuid.uuid4().hex

    def _make_reentry_id(self) -> str | None:
        return self._external_reentry_id

    def _check_authority(self, action: str, evidence: Mapping[str, Any]) -> bool:
        """Verify authority for a mutation-boundary action.

        Returns True when no authority requirement is registered for the
        action. Subclasses may override to inject test evidence.
        """

        manifest = self._manifest
        requirements = (manifest.policy.authority if manifest.policy else None) or ()
        for req in requirements:
            if req.action != action:
                continue
            if not self._registries.authorities.has(req.authority_id):
                return False
            if not self._registries.authorities.verify(
                req.authority_id,
                action=action,
                evidence=dict(evidence),
                context={"run_id": self._run_id, "manifest_id": manifest.id},
            ):
                return False
        return True

    def _check_capability(self, requirement, context: ExecutionContext):
        if not self._registries.capabilities.has(requirement.capability_id):
            from arnold.kernel import CapabilityCheck, CapabilityId

            return CapabilityCheck(
                capability_id=CapabilityId(namespace="runtime", name=requirement.capability_id),
                allowed=False,
                reason="capability not registered",
            )
        return self._registries.capabilities.check(
            requirement.capability_id,
            route=requirement.route,
            context={"run_id": self._run_id, "coordinate": str(context.coordinate)},
        )

    def _record_wbc_effect_intent(
        self,
        *,
        effect_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        if self._wbc_attempt is None:
            return
        self._wbc_attempt.effect_intent(effect_id, payload)

    def _record_wbc_effect_outcome(
        self,
        *,
        effect_id: str,
        status: str,
        payload: Mapping[str, Any],
    ) -> None:
        if self._wbc_attempt is None:
            return
        self._wbc_attempt.effect_outcome(effect_id, status=status, payload=payload)

    def _record_wbc_reconciliation(
        self,
        *,
        name: str,
        outcome: str,
        payload: Mapping[str, Any],
    ) -> None:
        if self._wbc_attempt is None:
            return
        self._wbc_attempt.reconciliation(name, outcome=outcome, payload=payload)

    def _budget_for_node(
        self, coordinate: RouteCoordinate, node: WorkflowNode
    ) -> BudgetReservation:
        """Return the budget reservation to record before executing a node."""

        del coordinate, node
        return BudgetReservation(node_ref="", cost=0.0, seconds=0.0, tokens=0)

    def _execute_node_payload(
        self, coordinate: RouteCoordinate, node: WorkflowNode, context: ExecutionContext
    ) -> NodeOutcome:
        """Concrete node execution. Override in tests/fakes."""

        del coordinate, node, context
        return NodeOutcome(state=NodeState.COMPLETED)

    def _execute_fanout_child(
        self,
        coordinate: RouteCoordinate,
        parent_node: WorkflowNode,
        context: ExecutionContext,
    ) -> NodeOutcome:
        """Execute a synthetic fanout child coordinate."""

        del parent_node
        return NodeOutcome(
            state=NodeState.COMPLETED,
            outputs={"child_key": coordinate.child_key or ""},
        )

    def _reduce(
        self,
        coordinate: RouteCoordinate,
        reducer_ref: str,
        inputs: tuple[Mapping[str, Any], ...],
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        """Reduce fanout child outputs. Override to call a registry."""

        del coordinate, context
        if self._registries.reducers.has(reducer_ref):
            return self._registries.reducers.reduce(reducer_ref, inputs=inputs, context={})
        return {"reducer_id": reducer_ref, "count": len(inputs)}

    def _execute_effect(
        self,
        coordinate: RouteCoordinate,
        effect_ref,
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        """Execute an external effect through the effect registry."""

        idempotency = effect_ref.idempotency or None
        if idempotency is None:
            policy = self._node_by_id(coordinate.node_ref).policy
            idempotency = policy.idempotency if policy else None
        require_idempotency_policy(
            key_ref=idempotency.key_ref if idempotency else None,
            key_template=idempotency.key_template if idempotency else None,
            required=idempotency.required if idempotency else True,
        )
        key = derive_effect_idempotency_key(
            run_id=self._run_id,
            node_ref=coordinate.node_ref,
            effect_id=effect_ref.effect_id,
            key_template=idempotency.key_template if idempotency else None,
            key_ref=idempotency.key_ref if idempotency else None,
        )
        return self._registries.effects.execute(
            effect_ref.effect_id,
            route=effect_ref.route,
            payload={"coordinate": str(context.coordinate)},
            idempotency_key=key,
            context={"run_id": self._run_id},
        )

    def _select_branch(
        self,
        coordinate: RouteCoordinate,
        node: WorkflowNode,
        edges: tuple[WorkflowEdge, ...],
        context: ExecutionContext,
    ) -> str | None:
        """Select a branch target after a branch node completes.

        Default selects the first conditional edge, or the first edge if none
        are conditional. Override for deterministic tests.
        """

        del coordinate, context
        conditional = tuple(edge for edge in edges if edge.condition_ref is not None)
        if conditional:
            return conditional[0].id
        if edges:
            return edges[0].id
        return None

    def _load_subpipeline_manifest(self, node: WorkflowNode) -> WorkflowManifest | None:
        """Load a child manifest for a subpipeline node. Override in tests."""

        del node
        return None

    def _execute_subpipeline_scope(
        self,
        coordinate: RouteCoordinate,
        node: WorkflowNode,
        child_manifest: WorkflowManifest | None,
        context: ExecutionContext,
    ) -> NodeOutcome:
        """Run the body of a subpipeline. Override in tests to simulate children."""

        del coordinate, node, child_manifest, context
        return NodeOutcome(state=NodeState.COMPLETED)

    def _emit_control_signals(
        self,
        coordinate: RouteCoordinate,
        node: WorkflowNode,
        outcome: NodeOutcome,
        context: ExecutionContext,
    ) -> tuple[Mapping[str, Any] | ControlTransition, ...]:
        """Return control transitions emitted by a node outcome.

        Override in tests to simulate control signals.
        """

        del coordinate, node, context
        return tuple(outcome.control_signals)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run_manifest(
        self,
        manifest: WorkflowManifest,
        *,
        artifact_root: Path,
        registries: ExecutionRegistries,
        resume_cursor: ManifestCursor | None = None,
        state_store: StateStore | None = None,
        logger: ExecutionLogger | None = None,
    ) -> ExecutionResult:
        self._manifest = manifest
        self._root = Path(artifact_root)
        self._registries = registries
        self._journal = NDJsonEventJournal(self._root)
        self._store = self._create_artifact_store(self._root)
        self._outputs: dict[RouteCoordinate, dict[str, Any]] = {}
        self._run_id = self._make_run_id()
        self._reentry_id = resume_cursor.reentry_id if resume_cursor else self._make_reentry_id()
        self._scope_stack: tuple[str, ...] = self._initial_scope_stack or ()
        self._init_ts = self._external_init_ts or self._now()
        if state_store is not None:
            self._state_store = state_store
        if logger is not None:
            self._logger = logger
        self._wbc_attempt = begin_native_wbc_attempt(
            self._root,
            producer_family="arnold_execution",
            surface="backend.run_manifest",
            run_id=self._run_id,
            manifest_hash=manifest.manifest_hash or "",
            subject={"manifest_id": manifest.id, "resume": resume_cursor is not None},
            metadata={"backend": self.__class__.__name__},
            start_payload={"artifact_root": str(self._root), "resume": resume_cursor is not None},
        )

        span = self._logger.span("run_manifest", self._run_id)
        span.__enter__()

        diagnostics: list[ExecutionDiagnostic] = []
        terminal: ExecutionState | None = None

        prior_events = self._journal.read()
        self._append(
            EventFamily.NODE_LIFECYCLE,
            "manifest_loaded",
            {"manifest_id": manifest.id, "schema_version": manifest.SCHEMA_VERSION},
        )
        self._append(
            EventFamily.NODE_LIFECYCLE,
            "manifest_validated",
            {"manifest_id": manifest.id, "manifest_hash": manifest.manifest_hash or ""},
        )
        self._logger.log_event(
            "run_started",
            self._run_id,
            {
                "manifest_id": manifest.id,
                "manifest_hash": manifest.manifest_hash or "",
                "artifact_root": str(self._root),
            },
        )

        self._save_checkpoint("running")

        if resume_cursor is not None and resume_cursor.node is not None:
            node_ref = resume_cursor.node.id
            if not self._check_authority("resume", self._resume_payload):
                terminal = ExecutionState.QUARANTINED
                diagnostics.append(
                    ExecutionDiagnostic(
                        code="authority_denied",
                        message="resume authority denied",
                        node_id=node_ref,
                    )
                )
                self._append(
                    EventFamily.SUSPENSION,
                    "resume_rejected",
                    {"node_ref": node_ref, "reason": "authority denied"},
                )
                self._wbc_attempt.resume(
                    "resume_rejected",
                    {"node_ref": node_ref, "reason": "authority denied"},
                )
            else:
                self._append(
                    EventFamily.SUSPENSION,
                    "node_resumed",
                    {
                        "node_ref": node_ref,
                        "reentry_id": self._reentry_id or "",
                    },
                )
                self._logger.log_event(
                    "run_resumed",
                    self._run_id,
                    {"node_ref": node_ref, "reentry_id": self._reentry_id or ""},
                )
                self._wbc_attempt.resume(
                    "node_resumed",
                    {"node_ref": node_ref, "reentry_id": self._reentry_id or ""},
                )

        while terminal is None:
            terminal = self._check_deadline_ttl()
            if terminal is not None:
                break

            events = self._journal.read()
            control_projection = project_control_transitions(manifest, events)
            routing = project_routing_state(
                manifest,
                events,
                overlays=control_projection.overlays,
            )

            if routing.suspended:
                terminal = ExecutionState.SUSPENDED
                break

            if not routing.ready:
                terminal_failures = self._terminal_failures(routing)
                if terminal_failures:
                    failed = sorted(terminal_failures)[-1]
                    terminal = ExecutionState.FAILED
                    diagnostics.append(
                        ExecutionDiagnostic(
                            code="node_failed",
                            message=f"node {failed.node_ref} failed",
                            node_id=failed.node_ref,
                        )
                    )
                else:
                    terminal = ExecutionState.COMPLETED
                break

            for coordinate in list(routing.ready):
                terminal = self._check_deadline_ttl()
                if terminal is not None:
                    break

                # Routing may have changed underneath us (e.g. branch selection).
                events = self._journal.read()
                control_projection = project_control_transitions(manifest, events)
                routing = project_routing_state(
                    manifest,
                    events,
                    overlays=control_projection.overlays,
                )
                if coordinate not in routing.ready:
                    continue

                try:
                    self._execute_coordinate(coordinate, routing)
                except _TerminalState as exc:
                    terminal = exc.state
                    break
                except BudgetExceeded as exc:
                    terminal = ExecutionState.FAILED
                    diagnostics.append(
                        ExecutionDiagnostic(
                            code="budget_exceeded",
                            message=str(exc),
                            node_id=coordinate.node_ref,
                        )
                    )
                    self._append(
                        EventFamily.NODE_LIFECYCLE,
                        "run_failed",
                        {"reason": str(exc), "node_ref": coordinate.node_ref},
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    terminal = ExecutionState.FAILED
                    diagnostics.append(
                        ExecutionDiagnostic(
                            code="execution_error",
                            message=str(exc),
                            node_id=coordinate.node_ref,
                        )
                    )
                    self._append(
                        EventFamily.NODE_LIFECYCLE,
                        "run_failed",
                        {"reason": str(exc), "node_ref": coordinate.node_ref},
                    )
                    break

                events = self._journal.read()
                control_projection = project_control_transitions(manifest, events)
                routing = project_routing_state(
                    manifest,
                    events,
                    overlays=control_projection.overlays,
                )

            if terminal is not None:
                break

        terminal = terminal or ExecutionState.COMPLETED
        self._append(
            EventFamily.NODE_LIFECYCLE,
            f"run_{terminal.value}",
            {"reason": "terminal state reached"},
        )
        self._save_checkpoint(terminal.value)

        events = self._journal.read()
        control_projection = project_control_transitions(manifest, events)
        routing = project_routing_state(
            manifest,
            events,
            overlays=control_projection.overlays,
        )
        governor = fold_governor_state(events)
        budget = self._node_budget(None)
        elapsed = (self._now() - self._init_ts).total_seconds()
        progress = build_progress_report(events)
        snapshot = build_health_snapshot(
            status=terminal.value,
            routing_state=routing,
            governor_state=governor,
            budget=budget,
            elapsed_seconds=elapsed,
        )
        self._logger.log_event(
            f"run_{terminal.value}",
            self._run_id,
            {
                "progress": {
                    "total_nodes": progress.total_nodes,
                    "completed": progress.completed,
                    "failed": progress.failed,
                    "pending": progress.pending,
                    "suspended": progress.suspended,
                    "consumed_cost": progress.consumed_cost,
                    "remaining_cost": progress.remaining_cost,
                    "health_status": progress.health_status,
                },
                "health": snapshot_to_dict(snapshot),
            },
        )

        resume_cursor_out: ManifestCursor | None = None
        if terminal == ExecutionState.SUSPENDED:
            if routing.suspended:
                suspended = sorted(routing.suspended)[0]
                resume_cursor_out = self._build_resume_cursor(suspended)

        span.__exit__(None, None, None)

        if terminal == ExecutionState.SUSPENDED:
            self._wbc_attempt.terminal(
                status="suspended",
                outcome="checkpoint",
                payload={"state": terminal.value, "resume_available": resume_cursor_out is not None},
            )
        elif terminal == ExecutionState.QUARANTINED:
            self._wbc_attempt.terminal(
                status="quarantined",
                outcome="result",
                payload={"state": terminal.value, "diagnostic_count": len(diagnostics)},
            )
        elif terminal == ExecutionState.CANCELLED:
            self._wbc_attempt.terminal(
                status="cancelled",
                outcome="result",
                payload={"state": terminal.value, "diagnostic_count": len(diagnostics)},
            )
        elif terminal == ExecutionState.FAILED:
            self._wbc_attempt.terminal(
                status="failed",
                outcome="result",
                payload={"state": terminal.value, "diagnostic_count": len(diagnostics)},
            )
        else:
            self._wbc_attempt.terminal(
                status="completed",
                outcome="result",
                payload={"state": terminal.value, "diagnostic_count": len(diagnostics)},
            )

        return ExecutionResult(
            state=terminal,
            manifest_id=manifest.id,
            manifest_hash=manifest.manifest_hash or "",
            artifact_root=self._root,
            resume_cursor=resume_cursor_out,
            diagnostics=tuple(diagnostics),
            outputs=self._collect_outputs(),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _manifest_ref(self) -> ManifestReference:
        identity = workflow_identity_from_manifest(self._manifest)
        return ManifestReference(
            alias=identity.alias,
            manifest_hash=identity.manifest_hash,
        )

    def _append(
        self,
        family: EventFamily,
        kind: str,
        payload: Mapping[str, Any],
        *,
        scope_stack: tuple[str, ...] | None = None,
        idempotency_key: str | None = None,
    ) -> EventEnvelope:
        event = EventEnvelope(
            event_id=f"{self._run_id}:{kind}:{self._next_event_counter()}",
            family=family,
            kind=kind,
            manifest=self._manifest_ref(),
            run_id=self._run_id,
            payload_schema_hash=self._manifest.manifest_hash or "sha256:" + "0" * 64,
            payload=dict(payload),
            scope_stack=scope_stack if scope_stack is not None else self._scope_stack,
            reentry_id=self._reentry_id,
            artifact_root=str(self._root),
            idempotency_key=idempotency_key,
            replay=ReplayReference(journal_uri=self._journal.journal_uri),
        )
        return self._journal.append(event)

    _counter = 0

    def _next_event_counter(self) -> int:
        LocalJournalBackend._counter += 1
        return LocalJournalBackend._counter

    def _node_by_id(self, node_ref: str) -> WorkflowNode:
        for node in self._manifest.nodes:
            if node.id == node_ref:
                return node
        raise ValueError(f"node {node_ref!r} not found in manifest")

    def _outgoing_edges(self, node_ref: str) -> tuple[WorkflowEdge, ...]:
        return tuple(
            sorted(
                (edge for edge in self._manifest.edges if edge.source == node_ref),
                key=lambda edge: edge.id,
            )
        )

    def _terminal_failures(self, routing: RoutingState) -> set[RouteCoordinate]:
        """Return failed coordinates that are not superseded by a later success."""

        terminal: set[RouteCoordinate] = set()
        for failed in routing.failed:
            if any(
                coord.node_ref == failed.node_ref
                and coord.scope_stack == failed.scope_stack
                and coord.child_key == failed.child_key
                and coord in routing.completed
                for coord in routing.completed
            ):
                continue
            if any(
                ready.node_ref == failed.node_ref
                and ready.scope_stack == failed.scope_stack
                and ready.child_key == failed.child_key
                for ready in routing.ready
            ):
                continue
            terminal.add(failed)
        return terminal

    def _node_budget(self, node: WorkflowNode | None) -> GovernorBudget:
        from arnold.manifest import BudgetPolicy

        def _to_governor(policy: BudgetPolicy | None) -> GovernorBudget | None:
            if policy is None:
                return None
            return GovernorBudget(
                cost_limit=policy.max_cost,
                seconds_limit=policy.max_seconds,
                token_limit=policy.token_budget,
            )

        manifest_budget = _to_governor(self._manifest.policy.budget if self._manifest.policy else None)
        node_budget = _to_governor(node.policy.budget if node and node.policy else None)
        return node_budget_policy(manifest_budget, node_budget)

    def _check_budget(self, reservation: BudgetReservation) -> None:
        budget = self._node_budget(None)
        state = fold_governor_state(self._journal.read())
        projected = GovernorState(
            consumed_cost=state.consumed_cost + reservation.cost,
            consumed_seconds=state.consumed_seconds + reservation.seconds,
            consumed_tokens=state.consumed_tokens + reservation.tokens,
            released_cost=state.released_cost,
            released_seconds=state.released_seconds,
            released_tokens=state.released_tokens,
            reservations=dict(state.reservations),
        )
        projected.check(budget, coordinate=reservation.node_ref)

    def _collect_outputs(self) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for coord, value in self._outputs.items():
            if coord.scope_stack:
                continue
            if coord.child_key is None and not coord.node_ref.endswith(":reducer"):
                outputs[coord.node_ref] = value
        return outputs

    def _build_resume_cursor(self, coordinate: RouteCoordinate) -> ManifestCursor:
        from arnold.manifest import NodeRef, manifest_coordinate

        coord = manifest_coordinate(
            self._manifest.id,
            self._manifest.manifest_hash or "",
        )
        return coord.cursor(
            node=NodeRef(coordinate.node_ref),
            reentry_id=self._reentry_id,
        )

    def _check_deadline_ttl(self) -> ExecutionState | None:
        now = self._now()
        timing = self._manifest.policy.timing if self._manifest.policy else None
        if timing is None:
            return None

        if timing.ttl_seconds is not None:
            expiry = self._init_ts.timestamp() + timing.ttl_seconds
            if now.timestamp() >= expiry:
                self._append(
                    EventFamily.NODE_LIFECYCLE,
                    "ttl_expired",
                    {"ttl_seconds": timing.ttl_seconds, "init_ts": self._init_ts.isoformat()},
                )
                return ExecutionState.FAILED

        if timing.deadline_ref:
            try:
                deadline = datetime.fromisoformat(timing.deadline_ref)
                if now >= deadline:
                    self._append(
                        EventFamily.NODE_LIFECYCLE,
                        "manifest_deadline",
                        {"deadline_ref": timing.deadline_ref},
                    )
                    return ExecutionState.FAILED
            except ValueError:
                pass

        return None

    def _save_checkpoint(self, status: str) -> None:
        """Persist a snapshot of the current run state if a store is attached."""

        if self._state_store is None:
            return

        events = self._journal.read()
        routing = project_routing_state(self._manifest, events)
        governor = fold_governor_state(events)
        last_sequence = events[-1].sequence if events else None

        now = self._now().isoformat()
        checkpoint = RunCheckpoint(
            run_id=self._run_id,
            manifest_id=self._manifest.id,
            manifest_hash=self._manifest.manifest_hash or "",
            status=status,
            routing=RoutingSnapshot(
                completed=tuple(routing_snapshot(routing)["completed"]),
                failed=tuple(routing_snapshot(routing)["failed"]),
                suspended=tuple(routing_snapshot(routing)["suspended"]),
                ready=tuple(routing_snapshot(routing)["ready"]),
                blocked=tuple(routing_snapshot(routing)["blocked"]),
            ),
            journal_pointer=JournalPointer(
                journal_uri=self._journal.journal_uri,
                sequence=last_sequence,
            ),
            budget=BudgetSnapshot(
                consumed_cost=governor.consumed_cost,
                consumed_seconds=governor.consumed_seconds,
                consumed_tokens=governor.consumed_tokens,
                released_cost=governor.released_cost,
                released_seconds=governor.released_seconds,
                released_tokens=governor.released_tokens,
            ),
            outputs=self._collect_outputs(),
            scope_stack=self._scope_stack,
            reentry_id=self._reentry_id,
            created_at=self._init_ts.isoformat(),
            updated_at=now,
        )
        self._state_store.save(checkpoint)
        self._logger.log_event(
            "checkpoint_saved",
            self._run_id,
            {"status": status, "sequence": last_sequence},
        )

    def _execute_coordinate(
        self, coordinate: RouteCoordinate, routing: RoutingState
    ) -> None:
        context = ExecutionContext(
            coordinate=coordinate,
            scope_stack=coordinate.scope_stack,
            outputs=self._outputs,
            resume_payload=self._resume_payload,
        )

        if coordinate.child_key is not None:
            self._execute_fanout_child_coordinate(coordinate, context)
            return

        if coordinate.node_ref.endswith(":reducer"):
            self._execute_reducer_coordinate(coordinate, routing, context)
            return

        node = self._node_by_id(coordinate.node_ref)

        # Capabilities
        for req in node.capabilities:
            check = self._check_capability(req, context)
            self._append(
                EventFamily.NODE_LIFECYCLE,
                "capability_checked",
                {
                    "node_ref": coordinate.node_ref,
                    "capability_id": req.capability_id,
                    "allowed": check.allowed,
                    "required": req.required,
                },
            )
            if req.required and not check.allowed:
                self._append(
                    EventFamily.NODE_LIFECYCLE,
                    "node_failed",
                    {
                        "node_ref": coordinate.node_ref,
                        "error": f"capability {req.capability_id} denied",
                    },
                )
                return

        # Budget reservation
        reservation = self._budget_for_node(coordinate, node)
        if reservation.node_ref != coordinate.node_ref:
            reservation = BudgetReservation(
                node_ref=coordinate.node_ref,
                cost=reservation.cost,
                seconds=reservation.seconds,
                tokens=reservation.tokens,
            )
        self._check_budget(reservation)
        reservation_id = f"{coordinate.node_ref}:reserve"
        self._append(
            EventFamily.NODE_LIFECYCLE,
            "budget_reserved",
            {
                **reservation_payload(reservation),
                "reservation_id": reservation_id,
            },
            idempotency_key=reservation_id,
        )
        self._logger.log_event(
            "budget_reserved",
            self._run_id,
            {
                "node_ref": coordinate.node_ref,
                "reservation_id": reservation_id,
                "cost": reservation.cost,
                "seconds": reservation.seconds,
                "tokens": reservation.tokens,
            },
        )

        # Loop iteration marker
        if node.policy and node.policy.loop is not None:
            self._append(
                EventFamily.NODE_LIFECYCLE,
                "loop_iteration",
                {
                    "node_ref": coordinate.node_ref,
                    "iteration": coordinate.iteration,
                },
            )

        self._append(
            EventFamily.NODE_LIFECYCLE,
            "node_started",
            {
                "node_ref": coordinate.node_ref,
                "attempt": coordinate.attempt,
                "iteration": coordinate.iteration,
            },
        )
        self._logger.log_event(
            "node_started",
            self._run_id,
            {
                "node_ref": coordinate.node_ref,
                "attempt": coordinate.attempt,
                "iteration": coordinate.iteration,
            },
        )

        self._apply_control_transitions(coordinate, node)

        outcome = self._run_node_body(coordinate, node, context)

        self._process_control_signals(coordinate, node, outcome, context)

        # Timeout check
        node_timing = node.policy.timing if node.policy else None
        timeout_seconds = node_timing.timeout_seconds if node_timing else None
        if timeout_seconds is not None and outcome.state != NodeState.TIMEOUT:
            # _run_node_body already measures elapsed; timeout outcome handled there
            pass

        if outcome.state == NodeState.CANCELLED:
            self._append(
                EventFamily.NODE_LIFECYCLE,
                "node_cancelled",
                {"node_ref": coordinate.node_ref},
            )
            self._logger.log_event(
                "node_failed",
                self._run_id,
                {"node_ref": coordinate.node_ref, "reason": "cancelled"},
            )
            self._release_budget(reservation_id, reservation)
            raise _TerminalState(ExecutionState.CANCELLED)

        if outcome.state == NodeState.SUSPENDED:
            self._outputs[coordinate] = dict(outcome.outputs)
            self._append(
                EventFamily.SUSPENSION,
                "node_suspended",
                {
                    "node_ref": coordinate.node_ref,
                    "route_id": outcome.suspension_route_id or "default",
                    "attempt": coordinate.attempt,
                    "iteration": coordinate.iteration,
                },
            )
            self._logger.log_event(
                "run_suspended",
                self._run_id,
                {
                    "node_ref": coordinate.node_ref,
                    "route_id": outcome.suspension_route_id or "default",
                },
            )
            self._save_checkpoint("suspended")
            self._release_budget(reservation_id, reservation)
            raise _TerminalState(ExecutionState.SUSPENDED)

        if outcome.state == NodeState.TIMEOUT:
            self._append(
                EventFamily.NODE_LIFECYCLE,
                "node_timeout",
                {
                    "node_ref": coordinate.node_ref,
                    "timeout_seconds": timeout_seconds,
                },
            )
            self._append(
                EventFamily.NODE_LIFECYCLE,
                "node_failed",
                {
                    "node_ref": coordinate.node_ref,
                    "error": outcome.error or "node timed out",
                    "attempt": coordinate.attempt,
                    "iteration": coordinate.iteration,
                },
            )
            self._logger.log_event(
                "node_failed",
                self._run_id,
                {
                    "node_ref": coordinate.node_ref,
                    "error": outcome.error or "node timed out",
                    "attempt": coordinate.attempt,
                    "iteration": coordinate.iteration,
                },
            )
            self._release_budget(reservation_id, reservation)
            return

        if outcome.state == NodeState.FAILED:
            self._append(
                EventFamily.NODE_LIFECYCLE,
                "node_failed",
                {
                    "node_ref": coordinate.node_ref,
                    "error": outcome.error or "node failed",
                    "attempt": coordinate.attempt,
                    "iteration": coordinate.iteration,
                },
            )
            self._logger.log_event(
                "node_failed",
                self._run_id,
                {
                    "node_ref": coordinate.node_ref,
                    "error": outcome.error or "node failed",
                    "attempt": coordinate.attempt,
                    "iteration": coordinate.iteration,
                },
            )
            self._release_budget(reservation_id, reservation)
            self._maybe_compensate(coordinate, node)
            self._maybe_escalate(coordinate, node)
            return

        # COMPLETED
        self._outputs[coordinate] = dict(outcome.outputs)

        # Effects
        effects = node.policy.effects if node.policy else ()
        for effect in effects:
            if not self._run_effect(coordinate, effect, context):
                self._append(
                    EventFamily.NODE_LIFECYCLE,
                    "node_failed",
                    {
                        "node_ref": coordinate.node_ref,
                        "error": f"effect {effect.effect_id} failed",
                    },
                )
                self._logger.log_event(
                    "node_failed",
                    self._run_id,
                    {"node_ref": coordinate.node_ref, "error": f"effect {effect.effect_id} failed"},
                )
                self._release_budget(reservation_id, reservation)
                self._maybe_compensate(coordinate, node)
                self._maybe_escalate(coordinate, node)
                return

        # Branch selection
        outgoing = self._outgoing_edges(node.id)
        if outgoing and any(edge.condition_ref is not None for edge in outgoing):
            edge_id = outcome.branch_edge_id or self._select_branch(
                coordinate, node, outgoing, context
            )
            if edge_id:
                self._append(
                    EventFamily.NODE_LIFECYCLE,
                    "branch_selected",
                    {
                        "node_ref": coordinate.node_ref,
                        "edge_id": edge_id,
                    },
                )

        # Subpipeline
        if node.subpipeline is not None:
            child_manifest = self._load_subpipeline_manifest(node)
            self._append(
                EventFamily.NODE_LIFECYCLE,
                "subpipeline_entered",
                {
                    "node_ref": coordinate.node_ref,
                    "child_manifest_hash": node.subpipeline.manifest_hash,
                },
                scope_stack=coordinate.scope_stack,
            )
            child_outcome = self._execute_subpipeline_scope(
                coordinate, node, child_manifest, context
            )
            self._append(
                EventFamily.NODE_LIFECYCLE,
                "subpipeline_exited",
                {
                    "node_ref": coordinate.node_ref,
                    "child_state": child_outcome.state.value,
                },
                scope_stack=coordinate.scope_stack,
            )
            if child_outcome.state != NodeState.COMPLETED:
                self._append(
                    EventFamily.NODE_LIFECYCLE,
                    "node_failed",
                    {
                        "node_ref": coordinate.node_ref,
                        "error": child_outcome.error or "subpipeline failed",
                    },
                )
                self._logger.log_event(
                    "node_failed",
                    self._run_id,
                    {"node_ref": coordinate.node_ref, "error": child_outcome.error or "subpipeline failed"},
                )
                self._release_budget(reservation_id, reservation)
                return

        # Artifacts
        for spec in outcome.artifacts:
            self._write_artifact(coordinate, spec)

        self._append(
            EventFamily.NODE_LIFECYCLE,
            "budget_settled",
            {
                "node_ref": coordinate.node_ref,
                "reservation_id": reservation_id,
                "actual_cost": outcome.actual_cost,
                "actual_seconds": outcome.actual_seconds,
                "actual_tokens": outcome.actual_tokens,
            },
            idempotency_key=reservation_id,
        )
        self._logger.log_event(
            "budget_settled",
            self._run_id,
            {
                "node_ref": coordinate.node_ref,
                "reservation_id": reservation_id,
                "actual_cost": outcome.actual_cost,
                "actual_seconds": outcome.actual_seconds,
                "actual_tokens": outcome.actual_tokens,
            },
        )

        self._append(
            EventFamily.NODE_LIFECYCLE,
            "node_completed",
            {
                "node_ref": coordinate.node_ref,
                "attempt": coordinate.attempt,
                "iteration": coordinate.iteration,
                "outputs": outcome.outputs,
            },
        )
        self._logger.log_event(
            "node_completed",
            self._run_id,
            {
                "node_ref": coordinate.node_ref,
                "attempt": coordinate.attempt,
                "iteration": coordinate.iteration,
            },
        )
        self._save_checkpoint("running")

    def _run_node_body(
        self, coordinate: RouteCoordinate, node: WorkflowNode, context: ExecutionContext
    ) -> NodeOutcome:
        node_timing = node.policy.timing if node.policy else None
        timeout_seconds = node_timing.timeout_seconds if node_timing else None

        start = self._monotonic()
        outcome = self._execute_node_payload(coordinate, node, context)
        elapsed = self._monotonic() - start

        if timeout_seconds is not None and elapsed > timeout_seconds:
            return NodeOutcome(
                state=NodeState.TIMEOUT,
                error=f"timeout after {elapsed:.3f}s (limit {timeout_seconds}s)",
            )
        return outcome

    def _execute_fanout_child_coordinate(
        self, coordinate: RouteCoordinate, context: ExecutionContext
    ) -> None:
        parent_node = self._node_by_id(coordinate.node_ref)
        outcome = self._execute_fanout_child(coordinate, parent_node, context)
        self._outputs[coordinate] = dict(outcome.outputs)
        self._append(
            EventFamily.NODE_LIFECYCLE,
            "node_completed",
            {
                "node_ref": coordinate.node_ref,
                "child_key": coordinate.child_key,
                "outputs": outcome.outputs,
            },
        )

    def _execute_reducer_coordinate(
        self,
        coordinate: RouteCoordinate,
        routing: RoutingState,
        context: ExecutionContext,
    ) -> None:
        parent_id = coordinate.node_ref[: -len(":reducer")]
        parent_node = self._node_by_id(parent_id)
        reducer_ref = (parent_node.policy.fanout.reducer_ref if parent_node.policy and parent_node.policy.fanout else None) or ""
        inputs = routing.reducer_inputs.get(coordinate, ())
        input_outputs = tuple(self._outputs.get(child, {}) for child in inputs)
        result = self._reduce(coordinate, reducer_ref, input_outputs, context)
        self._outputs[coordinate] = dict(result)
        self._append(
            EventFamily.NODE_LIFECYCLE,
            "reducer_completed",
            {
                "node_ref": coordinate.node_ref,
                "reducer_ref": reducer_ref,
                "outputs": result,
            },
        )
        self._append(
            EventFamily.NODE_LIFECYCLE,
            "node_completed",
            {
                "node_ref": coordinate.node_ref,
                "outputs": result,
            },
        )

    def _run_effect(
        self,
        coordinate: RouteCoordinate,
        effect_ref,
        context: ExecutionContext,
    ) -> bool:
        effect_payload: dict[str, Any] = {
            "node_ref": coordinate.node_ref,
            "effect_id": effect_ref.effect_id,
            "route": effect_ref.route,
            "scope_stack": list(coordinate.scope_stack),
        }
        self._record_wbc_effect_intent(effect_id=effect_ref.effect_id, payload=effect_payload)
        try:
            idempotency = effect_ref.idempotency or None
            if idempotency is None:
                node = self._node_by_id(coordinate.node_ref)
                policy = node.policy.idempotency if node.policy else None
                idempotency = policy
            require_idempotency_policy(
                key_ref=idempotency.key_ref if idempotency else None,
                key_template=idempotency.key_template if idempotency else None,
                required=idempotency.required if idempotency else True,
            )
        except Exception as exc:  # noqa: BLE001
            self._append(
                EventFamily.EFFECT,
                "effect_rejected",
                {
                    "node_ref": coordinate.node_ref,
                    "effect_id": effect_ref.effect_id,
                    "error": str(exc),
                },
            )
            self._record_wbc_effect_outcome(
                effect_id=effect_ref.effect_id,
                status="rejected",
                payload={**effect_payload, "error": str(exc)},
            )
            return False

        key = derive_effect_idempotency_key(
            run_id=self._run_id,
            node_ref=coordinate.node_ref,
            effect_id=effect_ref.effect_id,
            key_template=effect_ref.idempotency.key_template if effect_ref.idempotency else None,
            key_ref=effect_ref.idempotency.key_ref if effect_ref.idempotency else None,
        )
        effect_payload["idempotency_key"] = key

        ledger = fold_effect_ledger(self._journal.read())
        if ledger.is_duplicate(key):
            self._record_wbc_reconciliation(
                name=f"effect.{effect_ref.effect_id}.duplicate",
                outcome="already_recorded",
                payload=effect_payload,
            )
            self._record_wbc_effect_outcome(
                effect_id=effect_ref.effect_id,
                status="duplicate_skipped",
                payload=effect_payload,
            )
            return True

        descriptor = EffectDescriptor(
            effect_id=effect_ref.effect_id,
            kind=EffectKind.INTENT,
            target=effect_ref.route,
            idempotency_key=key,
            payload_schema_hash=effect_ref.payload_schema_hash or "",
        )
        self._append(
            EventFamily.EFFECT,
            "effect_intent",
            intent_payload(descriptor),
            scope_stack=coordinate.scope_stack,
            idempotency_key=key,
        )

        try:
            result = self._execute_effect(coordinate, effect_ref, context)
        except Exception as exc:  # noqa: BLE001
            self._append(
                EventFamily.EFFECT,
                "effect_failure",
                {
                    "effect_id": effect_ref.effect_id,
                    "idempotency_key": key,
                    "error": str(exc),
                },
                scope_stack=coordinate.scope_stack,
                idempotency_key=key,
            )
            self._record_wbc_effect_outcome(
                effect_id=effect_ref.effect_id,
                status="failed",
                payload={**effect_payload, "error": str(exc)},
            )
            return False

        self._append(
            EventFamily.EFFECT,
            "effect_fulfillment",
            fulfillment_payload(descriptor, result),
            scope_stack=coordinate.scope_stack,
            idempotency_key=key,
        )
        self._record_wbc_effect_outcome(
            effect_id=effect_ref.effect_id,
            status="fulfilled",
            payload={**effect_payload, "result": dict(result)},
        )
        return True

    def _write_artifact(
        self, coordinate: RouteCoordinate, spec: ArtifactSpec
    ) -> ArtifactBinding:
        provenance = spec.provenance
        if provenance is None:
            provenance = GeneratedArtifactProvenance(
                generator_module="arnold.execution.backend",
                generator_source_hash="sha256:" + "0" * 64,
                manifest_contract_version=self._manifest.SCHEMA_VERSION,
                generated_at=self._now().isoformat(),
            )
        provenance = self._workflow_bound_provenance(provenance)
        binding = self._store.write_artifact(
            artifact_id=spec.artifact_id,
            content=spec.content,
            content_type_id=spec.content_type_id,
            provenance=provenance,
            extension=spec.extension,
        )
        self._append(
            EventFamily.ARTIFACT,
            "artifact_written",
            {
                "artifact_id": spec.artifact_id,
                "relative_path": binding.relative_path,
                "content_hash": binding.provenance.provenance_hash,
                "content_type_id": spec.content_type_id,
                "node_ref": coordinate.node_ref,
            },
            scope_stack=coordinate.scope_stack,
        )
        return binding

    def _workflow_bound_provenance(
        self, provenance: GeneratedArtifactProvenance
    ) -> GeneratedArtifactProvenance:
        identity = workflow_identity_from_manifest(self._manifest)
        expected = {
            "workflow_alias": identity.alias,
            "manifest_hash": identity.manifest_hash,
            "pipeline_identity": identity.pipeline_identity,
        }
        actual = {
            "workflow_alias": provenance.workflow_alias,
            "manifest_hash": provenance.manifest_hash,
            "pipeline_identity": provenance.pipeline_identity,
        }
        if all(value is None for value in actual.values()):
            return replace(provenance, **expected)
        if actual != expected:
            raise ValueError("artifact provenance workflow identity does not match executing manifest")
        return provenance

    # ------------------------------------------------------------------
    # Control transitions, compensation, and escalation
    # ------------------------------------------------------------------

    def _journal_control_transition(
        self,
        payload: Mapping[str, Any],
        *,
        scope_stack: tuple[str, ...] | None = None,
    ) -> None:
        self._append(
            EventFamily.CONTROL_TRANSITION,
            "control_transition",
            dict(payload),
            scope_stack=scope_stack if scope_stack is not None else self._scope_stack,
        )

    def _apply_control_transitions(
        self,
        coordinate: RouteCoordinate,
        node: WorkflowNode,
    ) -> None:
        """Dispatch declared control transitions and overlays through the registry."""

        controls = self._registries.controls
        manifest_hash = self._manifest.manifest_hash or ""
        for slot in collect_declared_transitions(node):
            transition = dispatch_control_transition(
                controls,
                slot,
                coordinate,
                run_id=self._run_id,
            )
            if transition is not None:
                payload = control_transition_from_projection(
                    transition,
                    scope_stack=coordinate.scope_stack,
                    manifest_hash=manifest_hash,
                )
                self._journal_control_transition(
                    payload,
                    scope_stack=coordinate.scope_stack,
                )
        for slot in collect_declared_overlays(node):
            for transition in dispatch_topology_overlay(
                controls,
                slot,
                coordinate,
                run_id=self._run_id,
            ):
                payload = control_transition_from_projection(
                    transition,
                    scope_stack=coordinate.scope_stack,
                    manifest_hash=manifest_hash,
                )
                # Topology overlays are recorded as control transitions with
                # kind ``overlay`` so routing can project them without mutating
                # the canonical manifest hash.
                payload = {**payload, "kind": "overlay"}
                self._journal_control_transition(
                    payload,
                    scope_stack=coordinate.scope_stack,
                )

    def _process_control_signals(
        self,
        coordinate: RouteCoordinate,
        node: WorkflowNode,
        outcome: NodeOutcome,
        context: ExecutionContext,
    ) -> None:
        """Journal control transitions emitted by a node outcome."""

        signals = self._emit_control_signals(coordinate, node, outcome, context)
        if not signals:
            return
        manifest_hash = self._manifest.manifest_hash or ""
        for signal in signals:
            if isinstance(signal, ControlTransition):
                payload = control_transition_from_projection(
                    signal,
                    scope_stack=coordinate.scope_stack,
                    manifest_hash=manifest_hash,
                )
            else:
                payload = {
                    "kind": signal.get("kind", ""),
                    "source_node": signal.get("source_node", coordinate.node_ref),
                    "target_node": signal.get("target_node", ""),
                    "scope_stack": list(coordinate.scope_stack),
                    "payload": dict(signal.get("payload", {})),
                    "manifest_hash": manifest_hash,
                }
            self._journal_control_transition(
                payload,
                scope_stack=coordinate.scope_stack,
            )

    def _execute_compensation_effect(
        self,
        step: "CompensationStep",
        context: ExecutionContext,
    ) -> tuple[bool, str | None]:
        """Execute a single compensation target through the effect ledger."""

        effect_ref = step.target.effect
        coordinate = step.coordinate
        effect_payload: dict[str, Any] = {
            "node_ref": coordinate.node_ref,
            "effect_id": effect_ref.effect_id,
            "route": effect_ref.route,
            "scope_stack": list(coordinate.scope_stack),
            "compensation": True,
            "idempotency_key": step.idempotency_key,
        }
        self._record_wbc_effect_intent(
            effect_id=f"{effect_ref.effect_id}.compensation",
            payload=effect_payload,
        )
        ledger = fold_effect_ledger(self._journal.read())
        if ledger.is_duplicate(step.idempotency_key):
            self._record_wbc_reconciliation(
                name=f"effect.{effect_ref.effect_id}.compensation.duplicate",
                outcome="already_recorded",
                payload=effect_payload,
            )
            self._record_wbc_effect_outcome(
                effect_id=f"{effect_ref.effect_id}.compensation",
                status="duplicate_skipped",
                payload=effect_payload,
            )
            return True, None

        descriptor = EffectDescriptor(
            effect_id=effect_ref.effect_id,
            kind=EffectKind.INTENT,
            target=effect_ref.route,
            idempotency_key=step.idempotency_key,
            payload_schema_hash=effect_ref.payload_schema_hash or "",
        )
        self._append(
            EventFamily.EFFECT,
            "effect_intent",
            intent_payload(descriptor),
            scope_stack=coordinate.scope_stack,
            idempotency_key=step.idempotency_key,
        )
        try:
            result = self._execute_effect(coordinate, effect_ref, context)
        except Exception as exc:  # noqa: BLE001
            self._append(
                EventFamily.EFFECT,
                "effect_failure",
                {
                    "effect_id": effect_ref.effect_id,
                    "idempotency_key": step.idempotency_key,
                    "error": str(exc),
                },
                scope_stack=coordinate.scope_stack,
                idempotency_key=step.idempotency_key,
            )
            self._record_wbc_effect_outcome(
                effect_id=f"{effect_ref.effect_id}.compensation",
                status="failed",
                payload={**effect_payload, "error": str(exc)},
            )
            return False, str(exc)
        self._append(
            EventFamily.EFFECT,
            "effect_fulfillment",
            fulfillment_payload(descriptor, result),
            scope_stack=coordinate.scope_stack,
            idempotency_key=step.idempotency_key,
        )
        self._record_wbc_effect_outcome(
            effect_id=f"{effect_ref.effect_id}.compensation",
            status="fulfilled",
            payload={**effect_payload, "result": dict(result)},
        )
        return True, None

    def _maybe_compensate(
        self,
        coordinate: RouteCoordinate,
        node: WorkflowNode,
    ) -> None:
        """Trigger compensation for a failed coordinate if a policy exists."""

        manifest_policy = self._manifest.policy.compensation if self._manifest.policy else None
        policy = compensation_policy_for_node(node, manifest_policy)
        if policy is None:
            return
        scope_stack = compensation_scope_stack(coordinate, policy)
        run_key = compensation_run_idempotency_key(
            run_id=self._run_id,
            trigger_node_ref=coordinate.node_ref,
            scope_stack=scope_stack,
        )
        events = self._journal.read()
        if compensation_already_started(
            events,
            trigger_node_ref=coordinate.node_ref,
            scope_stack=scope_stack,
        ):
            return

        steps = build_compensation_steps(
            events,
            policy,
            coordinate,
            run_id=self._run_id,
        )
        context = ExecutionContext(
            coordinate=coordinate,
            scope_stack=scope_stack,
            outputs=self._outputs,
            resume_payload=self._resume_payload,
        )
        self._append(
            EventFamily.NODE_LIFECYCLE,
            "compensation_started",
            compensation_started_payload(
                trigger_node_ref=coordinate.node_ref,
                scope_stack=scope_stack,
                step_count=len(steps),
            ),
            scope_stack=scope_stack,
            idempotency_key=run_key,
        )
        completed_steps = 0
        failed_steps = 0
        for step in steps:
            success, error = self._execute_compensation_effect(step, context)
            if success:
                completed_steps += 1
                self._append(
                    EventFamily.NODE_LIFECYCLE,
                    "compensation_step_completed",
                    compensation_step_payload(step=step, success=True),
                    scope_stack=scope_stack,
                )
            else:
                failed_steps += 1
                self._append(
                    EventFamily.NODE_LIFECYCLE,
                    "compensation_step_failed",
                    compensation_step_payload(
                        step=step,
                        success=False,
                        error=error or f"effect {step.target.effect.effect_id} failed",
                    ),
                    scope_stack=scope_stack,
                )
        self._append(
            EventFamily.NODE_LIFECYCLE,
            "compensation_completed",
            compensation_completed_payload(
                trigger_node_ref=coordinate.node_ref,
                scope_stack=scope_stack,
                completed_steps=completed_steps,
                failed_steps=failed_steps,
            ),
            scope_stack=scope_stack,
            idempotency_key=run_key,
        )

    def _execute_escalation_target(
        self,
        target_ref: str,
        scope_stack: tuple[str, ...],
    ) -> None:
        """Execute an escalation target node in the current scope."""

        try:
            target_node = self._node_by_id(target_ref)
        except ValueError:
            self._append(
                EventFamily.NODE_LIFECYCLE,
                "escalation_target_missing",
                {"node_ref": target_ref, "scope_stack": list(scope_stack)},
                scope_stack=scope_stack,
            )
            return
        target_coordinate = RouteCoordinate(
            node_ref=target_ref,
            scope_stack=scope_stack,
        )
        events = self._journal.read()
        control_projection = project_control_transitions(self._manifest, events)
        routing = project_routing_state(
            self._manifest,
            events,
            overlays=control_projection.overlays,
        )
        self._execute_coordinate(target_coordinate, routing)

    def _maybe_escalate(
        self,
        coordinate: RouteCoordinate,
        node: WorkflowNode,
        *,
        explicit_signal: bool = False,
    ) -> None:
        """Route to escalation targets after retry exhaustion or explicit signal."""

        manifest_policy = self._manifest.policy.escalation if self._manifest.policy else None
        route = should_escalate(
            coordinate,
            node,
            manifest_policy,
            explicit_signal=explicit_signal,
        )
        if route is None:
            return
        if escalation_already_routed(
            self._journal.read(),
            source_node=coordinate.node_ref,
            scope_stack=coordinate.scope_stack,
            attempt=coordinate.attempt,
        ):
            return

        manifest_hash = self._manifest.manifest_hash or ""
        self._append(
            EventFamily.CONTROL_TRANSITION,
            "escalation_routed",
            escalation_routed_payload(route, manifest_hash=manifest_hash),
            scope_stack=coordinate.scope_stack,
        )
        for target_ref in route.target_refs:
            self._execute_escalation_target(target_ref, coordinate.scope_stack)

    def _release_budget(self, reservation_id: str, reservation: BudgetReservation) -> None:
        self._append(
            EventFamily.NODE_LIFECYCLE,
            "budget_released",
            {
                **release_payload(
                    BudgetRelease(
                        node_ref=reservation.node_ref,
                        reservation_id=reservation_id,
                        released_cost=reservation.cost,
                        released_seconds=reservation.seconds,
                        released_tokens=reservation.tokens,
                    )
                ),
                "reservation_id": reservation_id,
            },
            idempotency_key=reservation_id,
        )
        self._logger.log_event(
            "budget_released",
            self._run_id,
            {
                "node_ref": reservation.node_ref,
                "reservation_id": reservation_id,
                "released_cost": reservation.cost,
                "released_seconds": reservation.seconds,
                "released_tokens": reservation.tokens,
            },
        )


class _TerminalState(Exception):
    """Raised to short-circuit the run loop into a terminal state."""

    def __init__(self, state: ExecutionState) -> None:
        self.state = state


__all__ = [
    "ArtifactSpec",
    "ExecutionBackend",
    "ExecutionContext",
    "LocalJournalBackend",
    "NodeOutcome",
    "NodeState",
    "SkeletalBackend",
]
