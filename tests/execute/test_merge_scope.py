from __future__ import annotations

import argparse
import json
from pathlib import Path

from arnold_pipelines.megaplan._core import execute_batch_artifact_path
from arnold_pipelines.megaplan.authority.batch_scope import (
    BATCH_SCOPE_KEY,
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
    BatchScope,
)
from arnold_pipelines.megaplan.authority.binding import (
    DispatchIdentity,
    ResultEnvelope,
    TASK_COMPLETION_CLAIM,
    TASK_RESULT_CAPABILITY,
    TaskAttempt,
    TaskClaim,
)
from arnold_pipelines.megaplan.execute import batch as batch_module
from arnold_pipelines.megaplan.execute.merge import (
    _merge_batch_results,
    reconcile_latest_execution_batch,
)
from arnold_pipelines.run_authority import EvidenceEnvelope
from arnold_pipelines.megaplan.workers._impl import WorkerResult


def test_code_execute_rejects_off_batch_task_updates() -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T2",
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
            },
            {
                "id": "T7",
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
            },
        ],
        "sense_checks": [
            {"id": "SC2", "task_id": "T2", "executor_note": ""},
            {"id": "SC7", "task_id": "T7", "executor_note": ""},
        ],
    }
    issues: list[str] = []

    merged_count, total_tasks, _ack_count, _total_checks = _merge_batch_results(
        finalize_data=finalize_data,
        payload={
            "task_updates": [
                {
                    "task_id": "T7",
                    "status": "done",
                    "executor_notes": "completed unrelated task",
                    "files_changed": ["src/unrelated.py"],
                    "commands_run": [],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC7", "executor_note": "off-batch check"}
            ],
        },
        batch_task_ids=["T2"],
        batch_sense_check_ids=["SC2"],
        issues=issues,
        mode="code",
    )

    tasks_by_id = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged_count == 0
    assert total_tasks == 1
    assert tasks_by_id["T2"]["status"] == "pending"
    assert tasks_by_id["T7"]["status"] == "pending"
    checks_by_id = {check["id"]: check for check in finalize_data["sense_checks"]}
    assert checks_by_id["SC2"]["executor_note"] == ""
    assert checks_by_id["SC7"]["executor_note"] == ""
    assert any("unknown task_id 'T7'" in issue for issue in issues)
    assert any("unknown sense_check_id 'SC7'" in issue for issue in issues)
    assert any("1/1 batch tasks have no executor update" in issue for issue in issues)


def test_creative_execute_rejects_off_batch_tasks_and_sense_checks() -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "pending", "executor_notes": "", "sections_written": []},
            {"id": "T9", "status": "pending", "executor_notes": "", "sections_written": []},
        ],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "executor_note": ""},
            {"id": "SC9", "task_id": "T9", "executor_note": ""},
        ],
    }
    stance = {
        "challenge_engaged": "I engaged the challenge directly.",
        "angle_taken": "I chose a narrow image.",
        "what_changed": "I removed the summary.",
    }
    issues: list[str] = []
    task_update = {
        "task_id": "T9",
        "status": "done",
        "executor_notes": "wrote an undispatched section",
        "sections_written": ["off_scope"],
        "stance": stance,
        "stop_signal": {"requested": False, "defense": ""},
    }
    sense_check_ack = {
        "sense_check_id": "SC9",
        "executor_note": "off-scope acknowledgment",
    }

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload={
            "task_updates": [task_update],
            "sense_check_acknowledgments": [sense_check_ack],
        },
        batch_task_ids=["T1"],
        batch_sense_check_ids=["SC1"],
        issues=issues,
        mode="creative",
    )

    assert merged == (0, 1, 0, 1)
    assert finalize_data["tasks"][1]["status"] == "pending"
    assert finalize_data["sense_checks"][1]["executor_note"] == ""
    # Keep the assertion local to the payload shape above: creative cross-task
    # rows are now refused by the validator instead of falling through as
    # ordinary unknown merge targets.
    assert task_update["authority_validation"]["outcome"] == "quarantined"
    assert task_update["authority_validation"]["reason"] == "subject_outside_dispatched_batch"
    assert sense_check_ack["authority_validation"]["outcome"] == "quarantined"
    assert any("Grant-aware validation quarantined task_update[0]" in issue for issue in issues)
    assert any("Grant-aware validation quarantined sense_check_acknowledgment[0]" in issue for issue in issues)


def _finalize_payload() -> dict[str, object]:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": "First task",
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
            },
            {
                "id": "T2",
                "description": "Second task",
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
            },
        ],
        "sense_checks": [
            {
                "id": "SC1",
                "task_id": "T1",
                "question": "Was T1 handled?",
                "executor_note": "",
            },
            {
                "id": "SC2",
                "task_id": "T2",
                "question": "Was T2 handled?",
                "executor_note": "",
            },
        ],
    }


def _task_envelope(
    entry: dict[str, object],
    *,
    subject_id: str = "T1",
    run_revision: str = "revision-1",
    dispatch_id: str = "dispatch-1",
    prerequisite_digest: str = "prereq-1",
    worker_id: str = "worker-1",
    ordinal: int = 1,
) -> ResultEnvelope:
    dispatch = DispatchIdentity.create(
        dispatch_id=dispatch_id,
        run_id="run-1",
        run_revision=run_revision,
        coordinator_attempt_id="coordinator-1",
        fence_token=3,
        subject_ids=(subject_id,),
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest=prerequisite_digest,
        worker_id=worker_id,
    )
    base_id = f"{dispatch_id}:task:{subject_id}:{ordinal}"
    evidence = EvidenceEnvelope(
        evidence_id=f"{base_id}:evidence",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        evidence_type="megaplan.task_update",
        source="test",
        payload={"entry": entry},
    )
    attempt = TaskAttempt(
        attempt_id=f"{base_id}:attempt",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        subject_id=subject_id,
        grant_id=dispatch.dispatch_id,
        coordinator_attempt_id=dispatch.coordinator_attempt_id,
        fence_token=dispatch.fence_token,
        ordinal=ordinal,
    )
    claim = TaskClaim(
        claim_id=f"{base_id}:claim",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        subject_id=subject_id,
        attempt_id=attempt.attempt_id,
        grant_id=dispatch.dispatch_id,
        coordinator_attempt_id=dispatch.coordinator_attempt_id,
        fence_token=dispatch.fence_token,
        claim_type=TASK_COMPLETION_CLAIM,
        evidence_ids=(evidence.evidence_id,),
        idempotency_key=f"{dispatch_id}:task:{subject_id}:claim",
        payload={"entry": entry},
    )
    return ResultEnvelope(
        dispatch=dispatch,
        attempt=attempt,
        claim=claim,
        evidence=(evidence,),
    )


def _payload_with_task_envelopes(
    entries: list[dict[str, object]],
    envelopes: list[ResultEnvelope],
) -> dict[str, object]:
    for entry, envelope in zip(entries, envelopes, strict=True):
        entry["authority"] = {
            "envelope_digest": envelope.digest(),
            "dispatch_id": envelope.dispatch_id,
            "run_revision": envelope.run_revision,
            "plan_revision": envelope.plan_revision,
            "fence": envelope.dispatch.fence.to_dict(),
            "scope": {
                "subject_ids": list(envelope.dispatch.subject_ids),
                "capabilities": list(envelope.dispatch.capabilities),
            },
            "prerequisite_digest": envelope.prerequisite_digest,
            "worker_id": envelope.worker_id,
            "attempt": envelope.attempt.to_dict(),
        }
    return {
        DISPATCH_IDENTITY_KEY: envelopes[0].dispatch.to_dict(),
        RESULT_ENVELOPES_KEY: [envelope.to_dict() for envelope in envelopes],
        "task_updates": entries,
        "sense_check_acknowledgments": [],
    }


def test_grant_aware_merge_accepts_enveloped_task_update() -> None:
    finalize_data = _finalize_payload()
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "validated through dispatch envelope",
        "files_changed": [],
        "commands_run": ["pytest tests/execute/test_merge_scope.py"],
    }
    envelope = _task_envelope(entry)
    issues: list[str] = []

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload=_payload_with_task_envelopes([entry], [envelope]),
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        issues=issues,
        mode="code",
        state={
            "run_revision": "revision-1",
            "coordinator_attempt_id": "coordinator-1",
            "fence_token": 3,
            "prerequisite_digest": "prereq-1",
            "worker_id": "worker-1",
        },
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged == (1, 1, 0, 0)
    assert tasks["T1"]["status"] == "done"
    assert entry["authority_validation"]["outcome"] == "accepted"
    assert not any("Grant-aware validation" in issue for issue in issues)


def test_doc_merge_keeps_sections_validation_after_authority_acceptance() -> None:
    finalize_data = _finalize_payload()
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "drafted the requested section",
        "sections_written": ["overview"],
    }
    envelope = _task_envelope(entry)
    issues: list[str] = []

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload=_payload_with_task_envelopes([entry], [envelope]),
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        issues=issues,
        mode="doc",
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged == (1, 1, 0, 0)
    assert tasks["T1"]["status"] == "done"
    assert tasks["T1"]["sections_written"] == ["overview"]
    assert entry["authority_validation"]["outcome"] == "accepted"
    assert not any("Skipped malformed task_updates" in issue for issue in issues)


def test_doc_merge_rejects_missing_sections_after_authority_acceptance() -> None:
    finalize_data = _finalize_payload()
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "missing prose field",
    }
    envelope = _task_envelope(entry)
    issues: list[str] = []

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload=_payload_with_task_envelopes([entry], [envelope]),
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        issues=issues,
        mode="doc",
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged == (0, 1, 0, 0)
    assert tasks["T1"]["status"] == "pending"
    assert entry["authority_validation"]["outcome"] == "accepted"
    assert any("Skipped malformed task_updates[0]" in issue for issue in issues)


def test_creative_merge_keeps_stance_validation_after_authority_acceptance() -> None:
    finalize_data = _finalize_payload()
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "revised the scene",
        "sections_written": ["scene"],
        "stance": {
            "challenge_engaged": "The challenge was considered.",
            "angle_taken": "A distant angle was used.",
            "what_changed": "The summary remained.",
        },
        "stop_signal": {"requested": False, "defense": ""},
    }
    envelope = _task_envelope(entry)
    issues: list[str] = []

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload=_payload_with_task_envelopes([entry], [envelope]),
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        issues=issues,
        mode="creative",
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged == (1, 1, 0, 0)
    assert tasks["T1"]["status"] == "done"
    assert "stance_violations" in tasks["T1"]
    assert "stance must use first person" in tasks["T1"]["stance_violations"]
    assert entry["authority_validation"]["outcome"] == "accepted"


def test_normal_execute_batch_stamps_authority_before_merge(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    finalize_data = _finalize_payload()
    state = {
        "name": "run-1",
        "config": {"mode": "code", "project_dir": str(project_dir)},
        "meta": {},
        "iteration": 3,
        "plan_versions": [{"hash": "revision-1"}],
        "active_step": {"run_id": "coordinator-1", "attempt": 3},
    }
    worker = WorkerResult(
        payload={
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "normal worker result",
                    "files_changed": [],
                    "commands_run": [],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "validated"}
            ],
        },
        raw_output="",
        duration_ms=1,
        cost_usd=0.0,
    )

    monkeypatch.setattr(
        batch_module.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "default", False),
    )
    monkeypatch.setattr(batch_module, "maybe_run_channel_shadow", lambda **kwargs: None)
    monkeypatch.setattr(
        batch_module,
        "_render_execute_prompt_for_dispatch",
        lambda **kwargs: kwargs.get("prompt_override"),
    )
    monkeypatch.setattr(batch_module, "_collect_quality_deviations", lambda **kwargs: [])
    monkeypatch.setattr(
        batch_module,
        "_auto_attribute_unclaimed_paths",
        lambda **kwargs: batch_module.AttributionResult(
            records=[], recursive_snapshot=None
        ),
    )
    monkeypatch.setattr(batch_module, "_observe_git_changes", lambda **kwargs: [])
    monkeypatch.setattr(batch_module, "_pre_existing_task_ids", lambda plan_dir: set())
    monkeypatch.setattr(
        batch_module,
        "_check_done_task_evidence_by_kind",
        lambda tasks, **kwargs: [],
    )
    monkeypatch.setattr(
        batch_module,
        "validate_execution_evidence",
        lambda *args, **kwargs: {"skipped": False, "findings": []},
    )
    monkeypatch.setattr(batch_module, "project_advisory_path_sets", lambda *args, **kwargs: None)

    result = batch_module._run_and_merge_batch(
        root=project_dir,
        plan_dir=plan_dir,
        state=state,
        args=argparse.Namespace(),
        agent="codex",
        mode="default",
        refreshed=False,
        prompt_override="execute prompt",
        batch_task_ids=["T1"],
        batch_sense_check_ids=["SC1"],
        finalize_data=finalize_data,
        batch_number=1,
        batches_total=1,
        quality_config={},
        capture_git_status_snapshot_fn=lambda path: ({}, None),
    )

    artifact_path = execute_batch_artifact_path(plan_dir, 1, ["T1"])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    task_validation = artifact["task_updates"][0]["authority_validation"]
    check_validation = artifact["sense_check_acknowledgments"][0][
        "authority_validation"
    ]
    assert result.merged_task_count == 1
    assert result.acknowledged_sense_check_count == 1
    assert task_validation["outcome"] == "accepted"
    assert task_validation["reason"] == "task_update_authority_valid"
    assert task_validation["source_path"] == str(artifact_path)
    assert check_validation["outcome"] == "accepted"
    assert check_validation["reason"] == "sense_check_acknowledgment_authority_valid"
    assert finalize_data["tasks"][0]["status"] == "done"
    assert artifact[DISPATCH_IDENTITY_KEY]["grant"]["grant_id"].endswith(
        ":execute:batch:1:1f93603db53b"
    )
    assert artifact[RESULT_ENVELOPES_KEY]


def test_review_rework_creative_batch_quarantines_cross_task_update(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "description": "Scoped creative rework",
                "status": "pending",
                "executor_notes": "",
                "sections_written": [],
            },
            {
                "id": "T9",
                "description": "Unrelated creative task",
                "status": "pending",
                "executor_notes": "",
                "sections_written": [],
            },
        ],
        "sense_checks": [],
    }
    valid_stance = {
        "challenge_engaged": "I chose the harder image.",
        "angle_taken": "I picked a close angle.",
        "what_changed": "I killed the summary.",
    }
    worker = WorkerResult(
        payload={
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "handled scoped rework",
                    "sections_written": ["allowed"],
                    "stance": valid_stance,
                    "stop_signal": {"requested": False, "defense": ""},
                },
                {
                    "task_id": "T9",
                    "status": "done",
                    "executor_notes": "tried to handle unrelated rework",
                    "sections_written": ["cross_task"],
                    "stance": valid_stance,
                    "stop_signal": {"requested": False, "defense": ""},
                },
            ],
            "sense_check_acknowledgments": [],
        },
        raw_output="",
        duration_ms=1,
        cost_usd=0.0,
    )
    state = {
        "name": "run-1",
        "config": {"mode": "creative", "project_dir": str(project_dir)},
        "meta": {},
        "iteration": 3,
        "plan_versions": [{"hash": "revision-1"}],
        "active_step": {"run_id": "coordinator-1", "attempt": 3},
    }

    monkeypatch.setattr(
        batch_module.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "default", False),
    )
    monkeypatch.setattr(batch_module, "maybe_run_channel_shadow", lambda **kwargs: None)
    monkeypatch.setattr(
        batch_module,
        "_render_execute_prompt_for_dispatch",
        lambda **kwargs: kwargs.get("prompt_override"),
    )
    monkeypatch.setattr(batch_module, "_pre_existing_task_ids", lambda plan_dir: set())
    monkeypatch.setattr(
        batch_module,
        "validate_execution_evidence",
        lambda *args, **kwargs: {"skipped": False, "findings": []},
    )

    result = batch_module._run_and_merge_batch(
        root=project_dir,
        plan_dir=plan_dir,
        state=state,
        args=argparse.Namespace(),
        agent="codex",
        mode="default",
        refreshed=False,
        prompt_override="execute prompt",
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        finalize_data=finalize_data,
        batch_number=1,
        batches_total=1,
        quality_config={},
        capture_git_status_snapshot_fn=lambda path: ({}, None),
    )

    artifact_path = execute_batch_artifact_path(plan_dir, 1, ["T1"])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    accepted, quarantined = artifact["task_updates"]
    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert result.merged_task_count == 1
    assert tasks["T1"]["status"] == "done"
    assert tasks["T9"]["status"] == "pending"
    assert accepted["authority_validation"]["outcome"] == "accepted"
    assert quarantined["authority_validation"]["outcome"] == "quarantined"
    assert quarantined["authority_validation"]["reason"] == "subject_outside_dispatched_batch"
    assert "authority_generation_error" in quarantined


def test_grant_aware_merge_rejects_stale_revision_before_mutation() -> None:
    finalize_data = _finalize_payload()
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "stale result",
        "files_changed": [],
        "commands_run": [],
    }
    envelope = _task_envelope(entry, run_revision="old-revision")
    issues: list[str] = []

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload=_payload_with_task_envelopes([entry], [envelope]),
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        issues=issues,
        mode="code",
        state={"run_revision": "current-revision"},
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged == (0, 1, 0, 0)
    assert tasks["T1"]["status"] == "pending"
    assert entry["authority_validation"]["outcome"] == "superseded-or-conflicting"
    assert any("plan_revision_mismatch" in issue for issue in issues)


def test_grant_aware_merge_reports_malformed_authority_source_path() -> None:
    finalize_data = _finalize_payload()
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "malformed authority",
        "files_changed": [],
        "commands_run": [],
    }
    source_path = "/tmp/plan/execute_batches/batch_1/tasks_1f93603db53b.json"
    issues: list[str] = []

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload={
            DISPATCH_IDENTITY_KEY: "not an object",
            RESULT_ENVELOPES_KEY: [],
            "task_updates": [entry],
            "sense_check_acknowledgments": [],
        },
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        issues=issues,
        mode="code",
        source_path=source_path,
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged == (0, 1, 0, 0)
    assert tasks["T1"]["status"] == "pending"
    assert any("malformed_dispatch_identity" in issue for issue in issues)
    assert any(source_path in issue for issue in issues)


def test_grant_aware_merge_ignores_duplicate_idempotent_result() -> None:
    finalize_data = _finalize_payload()
    first = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "first accepted result",
        "files_changed": [],
        "commands_run": [],
    }
    duplicate = dict(first)
    first_envelope = _task_envelope(first, ordinal=1)
    duplicate_envelope = _task_envelope(duplicate, ordinal=1)
    issues: list[str] = []

    merged = _merge_batch_results(
        finalize_data=finalize_data,
        payload=_payload_with_task_envelopes(
            [first, duplicate],
            [first_envelope, duplicate_envelope],
        ),
        batch_task_ids=["T1"],
        batch_sense_check_ids=[],
        issues=issues,
        mode="code",
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert merged == (1, 1, 0, 0)
    assert tasks["T1"]["executor_notes"] == "first accepted result"
    assert first["authority_validation"]["outcome"] == "accepted"
    assert duplicate["authority_validation"]["outcome"] == "duplicate-idempotent"
    assert any("duplicate-idempotent" in issue for issue in issues)


def test_reconcile_uses_selected_artifacts_proven_scope(tmp_path: Path) -> None:
    finalize_data = _finalize_payload()
    (tmp_path / "finalize.json").write_text(json.dumps(finalize_data), encoding="utf-8")
    scope = BatchScope.create(batch_number=2, task_ids=["T2"], sense_check_ids=["SC2"])
    artifact = execute_batch_artifact_path(tmp_path, 2, scope.task_ids)
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                BATCH_SCOPE_KEY: scope.to_dict(),
                "task_updates": [
                    {"task_id": "T1", "status": "done", "executor_notes": "off scope", "files_changed": [], "commands_run": []},
                    {"task_id": "T2", "status": "done", "executor_notes": "proven", "files_changed": [], "commands_run": []},
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "off scope"},
                    {"sense_check_id": "SC2", "executor_note": "proven"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = reconcile_latest_execution_batch(tmp_path, {"config": {"mode": "code"}})

    saved = json.loads((tmp_path / "finalize.json").read_text(encoding="utf-8"))
    tasks = {task["id"]: task for task in saved["tasks"]}
    checks = {check["id"]: check for check in saved["sense_checks"]}
    assert result["reconciled"] is True
    assert result["total_task_count"] == 1
    assert result["total_sense_check_count"] == 1
    assert tasks["T1"]["status"] == "pending"
    assert tasks["T2"]["status"] == "done"
    assert checks["SC1"]["executor_note"] == ""
    assert checks["SC2"]["executor_note"] == "proven"


def test_reconcile_routes_off_scope_enveloped_rows_to_validator(tmp_path: Path) -> None:
    finalize_data = _finalize_payload()
    (tmp_path / "finalize.json").write_text(json.dumps(finalize_data), encoding="utf-8")
    scope = BatchScope.create(batch_number=2, task_ids=["T2"], sense_check_ids=[])
    artifact = execute_batch_artifact_path(tmp_path, 2, scope.task_ids)
    artifact.parent.mkdir(parents=True)
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "off-scope enveloped result",
        "files_changed": [],
        "commands_run": [],
    }
    envelope = _task_envelope(entry, subject_id="T1")
    payload = _payload_with_task_envelopes([entry], [envelope])
    payload[BATCH_SCOPE_KEY] = scope.to_dict()
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    result = reconcile_latest_execution_batch(tmp_path, {"config": {"mode": "code"}})

    saved = json.loads((tmp_path / "finalize.json").read_text(encoding="utf-8"))
    tasks = {task["id"]: task for task in saved["tasks"]}
    assert result["reconciled"] is True
    assert result["merged_task_count"] == 0
    assert tasks["T1"]["status"] == "pending"
    assert tasks["T2"]["status"] == "pending"
    assert any("Grant-aware validation rejected" in issue for issue in result["issues"])
    assert any("subject_outside_dispatched_batch" in issue for issue in result["issues"])


def test_reconcile_quarantines_legacy_artifact_with_source_path(tmp_path: Path) -> None:
    finalize_data = _finalize_payload()
    finalize_path = tmp_path / "finalize.json"
    original = json.dumps(finalize_data)
    finalize_path.write_text(original, encoding="utf-8")
    artifact = tmp_path / "execution_batch_1.json"
    artifact.write_text(
        json.dumps(
            {
                "task_updates": [
                    {"task_id": "T1", "status": "done", "executor_notes": "legacy", "files_changed": [], "commands_run": []}
                ]
            }
        ),
        encoding="utf-8",
    )

    result = reconcile_latest_execution_batch(tmp_path, {"config": {"mode": "code"}})

    assert result["reconciled"] is False
    assert result["authority_status"] == "quarantined"
    assert result["artifact_path"] == str(artifact)
    assert result["quarantine"]["reason"] == "missing_batch_scope"
    assert result["quarantine"]["source_path"] == str(artifact)
    assert json.loads(finalize_path.read_text(encoding="utf-8")) == finalize_data
    events = (tmp_path / "events.ndjson").read_text(encoding="utf-8")
    assert "authority_divergence" in events
    assert str(artifact) in events
