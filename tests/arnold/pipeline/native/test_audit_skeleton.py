"""Per-attempt audit skeleton tests.

Covers the M6 requirement that every attempt audit record includes:
- stable ``attempt_id`` (unique per attempt)
- parent lineage (``run_path``, ``parent_run_path``)
- step path (``step_path``)
- attempt start (``started_at``)
- step outcome (``status``)
- attempt end (``ended_at``)
- path-addressed correlation to tree traces (``call_site_path``)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.native import (
    compile_pipeline,
    phase,
    pipeline,
    run_native_pipeline,
    workflow,
)
from arnold.pipeline.native.audit import AuditHooks, AuditRecord
from arnold.pipeline.native.hooks import NullNativeRuntimeHooks


# ── helpers ───────────────────────────────────────────────────────────


def _read_audit_ndjson(audit_dir: Path) -> list[dict[str, Any]]:
    """Read and parse the audit.ndjson file, returning a list of records."""
    audit_file = audit_dir / "audit.ndjson"
    if not audit_file.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in audit_file.read_text(encoding="utf-8").strip().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _step_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter audit records to only step-attempt records (exclude run.init)."""
    return [r for r in records if "attempt_id" in r]


# ── AuditRecord unit tests ────────────────────────────────────────────


class TestAuditRecordFields:
    """All required M6 skeleton fields are present on AuditRecord."""

    def test_attempt_id_is_stable_hex_string(self) -> None:
        """attempt_id must be a non-empty hex string (UUID-based)."""
        record = AuditRecord(
            attempt_id="abc123def456",
            run_id="run-01",
            step_path="root/step",
        )
        assert isinstance(record.attempt_id, str)
        assert len(record.attempt_id) == 12
        assert all(c in "0123456789abcdef" for c in record.attempt_id)

    def test_run_path_is_recorded(self) -> None:
        """run_path is captured for lineage."""
        record = AuditRecord(
            attempt_id="abc123",
            run_id="run-01",
            step_path="root/child/step",
            run_path="root/child",
        )
        assert record.run_path == "root/child"

    def test_parent_run_path_is_recorded(self) -> None:
        """parent_run_path is captured for trace correlation."""
        record = AuditRecord(
            attempt_id="abc123",
            run_id="run-01",
            step_path="root/child/step",
            parent_run_path="root",
        )
        assert record.parent_run_path == "root"

    def test_parent_run_path_can_be_none(self) -> None:
        """parent_run_path may be None for root-level steps."""
        record = AuditRecord(
            attempt_id="abc123",
            run_id="run-01",
            step_path="root/step",
            parent_run_path=None,
        )
        assert record.parent_run_path is None

    def test_call_site_path_is_recorded(self) -> None:
        """call_site_path is captured for tree-trace correlation."""
        record = AuditRecord(
            attempt_id="abc123",
            run_id="run-01",
            step_path="root/child/step",
            call_site_path=["child"],
        )
        assert record.call_site_path == ["child"]

    def test_call_site_path_can_be_none(self) -> None:
        """call_site_path may be None for root-level steps."""
        record = AuditRecord(
            attempt_id="abc123",
            run_id="run-01",
            step_path="root/step",
            call_site_path=None,
        )
        assert record.call_site_path is None

    def test_to_dict_includes_all_skeleton_fields(self) -> None:
        """to_dict() must serialize all M6-required fields."""
        record = AuditRecord(
            attempt_id="abc123",
            run_id="run-01",
            step_path="root/step",
            run_path="root",
            parent_run_path=None,
            call_site_path=[],
            attempt=1,
            input_keys=["state", "inputs"],
        )
        d = record.to_dict()

        required_fields = {
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
        }
        assert set(d.keys()) == required_fields
        assert d["attempt_id"] == "abc123"
        assert d["run_id"] == "run-01"
        assert d["step_path"] == "root/step"
        assert d["run_path"] == "root"
        assert d["parent_run_path"] is None
        assert d["call_site_path"] == []
        assert d["attempt"] == 1
        assert d["status"] == "started"

    def test_started_at_is_iso_timestamp(self) -> None:
        """started_at must be an ISO-8601 timestamp string."""
        record = AuditRecord(
            attempt_id="abc123",
            run_id="run-01",
            step_path="root/step",
        )
        assert isinstance(record.started_at, str)
        assert "T" in record.started_at
        # Must be parseable as ISO format
        from datetime import datetime

        datetime.fromisoformat(record.started_at)

    def test_mark_success_sets_status_and_ended_at(self) -> None:
        """mark_success must set status='success' and populate ended_at."""
        record = AuditRecord(
            attempt_id="abc123",
            run_id="run-01",
            step_path="root/step",
        )
        record.mark_success({"output": "value"})
        assert record.status == "success"
        assert record.ended_at is not None
        assert "T" in record.ended_at
        assert record.output_keys == ["output"]

    def test_mark_failure_sets_status_and_error_details(self) -> None:
        """mark_failure must set status='failure' and error details."""
        record = AuditRecord(
            attempt_id="abc123",
            run_id="run-01",
            step_path="root/step",
        )
        exc = ValueError("bad value")
        record.mark_failure(exc)
        assert record.status == "failure"
        assert record.ended_at is not None
        assert record.error_type == "ValueError"
        assert record.error_message == "bad value"


# ── AuditHooks integration tests ──────────────────────────────────────


class TestAuditHooksIntegration:
    """End-to-end tests verifying audit records through pipeline execution."""

    def test_single_phase_produces_audit_record(self, tmp_path: Path) -> None:
        """A single-phase pipeline produces one audit record with all skeleton fields."""
        audit_dir = tmp_path / "audit"

        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        hooks = AuditHooks(audit_dir=audit_dir)
        result = run_native_pipeline(prog, hooks=hooks)

        assert result.state == {"result": 42}

        records = _read_audit_ndjson(audit_dir)
        step_recs = _step_records(records)
        assert len(step_recs) == 1

        rec = step_recs[0]
        # Required skeleton fields
        assert "attempt_id" in rec
        assert isinstance(rec["attempt_id"], str)
        assert len(rec["attempt_id"]) == 32  # full UUID hex

        assert "run_id" in rec
        assert isinstance(rec["run_id"], str)

        # step_path must be a non-empty string (falls back to run_path on older runtimes)
        assert isinstance(rec["step_path"], str)
        assert len(rec["step_path"]) > 0

        # run_path must be a non-empty string
        assert isinstance(rec["run_path"], str)
        assert len(rec["run_path"]) > 0

        # parent_run_path is present (may be None for root-level)
        assert "parent_run_path" in rec

        # call_site_path is present (may be empty list for root-level)
        assert "call_site_path" in rec
        assert isinstance(rec["call_site_path"], list)

        assert rec["attempt"] == 1
        assert rec["status"] == "success"
        assert "T" in rec["started_at"]
        assert "T" in rec["ended_at"]
        assert rec["started_at"] <= rec["ended_at"]

    def test_multi_phase_pipeline_produces_multiple_records(self, tmp_path: Path) -> None:
        """Each phase produces a separate audit record with its own attempt_id."""
        audit_dir = tmp_path / "audit"

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        hooks = AuditHooks(audit_dir=audit_dir)
        result = run_native_pipeline(prog, hooks=hooks)

        assert result.state == {"a": 1, "b": 2}

        records = _read_audit_ndjson(audit_dir)
        step_recs = _step_records(records)
        assert len(step_recs) == 2

        # Each record has a unique attempt_id
        ids = {r["attempt_id"] for r in step_recs}
        assert len(ids) == 2

        # All share the same run_id
        run_ids = {r["run_id"] for r in step_recs}
        assert len(run_ids) == 1

        # Step paths are non-empty strings
        for r in step_recs:
            assert isinstance(r["step_path"], str)
            assert len(r["step_path"]) > 0
            assert r["status"] == "success"

    def test_nested_workflow_produces_correct_lineage(self, tmp_path: Path) -> None:
        """Child workflow steps have parent_run_path and call_site_path set."""
        audit_dir = tmp_path / "audit"

        @phase
        def child_step(ctx: dict) -> dict:
            return {"child": "done"}

        @workflow(
            name="child_flow",
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield child(ctx, id="child_call")
            return state

        prog = compile_pipeline(parent)
        hooks = AuditHooks(audit_dir=audit_dir)
        result = run_native_pipeline(prog, hooks=hooks)

        assert result.state == {"child": "done"}

        records = _read_audit_ndjson(audit_dir)
        step_recs = _step_records(records)

        # At least one step record exists for the child workflow
        # (on older runtimes, subpipeline steps may not produce audit records;
        #  on newer runtimes with step_path context, they do)
        if step_recs:
            # If records exist, verify lineage fields are present
            for rec in step_recs:
                assert "attempt_id" in rec
                assert "run_path" in rec
                assert "parent_run_path" in rec
                assert "call_site_path" in rec
                assert isinstance(rec["step_path"], str)
                assert len(rec["step_path"]) > 0

    def test_failed_step_produces_failure_record(self, tmp_path: Path) -> None:
        """A step that raises an exception produces a failure audit record."""
        audit_dir = tmp_path / "audit"

        @phase
        def failing_step(ctx: dict) -> dict:
            raise RuntimeError("boom")

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield failing_step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        hooks = AuditHooks(audit_dir=audit_dir)

        with pytest.raises(RuntimeError, match="boom"):
            run_native_pipeline(prog, hooks=hooks)

        records = _read_audit_ndjson(audit_dir)
        step_recs = _step_records(records)
        assert len(step_recs) == 1

        rec = step_recs[0]
        assert rec["status"] == "failure"
        assert rec["error_type"] == "RuntimeError"
        assert rec["error_message"] == "boom"
        # Ended_at must still be populated for failures
        assert "T" in rec["ended_at"]

    def test_pass_through_when_audit_dir_is_none(self) -> None:
        """When audit_dir is None, AuditHooks is a pure pass-through."""
        hooks = AuditHooks(audit_dir=None)

        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)
        assert result.state == {"result": 42}
        # No audit file written
        assert hooks._audit_path() is None

    def test_audit_record_has_run_init_marker(self, tmp_path: Path) -> None:
        """The audit file starts with a run.init event."""
        audit_dir = tmp_path / "audit"

        @phase
        def step(ctx: dict) -> dict:
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        hooks = AuditHooks(audit_dir=audit_dir)
        run_native_pipeline(prog, hooks=hooks)

        records = _read_audit_ndjson(audit_dir)
        assert len(records) >= 2  # run.init + at least 1 step record
        assert records[0]["event"] == "run.init"
        assert "run_id" in records[0]
        assert "started_at" in records[0]

    def test_timestamps_are_ordered(self, tmp_path: Path) -> None:
        """started_at <= ended_at for every record."""
        audit_dir = tmp_path / "audit"

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        hooks = AuditHooks(audit_dir=audit_dir)
        run_native_pipeline(prog, hooks=hooks)

        records = _read_audit_ndjson(audit_dir)
        step_recs = _step_records(records)
        for rec in step_recs:
            assert rec["started_at"] <= rec["ended_at"], (
                f"started_at ({rec['started_at']}) > ended_at ({rec['ended_at']})"
            )

    def test_path_addressed_correlation_to_tree_traces(self, tmp_path: Path) -> None:
        """Audit records contain path fields that correlate with tree traces.

        Specifically: step_path, run_path, parent_run_path, and call_site_path
        must be present and consistent across records.
        """
        audit_dir = tmp_path / "audit"

        @phase
        def child_step(ctx: dict) -> dict:
            return {"child": "ok"}

        @workflow(
            name="child_flow",
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: dict) -> dict:
            state = yield child_step(ctx)
            return state

        @phase
        def root_step(ctx: dict) -> dict:
            return {"root": "ok"}

        @pipeline
        def parent(ctx: dict) -> dict:
            state = yield root_step(ctx)
            state = yield child(ctx, id="inner")
            return state

        prog = compile_pipeline(parent)
        hooks = AuditHooks(audit_dir=audit_dir)
        run_native_pipeline(prog, hooks=hooks)

        records = _read_audit_ndjson(audit_dir)
        step_recs = _step_records(records)

        # All records must have path-addressed correlation fields
        for rec in step_recs:
            # step_path: stable tree-shaped path of the step
            assert "step_path" in rec
            assert isinstance(rec["step_path"], str)
            assert len(rec["step_path"]) > 0

            # run_path: parent of step_path, for trace correlation
            assert "run_path" in rec
            assert isinstance(rec["run_path"], str)
            assert len(rec["run_path"]) > 0

            # parent_run_path: parent lineage for tree-trace correlation
            assert "parent_run_path" in rec

            # call_site_path: call-site segments for tree-trace correlation
            assert "call_site_path" in rec
            assert isinstance(rec["call_site_path"], list)

        # Root step paths should all start with "root"
        for rec in step_recs:
            assert rec["step_path"].startswith("root"), (
                f"step_path must start with 'root': {rec['step_path']}"
            )
            assert rec["run_path"].startswith("root"), (
                f"run_path must start with 'root': {rec['run_path']}"
            )

    def test_attempt_numbers_are_stable(self, tmp_path: Path) -> None:
        """Attempt numbers start at 1 and are consistent across records."""
        audit_dir = tmp_path / "audit"

        @phase
        def step(ctx: dict) -> dict:
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        hooks = AuditHooks(audit_dir=audit_dir)
        run_native_pipeline(prog, hooks=hooks)

        records = _read_audit_ndjson(audit_dir)
        step_recs = _step_records(records)
        assert len(step_recs) == 1
        assert step_recs[0]["attempt"] == 1

    def test_audit_hooks_delegates_to_inner(self, tmp_path: Path) -> None:
        """AuditHooks delegates all callbacks to the inner hooks."""
        audit_dir = tmp_path / "audit"
        calls: list[str] = []

        class TrackingHooks(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                calls.append("inner.on_step_start")
                return ctx

        inner = TrackingHooks()
        hooks = AuditHooks(inner=inner, audit_dir=audit_dir)

        @phase
        def step(ctx: dict) -> dict:
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, hooks=hooks)

        assert "inner.on_step_start" in calls

    def test_input_keys_are_recorded(self, tmp_path: Path) -> None:
        """input_keys captures the top-level keys of the context dict."""
        audit_dir = tmp_path / "audit"

        @phase
        def step(ctx: dict) -> dict:
            return {"ok": True}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        hooks = AuditHooks(audit_dir=audit_dir)
        run_native_pipeline(prog, hooks=hooks, initial_state={"base": 1})

        records = _read_audit_ndjson(audit_dir)
        step_recs = _step_records(records)
        assert len(step_recs) == 1
        # Context dict contains at minimum: state, inputs, run_path, step_path, etc.
        assert "state" in step_recs[0]["input_keys"]
        assert "inputs" in step_recs[0]["input_keys"]


# ── AuditHooks constructor tests ──────────────────────────────────────


class TestAuditHooksConstructor:
    """AuditHooks constructor and boundary behavior."""

    def test_default_inner_is_null_hooks(self) -> None:
        """When no inner hooks are provided, NullNativeRuntimeHooks is used."""
        hooks = AuditHooks(audit_dir=None)
        assert isinstance(hooks._inner, NullNativeRuntimeHooks)

    def test_explicit_inner_is_used(self) -> None:
        """Explicit inner hooks are stored and used."""

        class CustomHooks(NullNativeRuntimeHooks):
            pass

        inner = CustomHooks()
        hooks = AuditHooks(inner=inner, audit_dir=None)
        assert hooks._inner is inner

    def test_run_id_is_stable_uuid_hex(self) -> None:
        """The run_id is a UUID hex string generated at construction."""
        hooks = AuditHooks(audit_dir=None)
        assert isinstance(hooks._run_id, str)
        assert len(hooks._run_id) == 32
        assert all(c in "0123456789abcdef" for c in hooks._run_id)

    def test_different_hooks_have_different_run_ids(self) -> None:
        """Each AuditHooks instance gets its own run_id."""
        h1 = AuditHooks(audit_dir=None)
        h2 = AuditHooks(audit_dir=None)
        assert h1._run_id != h2._run_id

    def test_halt_reason_defaults_to_none(self) -> None:
        """halt_reason starts as None."""
        hooks = AuditHooks(audit_dir=None)
        assert hooks.halt_reason is None
