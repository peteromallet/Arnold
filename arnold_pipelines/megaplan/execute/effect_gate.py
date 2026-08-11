"""Steps 13C-13D3: Execute batch effect gate adapter.

This is the single execute-to-action-gate/WBC adapter. It routes
bounded local-workspace, process, terminal, and publication-handoff
rows from ``batch.py`` through the action gate and WBC effect protocol.

Step 13C: create the adapter.
Step 13D1: inventory execute batch mutation sinks.
Step 13D2: route at most three local workspace and process rows.
Step 13D3: route at most three terminal and publication handoff rows.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from arnold.workflow.effect_protocol import (
    EffectProtocol,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_INDETERMINATE,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptIdentity,
    AttemptProvenance,
    GlobalEffectIdentity,
    GrantRef,
    RuntimeAdapter,
    VersionSet,
)

from arnold_pipelines.megaplan.custody.action_validator import (
    ActionBoundaryType,
    GateResult,
)

LOGGER = logging.getLogger(__name__)


# ── Execute effect families ──────────────────────────────────────────────────


class ExecuteEffectFamily(str, Enum):
    """Mutation families inventoried in the execute batch module."""

    LOCAL_WORKSPACE = "local_workspace"
    """Local file-system writes: artifacts, checkpoints, state saves."""

    PROCESS = "process"
    """Subprocess execution: worker invocation, shell commands."""

    TERMINAL = "terminal"
    """Terminal batch finalization: closing checkpoints, final state."""

    PUBLICATION_HANDOFF = "publication_handoff"
    """Boundary receipt publication that may trigger downstream actions."""


# ── Execute target identity ──────────────────────────────────────────────────


@dataclass(frozen=True)
class ExecuteTarget:
    """Stable identity for an execute batch effect target."""

    family: ExecuteEffectFamily
    batch_number: int
    task_ids: tuple[str, ...]
    action: str  # e.g. "write_artifact", "run_worker", "finalize_batch"

    @property
    def target_key(self) -> str:
        ids = ",".join(sorted(self.task_ids)) if self.task_ids else "none"
        return f"execute:{self.family.value}:batch{self.batch_number}:{self.action}:{ids}"


# ── Execute outcome ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExecuteOutcome:
    """Result of an execute batch effect through the adapter."""

    ok: bool
    family: str
    action: str
    glek: str
    outcome_kind: str
    error: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


# ── Execute effect gate adapter ──────────────────────────────────────────────


class ExecuteEffectGate:
    """Single adapter routing execute batch mutations through WBC/action gate.

    Step 13C: this is the sole execute-to-gate adapter.
    Steps 13D2-13D3: at most three rows per shard are routed through it.
    """

    def __init__(
        self,
        protocol: EffectProtocol,
        *,
        action_gate_check: Optional[
            Callable[[ActionBoundaryType, str], GateResult]
        ] = None,
        production_enabled: bool = False,
    ) -> None:
        self._protocol = protocol
        self._action_gate_check = action_gate_check
        self._production_enabled = production_enabled

    # ── gate ────────────────────────────────────────────────────────────

    def _gate(self, target: ExecuteTarget) -> GateResult:
        if self._action_gate_check is None:
            return GateResult.SHADOW_PASS
        return self._action_gate_check("dispatch", target.target_key)

    # ── GLEK ─────────────────────────────────────────────────────────────

    @staticmethod
    def _build_effect_identity(
        target: ExecuteTarget,
    ) -> GlobalEffectIdentity:
        return GlobalEffectIdentity(
            environment_id=f"execute-batch-{target.batch_number}",
            action_target=target.target_key,
            action_version="m10",
            effect_family=target.family.value,
            provider_target=f"execute:batch{target.batch_number}",
            canonical_request_identity=target.target_key,
            boundary_schema_hash="m10-execute-v1",
        )

    @staticmethod
    def _build_identity_bundle(
        attempt_id: str,
    ) -> tuple[AttemptIdentity, AttemptProvenance, RuntimeAdapter, VersionSet, GrantRef]:
        identity = AttemptIdentity(
            workflow_id=f"exec-{attempt_id}",
            run_id=f"exec-{attempt_id}",
            graph_revision="m10",
            attempt_id=attempt_id,
        )
        provenance = AttemptProvenance(
            parent_attempt_id=None,
        )
        adapter = RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="m10-execute",
        )
        versions = VersionSet(code_version="m10")
        grant_ref = GrantRef(grant_id=f"exec-grant-{attempt_id}")
        return identity, provenance, adapter, versions, grant_ref

    # ── dispatch ─────────────────────────────────────────────────────────

    def route(
        self,
        *,
        target: ExecuteTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
    ) -> ExecuteOutcome:
        """Route an execute batch mutation through the WBC protocol.

        Args:
            target: Stable execute target identity.
            intent_payload: The effect payload (intent data).
            apply_fn: The actual mutating function.
            attempt_id: Explicit attempt id; auto-generated if None.

        Returns:
            ExecuteOutcome with the GLEK, outcome, and error.
        """
        if self._production_enabled:
            LOGGER.warning(
                "Production execute dispatch attempted for %s — "
                "production is action-off in M10",
                target.target_key,
            )

        verdict = self._gate(target)
        if verdict not in (
            GateResult.AUTHORIZED,
            GateResult.SHADOW_PASS,
        ):
            return ExecuteOutcome(
                ok=False,
                family=target.family.value,
                action=target.action,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error=f"Action gate blocked: {verdict.value}",
                evidence={"gate_verdict": verdict.value},
            )

        aid = attempt_id or str(uuid.uuid4())
        ei = self._build_effect_identity(target)
        ident, prov, adapter, versions, grant_ref = self._build_identity_bundle(aid)

        try:
            reservation = self._protocol.reserve_and_start(
                attempt_id=aid,
                effect_identity=ei,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )
            glek = reservation.global_logical_effect_key

            self._protocol.persist_intent(
                attempt_id=aid,
                glek=glek,
                intent_payload=intent_payload,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )

            try:
                result = apply_fn(intent_payload)
            except Exception as exc:
                self._protocol.accept_outcome(
                    aid, glek, OUTCOME_FAILED,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
                return ExecuteOutcome(
                    ok=False,
                    family=target.family.value,
                    action=target.action,
                    glek=glek,
                    outcome_kind=OUTCOME_FAILED,
                    error=str(exc),
                )

            self._protocol.accept_outcome(
                aid, glek, OUTCOME_COMPLETED,
                {"result": str(result)[:1000]},
            )
            return ExecuteOutcome(
                ok=True,
                family=target.family.value,
                action=target.action,
                glek=glek,
                outcome_kind=OUTCOME_COMPLETED,
                evidence={"result_summary": str(result)[:200]},
            )

        except Exception as exc:
            return ExecuteOutcome(
                ok=False,
                family=target.family.value,
                action=target.action,
                glek="",
                outcome_kind=OUTCOME_INDETERMINATE,
                error=f"Protocol error: {type(exc).__name__}: {exc}",
            )


__all__ = [
    "ExecuteEffectFamily",
    "ExecuteTarget",
    "ExecuteOutcome",
    "ExecuteEffectGate",
]
