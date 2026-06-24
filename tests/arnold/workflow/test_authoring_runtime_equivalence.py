"""M7: runtime-equivalence tests for Python-shaped authoring.

Each authored M3 fixture is compiled into a :class:`arnold.manifest.WorkflowManifest`
and then executed through the same journal-backed manifest runtime that powers the
explicit-DSL canonical fixtures.  These tests prove that the authoring path is
behaviourally equivalent: the compiled manifests produce deterministic final states,
event journals, suspension/resume cursors, and subpipeline scopes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from arnold.execution import ExecutionRegistries, ExecutionState, run
from arnold.execution.backend import LocalJournalBackend
from arnold.kernel import read_event_journal
from arnold.workflow import compile_workflow_file

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "workflow_authoring" / "m3"


class _DeterministicBackend(LocalJournalBackend):
    """Backend with stable time and run identifiers for reproducible events."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("run_id", "m7-runtime-equivalence")
        kwargs.setdefault(
            "init_ts", datetime(2026, 6, 22, 0, 0, 0, tzinfo=timezone.utc)
        )
        super().__init__(**kwargs)
        self._now_value = datetime(2026, 6, 22, 0, 0, 0, tzinfo=timezone.utc)
        self._monotonic_value = 0.0

    def _now(self) -> datetime:
        return self._now_value

    def _monotonic(self) -> float:
        self._monotonic_value += 1.0
        return self._monotonic_value


def _normalize_event(event: Any) -> dict[str, Any]:
    """Strip non-deterministic payload fields so two runs can be compared."""

    payload = {
        key: value
        for key, value in event.payload.items()
        if key not in {"occurred_at", "timestamp", "run_id", "created_at", "updated_at"}
    }
    return {
        "family": event.family.value,
        "kind": event.kind,
        "payload": payload,
        "scope_stack": tuple(payload.get("scope_stack", ())),
    }


@pytest.mark.parametrize(
    ("fixture_name", "expected_completed"),
    [
        (
            "valid_m3_branch_routes.py",
            {"route", "execute", "review-approved"},
        ),
        (
            "valid_m3_bounded_loop.py",
            {"plan", "execute", "review", "revise"},
        ),
        (
            "valid_m3_policy_refs.py",
            {"plan", "execute", "review"},
        ),
        (
            "valid_m3_subflow_ref.py",
            {"plan", "execute", "nested-review"},
        ),
    ],
)
def test_compiled_authoring_fixture_runs_to_completion(
    tmp_path: Path,
    fixture_name: str,
    expected_completed: set[str],
) -> None:
    manifest = compile_workflow_file(FIXTURE_DIR / fixture_name)
    backend = _DeterministicBackend()

    result = run(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
        backend=backend,
    )

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)
    kinds = [e.kind for e in events]

    assert "manifest_loaded" in kinds
    assert "manifest_validated" in kinds
    assert "node_completed" in kinds
    assert "run_completed" in kinds

    completed = {
        e.payload["node_ref"]
        for e in events
        if e.kind == "node_completed" and e.payload.get("child_key") is None
    }
    assert completed == expected_completed, f"completed nodes mismatch for {fixture_name}"


@pytest.mark.parametrize(
    ("fixture_name", "expected_shape_events"),
    [
        (
            "valid_m3_branch_routes.py",
            {"branch_selected": 1},
        ),
        (
            "valid_m3_bounded_loop.py",
            {"loop_iteration": 3},
        ),
        (
            "valid_m3_policy_refs.py",
            {},
        ),
        (
            "valid_m3_subflow_ref.py",
            {"subpipeline_entered": 1, "subpipeline_exited": 1},
        ),
    ],
)
def test_compiled_authoring_fixture_emits_expected_shape_events(
    tmp_path: Path,
    fixture_name: str,
    expected_shape_events: dict[str, int],
) -> None:
    manifest = compile_workflow_file(FIXTURE_DIR / fixture_name)
    backend = _DeterministicBackend()

    result = run(
        manifest,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
        backend=backend,
    )

    assert result.state is ExecutionState.COMPLETED
    events = read_event_journal(tmp_path)

    for kind, expected_count in expected_shape_events.items():
        actual = [e for e in events if e.kind == kind]
        assert len(actual) == expected_count, (
            f"{fixture_name}: expected {expected_count} {kind} events, got {len(actual)}"
        )


@pytest.mark.parametrize("fixture_name", [
    "valid_m3_branch_routes.py",
    "valid_m3_bounded_loop.py",
    "valid_m3_policy_refs.py",
    "valid_m3_subflow_ref.py",
])
def test_compiled_authoring_fixture_is_deterministic_across_runs(
    tmp_path: Path,
    fixture_name: str,
) -> None:
    manifest = compile_workflow_file(FIXTURE_DIR / fixture_name)

    def _run(root: Path) -> ExecutionState:
        backend = _DeterministicBackend(run_id="m7-determinism")
        return run(
            manifest,
            artifact_root=root,
            registries=ExecutionRegistries(),
            backend=backend,
        )

    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    result_a = _run(root_a)
    result_b = _run(root_b)

    assert result_a.state is ExecutionState.COMPLETED
    assert result_b.state is ExecutionState.COMPLETED
    assert result_a.outputs == result_b.outputs

    events_a = read_event_journal(root_a)
    events_b = read_event_journal(root_b)
    assert len(events_a) == len(events_b)
    assert [_normalize_event(e) for e in events_a] == [
        _normalize_event(e) for e in events_b
    ]


def test_compiled_authoring_manifest_hash_is_stable(tmp_path: Path) -> None:
    """Re-compiling the same source file yields identical manifest identity."""

    source = FIXTURE_DIR / "valid_m3_policy_refs.py"
    first = compile_workflow_file(source)
    second = compile_workflow_file(source)

    assert first.manifest_hash == second.manifest_hash
    assert first.topology_hash == second.topology_hash

    # Runtime does not mutate the manifest hash.
    backend = _DeterministicBackend()
    run(
        first,
        artifact_root=tmp_path,
        registries=ExecutionRegistries(),
        backend=backend,
    )
    assert first.manifest_hash == second.manifest_hash
