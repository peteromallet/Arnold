"""Megaplan product backend adapter for the M3 manifest runtime.

The adapter subclasses ``arnold.execution.LocalJournalBackend`` and overrides
``_execute_node_payload`` to dispatch explicit node IDs to relocated product
handlers in ``arnold_pipelines.megaplan.handlers``.  Model and tool work is
routed through ``arnold.agent`` registries and ``arnold.execution.registries``;
no legacy worker paths from the neutral runtime are imported.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold.execution.backend import (
    ExecutionContext,
    LocalJournalBackend,
    NodeOutcome,
    NodeState,
)
from arnold.execution.registries import ExecutionRegistries
from arnold.kernel import ControlTransition
from arnold.kernel.control import ControlTarget as KernelControlTarget, ControlTransitionType
from arnold.manifest import WorkflowNode


# ---------------------------------------------------------------------------
# Handler dispatch context
# ---------------------------------------------------------------------------

@dataclass
class MegaplanHandlerContext:
    """Inputs supplied to a Megaplan handler when invoked from the manifest backend."""

    plan_dir: Path
    state: dict[str, Any]
    args: argparse.Namespace
    node_id: str
    inputs: Mapping[str, Any] = field(default_factory=dict)

    def as_namespace(self, *, root: Path) -> argparse.Namespace:
        """Return a namespace that legacy handlers can consume."""

        ns = argparse.Namespace()
        for key, value in vars(self.args).items():
            setattr(ns, key, value)
        ns.plan_dir = self.plan_dir
        ns.plan = getattr(ns, "plan", None) or self.plan_dir.name
        ns.root = root
        ns.state = self.state
        ns.node_id = self.node_id
        ns.manifest_inputs = dict(self.inputs)
        return ns


# ---------------------------------------------------------------------------
# Megaplan manifest backend
# ---------------------------------------------------------------------------

class MegaplanManifestBackend(LocalJournalBackend):
    """Product backend that dispatches manifest nodes to Megaplan handlers.

    The backend is intentionally thin: it bridges the neutral runtime's
    ``_execute_node_payload`` hook to product handlers, translates their
    ``StepResponse`` into ``NodeOutcome``, and emits control transitions for
    branch choices.  Heavy policy remains in the handlers and in registries.
    """

    HANDLER_NODE_IDS: frozenset[str] = frozenset({
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "finalize",
        "execute",
        "review",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
        "tiebreaker_synthesis",
        "tiebreaker_decision",
        "tiebreaker_run",
        "tiebreaker_decide",
        "override",
    })

    def __init__(
        self,
        *,
        plan_dir: Path,
        state: dict[str, Any] | None = None,
        args: argparse.Namespace | None = None,
        registries: ExecutionRegistries | None = None,
        run_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(run_id=run_id, **kwargs)
        self._plan_dir = Path(plan_dir)
        self._state = dict(state or {})
        self._args = args or argparse.Namespace()
        self._product_registries = registries

    # ------------------------------------------------------------------
    # Pluggable backend hooks
    # ------------------------------------------------------------------

    def _execute_node_payload(
        self,
        coordinate: "RouteCoordinate",
        node: WorkflowNode,
        context: ExecutionContext,
    ) -> NodeOutcome:
        """Dispatch explicit node IDs to product handlers."""

        node_id = coordinate.node_ref
        if node_id not in self.HANDLER_NODE_IDS:
            # Neutral pass-through: return inputs as outputs.
            return NodeOutcome(
                state=NodeState.COMPLETED,
                outputs={"node_id": node_id},
            )

        handler = self._resolve_handler(node_id)
        root = self._plan_dir.parent
        handler_ctx = MegaplanHandlerContext(
            plan_dir=self._plan_dir,
            state=self._state,
            args=self._args,
            node_id=node_id,
            inputs=context.outputs,
        )

        try:
            response = handler(root, handler_ctx.as_namespace(root=root))
        except Exception as exc:  # noqa: BLE001
            return NodeOutcome(
                state=NodeState.FAILED,
                error=f"{node_id} handler failed: {exc}",
            )

        return self._response_to_outcome(node_id, response)

    # ------------------------------------------------------------------
    # Handler resolution
    # ------------------------------------------------------------------

    def _resolve_handler(self, node_id: str):
        """Return the product handler callable for a node ID."""

        from arnold_pipelines.megaplan import handlers

        mapping = {
            "prep": handlers.handle_prep,
            "plan": handlers.handle_plan,
            "critique": handlers.handle_critique,
            "gate": handlers.handle_gate,
            "revise": handlers.handle_revise,
            "finalize": handlers.handle_finalize,
            "execute": handlers.handle_execute,
            "review": handlers.handle_review,
            "tiebreaker_researcher": handlers.handle_tiebreaker_run,
            "tiebreaker_challenger": handlers.handle_tiebreaker_run,
            "tiebreaker_synthesis": handlers.handle_tiebreaker_run,
            "tiebreaker_decision": handlers.handle_tiebreaker_decide,
            "tiebreaker_run": handlers.handle_tiebreaker_run,
            "tiebreaker_decide": handlers.handle_tiebreaker_decide,
            "override": handlers.handle_override,
        }
        try:
            return mapping[node_id]
        except KeyError as exc:
            raise LookupError(f"no handler registered for node {node_id!r}") from exc

    # ------------------------------------------------------------------
    # Outcome translation
    # ------------------------------------------------------------------

    def _route_binding_for_signal(self, node_id: str, route_signal: object) -> tuple[str, str] | None:
        if not isinstance(route_signal, str) or not route_signal:
            return None
        from arnold_pipelines.megaplan.route_dispatch import resolve_route_binding_for_signal

        binding = resolve_route_binding_for_signal(node_id, route_signal)
        if binding is None:
            return None
        route_id = binding.get("id")
        target_ref = binding.get("target_ref")
        if isinstance(route_id, str) and route_id and isinstance(target_ref, str) and target_ref:
            return route_id, target_ref
        return None

    def _response_to_outcome(
        self,
        node_id: str,
        response: Mapping[str, Any],
    ) -> NodeOutcome:
        """Translate a Megaplan StepResponse into a neutral NodeOutcome."""

        success = bool(response.get("success", True))

        outputs = dict(response)
        outputs["node_id"] = node_id

        branch_edge_id = self._branch_edge_id(node_id, response)
        suspension_route_id = self._suspension_route_id(node_id, response)
        control_signals = self._build_control_signals(node_id, response)

        state: NodeState
        if not success:
            state = NodeState.FAILED
        elif suspension_route_id is not None:
            state = NodeState.SUSPENDED
        else:
            state = NodeState.COMPLETED
        error: str | None = None
        if not success:
            error = str(response.get("message") or response.get("error") or f"{node_id} failed")

        return NodeOutcome(
            state=state,
            outputs=outputs,
            error=error,
            branch_edge_id=branch_edge_id,
            suspension_route_id=suspension_route_id,
            control_signals=tuple(control_signals),
        )

    def _branch_edge_id(self, node_id: str, response: Mapping[str, Any]) -> str | None:
        """Map the response's next_step/recommendation to a manifest edge id.

        Conditional edges in the compiled manifest are named
        ``{source}:{target}``.  This mapping converts legacy handler outputs
        into those ids so the neutral router can select the correct target.
        """

        next_step = response.get("next_step")
        recommendation = response.get("recommendation")
        override_action = response.get("override_action")
        review_verdict = response.get("review_verdict")
        route_signal = response.get("route_signal")

        binding = self._route_binding_for_signal(node_id, route_signal)
        if binding is not None:
            return binding[0]

        if node_id == "gate":
            if isinstance(next_step, str):
                key = {
                    "finalize": "gate:finalize",
                    "revise": "gate:revise",
                    "override": "gate:override",
                    "tiebreaker_run": "gate:tiebreaker",
                    "tiebreaker": "gate:tiebreaker",
                    "override add-note": "gate:override",
                    "override force-proceed": "gate:force_proceed",
                    "force_proceed": "gate:force_proceed",
                    "force-proceed": "gate:force_proceed",
                    "halt": "gate:halt",
                    "gate": "gate:blocked",
                    "suspend": "gate:suspend",
                }.get(next_step)
                if key:
                    return key
            if isinstance(recommendation, str):
                return {
                    "PROCEED": "gate:finalize",
                    "ITERATE": "gate:revise",
                    "ESCALATE": "gate:override",
                    "TIEBREAKER": "gate:tiebreaker",
                    "ABORT": "gate:halt",
                }.get(recommendation)
            return "gate:finalize"

        if node_id == "revise":
            if isinstance(next_step, str) and next_step in {"revise:loop", "critique"}:
                return "revise:critique"
            return None

        if node_id == "review":
            if review_verdict == "needs_rework":
                return "review:revise"
            if review_verdict == "pass":
                return "review:halt"
            if isinstance(next_step, str):
                return {
                    "finalize": "review:halt",
                    "revise": "review:revise",
                    "halt": "review:halt",
                }.get(next_step)
            return None

        if node_id == "override":
            if isinstance(override_action, str):
                return {
                    "finalize": "override:finalize",
                    "abort": "override:halt",
                    "replan": "override:revise",
                }.get(override_action)
            if isinstance(next_step, str):
                return {
                    "finalize": "override:finalize",
                    "halt": "override:halt",
                    "revise": "override:revise",
                }.get(next_step)
            return None

        return None

    def _suspension_route_id(self, node_id: str, response: Mapping[str, Any]) -> str | None:
        """Return a suspension route when a handler halts for human input."""

        state = response.get("state")
        if state in {"awaiting_human", "clarified", "suspended"}:
            return f"{node_id}:human"
        if response.get("next_step") == "suspend":
            return f"{node_id}:suspend"
        return None

    def _build_control_signals(
        self,
        node_id: str,
        response: Mapping[str, Any],
    ) -> list[Mapping[str, Any] | ControlTransition]:
        """Build neutral control transitions from handler response fields."""

        signals: list[Mapping[str, Any] | ControlTransition] = []
        recommendation = response.get("recommendation")
        route_signal = response.get("route_signal")
        binding = self._route_binding_for_signal(node_id, route_signal)
        if binding is not None:
            _, target = binding
            signals.append(
                ControlTransition(
                    transition_type=ControlTransitionType.OVERRIDE,
                    source=KernelControlTarget(node_ref=node_id),
                    target=KernelControlTarget(node_ref=target),
                    trigger=f"{node_id}:{route_signal}",
                    payload_schema_hash="",
                    policy_ref=f"megaplan:{node_id}",
                    idempotency_key=f"{node_id}:{route_signal}",
                    payload={"route_signal": route_signal},
                )
            )
            return signals
        if recommendation in {"PROCEED", "ITERATE", "ESCALATE", "TIEBREAKER", "ABORT"}:
            target = {
                "PROCEED": "finalize",
                "ITERATE": "revise",
                "ESCALATE": "override",
                "TIEBREAKER": "tiebreaker",
                "ABORT": "halt",
            }[recommendation]
            signals.append(
                ControlTransition(
                    transition_type=ControlTransitionType.OVERRIDE,
                    source=KernelControlTarget(node_ref=node_id),
                    target=KernelControlTarget(node_ref=target),
                    trigger=f"gate:{recommendation.lower()}",
                    payload_schema_hash="",
                    policy_ref="megaplan:gate",
                    idempotency_key=f"{node_id}:{recommendation.lower()}",
                    payload={"recommendation": recommendation},
                )
            )

        override_action = response.get("override_action")
        if isinstance(override_action, str):
            signals.append(
                {
                    "kind": "override",
                    "source_node": node_id,
                    "target_node": override_action,
                    "payload": {"action": override_action},
                }
            )

        return signals


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def build_megaplan_registries(
    *,
    dispatcher: Any | None = None,
    extra_capabilities: Mapping[str, Any] | None = None,
    extra_effects: Mapping[str, Any] | None = None,
) -> ExecutionRegistries:
    """Build execution registries for Megaplan, backed by ``arnold.agent`` if available."""

    from arnold.execution.registries import build_agent_adapter_bridge

    if dispatcher is not None:
        registries = build_agent_adapter_bridge(dispatcher, mode="unit")
    else:
        registries = ExecutionRegistries()

    # Ensure neutral defaults exist; product-specific handlers are registered by
    # the caller or by manifest metadata.
    for key, handler in (extra_capabilities or {}).items():
        registries.capabilities.register(key, handler)
    for key, handler in (extra_effects or {}).items():
        registries.effects.register(key, handler)

    return registries


__all__ = [
    "MegaplanHandlerContext",
    "MegaplanManifestBackend",
    "build_megaplan_registries",
]
