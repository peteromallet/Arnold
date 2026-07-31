"""Native runtime hook protocol and no-op default implementation.

``NativeRuntimeHooks`` is the extension point through which downstream
slices (M3+) can inject behaviour into the native sequential walk-loop
without the native package importing Megaplan-specific code.

All 8 callbacks have documented insertion points and explicit no-op
defaults in ``NullNativeRuntimeHooks``.  The surface mirrors the
graph executor's ``ExecutorHooks`` protocol where possible, adapted
for the native runtime's dict-based context and ``NativeInstruction``
types.

Wrapping / delegation pattern
-----------------------------
The frozen ``NativeRuntimeHooks`` protocol is intentionally minimal.
Extension behaviour (trace emission, file-backed audit, retry wiring)
is added through **wrapping** — a hook wrapper accepts an inner
``NativeRuntimeHooks`` instance and delegates every callback to it
while adding its own behaviour:

* :class:`~arnold.pipeline.native.trace.NativeTraceHooks` — emits
  native-trace artifacts (``state.json``, ``events.ndjson``, etc.)
  when a ``trace_dir`` is configured.
* :class:`~arnold.pipeline.native.audit.AuditHooks` — writes
  file-backed audit records (``audit.ndjson``) recording per-attempt
  step outcomes, timestamps, and error details when an ``audit_dir``
  is configured.

Both wrappers are pure pass-throughs when their output directory is
``None``, so callers pay zero overhead beyond attribute access.

Boundary discipline
-------------------
No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, runtime_checkable

from arnold.kernel.effect import EffectDescriptor, EffectKind
from arnold.kernel.effect_ledger import EffectLedger, EffectRecordState
from arnold.pipeline.native.ir import NativeInstruction
from arnold.workflow.native_wbc import NativeWbcAttempt, begin_native_wbc_attempt

__all__ = [
    "DuplicateFulfilledAction",
    "EffectLedgerHooks",
    "NativeRuntimeHooks",
    "NativeWbcHooks",
    "NullNativeRuntimeHooks",
]


DuplicateFulfilledAction = Literal["skip", "retry", "fail"]
_VALID_DUPLICATE_ACTIONS = frozenset({"skip", "retry", "fail"})


@runtime_checkable
class NativeRuntimeHooks(Protocol):
    """Structural protocol for native runtime extension points.

    Every method is called by :func:`run_native_pipeline` at the
    documented insertion point.  Implementations that only need a
    subset of callbacks may inherit from :class:`NullNativeRuntimeHooks`
    and override what they need.

    **Frozen surface** — no new callbacks may be added during M1.
    """

    def on_step_start(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        """Insertion point: immediately before ``instr.func(ctx)``.

        May return a rewritten context dict (e.g. to inject per-step
        resources or rewrite bound parameters).

        No-op default: returns *ctx* unchanged.
        """
        ...

    def on_step_end(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
    ) -> Any:
        """Insertion point: immediately after ``instr.func(ctx)`` returns.

        May return a rewritten result (e.g. to verify outputs or
        inject metadata).

        No-op default: returns *result* unchanged.
        """
        ...

    def on_step_error(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        exc: BaseException,
    ) -> None:
        """Insertion point: when ``instr.func(ctx)`` raises an exception.

        The exception propagates from the runtime regardless; this
        callback is for telemetry and error-record writing only.

        No-op default: does nothing.
        """
        ...

    def merge_state(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        outputs: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> tuple[dict[str, Any], frozenset[str]]:
        """Insertion point: after outputs are merged into state.

        Receives the post-merge state and owned-key accumulator;
        returns ``(new_state, new_owned_keys)``.  The runtime uses
        the returned state for subsequent phases.

        No-op default: returns ``(state, owned_keys)`` unchanged.
        """
        ...

    def join_envelope(
        self,
        instr: NativeInstruction,
        current_envelope: Any,
        step_envelope: Any,
    ) -> Any:
        """Insertion point: envelope accumulation after each step completes.

        No-op default: returns *step_envelope* when truthy, else
        *current_envelope*.
        """
        ...

    def should_suspend(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        result: Any,
    ) -> tuple[bool, str | None]:
        """Insertion point: after state merge, before advancing pc.

        One of the terminal walk-loop exits.  Returns
        ``(should_suspend, reason)``.  When *should_suspend* is
        ``True``, the runtime stops executing and returns.

        No-op default: returns ``(False, None)``.
        """
        ...

    def should_halt_loop(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        iteration: int,
    ) -> tuple[bool, str | None]:
        """Insertion point: at the start of each loop iteration (before body).

        One of the terminal walk-loop exits.  Covers iteration limits,
        cost-based abort, and stall detection.

        No-op default: returns ``(False, None)``.
        """
        ...

    def on_stage_complete(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
        state: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> None:
        """Insertion point: at every normal stage completion.

        Called for normal phase completions before the runtime advances
        to the next instruction.  Covers state-merge-to-disk, telemetry,
        and suspension-cursor persistence for downstream implementations.

        No-op default: does nothing.
        """
        ...

    def on_checkpoint(
        self,
        cursor: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        """Insertion point: after cursor persistence and after clean final completion.

        Fired with the serialised cursor dict and final working state so
        downstream hooks can react to durable checkpoint writes (e.g.
        publish telemetry, write auxiliary artifacts, or notify observers).

        Called:
        * Immediately after :func:`~arnold.pipeline.native.checkpoint.persist_native_cursor`
          writes the resume cursor on max_phases suspension.
        * After the walk-loop exits normally (clean completion, no suspension).

        Not called on exception paths or early returns.

        No-op default: does nothing.
        """
        ...


class NullNativeRuntimeHooks:
    """No-op reference implementation of :class:`NativeRuntimeHooks`.

    Every method implements the documented no-op default.  Passing an
    instance to :func:`run_native_pipeline` produces identical behavior
    to the ``hooks=None`` path.

    ``halt_reason`` is set by the runtime when any terminal exit fires.
    """

    halt_reason: str | None

    def __init__(self) -> None:
        self.halt_reason = None

    def on_step_start(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        return ctx

    def on_step_end(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
    ) -> Any:
        return result

    def on_step_error(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        exc: BaseException,
    ) -> None:
        pass

    def merge_state(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        outputs: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> tuple[dict[str, Any], frozenset[str]]:
        return state, owned_keys

    def join_envelope(
        self,
        instr: NativeInstruction,
        current_envelope: Any,
        step_envelope: Any,
    ) -> Any:
        return step_envelope if step_envelope else current_envelope

    def should_suspend(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        result: Any,
    ) -> tuple[bool, str | None]:
        return False, None

    def should_halt_loop(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        iteration: int,
    ) -> tuple[bool, str | None]:
        return False, None

    def on_stage_complete(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
        state: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> None:
        pass

    def on_checkpoint(
        self,
        cursor: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        pass


class EffectLedgerHooks:
    """Hook wrapper that tracks side-effect lifecycle in an EffectLedger."""

    halt_reason: str | None

    def __init__(
        self,
        inner: NativeRuntimeHooks | None = None,
        *,
        duplicate_fulfilled_action: DuplicateFulfilledAction = "skip",
        effect_protocol: Any = None,
        artifact_root: str | Path | None = None,
        program_name: str = "",
    ) -> None:
        if duplicate_fulfilled_action not in _VALID_DUPLICATE_ACTIONS:
            raise ValueError(
                "duplicate_fulfilled_action must be one of 'skip', 'retry', or 'fail'"
            )
        self._inner: NativeRuntimeHooks = (
            inner if inner is not None else NullNativeRuntimeHooks()
        )
        self._ledger = EffectLedger()
        self._duplicate_fulfilled_action = duplicate_fulfilled_action
        self._active_effect_metadata: dict[str, Any] | None = None
        self._last_effect_metadata: dict[str, Any] | None = None
        self.halt_reason = None
        # Step 9A: optional WBC effect-protocol adapter for durable
        # intent persistence and gated dispatch.
        self._effect_protocol = effect_protocol
        # Tracking counters for test verification (Step 9A).
        self.wbc_intents_persisted: int = 0
        self.wbc_dispatches: int = 0
        self.wbc_zero_call_blocks: int = 0
        # Step 4: durable effect-ledger WBC evidence surface.
        self._wbc: NativeWbcAttempt = begin_native_wbc_attempt(
            artifact_root,
            producer_family="arnold_native",
            surface="effect_ledger_hooks",
            subject={"program": program_name},
            start_payload={"program": program_name},
        )

    def _build_effect_descriptor(self, instr: NativeInstruction) -> EffectDescriptor | None:
        if not instr.operation or not instr.idempotency_key:
            return None
        return EffectDescriptor(
            effect_id=f"{instr.name or instr.op}__pc{instr.pc}",
            kind=EffectKind.INTENT,
            target=instr.target or "",
            idempotency_key=instr.idempotency_key,
            payload_schema_hash="",
        )

    def _build_effect_metadata(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        *,
        lifecycle_state: str,
        duplicate_action: str | None,
    ) -> dict[str, Any]:
        attempt = ctx.get("attempt")
        return {
            "idempotency_key": instr.idempotency_key,
            "step_path": ctx.get("step_path"),
            "operation": instr.operation,
            "target": instr.target,
            "attempt": attempt if isinstance(attempt, int) else 1,
            "lifecycle_state": lifecycle_state,
            "effect_class": instr.effect_class,
            "duplicate_action": duplicate_action,
        }

    def checkpoint_effect_metadata(self) -> dict[str, Any] | None:
        """Return a copy of the most recent effect metadata snapshot."""
        if self._last_effect_metadata is None:
            return None
        return dict(self._last_effect_metadata)

    def _persist_wbc_durable_intent(
        self,
        instr: NativeInstruction,
        descriptor: EffectDescriptor,
        ctx: dict[str, Any],
    ) -> None:
        """Step 9A: persist durable intent through the WBC protocol.

        Called from ``on_step_start`` when a protocol is attached.
        If this raises, the caller propagates the error — the inner
        handler and instruction func are never invoked (zero-call-on-
        failure).
        """
        if self._effect_protocol is None:
            return
        intent_payload = {
            "effect_id": descriptor.effect_id,
            "kind": descriptor.kind.value,
            "target": descriptor.target,
            "idempotency_key": descriptor.idempotency_key,
            "step_path": ctx.get("step_path"),
            "operation": instr.operation,
        }
        try:
            self._effect_protocol.persist_durable_intent(
                idempotency_key=descriptor.idempotency_key,
                intent_payload=intent_payload,
            )
            self.wbc_intents_persisted += 1
        except Exception:
            self.wbc_zero_call_blocks += 1
            raise

    def on_step_start(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        ctx = self._inner.on_step_start(instr, ctx)
        descriptor = self._build_effect_descriptor(instr)
        if descriptor is None:
            self._active_effect_metadata = None
            return ctx

        # Step 9A: persist durable intent through the WBC protocol before
        # the step executes.  If this raises, the inner handler and the
        # instruction func are never invoked (zero-call-on-failure).
        self._persist_wbc_durable_intent(instr, descriptor, ctx)

        # Step 4: durable effect_intent WBC evidence.
        self._wbc.effect_intent(
            descriptor.effect_id,
            payload={
                "idempotency_key": descriptor.idempotency_key,
                "target": descriptor.target,
                "operation": instr.operation,
            },
        )

        prerecorded = self._ledger.prerecord(descriptor)
        record = self._ledger.get_record(descriptor.idempotency_key)
        duplicate_action: str | None = None
        lifecycle_state = EffectRecordState.INTENDED.value
        if record is not None:
            lifecycle_state = record.state.value
            if not prerecorded:
                duplicate_action = (
                    self._duplicate_fulfilled_action
                    if record.state is EffectRecordState.FULFILLED
                    else "retry"
                )
                # Step 4: durable reconciliation WBC evidence for duplicates.
                self._wbc.reconciliation(
                    descriptor.effect_id,
                    outcome=duplicate_action,
                    payload={
                        "idempotency_key": descriptor.idempotency_key,
                        "lifecycle_state": lifecycle_state,
                    },
                )

        metadata = self._build_effect_metadata(
            instr,
            ctx,
            lifecycle_state=lifecycle_state,
            duplicate_action=duplicate_action,
        )
        ctx["effect"] = dict(metadata)
        self._active_effect_metadata = dict(metadata)
        self._last_effect_metadata = dict(metadata)
        return ctx

    def on_step_end(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
    ) -> Any:
        result = self._inner.on_step_end(instr, ctx, result)
        effect_ctx = ctx.get("effect")
        if isinstance(effect_ctx, dict) and effect_ctx.get("duplicate_action") is not None:
            if self._active_effect_metadata is not None:
                self._last_effect_metadata = dict(self._active_effect_metadata)
            self._active_effect_metadata = None
            return result
        if self._active_effect_metadata is not None and instr.idempotency_key:
            self._ledger.mark_fulfilled(instr.idempotency_key)
            self._active_effect_metadata["lifecycle_state"] = (
                EffectRecordState.FULFILLED.value
            )
            self._last_effect_metadata = dict(self._active_effect_metadata)
            self._active_effect_metadata = None
            # Step 9A: record COMPLETED outcome through protocol if attached.
            if self._effect_protocol is not None:
                self.wbc_dispatches += 1
                self._effect_protocol.record_outcome(
                    idempotency_key=instr.idempotency_key,
                    outcome="COMPLETED",
                )
            # Step 4: durable effect_outcome WBC evidence.
            self._wbc.effect_outcome(
                instr.operation or instr.name or "step",
                status="COMPLETED",
                payload={"idempotency_key": instr.idempotency_key},
            )
        return result

    def on_step_error(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        exc: BaseException,
    ) -> None:
        self._inner.on_step_error(instr, ctx, exc)
        effect_ctx = ctx.get("effect")
        if isinstance(effect_ctx, dict) and effect_ctx.get("duplicate_action") is not None:
            if self._active_effect_metadata is not None:
                self._last_effect_metadata = dict(self._active_effect_metadata)
            self._active_effect_metadata = None
            return
        if self._active_effect_metadata is not None and instr.idempotency_key:
            self._ledger.mark_failed(instr.idempotency_key)
            self._active_effect_metadata["lifecycle_state"] = (
                EffectRecordState.FAILED.value
            )
            self._last_effect_metadata = dict(self._active_effect_metadata)
            self._active_effect_metadata = None
            # Step 9A: record FAILED outcome through protocol if attached.
            if self._effect_protocol is not None:
                self._effect_protocol.record_outcome(
                    idempotency_key=instr.idempotency_key,
                    outcome="FAILED",
                    detail={"error": str(exc)},
                )
            # Step 4: durable effect_outcome WBC evidence.
            self._wbc.effect_outcome(
                instr.operation or instr.name or "step",
                status="FAILED",
                payload={"idempotency_key": instr.idempotency_key, "error": str(exc)},
            )

    def merge_state(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        outputs: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> tuple[dict[str, Any], frozenset[str]]:
        return self._inner.merge_state(instr, state, outputs, owned_keys)

    def join_envelope(
        self,
        instr: NativeInstruction,
        current_envelope: Any,
        step_envelope: Any,
    ) -> Any:
        return self._inner.join_envelope(instr, current_envelope, step_envelope)

    def should_suspend(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        result: Any,
    ) -> tuple[bool, str | None]:
        return self._inner.should_suspend(instr, state, result)

    def should_halt_loop(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        iteration: int,
    ) -> tuple[bool, str | None]:
        return self._inner.should_halt_loop(instr, state, iteration)

    def on_stage_complete(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
        state: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> None:
        self._inner.on_stage_complete(instr, ctx, result, state, owned_keys)

    def on_checkpoint(
        self,
        cursor: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        self._inner.on_checkpoint(cursor, state)

    def record_cancellation(
        self,
        cancellation: dict[str, Any],
        *,
        state: dict[str, Any] | None = None,
    ) -> None:
        callback = getattr(self._inner, "record_cancellation", None)
        if callable(callback):
            callback(cancellation, state=state)


class NativeWbcHooks:
    """Delegating ``NativeRuntimeHooks`` wrapper that emits durable WBC evidence.

    Wraps an inner ``NativeRuntimeHooks`` and records start, step-effect,
    checkpoint, error, and terminal/close events under
    ``<artifact_root>/.native_wbc/arnold_native/hooks`` while delegating the
    actual hook work to the inner instance.

    ``close`` is idempotent — calling it more than once is a safe no-op.
    """

    halt_reason: str | None

    def __init__(
        self,
        inner: NativeRuntimeHooks | None = None,
        *,
        artifact_root: str | Path | None = None,
        program_name: str = "",
        run_id: str = "",
        plugin_id: str = "",
        manifest_hash: str = "",
    ) -> None:
        self._inner: NativeRuntimeHooks = (
            inner if inner is not None else NullNativeRuntimeHooks()
        )
        self._wbc: NativeWbcAttempt = begin_native_wbc_attempt(
            artifact_root,
            producer_family="arnold_native",
            surface="hooks",
            run_id=run_id,
            plugin_id=plugin_id,
            manifest_hash=manifest_hash,
            subject={"program": program_name},
            start_payload={"program": program_name},
        )
        self._closed: bool = False
        self.halt_reason: str | None = None

    # ── NativeRuntimeHooks delegation + WBC evidence ───────────────

    def on_step_start(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        ctx = self._inner.on_step_start(instr, ctx)
        self._wbc.effect(
            "on_step_start",
            {"op": instr.op, "name": instr.name},
        )
        return ctx

    def on_step_end(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
    ) -> Any:
        result = self._inner.on_step_end(instr, ctx, result)
        self._wbc.effect(
            "on_step_end",
            {"op": instr.op, "name": instr.name},
        )
        return result

    def on_step_error(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        exc: BaseException,
    ) -> None:
        self._inner.on_step_error(instr, ctx, exc)
        self._wbc.effect(
            "on_step_error",
            {"op": instr.op, "name": instr.name, "error": str(exc)},
        )

    def merge_state(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        outputs: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> tuple[dict[str, Any], frozenset[str]]:
        return self._inner.merge_state(instr, state, outputs, owned_keys)

    def join_envelope(
        self,
        instr: NativeInstruction,
        current_envelope: Any,
        step_envelope: Any,
    ) -> Any:
        return self._inner.join_envelope(instr, current_envelope, step_envelope)

    def should_suspend(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        result: Any,
    ) -> tuple[bool, str | None]:
        return self._inner.should_suspend(instr, state, result)

    def should_halt_loop(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        iteration: int,
    ) -> tuple[bool, str | None]:
        return self._inner.should_halt_loop(instr, state, iteration)

    def on_stage_complete(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
        state: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> None:
        self._inner.on_stage_complete(instr, ctx, result, state, owned_keys)

    def on_checkpoint(
        self,
        cursor: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        self._inner.on_checkpoint(cursor, state)
        self._wbc.effect("on_checkpoint", {})

    def record_cancellation(
        self,
        cancellation: dict[str, Any],
        *,
        state: dict[str, Any] | None = None,
    ) -> None:
        callback = getattr(self._inner, "record_cancellation", None)
        if callable(callback):
            callback(cancellation, state=state)
        payload = dict(cancellation) if isinstance(cancellation, Mapping) else {}
        self._wbc.effect("record_cancellation", payload)

    def record_run_init(
        self,
        program: Any,
        *,
        run_path: str,
        pack_provenance: Mapping[str, Any] | None = None,
    ) -> None:
        """Preserve optional run-provenance callbacks through the wrapper."""
        callback = getattr(self._inner, "record_run_init", None)
        if callable(callback):
            callback(
                program,
                run_path=run_path,
                pack_provenance=pack_provenance,
            )

    # ── Idempotent close ───────────────────────────────────────────

    def close(
        self,
        *,
        status: str = "completed",
        outcome: str = "result",
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        """Emit the terminal record for this hooks surface.

        Idempotent: a second call is a silent no-op.  Also delegates to the
        inner hook's ``close`` (if any) so that chained wrappers flush their
        own evidence.
        """
        if self._closed:
            return
        self._wbc.terminal(status=status, outcome=outcome, payload=payload or {})
        inner_close = getattr(self._inner, "close", None)
        if callable(inner_close):
            inner_close(status=status, outcome=outcome, payload=payload)
        self._closed = True
