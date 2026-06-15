"""Regression tests for doc-mode scope-drift handling.

Doc-mode plans declare their deliverable via the init-time ``output_path``
config and per-task evidence is ``sections_written`` rather than
``files_changed``. The execute scope-drift detector previously consulted
only ``payload.files_changed``, so the deliverable was always flagged as
unclaimed. Under robust+ robustness this blocked the finalized -> executed
transition with no recovery path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import arnold.pipelines.megaplan.execute.aggregation as execute_agg
from arnold.pipelines.megaplan.types import CliError


@pytest.fixture
def patched_snapshot(monkeypatch: pytest.MonkeyPatch):
    """Force a known git status snapshot containing the doc deliverable."""

    def _snapshot(_: Path) -> tuple[dict[str, str], str | None]:
        return ({"docs/foo.md": "deliverable-hash"}, None)

    monkeypatch.setattr(execute_agg, "_capture_git_status_snapshot", _snapshot)


@pytest.fixture
def patched_loc(monkeypatch: pytest.MonkeyPatch):
    """Pretend ``docs/foo.md`` has 264 LOC, well above the 20 LOC threshold."""

    def _loc(_project_dir: Path, paths: set[str]) -> dict[str, int]:
        return {path: 264 for path in paths}

    monkeypatch.setattr(execute_agg, "collect_loc_by_file", _loc)


def _empty_payload() -> dict[str, Any]:
    return {"files_changed": []}


def test_doc_mode_output_path_in_files_claimed(
    tmp_path: Path,
    patched_snapshot: None,
    patched_loc: None,
) -> None:
    """When mode == doc, the configured output_path is treated as claimed."""

    state: dict[str, Any] = {
        "config": {
            "project_dir": str(tmp_path),
            "mode": "doc",
            "output_path": "docs/foo.md",
        }
    }

    drift = execute_agg._compute_execute_scope_drift(
        tmp_path,
        _empty_payload(),
        state,
    )

    assert drift.files_added == []
    assert drift.severity != "high"
    assert drift.loc_added_outside_claimed == 0


def test_code_mode_unchanged_unclaimed_doc_still_flagged(
    tmp_path: Path,
    patched_snapshot: None,
    patched_loc: None,
) -> None:
    """Code-mode behavior is unchanged: an unclaimed deliverable is still flagged."""

    state: dict[str, Any] = {
        "config": {
            "project_dir": str(tmp_path),
            "mode": "code",
            # output_path is irrelevant for code mode and must not be auto-claimed
            "output_path": "docs/foo.md",
        }
    }

    drift = execute_agg._compute_execute_scope_drift(
        tmp_path,
        _empty_payload(),
        state,
    )

    assert drift.files_added == ["docs/foo.md"]
    assert drift.loc_added_outside_claimed == 264
    assert drift.severity == "high"


def test_compute_scope_drift_without_state_is_safe(
    tmp_path: Path,
    patched_snapshot: None,
    patched_loc: None,
) -> None:
    """Backwards compatibility: callers may still omit state."""

    drift = execute_agg._compute_execute_scope_drift(
        tmp_path,
        _empty_payload(),
    )

    assert drift.files_added == ["docs/foo.md"]
    assert drift.severity == "high"


def _write_batch_artifact(
    plan_dir: Path,
    batch_number: int,
    files_changed: list[str],
    *,
    task_files_changed: list[str] | None = None,
) -> None:
    import json

    payload: dict[str, Any] = {"files_changed": files_changed}
    if task_files_changed is not None:
        payload["task_updates"] = [
            {
                "task_id": f"T{batch_number}",
                "status": "done",
                "executor_notes": "done",
                "files_changed": task_files_changed,
                "commands_run": [],
            }
        ]
    (plan_dir / f"execution_batch_{batch_number}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


@pytest.fixture
def patched_snapshot_multi(monkeypatch: pytest.MonkeyPatch):
    """Working tree shows three deliverables spread across prior batches."""

    def _snapshot(_: Path) -> tuple[dict[str, str], str | None]:
        return (
            {"src/a.py": "h1", "src/b.py": "h2", "src/c.py": "h3"},
            None,
        )

    monkeypatch.setattr(execute_agg, "_capture_git_status_snapshot", _snapshot)


def test_per_batch_claims_unioned_from_disk(
    tmp_path: Path,
    patched_snapshot_multi: None,
    patched_loc: None,
) -> None:
    """A fully-claimed multi-batch run is not flagged even when the current
    aggregate payload is empty (e.g. a test-only final batch). Claims are
    unioned across every on-disk ``execution_batch_*.json``."""

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_batch_artifact(plan_dir, 1, ["src/a.py", "src/b.py"])
    _write_batch_artifact(plan_dir, 2, ["src/c.py"])
    # Final batch is test-only: empty files_changed.
    _write_batch_artifact(plan_dir, 3, [])

    state: dict[str, Any] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}

    drift = execute_agg._compute_execute_scope_drift(
        tmp_path,
        _empty_payload(),
        state,
        plan_dir=plan_dir,
    )

    assert drift.files_added == []
    assert drift.severity != "high"


def test_per_batch_claims_include_task_update_files_changed(
    tmp_path: Path,
    patched_snapshot_multi: None,
    patched_loc: None,
) -> None:
    """Retry aggregates must count durable per-task file evidence from earlier
    batch artifacts, even when top-level ``files_changed`` is empty."""

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_batch_artifact(
        plan_dir,
        1,
        [],
        task_files_changed=["src/a.py", "src/b.py"],
    )
    _write_batch_artifact(plan_dir, 2, [], task_files_changed=["src/c.py"])

    state: dict[str, Any] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}

    drift = execute_agg._compute_execute_scope_drift(
        tmp_path,
        _empty_payload(),
        state,
        plan_dir=plan_dir,
    )

    assert drift.files_added == []
    assert drift.severity != "high"


def test_per_batch_union_still_flags_genuinely_unclaimed_file(
    tmp_path: Path,
    patched_snapshot_multi: None,
    patched_loc: None,
) -> None:
    """A file changed in the tree but claimed by no batch still flags high."""

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_batch_artifact(plan_dir, 1, ["src/a.py", "src/b.py"])
    # src/c.py is in the working tree (patched_snapshot_multi) but unclaimed.
    _write_batch_artifact(plan_dir, 2, [])

    state: dict[str, Any] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}

    drift = execute_agg._compute_execute_scope_drift(
        tmp_path,
        _empty_payload(),
        state,
        plan_dir=plan_dir,
    )

    assert drift.files_added == ["src/c.py"]
    assert drift.severity == "high"


def test_single_shot_behavior_unchanged_without_plan_dir(
    tmp_path: Path,
    patched_snapshot: None,
    patched_loc: None,
) -> None:
    """Single-shot (no plan_dir) path is unchanged: an unclaimed deliverable
    is still flagged exactly as before."""

    state: dict[str, Any] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}

    drift = execute_agg._compute_execute_scope_drift(
        tmp_path,
        _empty_payload(),
        state,
    )

    assert drift.files_added == ["docs/foo.md"]
    assert drift.severity == "high"


def test_compute_scope_drift_halts_on_snapshot_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        execute_agg,
        "_capture_git_status_snapshot",
        lambda _path: (_ for _ in ()).throw(RuntimeError("snapshot boom")),
    )
    monkeypatch.setattr(
        execute_agg,
        "collect_loc_by_file",
        lambda _project_dir, _paths: {},
    )

    with pytest.raises(CliError, match="M3B_HALT_SCOPE_DRIFT_SNAPSHOT"):
        execute_agg._compute_execute_scope_drift(tmp_path, _empty_payload())
