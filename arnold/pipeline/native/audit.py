"""File-backed audit hook support for the native pipeline runtime.

Implemented as a :class:`AuditHooks` that wraps an inner
:class:`NativeRuntimeHooks` instance and delegates every callback to it.
When *audit_dir* is set, audit records are appended to an ``audit.ndjson``
file (one JSON record per line) at the documented insertion points. Callers
may also provide a persistence backend/scope pair to route audit writes
through a durable backend without changing callback semantics.

Each audit record captures:

* ``run_id`` — stable identifier for the run
* ``attempt_id`` — stable unique identifier for this specific attempt
* ``step_path`` — the stable tree-shaped path of the step
* ``run_path`` — the run path (parent of step_path, for trace correlation)
* ``parent_run_path`` — the parent run path (for lineage / tree-trace correlation)
* ``call_site_path`` — call-site path segments (for tree-trace correlation)
* ``attempt`` — attempt number (defaults to 1, incremented by retry wiring)
* ``input_keys`` — sorted list of input context dict keys
* ``output_keys`` — sorted list of output/result dict keys (success only)
* ``started_at`` / ``ended_at`` — ISO-8601 timestamps
* ``status`` — ``"success"`` or ``"failure"``
* ``error_type`` / ``error_message`` — exception details (failure only)

The audit file is written separately from ``resume_cursor.json`` and
checkpoints, providing an append-only audit trail that survives
suspension/resume cycles.

Example usage through :func:`run_native_pipeline`::

    result = run_native_pipeline(
        program,
        artifact_root="./run_01",
        audit_dir="./run_01/audit",
    )

Boundary discipline
-------------------
No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import NativeInstruction, NativeProgram
from arnold.pipeline.native.persistence import (
    FileNativePersistenceBackend,
    NativePersistenceBackend,
    NativePersistenceScope,
    bind_legacy_artifact_root,
)
from arnold.security.audit import claim_broker_audit_entry
from arnold.security.redaction import redact_value
from arnold.security.types import RedactionStatus, RetentionPolicy


__all__ = [
    "AuditHooks",
    "AuditRecord",
    "resolved_versions_by_stable_id_for_run",
]

def _ensure_dir(path: Path) -> None:
    """Create directory *path* if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def _utcnow_iso() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _dict_keys_summary(d: Any) -> list[str] | None:
    """Return sorted top-level keys of a dict-like, or None if not applicable."""
    if isinstance(d, Mapping):
        return sorted(str(k) for k in d.keys())
    return None


def _backend_for_audit_dir(
    audit_dir: str | Path,
) -> tuple[NativePersistenceBackend, NativePersistenceScope]:
    audit_root = Path(audit_dir)
    binding = bind_legacy_artifact_root(audit_root)
    backend = FileNativePersistenceBackend(
        lambda scope: audit_root
        if scope == binding.scope
        else (_ for _ in ()).throw(KeyError(scope))
    )
    return backend, binding.scope


def _load_audit_records(
    audit_dir: str | Path | None = None,
    *,
    persistence_backend: NativePersistenceBackend | None = None,
    persistence_scope: NativePersistenceScope | None = None,
) -> list[dict[str, Any]]:
    if persistence_backend is not None or persistence_scope is not None:
        if persistence_backend is None or persistence_scope is None:
            raise ValueError(
                "persistence_backend and persistence_scope must be provided together"
            )
        return [
            dict(row.payload)
            for row in persistence_backend.read_audit_records(persistence_scope)
            if isinstance(row.payload, Mapping)
        ]
    if audit_dir is None:
        return []
    audit_path = Path(audit_dir) / "audit.ndjson"
    if not audit_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def resolved_versions_by_stable_id_for_run(
    audit_dir: str | Path | None = None,
    *,
    run_id: str | None = None,
    persistence_backend: NativePersistenceBackend | None = None,
    persistence_scope: NativePersistenceScope | None = None,
) -> dict[str, str]:
    """Return ``stable_id -> resolved version`` from a run's ``run.init`` record."""
    run_inits = [
        record
        for record in _load_audit_records(
            audit_dir,
            persistence_backend=persistence_backend,
            persistence_scope=persistence_scope,
        )
        if record.get("event") == "run.init"
    ]
    if run_id is not None:
        run_inits = [
            record for record in run_inits if str(record.get("run_id", "")) == run_id
        ]
    elif len(run_inits) > 1:
        raise LookupError("multiple run.init records found; pass run_id explicitly")

    if not run_inits:
        return {}

    pack_provenance = run_inits[-1].get("pack_provenance")
    if not isinstance(pack_provenance, Mapping):
        return {}
    dependencies = pack_provenance.get("dependencies")
    if not isinstance(dependencies, list):
        return {}

    resolved: dict[str, str] = {}
    for dependency in dependencies:
        if not isinstance(dependency, Mapping):
            continue
        stable_id = dependency.get("stable_id")
        version = dependency.get("version")
        if stable_id and version:
            resolved[str(stable_id)] = str(version)
    return resolved


# ── AuditRecord ───────────────────────────────────────────────────────


class AuditRecord:
    """A single audit record representing one step attempt.

    This is a simple mutable bag used internally by :class:`AuditHooks`
    to accumulate per-step data before flushing to ``audit.ndjson``.
    It is not intended for direct construction by callers.
    """

    __slots__ = (
        "attempt_id",
        "run_id",
        "step_path",
        "run_path",
        "parent_run_path",
        "call_site_path",
        "attempt",
        "input_keys",
        "output_keys",
        "started_at",
        "ended_at",
        "status",
        "error_type",
        "error_message",
        "operation",
        "target",
        "idempotency_key",
        "effect_class",
        "effect_lifecycle_state",
        "duplicate_action",
        "git_command_ref",
        "git_effect_ref",
        "prompt_ref",
        "completion_ref",
        "redaction_status",
        "retention_policy",
    )

    def __init__(
        self,
        *,
        attempt_id: str,
        run_id: str,
        step_path: str,
        run_path: str = "",
        parent_run_path: str | None = None,
        call_site_path: list[str] | None = None,
        attempt: int = 1,
        input_keys: list[str] | None = None,
        operation: str | None = None,
        target: str | None = None,
        idempotency_key: str | None = None,
        effect_class: str | None = None,
        effect_lifecycle_state: str | None = None,
        duplicate_action: str | None = None,
        git_command_ref: str | None = None,
        git_effect_ref: str | None = None,
        prompt_ref: str | None = None,
        completion_ref: str | None = None,
        redaction_status: str | None = None,
        retention_policy: str | None = None,
    ) -> None:
        self.attempt_id = attempt_id
        self.run_id = run_id
        self.step_path = step_path
        self.run_path = run_path
        self.parent_run_path = parent_run_path
        self.call_site_path = call_site_path
        self.attempt = attempt
        self.input_keys = input_keys
        self.output_keys: list[str] | None = None
        self.started_at: str = _utcnow_iso()
        self.ended_at: str | None = None
        self.status: str = "started"
        self.error_type: str | None = None
        self.error_message: str | None = None
        self.operation = operation
        self.target = target
        self.idempotency_key = idempotency_key
        self.effect_class = effect_class
        self.effect_lifecycle_state = effect_lifecycle_state
        self.duplicate_action = duplicate_action
        self.git_command_ref = git_command_ref
        self.git_effect_ref = git_effect_ref
        self.prompt_ref = prompt_ref
        self.completion_ref = completion_ref
        self.redaction_status = redaction_status or RedactionStatus.SANITIZED.value
        self.retention_policy = retention_policy or RetentionPolicy.AUDIT.value

    def mark_success(self, result: Any) -> None:
        """Finalize the record with a success outcome."""
        self.ended_at = _utcnow_iso()
        self.status = "success"
        self.output_keys = _dict_keys_summary(result)

    def mark_failure(self, exc: BaseException) -> None:
        """Finalize the record with a failure outcome."""
        self.ended_at = _utcnow_iso()
        self.status = "failure"
        self.error_type = type(exc).__name__
        self.error_message = str(exc)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for NDJSON writing."""
        return {
            "attempt_id": self.attempt_id,
            "run_id": self.run_id,
            "step_path": self.step_path,
            "run_path": self.run_path,
            "parent_run_path": self.parent_run_path,
            "call_site_path": self.call_site_path,
            "attempt": self.attempt,
            "input_keys": self.input_keys,
            "output_keys": self.output_keys,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "operation": self.operation,
            "target": self.target,
            "idempotency_key": self.idempotency_key,
            "effect_class": self.effect_class,
            "effect_lifecycle_state": self.effect_lifecycle_state,
            "duplicate_action": self.duplicate_action,
            "git_command_ref": self.git_command_ref,
            "git_effect_ref": self.git_effect_ref,
            "prompt_ref": self.prompt_ref,
            "completion_ref": self.completion_ref,
            "redaction_status": self.redaction_status,
            "retention_policy": self.retention_policy,
        }


# ── AuditHooks ────────────────────────────────────────────────────────


class AuditHooks:
    """Native runtime hooks that emit file-backed audit records when enabled.

    Wraps an inner :class:`NativeRuntimeHooks` (default
    :class:`NullNativeRuntimeHooks`) and delegates every callback to it.
    When *audit_dir* is set, audit records are written to ``audit.ndjson``
    at the documented insertion points:

    * ``on_step_start`` — creates an in-progress :class:`AuditRecord`.
    * ``on_step_end`` — finalizes the record as ``"success"`` and flushes.
    * ``on_step_error`` — finalizes the record as ``"failure"`` and flushes.

    When neither *audit_dir* nor a persistence backend is provided, every
    callback is a pure pass-through to the inner hooks.

    The audit file is append-only NDJSON (one JSON record per line),
    written separately from ``resume_cursor.json`` and checkpoints.
    """

    halt_reason: str | None

    def __init__(
        self,
        inner: NativeRuntimeHooks | None = None,
        *,
        audit_dir: str | Path | None = None,
        persistence_backend: NativePersistenceBackend | None = None,
        persistence_scope: NativePersistenceScope | None = None,
    ) -> None:
        self._inner: NativeRuntimeHooks = (
            inner if inner is not None else NullNativeRuntimeHooks()
        )
        self._audit_dir: Path | None = (
            Path(audit_dir) if audit_dir is not None else None
        )
        if persistence_backend is not None or persistence_scope is not None:
            if persistence_backend is None or persistence_scope is None:
                raise ValueError(
                    "persistence_backend and persistence_scope must be provided together"
                )
            self._audit_backend = persistence_backend
            self._audit_scope = persistence_scope
        elif self._audit_dir is not None:
            self._audit_backend, self._audit_scope = _backend_for_audit_dir(
                self._audit_dir
            )
        else:
            self._audit_backend = None
            self._audit_scope = None
        self.halt_reason: str | None = None
        self._run_id: str = uuid4().hex
        self._attempts: dict[str, int] = {}
        self._active_record: AuditRecord | None = None
        self._run_init_written = False

        if self._audit_dir is not None:
            _ensure_dir(self._audit_dir)

    # ── private helpers ─────────────────────────────────────────────

    def _audit_path(self) -> Path | None:
        """Return the path to ``audit.ndjson``, or ``None`` if disabled."""
        if self._audit_dir is None:
            return None
        return self._audit_dir / "audit.ndjson"

    def _append_record(self, record: dict[str, Any]) -> None:
        """Append a JSON line to ``audit.ndjson``."""
        if self._audit_backend is None or self._audit_scope is None:
            return
        payload = redact_value(record)
        if not isinstance(payload, Mapping):
            payload = {"payload": payload}
        self._audit_backend.append_audit_record(
            self._audit_scope,
            payload=dict(payload),
        )

    def _write_run_init(
        self,
        *,
        program_name: str | None = None,
        program_stable_id: str | None = None,
        run_path: str | None = None,
        pack_provenance: Mapping[str, Any] | None = None,
    ) -> None:
        if self._audit_backend is None or self._run_init_written:
            return
        record: dict[str, Any] = {
            "event": "run.init",
            "run_id": self._run_id,
            "started_at": _utcnow_iso(),
        }
        if program_name:
            record["program_name"] = program_name
        if program_stable_id:
            record["program_stable_id"] = program_stable_id
        if run_path:
            record["run_path"] = run_path
        if pack_provenance is not None:
            record["pack_provenance"] = dict(pack_provenance)
        self._append_record(record)
        self._run_init_written = True

    def _flush_active(self) -> None:
        """Flush the active audit record to disk if one exists."""
        if self._active_record is not None:
            self._join_broker_audit(self._active_record)
            self._append_record(self._active_record.to_dict())
            self._active_record = None

    def _join_broker_audit(self, record: AuditRecord) -> None:
        """Merge broker audit metadata keyed by ``run_id`` and ``step_path``."""

        broker = claim_broker_audit_entry(record.run_id, record.step_path)
        if not broker:
            return
        effect_refs = broker.get("effect_refs")
        if not record.git_effect_ref and isinstance(effect_refs, list) and effect_refs:
            record.git_effect_ref = str(effect_refs[0])
        record.git_command_ref = broker.get("git_command_ref")
        record.git_effect_ref = broker.get("git_effect_ref") or record.git_effect_ref
        record.prompt_ref = broker.get("prompt_ref")
        record.completion_ref = broker.get("completion_ref")
        record.redaction_status = str(
            broker.get("redaction_status") or record.redaction_status
        )
        record.retention_policy = str(
            broker.get("retention_policy") or record.retention_policy
        )

    def _step_key(self, instr: NativeInstruction) -> str:
        """Return a stable key for a step (used for attempt counting)."""
        # Use name+pc as the step identity; this is stable across
        # suspension/resume because pc is deterministic.
        return f"{instr.name or instr.op}__pc{instr.pc}"

    def _resolve_step_path(self, ctx: dict[str, Any]) -> str:
        """Extract the stable step_path from context."""
        step_path = ctx.get("step_path")
        if isinstance(step_path, str) and step_path:
            return step_path
        run_path = ctx.get("run_path")
        if isinstance(run_path, str) and run_path:
            return run_path
        return "root"

    def _resolve_run_path(self, ctx: dict[str, Any]) -> str:
        """Extract the run_path (parent of step_path) from context."""
        run_path = ctx.get("run_path")
        if isinstance(run_path, str) and run_path:
            return run_path
        return "root"

    def _resolve_parent_run_path(self, ctx: dict[str, Any]) -> str | None:
        """Extract the parent_run_path from context for lineage."""
        parent = ctx.get("parent_run_path")
        if isinstance(parent, str) and parent:
            return parent
        return None

    def _resolve_call_site_path(self, ctx: dict[str, Any]) -> list[str]:
        """Extract the call_site_path from context for trace correlation."""
        csp = ctx.get("call_site_path")
        if isinstance(csp, (list, tuple)):
            return [str(s) for s in csp]
        return []

    def _parent_path(self, step_path: str) -> str | None:
        """Derive parent path from step_path by removing the last segment."""
        parts = step_path.rsplit("/", 1)
        if len(parts) == 2 and parts[0]:
            return parts[0]
        return None

    def _next_attempt(self, step_key: str) -> int:
        """Return the next attempt number for *step_key*."""
        current = self._attempts.get(step_key, 0)
        attempt = current + 1
        self._attempts[step_key] = attempt
        return attempt

    def record_run_init(
        self,
        program: NativeProgram,
        *,
        run_path: str,
        pack_provenance: Mapping[str, Any] | None = None,
    ) -> None:
        self._write_run_init(
            program_name=program.name,
            program_stable_id=program.stable_id,
            run_path=run_path,
            pack_provenance=pack_provenance,
        )

    # ── NativeRuntimeHooks callbacks ─────────────────────────────────

    def on_step_start(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        ctx = self._inner.on_step_start(instr, ctx)
        if self._audit_backend is not None:
            self._write_run_init(run_path=self._resolve_run_path(ctx))
            step_key = self._step_key(instr)
            step_path = self._resolve_step_path(ctx)
            effect_meta = ctx.get("effect")
            effect_meta = effect_meta if isinstance(effect_meta, Mapping) else {}
            self._active_record = AuditRecord(
                attempt_id=uuid4().hex,
                run_id=self._run_id,
                step_path=step_path,
                run_path=self._resolve_run_path(ctx),
                parent_run_path=self._resolve_parent_run_path(ctx),
                call_site_path=self._resolve_call_site_path(ctx),
                attempt=self._next_attempt(step_key),
                input_keys=_dict_keys_summary(ctx),
                operation=instr.operation,
                target=instr.target,
                idempotency_key=instr.idempotency_key,
                effect_class=instr.effect_class,
                effect_lifecycle_state=effect_meta.get("lifecycle_state"),
                duplicate_action=effect_meta.get("duplicate_action"),
            )
        return ctx

    def on_step_end(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
    ) -> Any:
        result = self._inner.on_step_end(instr, ctx, result)
        if self._audit_backend is not None and self._active_record is not None:
            self._active_record.mark_success(result)
            self._active_record.effect_lifecycle_state = "fulfilled"
            self._flush_active()
        return result

    def on_step_error(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        exc: BaseException,
    ) -> None:
        self._inner.on_step_error(instr, ctx, exc)
        if self._audit_backend is not None and self._active_record is not None:
            self._active_record.mark_failure(exc)
            self._active_record.effect_lifecycle_state = "failed"
            self._flush_active()

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
        return self._inner.on_stage_complete(instr, ctx, result, state, owned_keys)

    def on_checkpoint(
        self,
        cursor: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        return self._inner.on_checkpoint(cursor, state)
