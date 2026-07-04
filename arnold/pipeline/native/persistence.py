"""Shared native persistence protocol and compatibility shims.

This module defines the storage-facing contract for native runtime
durability work. The boundary is intentionally expressed in stable
project/run/artifact identifiers rather than raw filesystem paths so
future backends can swap file storage for database storage without
changing runtime control flow semantics.

Only neutral persistence metadata lives here. Routing, suspension
policy, and native runtime control decisions remain owned by the
existing runtime and resume helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import hashlib
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Protocol, runtime_checkable

from arnold.runtime.event_journal import NdjsonEventJournal, read_event_journal_paged
from arnold.runtime.state_persistence import atomic_write_json

ResumeSurfaceSource = Literal[
    "state_resume_cursor",
    "typed_contract",
    "composite_resume_cursor",
    "awaiting_user",
    "resume_cursor",
    "none",
]

TraceArtifactName = Literal[
    "state.json",
    "events.ndjson",
    "stages.json",
    "artifacts.json",
    "checkpoint.json",
    "tree.json",
]


@dataclass(frozen=True)
class NativePersistenceScope:
    """Stable backend address for one persisted native run substrate."""

    project_id: str
    run_id: str
    artifact_id: str


@dataclass(frozen=True)
class LegacyArtifactBinding:
    """Compatibility bridge from path-based callers to stable identifiers."""

    scope: NativePersistenceScope
    artifact_root: Path


@dataclass(frozen=True)
class TypedResumeMetadata:
    contract: Any
    phase: str | None
    pipeline: str | None
    choices: list[str] | None
    resume_input_schema: Mapping[str, Any]
    cursor_data: Any
    suspension_kind: str | None
    awaitable: str | None


@dataclass(frozen=True)
class ResumeSurfaceObservation:
    source: ResumeSurfaceSource
    present: bool
    valid: bool
    kind: str
    path: str | None = None
    payload: Any = None
    diagnostic: str | None = None


@dataclass(frozen=True)
class ResolvedResumeSurface:
    source: ResumeSurfaceSource
    kind: str
    blocked: bool
    payload: Any = None
    path: str | None = None
    diagnostic: str | None = None
    observations: tuple[ResumeSurfaceObservation, ...] = ()


@dataclass(frozen=True)
class OrderedPersistenceRow:
    """Ordered append-only record returned by audit/event readers."""

    sequence: int
    payload: Mapping[str, Any]
    kind: str | None = None


ArtifactRootResolver = Callable[[NativePersistenceScope], str | Path]


def _scope_digest(path: Path) -> str:
    resolved = str(path.expanduser().resolve(strict=False))
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()


def bind_legacy_artifact_root(
    artifact_root: str | Path,
    *,
    project_id: str = "native-file-compat",
) -> LegacyArtifactBinding:
    """Map a legacy artifact root onto stable persistence identifiers.

    The returned identifiers are deterministic for the same artifact
    root but never expose the raw path to backend callers.
    """

    root = Path(artifact_root)
    digest = _scope_digest(root)
    scope = NativePersistenceScope(
        project_id=project_id,
        run_id=f"run-{digest[:20]}",
        artifact_id=f"artifact-{digest[20:40]}",
    )
    return LegacyArtifactBinding(scope=scope, artifact_root=root)


def legacy_scope_for_artifact_root(
    artifact_root: str | Path,
    *,
    project_id: str = "native-file-compat",
) -> NativePersistenceScope:
    """Return the stable scope for a legacy path-based artifact root."""

    return bind_legacy_artifact_root(
        artifact_root,
        project_id=project_id,
    ).scope


@runtime_checkable
class NativePersistenceBackend(Protocol):
    """Storage contract for native checkpoint/resume durability groups."""

    def write_resume_cursor(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> str | None:
        ...

    def read_resume_cursor(
        self,
        scope: NativePersistenceScope,
    ) -> dict[str, Any] | None:
        ...

    def delete_resume_cursor(self, scope: NativePersistenceScope) -> None:
        ...

    def read_state_resume_cursor(
        self,
        scope: NativePersistenceScope,
    ) -> dict[str, Any] | None:
        ...

    def write_composite_resume_cursor(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> str | None:
        ...

    def read_composite_resume_cursor(
        self,
        scope: NativePersistenceScope,
    ) -> dict[str, Any] | None:
        ...

    def delete_composite_resume_cursor(self, scope: NativePersistenceScope) -> None:
        ...

    def write_human_gate(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> str | None:
        ...

    def read_human_gate(self, scope: NativePersistenceScope) -> dict[str, Any] | None:
        ...

    def delete_human_gate(self, scope: NativePersistenceScope) -> None:
        ...

    def resolve_resume_surface(
        self,
        scope: NativePersistenceScope,
    ) -> ResolvedResumeSurface:
        ...

    def append_audit_record(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> OrderedPersistenceRow:
        ...

    def read_audit_records(
        self,
        scope: NativePersistenceScope,
    ) -> list[OrderedPersistenceRow]:
        ...

    def emit_event(
        self,
        scope: NativePersistenceScope,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        phase: str | None = None,
        idempotency_key: str | None = None,
        event_scope: str | None = None,
    ) -> OrderedPersistenceRow:
        ...

    def read_events(
        self,
        scope: NativePersistenceScope,
        *,
        since_sequence: int | None = None,
        to_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[OrderedPersistenceRow]:
        ...

    def write_trace_artifact(
        self,
        scope: NativePersistenceScope,
        *,
        name: TraceArtifactName,
        payload: Any,
    ) -> str | None:
        ...

    def read_trace_artifact(
        self,
        scope: NativePersistenceScope,
        *,
        name: TraceArtifactName,
    ) -> Any:
        ...


class FileNativePersistenceBackend:
    """File-backed persistence backend preserving current artifact layout."""

    def __init__(self, artifact_root_resolver: ArtifactRootResolver) -> None:
        self._artifact_root_resolver = artifact_root_resolver

    def write_resume_cursor(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> str | None:
        path = self._artifact_root(scope) / "resume_cursor.json"
        atomic_write_json(path, dict(payload))
        return str(path)

    def read_resume_cursor(
        self,
        scope: NativePersistenceScope,
    ) -> dict[str, Any] | None:
        return self._read_json_object(self._artifact_root(scope) / "resume_cursor.json")

    def delete_resume_cursor(self, scope: NativePersistenceScope) -> None:
        self._delete_file(self._artifact_root(scope) / "resume_cursor.json")

    def read_state_resume_cursor(
        self,
        scope: NativePersistenceScope,
    ) -> dict[str, Any] | None:
        state = self._read_json_object(self._artifact_root(scope) / "state.json")
        if state is None:
            return None
        cursor = state.get("resume_cursor")
        return dict(cursor) if isinstance(cursor, dict) else None

    def write_composite_resume_cursor(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> str | None:
        path = self._artifact_root(scope) / "composite_resume_cursor.json"
        atomic_write_json(path, dict(payload))
        return str(path)

    def read_composite_resume_cursor(
        self,
        scope: NativePersistenceScope,
    ) -> dict[str, Any] | None:
        return self._read_json_object(
            self._artifact_root(scope) / "composite_resume_cursor.json"
        )

    def delete_composite_resume_cursor(self, scope: NativePersistenceScope) -> None:
        self._delete_file(self._artifact_root(scope) / "composite_resume_cursor.json")

    def write_human_gate(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> str | None:
        path = self._artifact_root(scope) / "awaiting_user.json"
        atomic_write_json(path, dict(payload))
        return str(path)

    def read_human_gate(self, scope: NativePersistenceScope) -> dict[str, Any] | None:
        return self._read_json_object(self._artifact_root(scope) / "awaiting_user.json")

    def delete_human_gate(self, scope: NativePersistenceScope) -> None:
        self._delete_file(self._artifact_root(scope) / "awaiting_user.json")

    def resolve_resume_surface(
        self,
        scope: NativePersistenceScope,
    ) -> ResolvedResumeSurface:
        from arnold.pipeline.resume import resolve_resume_surface

        return resolve_resume_surface(self._artifact_root(scope))

    def append_audit_record(
        self,
        scope: NativePersistenceScope,
        *,
        payload: Mapping[str, Any],
    ) -> OrderedPersistenceRow:
        path = self._artifact_root(scope) / "audit.ndjson"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload_dict = dict(payload)
        line = json.dumps(
            payload_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        with path.open("a+", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            handle.seek(0)
            sequence = sum(1 for raw_line in handle if raw_line.strip())
        kind = payload_dict.get("event") if isinstance(payload_dict.get("event"), str) else "audit"
        return OrderedPersistenceRow(
            sequence=sequence,
            payload=payload_dict,
            kind=kind,
        )

    def read_audit_records(
        self,
        scope: NativePersistenceScope,
    ) -> list[OrderedPersistenceRow]:
        path = self._artifact_root(scope) / "audit.ndjson"
        return self._read_ndjson_rows(path, default_kind="audit")

    def emit_event(
        self,
        scope: NativePersistenceScope,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        phase: str | None = None,
        idempotency_key: str | None = None,
        event_scope: str | None = None,
    ) -> OrderedPersistenceRow:
        event = NdjsonEventJournal(self._artifact_root(scope)).emit(
            kind,
            payload=dict(payload or {}),
            phase=phase,
            idempotency_key=idempotency_key,
            scope=event_scope,
        )
        return OrderedPersistenceRow(
            sequence=int(event["seq"]),
            payload=dict(event),
            kind=kind,
        )

    def read_events(
        self,
        scope: NativePersistenceScope,
        *,
        since_sequence: int | None = None,
        to_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[OrderedPersistenceRow]:
        events = read_event_journal_paged(
            self._artifact_root(scope),
            since_seq=since_sequence,
            to_seq=to_sequence,
            limit=limit,
        )
        return [
            OrderedPersistenceRow(
                sequence=int(event.get("seq", 0)),
                payload=dict(event),
                kind=event.get("kind") if isinstance(event.get("kind"), str) else None,
            )
            for event in events
        ]

    def write_trace_artifact(
        self,
        scope: NativePersistenceScope,
        *,
        name: TraceArtifactName,
        payload: Any,
    ) -> str | None:
        path = self._artifact_root(scope) / name
        if name == "events.ndjson":
            self._write_ndjson_artifact(path, payload)
            return str(path)
        atomic_write_json(path, payload)
        return str(path)

    def read_trace_artifact(
        self,
        scope: NativePersistenceScope,
        *,
        name: TraceArtifactName,
    ) -> Any:
        path = self._artifact_root(scope) / name
        if not path.exists():
            return None
        if name == "events.ndjson":
            return [row.payload for row in self._read_ndjson_rows(path, default_kind="event")]
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _artifact_root(self, scope: NativePersistenceScope) -> Path:
        return Path(self._artifact_root_resolver(scope))

    @staticmethod
    def _delete_file(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return

    @staticmethod
    def _read_json_object(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return dict(raw) if isinstance(raw, dict) else None

    @staticmethod
    def _read_ndjson_rows(
        path: Path,
        *,
        default_kind: str,
    ) -> list[OrderedPersistenceRow]:
        if not path.exists():
            return []
        rows: list[OrderedPersistenceRow] = []
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            raw_kind = payload.get("kind")
            if not isinstance(raw_kind, str):
                raw_kind = payload.get("event")
            kind = raw_kind if isinstance(raw_kind, str) else default_kind
            rows.append(
                OrderedPersistenceRow(
                    sequence=index,
                    payload=payload,
                    kind=kind,
                )
            )
        return rows

    @staticmethod
    def _write_ndjson_artifact(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, str):
            text = payload
        elif isinstance(payload, list):
            text = "\n".join(
                json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    default=str,
                )
                for item in payload
            )
        else:
            raise TypeError("events.ndjson payload must be a string or list of JSON records")
        path.write_text(f"{text}\n" if text else "", encoding="utf-8")


__all__ = [
    "ArtifactRootResolver",
    "FileNativePersistenceBackend",
    "LegacyArtifactBinding",
    "NativePersistenceBackend",
    "NativePersistenceScope",
    "OrderedPersistenceRow",
    "ResolvedResumeSurface",
    "ResumeSurfaceObservation",
    "ResumeSurfaceSource",
    "TraceArtifactName",
    "TypedResumeMetadata",
    "bind_legacy_artifact_root",
    "legacy_scope_for_artifact_root",
]
