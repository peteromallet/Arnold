"""RecoveryPolicy.classify — M4 T16 (Step 11a) + M8A T8 circuit integration.

Pure classifier extracted from ``megaplan.auto`` so any orchestration
consumer can ask "what should I do with this error?" without importing
the planning driver.

Contract
--------
:class:`RecoveryPolicy` exposes two methods:

* :meth:`RecoveryPolicy.classify(error, layer) -> RecoveryDecision`
  — target-agnostic decision plus budget delta, never a state mutation.
* :meth:`RecoveryPolicy.classify_with_circuit(error, layer, *, circuit, ...) -> RecoveryDecision`
  — consults a :class:`~arnold_pipelines.megaplan.orchestration.plan_circuit.PlanCircuit`
  before authorizing any retry; normalizes the failure signature and opens
  the circuit when the threshold is reached.

The caller (``auto.py`` today) still owns counter bumps, event emissions,
and state machine transitions.

Decision actions
~~~~~~~~~~~~~~~~
* ``retry_fresh``     — start a clean attempt at the same phase
* ``retry_transient`` — replay after a transient external failure (provider stall)
* ``escalate``        — bubble up; caller decides target (target-agnostic)
* ``halt``            — terminal; ``halt_kind`` carries the reason category

``halt(kind)`` / ``escalate`` deliberately stay target-agnostic — no
``STATE_*`` literal escapes this module.  The caller maps the
``halt_kind`` to its own state machine.

Per-class budgets
~~~~~~~~~~~~~~~~~
* context-exhaustion (mirrors ``DEFAULT_MAX_CONTEXT_RETRIES``)
* transient external (mirrors ``DEFAULT_MAX_EXTERNAL_RETRIES``)
* blocked-task (mirrors ``DEFAULT_MAX_BLOCKED_RETRIES`` at auto.py:117)
* circuit-open (plan-level; no budget counter — the circuit itself is the guard)

The classifier returns ``budget_delta`` as the *increment* the caller
should apply to its corresponding counter (always ``+1`` for now, or ``0``
for ``halt``/``escalate``).  Counter bumps and event emits remain in
``auto.py`` so this module stays a pure decision function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal, Optional

# ---------------------------------------------------------------------------
# Lazy imports — keep this module importable from non-planning consumers.
# auto.py is intentionally NOT imported at module load.
# ---------------------------------------------------------------------------

from arnold_pipelines.megaplan.orchestration.phase_result import ExitKind

# Mirror the budget caps lifted from auto.py (DEFAULT_MAX_BLOCKED_RETRIES :117).
DEFAULT_MAX_CONTEXT_RETRIES: Final[int] = 2
DEFAULT_MAX_EXTERNAL_RETRIES: Final[int] = 1
DEFAULT_MAX_BLOCKED_RETRIES: Final[int] = 1

# Pulled inline from auto.py:86,104 so non-planning consumers don't have to
# import auto.py to classify a transient. Keep in sync.
EXTERNAL_RETRYABLE_PHASES: Final[frozenset[str]] = frozenset(
    {"plan", "prep", "critique", "revise", "gate", "finalize", "review"}
)
EXTERNAL_RETRYABLE_LAYERS: Final[frozenset[str]] = frozenset(
    {
        "stream_content_stall",
        "stream_first_content_timeout",
        "stream_read_timeout",
        "transport_timeout",
        "worker_stream_stall",
    }
)
EXTERNAL_PERMANENT_ERROR_KINDS: Final[frozenset[str]] = frozenset(
    {
        "auth", "balance", "quota", "billing", "config",
        "bad_request", "invalid_request", "unsupported_model",
        "context_exhausted", "context_length", "rate_limit",
    }
)

Action = Literal["retry_fresh", "retry_transient", "escalate", "halt"]

# Target-agnostic halt categories. The caller maps these to its own state.
HaltKind = Literal[
    "context_retry_exhausted",
    "external_retry_exhausted",
    "blocked_retry_exhausted",
    "permanent_external",
    "circuit_open",
    "unclassified",
]


@dataclass(frozen=True)
class RecoveryDecision:
    """Pure decision returned by :meth:`RecoveryPolicy.classify`."""

    action: Action
    # +1 against the matched budget when retrying; 0 for halt/escalate.
    budget_delta: int = 0
    # Which counter the delta targets (or which budget was exhausted on halt).
    budget_kind: Optional[Literal["context", "external", "blocked"]] = None
    # Populated only when action == "halt".
    halt_kind: Optional[HaltKind] = None
    # Optional human-readable reason for event emission.
    reason: str = ""


def _is_retryable_external_error(phase: str, external_error: Any) -> bool:
    """Mirror of auto._is_retryable_external_error (auto.py:221).

    Kept in sync deliberately; lifting it here lets non-planning consumers
    classify without importing auto.py.
    """
    if phase not in EXTERNAL_RETRYABLE_PHASES:
        return False
    if external_error is None:
        return False

    error_kind = str(getattr(external_error, "error_kind", "") or "").lower()
    status_code = getattr(external_error, "status_code", None)
    retry_after_s = getattr(external_error, "retry_after_s", None)
    provider_error_code = str(
        getattr(external_error, "provider_error_code", "") or ""
    ).lower()
    error_layer = str(getattr(external_error, "error_layer", "") or "").lower()
    message = str(getattr(external_error, "message", "") or "").lower()

    if error_kind in EXTERNAL_PERMANENT_ERROR_KINDS:
        return False
    if retry_after_s is not None:
        return False
    if isinstance(status_code, int) and 400 <= status_code < 500 and status_code != 408:
        return False

    if error_layer in EXTERNAL_RETRYABLE_LAYERS:
        return True
    if error_kind in {"stream_content_stall", "stalled_stream"}:
        return True
    if (
        error_kind == "network"
        and (provider_error_code == "timeout" or "timeout" in message or "timed out" in message)
        and (status_code is None or status_code in {408, 500, 502, 503, 504})
    ):
        return True
    return False


@dataclass(frozen=True)
class RecoveryPolicy:
    """Classify recovery errors without touching state.

    All caps default to the values lifted from ``auto.py``; callers can
    construct an alternate policy for tests by overriding the caps.
    """

    max_context_retries: int = DEFAULT_MAX_CONTEXT_RETRIES
    max_external_retries: int = DEFAULT_MAX_EXTERNAL_RETRIES
    max_blocked_retries: int = DEFAULT_MAX_BLOCKED_RETRIES

    # ------------------------------------------------------------------
    # The single public surface.
    # ------------------------------------------------------------------

    def classify(
        self,
        error: Any,
        layer: str,
        *,
        context_retries_used: int = 0,
        external_retries_used: int = 0,
        blocked_retries_used: int = 0,
        phase: str = "",
    ) -> RecoveryDecision:
        """Classify ``error`` observed at ``layer`` (phase / orchestration / etc.).

        Parameters
        ----------
        error
            The error or PhaseResult-like object. May have ``exit_kind``,
            ``error_kind``, ``error_layer``, etc.
        layer
            Where the error surfaced (``"phase"``, ``"orchestration"``, ...).
            Used for diagnostics only; classification is shape-driven.
        context_retries_used / external_retries_used / blocked_retries_used
            Current usage counters (caller-owned). The classifier uses these
            to decide whether the budget is still available.
        phase
            Phase name (e.g. ``"plan"``, ``"execute"``); needed for the
            external-retryable filter.
        """
        exit_kind = self._read_exit_kind(error)

        # 1) Context exhaustion — caller decides retry_fresh vs halt by budget.
        if exit_kind == ExitKind.context_exhausted or self._mentions_context_exhaustion(error):
            if context_retries_used < self.max_context_retries:
                return RecoveryDecision(
                    action="retry_fresh",
                    budget_delta=1,
                    budget_kind="context",
                    reason="context_exhausted",
                )
            return RecoveryDecision(
                action="halt",
                halt_kind="context_retry_exhausted",
                budget_kind="context",
                reason="context budget exhausted",
            )

        # 2) Transient external — provider stalls / transport timeouts.
        # Extract nested external_error sub-object if present (PhaseResult carries
        # error attributes one level down); fall back to error itself for bare objects.
        _ext_obj = getattr(error, "external_error", None) or error
        if exit_kind == ExitKind.external_error or self._looks_external(_ext_obj):
            if _is_retryable_external_error(phase, _ext_obj):
                if external_retries_used < self.max_external_retries:
                    return RecoveryDecision(
                        action="retry_transient",
                        budget_delta=1,
                        budget_kind="external",
                        reason="transient external",
                    )
                return RecoveryDecision(
                    action="halt",
                    halt_kind="external_retry_exhausted",
                    budget_kind="external",
                    reason="external budget exhausted",
                )
            # Non-retryable external (auth/billing/etc) — terminal.
            return RecoveryDecision(
                action="halt",
                halt_kind="permanent_external",
                reason="permanent external error",
            )

        # 3) Blocked-by-prereq / blocked-by-quality — caller may retry.
        if exit_kind in (ExitKind.blocked_by_quality, ExitKind.blocked_by_prereq):
            if blocked_retries_used < self.max_blocked_retries:
                return RecoveryDecision(
                    action="retry_fresh",
                    budget_delta=1,
                    budget_kind="blocked",
                    reason="blocked retry",
                )
            return RecoveryDecision(
                action="halt",
                halt_kind="blocked_retry_exhausted",
                budget_kind="blocked",
                reason="blocked budget exhausted",
            )

        # 4) Timeout / internal_error — escalate (caller picks next step).
        if exit_kind in (ExitKind.timeout, ExitKind.internal_error):
            return RecoveryDecision(
                action="escalate",
                reason=f"escalate {exit_kind.value if exit_kind else 'unknown'}",
            )

        # 5) Default — unclassified, halt to be safe.
        return RecoveryDecision(
            action="halt",
            halt_kind="unclassified",
            reason="unclassified error",
        )

    # ------------------------------------------------------------------
    # classify_with_circuit — consults PlanCircuit before authorizing retry
    # ------------------------------------------------------------------

    def classify_with_circuit(
        self,
        error: Any,
        layer: str,
        *,
        circuit: Any,  # PlanCircuit (lazy import)
        context_retries_used: int = 0,
        external_retries_used: int = 0,
        blocked_retries_used: int = 0,
        phase: str = "",
        task_id: str | None = None,
        batch_id: str | None = None,
        attempt_id: str | None = None,
        blocker: Any = None,
        provider: str | None = None,
        ref_metadata: str | None = None,
        fence: str | None = None,
    ) -> RecoveryDecision:
        """Classify with circuit-breaking — normalizes failure and checks circuit.

        Before returning any retry action, this method:

        1. Normalizes the failure into a :class:`FailureSignature`.
        2. Records the occurrence against *circuit*.
        3. If the circuit opens or is already open, returns
           ``halt(kind="circuit_open")`` immediately — no retry is authorized.
        4. Otherwise delegates to :meth:`classify` for budget-aware
           classification.

        Parameters
        ----------
        error, layer, context_retries_used, external_retries_used,
        blocked_retries_used, phase:
            Forwarded to :meth:`classify`.
        circuit:
            A :class:`~arnold_pipelines.megaplan.orchestration.plan_circuit.PlanCircuit`
            instance that tracks failure occurrences.
        task_id / batch_id / attempt_id:
            Scope identity for normalization.
        blocker:
            Blocker payload whose digest is used for normalization.
        provider:
            Provider identifier.
        ref_metadata:
            Source/install revision metadata.
        fence:
            Current grant/authority fence identifier.

        Returns
        -------
        RecoveryDecision
        """
        from arnold_pipelines.megaplan.orchestration.plan_circuit import (
            normalize_failure_signature,
        )

        # 1) Normalize the failure signature.
        signature = normalize_failure_signature(
            error,
            task_id=task_id,
            batch_id=batch_id,
            attempt_id=attempt_id,
            blocker=blocker,
            provider=provider,
            ref_metadata=ref_metadata,
            fence=fence,
        )

        # 2) Record against the circuit.
        circuit_decision = circuit.record_failure(signature)

        # 3) If the circuit is open, halt immediately — no retry allowed.
        if circuit_decision.is_open:
            return RecoveryDecision(
                action="halt",
                halt_kind="circuit_open",
                reason=(
                    f"Circuit open for failure class '{signature.failure_class}' "
                    f"(occurrence {circuit_decision.occurrence_count}/{circuit_decision.threshold})"
                ),
            )

        # 4) Circuit is not open — delegate to standard classify.
        return self.classify(
            error,
            layer,
            context_retries_used=context_retries_used,
            external_retries_used=external_retries_used,
            blocked_retries_used=blocked_retries_used,
            phase=phase,
        )

    # ------------------------------------------------------------------
    # Helpers — shape-driven, no isinstance gymnastics.
    # ------------------------------------------------------------------

    def _read_exit_kind(self, error: Any) -> Optional[ExitKind]:
        raw = getattr(error, "exit_kind", None)
        if isinstance(raw, ExitKind):
            return raw
        if isinstance(raw, str):
            try:
                return ExitKind(raw)
            except ValueError:
                return None
        return None

    def _mentions_context_exhaustion(self, error: Any) -> bool:
        text = str(getattr(error, "message", "") or "")
        return "ran out of room in the model" in text.lower()

    def _looks_external(self, error: Any) -> bool:
        # Has any of the external-error markers.
        for attr in ("error_kind", "error_layer", "provider_error_code", "status_code", "retry_after_s"):
            if getattr(error, attr, None) is not None:
                return True
        return False

    # ------------------------------------------------------------------
    # Arnold adapter — bridges the Arnold RecoveryPolicy Protocol
    # ------------------------------------------------------------------

    def classify_arnold(
        self,
        error: Any,
        context: Any,  # arnold.runtime.recovery.RecoveryContext (Protocol)
    ) -> Any:  # arnold.runtime.recovery.RecoveryDecision
        """Arnold :class:`~arnold.runtime.recovery.ArnoldRecoveryPolicy` adapter.

        Maps the Arnold ``classify(error, RecoveryContext)`` Protocol onto
        the source-compatible ``classify(error, layer, *, …)`` signature.

        ``RecoveryContext.metadata`` carries the Megaplan keyword arguments:
        ``layer`` (default ``\"phase\"``), ``context_retries_used``,
        ``external_retries_used``, ``blocked_retries_used``, and ``phase``.

        The Megaplan :class:`RecoveryDecision` is translated into an Arnold
        :class:`~arnold.runtime.recovery.RecoveryDecision` with
        ``status=\"decided\"``, opaque ``action`` / ``reason``, and
        ``budget_consumed`` carrying the budget kind, delta, and halt kind.
        """
        from arnold_pipelines.megaplan.orchestration.recovery import RecoveryDecision as ArnoldDecision

        meta = getattr(context, "metadata", {}) or {}
        layer = meta.get("layer", "phase")
        ctx_used = meta.get("context_retries_used", 0)
        ext_used = meta.get("external_retries_used", 0)
        blk_used = meta.get("blocked_retries_used", 0)
        phase = meta.get("phase", "")

        megaplan_decision = self.classify(
            error,
            layer,
            context_retries_used=ctx_used,
            external_retries_used=ext_used,
            blocked_retries_used=blk_used,
            phase=phase,
        )

        budget_consumed: dict[str, Any] = {}
        if megaplan_decision.budget_kind:
            budget_consumed["budget_kind"] = megaplan_decision.budget_kind
        if megaplan_decision.budget_delta:
            budget_consumed["budget_delta"] = megaplan_decision.budget_delta
        if megaplan_decision.halt_kind:
            budget_consumed["halt_kind"] = megaplan_decision.halt_kind

        return ArnoldDecision(
            status="decided",
            action=megaplan_decision.action,
            reason=megaplan_decision.reason,
            budget_consumed=budget_consumed,
        )


__all__ = [
    "Action",
    "HaltKind",
    "RecoveryDecision",
    "RecoveryPolicy",
    "DEFAULT_MAX_CONTEXT_RETRIES",
    "DEFAULT_MAX_EXTERNAL_RETRIES",
    "DEFAULT_MAX_BLOCKED_RETRIES",
    "EXTERNAL_RETRYABLE_PHASES",
    "EXTERNAL_RETRYABLE_LAYERS",
    "EXTERNAL_PERMANENT_ERROR_KINDS",
]
