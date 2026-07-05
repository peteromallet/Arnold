"""Optional native trace emission — write state, events, artifact inventory,
stage sequence, and final checkpoint notification to a trace directory.

Implemented as a :class:`NativeTraceHooks` that wraps an inner
:class:`NativeRuntimeHooks` instance and emits trace data to a
``trace_dir`` when it is set.  When ``trace_dir`` is ``None`` (the
default), the wrapper passes through to the inner hooks with zero
overhead beyond a few attribute accesses — there are no allocations,
no file opens, and no event journal writes unless a persistence backend
is provided explicitly.

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
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import PATH_DELIMITER, ROOT_PATH, NativeInstruction, NativeProgram
from arnold.pipeline.native.persistence import (
    FileNativePersistenceBackend,
    NativePersistenceBackend,
    NativePersistenceScope,
    bind_legacy_artifact_root,
)
from arnold.runtime.event_journal import BackendEventJournal, NdjsonEventJournal


__all__ = [
    "NativeTraceHooks",
    "write_artifact_inventory",
]

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


def _backend_for_trace_dir(
    trace_dir: str | Path,
) -> tuple[NativePersistenceBackend, NativePersistenceScope]:
    trace_root = Path(trace_dir)
    binding = bind_legacy_artifact_root(trace_root)
    backend = FileNativePersistenceBackend(
        lambda scope: trace_root
        if scope == binding.scope
        else (_ for _ in ()).throw(KeyError(scope))
    )
    return backend, binding.scope


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

    When neither *trace_dir* nor a persistence backend is provided, every
    callback is a pure pass-through to the inner hooks.
    """

    halt_reason: str | None

    def __init__(
        self,
        inner: NativeRuntimeHooks | None = None,
        *,
        trace_dir: str | Path | None = None,
        artifact_root: str | Path = ".",
        persistence_backend: NativePersistenceBackend | None = None,
        persistence_scope: NativePersistenceScope | None = None,
    ) -> None:
        self._inner: NativeRuntimeHooks = (
            inner if inner is not None else NullNativeRuntimeHooks()
        )
        self._trace_dir: Path | None = (
            Path(trace_dir) if trace_dir is not None else None
        )
        self._artifact_root: Path = Path(artifact_root)
        self.halt_reason: str | None = None
        if persistence_backend is not None or persistence_scope is not None:
            if persistence_backend is None or persistence_scope is None:
                raise ValueError(
                    "persistence_backend and persistence_scope must be provided together"
                )
            self._persistence_backend = persistence_backend
            self._persistence_scope = persistence_scope
        elif self._trace_dir is not None:
            self._persistence_backend, self._persistence_scope = _backend_for_trace_dir(
                self._trace_dir
            )
        else:
            self._persistence_backend = None
            self._persistence_scope = None
        self._journal: NdjsonEventJournal | BackendEventJournal | None = None
        self._stage_seq: list[str] = []
        self._active_runs: list[str] = []
        self._tree_nodes: dict[str, dict[str, Any]] = {}
        self._tree_order: list[str] = []

        if self._trace_dir is not None:
            _ensure_dir(self._trace_dir)
        if self._persistence_backend is not None and self._persistence_scope is not None:
            self._load_existing_tree_json()
            self._journal = BackendEventJournal(
                self._persistence_backend,
                self._persistence_scope,
            )
            self._journal.emit("pipeline.init", payload={"status": "started"})
            self._write_state_json({})

    def seed_stage_sequence(self, stages: list[str]) -> None:
        """Seed the trace stage sequence from restored runtime stages."""
        self._stage_seq = [_trace_stage_id(stage_id) for stage_id in stages]

    # ── private helpers ─────────────────────────────────────────────

    def _write_state_json(self, state: dict[str, Any]) -> None:
        """Write *state* as ``state.json`` in the trace directory."""
        if self._persistence_backend is None or self._persistence_scope is None:
            return
        from arnold.pipeline.native.runtime import _jsonable_value

        self._persistence_backend.write_trace_artifact(
            self._persistence_scope,
            name="state.json",
            payload=_jsonable_value(state),
        )

    def _write_stages_json(self) -> None:
        """Write the ordered stage sequence as ``stages.json``."""
        if self._persistence_backend is None or self._persistence_scope is None:
            return
        self._persistence_backend.write_trace_artifact(
            self._persistence_scope,
            name="stages.json",
            payload=self._stage_seq,
        )

    def _write_tree_json(self) -> None:
        if self._persistence_backend is None or self._persistence_scope is None:
            return
        nodes = [self._tree_nodes[path] for path in self._tree_order if path in self._tree_nodes]
        payload = {
            "root_path": ROOT_PATH,
            "nodes": nodes,
        }
        self._persistence_backend.write_trace_artifact(
            self._persistence_scope,
            name="tree.json",
            payload=payload,
        )

    def _write_artifacts_json(self) -> None:
        """Write an artifact inventory as ``artifacts.json``."""
        if self._persistence_backend is None or self._persistence_scope is None:
            return
        inventory = write_artifact_inventory(self._artifact_root)
        self._persistence_backend.write_trace_artifact(
            self._persistence_scope,
            name="artifacts.json",
            payload=inventory,
        )

    def _write_checkpoint_json(self, cursor: dict[str, Any], final: bool) -> None:
        """Write the final checkpoint notification as ``checkpoint.json``."""
        if self._persistence_backend is None or self._persistence_scope is None:
            return
        native_payload = cursor.get("native")
        cancellation = cursor.get("cancellation")
        payload: dict[str, Any] = {
            "final": final,
            "stage_sequence": list(self._stage_seq),
            "cursor_stage": cursor.get("stage", ""),
            "cursor_pc": (
                native_payload.get("pc")
                if isinstance(native_payload, dict)
                else None
            ),
            "run_path": cursor.get("run_path"),
            "step_path": cursor.get("step_path"),
            "call_site_path": cursor.get("call_site_path"),
            "tree_file": "tree.json",
            "tree_node_count": len(self._tree_nodes),
            "status": (
                "cancelled"
                if isinstance(cancellation, Mapping)
                else ("completed" if final else "suspended")
            ),
        }
        if isinstance(cancellation, Mapping):
            payload["cancellation"] = dict(cancellation)
        self._persistence_backend.write_trace_artifact(
            self._persistence_scope,
            name="checkpoint.json",
            payload=payload,
        )

    def _load_existing_tree_json(self) -> None:
        if self._persistence_backend is None or self._persistence_scope is None:
            return
        payload = self._persistence_backend.read_trace_artifact(
            self._persistence_scope,
            name="tree.json",
        )
        if payload is None:
            return
        if not isinstance(payload, Mapping):
            return
        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list):
            return
        for raw_node in raw_nodes:
            if not isinstance(raw_node, Mapping):
                continue
            path = raw_node.get("path")
            if not isinstance(path, str) or not path:
                continue
            node = dict(raw_node)
            children = raw_node.get("children")
            if not isinstance(children, list):
                node["children"] = []
            metadata = raw_node.get("metadata")
            if not isinstance(metadata, Mapping):
                node["metadata"] = {}
            self._tree_nodes[path] = node
            self._tree_order.append(path)

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
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        normalized_run_path = _normalize_trace_path(run_path)
        parent_path = _normalize_trace_path(parent_run_path) if parent_run_path else _parent_trace_path(normalized_run_path)
        node_metadata = {
            "program_name": program.name,
            "program_stable_id": program.stable_id,
            "status": "running",
        }
        if metadata:
            node_metadata.update(dict(metadata))
        self._active_runs.append(normalized_run_path)
        node = self._ensure_tree_node(
            path=normalized_run_path,
            kind=kind,
            name=program.name,
            run_path=normalized_run_path,
            parent_path=parent_path,
            parent_run_path=parent_run_path,
            call_site_path=call_site_path,
            metadata=node_metadata,
        )
        if self._journal is not None:
            self._journal.emit(
                "run.enter",
                payload={"trace": dict(node), "program_name": program.name, "program_stable_id": program.stable_id},
                phase=program.name,
            )

    def record_run_init(
        self,
        program: NativeProgram,
        *,
        run_path: str,
        pack_provenance: Mapping[str, Any] | None = None,
    ) -> None:
        callback = getattr(self._inner, "record_run_init", None)
        if callable(callback):
            callback(
                program,
                run_path=run_path,
                pack_provenance=pack_provenance,
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

    def record_cancellation(
        self,
        cancellation: Mapping[str, Any],
        *,
        state: dict[str, Any] | None = None,
    ) -> None:
        callback = getattr(self._inner, "record_cancellation", None)
        if callable(callback):
            callback(cancellation, state=state)

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

    def emit_pipeline_cancelled(
        self,
        cancellation: Mapping[str, Any],
    ) -> None:
        trace = self._trace_context(
            path=cancellation.get("step_path") or cancellation.get("run_path") or ROOT_PATH,
            run_path=cancellation.get("run_path"),
            step_path=cancellation.get("step_path"),
            call_site_path=cancellation.get("call_site_path"),
        )
        metadata = {
            "status": "cancelled",
            "reason": cancellation.get("reason"),
            "boundary": cancellation.get("boundary"),
        }
        self._ensure_tree_node(
            path=trace["path"],
            kind=trace["kind"],
            name=str(cancellation.get("instruction_name") or trace["path"].split(PATH_DELIMITER)[-1]),
            run_path=trace["run_path"],
            step_path=trace["step_path"],
            parent_path=trace["parent_path"],
            parent_run_path=trace["parent_run_path"],
            call_site_path=trace["call_site_path"],
            metadata=metadata,
        )
        self._ensure_tree_node(
            path=trace["run_path"],
            kind=self._tree_nodes.get(trace["run_path"], {}).get("kind", "pipeline"),
            name=self._tree_nodes.get(trace["run_path"], {}).get("name", trace["run_path"].split(PATH_DELIMITER)[-1]),
            run_path=trace["run_path"],
            parent_path=_parent_trace_path(trace["run_path"]),
            parent_run_path=trace["parent_run_path"],
            call_site_path=trace["call_site_path"],
            metadata=metadata,
        )
        if self._journal is not None:
            self._journal.emit(
                "pipeline_cancelled",
                payload={
                    "status": "cancelled",
                    "reason": cancellation.get("reason"),
                    "boundary": cancellation.get("boundary"),
                    "trace": trace,
                },
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

    def emit_token_progress(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
        estimated_cost_usd: float | None = None,
        cost_status: str | None = None,
        cost_source: str | None = None,
        model: str | None = None,
        run_path: Any = None,
        step_path: Any = None,
        call_site_path: Any = None,
    ) -> None:
        """Emit a ``token_progress`` event with per-turn token/cost deltas.

        Called opportunistically from provider call sites.  When no journal is
        configured the call is a no-op so that missing metadata degrades
        cleanly without breaking the agent loop.
        """
        if self._journal is None:
            return
        trace = self._trace_context(
            path=step_path or run_path or ROOT_PATH,
            run_path=run_path,
            step_path=step_path,
            call_site_path=call_site_path,
        )
        payload: dict[str, Any] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cache_write_tokens": cache_write_tokens,
            "reasoning_tokens": reasoning_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "cost_status": cost_status,
            "cost_source": cost_source,
            "model": model,
            "trace": trace,
        }
        self._journal.emit("token_progress", payload=payload)
