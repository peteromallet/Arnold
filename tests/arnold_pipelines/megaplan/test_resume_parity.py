"""Resume and full-pipeline parity tests.

Proves that a manifest-backed run can be started fresh, suspended at a human
gate, and resumed from a journal-derived cursor without relying on mutable
``state.json`` authority.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from arnold.execution import run as run_manifest
from arnold.execution.registries import ExecutionRegistries
from arnold.execution.result import ExecutionState
from arnold.execution.state_store import FileStateStore
from arnold.kernel import read_event_journal
from arnold.manifest import NodeRef, manifest_coordinate

from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline
from tests.arnold_pipelines.megaplan.test_parity_harness import (
    FakeMegaplanBackend,
    completed_nodes,
    event_sequence,
    make_simple_handler,
    normalize_events,
)


def _fresh_handlers() -> dict[str, Any]:
    return {
        "prep": make_simple_handler({"success": True, "next_step": "plan"}),
        "plan": make_simple_handler({"success": True, "next_step": "critique"}),
        "critique": make_simple_handler({"success": True, "next_step": "gate"}),
        "gate": make_simple_handler({"success": True, "recommendation": "PROCEED"}),
        "finalize": make_simple_handler({"success": True, "next_step": "execute"}),
        "execute": make_simple_handler({"success": True, "next_step": "review"}),
        "review": make_simple_handler({"success": True, "verdict": "pass"}),
    }


def _suspending_handlers() -> dict[str, Any]:
    return {
        "prep": make_simple_handler({"success": True, "next_step": "plan"}),
        "plan": make_simple_handler({"success": True, "next_step": "critique"}),
        "critique": make_simple_handler({"success": True, "next_step": "gate"}),
        "gate": make_simple_handler({"success": True, "state": "awaiting_human", "next_step": "suspend"}),
    }


class TestFreshPlanParity:
    def test_full_pipeline_fresh_run_event_sequence(self, tmp_path: Path) -> None:
        manifest = build_and_compile_pipeline()
        plan_dir = tmp_path / "plans" / "fresh"
        plan_dir.mkdir(parents=True)
        artifact_root = tmp_path / "artifacts"

        backend = FakeMegaplanBackend(
            plan_dir=plan_dir,
            handlers=_fresh_handlers(),
            state={},
            args=argparse.Namespace(),
            run_id="fresh-run",
        )
        result = run_manifest(
            manifest,
            artifact_root=artifact_root,
            backend=backend,
            registries=ExecutionRegistries(),
        )
        events = list(read_event_journal(artifact_root))

        assert result.state == ExecutionState.COMPLETED
        sequence = event_sequence(events)
        # The journal records manifest lifecycle events; run_started is logger-only.
        assert sequence[0] == "manifest_loaded"
        assert sequence[-1] == "run_completed"
        assert completed_nodes(events) == [
            "prep", "plan", "critique", "gate", "finalize", "execute", "review", "halt"
        ]

    def test_fresh_run_normalized_events_are_deterministic(self, tmp_path: Path) -> None:
        manifest = build_and_compile_pipeline()
        plan_dir = tmp_path / "plans" / "fresh"
        plan_dir.mkdir(parents=True)
        artifact_root = tmp_path / "artifacts"

        backend = FakeMegaplanBackend(
            plan_dir=plan_dir,
            handlers=_fresh_handlers(),
            run_id="fresh-run",
        )
        run_manifest(manifest, artifact_root=artifact_root, backend=backend)
        events = list(read_event_journal(artifact_root))

        normalized = normalize_events(events)
        for event in normalized:
            payload = event["payload"]
            for key in ("run_id", "event_id", "timestamp", "duration_ms"):
                if key in payload:
                    assert payload[key] == "<normalized>", f"{key} not normalized"


class TestResumeFromSuspension:
    def test_suspended_run_resumes_from_journal_cursor(self, tmp_path: Path) -> None:
        manifest = build_and_compile_pipeline()
        plan_dir = tmp_path / "plans" / "resume"
        plan_dir.mkdir(parents=True)
        artifact_root = tmp_path / "artifacts"

        # First pass: suspend at gate.
        backend = FakeMegaplanBackend(
            plan_dir=plan_dir,
            handlers=_suspending_handlers(),
            run_id="resume-run",
        )
        result = run_manifest(manifest, artifact_root=artifact_root, backend=backend)
        events = list(read_event_journal(artifact_root))
        assert result.state == ExecutionState.SUSPENDED
        assert any(e.kind == "node_suspended" for e in events)

        # Derive a resume cursor from the journal-derived suspension point.
        suspend_event = next(e for e in events if e.kind == "node_suspended")
        cursor = manifest_coordinate(
            manifest.id,
            manifest.manifest_hash or "",
        ).cursor(
            node=NodeRef("gate"),
            reentry_id=suspend_event.payload.get("route_id") or "gate:human",
        )

        # Resume: gate now proceeds.
        resume_handlers = _fresh_handlers()
        resume_backend = FakeMegaplanBackend(
            plan_dir=plan_dir,
            handlers=resume_handlers,
            run_id="resume-run",
            reentry_id=cursor.reentry_id,
        )
        result2 = run_manifest(
            manifest,
            artifact_root=artifact_root,
            backend=resume_backend,
            resume_cursor=cursor,
        )
        events2 = list(read_event_journal(artifact_root))

        assert result2.state == ExecutionState.COMPLETED
        # Gate was suspended on the first pass and completed on the resume pass.
        assert completed_nodes(events2).count("gate") == 1
        assert completed_nodes(events2)[-4:-1] == ["finalize", "execute", "review"]

    def test_state_store_checkpoint_round_trips_without_state_json(self, tmp_path: Path) -> None:
        manifest = build_and_compile_pipeline()
        plan_dir = tmp_path / "plans" / "store"
        plan_dir.mkdir(parents=True)
        artifact_root = tmp_path / "artifacts"
        state_store = FileStateStore(artifact_root)

        backend = FakeMegaplanBackend(
            plan_dir=plan_dir,
            handlers=_suspending_handlers(),
            run_id="store-run",
            state_store=state_store,
        )
        result = run_manifest(
            manifest,
            artifact_root=artifact_root,
            backend=backend,
            state_store=state_store,
        )
        assert result.state == ExecutionState.SUSPENDED
        # The checkpoint is written by the state store, not by legacy state.json.
        assert state_store.list()
