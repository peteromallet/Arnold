"""Debug-only helpers for replaying a native run from recorded trace artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from arnold.pipeline.contract_validation import validate_payload_against_schema
from arnold.pipeline.native.checkpoint import (
    NATIVE_CURSOR_VERSION,
    NativeCursorCorruptError,
    persist_native_cursor,
    read_native_cursor,
)
from arnold.pipeline.native.ir import PATH_DELIMITER, ROOT_PATH, NativeProgram
from arnold.pipeline.native.runtime import NativeExecutionResult, run_native_pipeline


def _normalize_trace_path(path: Any) -> str:
    text = str(path or "").strip()
    if not text:
        return ROOT_PATH
    parts = [segment for segment in text.split(PATH_DELIMITER) if segment]
    if not parts:
        return ROOT_PATH
    if parts[0] != ROOT_PATH:
        parts.insert(0, ROOT_PATH)
    return PATH_DELIMITER.join(parts)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path} is not readable JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_tree_node(trace_dir: Path, target_path: str) -> dict[str, Any] | None:
    tree_payload = _read_json_object(trace_dir / "tree.json")
    nodes = tree_payload.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError(f"{trace_dir / 'tree.json'} must contain a nodes list")
    normalized_target = _normalize_trace_path(target_path)
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if _normalize_trace_path(node.get("path")) == normalized_target:
            return node
    return None


def _fallback_target_node(
    *,
    program: NativeProgram,
    checkpoint: Mapping[str, Any],
    target_path: str,
) -> dict[str, Any]:
    normalized_target = _normalize_trace_path(target_path)
    current_paths = {
        _normalize_trace_path(checkpoint.get("run_path")),
        _normalize_trace_path(checkpoint.get("step_path")),
    }
    if normalized_target not in current_paths:
        raise ValueError(f"Trace tree does not contain target path {normalized_target!r}")

    pc_value = checkpoint.get("cursor_pc")
    instr_name = normalized_target.split(PATH_DELIMITER)[-1]
    if isinstance(pc_value, int) and 0 <= pc_value < len(program.instructions):
        instr_name = program.instructions[pc_value].name or instr_name
    parent_path = (
        PATH_DELIMITER.join(normalized_target.split(PATH_DELIMITER)[:-1])
        if normalized_target != ROOT_PATH
        else None
    )
    return {
        "path": normalized_target,
        "run_path": checkpoint.get("run_path"),
        "step_path": checkpoint.get("step_path"),
        "parent_path": parent_path,
        "call_site_path": normalized_target.split(PATH_DELIMITER)[1:-1],
        "name": instr_name,
        "metadata": {"pc": pc_value} if isinstance(pc_value, int) else {},
    }


def _assert_checkpoint_owns_target(
    checkpoint: Mapping[str, Any],
    node: Mapping[str, Any],
) -> None:
    current_paths = {
        _normalize_trace_path(checkpoint.get("run_path")),
        _normalize_trace_path(checkpoint.get("step_path")),
    }
    node_paths = {
        _normalize_trace_path(node.get("path")),
        _normalize_trace_path(node.get("run_path")),
        _normalize_trace_path(node.get("step_path")),
    }
    if current_paths.isdisjoint(node_paths):
        raise ValueError(
            "start_from_trace only supports the current checkpoint location from a prior "
            "trace snapshot; the requested target path does not match checkpoint.json"
        )


def _phase_schema_for_pc(program: NativeProgram, pc: int) -> Mapping[str, Any] | None:
    if pc < 0 or pc >= len(program.instructions):
        return None
    instr = program.instructions[pc]
    for phase_ir in program.phases:
        if phase_ir.name == instr.name:
            return phase_ir.inputs_schema
    return None


def _validate_injected_state(
    *,
    program: NativeProgram,
    pc: int,
    candidate_state: Mapping[str, Any],
) -> None:
    schemas = [program.inputs_schema, _phase_schema_for_pc(program, pc)]
    for schema in schemas:
        if not isinstance(schema, Mapping):
            continue
        result = validate_payload_against_schema(candidate_state, schema)
        if result.diagnostics:
            detail = "; ".join(
                f"{diagnostic.payload_pointer}: {diagnostic.message}"
                for diagnostic in result.diagnostics
            )
            raise ValueError(f"Injected replay state failed schema validation: {detail}")

    if 0 <= pc < len(program.instructions):
        consumes = getattr(program.instructions[pc], "consumes", ()) or ()
        missing: list[str] = []
        for port in consumes:
            name = getattr(port, "port_name", getattr(port, "name", None))
            if isinstance(name, str) and name and name not in candidate_state:
                missing.append(name)
        if missing:
            raise ValueError(
                "Injected replay state is missing consumed ports required by the target "
                f"step: {sorted(set(missing))}"
            )


def _copy_source_artifacts(source_root: Path, artifact_root: Path) -> None:
    if artifact_root.exists():
        raise ValueError(
            f"Replay artifact root {artifact_root} must not exist; start_from_trace writes "
            "into a fresh destination"
        )
    shutil.copytree(source_root, artifact_root)


def _synthesize_resume_cursor(
    *,
    program: NativeProgram,
    checkpoint: Mapping[str, Any],
    node: Mapping[str, Any],
    state: Mapping[str, Any],
    artifact_root: Path,
) -> None:
    pc_value = checkpoint.get("cursor_pc")
    if not isinstance(pc_value, int):
        metadata = node.get("metadata")
        if isinstance(metadata, Mapping) and isinstance(metadata.get("pc"), int):
            pc_value = int(metadata["pc"])
        else:
            raise ValueError(
                "Trace artifacts do not include a resumable program counter for the target path"
            )

    stage = checkpoint.get("cursor_stage")
    if not isinstance(stage, str) or not stage:
        name = str(node.get("name") or f"pc{pc_value}")
        stage = f"{program.name}__{name}__pc{pc_value}"

    persist_native_cursor(
        artifact_root,
        stage=stage,
        pc=pc_value,
        stages=[],
        loops={},
        frames={"__state__": dict(state)},
        cursor_id=uuid4().hex,
        version=NATIVE_CURSOR_VERSION,
        run_path=node.get("run_path"),
        step_path=node.get("step_path"),
        call_site_path=node.get("call_site_path"),
        path_stack=[],
    )


def start_from_trace(
    program: NativeProgram,
    trace_dir: str | Path,
    target_path: str,
    artifact_root: str | Path,
    *,
    debug: bool = True,
    injected_state: Mapping[str, Any] | None = None,
) -> NativeExecutionResult:
    """Replay a prior native trace snapshot into a fresh artifact root.

    The helper is intentionally conservative: it only replays from the trace's
    current checkpoint location, copies the prior artifact root into a fresh
    destination without mutating the source, and treats state injection as an
    explicit debug/test-only escape hatch.
    """

    if injected_state is not None and not debug:
        raise ValueError(
            "Synthetic replay state injection is debug/test-only; pass debug=True "
            "to start_from_trace when injected_state is provided"
        )
    if injected_state is not None and not isinstance(injected_state, Mapping):
        raise ValueError("injected_state must be a mapping when provided")

    trace_root = Path(trace_dir)
    checkpoint = _read_json_object(trace_root / "checkpoint.json")
    node = _read_tree_node(trace_root, target_path)
    if node is None:
        node = _fallback_target_node(
            program=program,
            checkpoint=checkpoint,
            target_path=target_path,
        )
    _assert_checkpoint_owns_target(checkpoint, node)
    recorded_state = _read_json_object(trace_root / "state.json")

    candidate_state = dict(recorded_state)
    if injected_state is not None:
        candidate_state.update(dict(injected_state))

    pc_value = checkpoint.get("cursor_pc")
    if not isinstance(pc_value, int):
        metadata = node.get("metadata")
        pc_value = metadata.get("pc") if isinstance(metadata, Mapping) else None
    if not isinstance(pc_value, int):
        raise ValueError("Trace artifacts do not include a resumable program counter")

    _validate_injected_state(
        program=program,
        pc=pc_value,
        candidate_state=candidate_state,
    )

    source_root = trace_root.parent
    destination_root = Path(artifact_root)
    if source_root.resolve() == destination_root.resolve():
        raise ValueError(
            "start_from_trace requires a fresh artifact root distinct from the source"
        )
    _copy_source_artifacts(source_root, destination_root)

    try:
        existing_cursor = read_native_cursor(destination_root)
    except NativeCursorCorruptError as exc:
        raise ValueError(
            f"Copied source artifact root contains a corrupt native cursor: {exc.detail}"
        ) from exc

    if existing_cursor is None:
        _synthesize_resume_cursor(
            program=program,
            checkpoint=checkpoint,
            node=node,
            state=candidate_state,
            artifact_root=destination_root,
        )

    return run_native_pipeline(
        program,
        artifact_root=destination_root,
        resume=True,
        initial_state=dict(injected_state) if injected_state is not None else None,
    )


__all__ = ["start_from_trace"]
