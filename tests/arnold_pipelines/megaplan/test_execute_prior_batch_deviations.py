"""Regression tests for same-digest prior-batch deviation surfacing.

Occurrence 4c0190500877 (astrid-first m3): a re-dispatched batch with the same
task-set digest never saw its own prior blocking deviation, so the executor
repeated the identical test-budget violation (2x ``timeout 120`` = 240s >
max_seconds=120) across six tasks. ``_prior_execute_batch_deviations`` now
scans every earlier artifact with the same task-set digest, suppresses
deviations superseded by a later fully accepted terminal attempt, filters
transient advisories, and merges deterministically with a bounded tail.
"""

from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan._core import (
    execute_batch_artifact_path,
    stable_task_id_digest,
)
from arnold_pipelines.megaplan.prompts.execute import (
    _execute_batch_prompt,
    _prior_execute_batch_deviations,
)

_BUDGET_DEVIATION = (
    "Task T1 blocked by admitted test budget: task_test_budget_exhausted: "
    "declared test timeout total 240s exceeds max_seconds=120"
)


def _write_artifact(
    plan_dir: Path,
    index: int,
    task_ids: list[str],
    *,
    deviations: list[str] | None,
    task_updates: list[dict] | None = None,
    scope_digest: str | None = None,
) -> Path:
    path = execute_batch_artifact_path(plan_dir, index, task_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"deviations": deviations}
    if scope_digest is not None:
        payload["batch_scope"] = {"task_set_digest": scope_digest}
    if task_updates is not None:
        payload["task_updates"] = task_updates
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _accepted_update(task_id: str, status: str = "done") -> dict:
    return {
        "task_id": task_id,
        "status": status,
        "authority_validation": {"outcome": "accepted"},
    }


def _rejected_update(task_id: str, status: str = "blocked") -> dict:
    return {
        "task_id": task_id,
        "status": status,
        "authority_validation": {"outcome": "rejected"},
    }


def _make_state(tmp_path: Path) -> dict:
    return {
        "name": "megaplan-run",
        "created_at": "2026-07-10T00:00:00Z",
        "current_state": "finalized",
        "iteration": 1,
        "config": {"mode": "code", "project_dir": str(tmp_path), "max_tasks_per_batch": 2},
        "sessions": {},
        "history": [],
        "meta": {},
        "plan_versions": [{"hash": "sha256:plan-revision"}],
        "active_step": {"run_id": "coordinator-attempt", "attempt": 2},
    }


def _finalize_data(task_ids: list[str]) -> dict:
    return {
        "tasks": [
            {"id": tid, "status": "pending", "depends_on": [], "description": tid}
            for tid in task_ids
        ],
        "sense_checks": [],
        "baseline_test_failures": None,
        "user_actions": [],
    }


def test_same_digest_retry_surfaces_own_prior_budget_deviation(tmp_path: Path) -> None:
    task_ids = ["T1", "T2"]
    digest = stable_task_id_digest(task_ids)
    # Attempt at artifact 2 carried the budget deviation; retry dispatches at
    # artifact 7 with a deliberately different logical prompt batch number.
    _write_artifact(
        tmp_path,
        2,
        task_ids,
        deviations=[_BUDGET_DEVIATION],
        task_updates=[_rejected_update("T1"), _rejected_update("T2")],
        scope_digest=digest,
    )
    deviations = _prior_execute_batch_deviations(
        tmp_path,
        task_ids,
        prompt_batch_number=3,
        current_artifact_number=7,
    )
    assert deviations == [_BUDGET_DEVIATION]


def test_later_all_accepted_attempt_suppresses_older_same_digest(tmp_path: Path) -> None:
    task_ids = ["T1", "T2"]
    digest = stable_task_id_digest(task_ids)
    _write_artifact(
        tmp_path,
        2,
        task_ids,
        deviations=[_BUDGET_DEVIATION],
        task_updates=[_rejected_update("T1"), _rejected_update("T2")],
        scope_digest=digest,
    )
    # Artifact 4 is a fully accepted terminal attempt of the same task set.
    _write_artifact(
        tmp_path,
        4,
        task_ids,
        deviations=["Advisory audit finding: provisional"],
        task_updates=[_accepted_update("T1"), _accepted_update("T2")],
        scope_digest=digest,
    )
    deviations = _prior_execute_batch_deviations(
        tmp_path,
        task_ids,
        prompt_batch_number=5,
        current_artifact_number=7,
    )
    # Old hard deviation is superseded; the advisory is transient-filtered.
    assert deviations == []


def test_blocked_or_partial_attempt_does_not_suppress_older(tmp_path: Path) -> None:
    task_ids = ["T1", "T2"]
    digest = stable_task_id_digest(task_ids)
    _write_artifact(
        tmp_path,
        2,
        task_ids,
        deviations=[_BUDGET_DEVIATION],
        task_updates=[_rejected_update("T1"), _rejected_update("T2")],
        scope_digest=digest,
    )
    # Artifact 4 accepted only T1 (partial) — must NOT suppress the older block.
    _write_artifact(
        tmp_path,
        4,
        task_ids,
        deviations=["Advisory observation mismatch: later"],
        task_updates=[_accepted_update("T1"), _rejected_update("T2")],
        scope_digest=digest,
    )
    deviations = _prior_execute_batch_deviations(
        tmp_path,
        task_ids,
        prompt_batch_number=5,
        current_artifact_number=7,
    )
    assert _BUDGET_DEVIATION in deviations


def test_transient_filter_dedupe_order_and_cap(tmp_path: Path) -> None:
    task_ids = ["T1", "T2"]
    digest = stable_task_id_digest(task_ids)
    transient = [
        "Advisory observation mismatch: x",
        "6/8 tasks have no executor update",
        "4/6 sense checks have no executor acknowledgment",
    ]
    hard = [f"hard deviation {i}" for i in range(12)]
    # Prior attempt at index 1 carries transient + 12 hard deviations.
    _write_artifact(
        tmp_path,
        1,
        task_ids,
        deviations=transient + hard[:12],
        task_updates=[_rejected_update("T1"), _rejected_update("T2")],
        scope_digest=digest,
    )
    # A same-path retry in the CURRENT numeric slot preserves the prior attempt's
    # payload (checkpoint prep keeps it before prompt rendering); the scan must
    # include the current slot, so this retry's repeated deviations surface too.
    _write_artifact(
        tmp_path,
        2,
        task_ids,
        deviations=[hard[6], hard[6], hard[7]],
        task_updates=[_rejected_update("T1"), _rejected_update("T2")],
        scope_digest=digest,
    )
    deviations = _prior_execute_batch_deviations(
        tmp_path,
        task_ids,
        prompt_batch_number=2,
        current_artifact_number=2,
    )
    # Transient gone; duplicates last-occurrence (hard 6 re-appended at the
    # tail); cap 10; deterministic order.
    assert all("Advisory" not in d and "no executor" not in d for d in deviations)
    assert len(deviations) == 10
    assert deviations[-1] == hard[7]
    assert deviations.count(hard[6]) == 1
    # Two renders are byte-identical.
    again = _prior_execute_batch_deviations(
        tmp_path,
        task_ids,
        prompt_batch_number=2,
        current_artifact_number=2,
    )
    assert again == deviations


def test_legacy_artifact_participates_via_adjacent_compat_path(tmp_path: Path) -> None:
    task_ids = ["T1", "T2"]
    # Legacy flat artifact (no batch_scope): only reachable via the adjacent
    # compatibility path (prompt_batch_number - 1).
    legacy = tmp_path / "execution_batch_1.json"
    legacy.write_text(
        json.dumps({"deviations": [_BUDGET_DEVIATION]}), encoding="utf-8"
    )
    deviations = _prior_execute_batch_deviations(
        tmp_path,
        task_ids,
        prompt_batch_number=2,
        current_artifact_number=2,
    )
    assert deviations == [_BUDGET_DEVIATION]


def test_prompt_checkpoint_uses_dispatch_artifact_number(tmp_path: Path) -> None:
    task_ids = ["T1", "T2"]
    digest = stable_task_id_digest(task_ids)
    _write_artifact(
        tmp_path,
        3,
        task_ids,
        deviations=[_BUDGET_DEVIATION],
        task_updates=[_rejected_update("T1"), _rejected_update("T2")],
        scope_digest=digest,
    )
    (tmp_path / "finalize.json").write_text(
        json.dumps(_finalize_data(task_ids)), encoding="utf-8"
    )
    prompt = _execute_batch_prompt(
        _make_state(tmp_path),
        tmp_path,
        task_ids,
        current_artifact_number=7,
    )
    # The checkpoint path names the dispatch artifact number (batch_7), and the
    # prior deviation is visible to the executor.
    assert "batch_7" in prompt
    assert "task_test_budget_exhausted" in prompt
    assert _BUDGET_DEVIATION.split(": ")[0] in prompt