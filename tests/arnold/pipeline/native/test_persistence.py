from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.pipeline import resume as resume_module
from arnold.pipeline.native.persistence import (
    FileNativePersistenceBackend,
    NativePersistenceBackend,
    OrderedPersistenceRow,
    ResolvedResumeSurface,
    ResumeSurfaceObservation,
    TypedResumeMetadata,
    bind_legacy_artifact_root,
    legacy_scope_for_artifact_root,
)


class _BackendStub:
    def write_resume_cursor(self, scope, *, payload):
        return None

    def read_resume_cursor(self, scope):
        return None

    def delete_resume_cursor(self, scope) -> None:
        return None

    def read_state_resume_cursor(self, scope):
        return None

    def write_composite_resume_cursor(self, scope, *, payload):
        return None

    def read_composite_resume_cursor(self, scope):
        return None

    def delete_composite_resume_cursor(self, scope) -> None:
        return None

    def write_human_gate(self, scope, *, payload):
        return None

    def read_human_gate(self, scope):
        return None

    def delete_human_gate(self, scope) -> None:
        return None

    def resolve_resume_surface(self, scope):
        return ResolvedResumeSurface(source="none", kind="none", blocked=False)

    def append_audit_record(self, scope, *, payload):
        return OrderedPersistenceRow(sequence=1, payload=dict(payload), kind="audit")

    def read_audit_records(self, scope):
        return []

    def emit_event(
        self,
        scope,
        *,
        kind,
        payload=None,
        phase=None,
        idempotency_key=None,
        event_scope=None,
    ):
        return OrderedPersistenceRow(
            sequence=1,
            payload=dict(payload or {}),
            kind=kind,
        )

    def read_events(
        self,
        scope,
        *,
        since_sequence=None,
        to_sequence=None,
        limit=None,
    ):
        return []

    def write_trace_artifact(self, scope, *, name, payload):
        return None

    def read_trace_artifact(self, scope, *, name):
        return None


def test_legacy_artifact_binding_uses_stable_identifiers(tmp_path: Path) -> None:
    root = tmp_path / "nested" / "artifact-root"
    binding = bind_legacy_artifact_root(root)
    rebound = bind_legacy_artifact_root(root)

    assert binding.scope == rebound.scope
    assert binding.artifact_root == root
    assert binding.scope.project_id == "native-file-compat"
    assert binding.scope.run_id.startswith("run-")
    assert binding.scope.artifact_id.startswith("artifact-")

    root_text = str(root.resolve(strict=False))
    assert root_text not in binding.scope.run_id
    assert root_text not in binding.scope.artifact_id


def test_legacy_scope_helper_matches_binding(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"

    assert legacy_scope_for_artifact_root(root) == bind_legacy_artifact_root(root).scope


def test_resume_module_reuses_shared_persistence_types() -> None:
    assert resume_module.TypedResumeMetadata is TypedResumeMetadata
    assert resume_module.ResumeSurfaceObservation is ResumeSurfaceObservation
    assert resume_module.ResolvedResumeSurface is ResolvedResumeSurface


def test_protocol_is_runtime_checkable() -> None:
    backend: Any = _BackendStub()

    assert isinstance(backend, NativePersistenceBackend)


def _backend_for(root: Path) -> tuple[FileNativePersistenceBackend, Any]:
    binding = bind_legacy_artifact_root(root)
    backend = FileNativePersistenceBackend(
        lambda scope: root if scope == binding.scope else (_ for _ in ()).throw(KeyError(scope))
    )
    return backend, binding.scope


def test_file_backend_preserves_resume_and_human_gate_paths(tmp_path: Path) -> None:
    backend, scope = _backend_for(tmp_path)

    resume_path = backend.write_resume_cursor(
        scope,
        payload={"stage": "review", "native": {"pc": 1, "version": 1}},
    )
    composite_path = backend.write_composite_resume_cursor(
        scope,
        payload={"kind": "composite_suspension", "children": {"child": {"stage": "a"}}},
    )
    human_gate_path = backend.write_human_gate(
        scope,
        payload={"status": "awaiting_user", "phase": "approve"},
    )

    assert resume_path == str(tmp_path / "resume_cursor.json")
    assert composite_path == str(tmp_path / "composite_resume_cursor.json")
    assert human_gate_path == str(tmp_path / "awaiting_user.json")
    assert backend.read_resume_cursor(scope) == {
        "stage": "review",
        "native": {"pc": 1, "version": 1},
    }
    assert backend.read_composite_resume_cursor(scope) == {
        "kind": "composite_suspension",
        "children": {"child": {"stage": "a"}},
    }
    assert backend.read_human_gate(scope) == {
        "status": "awaiting_user",
        "phase": "approve",
    }


def test_file_backend_reads_state_resume_cursor_and_resolves_precedence(tmp_path: Path) -> None:
    backend, scope = _backend_for(tmp_path)
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "resume_cursor": {"stage": "state-first"},
                "contract_result": {"status": "ignored"},
            }
        ),
        encoding="utf-8",
    )
    backend.write_composite_resume_cursor(
        scope,
        payload={"kind": "composite_suspension", "children": {}},
    )
    backend.write_human_gate(scope, payload={"status": "awaiting_user"})
    backend.write_resume_cursor(scope, payload={"stage": "fallback"})

    assert backend.read_state_resume_cursor(scope) == {"stage": "state-first"}
    resolved = backend.resolve_resume_surface(scope)
    assert resolved.source == "state_resume_cursor"
    assert resolved.kind == "state_resume_cursor"
    assert resolved.blocked is False
    assert resolved.payload == {"stage": "state-first"}


def test_file_backend_appends_audit_records_as_ndjson(tmp_path: Path) -> None:
    backend, scope = _backend_for(tmp_path)

    first = backend.append_audit_record(scope, payload={"event": "run.init", "run_id": "r1"})
    second = backend.append_audit_record(scope, payload={"event": "phase.end", "phase": "review"})

    assert first == OrderedPersistenceRow(
        sequence=1,
        payload={"event": "run.init", "run_id": "r1"},
        kind="run.init",
    )
    assert second == OrderedPersistenceRow(
        sequence=2,
        payload={"event": "phase.end", "phase": "review"},
        kind="phase.end",
    )
    lines = (tmp_path / "audit.ndjson").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"event": "run.init", "run_id": "r1"},
        {"event": "phase.end", "phase": "review"},
    ]
    assert backend.read_audit_records(scope) == [first, second]


def test_file_backend_uses_monotonic_event_journal_sequences(tmp_path: Path) -> None:
    backend, scope = _backend_for(tmp_path)

    first = backend.emit_event(
        scope,
        kind="pipeline.init",
        payload={"status": "started"},
        event_scope="trace",
    )
    second = backend.emit_event(
        scope,
        kind="phase.end",
        payload={"phase": "review"},
        phase="review",
        idempotency_key="review-1",
    )

    assert first.sequence == 0
    assert second.sequence == 1
    events = backend.read_events(scope)
    assert [row.sequence for row in events] == [0, 1]
    assert [row.kind for row in events] == ["pipeline.init", "phase.end"]
    assert events[0].payload["scope"] == "trace"
    assert events[1].payload["phase"] == "review"
    assert events[1].payload["idempotency_key"] == "review-1"


def test_file_backend_reads_and_writes_trace_artifacts(tmp_path: Path) -> None:
    backend, scope = _backend_for(tmp_path)

    state_path = backend.write_trace_artifact(
        scope,
        name="state.json",
        payload={"resume_cursor": {"stage": "checkpoint"}},
    )
    tree_path = backend.write_trace_artifact(
        scope,
        name="tree.json",
        payload={"root_path": "root", "nodes": [{"path": "root"}]},
    )
    events_path = backend.write_trace_artifact(
        scope,
        name="events.ndjson",
        payload=[
            {"seq": 0, "kind": "pipeline.init", "payload": {}},
            {"seq": 1, "kind": "phase.end", "payload": {"phase": "review"}},
        ],
    )

    assert state_path == str(tmp_path / "state.json")
    assert tree_path == str(tmp_path / "tree.json")
    assert events_path == str(tmp_path / "events.ndjson")
    assert backend.read_trace_artifact(scope, name="state.json") == {
        "resume_cursor": {"stage": "checkpoint"}
    }
    assert backend.read_trace_artifact(scope, name="tree.json") == {
        "root_path": "root",
        "nodes": [{"path": "root"}],
    }
    assert backend.read_trace_artifact(scope, name="events.ndjson") == [
        {"seq": 0, "kind": "pipeline.init", "payload": {}},
        {"seq": 1, "kind": "phase.end", "payload": {"phase": "review"}},
    ]
