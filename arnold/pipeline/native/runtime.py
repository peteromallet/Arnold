"""Native sequential runtime state machine.

Walks a compiled :class:`NativeProgram` one instruction at a time,
invokes phase/decision callables with a minimal dictionary context,
merges state like the graph executor, and persists resume cursors
when execution is interrupted by a ``max_phases`` limit.

The runtime does NOT import megaplan or register production pipelines.
It is gated behind ``require_native_runtime()`` at the entrypoint level
and is otherwise a pure library module.

Parity with graph executor
--------------------------
- Envelope propagation via ``hooks.join_envelope``.
- Callable return normalization (dict, StepResult, ContractResult).
- Schema-registry-backed handoff via ``StepIOContractContext``.
- ``state["__contract_results__"]`` publication matching executor shape.
- Telemetry-sink handling via ``telemetry_path``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4
from uuid import uuid4
from uuid import uuid4

from arnold.pipeline.native.checkpoint import (
    persist_native_cursor,
    read_native_cursor,
)
from arnold.pipeline.native.context import require_native_runtime
from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import (
    NativeInstruction,
    NativeProgram,
)
from arnold.pipeline.native.trace import NativeTraceHooks


class NativeRuntimeError(Exception):
    """Raised by the native runtime for execution-time contract violations.

    Examples include a decision returning a label outside its declared
    vocabulary or a loop guard that cannot resolve a valid branch.
    """


class NativeExecutionResult:
    """Result returned by :func:`run_native_pipeline`.

    Carries the final working state, the ordered list of completed
    stage identifiers, the accumulated envelope, and an optional path
    to the persisted resume cursor (set when execution was interrupted
    by ``max_phases``).
    """

    def __init__(
        self,
        *,
        state: dict[str, Any],
        stages: list[str],
        pc: int,
        suspended: bool = False,
        cursor_path: str | None = None,
        envelope: Any = None,
    ) -> None:
        self.state = state
        self.stages = stages
        self.pc = pc
        self.suspended = suspended
        self.cursor_path = cursor_path
        self.envelope = envelope


def _normalize_phase_result(result: Any, stage_id: str) -> tuple[dict[str, Any], Any]:
    """Normalize a phase return value into (outputs_dict, contract_result_or_none).

    Handles the same shapes the graph executor normalizes via StepResult:

    * dict → outputs, no contract_result
    * object with ``.outputs`` → that dict, no contract_result
    * object with ``.contract_result`` → outputs (from .outputs or .payload),
      plus the ContractResult for ``__contract_results__`` publication
    * anything else → empty outputs, no contract_result
    """
    contract_result: Any = None
    outputs: dict[str, Any] = {}

    if isinstance(result, dict):
        outputs = result
    elif hasattr(result, "outputs"):
        raw = getattr(result, "outputs", None)
        if isinstance(raw, dict):
            outputs = raw
        # Extract contract_result if present (graph-executor StepResult pattern)
        cr = getattr(result, "contract_result", None)
        if cr is not None:
            contract_result = cr
            # If this is a ContractResult with a .payload, also merge payload
            # into outputs so downstream phases see the carried data.
            cr_payload = getattr(cr, "payload", None)
            if isinstance(cr_payload, dict) and not outputs:
                outputs = dict(cr_payload)
    else:
        outputs = {}

    return outputs, contract_result


def _enforce_native_typed_handoff(
    *,
    instr: NativeInstruction,
    handoff_value: Any,
    instructions: tuple[NativeInstruction, ...],
    artifact_root: str,
    schema_registry: Any = None,
    telemetry_path: str | None = None,
    hooks: Any = None,
    state: dict[str, Any] | None = None,
) -> None:
    """Enforce typed step-IO handoff for a phase with typed produces ports.

    Matches the graph executor's ``_enforce_typed_step_io_handoff`` semantics:
    walks the instruction list for consumer phases whose ``consumes``
    declarations reference this producer's port names, calls
    ``evaluate_step_io_handoff`` for each pair (with a
    ``StepIOContractContext`` when *schema_registry* is provided), and
    raises ``StepIOEnforcementError`` when the resolved policy blocks
    the write.

    When *hooks* provides a ``resolve_step_io_policy`` callback that returns
    a non-``None`` policy, that policy is forwarded to
    ``evaluate_step_io_handoff`` as the ``policy`` argument, bypassing the
    evaluator's default ``resolve_step_io_policy`` call.  This is the seam
    through which Megaplan (and future slices) can inject
    ``resolve_megaplan_step_io_policy()`` without the native package
    importing Megaplan code.

    Falls through (no-op) when:
      * The phase has no typed ``produces`` ports.
      * No consumer references any producer port name.
      * Either side resolves to non-typed (gradual-typing pass-through).
      * The resolved policy does not enforce.
    """
    produces = getattr(instr, "produces", ()) or ()
    if not produces:
        return

    # Collect consumer phases that reference these producer ports
    consumers: list[tuple[NativeInstruction, Any, Any]] = []
    for other in instructions:
        if other.op != "phase" or other.pc == instr.pc:
            continue
        other_consumes = getattr(other, "consumes", ()) or ()
        for consumer_port in other_consumes:
            port_name = getattr(consumer_port, "port_name", getattr(consumer_port, "name", ""))
            for producer_port in produces:
                if getattr(producer_port, "name", "") == port_name:
                    consumers.append((other, producer_port, consumer_port))
                    break

    if not consumers:
        return

    # Lazy imports — keep the no-typed-ports path import-free
    from arnold.pipeline.step_io_contract import StepIOContractContext, StepIOOperation
    from arnold.pipeline.step_io_handoff import evaluate_step_io_handoff
    from arnold.pipeline.step_io_policy import effective_blocks_write
    from arnold.pipeline.executor import StepIOEnforcementError

    # ── Resolve policy via hooks (seam for Megaplan injection) ────────
    policy_override: Any = None
    if hooks is not None and hasattr(hooks, "resolve_step_io_policy"):
        policy_override = hooks.resolve_step_io_policy(
            instr=instr,
            state=state or {},
            handoff_value=handoff_value,
            schema_registry=schema_registry,
        )

    # Build contract context when a schema registry is available
    context = None
    if schema_registry is not None:
        context = StepIOContractContext(
            operation=StepIOOperation.WRITE,
            registry=schema_registry,
            fail_closed_on_write=True,
        )

    for consumer_instr, producer_port, consumer_port in consumers:
        handoff = evaluate_step_io_handoff(
            handoff_value,
            operation=StepIOOperation.WRITE,
            context=context,
            policy=policy_override,
            producer_port=producer_port,
            consumer_port_decl=consumer_port,
            consumer_step=consumer_instr.name,
            producer_stage=instr.name,
            artifact=f"{instr.name}.{getattr(producer_port, 'name', '')}",
            telemetry_path=telemetry_path,
        )
        if effective_blocks_write(handoff.decision, handoff.policy):
            raise StepIOEnforcementError(
                f"step IO enforced violation at native phase "
                f"{instr.name}->{consumer_instr.name}: "
                f"{handoff.decision.block_reason}"
            )


def run_native_pipeline(
    program: NativeProgram,
    *,
    artifact_root: str | Path = ".",
    initial_state: dict[str, Any] | None = None,
    max_phases: int | None = None,
    resume: bool = False,
    hooks: NativeRuntimeHooks | None = None,
    schema_registry: Any = None,
    telemetry_path: str | Path | None = None,
    initial_envelope: Any = None,
    trace_dir: str | Path | None = None,
) -> NativeExecutionResult:
    """Execute a compiled native pipeline program sequentially.

    Walks *program.instructions* starting from pc 0 (or a saved pc when
    *resume* is ``True`` and a cursor exists under *artifact_root*).
    Each ``phase`` instruction invokes its callable with a lightweight
    context dict, merges ``outputs`` into working state like the graph
    executor, and advances the program counter.  ``decision`` instructions
    route via return-value→branch lookup.  ``jump`` instructions follow
    their ``next_pc`` link.  Execution stops at ``halt`` or after
    *max_phases* phase completions.

    When *max_phases* is reached, the runtime persists a resume cursor
    via :func:`persist_native_cursor` (including the working state under
    a ``__state__`` key in the ``frames`` dict) and returns with
    ``suspended=True``.  The caller can later call this function again
    with ``resume=True`` to continue from the saved point.

    Envelope propagation follows the graph executor pattern: after each
    phase and decision, ``hooks.join_envelope`` is called to accumulate
    the step envelope.  The final accumulated envelope is returned in
    :attr:`NativeExecutionResult.envelope`.

    When *schema_registry* is provided, typed step-IO handoff evaluation
    passes a ``StepIOContractContext`` so schema-version checks match
    graph executor behavior.

    Args:
        program: A compiled :class:`NativeProgram`.
        artifact_root: Directory for reading/writing the resume cursor.
        initial_state: Starting working state dict (default empty).
        max_phases: Maximum number of ``phase`` instructions to execute
            before suspending (``None`` → no limit).
        resume: If ``True``, attempt to read a cursor from *artifact_root*
            and start from its saved pc and state.
        hooks: Optional :class:`NativeRuntimeHooks` for injecting
            lifecycle behaviour.  When ``None`` (the default), a
            :class:`NullNativeRuntimeHooks` instance is used internally
            so all callbacks are no-ops.
        schema_registry: Optional contract schema registry used by
            typed step-IO handoff evaluation (forwarded to
            ``StepIOContractContext``).  When ``None``, no registry
            lookup is performed.
        telemetry_path: Optional path for step-IO telemetry sink
            (forwarded to ``evaluate_step_io_handoff``).
        initial_envelope: Starting envelope value for ``join_envelope``
            accumulation (default ``None``).
        trace_dir: Optional directory for parity-trace emission.  When
            set, a :class:`NativeTraceHooks` wrapper is layered over
            *hooks* to write ``state.json``, ``events.ndjson``,
            artifact inventory, stage sequence, and final checkpoint
            notification.  When ``None`` (the default), no trace files
            are emitted and behaviour is identical to previous versions.

    Returns:
        :class:`NativeExecutionResult` with final state, completed stages,
        current pc, suspension status, and accumulated envelope.
    """
    require_native_runtime()

    # Resolve hooks — always have a hooks instance so the runtime never
    # needs None-guards around callback invocations.
    _hooks: NativeRuntimeHooks = hooks if hooks is not None else NullNativeRuntimeHooks()

    # ── Wrap with trace hooks when trace_dir is set ────────────────
    if trace_dir is not None:
        _hooks = NativeTraceHooks(
            inner=_hooks,
            trace_dir=trace_dir,
            artifact_root=artifact_root,
        )

    state: dict[str, Any] = dict(initial_state) if initial_state is not None else {}
    stages: list[str] = []
    owned_keys: frozenset[str] = frozenset()
    prefix = _safe_name(program.name)

    # ── envelope accumulation (matches graph executor pattern) ─────
    envelope: Any = initial_envelope

    instructions = program.instructions
    if not instructions:
        return NativeExecutionResult(state=state, stages=stages, pc=0, envelope=envelope)

    # ── resolve starting pc and restore state from cursor ────────────
    start_pc = 0
    loops: dict[str, int] = {}
    frames: dict[str, Any] = {}

    if resume:
        cursor = read_native_cursor(artifact_root)
        if cursor is not None:
            start_pc = cursor["native"]["pc"]
            stages = list(cursor.get("stages", []))
            loops = dict(cursor.get("loops", {}))
            frames = dict(cursor.get("frames", {}))
            # Restore working state from cursor if present
            saved_state = frames.pop("__state__", None)
            if isinstance(saved_state, dict):
                state = saved_state
            # Restore envelope from cursor frames if present
            saved_envelope = frames.pop("__envelope__", None)
            if saved_envelope is not None:
                envelope = saved_envelope

    # ── resolve cursor_id (stable across suspension/resume) ──────────
    _cursor_id: str | None = None
    if resume:
        _cursor = read_native_cursor(artifact_root)
        if _cursor is not None:
            _cursor_id = _cursor.get("cursor_id")
    if _cursor_id is None:
        _cursor_id = uuid4().hex

    # ── pre-validate pc ──────────────────────────────────────────────
    if start_pc < 0 or start_pc >= len(instructions):
        return NativeExecutionResult(state=state, stages=stages, pc=start_pc, envelope=envelope)

    telemetry_path_str: str | None = None
    if telemetry_path is not None:
        telemetry_path_str = str(telemetry_path)

    phase_count = 0
    pc = start_pc
    forward_visited: set[int] = set()

    while 0 <= pc < len(instructions):
        instr = instructions[pc]

        if instr.op == "halt":
            break

        elif instr.op == "phase":
            if instr.func is None:
                # Phase with no callable — skip
                pc = instr.next_pc if instr.next_pc is not None else pc + 1
                continue

            stage_id = f"{prefix}__{instr.name}__pc{pc}"

            # Build lightweight context (dict-based, no StepContext dependency)
            ctx: dict[str, Any] = {
                "state": dict(state),
                "inputs": dict(state),
            }
            if isinstance(artifact_root, Path):
                ctx["artifact_root"] = str(artifact_root)
            else:
                ctx["artifact_root"] = str(artifact_root)

            # Include contract_results in context (matching _build_ctx pattern)
            contract_results_published = state.get("__contract_results__")
            if isinstance(contract_results_published, dict):
                ctx["contract_results"] = dict(contract_results_published)

            # ── Hook: on_step_start (may rewrite ctx) ─────────────
            ctx = _hooks.on_step_start(instr, ctx)

            # Invoke the phase
            try:
                result = instr.func(ctx)
            except BaseException as exc:
                _hooks.on_step_error(instr, ctx, exc)
                raise

            # ── Hook: on_step_end (may rewrite result) ────────────
            result = _hooks.on_step_end(instr, ctx, result)

            # ── Callable return normalization (matching graph executor) ──
            outputs, contract_result = _normalize_phase_result(result, stage_id)

            # ── Resolve handoff value for typed enforcement ────────
            # Graph executor pattern: prefers contract_result, falls back
            # to outputs[stage.name], then None.
            handoff_value: Any = None
            if contract_result is not None:
                handoff_value = contract_result
            elif outputs:
                handoff_value = outputs.get(instr.name)
            if handoff_value is None and outputs:
                # Last resort: use the full outputs dict as handoff value
                # (matches native runtime's existing behavior for plain dicts)
                handoff_value = outputs

            # ── Typed step-IO handoff enforcement ──────────────────
            # Runs BEFORE the outputs/state merge so state is unchanged
            # when an enforce-block fires — matches graph executor behavior.
            artifact_root_str = str(artifact_root) if not isinstance(artifact_root, str) else artifact_root
            if handoff_value is not None:
                _enforce_native_typed_handoff(
                    instr=instr,
                    handoff_value=handoff_value,
                    instructions=instructions,
                    artifact_root=artifact_root_str,
                    schema_registry=schema_registry,
                    telemetry_path=telemetry_path_str,
                    hooks=_hooks,
                    state=state,
                )

            if outputs:
                state.update(outputs)

            # ── Publish contract_result into routing surface ───────
            # Matches graph executor: ``state["__contract_results__"][stage.name] = contract_result``
            if contract_result is not None:
                published = state.get("__contract_results__")
                if not isinstance(published, dict):
                    published = {}
                    state["__contract_results__"] = published
                published[instr.name] = contract_result

            # ── Hook: merge_state (may rewrite state / owned_keys) ──
            state, owned_keys = _hooks.merge_state(instr, state, outputs, owned_keys)

            # ── Envelope accumulation ─────────────────────────────
            step_envelope: Any = None
            if hasattr(result, "envelope"):
                step_envelope = result.envelope
            elif isinstance(result, dict):
                step_envelope = result.get("envelope")
            envelope = _hooks.join_envelope(instr, envelope, step_envelope)

            # ── Hook: should_suspend (terminal exit) ────────────────
            do_suspend, suspend_reason = _hooks.should_suspend(instr, state, result)
            if do_suspend:
                _hooks.on_stage_complete(instr, ctx, result, state, owned_keys)
                if hasattr(_hooks, "halt_reason"):
                    _hooks.halt_reason = suspend_reason  # type: ignore[attr-defined]
                return NativeExecutionResult(
                    state=dict(state),
                    stages=list(stages),
                    pc=pc,
                    suspended=True,
                    cursor_path=str(Path(artifact_root) / "resume_cursor.json"),
                    envelope=envelope,
                )

            # Record completed stage only after successful phase completion
            stages.append(stage_id)
            phase_count += 1

            # Check max_phases limit (check AFTER merging, same as graph executor
            # which fires terminal exits after step completion)
            if max_phases is not None and phase_count >= max_phases:
                # ── Hook: on_stage_complete before suspension ──────
                _hooks.on_stage_complete(instr, ctx, result, state, owned_keys)
                # Advance pc to the next instruction for the resume point
                next_pc = instr.next_pc if instr.next_pc is not None else pc + 1
                _persist_suspension(
                    artifact_root=artifact_root,
                    stage=stage_id,
                    pc=next_pc,
                    stages=stages,
                    loops=loops,
                    frames=frames,
                    state=state,
                    envelope=envelope,
                    cursor_id=_cursor_id,
                )
                # ── Hook: on_checkpoint (after cursor persistence) ──
                _cursor = _build_cursor_dict(
                    stage=stage_id,
                    pc=next_pc,
                    stages=list(stages),
                    loops=dict(loops),
                    frames=dict(frames),
                    state=state,
                    envelope=envelope,
                    cursor_id=_cursor_id,
                )
                _hooks.on_checkpoint(_cursor, dict(state))
                return NativeExecutionResult(
                    state=dict(state),
                    stages=list(stages),
                    pc=next_pc,
                    suspended=True,
                    cursor_path=str(Path(artifact_root) / "resume_cursor.json"),
                    envelope=envelope,
                )

            # ── Hook: on_stage_complete (normal completion) ────────
            _hooks.on_stage_complete(instr, ctx, result, state, owned_keys)

            # Advance to next instruction
            pc = instr.next_pc if instr.next_pc is not None else pc + 1
            forward_visited.clear()

        elif instr.op == "decision":
            if instr.func is None:
                # No callable — can't route; halt
                break

            ctx: dict[str, Any] = {
                "state": dict(state),
                "inputs": dict(state),
            }
            if isinstance(artifact_root, Path):
                ctx["artifact_root"] = str(artifact_root)
            else:
                ctx["artifact_root"] = str(artifact_root)

            # ── Hook: on_step_start (may rewrite ctx / inject control override) ──
            ctx = _hooks.on_step_start(instr, ctx)

            # ── Control override short-circuit (Megaplan T7) ──────
            # When a hook (e.g. MegaplanNativeRuntimeHooks) resolves a
            # catalog-driven control override, skip the decision body and
            # route directly. Priority: halt > override > decision > normal.
            control_override: str | None = ctx.pop("__override_route__", None)
            if control_override is None:
                # Backward-compatibility for any older hook implementation.
                control_override = ctx.pop("__control_override__", None)
            if control_override is not None:
                override_label = control_override
                if instr.branches and control_override not in instr.branches:
                    override_label = "override" if "override" in instr.branches else None
                if override_label is not None:
                    # Build a synthetic result with envelope=None so the
                    # downstream envelope join is a no-op.
                    result = {"__override_route__": control_override}
                    result = _hooks.on_step_end(instr, ctx, result)
                    label = override_label
                else:
                    try:
                        result = instr.func(ctx)
                    except BaseException as exc:
                        _hooks.on_step_error(instr, ctx, exc)
                        raise
                    result = _hooks.on_step_end(instr, ctx, result)
                    label = _resolve_decision_label(result)
            else:
                try:
                    result = instr.func(ctx)
                except BaseException as exc:
                    _hooks.on_step_error(instr, ctx, exc)
                    raise
                result = _hooks.on_step_end(instr, ctx, result)

                # Resolve branch label
                label = _resolve_decision_label(result)

            # ── Envelope accumulation for decisions ───────────────
            step_envelope: Any = None
            if hasattr(result, "envelope"):
                step_envelope = result.envelope
            elif isinstance(result, dict):
                step_envelope = result.get("envelope")
            envelope = _hooks.join_envelope(instr, envelope, step_envelope)

            # ── Validate decision return value against declared vocabulary ──
            if instr.branches and label not in instr.branches:
                raise NativeRuntimeError(
                    f"Decision '{instr.name}' returned label {label!r} "
                    f"which is not in its declared vocabulary: "
                    f"{sorted(instr.branches.keys())}"
                )

            target_pc = instr.branches.get(label) if instr.branches else None

            if target_pc is not None and 0 <= target_pc < len(instructions):
                # ── Track loop iteration for loop guard decisions ──────
                _maybe_count_loop_iteration(
                    instr=instr,
                    label=label,
                    target_pc=target_pc,
                    program=program,
                    loops=loops,
                )

                # ── Hook: should_halt_loop (before loop body) ──────────
                # Fire when the decision is a loop guard routing to its body
                if _is_loop_body_entry(instr, target_pc, program):
                    iteration = loops.get(instr.name, 0)
                    do_halt, halt_reason = _hooks.should_halt_loop(instr, state, iteration)
                    if do_halt:
                        _hooks.on_stage_complete(instr, ctx, result, state, owned_keys)
                        if hasattr(_hooks, "halt_reason"):
                            _hooks.halt_reason = halt_reason  # type: ignore[attr-defined]
                        return NativeExecutionResult(
                            state=dict(state),
                            stages=list(stages),
                            pc=pc,
                            envelope=envelope,
                        )

                # ── Hook: on_edge_traverse (after non-halt target resolved) ──
                _hooks.on_edge_traverse(instr, state, label, target_pc)

                pc = target_pc
                forward_visited.clear()
            else:
                # No valid branch — halt
                break

        elif instr.op == "jump":
            next_pc = instr.next_pc if instr.next_pc is not None else pc + 1
            # Detect forward progress stall
            if next_pc == pc:
                break
            # Back-edge detection: if next_pc <= pc, this is a loop back-edge,
            # so clear the forward_visited set to allow revisiting.
            if next_pc <= pc:
                forward_visited.clear()
            elif next_pc in forward_visited:
                # Forward jump to an already visited pc → possible infinite loop
                break
            forward_visited.add(pc)
            pc = next_pc

        else:
            # Unknown op — treat as no-op and advance
            pc += 1

    # ── Hook: on_checkpoint (clean completion) ────────────────────────
    _clean_cursor = _build_cursor_dict(
        stage=stages[-1] if stages else "",
        pc=pc,
        stages=list(stages),
        loops=dict(loops),
        frames=dict(frames),
        state=state,
        envelope=envelope,
        final=True,
        cursor_id=_cursor_id,
    )
    _hooks.on_checkpoint(_clean_cursor, dict(state))

    return NativeExecutionResult(state=state, stages=stages, pc=pc, envelope=envelope)


# ── helpers ───────────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """Return a name safe for use as a stage-name prefix."""
    return name.replace(" ", "_").replace("-", "_")


def _resolve_decision_label(result: Any) -> str:
    """Resolve a decision return value to a branch label string."""
    if isinstance(result, str):
        return result
    if hasattr(result, "next") and isinstance(getattr(result, "next"), str):
        return result.next
    # Truthy/falsy fallback
    return "__truthy__" if result else "__falsy__"


def _maybe_count_loop_iteration(
    *,
    instr: NativeInstruction,
    label: str,
    target_pc: int,
    program: NativeProgram,
    loops: dict[str, int],
) -> None:
    """Increment the loop counter when a loop-guard decision enters its body.

    A loop guard is identified by matching *instr.func* against the
    ``guard`` callable of every :class:`NativeLoopGuard` in *program*.
    The body branch is the one with the smallest target program counter
    (the compiler emits the body before the exit path).  Only increments
    when the resolved *target_pc* matches the body branch.
    """
    for loop_guard in program.loop_guards:
        if loop_guard.guard is instr.func and instr.branches:
            # Body branch has the smallest target PC.
            body_pc = min(instr.branches.values())
            if target_pc == body_pc:
                loops[instr.name] = loops.get(instr.name, 0) + 1
            break


def _is_loop_body_entry(
    instr: NativeInstruction,
    target_pc: int,
    program: NativeProgram,
) -> bool:
    """Return ``True`` when *instr* is a loop guard routing to its body pc.

    Used by the hooks wiring to fire ``should_halt_loop`` at the right
    insertion point — after the guard evaluates but before the body runs.
    """
    for loop_guard in program.loop_guards:
        if loop_guard.guard is instr.func and instr.branches:
            body_pc = min(instr.branches.values())
            return target_pc == body_pc
    return False


def _build_cursor_dict(
    *,
    stage: str,
    pc: int,
    stages: list[str],
    loops: dict[str, int],
    frames: dict[str, Any],
    state: dict[str, Any],
    envelope: Any = None,
    final: bool = False,
    cursor_id: str | None = None,
) -> dict[str, Any]:
    """Build a cursor dict matching the shape written by :func:`persist_native_cursor`.

    The returned dict mirrors the on-disk ``resume_cursor.json`` shape so
    ``on_checkpoint`` receivers see exactly what was persisted.  When
    *final* is ``True`` (clean completion), a ``final`` marker is included.

    Includes additive ``cursor_id`` and ``stage_reentry_points`` for
    graph-compatible reentry metadata (M2 requirement).
    """
    from arnold.pipeline.native.checkpoint import NATIVE_CURSOR_VERSION

    frames_with_state = dict(frames)
    frames_with_state["__state__"] = dict(state)
    if envelope is not None:
        frames_with_state["__envelope__"] = envelope

    # Build stage_reentry_points from completed stages
    stage_reentry_points: dict[str, Any] = {}
    for stage_id in stages:
        # stage_id format: "prefix__phase_name__pcN"
        parts = stage_id.split("__")
        if len(parts) >= 2:
            phase_name = parts[-2]  # extract phase name
            stage_reentry_points[phase_name] = stage_id

    cursor: dict[str, Any] = {
        "stage": stage,
        "resume_cursor": None,
        "stages": list(stages),
        "loops": dict(loops),
        "frames": frames_with_state,
        "native": {
            "pc": pc,
            "version": NATIVE_CURSOR_VERSION,
        },
        "cursor_id": cursor_id,
        "stage_reentry_points": stage_reentry_points,
    }
    if final:
        cursor["final"] = True
    return cursor


def _persist_suspension(
    *,
    artifact_root: str | Path,
    stage: str,
    pc: int,
    stages: list[str],
    loops: dict[str, int],
    frames: dict[str, Any],
    state: dict[str, Any],
    envelope: Any = None,
    cursor_id: str | None = None,
) -> None:
    """Persist a resume cursor at the suspension point.

    The working *state* is stored under ``__state__`` in the *frames* dict
    so it can be restored on resume.  The *envelope* is stored under
    ``__envelope__`` so it survives suspension/resume cycles.

    Includes additive ``cursor_id`` and ``stage_reentry_points`` for
    graph-compatible reentry metadata (M2 requirement).
    """
    try:
        frames_with_state = dict(frames)
        frames_with_state["__state__"] = dict(state)
        if envelope is not None:
            frames_with_state["__envelope__"] = envelope

        # Build stage_reentry_points from completed stages
        stage_reentry_points: dict[str, Any] = {}
        for stage_id in stages:
            parts = stage_id.split("__")
            if len(parts) >= 2:
                phase_name = parts[-2]
                stage_reentry_points[phase_name] = stage_id

        persist_native_cursor(
            artifact_root,
            stage=stage,
            pc=pc,
            stages=list(stages),
            loops=dict(loops),
            frames=frames_with_state,
            cursor_id=cursor_id,
            stage_reentry_points=stage_reentry_points,
        )
    except Exception:
        # Best-effort: if persist fails, execution result still carries
        # the pc/stages so the caller can retry or log.
        pass


__all__ = [
    "NativeExecutionResult",
    "NativeRuntimeError",
    "run_native_pipeline",
]
