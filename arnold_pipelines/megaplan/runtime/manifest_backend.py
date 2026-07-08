"""Megaplan product backend adapter for the M3 manifest runtime.

The adapter subclasses ``arnold.execution.LocalJournalBackend`` and overrides
``_execute_node_payload`` to dispatch explicit node IDs to relocated product
handlers in ``arnold_pipelines.megaplan.handlers``.  Model and tool work is
routed through ``arnold.agent`` registries and ``arnold.execution.registries``;
no legacy worker paths from the neutral runtime are imported.
"""

from __future__ import annotations

import argparse
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
    ``_execute_node_payload`` hook to product handlers and preserves their
    payloads in ``NodeOutcome.outputs``. Product routing authority stays in the
    compiled manifest and declared policy surfaces; this adapter does not
    translate handler decision fields into routes or control transitions.
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

        return self._node_outcome_from_response(node_id, response)

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

    def _node_outcome_from_response(
        self,
        node_id: str,
        response: Mapping[str, Any],
    ) -> NodeOutcome:
        """Translate a Megaplan StepResponse into a neutral NodeOutcome."""

        success = bool(response.get("success", True))
        outputs = dict(response)
        outputs["node_id"] = node_id

        state = self._node_state_from_response(success=success, response=response)
        error: str | None = None
        if not success:
            error = str(response.get("message") or response.get("error") or f"{node_id} failed")

        return NodeOutcome(
            state=state,
            outputs=outputs,
            error=error,
        )

    def _node_state_from_response(
        self,
        *,
        success: bool,
        response: Mapping[str, Any],
    ) -> NodeState:
        """Translate explicit runtime-state hints without deriving product routes."""

        if not success:
            return NodeState.FAILED
        runtime_state = response.get("node_state")
        if isinstance(runtime_state, str):
            try:
                return NodeState(runtime_state)
            except ValueError:
                pass
        if response.get("suspend") is True:
            return NodeState.SUSPENDED
        if response.get("state") in {"awaiting_human", "clarified", "suspended"}:
            return NodeState.SUSPENDED
        return NodeState.COMPLETED


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
