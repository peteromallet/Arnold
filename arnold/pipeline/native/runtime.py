"""Native sequential runtime state machine.

Walks a compiled :class:`NativeProgram` one instruction at a time,
invokes phase/decision callables with a minimal dictionary context,
merges state like the graph executor, and persists resume cursors
when execution is interrupted by a ``max_phases`` limit.

The runtime does NOT import megaplan or register production pipelines.
It is a pure library module; runtime selection happens in executor and
pipeline-specific routing code.

Parity with graph executor
--------------------------
- Envelope propagation via ``hooks.join_envelope``.
- Callable return normalization (dict, StepResult, ContractResult).
- Schema-registry-backed handoff via ``StepIOContractContext``.
- ``state["__contract_results__"]`` publication matching executor shape.
- Telemetry-sink handling via ``telemetry_path``.

Ownership:
    The runtime executes topology owned by ``.pypeline`` modules and named
    native subworkflows.  Boundary contracts and boundary receipts are
    durable-effect declarations and checks consumed during execution — they
    do not define or alter the runtime execution path.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from arnold.pipeline.native.checkpoint import (
    NATIVE_CURSOR_VERSION,
    NativeCursorCorruptError,
    persist_native_cursor,
    read_native_cursor,
)
from arnold.pipeline.native.context import require_native_runtime
from arnold.pipeline.native.hooks import (
    NativeWbcHooks,
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import (
    PATH_DELIMITER,
    ROOT_PATH,
    NativeInstruction,
    NativeProgram,
    ParallelInstruction,
)
from arnold.pipeline.native.pack_metadata import PackLockfile, PackManifest
from arnold.pipeline.native.pack_registry import PackRegistry, ResolvedPackExport
from arnold.pipeline.native.pack_validation import (
    PACK_CLOSURE_MAX_DEPTH,
    PackClosureValidationError,
    validate_shared_pack_closure,
)
from arnold.pipeline.native.persistence import (
    FileNativePersistenceBackend,
    NativePersistenceBackend,
    NativePersistenceScope,
    bind_legacy_artifact_root,
)
from arnold.pipeline.native.reconcile import (
    ReconcileDecision,
    ReconcileMetadata,
    reconcile_file_write,
    reconcile_git_branch_create,
    reconcile_git_commit,
    reconcile_git_worktree,
)
from arnold.pipeline.native.trace import NativeTraceHooks
from arnold.supervisor.cancellation import (
    CancellationRequested,
    cancellation_result_payload,
    cancelled_contract_result,
)
from arnold.workflow.native_wbc import (
    NativeWbcAttempt,
    begin_native_wbc_attempt,
)

_MAX_SUBPIPELINE_DEPTH = PACK_CLOSURE_MAX_DEPTH
_DEFAULT_PHASE_MAX_ATTEMPTS = 1


def _pack_manifest_id(manifest: PackManifest) -> str:
    return manifest.stable_id or manifest.name


def _resolved_pack_export_record(resolved: ResolvedPackExport) -> dict[str, Any]:
    lockfile_entry = resolved.lockfile_entry or resolved.registration.to_lockfile_entry()
    return {
        "stable_id": resolved.export.stable_id,
        "version": lockfile_entry.version,
        "interface_hash": lockfile_entry.interface_hash,
        "pack_id": resolved.registration.pack_id,
        "pack_version": resolved.manifest.version,
        "export_name": resolved.export.name,
        "export_kind": resolved.export.kind,
    }


def _resolve_runtime_pack_provenance(
    *,
    pack_manifest: PackManifest | None,
    pack_lockfile: PackLockfile | None,
    pack_registry: PackRegistry | None,
) -> dict[str, Any] | None:
    if pack_manifest is None:
        if pack_lockfile is not None or pack_registry is not None:
            raise NativeRuntimeError(
                "pack_manifest is required when providing pack_lockfile or pack_registry"
            )
        return None

    pack_provenance: dict[str, Any] = {
        "manifest_stable_id": _pack_manifest_id(pack_manifest),
        "manifest_version": pack_manifest.version,
        "dependencies": [],
    }
    if not pack_manifest.dependencies:
        return pack_provenance

    if pack_registry is None:
        raise NativeRuntimeError(
            "pack_registry is required for runtime pack provenance when dependencies are declared"
        )
    if pack_lockfile is None:
        raise NativeRuntimeError(
            "pack_lockfile is required for runtime pack provenance when dependencies are declared"
        )

    resolved_dependencies: list[dict[str, Any]] = []
    visited: set[str] = set()

    def visit_dependency(stable_id: str) -> None:
        if stable_id in visited:
            return
        try:
            resolved = pack_registry.resolve_entry(stable_id, lockfile=pack_lockfile)
        except (LookupError, ValueError) as exc:
            raise NativeRuntimeError(
                f"runtime pack provenance resolution failed for dependency "
                f"{stable_id!r}: {exc}"
            ) from exc
        visited.add(stable_id)
        resolved_dependencies.append(_resolved_pack_export_record(resolved))
        for dependency in resolved.manifest.dependencies:
            visit_dependency(dependency.stable_id)

    for dependency in pack_manifest.dependencies:
        visit_dependency(dependency.stable_id)

    pack_provenance["dependencies"] = resolved_dependencies
    return pack_provenance


def _native_extra_with_pack_provenance(
    native_extra: Mapping[str, Any] | None,
    pack_provenance: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    merged = dict(native_extra or {})
    if pack_provenance is not None:
        merged["pack_provenance"] = dict(pack_provenance)
    return merged or None


@dataclass(frozen=True)
class _PathFrame:
    segment: str
    parent_run_path: str
    kind: str = "loop"
    header_pc: int | None = None


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


def _cancellation_requested(envelope: Any) -> bool:
    if envelope is None:
        return False
    if isinstance(envelope, Mapping):
        return bool(envelope.get("cancellation"))
    value = getattr(envelope, "cancellation", None)
    if value is not None:
        return bool(value)
    cross_cutting = getattr(envelope, "cross_cutting", None)
    if cross_cutting is not None:
        return bool(getattr(cross_cutting, "cancellation", False))
    return False


def _check_cancellation_boundary(
    *,
    boundary: str,
    instr: NativeInstruction | None,
    state: Mapping[str, Any],
    envelope: Any,
    run_path: str,
    step_path: str | None = None,
    call_site_path: tuple[str, ...] = (),
) -> None:
    """Raise when cancellation is requested at an existing runtime boundary."""

    del state
    if not _cancellation_requested(envelope):
        return
    raise CancellationRequested(
        boundary=boundary,
        run_path=run_path,
        step_path=step_path,
        call_site_path=tuple(call_site_path),
        instruction_op=instr.op if instr is not None else None,
        instruction_name=instr.name if instr is not None else None,
    )


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
) -> None:
    """Enforce typed step-IO handoff for a phase with typed produces ports.

    Matches the graph executor's ``_enforce_typed_step_io_handoff`` semantics:
    walks the instruction list for consumer phases whose ``consumes``
    declarations reference this producer's port names, calls
    ``evaluate_step_io_handoff`` for each pair (with a
    ``StepIOContractContext`` when *schema_registry* is provided), and
    raises ``StepIOEnforcementError`` when the resolved policy blocks
    the write.

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


def _schema_field_names(schema: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(schema, Mapping):
        return ()
    required = schema.get("required")
    if isinstance(required, (list, tuple)):
        fields = tuple(name for name in required if isinstance(name, str))
        if fields:
            return fields
    properties = schema.get("properties")
    if isinstance(properties, Mapping):
        return tuple(name for name in properties.keys() if isinstance(name, str))
    return ()


def _extract_child_inputs(
    state: Mapping[str, Any],
    inputs_schema: Mapping[str, Any] | None,
) -> dict[str, Any]:
    field_names = _schema_field_names(inputs_schema)
    if not field_names:
        return {
            key: value
            for key, value in state.items()
            if isinstance(key, str) and not key.startswith("__")
        }
    extracted = {name: state[name] for name in field_names if name in state}
    if extracted:
        return extracted
    return {
        key: value
        for key, value in state.items()
        if isinstance(key, str) and not key.startswith("__")
    }


def _extract_child_outputs(
    state: Mapping[str, Any],
    outputs_schema: Mapping[str, Any] | None,
    output_bindings: Mapping[str, str],
) -> dict[str, Any]:
    field_names = _schema_field_names(outputs_schema)
    if not field_names:
        return {
            key: value
            for key, value in state.items()
            if isinstance(key, str) and not key.startswith("__")
        }
    outputs: dict[str, Any] = {}
    for child_key in field_names:
        if child_key not in state:
            continue
        parent_key = output_bindings.get(child_key, child_key)
        outputs[parent_key] = state[child_key]
    if outputs:
        return outputs
    return {
        key: value
        for key, value in state.items()
        if isinstance(key, str) and not key.startswith("__")
    }


def _resolve_parallel_map_items(
    *,
    items_ref: str,
    state: Mapping[str, Any],
    parameter_values: Mapping[str, Any],
) -> list[Any]:
    if items_ref in parameter_values:
        raw_items = parameter_values[items_ref]
    elif items_ref in state:
        raw_items = state[items_ref]
    else:
        raise NativeRuntimeError(
            f"parallel_map could not resolve collection {items_ref!r}"
        )
    if isinstance(raw_items, (str, bytes)) or isinstance(raw_items, Mapping):
        raise NativeRuntimeError(
            f"parallel_map collection {items_ref!r} must resolve to a list-like iterable"
        )
    if not isinstance(raw_items, Iterable):
        raise NativeRuntimeError(
            f"parallel_map collection {items_ref!r} must resolve to an iterable"
        )
    return list(raw_items)


def _parallel_map_item_bindings(
    item: Any,
    *,
    index: int,
    items_ref: str,
) -> dict[str, Any]:
    bindings = {"item": item, "index": index, items_ref: item}
    if isinstance(item, Mapping):
        for key, value in item.items():
            if isinstance(key, str):
                bindings[key] = value
        return bindings
    item_dict = getattr(item, "__dict__", None)
    if isinstance(item_dict, Mapping):
        for key, value in item_dict.items():
            if isinstance(key, str):
                bindings[key] = value
    return bindings


def _parallel_map_item_coordinate(
    *,
    path_template: str,
    item: Any,
    index: int,
    items_ref: str,
) -> str:
    if not path_template:
        return f"[{index}]"
    try:
        return path_template.format_map(
            _parallel_map_item_bindings(item, index=index, items_ref=items_ref)
        )
    except Exception as exc:
        raise NativeRuntimeError(
            f"parallel_map path_template {path_template!r} could not be resolved for item {index}"
        ) from exc


def _validate_path_segment(segment: str) -> str:
    text = str(segment).strip()
    if not text:
        raise NativeRuntimeError("Native path segments must be non-empty")
    if PATH_DELIMITER in text:
        raise NativeRuntimeError(
            f"Native path segment {text!r} must not contain {PATH_DELIMITER!r}"
        )
    return text


def _normalize_call_site_segments(segments: Iterable[Any]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in segments:
        text = str(raw).strip()
        if not text:
            continue
        parts = [part for part in text.split(PATH_DELIMITER) if part]
        for part in parts:
            normalized.append(_validate_path_segment(part))
    return tuple(normalized)


def _normalize_run_path(run_path: str | Path) -> str:
    text = str(run_path).strip()
    if not text:
        return ROOT_PATH
    segments = _normalize_call_site_segments(text.split(PATH_DELIMITER))
    if not segments:
        return ROOT_PATH
    if segments[0] != ROOT_PATH:
        segments = (ROOT_PATH, *segments)
    return PATH_DELIMITER.join(segments)


def _path_segments_from_run_path(run_path: str) -> tuple[str, ...]:
    normalized = _normalize_run_path(run_path)
    return tuple(normalized.split(PATH_DELIMITER))


def _call_site_path_for_run_path(run_path: str) -> tuple[str, ...]:
    segments = _path_segments_from_run_path(run_path)
    if not segments or segments[0] != ROOT_PATH:
        return segments
    return segments[1:]


def _append_run_path_segments(run_path: str, *segments: str) -> str:
    base = _path_segments_from_run_path(run_path)
    appended = (*base, *_normalize_call_site_segments(segments))
    return PATH_DELIMITER.join(appended)


def _step_path_for_instr(run_path: str, instr: NativeInstruction) -> str:
    step_name = _validate_path_segment(instr.name or instr.op)
    return _append_run_path_segments(run_path, step_name)


def _serialize_path_stack(path_stack: list[_PathFrame]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for frame in path_stack:
        item = {
            "kind": frame.kind,
            "segment": frame.segment,
            "parent_run_path": frame.parent_run_path,
        }
        if isinstance(frame.header_pc, int):
            item["header_pc"] = frame.header_pc
        serialized.append(item)
    return serialized


def _deserialize_path_stack(raw: Any) -> list[_PathFrame]:
    if not isinstance(raw, list):
        return []
    restored: list[_PathFrame] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        kind = item.get("kind")
        if kind is None:
            kind = "loop"
        if not isinstance(kind, str) or not kind:
            continue
        header_pc = item.get("header_pc")
        segment = item.get("segment")
        parent_run_path = item.get("parent_run_path")
        if not isinstance(segment, str) or not segment:
            continue
        if not isinstance(parent_run_path, str) or not parent_run_path:
            continue
        normalized_header_pc = header_pc if isinstance(header_pc, int) else None
        if kind == "loop" and normalized_header_pc is None:
            continue
        restored.append(
            _PathFrame(
                segment=_validate_path_segment(segment),
                parent_run_path=_normalize_run_path(parent_run_path),
                kind=kind,
                header_pc=normalized_header_pc,
            )
        )
    return restored


def _cursor_path_metadata(
    *,
    program: NativeProgram,
    pc: int,
    run_path: str,
    path_stack: list[_PathFrame],
) -> dict[str, Any]:
    current_run_path = _normalize_run_path(run_path)
    current_path_stack = list(path_stack)
    instructions = program.instructions
    visited: set[int] = set()
    cur = pc

    while 0 <= cur < len(instructions):
        if cur in visited:
            break
        visited.add(cur)
        instr = instructions[cur]
        if instr.op == "jump":
            next_pc = instr.next_pc if instr.next_pc is not None else cur + 1
            if (
                next_pc <= cur
                and current_path_stack
                and current_path_stack[-1].kind == "loop"
                and next_pc == current_path_stack[-1].header_pc
            ):
                frame = current_path_stack.pop()
                current_run_path = frame.parent_run_path
            cur = next_pc
            continue
        if instr.op == "halt":
            break
        if instr.op in {"phase", "decision", "parallel", "parallel_map", "subpipeline"}:
            return {
                "run_path": current_run_path,
                "step_path": _step_path_for_instr(current_run_path, instr),
                "call_site_path": list(_call_site_path_for_run_path(current_run_path)),
                "path_stack": _serialize_path_stack(current_path_stack),
            }
        cur += 1

    return {
        "run_path": current_run_path,
        "step_path": None,
        "call_site_path": list(_call_site_path_for_run_path(current_run_path)),
        "path_stack": _serialize_path_stack(current_path_stack),
    }


def _parallel_map_item_state(
    parent_state: Mapping[str, Any],
    *,
    item: Any,
    index: int,
    items_ref: str,
    item_path: tuple[str, ...],
) -> dict[str, Any]:
    item_state = dict(parent_state)
    item_state.update(_parallel_map_item_bindings(item, index=index, items_ref=items_ref))
    item_state["__call_site_path__"] = item_path
    item_state["__parallel_map_item__"] = item
    item_state["__parallel_map_index__"] = index
    return item_state


def _loop_identity(
    instr: NativeInstruction,
    program: NativeProgram,
) -> str:
    loop_identity = instr.name
    for loop_guard in program.loop_guards:
        if loop_guard.guard is instr.func:
            loop_identity = loop_guard.stable_id or loop_guard.name or instr.name
            break
    return _validate_path_segment(loop_identity)


def _loop_counter_key(
    *,
    instr: NativeInstruction,
    program: NativeProgram,
    run_path: str,
) -> str:
    return _append_run_path_segments(run_path, _loop_identity(instr, program))


def _loop_iteration_count(
    *,
    instr: NativeInstruction,
    program: NativeProgram,
    loops: Mapping[str, int],
    run_path: str,
) -> int:
    scoped_key = _loop_counter_key(instr=instr, program=program, run_path=run_path)
    value = loops.get(scoped_key)
    if isinstance(value, int):
        return value
    legacy_value = loops.get(instr.name)
    if isinstance(legacy_value, int):
        return legacy_value
    return 0


def _resolve_phase_max_attempts(
    instr: NativeInstruction,
    phase_max_attempts: Mapping[str, int] | int | None,
) -> int:
    """Return the configured attempt budget for a phase instruction."""
    max_attempts = getattr(instr.func, "__phase_max_attempts__", None)
    if max_attempts is None and isinstance(phase_max_attempts, Mapping):
        stage_id = getattr(instr.func, "__step_id__", None)
        for key in (instr.name, stage_id):
            if isinstance(key, str) and key in phase_max_attempts:
                max_attempts = phase_max_attempts[key]
                break
    elif max_attempts is None:
        max_attempts = phase_max_attempts

    if max_attempts is None:
        return _DEFAULT_PHASE_MAX_ATTEMPTS
    if not isinstance(max_attempts, int) or max_attempts < 1:
        raise NativeRuntimeError(
            f"Native phase {instr.name!r} max_attempts must be an integer >= 1"
        )
    return max_attempts


def _raise_runtime_closure_error(exc: PackClosureValidationError) -> None:
    message = str(exc)
    if "pack closure cycle detected" in message:
        cycle = message.rsplit(": ", 1)[-1]
        raise NativeRuntimeError(
            f"Runtime subpipeline cycle detected: {cycle}"
        ) from exc
    if "pack closure depth exceeded" in message:
        depth_message = message.split("pack closure depth exceeded ", 1)[-1]
        depth_limit, _, remainder = depth_message.partition(" at ")
        child_identity = remainder.partition(" via ")[0] if remainder else ""
        detail = (
            f"Runtime subpipeline depth exceeded {depth_limit.strip()} at {child_identity}"
            if child_identity
            else f"Runtime subpipeline depth exceeded {depth_limit.strip()}"
        )
        raise NativeRuntimeError(detail) from exc
    raise NativeRuntimeError(f"Invalid native program closure: {message}") from exc


def _validate_runtime_program_closure(program: NativeProgram) -> None:
    try:
        validate_shared_pack_closure(program)
    except PackClosureValidationError as exc:
        _raise_runtime_closure_error(exc)


def run_native_pipeline(
    program: NativeProgram,
    *,
    artifact_root: str | Path = ".",
    initial_state: dict[str, Any] | None = None,
    max_phases: int | None = None,
    resume: bool = False,
    human_input: Mapping[str, Any] | str | None = None,
    override: Mapping[str, Any] | str | None = None,
    override_input: Mapping[str, Any] | str | None = None,
    hooks: NativeRuntimeHooks | None = None,
    schema_registry: Any = None,
    telemetry_path: str | Path | None = None,
    initial_envelope: Any = None,
    trace_dir: str | Path | None = None,
    run_path: str | Path = ROOT_PATH,
    phase_max_attempts: Mapping[str, int] | int | None = None,
    pack_manifest: PackManifest | None = None,
    pack_lockfile: PackLockfile | None = None,
    pack_registry: PackRegistry | None = None,
    persistence_backend: NativePersistenceBackend | None = None,
    project_lease_store: Any | None = None,
    project_lease_project_id: str | None = None,
    project_lease_worktree_id: str | None = None,
    project_lease_token: str | None = None,
    project_lease_seconds: int = 60,
    _subpipeline_depth: int = 0,
    _active_subpipelines: tuple[str, ...] = (),
    _parent_run_path: str | None = None,
    _trace_run_kind: str = "pipeline",
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
        human_input: Explicit human-gate resume payload.  A string is
            treated as the choice label; a mapping must contain exactly
            one choice field (``choice`` or ``_resume_choice``).
        override: Explicit human-gate override payload or label.  This
            alias is kept for callers that use graph-style override
            terminology; do not pass it together with ``override_input``.
        override_input: Explicit human-gate override payload or label.
            A string is treated as the override label; a mapping must
            contain exactly one override field.
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
        trace_dir: Optional directory for native-trace emission.  When
            set, a :class:`NativeTraceHooks` wrapper is layered over
            *hooks* to write ``state.json``, ``events.ndjson``,
            artifact inventory, stage sequence, and final checkpoint
            notification.  When ``None`` (the default), no trace files
            are emitted and behaviour is identical to previous versions.
        phase_max_attempts: Optional additive retry policy for phase
            instructions.  ``None`` preserves the current single-attempt
            behavior.  An integer applies to every phase; a mapping may
            target phase names or declared ``__step_id__`` values.
        pack_manifest: Optional pack manifest whose declared dependencies
            should be resolved and recorded as runtime provenance.
        pack_lockfile: Optional exact pin set used with ``pack_manifest``
            and ``pack_registry`` for fail-closed provenance resolution.
        pack_registry: Optional in-process registry used to resolve
            ``pack_manifest`` dependencies against ``pack_lockfile``.
        persistence_backend: Optional persistence backend used for native
            suspension, human-gate, and composite parent/child cursor state.
            When omitted, a file backend preserving the current artifact
            layout is used.

    Returns:
        :class:`NativeExecutionResult` with final state, completed stages,
        current pc, suspension status, and accumulated envelope.
    """
    require_native_runtime()
    if _subpipeline_depth == 0:
        _validate_runtime_program_closure(program)

    state: dict[str, Any] = dict(initial_state) if initial_state is not None else {}
    stages: list[str] = []
    owned_keys: frozenset[str] = frozenset()
    prefix = _safe_name(program.name)
    current_run_path = _normalize_run_path(run_path)
    trace_run_path = current_run_path
    trace_parent_run_path = (
        _normalize_run_path(_parent_run_path) if _parent_run_path else None
    )
    path_stack: list[_PathFrame] = []
    pack_provenance = _resolve_runtime_pack_provenance(
        pack_manifest=pack_manifest,
        pack_lockfile=pack_lockfile,
        pack_registry=pack_registry,
    )
    _persistence_backend, _persistence_scope = _runtime_persistence_binding(
        artifact_root,
        persistence_backend=persistence_backend,
    )
    _child_persistence_backend = (
        _persistence_backend if persistence_backend is not None else None
    )

    _runtime_wbc: NativeWbcAttempt = begin_native_wbc_attempt(
        artifact_root,
        producer_family="arnold_native",
        surface="runtime",
        run_id=getattr(initial_envelope, "run_id", "") or "",
        plugin_id=getattr(initial_envelope, "plugin_id", "") or "",
        manifest_hash=getattr(initial_envelope, "manifest_hash", "") or "",
        subject={"program": program.name, "resume": resume, "run_path": current_run_path},
        metadata={"trace_run_kind": _trace_run_kind},
        start_payload={"artifact_root": str(artifact_root), "resume": resume},
    )

    # Resolve hooks — always have a hooks instance so the runtime never
    # needs None-guards around callback invocations.
    _hooks: NativeRuntimeHooks = hooks if hooks is not None else NullNativeRuntimeHooks()
    _wbc_hooks = NativeWbcHooks(
        _hooks,
        artifact_root=artifact_root,
        program_name=program.name,
        run_id=getattr(initial_envelope, "run_id", "") or "",
        plugin_id=getattr(initial_envelope, "plugin_id", "") or "",
        manifest_hash=getattr(initial_envelope, "manifest_hash", "") or "",
    )
    _hooks = _wbc_hooks

    # ── Wrap with trace hooks when trace_dir is set ────────────────
    if trace_dir is not None:
        _hooks = NativeTraceHooks(
            inner=_hooks,
            trace_dir=trace_dir,
            artifact_root=artifact_root,
            persistence_backend=persistence_backend,
            persistence_scope=_persistence_scope if persistence_backend is not None else None,
        )

    # ── envelope accumulation (matches graph executor pattern) ─────
    envelope: Any = initial_envelope

    instructions = program.instructions
    if not instructions:
        return NativeExecutionResult(state=state, stages=stages, pc=0, envelope=envelope)

    trace_status = "running"
    if isinstance(_hooks, NativeTraceHooks):
        record_run_init = getattr(_hooks, "record_run_init", None)
        if callable(record_run_init):
            record_run_init(
                program,
                run_path=trace_run_path,
                pack_provenance=pack_provenance,
            )
        _hooks.on_run_enter(
            program,
            run_path=trace_run_path,
            parent_run_path=trace_parent_run_path,
            kind=_trace_run_kind,
            call_site_path=_call_site_path_for_run_path(trace_run_path),
            metadata=(
                {"pack_provenance": dict(pack_provenance)}
                if pack_provenance is not None
                else None
            ),
        )
    else:
        record_run_init = getattr(_hooks, "record_run_init", None)
        if callable(record_run_init):
            record_run_init(
                program,
                run_path=trace_run_path,
                pack_provenance=pack_provenance,
            )

    try:
        # ── resolve starting pc and restore state from cursor ────────────
        start_pc = 0
        loops: dict[str, int] = {}
        frames: dict[str, Any] = {}
        resume_cursor_data: dict[str, Any] | None = None
        composite_resume: dict[str, Any] | None = None

        if resume:
            try:
                resume_cursor_data = read_native_cursor(
                    artifact_root,
                    persistence_backend=_persistence_backend,
                    persistence_scope=_persistence_scope,
                    fallback_to_artifact_root=persistence_backend is None,
                )
            except NativeCursorCorruptError as exc:
                raise NativeRuntimeError(
                    f"Cannot resume native pipeline from corrupt cursor at "
                    f"{exc.cursor_path or Path(artifact_root) / 'resume_cursor.json'}: "
                    f"{exc.detail}"
                ) from exc
            # A missing cursor or graph-owned cursor is explicit: native resume starts
            # from pc 0 only when there is no valid native cursor to restore.
            if resume_cursor_data is not None:
                raw_composite = resume_cursor_data.get("composite")
                if (
                    isinstance(raw_composite, dict)
                    and raw_composite.get("kind") == "parent_child"
                ):
                    composite_resume = raw_composite
                    parent_frame = raw_composite["parent"]
                    start_pc = parent_frame["pc"]
                    stages = list(parent_frame.get("stages", []))
                    loops = dict(parent_frame.get("loops", {}))
                    frames = dict(parent_frame.get("frames", {}))
                    restored_state = dict(parent_frame.get("state", {}))
                    restored_state.update(initial_state or {})
                    state = restored_state
                    saved_envelope = parent_frame.get("envelope")
                    if saved_envelope is not None:
                        envelope = _deserialize_envelope(saved_envelope)
                    saved_run_path = parent_frame.get("run_path")
                    if isinstance(saved_run_path, str) and saved_run_path:
                        current_run_path = _normalize_run_path(saved_run_path)
                        trace_run_path = current_run_path
                    path_stack = _deserialize_path_stack(parent_frame.get("path_stack"))
                else:
                    start_pc = resume_cursor_data["native"]["pc"]
                    stages = list(resume_cursor_data.get("stages", []))
                    loops = dict(resume_cursor_data.get("loops", {}))
                    frames = dict(resume_cursor_data.get("frames", {}))
                    # Restore working state from cursor if present
                    saved_state = frames.pop("__state__", None)
                    if saved_state is not None:
                        if not isinstance(saved_state, dict):
                            raise NativeRuntimeError(
                                "Cannot resume native pipeline from malformed cursor: "
                                "frames.__state__ must be an object"
                            )
                        restored_state = dict(saved_state)
                        restored_state.update(initial_state or {})
                        state = restored_state
                    # Restore envelope from cursor frames if present
                    saved_envelope = frames.pop("__envelope__", None)
                    if saved_envelope is not None:
                        envelope = _deserialize_envelope(saved_envelope)
                    saved_run_path = resume_cursor_data.get("run_path")
                    if isinstance(saved_run_path, str) and saved_run_path:
                        current_run_path = _normalize_run_path(saved_run_path)
                        trace_run_path = current_run_path
                    path_stack = _deserialize_path_stack(resume_cursor_data.get("path_stack"))
                    if isinstance(_hooks, NativeTraceHooks):
                        resumed_step_path = None
                        resumed_pc = (
                            composite_resume["parent"]["pc"]
                            if composite_resume is not None
                            else start_pc
                        )
                        if 0 <= resumed_pc < len(instructions):
                            resumed_step_path = _step_path_for_instr(
                                current_run_path,
                                instructions[resumed_pc],
                            )
                        _hooks.seed_stage_sequence(stages)
                        _hooks.emit_pipeline_resumed(
                            reason=(
                                "child_suspended"
                                if composite_resume is not None
                                else "native_resume"
                            ),
                            run_path=current_run_path,
                            step_path=resumed_step_path,
                            call_site_path=_call_site_path_for_run_path(current_run_path),
                        )

        # ── resolve cursor_id (stable across suspension/resume) ──────────
        if override is not None and override_input is not None:
            raise NativeRuntimeError(
                "Pass only one of override= or override_input= when resuming a native human gate"
            )
        _resume_override_input = override_input if override_input is not None else override

        _cursor_id: str | None = None
        _human_gate_resume: bool = False
        if resume_cursor_data is not None:
            _cursor_id = resume_cursor_data.get("cursor_id")
            # Detect human-gate resume: native.suspension_kind == "human_gate"
            _native = resume_cursor_data.get("native", {})
            if isinstance(_native, dict) and _native.get("suspension_kind") == "human_gate":
                _human_gate_resume = True
            _runtime_wbc.effect(
                "resume_cursor_restored",
                {
                    "suspension_kind": (
                        _native.get("suspension_kind")
                        if isinstance(_native, dict)
                        else None
                    ),
                    "pc": start_pc,
                },
            )
        if _cursor_id is None:
            _cursor_id = uuid4().hex

        # ── pre-validate pc ──────────────────────────────────────────────
        if start_pc < 0 or start_pc >= len(instructions):
            trace_status = "completed"
            return NativeExecutionResult(state=state, stages=stages, pc=start_pc, envelope=envelope)

        telemetry_path_str: str | None = None
        if telemetry_path is not None:
            telemetry_path_str = str(telemetry_path)
        if not _active_subpipelines:
            _active_subpipelines = (program.stable_id or program.name,)
        parameter_values = _extract_child_inputs(state, program.inputs_schema)

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
                current_call_site_path = _call_site_path_for_run_path(current_run_path)
                current_step_path = _step_path_for_instr(current_run_path, instr)
                _check_cancellation_boundary(
                    boundary="step_enter",
                    instr=instr,
                    state=state,
                    envelope=envelope,
                    run_path=current_run_path,
                    step_path=current_step_path,
                    call_site_path=current_call_site_path,
                )
    
                max_attempts = _resolve_phase_max_attempts(
                    instr,
                    phase_max_attempts,
                )
                result: Any = None
                ctx: dict[str, Any] | None = None
                for attempt in range(1, max_attempts + 1):
                    # Build lightweight context (dict-based, no StepContext dependency)
                    ctx = {
                        "state": dict(state),
                        "inputs": dict(state),
                        "run_path": current_run_path,
                        "parent_run_path": trace_parent_run_path,
                        "step_path": current_step_path,
                        "call_site_path": current_call_site_path,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
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
                    _resume_reconcile = _reconcile_resumed_effect(
                        resume_cursor_data=resume_cursor_data,
                        instr=instr,
                        ctx=ctx,
                        state=state,
                        artifact_root=artifact_root,
                    )
                    if _resume_reconcile is not None:
                        ctx["effect_reconcile"] = _reconcile_decision_payload(
                            _resume_reconcile
                        )
                        if _resume_reconcile.skip_execution:
                            result = {}
                            break
                    if _should_skip_effect_execution(ctx):
                        result = {}
                        break

                    # Invoke the phase
                    try:
                        result = instr.func(ctx)
                        break
                    except BaseException as exc:
                        _hooks.on_step_error(instr, ctx, exc)
                        if attempt >= max_attempts:
                            raise
                assert ctx is not None

                # ── Hook: on_step_end (may rewrite result) ────────────
                result = _hooks.on_step_end(instr, ctx, result)
    
                # ── Callable return normalization (matching graph executor) ──
                outputs, contract_result = _normalize_phase_result(result, stage_id)
                state_patch = _extract_state_patch(result)
    
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
    
                # Match the graph executor: StepResult.state_patch is merged
                # after outputs/contract_result publication and before routing.
                if state_patch:
                    state.update(state_patch)
                    owned_keys = frozenset(owned_keys | frozenset(state_patch.keys()))
    
                # ── Hook: merge_state (may rewrite state / owned_keys) ──
                state, owned_keys = _hooks.merge_state(instr, state, outputs, owned_keys)
    
                # ── Envelope accumulation ─────────────────────────────
                step_envelope: Any = None
                if hasattr(result, "envelope"):
                    step_envelope = result.envelope
                elif isinstance(result, dict):
                    step_envelope = result.get("envelope")
                envelope = _hooks.join_envelope(instr, envelope, step_envelope)
    
                # A phase can return a suspended ContractResult directly.  Persist a
                # same-pc cursor and leave completion bookkeeping untouched so resume
                # re-enters the suspending phase.
                if _contract_result_is_suspended(contract_result):
                    _phase_resume_cursor = _contract_resume_cursor(contract_result)
                    _phase_contract_payload = _serialize_contract_result(contract_result)
                    _phase_suspension_payload = _serialize_contract_suspension(
                        contract_result
                    )
                    _phase_frames = dict(frames)
                    _phase_frames["__state__"] = _jsonable_value(dict(state))
                    if envelope is not None:
                        _phase_frames["__envelope__"] = _serialize_envelope(envelope)
                    _phase_extra = {
                        "suspension_kind": "phase_suspended",
                        "contract_result": _phase_contract_payload,
                        "suspension": _phase_suspension_payload,
                    }
                    _phase_path_metadata = _cursor_path_metadata(
                        program=program,
                        pc=pc,
                        run_path=current_run_path,
                        path_stack=path_stack,
                    )
                    persist_native_cursor(
                        artifact_root,
                        persistence_backend=_persistence_backend,
                        persistence_scope=_persistence_scope,
                        stage=stage_id,
                        pc=pc,
                        stages=list(stages),
                        reentry_stage=stage_id,
                        loops=dict(loops),
                        frames=_phase_frames,
                        resume_cursor=_phase_resume_cursor,
                        cursor_id=_cursor_id,
                        stage_reentry_points=_stage_reentry_points_for(stages),
                        effect=_hook_checkpoint_effect_metadata(_hooks),
                        native_extra=_native_extra_with_pack_provenance(
                            {"suspension_kind": "phase_suspended"},
                            pack_provenance,
                        ),
                        **_phase_path_metadata,
                        **_phase_extra,
                    )
                    _phase_cursor = _build_cursor_dict(
                        stage=stage_id,
                        pc=pc,
                        reentry_stage=stage_id,
                        stages=list(stages),
                        loops=dict(loops),
                        frames=_phase_frames,
                        state=state,
                        envelope=envelope,
                        cursor_id=_cursor_id,
                        effect=_hook_checkpoint_effect_metadata(_hooks),
                        resume_cursor=_phase_resume_cursor,
                        native_extra=_native_extra_with_pack_provenance(
                            {"suspension_kind": "phase_suspended"},
                            pack_provenance,
                        ),
                        extra={**_phase_path_metadata, **_phase_extra},
                    )
                    _hooks.on_checkpoint(_phase_cursor, dict(state))
                    if isinstance(_hooks, NativeTraceHooks):
                        _hooks.emit_pipeline_suspended(
                            reason="phase_suspended",
                            run_path=current_run_path,
                            step_path=current_step_path,
                            call_site_path=current_call_site_path,
                        )
                    trace_status = "suspended"
                    return NativeExecutionResult(
                        state=dict(state),
                        stages=list(stages),
                        pc=pc,
                        suspended=True,
                        cursor_path=str(Path(artifact_root) / "resume_cursor.json"),
                        envelope=envelope,
                    )
    
                # ── Hook: should_suspend (terminal exit) ────────────────
                do_suspend, suspend_reason = _hooks.should_suspend(instr, state, result)
                if do_suspend:
                    if _should_emit_stage_complete(instr):
                        _hooks.on_stage_complete(instr, ctx, result, state, owned_keys)
                    if hasattr(_hooks, "halt_reason"):
                        _hooks.halt_reason = suspend_reason  # type: ignore[attr-defined]
                    trace_status = "suspended"
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
                    if _should_emit_stage_complete(instr):
                        _hooks.on_stage_complete(instr, ctx, result, state, owned_keys)
                    # Advance pc to the next instruction for the resume point
                    next_pc = instr.next_pc if instr.next_pc is not None else pc + 1
                    reentry_stage = _reentry_stage_for_pc(program, next_pc)
                    _suspension_path_metadata = _cursor_path_metadata(
                        program=program,
                        pc=next_pc,
                        run_path=current_run_path,
                        path_stack=path_stack,
                    )
                    _persist_suspension(
                        artifact_root=artifact_root,
                        persistence_backend=_persistence_backend,
                        persistence_scope=_persistence_scope,
                        program=program,
                        stage=stage_id,
                        pc=next_pc,
                        reentry_stage=reentry_stage,
                        stages=stages,
                        loops=loops,
                        frames=frames,
                        state=state,
                        envelope=envelope,
                        cursor_id=_cursor_id,
                        path_metadata=_suspension_path_metadata,
                        effect=_hook_checkpoint_effect_metadata(_hooks),
                        pack_provenance=pack_provenance,
                    )
                    # ── Hook: on_checkpoint (after cursor persistence) ──
                    _cursor = _build_cursor_dict(
                        stage=stage_id,
                        pc=next_pc,
                        reentry_stage=reentry_stage,
                        stages=list(stages),
                        loops=dict(loops),
                        frames=dict(frames),
                        state=state,
                        envelope=envelope,
                        cursor_id=_cursor_id,
                        effect=_hook_checkpoint_effect_metadata(_hooks),
                        native_extra=_native_extra_with_pack_provenance(
                            None,
                            pack_provenance,
                        ),
                        extra=_suspension_path_metadata,
                    )
                    _hooks.on_checkpoint(_cursor, dict(state))
                    if isinstance(_hooks, NativeTraceHooks):
                        _hooks.emit_pipeline_suspended(
                            reason="max_phases",
                            run_path=current_run_path,
                            step_path=_cursor.get("step_path"),
                            call_site_path=current_call_site_path,
                        )
                    trace_status = "suspended"
                    return NativeExecutionResult(
                        state=dict(state),
                        stages=list(stages),
                        pc=next_pc,
                        suspended=True,
                        cursor_path=str(Path(artifact_root) / "resume_cursor.json"),
                        envelope=envelope,
                    )
    
                # ── Hook: on_stage_complete (normal completion) ────────
                if _should_emit_stage_complete(instr):
                    _hooks.on_stage_complete(instr, ctx, result, state, owned_keys)
                _check_cancellation_boundary(
                    boundary="step_exit",
                    instr=instr,
                    state=state,
                    envelope=envelope,
                    run_path=current_run_path,
                    step_path=current_step_path,
                    call_site_path=current_call_site_path,
                )

                # Advance to next instruction
                pc = instr.next_pc if instr.next_pc is not None else pc + 1
                forward_visited.clear()
    
            elif instr.op == "decision":
                if instr.func is None:
                    # No callable — can't route; halt
                    break

                current_call_site_path = _call_site_path_for_run_path(current_run_path)
                current_step_path = _step_path_for_instr(current_run_path, instr)
                _check_cancellation_boundary(
                    boundary="step_enter",
                    instr=instr,
                    state=state,
                    envelope=envelope,
                    run_path=current_run_path,
                    step_path=current_step_path,
                    call_site_path=current_call_site_path,
                )
    
                # ── Human-gate detection ──────────────────────────────
                # Inspect the decision callable's dunder attributes (set by
                # @decision(human_gate=True, ...)) to determine if this is a
                # human-gate suspension point BEFORE building context or
                # calling the decision body.
                _is_human_gate = bool(getattr(instr.func, "__decision_human_gate__", False))
    
                # ── Human-gate: initial suspension ────────────────────
                if _is_human_gate and not _human_gate_resume:
                    _hg_artifact_stage = str(getattr(instr.func, "__decision_artifact_stage__", "") or "")
                    _hg_choices = tuple(getattr(instr.func, "__decision_choices__", ()) or ())
                    _hg_resume_schema = getattr(instr.func, "__decision_resume_input_schema__", None)
                    _hg_override_routes = getattr(instr.func, "__decision_override_routes__", None)
                    _hg_name = getattr(instr.func, "__decision_name__", instr.name)
                    _hg_artifact_stage_for_checkpoint = (
                        _hg_artifact_stage if _hg_artifact_stage else _hg_name
                    )
    
                    from arnold.pipeline.steps.human_gate import (
                        make_human_suspension,
                    )
                    from arnold.pipeline.types import ContractResult, ContractStatus
    
                    _checkpoint_path = Path(artifact_root) / "awaiting_user.json"
                    _resume_cursor_payload: dict[str, Any] = {
                        "phase": _hg_name,
                        "retry_strategy": "awaiting_user",
                        "kind": "awaiting_user",
                    }
                    if _hg_choices:
                        _resume_cursor_payload["choices"] = list(_hg_choices)
                    _resume_cursor = json.dumps(_resume_cursor_payload, sort_keys=True)
                    _checkpoint: dict[str, Any] = {
                        "pipeline": program.name,
                        "version": NATIVE_CURSOR_VERSION,
                        "artifact_stage": _hg_artifact_stage_for_checkpoint,
                        "prompt": "",
                        "display_refs": [],
                        "stage": _hg_name,
                        "choices": list(_hg_choices),
                        "artifact_path": _resolve_native_human_gate_artifact_path(
                            artifact_root,
                            _hg_artifact_stage_for_checkpoint,
                        ),
                        "message": (
                            f"Pipeline '{program.name}' paused at human-gate "
                            f"'{_hg_name}'.  Review the artifact and choose: "
                            f"{', '.join(_hg_choices)}"
                        ),
                    }
                    if isinstance(_hg_resume_schema, dict):
                        _checkpoint["resume_input_schema"] = dict(_hg_resume_schema)
                    _persistence_backend.write_human_gate(
                        _persistence_scope,
                        payload=_checkpoint,
                    )
    
                    # Construct the typed HumanSuspension envelope.
                    _suspension = make_human_suspension(
                        _checkpoint,
                        resume_cursor=_resume_cursor,
                    )
                    _contract_result = ContractResult(
                        status=ContractStatus.SUSPENDED,
                        suspension=_suspension,
                        payload={
                            "source": "awaiting_user.json",
                            "awaiting_user": dict(_checkpoint),
                        },
                    )
    
                    # Build a stage-like identifier for the cursor.
                    _hg_stage_id = f"{_safe_name(program.name)}__{_hg_name}__pc{pc}"
    
                    # ── Persist cursor with graph-compatible top-level fields
                    # plus additive native restoration metadata.
                    _hg_cursor_extra: dict[str, Any] = {
                        "suspension_kind": "human_gate",
                        "artifact_stage": _hg_artifact_stage_for_checkpoint,
                        "choices": list(_hg_choices),
                        "contract_result": _contract_result.to_json(),
                        "suspension": _suspension.to_json(),
                    }
                    if isinstance(_hg_resume_schema, dict):
                        _hg_cursor_extra["resume_input_schema"] = _hg_resume_schema
                    if isinstance(_hg_override_routes, dict):
                        _hg_cursor_extra["override_routes"] = dict(_hg_override_routes)
    
                    _pause_state = dict(state)
                    _pause_state.update(
                        {
                            "_pipeline_paused": True,
                            "_pipeline_paused_stage": _hg_name,
                            "awaiting_user": str(_checkpoint_path),
                        }
                    )
    
                    # Mark loop frames with state for resume restoration.
                    _hg_frames = dict(frames)
                    _hg_frames["__state__"] = dict(_pause_state)
                    if envelope is not None:
                        _hg_frames["__envelope__"] = _serialize_envelope(envelope)
    
                    # Build stage_reentry_points from completed stages.
                    _hg_stage_reentry = _stage_reentry_points_for(stages)
                    _hg_path_metadata = _cursor_path_metadata(
                        program=program,
                        pc=pc,
                        run_path=current_run_path,
                        path_stack=path_stack,
                    )
    
                    persist_native_cursor(
                        artifact_root,
                        persistence_backend=_persistence_backend,
                        persistence_scope=_persistence_scope,
                        stage=_hg_stage_id,
                        pc=pc,
                        stages=list(stages),
                        reentry_stage=_hg_stage_id,
                        loops=dict(loops),
                        frames=_hg_frames,
                        resume_cursor=_resume_cursor,
                        cursor_id=_cursor_id,
                        stage_reentry_points=_hg_stage_reentry,
                        effect=_hook_checkpoint_effect_metadata(_hooks),
                        native_extra=_native_extra_with_pack_provenance(
                            {"suspension_kind": "human_gate"},
                            pack_provenance,
                        ),
                        **_hg_path_metadata,
                        **_hg_cursor_extra,
                    )
    
                    # ── Hook: on_checkpoint (after cursor persistence) ──
                    _hg_cursor = _build_cursor_dict(
                        stage=_hg_stage_id,
                        pc=pc,
                        reentry_stage=_hg_stage_id,
                        stages=list(stages),
                        loops=dict(loops),
                        frames=_hg_frames,
                        state=_pause_state,
                        envelope=envelope,
                        cursor_id=_cursor_id,
                        effect=_hook_checkpoint_effect_metadata(_hooks),
                        resume_cursor=_resume_cursor,
                        native_extra=_native_extra_with_pack_provenance(
                            {"suspension_kind": "human_gate"},
                            pack_provenance,
                        ),
                        extra={**_hg_path_metadata, **_hg_cursor_extra},
                    )
                    _hooks.on_checkpoint(_hg_cursor, dict(_pause_state))
                    _runtime_wbc.effect(
                        "human_gate_checkpoint_written",
                        {
                            "stage": _hg_name,
                            "choices": list(_hg_choices),
                            "checkpoint": str(_checkpoint_path),
                        },
                    )
                    if isinstance(_hooks, NativeTraceHooks):
                        _hooks.emit_pipeline_suspended(
                            reason="human_gate",
                            run_path=current_run_path,
                            step_path=_hg_cursor.get("step_path"),
                            call_site_path=_call_site_path_for_run_path(current_run_path),
                        )

                    trace_status = "suspended"
                    return NativeExecutionResult(
                        state=dict(_pause_state),
                        stages=list(stages),
                        pc=pc,
                        suspended=True,
                        cursor_path=str(Path(artifact_root) / "resume_cursor.json"),
                        envelope=envelope,
                    )
    
                # ── Human-gate: resume routing ────────────────────────
                if _is_human_gate and _human_gate_resume:
                    _hg_checkpoint_path = Path(artifact_root) / "awaiting_user.json"
                    _hg_checkpoint = (
                        _persistence_backend.read_human_gate(_persistence_scope) or {}
                    )
                    _resume_selection = _select_native_human_gate_resume_label(
                        human_input=human_input,
                        override_input=_resume_override_input,
                        checkpoint=_hg_checkpoint,
                    )
                    if _resume_selection is not None:
                        _resume_source, _resume_label = _resume_selection
                        _hg_choices = _native_human_gate_choices(
                            cursor=resume_cursor_data,
                            func=instr.func,
                        )
                        _hg_override_routes = _native_human_gate_override_routes(
                            cursor=resume_cursor_data,
                            func=instr.func,
                        )
                        target_pc = _resolve_native_human_gate_target_pc(
                            instr=instr,
                            instructions=instructions,
                            label=_resume_label,
                            source=_resume_source,
                            choices=_hg_choices,
                            override_routes=_hg_override_routes,
                        )
                        if target_pc is not None and not (0 <= target_pc < len(instructions)):
                            raise NativeRuntimeError(
                                f"Native human-gate decision '{instr.name}' accepted "
                                f"label {_resume_label!r}, but its target pc "
                                f"{target_pc!r} is outside the program"
                            )
    
                        # Clean up the checkpoint only after validating and
                        # accepting the label.  A failed unlink is treated as
                        # a failed resume so stale choices cannot be replayed.
                        try:
                            _persistence_backend.delete_human_gate(_persistence_scope)
                            _persistence_backend.delete_resume_cursor(_persistence_scope)
                        except OSError as exc:
                            raise NativeRuntimeError(
                                "Accepted native human-gate resume label "
                                f"{_resume_label!r}, but could not clear "
                                f"{_hg_checkpoint_path}: {exc}"
                            ) from exc
    
                        state.pop("_pipeline_paused", None)
                        state.pop("_pipeline_paused_stage", None)
                        state.pop("awaiting_user", None)
                        _human_gate_resume = False
                        _runtime_wbc.effect(
                            "human_gate_resume_selected",
                            {
                                "stage": instr.name,
                                "label": _resume_label,
                                "source": _resume_source,
                            },
                        )

                        if target_pc is not None:
                            _maybe_count_loop_iteration(
                                instr=instr,
                                label=_resume_label,
                                target_pc=target_pc,
                                program=program,
                                loops=loops,
                                run_path=current_run_path,
                            )
                            if _is_loop_body_entry(instr, target_pc, program):
                                iteration_segment = _loop_iteration_segment(
                                    instr,
                                    program,
                                    loops,
                                    current_run_path,
                                )
                                loop_parent_run_path = current_run_path
                                path_stack.append(
                                    _PathFrame(
                                        segment=iteration_segment,
                                        parent_run_path=current_run_path,
                                        kind="loop",
                                        header_pc=instr.pc,
                                    )
                                )
                                current_run_path = _append_run_path_segments(
                                    current_run_path,
                                    iteration_segment,
                                )
                                iteration = _loop_iteration_count(
                                    instr=instr,
                                    program=program,
                                    loops=loops,
                                    run_path=loop_parent_run_path,
                                )
                                do_halt, halt_reason = _hooks.should_halt_loop(
                                    instr,
                                    state,
                                    iteration,
                                )
                                if do_halt:
                                    if _should_emit_stage_complete(instr):
                                        _hooks.on_stage_complete(
                                            instr,
                                            {},
                                            _resume_label,
                                            state,
                                            owned_keys,
                                        )
                                    if hasattr(_hooks, "halt_reason"):
                                        _hooks.halt_reason = halt_reason  # type: ignore[attr-defined]
                                    return NativeExecutionResult(
                                        state=dict(state),
                                        stages=list(stages),
                                        pc=pc,
                                        envelope=envelope,
                                    )
    
                        if _should_emit_stage_complete(instr):
                            _hooks.on_stage_complete(
                                instr,
                                {},
                                (
                                    {"__override_route__": _resume_label}
                                    if _resume_source == "override"
                                    else _resume_label
                                ),
                                state,
                                owned_keys,
                            )
    
                        _hg_stage_id = f"{_safe_name(program.name)}__{instr.name}__pc{pc}"
                        stages.append(_hg_stage_id)
                        if target_pc is None:
                            break
                        pc = target_pc
                        forward_visited.clear()
                        continue
    
                    # No valid persisted choice yet: remain suspended and keep
                    # both durable files intact for a later process to resume.
                    return NativeExecutionResult(
                        state=dict(state),
                        stages=list(stages),
                        pc=pc,
                        suspended=True,
                        cursor_path=str(Path(artifact_root) / "resume_cursor.json"),
                        envelope=envelope,
                    )
    
                ctx: dict[str, Any] = {
                    "state": dict(state),
                    "inputs": dict(state),
                    "run_path": current_run_path,
                    "parent_run_path": trace_parent_run_path,
                    "step_path": _step_path_for_instr(current_run_path, instr),
                    "call_site_path": _call_site_path_for_run_path(current_run_path),
                }
                if isinstance(artifact_root, Path):
                    ctx["artifact_root"] = str(artifact_root)
                else:
                    ctx["artifact_root"] = str(artifact_root)
    
                # ── Hook: on_step_start (may rewrite ctx) ─────────────
                ctx = _hooks.on_step_start(instr, ctx)
                _resume_reconcile = _reconcile_resumed_effect(
                    resume_cursor_data=resume_cursor_data,
                    instr=instr,
                    ctx=ctx,
                    state=state,
                    artifact_root=artifact_root,
                )
                if _resume_reconcile is not None:
                    ctx["effect_reconcile"] = _reconcile_decision_payload(
                        _resume_reconcile
                    )
                    if _resume_reconcile.skip_execution:
                        result = {"__reconcile_skipped__": True}
                        result = _hooks.on_step_end(instr, ctx, result)
                        label = _resolve_decision_label(result)
                        target_pc = instr.branches.get(label) if instr.branches else None
                        if target_pc is not None and 0 <= target_pc < len(instructions):
                            pc = target_pc
                            forward_visited.clear()
                            continue
                        pc = instr.next_pc if instr.next_pc is not None else pc + 1
                        continue
                if _should_skip_effect_execution(ctx):
                    result = {"__reconcile_skipped__": True}
                    result = _hooks.on_step_end(instr, ctx, result)
                    label = _resolve_decision_label(result)
                    target_pc = instr.branches.get(label) if instr.branches else None
                    if target_pc is not None and 0 <= target_pc < len(instructions):
                        pc = target_pc
                        forward_visited.clear()
                        continue
                    pc = instr.next_pc if instr.next_pc is not None else pc + 1
                    continue
    
                # ── Control override short-circuit ──────────────────────
                # When a hook (e.g. MegaplanNativeRuntimeHooks) resolves a
                # catalog-driven control override, the context will carry
                # ``__override_route__``.  Skip the decision body and route
                # directly.  Priority: halt > override > decision > normal.
                control_override: str | None = ctx.pop("__override_route__", None)
                if control_override is None:
                    # Backward-compat for older hook implementations that use
                    # the original key name.
                    control_override = ctx.pop("__control_override__", None)
    
                if control_override is not None:
                    # Resolve the override route to a branch label.  First
                    # try the action name itself (e.g. "abort",
                    # "force_proceed"); if that is not in the vocabulary, fall
                    # back to "override"; otherwise execute the decision body
                    # normally so the program does not silently misroute.
                    override_label: str | None = control_override
                    if instr.branches and control_override not in instr.branches:
                        override_label = (
                            "override" if "override" in instr.branches else None
                        )
    
                    if override_label is not None:
                        # Build a synthetic result carrying the override
                        # metadata.  The decision body is intentionally
                        # **not** called — this is the control-override
                        # short-circuit.
                        result: Any = {"__override_route__": control_override}
                        result = _hooks.on_step_end(instr, ctx, result)
                        label: str = override_label
                    else:
                        # No matching branch for the override — execute the
                        # decision body normally.
                        try:
                            result = instr.func(ctx)
                        except BaseException as exc:
                            _hooks.on_step_error(instr, ctx, exc)
                            raise
                        result = _hooks.on_step_end(instr, ctx, result)
                        label = _resolve_decision_label(result)
                else:
                    # ── Normal decision execution (no override) ──────────
                    try:
                        result = instr.func(ctx)
                    except BaseException as exc:
                        _hooks.on_step_error(instr, ctx, exc)
                        raise
    
                    # ── Hook: on_step_end (may rewrite result) ────────────
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
                        run_path=current_run_path,
                    )
    
                    # ── Hook: should_halt_loop (before loop body) ──────────
                    # Fire when the decision is a loop guard routing to its body
                    if _is_loop_body_entry(instr, target_pc, program):
                        iteration_segment = _loop_iteration_segment(
                            instr,
                            program,
                            loops,
                            current_run_path,
                        )
                        loop_parent_run_path = current_run_path
                        path_stack.append(
                            _PathFrame(
                                segment=iteration_segment,
                                parent_run_path=current_run_path,
                                kind="loop",
                                header_pc=instr.pc,
                            )
                        )
                        current_run_path = _append_run_path_segments(
                            current_run_path,
                            iteration_segment,
                        )
                        iteration = _loop_iteration_count(
                            instr=instr,
                            program=program,
                            loops=loops,
                            run_path=loop_parent_run_path,
                        )
                        do_halt, halt_reason = _hooks.should_halt_loop(instr, state, iteration)
                        if do_halt:
                            if _should_emit_stage_complete(instr):
                                _hooks.on_stage_complete(instr, ctx, result, state, owned_keys)
                            if hasattr(_hooks, "halt_reason"):
                                _hooks.halt_reason = halt_reason  # type: ignore[attr-defined]
                            trace_status = "completed"
                            return NativeExecutionResult(
                                state=dict(state),
                                stages=list(stages),
                                pc=pc,
                                envelope=envelope,
                            )
    
                    # ── Hook: on_stage_complete (normal decision completion) ──
                    if _should_emit_stage_complete(instr):
                        _hooks.on_stage_complete(instr, ctx, result, state, owned_keys)
    
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
                if (
                    next_pc <= pc
                    and path_stack
                    and path_stack[-1].kind == "loop"
                    and next_pc == path_stack[-1].header_pc
                ):
                    frame = path_stack.pop()
                    current_run_path = frame.parent_run_path
                # Back-edge detection: if next_pc <= pc, this is a loop back-edge,
                # so clear the forward_visited set to allow revisiting.
                if next_pc <= pc:
                    forward_visited.clear()
                elif next_pc in forward_visited:
                    # Forward jump to an already visited pc → possible infinite loop
                    break
                forward_visited.add(pc)
                pc = next_pc
    
            elif instr.op == "parallel":
                # M5a: parallel blocks are compiled into sequential branch
                # instructions after this marker.  The marker itself is a
                # no-op at runtime; future milestones may add true fan-out.
                pc = instr.next_pc if instr.next_pc is not None else pc + 1
                continue
    
            elif instr.op == "parallel_map":
                parallel_block = getattr(instr, "subprogram", None)
                if parallel_block is None:
                    pc = instr.next_pc if instr.next_pc is not None else pc + 1
                    forward_visited.clear()
                    continue
    
                items = _resolve_parallel_map_items(
                    items_ref=parallel_block.items_ref,
                    state=state,
                    parameter_values=parameter_values,
                )
                mapper_results: list[Any] = []
                mapper_envelope: Any = None
                resume_from_index = 0
                composite_child_root: Path | None = None
                composite_child_index: int | None = None
                mapper = parallel_block.mapper
                if mapper is None:
                    raise NativeRuntimeError(
                        f"parallel_map {parallel_block.name or instr.name!r} has no mapper"
                    )
                compiled_mapper_program: NativeProgram | None = None
                if not getattr(mapper, "__phase__", False):
                    from arnold.pipeline.native.compiler import compile_pipeline

                    compiled_mapper_program = compile_pipeline(mapper)
                parallel_map_path = _append_run_path_segments(
                    current_run_path,
                    *instr.call_site_path,
                )
                if isinstance(_hooks, NativeTraceHooks):
                    _hooks.on_parallel_map_enter(
                        instr,
                        run_path=current_run_path,
                        path=parallel_map_path,
                        parent_run_path=trace_parent_run_path,
                        call_site_path=tuple(
                            _normalize_call_site_segments(
                                (*_call_site_path_for_run_path(current_run_path), *instr.call_site_path)
                            )
                        ),
                    )

                for index, item in enumerate(items):
                    item_coordinate = _parallel_map_item_coordinate(
                        path_template=parallel_block.path_template,
                        item=item,
                        index=index,
                        items_ref=parallel_block.items_ref,
                    )
                    item_path = _normalize_call_site_segments(
                        (*_call_site_path_for_run_path(current_run_path), *instr.call_site_path, item_coordinate)
                    )
                    item_run_path = _append_run_path_segments(current_run_path, *instr.call_site_path, item_coordinate)
                    item_state = _parallel_map_item_state(
                        state,
                        item=item,
                        index=index,
                        items_ref=parallel_block.items_ref,
                        item_path=item_path,
                    )
                    if composite_resume is not None and index == 0:
                        target_child_root = _composite_resume_child_root(
                            artifact_root=artifact_root,
                            composite=composite_resume,
                            parent_pc=pc,
                            child_run_path=item_run_path,
                        )
                        if target_child_root is None:
                            raw_child = composite_resume.get("child")
                            if isinstance(raw_child, Mapping):
                                raw_run_path = raw_child.get("run_path")
                                if isinstance(raw_run_path, str):
                                    raw_segments = _path_segments_from_run_path(raw_run_path)
                                    current_segments = _path_segments_from_run_path(
                                        current_run_path
                                    )
                                    if raw_segments[: len(current_segments)] == current_segments:
                                        for candidate_index, candidate_item in enumerate(items):
                                            candidate_coordinate = _parallel_map_item_coordinate(
                                                path_template=parallel_block.path_template,
                                                item=candidate_item,
                                                index=candidate_index,
                                                items_ref=parallel_block.items_ref,
                                            )
                                            candidate_run_path = _append_run_path_segments(
                                                current_run_path,
                                                *instr.call_site_path,
                                                candidate_coordinate,
                                            )
                                            target_child_root = _composite_resume_child_root(
                                                artifact_root=artifact_root,
                                                composite=composite_resume,
                                                parent_pc=pc,
                                                child_run_path=candidate_run_path,
                                            )
                                            if target_child_root is not None:
                                                composite_child_index = candidate_index
                                                break
                        else:
                            composite_child_index = index
                        if target_child_root is not None:
                            (
                                mapper_results,
                                mapper_envelope,
                                resume_from_index,
                            ) = _restore_parallel_map_progress(frames, pc=pc)
                            composite_child_root = target_child_root
                    if index < resume_from_index:
                        continue

                    if getattr(mapper, "__phase__", False):
                        mapper_instr = NativeInstruction(
                            pc=instr.pc,
                            op="phase",
                            name=parallel_block.mapper_name
                            or getattr(mapper, "__name__", "mapper"),
                            func=mapper,
                        )
                        ctx = {
                            "state": dict(item_state),
                            "inputs": dict(item_state),
                            "artifact_root": str(artifact_root),
                            "item": item,
                            "item_index": index,
                            "run_path": item_run_path,
                            "parent_run_path": current_run_path,
                            "step_path": _append_run_path_segments(
                                item_run_path,
                                _validate_path_segment(
                                    parallel_block.mapper_name
                                    or getattr(mapper, "__name__", "mapper")
                                ),
                            ),
                            "call_site_path": item_path,
                        }
                        if isinstance(_hooks, NativeTraceHooks):
                            _hooks.trace_only_step_start(mapper_instr, ctx)
                        try:
                            result = mapper(ctx)
                        except BaseException as exc:
                            if isinstance(_hooks, NativeTraceHooks):
                                _hooks.trace_only_step_error(mapper_instr, ctx, exc)
                            raise
                        if isinstance(_hooks, NativeTraceHooks):
                            _hooks.trace_only_step_end(mapper_instr, ctx)
                        outputs, _ = _normalize_phase_result(result, parallel_block.name or instr.name)
                        item_result = dict(outputs)
                        item_result.update(_extract_state_patch(result))
                        mapper_envelope = _hooks.join_envelope(
                            instr,
                            mapper_envelope,
                            getattr(result, "envelope", None),
                        )
                        if isinstance(_hooks, NativeTraceHooks):
                            _hooks.trace_only_stage_complete(mapper_instr, ctx)
                    else:
                        assert compiled_mapper_program is not None
                        child_program = compiled_mapper_program
                        child_name = getattr(child_program, "name", getattr(mapper, "__name__", "item"))
                        child_identity = child_program.stable_id or child_program.name
                        if child_identity in _active_subpipelines:
                            cycle = " -> ".join((*_active_subpipelines, child_identity))
                            raise NativeRuntimeError(
                                f"Runtime subpipeline cycle detected: {cycle}"
                            )
                        if _subpipeline_depth >= _MAX_SUBPIPELINE_DEPTH:
                            raise NativeRuntimeError(
                                "Runtime subpipeline depth exceeded "
                                f"{_MAX_SUBPIPELINE_DEPTH} at {child_identity}"
                            )
                        child_artifact_root = (
                            composite_child_root.parent
                            if composite_child_root is not None
                            and index == composite_child_index
                            else Path(artifact_root)
                            / f"_child_{child_name}"
                            / _safe_name(item_coordinate)
                        )
                        child_artifact_root.mkdir(parents=True, exist_ok=True)
                        child_initial_state = _extract_child_inputs(
                            item_state,
                            child_program.inputs_schema,
                        )
                        resume_child = (
                            composite_child_root is not None
                            and index == composite_child_index
                        )
                        _check_cancellation_boundary(
                            boundary="child_enter",
                            instr=instr,
                            state=item_state,
                            envelope=envelope,
                            run_path=item_run_path,
                            step_path=item_path,
                            call_site_path=(parallel_block.name or instr.name or "parallel_map", item_coordinate),
                        )
                        if resume_child:
                            _reconcile_child_resume_cursor(
                                child_artifact_root=child_artifact_root,
                                child_program=child_program,
                                persistence_backend=_child_persistence_backend,
                            )
                        child_result = run_native_pipeline(
                            program=child_program,
                            artifact_root=child_artifact_root,
                            initial_state=child_initial_state,
                            max_phases=None,
                            resume=resume_child,
                            human_input=human_input if resume_child else None,
                            override_input=_resume_override_input if resume_child else None,
                            hooks=_hooks,
                            trace_dir=None,
                            schema_registry=schema_registry,
                            telemetry_path=telemetry_path,
                            initial_envelope=envelope,
                            run_path=item_run_path,
                            phase_max_attempts=phase_max_attempts,
                            persistence_backend=_child_persistence_backend,
                            project_lease_store=project_lease_store,
                            project_lease_project_id=project_lease_project_id,
                            project_lease_worktree_id=project_lease_worktree_id,
                            project_lease_token=project_lease_token,
                            project_lease_seconds=project_lease_seconds,
                            _subpipeline_depth=_subpipeline_depth + 1,
                            _active_subpipelines=(
                                *_active_subpipelines,
                                child_identity,
                            ),
                            _parent_run_path=current_run_path,
                            _trace_run_kind="parallel_map_item",
                        )
                        _check_cancellation_boundary(
                            boundary="child_exit",
                            instr=instr,
                            state=child_result.state,
                            envelope=child_result.envelope,
                            run_path=item_run_path,
                            step_path=item_path,
                            call_site_path=(parallel_block.name or instr.name or "parallel_map", item_coordinate),
                        )
                        if child_result.suspended:
                            _child_cursor = _persist_parent_child_entry_cursor(
                                artifact_root=artifact_root,
                                persistence_backend=_persistence_backend,
                                persistence_scope=_persistence_scope,
                                child_persistence_backend=_child_persistence_backend,
                                child_artifact_root=child_artifact_root,
                                program=program,
                                instr=instr,
                                pc=pc,
                                current_run_path=current_run_path,
                                child_run_path=item_run_path,
                                path_stack=path_stack,
                                stages=stages,
                                loops=loops,
                                frames=frames,
                                state=state,
                                envelope=envelope,
                                cursor_id=_cursor_id,
                                suspension_kind="child_suspended",
                                effect=_hook_checkpoint_effect_metadata(_hooks),
                                pack_provenance=pack_provenance,
                                parent_frame_extra={
                                    _parallel_map_progress_key(pc): {
                                        "completed_results": _jsonable_value(
                                            list(mapper_results)
                                        ),
                                        "mapper_envelope": _serialize_envelope(
                                            mapper_envelope
                                        )
                                        if mapper_envelope is not None
                                        else None,
                                        "next_index": index,
                                    }
                                },
                            )
                            _hooks.on_checkpoint(_child_cursor, dict(state))
                            if isinstance(_hooks, NativeTraceHooks):
                                _hooks.emit_pipeline_suspended(
                                    reason="child_suspended",
                                    run_path=current_run_path,
                                    step_path=item_path,
                                    call_site_path=_child_cursor.get("call_site_path") or (),
                                )
                            trace_status = "suspended"
                            return NativeExecutionResult(
                                state=dict(state),
                                stages=list(stages),
                                pc=pc,
                                suspended=True,
                                cursor_path=str(Path(artifact_root) / "resume_cursor.json"),
                                envelope=envelope,
                            )
                        item_result = _extract_child_outputs(
                            child_result.state,
                            child_program.outputs_schema,
                            {},
                        )
                        mapper_envelope = _hooks.join_envelope(
                            instr,
                            mapper_envelope,
                            child_result.envelope,
                        )

                    mapper_results.append(item_result)

                if parallel_block.reducer is not None:
                    reducer_result = parallel_block.reducer(mapper_results)
                    outputs, _ = _normalize_phase_result(
                        reducer_result,
                        parallel_block.name or instr.name,
                    )
                    state_patch = _extract_state_patch(reducer_result)
                    parallel_outputs = dict(outputs)
                    parallel_outputs.update(state_patch)
                    mapper_envelope = _hooks.join_envelope(
                        instr,
                        mapper_envelope,
                        getattr(reducer_result, "envelope", None),
                    )
                else:
                    parallel_outputs = {instr.name: mapper_results}
    
                state.update(parallel_outputs)
                state, owned_keys = _hooks.merge_state(
                    instr,
                    state,
                    parallel_outputs,
                    owned_keys,
                )
                envelope = _hooks.join_envelope(instr, envelope, mapper_envelope)
                if isinstance(_hooks, NativeTraceHooks):
                    _hooks.on_parallel_map_exit(
                        instr,
                        run_path=current_run_path,
                        path=parallel_map_path,
                    )
                pc = instr.next_pc if instr.next_pc is not None else pc + 1
                forward_visited.clear()
                continue
    
            elif instr.op == "subpipeline":
                child_program = getattr(instr, 'subprogram', None)
                if child_program is not None:
                    child_name = instr.name or "child"
                    child_identity = child_program.stable_id or child_program.name
    
                    if child_identity in _active_subpipelines:
                        cycle = " -> ".join((*_active_subpipelines, child_identity))
                        raise NativeRuntimeError(f"Runtime subpipeline cycle detected: {cycle}")
                    if _subpipeline_depth >= _MAX_SUBPIPELINE_DEPTH:
                        raise NativeRuntimeError(
                            "Runtime subpipeline depth exceeded "
                            f"{_MAX_SUBPIPELINE_DEPTH} at {child_identity}"
                        )
    
                    # ── Isolate artifact root ──────────────────────────
                    child_artifact_root = _child_artifact_root(
                        artifact_root,
                        child_name=child_name,
                        call_site_path=instr.call_site_path,
                    )
                    child_run_path = _append_run_path_segments(
                        current_run_path,
                        *instr.call_site_path,
                    )
                    composite_child_cursor = _composite_resume_child_root(
                        artifact_root=artifact_root,
                        composite=composite_resume,
                        parent_pc=pc,
                        child_run_path=child_run_path,
                    )
                    if composite_child_cursor is not None:
                        child_artifact_root = composite_child_cursor.parent
                    child_artifact_root.mkdir(parents=True, exist_ok=True)
    
                    # ── Schema-filter child inputs from parent state ───
                    child_initial_state = _extract_child_inputs(
                        state,
                        child_program.inputs_schema,
                    )

                    if composite_child_cursor is None:
                        _child_entry_cursor = _persist_parent_child_entry_cursor(
                            artifact_root=artifact_root,
                            persistence_backend=_persistence_backend,
                            persistence_scope=_persistence_scope,
                            child_persistence_backend=_child_persistence_backend,
                            child_artifact_root=child_artifact_root,
                            program=program,
                            instr=instr,
                            pc=pc,
                            current_run_path=current_run_path,
                            child_run_path=child_run_path,
                            path_stack=path_stack,
                            stages=stages,
                            loops=loops,
                            frames=frames,
                            state=state,
                            envelope=envelope,
                            cursor_id=_cursor_id,
                            effect=_hook_checkpoint_effect_metadata(_hooks),
                            pack_provenance=pack_provenance,
                        )
                        _hooks.on_checkpoint(_child_entry_cursor, dict(state))
                        _check_cancellation_boundary(
                            boundary="child_enter",
                            instr=instr,
                            state=state,
                            envelope=envelope,
                            run_path=child_run_path,
                            step_path=_step_path_for_instr(current_run_path, instr),
                            call_site_path=tuple(instr.call_site_path),
                        )

                    # ── Execute child subpipeline ───────────────────────
                    if composite_child_cursor is not None:
                        _reconcile_child_resume_cursor(
                            child_artifact_root=child_artifact_root,
                            child_program=child_program,
                            persistence_backend=_child_persistence_backend,
                        )
                    child_result = run_native_pipeline(
                        program=child_program,
                        artifact_root=child_artifact_root,
                        initial_state=child_initial_state,
                        max_phases=None,
                        resume=composite_child_cursor is not None,
                        human_input=human_input
                        if composite_child_cursor is not None
                        else None,
                        override_input=_resume_override_input
                        if composite_child_cursor is not None
                        else None,
                        hooks=_hooks,
                        schema_registry=schema_registry,
                        telemetry_path=telemetry_path,
                        initial_envelope=envelope,
                        trace_dir=None,
                        run_path=child_run_path,
                        phase_max_attempts=phase_max_attempts,
                        persistence_backend=_child_persistence_backend,
                        project_lease_store=project_lease_store,
                        project_lease_project_id=project_lease_project_id,
                        project_lease_worktree_id=project_lease_worktree_id,
                        project_lease_token=project_lease_token,
                        project_lease_seconds=project_lease_seconds,
                        _subpipeline_depth=_subpipeline_depth + 1,
                        _active_subpipelines=(*_active_subpipelines, child_identity),
                        _parent_run_path=current_run_path,
                        _trace_run_kind="subpipeline",
                    )
                    _check_cancellation_boundary(
                        boundary="child_exit",
                        instr=instr,
                        state=child_result.state,
                        envelope=child_result.envelope,
                        run_path=child_run_path,
                        step_path=_step_path_for_instr(current_run_path, instr),
                        call_site_path=tuple(instr.call_site_path),
                    )

                    if child_result.suspended:
                        _child_suspended_cursor = _persist_parent_child_entry_cursor(
                            artifact_root=artifact_root,
                            persistence_backend=_persistence_backend,
                            persistence_scope=_persistence_scope,
                            child_persistence_backend=_child_persistence_backend,
                            child_artifact_root=child_artifact_root,
                            program=program,
                            instr=instr,
                            pc=pc,
                            current_run_path=current_run_path,
                            child_run_path=child_run_path,
                            path_stack=path_stack,
                            stages=stages,
                            loops=loops,
                            frames=frames,
                            state=state,
                            envelope=envelope,
                            cursor_id=_cursor_id,
                            suspension_kind="child_suspended",
                            effect=_hook_checkpoint_effect_metadata(_hooks),
                            pack_provenance=pack_provenance,
                        )
                        _hooks.on_checkpoint(_child_suspended_cursor, dict(state))
                        if isinstance(_hooks, NativeTraceHooks):
                            _hooks.emit_pipeline_suspended(
                                reason="child_suspended",
                                run_path=current_run_path,
                                step_path=_step_path_for_instr(current_run_path, instr),
                                call_site_path=_child_suspended_cursor.get("call_site_path")
                                or (),
                            )
                        trace_status = "suspended"
                        return NativeExecutionResult(
                            state=dict(state),
                            stages=list(stages),
                            pc=pc,
                            suspended=True,
                            cursor_path=str(Path(artifact_root) / "resume_cursor.json"),
                            envelope=envelope,
                        )

                    _clear_parent_child_entry_cursor(
                        artifact_root=artifact_root,
                        persistence_backend=_persistence_backend,
                        persistence_scope=_persistence_scope,
                        child_artifact_root=child_artifact_root,
                        pc=pc,
                    )

                    # ── Merge declared child outputs back into parent state ─
                    child_outputs = _extract_child_outputs(
                        child_result.state,
                        child_program.outputs_schema,
                        getattr(instr, "output_bindings", {}),
                    )
                    state.update(child_outputs)
                    state, owned_keys = _hooks.merge_state(
                        instr, state, child_outputs, owned_keys,
                    )
    
                    # ── Join child envelope ────────────────────────────
                    envelope = _hooks.join_envelope(
                        instr, envelope, child_result.envelope,
                    )
    
                    # ── Advance pc ──────────────────────────────────────
                    pc = instr.next_pc if instr.next_pc is not None else pc + 1
                    forward_visited.clear()
                else:
                    # No child program attached — skip
                    pc = instr.next_pc if instr.next_pc is not None else pc + 1
                    forward_visited.clear()
    
            else:
                # Unknown op — treat as no-op and advance
                pc += 1
    
        # ── Hook: on_checkpoint (clean completion) ────────────────────────
        _clean_cursor = _build_cursor_dict(
            stage=stages[-1] if stages else "",
            pc=pc,
            reentry_stage=_reentry_stage_for_pc(program, pc),
            stages=list(stages),
            loops=dict(loops),
            frames=dict(frames),
            state=state,
            envelope=envelope,
            final=True,
            cursor_id=_cursor_id,
            effect=_hook_checkpoint_effect_metadata(_hooks),
            native_extra=_native_extra_with_pack_provenance(None, pack_provenance),
            extra=_cursor_path_metadata(
                program=program,
                pc=pc,
                run_path=current_run_path,
                path_stack=path_stack,
            ),
        )
        _hooks.on_checkpoint(_clean_cursor, dict(state))

        trace_status = "completed"
        return NativeExecutionResult(state=state, stages=stages, pc=pc, envelope=envelope)
    except CancellationRequested as exc:
        payload = cancellation_result_payload(exc)
        state["__cancelled__"] = payload
        published = state.get("__contract_results__")
        if not isinstance(published, dict):
            published = {}
            state["__contract_results__"] = published
        published["__runtime_cancelled__"] = cancelled_contract_result(exc)

        try:
            if (
                project_lease_store is not None
                and project_lease_project_id
                and project_lease_worktree_id
                and project_lease_token
            ):
                project_lease_store.heartbeat_project_lease(
                    project_lease_project_id,
                    project_lease_worktree_id,
                    project_lease_token,
                    lease_seconds=project_lease_seconds,
                    progress=True,
                )
                project_lease_store.cancel_project_lease(
                    project_lease_project_id,
                    project_lease_worktree_id,
                    lease_token=project_lease_token,
                    result={"cancellation": dict(payload)},
                )
        except Exception:
            payload["lease_release_error"] = True

        cancel_stage = stages[-1] if stages else f"{_safe_name(program.name)}__cancelled__pc{pc}"
        cancel_path_metadata = _cursor_path_metadata(
            program=program,
            pc=pc,
            run_path=current_run_path,
            path_stack=path_stack,
        )
        cancel_path_metadata.update(
            {
                "suspension_kind": "cancelled",
                "cancellation": dict(payload),
            }
        )
        _persist_suspension(
            artifact_root=artifact_root,
            persistence_backend=_persistence_backend,
            persistence_scope=_persistence_scope,
            program=program,
            stage=cancel_stage,
            pc=pc,
            reentry_stage=_reentry_stage_for_pc(program, pc),
            stages=stages,
            loops=loops,
            frames=frames,
            state=state,
            envelope=envelope,
            cursor_id=_cursor_id,
            path_metadata=cancel_path_metadata,
            effect=_hook_checkpoint_effect_metadata(_hooks),
            pack_provenance=pack_provenance,
        )
        cancel_cursor = _build_cursor_dict(
            stage=cancel_stage,
            pc=pc,
            reentry_stage=_reentry_stage_for_pc(program, pc),
            stages=list(stages),
            loops=dict(loops),
            frames=dict(frames),
            state=state,
            envelope=envelope,
            cursor_id=_cursor_id,
            effect=_hook_checkpoint_effect_metadata(_hooks),
            native_extra=_native_extra_with_pack_provenance(
                {"suspension_kind": "cancelled"},
                pack_provenance,
            ),
            extra=cancel_path_metadata,
        )
        record_cancellation = getattr(_hooks, "record_cancellation", None)
        if callable(record_cancellation):
            record_cancellation(payload, state=dict(state))
        _hooks.on_checkpoint(cancel_cursor, dict(state))
        if isinstance(_hooks, NativeTraceHooks):
            _hooks.emit_pipeline_cancelled(payload)
            _hooks.emit_pipeline_suspended(
                reason="cancelled",
                run_path=current_run_path,
                step_path=payload.get("step_path"),
                call_site_path=payload.get("call_site_path") or (),
            )
        trace_status = "cancelled"
        return NativeExecutionResult(
            state=dict(state),
            stages=list(stages),
            pc=pc,
            suspended=True,
            cursor_path=str(Path(artifact_root) / "resume_cursor.json"),
            envelope=envelope,
        )
    except BaseException as exc:
        trace_status = "failed"
        raise
    finally:
        terminal_payload = {
            "pc": locals().get("pc", 0),
            "stages_completed": len(stages),
            "run_path": current_run_path,
        }
        if trace_status == "completed":
            _runtime_wbc.terminal(
                status="completed",
                outcome="result",
                payload=terminal_payload,
            )
        elif trace_status == "suspended":
            _runtime_wbc.terminal(
                status="suspended",
                outcome="checkpoint",
                payload=terminal_payload,
            )
        elif trace_status == "cancelled":
            _runtime_wbc.terminal(
                status="cancelled",
                outcome="cancelled",
                payload=terminal_payload,
            )
        else:
            _runtime_wbc.terminal(
                status="failed",
                outcome="error",
                payload=terminal_payload,
            )
        close_wbc = getattr(_wbc_hooks, "close", None)
        if callable(close_wbc):
            if trace_status == "completed":
                close_wbc(status="completed", outcome="result", payload=terminal_payload)
            elif trace_status == "suspended":
                close_wbc(status="suspended", outcome="checkpoint", payload=terminal_payload)
            elif trace_status == "cancelled":
                close_wbc(
                    status="cancelled",
                    outcome="cancelled",
                    payload=terminal_payload,
                )
            else:
                close_wbc(status="failed", outcome="error", payload=terminal_payload)
        if isinstance(_hooks, NativeTraceHooks):
            _hooks.on_run_exit(program, run_path=trace_run_path, status=trace_status)


# ── helpers ───────────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """Return a name safe for use as a stage-name prefix."""
    return name.replace(" ", "_").replace("-", "_")


def _runtime_persistence_binding(
    artifact_root: str | Path,
    *,
    persistence_backend: NativePersistenceBackend | None,
) -> tuple[NativePersistenceBackend, NativePersistenceScope]:
    binding = bind_legacy_artifact_root(artifact_root)
    if persistence_backend is not None:
        return persistence_backend, binding.scope
    backend = FileNativePersistenceBackend(
        lambda scope: binding.artifact_root
        if scope == binding.scope
        else (_ for _ in ()).throw(KeyError(scope))
    )
    return backend, binding.scope


def _resolve_decision_label(result: Any) -> str:
    """Resolve a decision return value to a branch label string."""
    if isinstance(result, str):
        return result
    if hasattr(result, "next") and isinstance(getattr(result, "next"), str):
        return result.next
    # Truthy/falsy fallback
    return "__truthy__" if result else "__falsy__"


def _select_native_human_gate_resume_label(
    *,
    human_input: Mapping[str, Any] | str | None,
    override_input: Mapping[str, Any] | str | None,
    checkpoint: Mapping[str, Any],
) -> tuple[str, str] | None:
    """Return the single accepted resume label source and value, if present."""
    override_label = _extract_native_resume_label(
        override_input,
        kind="override_input",
        keys=("override", "action", "label", "choice"),
    )
    human_label = _extract_native_resume_label(
        human_input,
        kind="human_input",
        keys=("choice", "_resume_choice"),
    )
    if override_label is not None and human_label is not None:
        raise NativeRuntimeError(
            "Native human-gate resume accepts exactly one of human_input or override input"
        )
    if override_label is not None:
        return ("override", override_label)
    if human_label is not None:
        return ("human_input", human_label)

    checkpoint_label = checkpoint.get("_resume_choice")
    if checkpoint_label is None:
        return None
    if not isinstance(checkpoint_label, str) or not checkpoint_label:
        raise NativeRuntimeError(
            "awaiting_user.json contains _resume_choice, but it is not a non-empty string"
        )
    return ("checkpoint", checkpoint_label)


def _extract_native_resume_label(
    payload: Mapping[str, Any] | str | None,
    *,
    kind: str,
    keys: tuple[str, ...],
) -> str | None:
    """Extract exactly one string label from an explicit resume payload."""
    if payload is None:
        return None
    if isinstance(payload, str):
        if not payload:
            raise NativeRuntimeError(f"{kind} must not be an empty string")
        return payload
    if not isinstance(payload, Mapping):
        raise NativeRuntimeError(
            f"{kind} must be a string label or mapping, got {type(payload).__name__}"
        )

    found = [
        (key, payload[key])
        for key in keys
        if key in payload and payload[key] is not None
    ]
    if len(found) != 1:
        raise NativeRuntimeError(
            f"{kind} must contain exactly one of {', '.join(keys)}"
        )
    key, value = found[0]
    if not isinstance(value, str) or not value:
        raise NativeRuntimeError(
            f"{kind}.{key} must be a non-empty string label"
        )
    return value


def _native_human_gate_choices(
    *,
    cursor: Mapping[str, Any] | None,
    func: Any,
) -> tuple[str, ...]:
    """Return declared human-gate choices from the cursor, falling back to metadata."""
    if cursor is not None:
        raw = cursor.get("choices")
        if isinstance(raw, list):
            return tuple(str(choice) for choice in raw)
        if isinstance(raw, tuple):
            return tuple(str(choice) for choice in raw)
    raw = getattr(func, "__decision_choices__", ()) if func is not None else ()
    if isinstance(raw, (list, tuple)):
        return tuple(str(choice) for choice in raw)
    return ()


def _native_human_gate_override_routes(
    *,
    cursor: Mapping[str, Any] | None,
    func: Any,
) -> dict[str, str | None]:
    """Return declared human-gate override routes from cursor or metadata."""
    raw: Any = None
    if cursor is not None:
        raw = cursor.get("override_routes")
    if not isinstance(raw, Mapping) and func is not None:
        raw = getattr(func, "__decision_override_routes__", None)
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(label): (None if target is None else str(target))
        for label, target in raw.items()
    }


def _resolve_native_human_gate_target_pc(
    *,
    instr: NativeInstruction,
    instructions: tuple[NativeInstruction, ...],
    label: str,
    source: str,
    choices: tuple[str, ...],
    override_routes: Mapping[str, str | None],
) -> int | None:
    """Validate a human-gate resume label and return the declared target pc."""
    branches = instr.branches or {}

    if source in {"human_input", "checkpoint"} and choices and label not in choices:
        raise NativeRuntimeError(
            f"Native human-gate decision '{instr.name}' received choice {label!r}, "
            f"but valid choices are {sorted(choices)}"
        )

    if label in override_routes:
        return _resolve_native_human_gate_route_target(
            route_target=override_routes[label],
            instr=instr,
            instructions=instructions,
            label=label,
        )

    if label in branches:
        return branches[label]

    valid_labels = sorted(set(branches) | set(choices) | set(override_routes))
    raise NativeRuntimeError(
        f"Native human-gate decision '{instr.name}' received {source} label "
        f"{label!r}, but no declared branch or override route accepts it. "
        f"Valid labels: {valid_labels}"
    )


def _resolve_native_human_gate_route_target(
    *,
    route_target: str | None,
    instr: NativeInstruction,
    instructions: tuple[NativeInstruction, ...],
    label: str,
) -> int | None:
    """Resolve an override_routes target while staying inside declared branches."""
    if route_target is None or route_target == "halt":
        return None

    if route_target in instr.branches:
        return instr.branches[route_target]

    target_pc = _find_native_instruction_pc(instructions, route_target)
    if target_pc is None:
        raise NativeRuntimeError(
            f"Native human-gate decision '{instr.name}' maps label {label!r} "
            f"to unknown route target {route_target!r}"
        )

    allowed_destinations = {
        _resolve_native_branch_destination(branch_pc, instructions)
        for branch_pc in instr.branches.values()
    }
    resolved_target = _resolve_native_branch_destination(target_pc, instructions)
    if resolved_target not in allowed_destinations:
        raise NativeRuntimeError(
            f"Native human-gate decision '{instr.name}' maps label {label!r} "
            f"to {route_target!r}, which is not a declared branch target"
        )
    return resolved_target


def _find_native_instruction_pc(
    instructions: tuple[NativeInstruction, ...],
    name: str,
) -> int | None:
    """Return the first executable instruction pc with *name*."""
    for candidate in instructions:
        if candidate.op in {"phase", "decision", "parallel", "subpipeline"}:
            if candidate.name == name:
                return candidate.pc
    return None


def _resolve_native_branch_destination(
    pc: int | None,
    instructions: tuple[NativeInstruction, ...],
) -> int | None:
    """Follow jumps from a branch target to its executable destination."""
    if pc is None:
        return None
    visited: set[int] = set()
    cur = pc
    while 0 <= cur < len(instructions):
        if cur in visited:
            return None
        visited.add(cur)
        instr = instructions[cur]
        if instr.op == "halt":
            return None
        if instr.op == "jump":
            if instr.next_pc is None:
                return None
            cur = instr.next_pc
            continue
        if instr.op in {"phase", "decision", "parallel", "subpipeline"}:
            return cur
        cur += 1
    return None


def _maybe_count_loop_iteration(
    *,
    instr: NativeInstruction,
    label: str,
    target_pc: int,
    program: NativeProgram,
    loops: dict[str, int],
    run_path: str,
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
                scoped_key = _loop_counter_key(
                    instr=instr,
                    program=program,
                    run_path=run_path,
                )
                current = loops.get(scoped_key)
                if not isinstance(current, int):
                    legacy = loops.pop(instr.name, None)
                    current = legacy if isinstance(legacy, int) else 0
                loops[scoped_key] = current + 1
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


def _loop_iteration_segment(
    instr: NativeInstruction,
    program: NativeProgram,
    loops: Mapping[str, int],
    run_path: str,
) -> str:
    """Return the stable path segment for the active loop iteration."""
    loop_identity = _loop_identity(instr, program)
    iteration = _loop_iteration_count(
        instr=instr,
        program=program,
        loops=loops,
        run_path=run_path,
    )
    return _validate_path_segment(f"{loop_identity}[{iteration}]")


def _stage_reentry_points_for(stages: list[str]) -> dict[str, Any]:
    """Return phase-name to stable-stage-id mappings for completed stages."""
    stage_reentry_points: dict[str, Any] = {}
    for stage_id in stages:
        parts = stage_id.split("__")
        if len(parts) >= 2:
            stage_reentry_points[parts[-2]] = stage_id
    return stage_reentry_points


def _hook_checkpoint_effect_metadata(hooks: Any) -> dict[str, Any] | None:
    """Walk wrapper hooks and return the latest effect metadata snapshot."""
    current = hooks
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        getter = getattr(current, "checkpoint_effect_metadata", None)
        if callable(getter):
            metadata = getter()
            if isinstance(metadata, dict):
                return dict(metadata)
        current = getattr(current, "_inner", None)
    return None


def _should_skip_effect_execution(ctx: Mapping[str, Any]) -> bool:
    effect = ctx.get("effect")
    if not isinstance(effect, Mapping):
        return False
    return effect.get("duplicate_action") == "skip"


def _reconcile_resumed_effect(
    *,
    resume_cursor_data: Mapping[str, Any] | None,
    instr: NativeInstruction,
    ctx: Mapping[str, Any],
    state: Mapping[str, Any],
    artifact_root: str | Path,
) -> ReconcileDecision | None:
    if resume_cursor_data is None or not instr.operation:
        return None
    effect = resume_cursor_data.get("effect")
    if not isinstance(effect, Mapping):
        return None
    if not _effect_matches_instruction(effect, instr, ctx):
        return None

    lifecycle_state = effect.get("lifecycle_state")
    if lifecycle_state == "fulfilled":
        return _fulfilled_effect_skip_decision(effect)

    metadata = _reconcile_metadata_from_effect(effect, state)
    decision = _dispatch_reconcile_decision(
        artifact_root=artifact_root,
        metadata=metadata,
        effect=effect,
    )
    if decision.blocked:
        raise NativeRuntimeError(_format_reconcile_block(instr, effect, decision))
    return decision


def _reconcile_child_resume_cursor(
    *,
    child_artifact_root: Path,
    child_program: NativeProgram,
    persistence_backend: NativePersistenceBackend | None,
) -> None:
    child_backend, child_scope = _runtime_persistence_binding(
        child_artifact_root,
        persistence_backend=persistence_backend,
    )
    try:
        child_cursor = read_native_cursor(
            child_artifact_root,
            persistence_backend=child_backend,
            persistence_scope=child_scope,
            fallback_to_artifact_root=persistence_backend is None,
        )
    except NativeCursorCorruptError as exc:
        raise NativeRuntimeError(
            f"Cannot resume child pipeline from corrupt cursor at "
            f"{exc.cursor_path or child_artifact_root / 'resume_cursor.json'}: "
            f"{exc.detail}"
        ) from exc
    if child_cursor is None:
        return
    child_pc = child_cursor.get("native", {}).get("pc")
    if not isinstance(child_pc, int) or child_pc < 0 or child_pc >= len(child_program.instructions):
        return
    frames = child_cursor.get("frames")
    child_state: Mapping[str, Any] = {}
    if isinstance(frames, Mapping) and isinstance(frames.get("__state__"), Mapping):
        child_state = frames["__state__"]
    instr = child_program.instructions[child_pc]
    run_path = child_cursor.get("run_path")
    if not isinstance(run_path, str) or not run_path:
        run_path = ROOT_PATH
    ctx = {"step_path": _step_path_for_instr(run_path, instr)}
    _reconcile_resumed_effect(
        resume_cursor_data=child_cursor,
        instr=instr,
        ctx=ctx,
        state=child_state,
        artifact_root=child_artifact_root,
    )


def _effect_matches_instruction(
    effect: Mapping[str, Any],
    instr: NativeInstruction,
    ctx: Mapping[str, Any],
) -> bool:
    key = effect.get("idempotency_key")
    if isinstance(key, str) and instr.idempotency_key == key:
        return True
    step_path = effect.get("step_path")
    if isinstance(step_path, str) and step_path == ctx.get("step_path"):
        return True
    return (
        effect.get("operation") == instr.operation
        and effect.get("target") == instr.target
        and instr.operation is not None
    )


def _reconcile_metadata_from_effect(
    effect: Mapping[str, Any],
    state: Mapping[str, Any],
) -> ReconcileMetadata:
    hints = _effect_reconcile_hints(effect, state)
    merged: dict[str, Any] = dict(effect)
    merged.update(hints)
    return ReconcileMetadata(
        operation=str(merged.get("operation") or ""),
        target=_optional_str(merged.get("target")),
        owned_paths=frozenset(
            path
            for path in merged.get("owned_paths", ())
            if isinstance(path, str) and path
        ),
        expected_ref=_optional_str(merged.get("expected_ref")),
        expected_commit=_optional_str(merged.get("expected_commit")),
        expected_content=_optional_str(merged.get("expected_content")),
        expected_sha256=_optional_str(merged.get("expected_sha256")),
    )


def _effect_reconcile_hints(
    effect: Mapping[str, Any],
    state: Mapping[str, Any],
) -> Mapping[str, Any]:
    raw = state.get("__effect_reconcile__")
    if not isinstance(raw, Mapping):
        return {}
    for key in (effect.get("idempotency_key"), effect.get("step_path")):
        if isinstance(key, str) and isinstance(raw.get(key), Mapping):
            return raw[key]
    return {}


def _dispatch_reconcile_decision(
    *,
    artifact_root: str | Path,
    metadata: ReconcileMetadata,
    effect: Mapping[str, Any],
) -> ReconcileDecision:
    operation = metadata.operation
    if operation == "file_write":
        return reconcile_file_write(_effect_file_path(artifact_root, metadata), metadata)

    repo_path = _effect_path(
        artifact_root,
        _optional_str(effect.get("repo_path")),
        default=Path(artifact_root),
    )
    status_path = _effect_path(
        artifact_root,
        _optional_str(effect.get("status_path")),
        default=repo_path,
    )
    if operation == "git_branch_create":
        return reconcile_git_branch_create(
            repo_path,
            metadata,
            status_path=status_path,
        )
    if operation == "git_commit":
        return reconcile_git_commit(repo_path, metadata, status_path=status_path)
    if operation == "git_worktree_op":
        return reconcile_git_worktree(repo_path, metadata, status_path=status_path)
    return ReconcileDecision(
        state="unknown",
        action="block",
        continue_execution=False,
        skip_execution=False,
        detail=f"unsupported side-effect operation: {operation!r}",
        required_metadata=(),
    )


def _fulfilled_effect_skip_decision(effect: Mapping[str, Any]) -> ReconcileDecision:
    return ReconcileDecision(
        state="fulfilled_duplicate",
        action="skip",
        continue_execution=False,
        skip_execution=True,
        detail=f"side effect already fulfilled: {effect.get('idempotency_key')!r}",
        required_metadata=(),
    )


def _reconcile_decision_payload(decision: ReconcileDecision) -> dict[str, Any]:
    return {
        "state": decision.state,
        "action": decision.action,
        "continue_execution": decision.continue_execution,
        "skip_execution": decision.skip_execution,
        "detail": decision.detail,
        "required_metadata": list(decision.required_metadata),
    }


def _format_reconcile_block(
    instr: NativeInstruction,
    effect: Mapping[str, Any],
    decision: ReconcileDecision,
) -> str:
    return (
        "Cannot resume native side-effecting step "
        f"{instr.name or instr.op!r} ({effect.get('idempotency_key')!r}): "
        f"reconcile state={decision.state!r}, action={decision.action!r}, "
        f"detail={decision.detail!r}, required_metadata={list(decision.required_metadata)!r}."
    )


def _effect_file_path(
    artifact_root: str | Path,
    metadata: ReconcileMetadata,
) -> Path:
    target = metadata.target
    if target:
        return _effect_path(artifact_root, target, default=Path(artifact_root))
    return Path(artifact_root)


def _effect_path(
    artifact_root: str | Path,
    raw_path: str | None,
    *,
    default: Path,
) -> Path:
    if raw_path is None:
        return default
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path(artifact_root) / path


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _resolve_native_human_gate_artifact_path(
    artifact_root: str | Path,
    artifact_stage: str,
) -> str | None:
    """Best-effort native equivalent of the graph gate's artifact_path field."""
    if not artifact_stage:
        return None
    candidate = Path(artifact_root) / artifact_stage
    if candidate.exists():
        return str(candidate)
    return None


def _build_cursor_dict(
    *,
    stage: str,
    pc: int,
    reentry_stage: str | None,
    stages: list[str],
    loops: dict[str, int],
    frames: dict[str, Any],
    state: dict[str, Any],
    envelope: Any = None,
    final: bool = False,
    cursor_id: str | None = None,
    effect: dict[str, Any] | None = None,
    resume_cursor: str | None = None,
    native_extra: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a cursor dict matching the shape written by :func:`persist_native_cursor`.

    The returned dict mirrors the on-disk ``resume_cursor.json`` shape so
    ``on_checkpoint`` receivers see exactly what was persisted.  When
    *final* is ``True`` (clean completion), a ``final`` marker is included.

    Includes additive ``cursor_id`` and ``stage_reentry_points`` for
    graph-compatible reentry metadata (M2 requirement).

    When *extra* is provided, its keys are merged into the top-level
    cursor dict as additive native restoration metadata (e.g. human-gate
    ``suspension_kind``, ``artifact_stage``, ``choices``).
    """
    from arnold.pipeline.native.checkpoint import NATIVE_CURSOR_VERSION

    frames_with_state = dict(frames)
    frames_with_state["__state__"] = _jsonable_value(dict(state))
    if envelope is not None:
        frames_with_state["__envelope__"] = _serialize_envelope(envelope)

    native_payload: dict[str, Any] = {
        "pc": pc,
        "version": NATIVE_CURSOR_VERSION,
    }
    if native_extra:
        native_payload.update(
            {
                key: value
                for key, value in native_extra.items()
                if key not in {"pc", "version"}
            }
        )

    cursor: dict[str, Any] = {
        "stage": stage,
        "resume_cursor": resume_cursor,
        "reentry_stage": reentry_stage,
        "stages": list(stages),
        "loops": dict(loops),
        "frames": frames_with_state,
        "native": native_payload,
        "cursor_id": cursor_id,
        "stage_reentry_points": _stage_reentry_points_for(stages),
    }
    if effect is not None:
        cursor["effect"] = dict(effect)
    # Merge additive native restoration metadata if provided.
    if extra:
        cursor.update(extra)
    if final:
        cursor["final"] = True
    return cursor


def _child_artifact_root(
    artifact_root: str | Path,
    *,
    child_name: str,
    call_site_path: Iterable[Any],
) -> Path:
    segments = _normalize_call_site_segments(call_site_path)
    if not segments:
        segments = (_safe_name(child_name),)
    child_dir = "_child_" + "_".join(_safe_name(segment) for segment in segments)
    return Path(artifact_root) / child_dir


def _child_cursor_path_for_parent(
    artifact_root: str | Path,
    child_artifact_root: Path,
) -> str:
    child_cursor_path = child_artifact_root / "resume_cursor.json"
    try:
        return child_cursor_path.relative_to(Path(artifact_root)).as_posix()
    except ValueError:
        return child_cursor_path.as_posix()


def _composite_resume_child_root(
    *,
    artifact_root: str | Path,
    composite: Mapping[str, Any] | None,
    parent_pc: int,
    child_run_path: str,
) -> Path | None:
    if not isinstance(composite, Mapping):
        return None
    parent = composite.get("parent")
    child = composite.get("child")
    if not isinstance(parent, Mapping) or not isinstance(child, Mapping):
        return None
    if parent.get("pc") != parent_pc:
        return None
    saved_child_run_path = child.get("run_path")
    if (
        isinstance(saved_child_run_path, str)
        and _normalize_run_path(saved_child_run_path) != _normalize_run_path(child_run_path)
    ):
        return None
    cursor_path = child.get("cursor_path")
    if not isinstance(cursor_path, str) or not cursor_path:
        return None
    return Path(artifact_root) / cursor_path


def _parallel_map_progress_key(pc: int) -> str:
    return f"__parallel_map_progress_pc_{pc}__"


def _restore_parallel_map_progress(
    frames: dict[str, Any],
    *,
    pc: int,
) -> tuple[list[Any], Any, int]:
    raw_progress = frames.pop(_parallel_map_progress_key(pc), None)
    if not isinstance(raw_progress, Mapping):
        return [], None, 0
    raw_results = raw_progress.get("completed_results")
    completed_results = list(raw_results) if isinstance(raw_results, list) else []
    raw_next_index = raw_progress.get("next_index")
    next_index = raw_next_index if isinstance(raw_next_index, int) else len(completed_results)
    if next_index < 0:
        next_index = 0
    raw_envelope = raw_progress.get("mapper_envelope")
    mapper_envelope = (
        _deserialize_envelope(raw_envelope) if raw_envelope is not None else None
    )
    return completed_results, mapper_envelope, next_index


def _persist_parent_child_entry_cursor(
    *,
    artifact_root: str | Path,
    persistence_backend: NativePersistenceBackend,
    persistence_scope: NativePersistenceScope,
    child_persistence_backend: NativePersistenceBackend | None,
    child_artifact_root: Path,
    program: NativeProgram,
    instr: NativeInstruction,
    pc: int,
    current_run_path: str,
    child_run_path: str,
    path_stack: list[_PathFrame],
    stages: list[str],
    loops: dict[str, int],
    frames: dict[str, Any],
    state: dict[str, Any],
    envelope: Any,
    cursor_id: str | None,
    suspension_kind: str | None = None,
    effect: dict[str, Any] | None = None,
    parent_frame_extra: Mapping[str, Any] | None = None,
    pack_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    stage_id = f"{_safe_name(program.name)}__{instr.name}__pc{pc}"
    parent_frames = dict(frames)
    if parent_frame_extra:
        parent_frames.update(dict(parent_frame_extra))
    frames_with_state = dict(frames)
    frames_with_state["__state__"] = _jsonable_value(dict(state))
    if envelope is not None:
        frames_with_state["__envelope__"] = _serialize_envelope(envelope)
    path_metadata = _cursor_path_metadata(
        program=program,
        pc=pc,
        run_path=current_run_path,
        path_stack=path_stack,
    )
    if suspension_kind == "child_suspended":
        child_backend, child_scope = _runtime_persistence_binding(
            child_artifact_root,
            persistence_backend=child_persistence_backend,
        )
        child_cursor = read_native_cursor(
            child_artifact_root,
            persistence_backend=child_backend,
            persistence_scope=child_scope,
            fallback_to_artifact_root=child_persistence_backend is None,
        )
        if child_cursor is not None:
            for key in ("run_path", "step_path", "call_site_path", "path_stack"):
                value = child_cursor.get(key)
                if value is not None:
                    path_metadata[key] = value
    composite = {
        "kind": "parent_child",
        "parent": {
            "pc": pc,
            "run_path": current_run_path,
            "path_stack": _serialize_path_stack(path_stack),
            "state": _jsonable_value(dict(state)),
            "stages": list(stages),
            "loops": dict(loops),
            "frames": _jsonable_value(parent_frames),
            "envelope": _serialize_envelope(envelope) if envelope is not None else None,
            "cursor_id": cursor_id,
        },
        "child": {
            "cursor_path": _child_cursor_path_for_parent(
                artifact_root,
                child_artifact_root,
            ),
            "run_path": child_run_path,
            "call_site_path": list(_call_site_path_for_run_path(child_run_path)),
        },
    }

    native_extra = _native_extra_with_pack_provenance(
        (
            {"suspension_kind": suspension_kind}
            if suspension_kind is not None
            else None
        ),
        pack_provenance,
    )
    extra: dict[str, Any] = {**path_metadata, "composite": composite}
    if suspension_kind is not None:
        extra["suspension_kind"] = suspension_kind

    persist_native_cursor(
        artifact_root,
        persistence_backend=persistence_backend,
        persistence_scope=persistence_scope,
        stage=stage_id,
        pc=pc,
        stages=list(stages),
        reentry_stage=stage_id,
        loops=dict(loops),
        frames=frames_with_state,
        cursor_id=cursor_id,
        stage_reentry_points=_stage_reentry_points_for(stages),
        effect=effect,
        native_extra=native_extra,
        **extra,
    )
    return _build_cursor_dict(
        stage=stage_id,
        pc=pc,
        reentry_stage=stage_id,
        stages=list(stages),
        loops=dict(loops),
        frames=frames_with_state,
        state=state,
        envelope=envelope,
        cursor_id=cursor_id,
        effect=effect,
        native_extra=native_extra,
        extra=extra,
    )


def _clear_parent_child_entry_cursor(
    *,
    artifact_root: str | Path,
    persistence_backend: NativePersistenceBackend,
    persistence_scope: NativePersistenceScope,
    child_artifact_root: Path,
    pc: int,
) -> None:
    payload = persistence_backend.read_resume_cursor(persistence_scope)
    if payload is None:
        return
    native = payload.get("native")
    composite = payload.get("composite")
    if not isinstance(native, dict) or native.get("pc") != pc:
        return
    if not isinstance(composite, dict) or composite.get("kind") != "parent_child":
        return
    child = composite.get("child")
    if not isinstance(child, dict):
        return
    if child.get("cursor_path") != _child_cursor_path_for_parent(
        artifact_root,
        child_artifact_root,
    ):
        return
    persistence_backend.delete_resume_cursor(persistence_scope)


def _reentry_stage_for_pc(program: NativeProgram, pc: int) -> str | None:
    """Return the stable native stage identifier for *pc*, following jumps."""
    instructions = program.instructions
    visited: set[int] = set()
    cur = pc
    while 0 <= cur < len(instructions):
        if cur in visited:
            return None
        visited.add(cur)
        instr = instructions[cur]
        if instr.op in {"phase", "decision"}:
            return f"{program.name}__{instr.name}__pc{instr.pc}"
        if instr.op == "jump":
            cur = instr.next_pc if instr.next_pc is not None else -1
            continue
        if instr.op == "halt":
            return "halt"
        cur += 1
    return None


def _persist_suspension(
    *,
    artifact_root: str | Path,
    persistence_backend: NativePersistenceBackend,
    persistence_scope: NativePersistenceScope,
    program: NativeProgram,
    stage: str,
    pc: int,
    reentry_stage: str | None,
    stages: list[str],
    loops: dict[str, int],
    frames: dict[str, Any],
    state: dict[str, Any],
    envelope: Any = None,
    cursor_id: str | None = None,
    path_metadata: Mapping[str, Any] | None = None,
    effect: dict[str, Any] | None = None,
    pack_provenance: Mapping[str, Any] | None = None,
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
        frames_with_state["__state__"] = _jsonable_value(dict(state))
        if envelope is not None:
            frames_with_state["__envelope__"] = _serialize_envelope(envelope)

        # Build stage_reentry_points from completed stages
        stage_reentry_points: dict[str, Any] = {}
        for stage_id in stages:
            parts = stage_id.split("__")
            if len(parts) >= 2:
                phase_name = parts[-2]
                stage_reentry_points[phase_name] = stage_id

        persist_native_cursor(
            artifact_root,
            persistence_backend=persistence_backend,
            persistence_scope=persistence_scope,
            stage=stage,
            pc=pc,
            stages=list(stages),
            reentry_stage=reentry_stage,
            loops=dict(loops),
            frames=frames_with_state,
            cursor_id=cursor_id,
            stage_reentry_points=stage_reentry_points,
            effect=effect,
            native_extra=_native_extra_with_pack_provenance(None, pack_provenance),
            **dict(path_metadata or _cursor_path_metadata(
                program=program,
                pc=pc,
                run_path=ROOT_PATH,
                path_stack=[],
            )),
        )
    except Exception:
        # Best-effort: if persist fails, execution result still carries
        # the pc/stages so the caller can retry or log.
        pass


def _extract_state_patch(result: Any) -> dict[str, Any]:
    """Return a normalized ``state_patch`` mapping from a phase result."""
    patch = getattr(result, "state_patch", {})
    if isinstance(patch, dict):
        return dict(patch)
    if hasattr(patch, "items"):
        try:
            return dict(patch.items())
        except Exception:
            return {}
    return {}


def _contract_result_is_suspended(contract_result: Any) -> bool:
    """Return True when *contract_result* carries ContractStatus.SUSPENDED."""
    if contract_result is None:
        return False
    status = getattr(contract_result, "status", None)
    return status == "suspended" or getattr(status, "value", None) == "suspended"


def _serialize_contract_result(contract_result: Any) -> Any:
    """Return a JSON-compatible representation of a ContractResult-like object."""
    if contract_result is None:
        return None
    if hasattr(contract_result, "to_json"):
        raw = contract_result.to_json()
        return _jsonable_value(raw)
    if isinstance(contract_result, Mapping):
        return _jsonable_value(dict(contract_result))
    return _jsonable_value(contract_result)


def _serialize_contract_suspension(contract_result: Any) -> Any:
    """Return the serialized suspension payload from a ContractResult-like object."""
    if contract_result is None:
        return None
    suspension = getattr(contract_result, "suspension", None)
    if suspension is None and isinstance(contract_result, Mapping):
        suspension = contract_result.get("suspension")
    if suspension is None:
        return None
    if hasattr(suspension, "to_json"):
        return _jsonable_value(suspension.to_json())
    if isinstance(suspension, Mapping):
        return _jsonable_value(dict(suspension))
    return _jsonable_value(suspension)


def _contract_resume_cursor(contract_result: Any) -> str | None:
    """Extract an opaque resume cursor from a suspended contract if present."""
    suspension = getattr(contract_result, "suspension", None)
    if suspension is None and isinstance(contract_result, Mapping):
        suspension = contract_result.get("suspension")
    resume_cursor = None
    if suspension is not None:
        resume_cursor = getattr(suspension, "resume_cursor", None)
        if resume_cursor is None and isinstance(suspension, Mapping):
            resume_cursor = suspension.get("resume_cursor")
    if resume_cursor is None:
        return None
    return str(resume_cursor)


def _serialize_envelope(envelope: Any) -> Any:
    """Return a JSON-serializable representation of *envelope*."""
    if envelope is None:
        return None
    if hasattr(envelope, "_to_jsonable"):
        return {"__runtime_envelope__": envelope._to_jsonable()}
    if hasattr(envelope, "to_jsonable"):
        return {"__run_envelope__": envelope.to_jsonable()}
    if hasattr(envelope, "to_json"):
        raw = envelope.to_json()
        if isinstance(raw, dict):
            return {"__run_envelope__": raw}
        if isinstance(raw, str):
            return {"__runtime_envelope_json__": raw}
    return envelope


def _jsonable_value(value: Any) -> Any:
    """Return a JSON-serializable native cursor payload value."""
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_json"):
        return _jsonable_value(value.to_json())
    if isinstance(value, Mapping):
        return {str(key): _jsonable_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable_value(item) for item in value]
    if isinstance(value, list):
        return [_jsonable_value(item) for item in value]
    return value


def _deserialize_envelope(payload: Any) -> Any:
    """Rehydrate a serialized envelope payload when possible."""
    if not isinstance(payload, dict):
        return payload
    if "__runtime_envelope__" in payload:
        from arnold.runtime.envelope import RuntimeEnvelope

        data = payload["__runtime_envelope__"]
        if isinstance(data, dict):
            return RuntimeEnvelope._from_jsonable(data)
    if "__runtime_envelope_json__" in payload:
        from arnold.runtime.envelope import RuntimeEnvelope

        data = payload["__runtime_envelope_json__"]
        if isinstance(data, str):
            return RuntimeEnvelope.from_json(data)
    if "__run_envelope__" in payload:
        from arnold.runtime.envelope import RunEnvelope

        data = payload["__run_envelope__"]
        if isinstance(data, dict):
            return RunEnvelope.from_jsonable(data)
    return payload


def _should_emit_stage_complete(instr: NativeInstruction) -> bool:
    """Allow callables to suppress public stage-complete hooks."""
    func = getattr(instr, "func", None)
    if func is None:
        return True
    return bool(getattr(func, "__native_runtime_emit_stage_complete__", True))


__all__ = [
    "NativeExecutionResult",
    "NativeRuntimeError",
    "run_native_pipeline",
]
