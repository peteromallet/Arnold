"""Regression: aggregate checkpoint adoption for shadowed same-index waves.

Occurrence 0ae19cc17afd (megaplan-maintenance, plan
m3b-custody-bound-repair-20260817-1428): the execute aggregate auto-loop
collapses each batch index to the *preferred* attempt
(``list_batch_artifacts``), so an accepted T1/T2+SC1/SC2 wave in
``execute_batches/batch_1/tasks_<digest>.json`` can be shadowed by a
same-index newer wave.  The quality gate then sees T1/T2 as done-but-hollow
("done tasks missing both files_changed and commands_run") and SC1/SC2 as
unacknowledged ("N/M sense checks have no executor acknowledgment") and parks
the phase with ``blocked_by_quality`` even though the accepted authority
evidence exists on disk.

The fix makes ``handle_execute_auto_loop`` replay every independently proven
batch artifact (including shadowed same-index waves) through the scoped merge
validator BEFORE the authoritative aggregate/quality checks, so accepted rows
backfill evidence and acknowledgments.  The replay is validator-gated and
idempotent: authority IDs persist only on pass, nothing is laundered, and a
resume never redoes accepted work nor skips genuinely failed work.
"""

from __future__ import annotations

import argparse
import json
import os
import types as _types
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.authority.binding import DispatchIdentity
from arnold_pipelines.megaplan.execute.batch import (
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
    handle_execute_auto_loop,
    _prepare_scoped_batch_checkpoint,
    _stamp_result_envelopes,
)


def _finalize(tasks: list[dict]) -> dict:
    return {
        "tasks": tasks,
        "sense_checks": [],
        "baseline_test_failures": None,
        "user_actions": [],
    }


def _task(tid: str, status: str, **extra) -> dict:
    row = {
        "id": tid,
        "status": status,
        "depends_on": [],
        "description": f"task {tid}",
        "executor_notes": "",
    }
    row.update(extra)
    return row


def _state(tmp_path: Path) -> dict:
    return {
        "name": "megaplan-run",
        "created_at": "2026-07-10T00:00:00Z",
        "current_state": "finalized",
        "iteration": 1,
        "config": {
            "mode": "code",
            "project_dir": str(tmp_path),
            "max_tasks_per_batch": 2,
        },
        "sessions": {},
        "history": [],
        "meta": {},
        "plan_versions": [{"hash": "sha256:plan-revision"}],
        "active_step": {"run_id": "coordinator-attempt", "attempt": 4},
    }


def _write_wave(
    tmp_path: Path,
    *,
    task_ids: list[str],
    sense_check_ids: list[str],
    state: dict,
    finalize_data: dict,
    task_updates: list[dict],
    acks: list[dict],
    mtime: float,
    drop_envelopes: bool = False,
) -> Path:
    """Create a scoped, dispatch-stamped artifact with accepted rows.

    Mirrors the ``test_authority_batch_scope.py`` fixture pattern: real
    scoped claims/capabilities via ``_prepare_scoped_batch_checkpoint`` +
    ``_stamp_result_envelopes``, not fabricated ``authority_validation``.
    With ``drop_envelopes=True`` the artifact keeps its scoped rows but has
    NO persisted result envelopes, so the grant-aware validator refuses it
    (``missing_result_envelopes``) instead of adopting anything.
    """
    path = _prepare_scoped_batch_checkpoint(
        tmp_path,
        batch_number=1,
        task_ids=task_ids,
        sense_check_ids=sense_check_ids,
        state=state,
        finalize_data=finalize_data,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    identity = DispatchIdentity.from_dict(payload[DISPATCH_IDENTITY_KEY])
    payload["task_updates"] = task_updates
    payload["sense_check_acknowledgments"] = acks
    _stamp_result_envelopes(payload, identity=identity, artifact_path=path)
    if drop_envelopes:
        payload.pop(RESULT_ENVELOPES_KEY, None)
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def _accepted_update(tid: str, files: list[str], commands: list[str]) -> dict:
    return {
        "task_id": tid,
        "status": "done",
        "files_changed": files,
        "commands_run": commands,
        "authority_validation": {
            "outcome": "accepted",
            "reason": "task_update_authority_valid",
        },
    }


def _accepted_ack(sc_id: str, note: str) -> dict:
    return {
        "sense_check_id": sc_id,
        "executor_note": note,
        "authority_validation": {
            "outcome": "accepted",
            "reason": "sense_check_acknowledgment_authority_valid",
        },
    }


def _runner(monkeypatch: pytest.MonkeyPatch, calls: list[list[str]]):
    """Fake worker that completes the dispatched batch with full evidence.

    Mirrors the real ``_run_and_merge_batch``: the merged finalize rows are
    written back AND a scoped dispatch artifact with result envelopes is
    persisted, so the authority reader / completed-set computation sees the
    batch as accepted (otherwise the tracked-task count stays zero).
    """

    def _fake_run_and_merge_batch(**kwargs):
        fin = kwargs["finalize_data"]
        batch_ids = list(kwargs["batch_task_ids"])
        calls.append(batch_ids)
        updates: list[dict] = []
        for task in fin.get("tasks", []):
            if isinstance(task, dict) and task.get("id") in set(batch_ids):
                task["status"] = "done"
                task["files_changed"] = [f"{task['id']}.py"]
                task["commands_run"] = [f"pytest {task['id']}.py"]
                updates.append(
                    {
                        "task_id": task["id"],
                        "status": "done",
                        "files_changed": task["files_changed"],
                        "commands_run": task["commands_run"],
                        "authority_validation": {
                            "outcome": "accepted",
                            "reason": "task_update_authority_valid",
                        },
                    }
                )
        path = _prepare_scoped_batch_checkpoint(
            kwargs["plan_dir"],
            batch_number=kwargs.get("batch_number", 1),
            task_ids=batch_ids,
            sense_check_ids=kwargs.get("batch_sense_check_ids", []),
            state=kwargs["state"],
            finalize_data=fin,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        identity = DispatchIdentity.from_dict(payload[DISPATCH_IDENTITY_KEY])
        payload["task_updates"] = updates
        # Faithful to _run_and_merge_batch: the artifact is rebuilt from THIS
        # run's worker response, so sense-check acknowledgments from a prior
        # (possibly unproven) attempt at the same digest path must NOT survive.
        # The real engine does payload = _capture_execute_payload(dict(worker.payload)).
        payload["sense_check_acknowledgments"] = [
            {
                "sense_check_id": sc_id,
                "executor_note": f"{sc_id} reworked note",
                "authority_validation": {
                    "outcome": "accepted",
                    "reason": "sense_check_acknowledgment_authority_valid",
                },
            }
            for sc_id in kwargs.get("batch_sense_check_ids", [])
        ]
        _stamp_result_envelopes(payload, identity=identity, artifact_path=path)
        path.write_text(json.dumps(payload), encoding="utf-8")
        worker = _types.SimpleNamespace(
            duration_ms=0,
            cost_usd=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            rate_limit=None,
            session_id=None,
            model_actual=None,
            worker_channel=None,
            auth_channel=None,
            auth_metadata=None,
            rendered_prompt=None,
            trace_output=None,
        )
        return _types.SimpleNamespace(
            worker=worker,
            agent=kwargs.get("agent", "shadow"),
            mode=kwargs.get("mode", "code"),
            refreshed=kwargs.get("refreshed", False),
            payload={"task_updates": [], "sense_check_acknowledgments": []},
            batch_number=kwargs.get("batch_number", 1),
            batch_task_ids=batch_ids,
            batch_sense_check_ids=kwargs.get("batch_sense_check_ids", []),
            merged_task_count=len(batch_ids),
            total_task_count=len(batch_ids),
            acknowledged_sense_check_count=0,
            total_sense_check_count=0,
            missing_task_evidence=[],
            execution_audit={},
            finalize_hash="",
            attribution_records=[],
            routing_degradations=[],
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._guard_execute_batch_admission",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._run_and_merge_batch",
        _fake_run_and_merge_batch,
    )


def _run_loop(tmp_path: Path, state: dict):
    return handle_execute_auto_loop(
        root=tmp_path,
        plan_dir=tmp_path,
        state=state,
        args=argparse.Namespace(),
        auto_approve=False,
        agent="shadow",
        mode="code",
        refreshed=False,
    )


def _read_finalize(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "finalize.json").read_text(encoding="utf-8"))


def test_shadowed_checkpoint_acks_unblock_aggregate_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accepted T1/T2 evidence + SC1/SC2 notes in a shadowed wave unblock.

    T1/T2 are done-but-hollow, SC1/SC2 unacknowledged, T3/T4 pending.  The
    preferred batch_1 attempt is the newer T3/T4 wave, so without the replay
    the aggregate gate would see T1/T2 hollow + SC1/SC2 unacked and park
    ``blocked_by_quality``.  The unconditional replay backfills the shadowed
    accepted wave first.
    """
    finalize_data = _finalize(
        [
            _task("T1", "done"),
            _task("T2", "done"),
            _task("T3", "pending"),
            _task("T4", "pending"),
        ]
    )
    finalize_data["sense_checks"] = [
        {
            "id": "SC1",
            "task_id": "T1",
            "question": "does T1 satisfy its acceptance criteria?",
            "status": "pending",
        },
        {
            "id": "SC2",
            "task_id": "T2",
            "question": "does T2 satisfy its acceptance criteria?",
            "status": "pending",
        },
    ]
    (tmp_path / "finalize.json").write_text(
        json.dumps(finalize_data), encoding="utf-8"
    )
    state = _state(tmp_path)

    # Shadowed wave (older mtime): accepted T1/T2 evidence + SC1/SC2 notes.
    _write_wave(
        tmp_path,
        task_ids=["T1", "T2"],
        sense_check_ids=["SC1", "SC2"],
        state=state,
        finalize_data=finalize_data,
        task_updates=[
            _accepted_update("T1", ["t1.py"], ["pytest t1.py"]),
            _accepted_update("T2", ["t2.py"], ["pytest t2.py"]),
        ],
        acks=[
            _accepted_ack("SC1", "sense check one proven"),
            _accepted_ack("SC2", "sense check two proven"),
        ],
        mtime=1_000_000.0,
    )
    # Preferred wave (newer mtime): T3/T4 pending — the aggregate collapses
    # batch_1 to this attempt, shadowing the accepted wave above.
    _write_wave(
        tmp_path,
        task_ids=["T3", "T4"],
        sense_check_ids=[],
        state=state,
        finalize_data=finalize_data,
        task_updates=[],
        acks=[],
        mtime=2_000_000.0,
    )

    calls: list[list[str]] = []
    _runner(monkeypatch, calls)

    response = _run_loop(tmp_path, state)

    # Only the pending frontier is dispatched; T1/T2 accepted rows are NOT
    # re-dispatched.
    assert calls == [["T3", "T4"]]
    assert response["success"] is True
    assert response["_phase_outcome"] == "success"
    assert response["deviations"] == []
    assert not any(
        "no executor acknowledgment" in d or "missing both files_changed" in d
        for d in response.get("deviations", [])
    )
    # Canonical ledger: T1/T2 retain accepted files/commands; SC1/SC2 notes.
    finalize = _read_finalize(tmp_path)
    tasks = {t["id"]: t for t in finalize["tasks"]}
    assert tasks["T1"]["files_changed"] == ["t1.py"]
    assert tasks["T1"]["commands_run"] == ["pytest t1.py"]
    assert tasks["T2"]["files_changed"] == ["t2.py"]
    assert tasks["T2"]["commands_run"] == ["pytest t2.py"]
    checks = {c["id"]: c for c in finalize["sense_checks"]}
    assert checks["SC1"]["executor_note"] == "sense check one proven"
    assert checks["SC2"]["executor_note"] == "sense check two proven"


def test_laundered_artifact_still_blocks_and_authority_stays_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shadowed artifact without valid authority must NOT launder rows.

    All tasks are terminal-status (done) but the shadowed wave carries
    accepted-looking rows with NO persisted result envelopes, so the rows are
    NOT authoritative.  The engine's stale-authority retry resets the
    done-but-unproven tasks to pending, re-dispatches them, and the phase
    succeeds only with the re-dispatch's REAL evidence — laundered files and
    notes never reach the ledger.
    """
    finalize_data = _finalize(
        [
            _task("T1", "done"),
            _task("T2", "done"),
        ]
    )
    finalize_data["sense_checks"] = [
        {
            "id": "SC1",
            "task_id": "T1",
            "question": "does T1 satisfy its acceptance criteria?",
            "status": "pending",
        },
        {
            "id": "SC2",
            "task_id": "T2",
            "question": "does T2 satisfy its acceptance criteria?",
            "status": "pending",
        },
    ]
    (tmp_path / "finalize.json").write_text(
        json.dumps(finalize_data), encoding="utf-8"
    )
    state = _state(tmp_path)

    # Shadowed wave: scoped rows but NO persisted result envelopes — the
    # grant-aware validator refuses it (missing_result_envelopes), so nothing
    # can be laundered into the ledger.
    _write_wave(
        tmp_path,
        task_ids=["T1", "T2"],
        sense_check_ids=["SC1", "SC2"],
        state=state,
        finalize_data=finalize_data,
        task_updates=[
            _accepted_update("T1", ["laundered.py"], ["echo laundered"]),
            _accepted_update("T2", ["laundered2.py"], ["echo laundered2"]),
        ],
        acks=[
            _accepted_ack("SC1", "laundered note one"),
            _accepted_ack("SC2", "laundered note two"),
        ],
        mtime=1_000_000.0,
        drop_envelopes=True,
    )

    calls: list[list[str]] = []
    _runner(monkeypatch, calls)

    response = _run_loop(tmp_path, state)

    # Canonical current-engine contract (codex escalation1, 2026-08-18): the
    # envelope-less artifact is NOT adopted as authoritative.  The engine's
    # stale-authority retry resets T1/T2 (done-but-unproven) to pending and
    # re-dispatches them, so the phase succeeds with the re-dispatch's REAL
    # evidence — never with the laundered rows/notes.
    assert calls == [["T1", "T2"]]
    assert response["success"] is True
    # Nothing laundered into the canonical ledger: real rework evidence only.
    finalize = _read_finalize(tmp_path)
    tasks = {t["id"]: t for t in finalize["tasks"]}
    assert tasks["T1"]["files_changed"] == ["T1.py"]
    assert tasks["T2"]["files_changed"] == ["T2.py"]
    assert "laundered.py" not in (tasks["T1"].get("files_changed") or [])
    assert "laundered2.py" not in (tasks["T2"].get("files_changed") or [])
    checks = {c["id"]: c for c in finalize["sense_checks"]}
    assert checks["SC1"]["executor_note"] == "SC1 reworked note"
    assert checks["SC2"]["executor_note"] == "SC2 reworked note"
    assert "laundered note one" not in checks["SC1"].get("executor_note", "")
    assert "laundered note two" not in checks["SC2"].get("executor_note", "")


def test_resume_after_pass_does_not_redo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second resume against the same durable valid artifacts is a no-op.

    No T1/T2 re-dispatch, accepted status/evidence stable, notes/evidence not
    duplicated.
    """
    finalize_data = _finalize(
        [
            _task("T1", "done"),
            _task("T2", "done"),
            _task("T3", "done"),
        ]
    )
    finalize_data["sense_checks"] = [
        {
            "id": "SC1",
            "task_id": "T1",
            "question": "does T1 satisfy its acceptance criteria?",
            "status": "pending",
        },
    ]
    (tmp_path / "finalize.json").write_text(
        json.dumps(finalize_data), encoding="utf-8"
    )
    state = _state(tmp_path)

    _write_wave(
        tmp_path,
        task_ids=["T1", "T2"],
        sense_check_ids=["SC1"],
        state=state,
        finalize_data=finalize_data,
        task_updates=[
            _accepted_update("T1", ["t1.py"], ["pytest t1.py"]),
            _accepted_update("T2", ["t2.py"], ["pytest t2.py"]),
        ],
        acks=[_accepted_ack("SC1", "check proven")],
        mtime=1_000_000.0,
    )
    _write_wave(
        tmp_path,
        task_ids=["T3"],
        sense_check_ids=[],
        state=state,
        finalize_data=finalize_data,
        task_updates=[],
        acks=[],
        mtime=2_000_000.0,
    )

    calls: list[list[str]] = []
    _runner(monkeypatch, calls)

    first = _run_loop(tmp_path, state)
    assert first["success"] is True

    calls.clear()
    second = _run_loop(tmp_path, state)
    assert second["success"] is True
    # No re-dispatch of accepted work on the second resume.
    assert calls == []

    finalize = _read_finalize(tmp_path)
    tasks = {t["id"]: t for t in finalize["tasks"]}
    # Single occurrence of the accepted evidence — no duplication.
    assert tasks["T1"]["files_changed"] == ["t1.py"]
    assert tasks["T1"]["commands_run"] == ["pytest t1.py"]
    checks = {c["id"]: c for c in finalize["sense_checks"]}
    assert checks["SC1"]["executor_note"] == "check proven"


def test_resume_after_real_fail_does_not_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuinely blocked task stays blocked; the phase never reports success.

    T1 has a proven shadowed wave; T2 has NO accepted authority at all and
    the worker genuinely blocks it (real policy failure).  The replay must
    not mark T2 done (no authority to adopt), and the second resume must
    neither mark it done nor skip its required work.
    """
    finalize_data = _finalize(
        [
            _task("T1", "done"),
            _task("T2", "pending"),
        ]
    )
    (tmp_path / "finalize.json").write_text(
        json.dumps(finalize_data), encoding="utf-8"
    )
    state = _state(tmp_path)

    # Only T1 has a proven accepted wave (shadowed / non-preferred index).
    _write_wave(
        tmp_path,
        task_ids=["T1"],
        sense_check_ids=[],
        state=state,
        finalize_data=finalize_data,
        task_updates=[_accepted_update("T1", ["t1.py"], ["pytest t1.py"])],
        acks=[],
        mtime=1_000_000.0,
    )

    calls: list[list[str]] = []

    def _fake_run_and_merge_batch(**kwargs):
        # The worker genuinely fails T2: it reports blocked with a real note
        # and writes NO accepted artifact (no authority is ever minted).
        fin = kwargs["finalize_data"]
        batch_ids = list(kwargs["batch_task_ids"])
        calls.append(batch_ids)
        for task in fin.get("tasks", []):
            if isinstance(task, dict) and task.get("id") in set(batch_ids):
                task["status"] = "blocked"
                task["executor_notes"] = "[harness] real policy failure"
                task["blocked_reason"] = "task_test_budget_exhausted"
        worker = _types.SimpleNamespace(
            duration_ms=0,
            cost_usd=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            rate_limit=None,
            session_id=None,
            model_actual=None,
            worker_channel=None,
            auth_channel=None,
            auth_metadata=None,
            rendered_prompt=None,
            trace_output=None,
        )
        return _types.SimpleNamespace(
            worker=worker,
            agent=kwargs.get("agent", "shadow"),
            mode=kwargs.get("mode", "code"),
            refreshed=kwargs.get("refreshed", False),
            payload={"task_updates": [], "sense_check_acknowledgments": []},
            batch_number=kwargs.get("batch_number", 1),
            batch_task_ids=batch_ids,
            batch_sense_check_ids=kwargs.get("batch_sense_check_ids", []),
            merged_task_count=0,
            total_task_count=len(batch_ids),
            acknowledged_sense_check_count=0,
            total_sense_check_count=0,
            missing_task_evidence=[],
            execution_audit={},
            finalize_hash="",
            attribution_records=[],
            routing_degradations=[],
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._guard_execute_batch_admission",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._run_and_merge_batch",
        _fake_run_and_merge_batch,
    )

    first = _run_loop(tmp_path, state)
    assert first["success"] is False
    assert first["_phase_outcome"] == "blocked_by_quality"
    # T2's genuine block is surfaced, not laundered into completed work.
    assert "T2" in (first.get("blocked_task_ids") or [])

    # Second resume must not skip T2's required work and must not mark it
    # done: it is still genuinely blocked.  Canonical engine contract (codex
    # escalation1, 2026-08-18): on the no-pending aggregate path a genuinely
    # blocked task reports the task-level prerequisite outcome
    # (blocked_by_prereq), not blocked_by_quality.
    calls.clear()
    second = _run_loop(tmp_path, state)
    assert second["success"] is False
    assert second["_phase_outcome"] == "blocked_by_prereq"
    finalize = _read_finalize(tmp_path)
    tasks = {t["id"]: t for t in finalize["tasks"]}
    assert tasks["T2"]["status"] == "blocked"
    assert tasks["T1"]["status"] == "done"
