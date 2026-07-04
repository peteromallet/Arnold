"""Optional native trace emission — write state, events, artifact inventory,
stage sequence, and final checkpoint notification to a trace directory.

Implemented as a :class:`NativeTraceHooks` that wraps an inner
:class:`NativeRuntimeHooks` instance and emits trace data to a
``trace_dir`` when it is set.  When ``trace_dir`` is ``None`` (the
default), the wrapper passes through to the inner hooks with zero
overhead beyond a few attribute accesses — there are no allocations,
no file opens, and no event journal writes.

Trace directory layout::

    <trace_dir>/
        state.json          # snapshot after each stage + final
        events.ndjson       # NdjsonEventJournal-compatible event stream
        stages.json         # ordered stage sequence
        artifacts.json      # content-hash inventory of output files
        checkpoint.json     # final checkpoint notification

Example usage through :func:`run_native_pipeline`::

    result = run_native_pipeline(
        program,
        artifact_root="./run_01",
        trace_dir="./run_01/traces",
    )
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import PATH_DELIMITER, ROOT_PATH, NativeInstruction, NativeProgram
from arnold.runtime.event_journal import NdjsonEventJournal


__all__ = [
    "NativeTraceHooks",
    "write_artifact_inventory",
]

# ── helpers ───────────────────────────────────────────────────────────


def _json_dumps(obj: Any) -> str:
    """Serialize *obj* to canonical JSON (sorted keys, compact)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256_hex(data: bytes) -> str:
    """Return ``sha256:<hex>`` string for *data*."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _ensure_dir(path: Path) -> None:
    """Create directory *path* if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


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


def _parent_trace_path(path: Any) -> str | None:
    normalized = _normalize_trace_path(path)
    parts = normalized.split(PATH_DELIMITER)
    if len(parts) <= 1:
        return None
    return PATH_DELIMITER.join(parts[:-1])


def _trace_stage_id(stage_id: str) -> str:
    """Normalize runtime stage ids to the short trace form.

    Runtime cursors store stable ids like ``program__step__pc1`` while
    trace fixtures historically record ``step__pc1``. Keep that public
    trace shape stable across fresh and resumed runs.
    """
    parts = stage_id.split("__")
    if len(parts) >= 2:
        return "__".join(parts[-2:])
    return stage_id


def write_artifact_inventory(root: str | Path) -> dict[str, str]:
    """Walk *root* and return a ``{relpath: sha256:<hex>}`` mapping.

    Directories and non-regular files are skipped.  Symlinks are
    followed.  Files larger than 10 MiB are hashed in 1 MiB chunks.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return {}
    inventory: dict[str, str] = {}
    for entry in sorted(root_path.rglob("*")):
        if not entry.is_file():
            continue
        rel = str(entry.relative_to(root_path))
        try:
            sha = hashlib.sha256()
            with open(entry, "rb") as fh:
                while True:
                    chunk = fh.read(1024 * 1024)
                    if not chunk:
                        break
                    sha.update(chunk)
            inventory[rel] = "sha256:" + sha.hexdigest()
        except (OSError, PermissionError):
            inventory[rel] = "error:unreadable"
    return inventory


# ── NativeTraceHooks ──────────────────────────────────────────────────


class NativeTraceHooks:
    """Native runtime hooks that emit native-trace artifacts when enabled.

    Wraps an inner :class:`NativeRuntimeHooks` (default
    :class:`NullNativeRuntimeHooks`) and delegates every callback to it.
    When *trace_dir* is set, additional trace data is written to the
    trace directory at the documented insertion points:

    * ``on_step_start`` — writes a ``phase.start`` event.
    * ``on_step_end`` — writes a ``phase.end`` event.
    * ``on_step_error`` — writes an ``error`` event.
    * ``on_stage_complete`` — snapshots ``state.json``.
    * ``on_checkpoint`` — writes ``stages.json``, ``artifacts.json``,
      and ``checkpoint.json``.

    When *trace_dir* is ``None`` every callback is a pure pass-through
    to the inner hooks — there are no file-system operations.
    """

    halt_reason: str | None

    def __init__(
        self,
        inner: NativeRuntimeHooks | None = None,
        *,
        trace_dir: str | Path | None = None,
        artifact_root: str | Path = ".",
    ) -> None:
        self._inner: NativeRuntimeHooks = (
            inner if inner is not None else NullNativeRuntimeHooks()
        )
        self._trace_dir: Path | None = (
            Path(trace_dir) if trace_dir is not None else None
        )
        self._artifact_root: Path = Path(artifact_root)
        self.halt_reason: str | None = None
        self._journal: NdjsonEventJournal | None = None
        self._stage_seq: list[str] = []
        self._active_runs: list[str] = []
        self._tree_nodes: dict[str, dict[str, Any]] = {}
        self._tree_order: list[str] = []

        if self._trace_dir is not None:
            _ensure_dir(self._trace_dir)
            self._journal = NdjsonEventJournal(self._trace_dir)
            self._journal.emit("pipeline.init", payload={"status": "started"})
            self._write_state_json({})

    def seed_stage_sequence(self, stages: list[str]) -> None:
        """Seed the trace stage sequence from restored runtime stages."""
        self._stage_seq = [_trace_stage_id(stage_id) for stage_id in stages]

    # ── private helpers ─────────────────────────────────────────────

    def _write_state_json(self, state: dict[str, Any]) -> None:
        """Write *state* as ``state.json`` in the trace directory."""
        if self._trace_dir is None:
            return
        (self._trace_dir / "state.json").write_text(
            _json_dumps(state), encoding="utf-8"
        )

    def _write_stages_json(self) -> None:
        """Write the ordered stage sequence as ``stages.json``."""
        if self._trace_dir is None:
            return
        (self._trace_dir / "stages.json").write_text(
            _json_dumps(self._stage_seq), encoding="utf-8"
        )

    def _write_tree_json(self) -> None:
        if self._trace_dir is None:
            return
        nodes = [self._tree_nodes[path] for path in self._tree_order if path in self._tree_nodes]
        payload = {
            "root_path": ROOT_PATH,
            "nodes": nodes,
        }
        (self._trace_dir / "tree.json").write_text(
            _json_dumps(payload), encoding="utf-8"
        )

    def _write_artifacts_json(self) -> None:
        """Write an artifact inventory as ``artifacts.json``."""
        if self._trace_dir is None:
            return
        inventory = write_artifact_inventory(self._artifact_root)
        (self._trace_dir / "artifacts.json").write_text(
            _json_dumps(inventory), encoding="utf-8"
        )

    def _write_checkpoint_json(self, cursor: dict[str, Any], final: bool) -> None:
        """Write the final checkpoint notification as ``checkpoint.json``."""
        if self._trace_dir is None:
            return
        payload: dict[str, Any] = {
            "final": final,
            "stage_sequence": list(self._stage_seq),
            "cursor_stage": cursor.get("stage", ""),
            "cursor_pc": (
                cursor.get("native", {}).get("pc")
                if isinstance(cursor.get("native"), dict)
                else None
            ),
            "run_path": cursor.get("run_path"),
            "step_path": cursor.get("step_path"),
            "call_site_path": cursor.get("call_site_path"),
            "tree_file": "tree.json",
            "tree_node_count": len(self._tree_nodes),
        }
        (self._trace_dir / "checkpoint.json").write_text(
            _json_dumps(payload), encoding="utf-8"
        )

    def _active_depth(self) -> int:
        return len(self._active_runs)

    def _should_write_root_artifacts(self) -> bool:
        return self._active_depth() <= 1

    def _trace_context(
        self,
        *,
        instr: NativeInstruction | None = None,
        ctx: Mapping[str, Any] | None = None,
        path: Any = None,
        run_path: Any = None,
        step_path: Any = None,
        parent_path: Any = None,
        parent_run_path: Any = None,
        call_site_path: Any = None,
        kind: str | None = None,
    ) -> dict[str, Any]:
        raw_run_path = run_path
        if raw_run_path is None and ctx is not None:
            raw_run_path = ctx.get("run_path")
        normalized_run_path = _normalize_trace_path(raw_run_path)
        raw_step_path = step_path
        if raw_step_path is None and ctx is not None:
            raw_step_path = ctx.get("step_path")
        normalized_step_path = (
            _normalize_trace_path(raw_step_path) if raw_step_path else None
        )
        raw_call_site_path = call_site_path
        if raw_call_site_path is None and ctx is not None:
            raw_call_site_path = ctx.get("call_site_path")
        normalized_call_site_path = []
        if isinstance(raw_call_site_path, (list, tuple)):
            normalized_call_site_path = [str(segment) for segment in raw_call_site_path]
        raw_path = path if path is not None else normalized_step_path or normalized_run_path
        normalized_path = _normalize_trace_path(raw_path)
        raw_parent_path = parent_path
        if raw_parent_path is None:
            raw_parent_path = _parent_trace_path(normalized_path)
        normalized_parent_path = (
            _normalize_trace_path(raw_parent_path) if raw_parent_path else None
        )
        raw_parent_run_path = parent_run_path
        if raw_parent_run_path is None and ctx is not None:
            raw_parent_run_path = ctx.get("parent_run_path")
        normalized_parent_run_path = (
            _normalize_trace_path(raw_parent_run_path) if raw_parent_run_path else None
        )
        trace_kind = kind or (instr.op if instr is not None else "run")
        trace_ctx: dict[str, Any] = {
            "path": normalized_path,
            "parent_path": normalized_parent_path,
            "run_path": normalized_run_path,
            "step_path": normalized_step_path,
            "parent_run_path": normalized_parent_run_path,
            "call_site_path": normalized_call_site_path,
            "kind": trace_kind,
        }
        if instr is not None:
            trace_ctx["op"] = instr.op
            trace_ctx["name"] = instr.name
            trace_ctx["pc"] = instr.pc
        return trace_ctx

    def _ensure_tree_node(
        self,
        *,
        path: Any,
        kind: str,
        name: str,
        run_path: Any,
        step_path: Any = None,
        parent_path: Any = None,
        parent_run_path: Any = None,
        call_site_path: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        trace_ctx = self._trace_context(
            path=path,
            run_path=run_path,
            step_path=step_path,
            parent_path=parent_path,
            parent_run_path=parent_run_path,
            call_site_path=call_site_path,
            kind=kind,
        )
        node_path = trace_ctx["path"]
        node = self._tree_nodes.get(node_path)
        if node is None:
            node = {
                "path": node_path,
                "parent_path": trace_ctx["parent_path"],
                "run_path": trace_ctx["run_path"],
                "step_path": trace_ctx["step_path"],
                "parent_run_path": trace_ctx["parent_run_path"],
                "call_site_path": trace_ctx["call_site_path"],
                "kind": kind,
                "name": name,
                "children": [],
                "metadata": {},
            }
            self._tree_nodes[node_path] = node
            self._tree_order.append(node_path)
        else:
            node.update(
                {
                    "parent_path": trace_ctx["parent_path"],
                    "run_path": trace_ctx["run_path"],
                    "step_path": trace_ctx["step_path"],
                    "parent_run_path": trace_ctx["parent_run_path"],
                    "call_site_path": trace_ctx["call_site_path"],
                    "kind": kind,
                    "name": name,
                }
            )
        if metadata:
            node["metadata"].update(dict(metadata))
        parent = trace_ctx["parent_path"]
        if parent:
            parent_node = self._ensure_tree_node(
                path=parent,
                kind=self._tree_nodes.get(parent, {}).get("kind", "run"),
                name=parent.split(PATH_DELIMITER)[-1],
                run_path=parent,
                parent_path=_parent_trace_path(parent),
                parent_run_path=_parent_trace_path(parent),
                call_site_path=parent.split(PATH_DELIMITER)[1:],
            )
            if node_path not in parent_node["children"]:
                parent_node["children"].append(node_path)
        return node

    def on_run_enter(
        self,
        program: NativeProgram,
        *,
        run_path: str,
        parent_run_path: str | None = None,
        kind: str = "pipeline",
        call_site_path: tuple[str, ...] = (),
    ) -> None:
        normalized_run_path = _normalize_trace_path(run_path)
        parent_path = _normalize_trace_path(parent_run_path) if parent_run_path else _parent_trace_path(normalized_run_path)
        self._active_runs.append(normalized_run_path)
        node = self._ensure_tree_node(
            path=normalized_run_path,
            kind=kind,
            name=program.name,
            run_path=normalized_run_path,
            parent_path=parent_path,
            parent_run_path=parent_run_path,
            call_site_path=call_site_path,
            metadata={
                "program_name": program.name,
                "program_stable_id": program.stable_id,
                "status": "running",
            },
        )
        if self._journal is not None:
            self._journal.emit(
                "run.enter",
                payload={"trace": dict(node), "program_name": program.name, "program_stable_id": program.stable_id},
                phase=program.name,
            )

    def on_run_exit(
        self,
        program: NativeProgram,
        *,
        run_path: str,
        status: str,
    ) -> None:
        normalized_run_path = _normalize_trace_path(run_path)
        node = self._ensure_tree_node(
            path=normalized_run_path,
            kind=self._tree_nodes.get(normalized_run_path, {}).get("kind", "pipeline"),
            name=program.name,
            run_path=normalized_run_path,
            metadata={"program_name": program.name, "program_stable_id": program.stable_id, "status": status},
        )
        if self._journal is not None:
            self._journal.emit(
                "run.exit",
                payload={"trace": dict(node), "status": status},
                phase=program.name,
            )
        if self._active_runs and self._active_runs[-1] == normalized_run_path:
            self._active_runs.pop()
        elif normalized_run_path in self._active_runs:
            self._active_runs.remove(normalized_run_path)

    def on_parallel_map_enter(
        self,
        instr: NativeInstruction,
        *,
        run_path: str,
        path: str,
        parent_run_path: str | None = None,
        call_site_path: tuple[str, ...] = (),
    ) -> None:
        node = self._ensure_tree_node(
            path=path,
            kind="parallel_map",
            name=instr.name or instr.op,
            run_path=run_path,
            parent_path=run_path,
            parent_run_path=parent_run_path,
            call_site_path=call_site_path,
            metadata={"op": instr.op, "pc": instr.pc},
        )
        if self._journal is not None:
            self._journal.emit(
                "parallel_map.enter",
                payload={"trace": dict(node)},
                phase=instr.name,
            )

    def on_parallel_map_exit(
        self,
        instr: NativeInstruction,
        *,
        run_path: str,
        path: str,
    ) -> None:
        node = self._ensure_tree_node(
            path=path,
            kind="parallel_map",
            name=instr.name or instr.op,
            run_path=run_path,
            parent_path=run_path,
            metadata={"op": instr.op, "pc": instr.pc, "status": "completed"},
        )
        if self._journal is not None:
            self._journal.emit(
                "parallel_map.exit",
                payload={"trace": dict(node)},
                phase=instr.name,
            )

    def trace_only_step_start(
        self,
        instr: NativeInstruction,
        ctx: Mapping[str, Any],
    ) -> None:
        trace = self._trace_context(instr=instr, ctx=ctx)
        self._ensure_tree_node(
            path=trace["path"],
            kind=instr.op,
            name=instr.name or instr.op,
            run_path=trace["run_path"],
            step_path=trace["step_path"],
            parent_path=trace["parent_path"],
            parent_run_path=trace["parent_run_path"],
            call_site_path=trace["call_site_path"],
            metadata={"pc": instr.pc, "op": instr.op},
        )
        if self._journal is not None:
            self._journal.emit(
                "phase.start",
                payload={"phase": instr.name, "pc": instr.pc, "trace": trace},
                phase=instr.name,
            )

    def trace_only_step_end(
        self,
        instr: NativeInstruction,
        ctx: Mapping[str, Any],
    ) -> None:
        trace = self._trace_context(instr=instr, ctx=ctx)
        if self._journal is not None:
            self._journal.emit(
                "phase.end",
                payload={"phase": instr.name, "pc": instr.pc, "trace": trace},
                phase=instr.name,
            )

    def trace_only_step_error(
        self,
        instr: NativeInstruction,
        ctx: Mapping[str, Any],
        exc: BaseException,
    ) -> None:
        trace = self._trace_context(instr=instr, ctx=ctx)
        if self._journal is not None:
            self._journal.emit(
                "error",
                payload={
                    "phase": instr.name,
                    "pc": instr.pc,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "trace": trace,
                },
                phase=instr.name,
            )

    def trace_only_stage_complete(
        self,
        instr: NativeInstruction,
        ctx: Mapping[str, Any],
    ) -> None:
        stage_id = _trace_stage_id(f"{instr.name}__pc{instr.pc}")
        trace = self._trace_context(instr=instr, ctx=ctx)
        node = self._ensure_tree_node(
            path=trace["path"],
            kind=instr.op,
            name=instr.name or instr.op,
            run_path=trace["run_path"],
            step_path=trace["step_path"],
            parent_path=trace["parent_path"],
            parent_run_path=trace["parent_run_path"],
            call_site_path=trace["call_site_path"],
            metadata={"pc": instr.pc, "op": instr.op, "stage_id": stage_id},
        )
        self._stage_seq.append(stage_id)
        if self._journal is not None:
            self._journal.emit(
                "stage.complete",
                payload={"stage": stage_id, "pc": instr.pc, "trace": dict(node)},
                phase=instr.name,
            )

    # ── NativeRuntimeHooks callbacks ─────────────────────────────────

    def on_step_start(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        ctx = self._inner.on_step_start(instr, ctx)
        self.trace_only_step_start(instr, ctx)
        return ctx

    def on_step_end(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
    ) -> Any:
        result = self._inner.on_step_end(instr, ctx, result)
        self.trace_only_step_end(instr, ctx)
        return result

    def on_step_error(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        exc: BaseException,
    ) -> None:
        self._inner.on_step_error(instr, ctx, exc)
        self.trace_only_step_error(instr, ctx, exc)

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
        self.trace_only_stage_complete(instr, ctx)
        if self._should_write_root_artifacts():
            self._write_state_json(state)

    def on_checkpoint(
        self,
        cursor: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        self._inner.on_checkpoint(cursor, state)
        final = bool(cursor.get("final", False))
        if self._should_write_root_artifacts():
            self._write_state_json(state)
            self._write_stages_json()
            self._write_tree_json()
            self._write_artifacts_json()
            self._write_checkpoint_json(cursor, final=final)
        trace = self._trace_context(
            path=cursor.get("step_path") or cursor.get("run_path") or ROOT_PATH,
            run_path=cursor.get("run_path"),
            step_path=cursor.get("step_path"),
            call_site_path=cursor.get("call_site_path"),
        )
        if self._journal is not None:
            self._journal.emit(
                "checkpoint",
                payload={
                    "final": final,
                    "stage_count": len(self._stage_seq),
                    "trace": trace,
                },
            )

    def emit_pipeline_suspended(
        self,
        *,
        reason: str,
        run_path: Any = None,
        step_path: Any = None,
        call_site_path: Any = None,
    ) -> None:
        trace = self._trace_context(
            path=step_path or run_path or ROOT_PATH,
            run_path=run_path,
            step_path=step_path,
            call_site_path=call_site_path,
        )
        if self._journal is not None:
            self._journal.emit(
                "pipeline_suspended",
                payload={"reason": reason, "trace": trace},
            )

    def emit_pipeline_resumed(
        self,
        *,
        reason: str,
        run_path: Any = None,
        step_path: Any = None,
        call_site_path: Any = None,
    ) -> None:
        trace = self._trace_context(
            path=step_path or run_path or ROOT_PATH,
            run_path=run_path,
            step_path=step_path,
            call_site_path=call_site_path,
        )
        if self._journal is not None:
            self._journal.emit(
                "pipeline_resumed",
                payload={"reason": reason, "trace": trace},
            )
