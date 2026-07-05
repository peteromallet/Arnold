from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Protocol

import pytest

from arnold.pipeline.native.persistence import NativePersistenceScope
from arnold.runtime.state_persistence import atomic_write_json


@dataclass(frozen=True)
class BackendContext:
    backend: Any
    scope: NativePersistenceScope
    root: Path | None = None
    seed_state: Callable[[Any], None] | None = None


class BackendHarness(Protocol):
    def open(self, name: str = "default") -> BackendContext: ...


class PersistenceBackendConformanceTests:
    def test_checkpoint_write_read_delete_cycle(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        ctx.backend.write_resume_cursor(
            ctx.scope,
            payload={"stage": "review", "native": {"pc": 3, "version": 1}},
        )
        assert ctx.backend.read_resume_cursor(ctx.scope) == {
            "stage": "review",
            "native": {"pc": 3, "version": 1},
        }

        ctx.backend.write_resume_cursor(
            ctx.scope,
            payload={"stage": "execute", "native": {"pc": 5, "version": 1}},
        )
        assert ctx.backend.read_resume_cursor(ctx.scope) == {
            "stage": "execute",
            "native": {"pc": 5, "version": 1},
        }

        ctx.backend.delete_resume_cursor(ctx.scope)
        assert ctx.backend.read_resume_cursor(ctx.scope) is None
        ctx.backend.delete_resume_cursor(ctx.scope)
        assert ctx.backend.read_resume_cursor(ctx.scope) is None

    def test_state_resume_cursor_reads_nested_cursor(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        assert ctx.seed_state is not None
        ctx.seed_state(
            {
                "resume_cursor": {"stage": "state-first"},
                "contract_result": {"status": "ignored"},
            }
        )
        assert ctx.backend.read_state_resume_cursor(ctx.scope) == {"stage": "state-first"}

    def test_composite_cursor_write_read_delete_cycle(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        payload = {"kind": "composite_suspension", "children": {"child_a": {"stage": "review"}}}
        ctx.backend.write_composite_resume_cursor(ctx.scope, payload=payload)
        assert ctx.backend.read_composite_resume_cursor(ctx.scope) == payload
        ctx.backend.delete_composite_resume_cursor(ctx.scope)
        assert ctx.backend.read_composite_resume_cursor(ctx.scope) is None

    def test_human_gate_write_read_delete_cycle(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        payload = {"status": "awaiting_user", "phase": "approve"}
        ctx.backend.write_human_gate(ctx.scope, payload=payload)
        assert ctx.backend.read_human_gate(ctx.scope) == payload
        ctx.backend.delete_human_gate(ctx.scope)
        assert ctx.backend.read_human_gate(ctx.scope) is None

    @pytest.mark.parametrize(
        ("name", "payload"),
        [
            ("state.json", {"resume_cursor": {"stage": "checkpoint"}, "version": 1}),
            ("tree.json", {"root_path": "root", "nodes": [{"path": "root/a"}]}),
            ("stages.json", [{"name": "review", "pc": 1}, {"name": "execute", "pc": 2}]),
            ("artifacts.json", {"artifacts": [{"name": "a.txt", "size": 123}]}),
            ("checkpoint.json", {"native": {"pc": 0, "version": 1}, "stage": "init"}),
            (
                "events.ndjson",
                [
                    {"seq": 0, "kind": "pipeline.init", "payload": {}},
                    {"seq": 1, "kind": "phase.end", "payload": {"phase": "review"}},
                ],
            ),
        ],
    )
    def test_trace_artifact_round_trip(
        self,
        backend_harness: BackendHarness,
        name: str,
        payload: Any,
    ) -> None:
        ctx = backend_harness.open()
        ctx.backend.write_trace_artifact(ctx.scope, name=name, payload=payload)
        assert ctx.backend.read_trace_artifact(ctx.scope, name=name) == payload

    def test_audit_append_and_restart_readback(self, backend_harness: BackendHarness) -> None:
        first = backend_harness.open("restart")
        first.backend.append_audit_record(first.scope, payload={"event": "first"})

        second = backend_harness.open("restart")
        second.backend.append_audit_record(second.scope, payload={"event": "second"})
        rows = second.backend.read_audit_records(second.scope)
        assert [row.payload["event"] for row in rows] == ["first", "second"]
        assert [row.sequence for row in rows] == [1, 2]

    def test_event_emission_is_monotonic_and_queryable(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        ctx.backend.emit_event(ctx.scope, kind="step.start", payload={"step": 1})
        ctx.backend.emit_event(ctx.scope, kind="step.end", payload={"step": 1}, phase="review")
        ctx.backend.emit_event(ctx.scope, kind="step.start", payload={"step": 2}, idempotency_key="step-2")

        rows = ctx.backend.read_events(ctx.scope)
        assert [row.sequence for row in rows] == [0, 1, 2]
        assert [row.kind for row in rows] == ["step.start", "step.end", "step.start"]
        assert rows[1].payload.get("phase") == "review"
        assert rows[2].payload.get("idempotency_key") == "step-2"
        assert [row.sequence for row in ctx.backend.read_events(ctx.scope, since_sequence=0, limit=2)] == [1, 2]
        assert [row.sequence for row in ctx.backend.read_events(ctx.scope, to_sequence=2)] == [0, 1]

    def test_resolve_surface_empty_dir_yields_none(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        resolved = ctx.backend.resolve_resume_surface(ctx.scope)
        assert resolved.source == "none"
        assert resolved.kind == "none"
        assert resolved.blocked is False
        assert resolved.payload is None

    def test_resolve_surface_state_resume_cursor_wins(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        assert ctx.seed_state is not None
        ctx.seed_state({"resume_cursor": {"stage": "state-first"}})
        ctx.backend.write_composite_resume_cursor(
            ctx.scope,
            payload={"kind": "composite_suspension", "children": {}},
        )
        ctx.backend.write_human_gate(ctx.scope, payload={"status": "awaiting_user"})
        ctx.backend.write_resume_cursor(ctx.scope, payload={"stage": "fallback"})

        resolved = ctx.backend.resolve_resume_surface(ctx.scope)
        assert resolved.source == "state_resume_cursor"
        assert resolved.kind == "state_resume_cursor"
        assert resolved.blocked is False
        assert resolved.payload == {"stage": "state-first"}

    def test_resolve_surface_composite_before_awaiting_user(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        ctx.backend.write_composite_resume_cursor(
            ctx.scope,
            payload={"kind": "composite_suspension", "children": {"c": {}}},
        )
        ctx.backend.write_human_gate(ctx.scope, payload={"status": "awaiting_user"})

        resolved = ctx.backend.resolve_resume_surface(ctx.scope)
        assert resolved.source == "composite_resume_cursor"
        assert resolved.kind == "composite_resume_cursor"
        assert resolved.blocked is False

    def test_resolve_surface_awaiting_user_before_resume_cursor(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        ctx.backend.write_human_gate(ctx.scope, payload={"status": "awaiting_user", "phase": "approve"})
        ctx.backend.write_resume_cursor(ctx.scope, payload={"stage": "fallback"})

        resolved = ctx.backend.resolve_resume_surface(ctx.scope)
        assert resolved.source == "awaiting_user"
        assert resolved.kind == "awaiting_user"
        assert resolved.blocked is False
        assert resolved.payload == {"status": "awaiting_user", "phase": "approve"}

    def test_resolve_surface_resume_cursor_last_resort(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        payload = {"stage": "last-resort", "native": {"pc": 1, "version": 1}}
        ctx.backend.write_resume_cursor(ctx.scope, payload=payload)

        resolved = ctx.backend.resolve_resume_surface(ctx.scope)
        assert resolved.source == "resume_cursor"
        assert resolved.kind == "native_resume_cursor"
        assert resolved.blocked is False
        assert resolved.payload == payload

    def test_resolve_surface_invalid_composite_is_blocked(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        ctx.backend.write_composite_resume_cursor(ctx.scope, payload={"kind": "wrong_kind", "children": {}})
        resolved = ctx.backend.resolve_resume_surface(ctx.scope)
        assert resolved.source == "composite_resume_cursor"
        assert resolved.kind == "invalid_composite_resume_cursor"
        assert resolved.blocked is True

    def test_resolve_surface_corrupt_native_is_blocked(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        ctx.backend.write_resume_cursor(ctx.scope, payload={"stage": "bad", "native": "not_a_dict"})
        resolved = ctx.backend.resolve_resume_surface(ctx.scope)
        assert resolved.source == "resume_cursor"
        assert resolved.kind == "corrupt_native"
        assert resolved.blocked is True

    def test_resolve_surface_observations_include_all_sources(self, backend_harness: BackendHarness) -> None:
        ctx = backend_harness.open()
        ctx.backend.write_human_gate(ctx.scope, payload={"status": "awaiting_user"})
        resolved = ctx.backend.resolve_resume_surface(ctx.scope)
        assert {obs.source for obs in resolved.observations} == {
            "state_resume_cursor",
            "typed_contract",
            "composite_resume_cursor",
            "awaiting_user",
            "resume_cursor",
        }
        assert len(resolved.observations) == 5

    def test_scopes_are_isolated_for_cursors_audit_trace_and_events(
        self,
        backend_harness: BackendHarness,
    ) -> None:
        a = backend_harness.open("a")
        b = backend_harness.open("b")

        a.backend.write_resume_cursor(a.scope, payload={"stage": "a"})
        b.backend.write_resume_cursor(b.scope, payload={"stage": "b"})
        assert a.backend.read_resume_cursor(a.scope) == {"stage": "a"}
        assert b.backend.read_resume_cursor(b.scope) == {"stage": "b"}

        a.backend.append_audit_record(a.scope, payload={"event": "audit-a"})
        b.backend.append_audit_record(b.scope, payload={"event": "audit-b"})
        assert [row.payload["event"] for row in a.backend.read_audit_records(a.scope)] == ["audit-a"]
        assert [row.payload["event"] for row in b.backend.read_audit_records(b.scope)] == ["audit-b"]

        a.backend.write_trace_artifact(a.scope, name="state.json", payload={"key": "a"})
        b.backend.write_trace_artifact(b.scope, name="state.json", payload={"key": "b"})
        assert a.backend.read_trace_artifact(a.scope, name="state.json") == {"key": "a"}
        assert b.backend.read_trace_artifact(b.scope, name="state.json") == {"key": "b"}

        a.backend.emit_event(a.scope, kind="only-a")
        b.backend.emit_event(b.scope, kind="only-b")
        assert [row.kind for row in a.backend.read_events(a.scope)] == ["only-a"]
        assert [row.kind for row in b.backend.read_events(b.scope)] == ["only-b"]


def write_state_payload(root: Path, payload: Any) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "state.json").write_text(json.dumps(payload), encoding="utf-8")
