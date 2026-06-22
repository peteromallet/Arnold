"""Backend protocol and journal-backed execution backend for manifests."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Protocol

from arnold.kernel import (
    BudgetRelease,
    BudgetReservation,
    BudgetSettlement,
    BudgetExceeded,
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
)
from arnold.kernel.artifacts import ArtifactBinding, ProvenanceParent
from arnold.kernel.effect_ledger import derive_effect_idempotency_key
from arnold.manifest import ManifestCursor, WorkflowEdge, WorkflowManifest, WorkflowNode

from arnold.execution.registries import ExecutionRegistries
from arnold.execution.result import ExecutionDiagnostic, ExecutionResult, ExecutionState
from arnold.execution.routing import project_routing_state
from arnold.execution.state import RouteCoordinate, RoutingState


class ExecutionBackend(Protocol):
    """Backend seam used by :func:`arnold.execution.run`."""

    def run_manifest(
        self,
        manifest: WorkflowManifest,
        *,
        artifact_root: Path,
        registries: ExecutionRegistries,
        resume_cursor: ManifestCursor | None = None,
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
    ) -> ExecutionResult:
        del registries
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
    ) -> None:
        self._external_run_id = run_id
        self._external_reentry_id = reentry_id
        self._external_init_ts = init_ts
        self._resume_payload = dict(resume_payload or {})
        self._initial_scope_stack = initial_scope_stack

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

        diagnostics: list[ExecutionDiagnostic] = []
        terminal: ExecutionState | None = None

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
            else:
                self._append(
                    EventFamily.SUSPENSION,
                    "node_resumed",
                    {
                        "node_ref": node_ref,
                        "reentry_id": self._reentry_id or "",
                    },
                )

        while terminal is None:
            terminal = self._check_deadline_ttl()
            if terminal is not None:
                break

            events = self._journal.read()
            routing = project_routing_state(manifest, events)

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
                routing = project_routing_state(manifest, self._journal.read())
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
                            node_ref=coordinate.node_ref,
                        )
                    )
                    self._append(
                        EventFamily.NODE_LIFECYCLE,
                        "run_failed",
                        {"reason": str(exc), "node_ref": coordinate.node_ref},
                    )
                    break

                routing = project_routing_state(manifest, self._journal.read())

            if terminal is not None:
                break

        terminal = terminal or ExecutionState.COMPLETED
        self._append(
            EventFamily.NODE_LIFECYCLE,
            f"run_{terminal.value}",
            {"reason": "terminal state reached"},
        )

        resume_cursor_out: ManifestCoordinate | None = None
        if terminal == ExecutionState.SUSPENDED:
            events = self._journal.read()
            routing = project_routing_state(manifest, events)
            if routing.suspended:
                suspended = sorted(routing.suspended)[0]
                resume_cursor_out = self._build_resume_cursor(suspended)

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
        return ManifestReference(
            alias=self._manifest.id,
            manifest_hash=self._manifest.manifest_hash or "",
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

        outcome = self._run_node_body(coordinate, node, context)

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
            self._release_budget(reservation_id, reservation)
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
                self._release_budget(reservation_id, reservation)
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
            return False

        key = derive_effect_idempotency_key(
            run_id=self._run_id,
            node_ref=coordinate.node_ref,
            effect_id=effect_ref.effect_id,
            key_template=effect_ref.idempotency.key_template if effect_ref.idempotency else None,
            key_ref=effect_ref.idempotency.key_ref if effect_ref.idempotency else None,
        )

        ledger = fold_effect_ledger(self._journal.read())
        if ledger.is_duplicate(key):
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
            return False

        self._append(
            EventFamily.EFFECT,
            "effect_fulfillment",
            fulfillment_payload(descriptor, result),
            scope_stack=coordinate.scope_stack,
            idempotency_key=key,
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
