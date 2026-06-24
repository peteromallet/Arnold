"""Native runtime hook protocol and no-op default implementation.

``NativeRuntimeHooks`` is the extension point through which downstream
slices (M3+) can inject behaviour into the native sequential walk-loop
without the native package importing Megaplan-specific code.

All 8 callbacks have documented insertion points and explicit no-op
defaults in ``NullNativeRuntimeHooks``.  The surface mirrors the
graph executor's ``ExecutorHooks`` protocol where possible, adapted
for the native runtime's dict-based context and ``NativeInstruction``
types.

Boundary discipline
-------------------
No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from arnold.pipeline.native.ir import NativeInstruction

__all__ = [
    "NativeRuntimeHooks",
    "NullNativeRuntimeHooks",
]


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
