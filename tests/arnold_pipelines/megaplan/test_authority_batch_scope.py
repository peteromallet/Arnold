from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.authority.batch_scope import (
    BATCH_SCOPE_KEY,
    BatchScope,
    resolve_batch_authority_metadata,
    resolve_batch_scope,
)
from arnold_pipelines.megaplan.authority.binding import (
    DispatchIdentity,
    EvidenceEnvelope,
    ResultEnvelope,
    SENSE_CHECK_RESULT_CAPABILITY,
    TASK_COMPLETION_CLAIM,
    TASK_RESULT_CAPABILITY,
    TaskAttempt,
    TaskClaim,
)
from arnold_pipelines.megaplan.execute.batch import (
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
    _prepare_scoped_batch_checkpoint,
    _replay_proven_batch_artifacts,
    _stamp_result_envelopes,
)


KNOWN_TASKS = {"T1", "T2", "T3"}
KNOWN_CHECKS = {"SC1", "SC2"}


def _artifact(scope: BatchScope, *, payload: dict | None = None) -> tuple[dict, Path]:
    artifact_payload = dict(payload or {})
    artifact_payload[BATCH_SCOPE_KEY] = scope.to_dict()
    path = Path(
        f"/plan/execute_batches/batch_{scope.batch_number}/"
        f"tasks_{scope.task_set_digest}.json"
    )
    return artifact_payload, path


def _resolve(payload: dict, path: Path, *, expected: int | None = None):
    return resolve_batch_scope(
        payload,
        path,
        known_task_ids=KNOWN_TASKS,
        known_sense_check_ids=KNOWN_CHECKS,
        expected_batch_number=expected,
    )


def test_scope_creation_is_canonical_duplicate_insensitive_and_immutable() -> None:
    scope = BatchScope.create(
        batch_number=2,
        task_ids=["T3", "T1", "T3"],
        sense_check_ids=["SC2", "SC1", "SC2"],
    )

    assert scope.task_ids == ("T1", "T3")
    assert scope.sense_check_ids == ("SC1", "SC2")
    assert scope == BatchScope.create(
        batch_number=2,
        task_ids=["T1", "T3"],
        sense_check_ids=["SC1", "SC2"],
    )
    with pytest.raises(FrozenInstanceError):
        scope.batch_number = 3  # type: ignore[misc]


def test_resolver_proves_canonical_s4_scope() -> None:
    scope = BatchScope.create(
        batch_number=2, task_ids=["T2", "T1"], sense_check_ids=["SC1"]
    )
    payload, path = _artifact(scope)

    resolution = _resolve(payload, path, expected=2)

    assert resolution.is_proven
    assert resolution.scope == scope
    assert resolution.quarantine is None


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda data: data.update(batch_number=3), "batch_identity_mismatch"),
        (lambda data: data.update(task_set_digest="0" * 12), "scope_digest_mismatch"),
    ],
)
def test_resolver_quarantines_contradictory_embedded_identity(mutate, reason: str) -> None:
    scope = BatchScope.create(batch_number=2, task_ids=["T1"])
    payload, path = _artifact(scope)
    mutate(payload[BATCH_SCOPE_KEY])

    resolution = _resolve(payload, path, expected=2)

    assert not resolution.is_proven
    assert resolution.quarantine is not None
    assert resolution.quarantine.reason == reason
    assert resolution.quarantine.source_path == str(path)


def test_resolver_quarantines_path_index_and_filename_digest_mismatches() -> None:
    scope = BatchScope.create(batch_number=2, task_ids=["T1"])
    payload, path = _artifact(scope)

    wrong_index = _resolve(payload, path.parent.parent / "batch_3" / path.name)
    wrong_digest = _resolve(payload, path.with_name("tasks_000000000000.json"))

    assert wrong_index.quarantine is not None
    assert wrong_index.quarantine.reason == "batch_identity_mismatch"
    assert wrong_digest.quarantine is not None
    assert wrong_digest.quarantine.reason == "artifact_digest_mismatch"


def test_resolver_quarantines_duplicate_or_unsorted_persisted_subjects() -> None:
    scope = BatchScope.create(batch_number=1, task_ids=["T1", "T2"])
    payload, path = _artifact(scope)
    payload[BATCH_SCOPE_KEY]["task_ids"] = ["T2", "T1", "T1"]

    resolution = _resolve(payload, path)

    assert resolution.quarantine is not None
    assert resolution.quarantine.reason == "noncanonical_subject_ids"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_ids", ["T1", ""]),
        ("task_ids", [" T1"]),
        ("sense_check_ids", [17]),
    ],
)
def test_resolver_quarantines_malformed_subject_ids(field: str, value: list[object]) -> None:
    scope = BatchScope.create(batch_number=1, task_ids=["T1"])
    payload, path = _artifact(scope)
    payload[BATCH_SCOPE_KEY][field] = value

    resolution = _resolve(payload, path)

    assert resolution.quarantine is not None
    assert resolution.quarantine.reason == "malformed_subject_id"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("task_ids", ["T9"], "unknown_task_ids"),
        ("sense_check_ids", ["SC9"], "unknown_sense_check_ids"),
    ],
)
def test_resolver_quarantines_unknown_plan_subjects(
    field: str, value: list[str], reason: str
) -> None:
    scope = BatchScope.create(batch_number=1, task_ids=["T1"])
    payload, path = _artifact(scope)
    payload[BATCH_SCOPE_KEY][field] = value

    resolution = _resolve(payload, path)

    assert resolution.quarantine is not None
    assert resolution.quarantine.reason == reason
    assert resolution.quarantine.to_dict()[field] == value


def test_resolver_quarantines_missing_legacy_metadata_with_source_path() -> None:
    path = Path("/plan/execution_batch_4.json")

    resolution = _resolve({"task_updates": [{"task_id": "T1"}]}, path)

    assert resolution.quarantine is not None
    assert resolution.quarantine.to_dict() == {
        "reason": "missing_batch_scope",
        "message": "artifact has no versioned embedded batch scope",
        "source_path": str(path),
        "task_ids": [],
        "sense_check_ids": [],
    }


def test_resolver_does_not_accept_metadata_on_unprovable_legacy_path() -> None:
    scope = BatchScope.create(batch_number=1, task_ids=["T1"])
    payload, _ = _artifact(scope)

    resolution = _resolve(payload, Path("/plan/execution_batch_1.json"))

    assert resolution.quarantine is not None
    assert resolution.quarantine.reason == "invalid_artifact_path"


def test_resolver_quarantines_unknown_schema_without_repairing_it() -> None:
    scope = BatchScope.create(batch_number=1, task_ids=["T1"])
    payload, path = _artifact(scope)
    payload[BATCH_SCOPE_KEY]["schema_version"] = 2

    resolution = _resolve(payload, path)

    assert resolution.quarantine is not None
    assert resolution.quarantine.reason == "unsupported_schema_version"


def test_resolver_does_not_mutate_payload_or_known_subject_inputs() -> None:
    scope = BatchScope.create(batch_number=1, task_ids=["T1"])
    payload, path = _artifact(scope)
    original = {BATCH_SCOPE_KEY: scope.to_dict()}
    known_tasks = ["T1"]
    known_checks = ["SC1"]

    resolve_batch_scope(
        payload,
        path,
        known_task_ids=known_tasks,
        known_sense_check_ids=known_checks,
    )

    assert payload == original
    assert known_tasks == ["T1"]
    assert known_checks == ["SC1"]


def test_checkpoint_is_scope_stamped_before_worker_updates(tmp_path: Path) -> None:
    artifact_path = _prepare_scoped_batch_checkpoint(
        tmp_path,
        batch_number=2,
        task_ids=["T2", "T1"],
        sense_check_ids=["SC2", "SC1"],
    )

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    resolution = resolve_batch_scope(
        payload,
        artifact_path,
        known_task_ids=KNOWN_TASKS,
        known_sense_check_ids=KNOWN_CHECKS,
        expected_batch_number=2,
    )

    assert resolution.scope == BatchScope.create(
        batch_number=2,
        task_ids=["T1", "T2"],
        sense_check_ids=["SC1", "SC2"],
    )


def test_checkpoint_persists_dispatch_identity_separate_from_batch_scope(
    tmp_path: Path,
) -> None:
    state = {
        "name": "megaplan-run",
        "created_at": "2026-07-10T00:00:00Z",
        "current_state": "finalized",
        "iteration": 3,
        "config": {"mode": "code"},
        "sessions": {},
        "history": [],
        "meta": {},
        "plan_versions": [{"hash": "sha256:plan-revision"}],
        "active_step": {"run_id": "coordinator-attempt", "attempt": 2},
    }
    finalize_data = {
        "tasks": [
            {"id": "T1", "depends_on": []},
            {"id": "T2", "depends_on": ["T1"]},
        ],
        "sense_checks": [{"id": "SC1", "task_id": "T2"}],
        "user_actions": [],
    }

    artifact_path = _prepare_scoped_batch_checkpoint(
        tmp_path,
        batch_number=2,
        task_ids=["T2", "T1"],
        sense_check_ids=["SC1"],
        state=state,
        finalize_data=finalize_data,
    )

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    scope = BatchScope.create(
        batch_number=2,
        task_ids=["T1", "T2"],
        sense_check_ids=["SC1"],
    )
    identity = DispatchIdentity.from_dict(payload[DISPATCH_IDENTITY_KEY])
    resolution = resolve_batch_scope(
        payload,
        artifact_path,
        known_task_ids=KNOWN_TASKS,
        known_sense_check_ids=KNOWN_CHECKS,
        expected_batch_number=2,
    )

    assert payload[BATCH_SCOPE_KEY] == scope.to_dict()
    assert resolution.scope == scope
    assert payload[RESULT_ENVELOPES_KEY] == []
    assert DISPATCH_IDENTITY_KEY not in payload[BATCH_SCOPE_KEY]
    assert RESULT_ENVELOPES_KEY not in payload[BATCH_SCOPE_KEY]
    assert identity.dispatch_id == f"megaplan-run:execute:batch:2:{scope.task_set_digest}"
    assert identity.run_id == "megaplan-run"
    assert identity.run_revision == "sha256:plan-revision"
    assert identity.coordinator_attempt_id == "coordinator-attempt"
    assert identity.fence_token == 2
    assert identity.subject_ids == ("SC1", "T1", "T2")
    assert identity.capabilities == (
        SENSE_CHECK_RESULT_CAPABILITY,
        TASK_RESULT_CAPABILITY,
    )
    assert identity.worker_id == f"megaplan-execute-batch-2-{scope.task_set_digest}"
    assert identity.prerequisite_digest
    assert identity.prerequisite_digest != scope.task_set_digest


def test_worker_result_envelopes_echo_dispatch_identity_and_attempts(
    tmp_path: Path,
) -> None:
    state = {
        "name": "megaplan-run",
        "created_at": "2026-07-10T00:00:00Z",
        "current_state": "finalized",
        "iteration": 3,
        "config": {"mode": "code"},
        "sessions": {},
        "history": [],
        "meta": {},
        "plan_versions": [{"hash": "sha256:plan-revision"}],
        "active_step": {"run_id": "coordinator-attempt", "attempt": 2},
    }
    finalize_data = {
        "tasks": [
            {"id": "T1", "depends_on": []},
            {"id": "T2", "depends_on": ["T1"]},
        ],
        "sense_checks": [{"id": "SC1", "task_id": "T2"}],
        "user_actions": [],
    }
    artifact_path = _prepare_scoped_batch_checkpoint(
        tmp_path,
        batch_number=2,
        task_ids=["T2", "T1"],
        sense_check_ids=["SC1"],
        state=state,
        finalize_data=finalize_data,
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    identity = DispatchIdentity.from_dict(payload[DISPATCH_IDENTITY_KEY])
    payload["task_updates"] = [
        {
            "task_id": "T1",
            "status": "done",
            "executor_notes": "implemented",
            "files_changed": ["pkg.py"],
            "commands_run": ["pytest tests/pkg.py"],
        }
    ]
    payload["sense_check_acknowledgments"] = [
        {"sense_check_id": "SC1", "executor_note": "covered"}
    ]

    envelopes = _stamp_result_envelopes(
        payload,
        identity=identity,
        artifact_path=artifact_path,
    )
    authority_resolution = resolve_batch_authority_metadata(payload, artifact_path)
    payload[BATCH_SCOPE_KEY]["task_ids"] = ["T999"]
    payload[BATCH_SCOPE_KEY]["task_set_digest"] = "000000000000"
    tampered_authority_resolution = resolve_batch_authority_metadata(
        payload, artifact_path
    )
    tampered_scope_resolution = resolve_batch_scope(
        payload,
        artifact_path,
        known_task_ids=KNOWN_TASKS,
        known_sense_check_ids=KNOWN_CHECKS,
        expected_batch_number=2,
    )

    assert len(envelopes) == 2
    assert all(isinstance(envelope, ResultEnvelope) for envelope in envelopes)
    assert authority_resolution.is_proven
    assert authority_resolution.metadata is not None
    assert len(authority_resolution.metadata.result_envelopes) == 2
    assert tampered_authority_resolution.is_proven
    assert tampered_scope_resolution.quarantine is not None
    task_echo = payload["task_updates"][0]["authority"]
    check_echo = payload["sense_check_acknowledgments"][0]["authority"]
    assert task_echo["dispatch_id"] == identity.dispatch_id
    assert task_echo["run_revision"] == "sha256:plan-revision"
    assert task_echo["fence"]["coordinator_attempt_id"] == "coordinator-attempt"
    assert task_echo["fence"]["token"] == 2
    assert task_echo["scope"]["subject_ids"] == list(identity.subject_ids)
    assert task_echo["prerequisite_digest"] == identity.prerequisite_digest
    assert task_echo["worker_id"] == identity.worker_id
    assert task_echo["attempt"]["subject_id"] == "T1"
    assert task_echo["attempt"]["grant_id"] == identity.dispatch_id
    assert check_echo["attempt"]["subject_id"] == "SC1"
    assert check_echo["attempt"]["grant_id"] == identity.dispatch_id
    assert payload[RESULT_ENVELOPES_KEY][0]["dispatch"] == identity.to_dict()


def test_no_pending_replay_quarantines_scoped_rows_without_result_authority(
    tmp_path: Path,
) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done"},
            {"id": "T2", "status": "skipped"},
            {"id": "T3", "status": "done"},
        ],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "executor_note": ""},
            {"id": "SC2", "task_id": "T2", "executor_note": ""},
            {"id": "SC3", "task_id": "T3", "executor_note": "unchanged"},
        ],
    }

    def write_scoped(
        batch_number: int,
        task_ids: list[str],
        sense_check_ids: list[str],
        payload: dict,
    ) -> None:
        scope = BatchScope.create(
            batch_number=batch_number,
            task_ids=task_ids,
            sense_check_ids=sense_check_ids,
        )
        payload[BATCH_SCOPE_KEY] = scope.to_dict()
        path = (
            tmp_path
            / "execute_batches"
            / f"batch_{batch_number}"
            / f"tasks_{scope.task_set_digest}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    write_scoped(
        1,
        ["T1"],
        ["SC1"],
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "blocked",
                    "executor_notes": "proven batch-one result",
                    "files_changed": [],
                    "commands_run": [],
                },
                {
                    "task_id": "T3",
                    "status": "blocked",
                    "executor_notes": "off-scope result",
                    "files_changed": [],
                    "commands_run": [],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "batch one proven"},
                {"sense_check_id": "SC3", "executor_note": "off-scope note"},
            ],
        },
    )
    write_scoped(
        2,
        ["T2"],
        ["SC2"],
        {
            "task_updates": [
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "proven batch-two result",
                    "files_changed": ["src/t2.py"],
                    "commands_run": ["pytest"],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC2", "executor_note": "batch two proven"}
            ],
        },
    )
    legacy_path = tmp_path / "execution_batch_3.json"
    legacy_path.write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "unproven legacy override",
                        "files_changed": ["legacy.py"],
                        "commands_run": ["legacy-test"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    replayed = _replay_proven_batch_artifacts(
        plan_dir=tmp_path,
        finalize_data=finalize_data,
        known_task_ids=["T1", "T2", "T3"],
        known_sense_check_ids=["SC1", "SC2", "SC3"],
        mode="code",
        state={"config": {"mode": "code"}},
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    checks = {check["id"]: check for check in finalize_data["sense_checks"]}
    assert replayed == []
    assert tasks["T1"]["status"] == "done"
    assert tasks["T1"].get("executor_notes") is None
    assert tasks["T2"]["status"] == "skipped"
    assert tasks["T3"] == {"id": "T3", "status": "done"}
    assert checks["SC1"]["executor_note"] == ""
    assert checks["SC2"]["executor_note"] == ""
    assert checks["SC3"]["executor_note"] == "unchanged"
    events = (tmp_path / "events.ndjson").read_text(encoding="utf-8")
    assert "authority_divergence" in events
    assert "batch_scope_missing_batch_scope" in events
    assert str(legacy_path) in events


def test_no_pending_replay_routes_off_scope_enveloped_rows_to_validator(
    tmp_path: Path,
) -> None:
    state = {
        "name": "megaplan-run",
        "created_at": "2026-07-10T00:00:00Z",
        "current_state": "finalized",
        "iteration": 3,
        "config": {"mode": "code"},
        "sessions": {},
        "history": [],
        "meta": {},
        "plan_versions": [{"hash": "sha256:plan-revision"}],
        "active_step": {"run_id": "coordinator-attempt", "attempt": 2},
    }
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "pending", "executor_notes": ""},
            {"id": "T2", "status": "pending", "executor_notes": ""},
        ],
        "sense_checks": [],
        "user_actions": [],
    }
    artifact_path = _prepare_scoped_batch_checkpoint(
        tmp_path,
        batch_number=1,
        task_ids=["T2"],
        sense_check_ids=[],
        state=state,
        finalize_data=finalize_data,
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    identity = DispatchIdentity.create(
        dispatch_id="megaplan-run:execute:batch:old-t1",
        run_id="megaplan-run",
        run_revision="sha256:plan-revision",
        coordinator_attempt_id="coordinator-attempt",
        fence_token=2,
        subject_ids=("T1",),
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest="old-t1-prerequisite-digest",
        worker_id="megaplan-execute-batch-old-t1",
    )
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "off-scope enveloped result",
        "files_changed": [],
        "commands_run": [],
    }
    evidence = EvidenceEnvelope(
        evidence_id="old-t1:evidence",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        evidence_type="megaplan.task_update",
        source="test",
        payload={"entry": entry},
    )
    attempt = TaskAttempt(
        attempt_id="old-t1:attempt",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        subject_id="T1",
        grant_id=identity.dispatch_id,
        coordinator_attempt_id=identity.coordinator_attempt_id,
        fence_token=identity.fence_token,
        ordinal=1,
    )
    claim = TaskClaim(
        claim_id="old-t1:claim",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        subject_id="T1",
        attempt_id=attempt.attempt_id,
        grant_id=identity.dispatch_id,
        coordinator_attempt_id=identity.coordinator_attempt_id,
        fence_token=identity.fence_token,
        claim_type=TASK_COMPLETION_CLAIM,
        evidence_ids=(evidence.evidence_id,),
        idempotency_key="old-t1:claim",
        payload={"entry": entry},
    )
    envelope = ResultEnvelope(
        dispatch=identity,
        attempt=attempt,
        claim=claim,
        evidence=(evidence,),
    )
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
    payload[DISPATCH_IDENTITY_KEY] = identity.to_dict()
    payload[RESULT_ENVELOPES_KEY] = [envelope.to_dict()]
    payload["task_updates"] = [entry]
    payload["sense_check_acknowledgments"] = []
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    replayed = _replay_proven_batch_artifacts(
        plan_dir=tmp_path,
        finalize_data=finalize_data,
        known_task_ids=["T1", "T2"],
        known_sense_check_ids=[],
        mode="code",
        state=state,
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    validation = replayed[0]["task_updates"][0]["authority_validation"]
    assert tasks["T1"]["status"] == "pending"
    assert tasks["T2"]["status"] == "pending"
    assert validation["outcome"] == "rejected"
    assert validation["reason"] == "subject_outside_dispatched_batch"
    assert validation["source_path"] == str(artifact_path)


def test_blocked_by_prereq_emits_prereq_blocked_task_ids_when_active_blocked_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for the CL2 execute-phase crash.

    ``handle_execute_auto_loop`` selects ``blocked_by_prereq`` from
    ``prereq_blocked_task_ids`` (execute/batch.py:6705-6719) but previously
    published only ``active_blocked_task_ids`` (execute/batch.py:6775-6783).
    The two sets can diverge: a harness-generated block is kept in the active
    blocked set while being dropped from the prereq set (and a
    baseline-unavailable checkpoint is dropped from active while kept in
    prereq).  When the prereq set contains a task the active set does not --
    the CL2 baseline/prerequisite case -- the old projection emitted the wrong
    set or, when active was empty, no ``blocked_task_ids`` at all, and the
    handler's ``PhaseResult`` rejected ``blocked_by_prereq``
    (``blocked_by_prereq requires at least one blocked_task``).  The response
    must emit the set that selected the outcome.
    """
    import argparse
    import types as _types

    from arnold_pipelines.megaplan.execute.batch import (
        _BASELINE_VERIFICATION_MARKER,
        handle_execute_auto_loop,
    )
    from arnold_pipelines.megaplan.orchestration.phase_result import (
        BlockedTask,
        ExitKind,
        PhaseResult,
    )

    # The M10 task-graph admission re-assertion is unrelated to the projection
    # under test and rejects a minimal non-v2 fixture, so stub it out.
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._guard_execute_batch_admission",
        lambda **kwargs: None,
    )

    # Drive one dispatch round without an LLM: a pending batch is "executed" by
    # a stub that re-blocks its tasks (pinned-baseline unresolved).  H carries a
    # harness-generated block note, so the late projection keeps H in
    # ``active_blocked_task_ids`` but drops it from ``prereq_blocked_task_ids``;
    # X is a genuine prerequisite block that stays in both.  The prereq set
    # {X} therefore differs from the active set {H, X}, and the old projection
    # (which published the active set) dropped nothing but reverted would fail.
    def _fake_run_and_merge_batch(**kwargs):
        fin = kwargs["finalize_data"]
        batch_ids = set(kwargs["batch_task_ids"])
        for task in fin.get("tasks", []):
            if isinstance(task, dict) and task.get("id") in batch_ids:
                task["status"] = "blocked"
                task["executor_notes"] = (
                    "[harness] synthetic block"
                    if task.get("id") == "H"
                    else "pinned baseline unresolved"
                )
        worker = _types.SimpleNamespace(
            duration_ms=0, cost_usd=0.0, prompt_tokens=0, completion_tokens=0,
            total_tokens=0, rate_limit=None, session_id=None, model_actual=None,
            worker_channel=None, auth_channel=None, auth_metadata=None,
            rendered_prompt=None, trace_output=None,
        )
        return _types.SimpleNamespace(
            worker=worker,
            agent=kwargs.get("agent", "shadow"),
            mode=kwargs.get("mode", "code"),
            refreshed=kwargs.get("refreshed", False),
            payload={"task_updates": [], "sense_check_acknowledgments": []},
            batch_number=kwargs.get("batch_number", 1),
            batch_task_ids=kwargs["batch_task_ids"],
            batch_sense_check_ids=kwargs.get("batch_sense_check_ids", []),
            merged_task_count=0,
            total_task_count=len(kwargs["batch_task_ids"]),
            acknowledged_sense_check_count=0,
            total_sense_check_count=len(kwargs.get("batch_sense_check_ids", [])),
            missing_task_evidence=[],
            execution_audit={},
            finalize_hash="",
            attribution_records=[],
            routing_degradations=[],
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._run_and_merge_batch",
        _fake_run_and_merge_batch,
    )

    finalize_data = {
        "tasks": [
            {
                "id": "X",
                "status": "pending",
                "depends_on": [],
                "description": "complete the pinned-baseline audit",
                "executor_notes": "",
            },
            {
                "id": "H",
                "status": "pending",
                "depends_on": [],
                "description": "synthetic harness checkpoint",
                "executor_notes": "",
            },
        ],
        "sense_checks": [],
        "baseline_test_failures": None,
        "user_actions": [],
    }
    (tmp_path / "finalize.json").write_text(
        json.dumps(finalize_data), encoding="utf-8"
    )
    state = {
        "name": "megaplan-run",
        "created_at": "2026-07-10T00:00:00Z",
        "current_state": "executed",
        "iteration": 1,
        "config": {"mode": "code", "project_dir": str(tmp_path)},
        "sessions": {},
        "history": [],
        "meta": {},
        "plan_versions": [{"hash": "sha256:plan-revision"}],
        "active_step": {"run_id": "coordinator-attempt", "attempt": 2},
    }
    response = handle_execute_auto_loop(
        root=tmp_path,
        plan_dir=tmp_path,
        state=state,
        args=argparse.Namespace(),
        auto_approve=False,
        agent="shadow",
        mode="code",
        refreshed=False,
    )

    assert response["_phase_outcome"] == "blocked_by_prereq"
    blocked_ids = response["blocked_task_ids"]
    # The emitted set must come from the set that selected the outcome
    # (prereq_blocked_task_ids) -- the genuine prerequisite block X, not the
    # active set which also carries the harness-generated block H.
    assert blocked_ids == ["X"]
    # Mirror the handler's PhaseResult emission contract
    # (handlers/execute.py:1197-1220): blocked_by_prereq builds one BlockedTask
    # per emitted blocked_task_ids entry.
    blocked = tuple(
        BlockedTask(task_id=tid, reason="blocked_by_prereq", notes="")
        for tid in blocked_ids
    )
    result = PhaseResult(
        phase="execute",
        invocation_id="test",
        exit_kind=ExitKind.blocked_by_prereq.value,
        blocked_tasks=blocked,
    )
    assert result.blocked_tasks
    assert result.blocked_tasks[0].task_id == "X"


def test_auto_loop_pending_left_behind_blocks_phase_and_skips_later_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Abort-recovery stop: a batch leaving non-complete tasks parks the phase.

    If a dispatched batch leaves any task non-terminal (worker aborted
    mid-batch, no accepted envelope, not authority-completed), the auto loop
    must stop BEFORE dispatching later batches, and the phase-final decision
    must surface the park (blocked_by_quality), never success.
    """
    import argparse
    import json
    import types as _types

    from arnold_pipelines.megaplan.execute.batch import (
        handle_execute_auto_loop,
    )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._guard_execute_batch_admission",
        lambda **kwargs: None,
    )

    calls: list[list[str]] = []
    _zero = 0

    def _fake_run_and_merge_batch(**kwargs):
        # Worker "aborts": batch tasks stay pending, no accepted envelopes.
        fin = kwargs["finalize_data"]
        batch_ids = list(kwargs["batch_task_ids"])
        calls.append(batch_ids)
        worker = _types.SimpleNamespace(
            duration_ms=0,
            cost_usd=0.0,
            prompt_tokens=_zero,
            completion_tokens=_zero,
            total_tokens=_zero,
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
        "arnold_pipelines.megaplan.execute.batch._run_and_merge_batch",
        _fake_run_and_merge_batch,
    )

    # Three independent tasks split into two batches of <=2.
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "pending", "depends_on": [], "description": "t1"},
            {"id": "T2", "status": "pending", "depends_on": [], "description": "t2"},
            {"id": "T3", "status": "pending", "depends_on": [], "description": "t3"},
        ],
        "sense_checks": [],
        "baseline_test_failures": None,
        "user_actions": [],
    }
    (tmp_path / "finalize.json").write_text(
        json.dumps(finalize_data), encoding="utf-8"
    )
    state = {
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
    response = handle_execute_auto_loop(
        root=tmp_path,
        plan_dir=tmp_path,
        state=state,
        args=argparse.Namespace(),
        auto_approve=False,
        agent="shadow",
        mode="code",
        refreshed=False,
    )

    # Only the first batch was dispatched; the loop stopped on pending-left-
    # behind instead of cascading into batch 2.
    assert calls == [["T1", "T2"]]
    assert response["success"] is False
    assert response["_phase_outcome"] == "blocked_by_quality"
    assert "remained non-complete after their execute batch" in response["summary"]
    assert state["current_state"] != "executed"


def test_explained_skip_plus_budget_block_drains_independent_frontier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loop-halt fix (occurrence 4c0190500877): accepted skipped + budget
    blocked must NOT park the auto loop.

    A merged ``skipped`` task with an accepted envelope is terminal; a
    ``blocked`` task carries its typed blocker disposition. Neither is
    \"pending-left-behind\", so a sole task-level block parks only the blocked
    rows and the dependency-independent frontier still dispatches. This is the
    regression that keeps T16 runnable after a budget-blocked batch.
    """
    import argparse
    import json
    import types as _types

    from arnold_pipelines.megaplan.execute.batch import (
        handle_execute_auto_loop,
    )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._guard_execute_batch_admission",
        lambda **kwargs: None,
    )

    calls: list[list[str]] = []

    def _fake_run_and_merge_batch(**kwargs):
        # Simulates merge outcomes: T1 explained-skipped (accepted), T2
        # budget-blocked by the merge admission gate, T3 completed.
        fin = kwargs["finalize_data"]
        batch_ids = list(kwargs["batch_task_ids"])
        calls.append(batch_ids)
        for tid in batch_ids:
            for task in fin["tasks"]:
                if task["id"] != tid:
                    continue
                if tid == "T1":
                    task["status"] = "skipped"
                    task["executor_notes"] = "explained skip: covered by T3"
                elif tid == "T2":
                    task["status"] = "blocked"
                    task["executor_notes"] = (
                        "[harness] task_test_budget_exhausted: declared test "
                        "timeout total 240s exceeds max_seconds=120"
                    )
                else:
                    task["status"] = "done"
                    task["files_changed"] = [f"{tid}.py"]
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
        "arnold_pipelines.megaplan.execute.batch._run_and_merge_batch",
        _fake_run_and_merge_batch,
    )

    # Three independent tasks: batch 1 = [T1, T2], batch 2 = [T3].
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "pending", "depends_on": [], "description": "t1"},
            {"id": "T2", "status": "pending", "depends_on": [], "description": "t2"},
            {"id": "T3", "status": "pending", "depends_on": [], "description": "t3"},
        ],
        "sense_checks": [],
        "baseline_test_failures": None,
        "user_actions": [],
    }
    (tmp_path / "finalize.json").write_text(
        json.dumps(finalize_data), encoding="utf-8"
    )
    state = {
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
    response = handle_execute_auto_loop(
        root=tmp_path,
        plan_dir=tmp_path,
        state=state,
        args=argparse.Namespace(),
        auto_approve=False,
        agent="shadow",
        mode="code",
        refreshed=False,
    )

    # The budget block parked T2 but the independent frontier (T3) still
    # dispatched — the loop did NOT halt after batch 1. The loop publishes
    # finalize at completion, so re-read the persisted state.
    assert calls == [["T1", "T2"], ["T3"]]
    published = json.loads((tmp_path / "finalize.json").read_text(encoding="utf-8"))
    by_id = {task["id"]: task for task in published["tasks"]}
    assert by_id["T1"]["status"] == "skipped"
    assert by_id["T2"]["status"] == "blocked"
    assert by_id["T3"]["status"] == "done"
    assert "remained non-complete after their execute batch" not in response.get(
        "summary", ""
    )


# ═══════════════════════════════════════════════════════════════════════════
# Dependency-aware execute frontier (occurrence 0ae19cc17afd, shipped in
# b2aaab3f "fix(execute): drain dependency-independent frontier after task
# block"). A sole task-level block must park the blocked rows with a typed
# disposition and continue with the dependency-independent frontier; the
# blocked row and its transitive dependents stay out of the runnable queue
# and are never flipped back to pending within the same invocation.
# ═══════════════════════════════════════════════════════════════════════════

import argparse as _argparse

from arnold_pipelines.megaplan.execute.batch import (
    _dependency_closed_blocked_task_ids,
    _has_genuine_task_level_blocker,
    _park_blocked_task_dispositions,
    _recompute_runnable_batches,
)


def _frontier_task(
    task_id: str,
    *,
    status: str = "pending",
    depends_on: list[str] | None = None,
    complexity: int = 1,
) -> dict[str, object]:
    return {
        "id": task_id,
        "status": status,
        "depends_on": list(depends_on or []),
        "complexity": complexity,
        "estimated_minutes": 3,
        "executor_notes": "",
        "files_changed": [],
        "commands_run": [],
        "evidence_files": [],
    }


def _frontier_state_and_args() -> tuple[dict[str, object], _argparse.Namespace]:
    state: dict[str, object] = {"config": {"max_tasks_per_batch": 5}}
    return state, _argparse.Namespace()


def test_validation_block_does_not_strand_independent_batches() -> None:
    """DAG A -> C with independent B: A blocks, B dispatches, C never does."""
    tasks = [
        _frontier_task("A"),
        _frontier_task("B"),
        _frontier_task("C", depends_on=["A"]),
    ]
    finalize_data = {"tasks": tasks}

    # Worker reports A blocked in the first wave (merge layer sets
    # status=blocked); park it with a typed disposition (no explicit blocker
    # fields -> validation_blocked).
    tasks[0]["status"] = "blocked"
    _park_blocked_task_dispositions(
        finalize_data,
        newly_blocked_task_ids=["A"],
        current_invocation_id="inv-1",
    )
    assert tasks[0]["status"] == "blocked"
    assert tasks[0]["blocked_reason"] == "validation_blocked"
    assert tasks[0]["recorded_invocation_id"] == "inv-1"

    # The runnable frontier must exclude A and its transitive dependent C,
    # leaving only independent B.
    state, args = _frontier_state_and_args()
    runnable = _recompute_runnable_batches(
        finalize_data,
        completed_task_ids=set(),
        state=state,  # type: ignore[arg-type]
        args=args,
    )
    assert runnable == [["B"]]

    # B dispatches and completes; the frontier is now empty, so the loop
    # breaks with the phase still blocked (A parked, C never dispatched).
    tasks[1]["status"] = "done"
    runnable_after = _recompute_runnable_batches(
        finalize_data,
        completed_task_ids={"B"},
        state=state,  # type: ignore[arg-type]
        args=args,
    )
    assert runnable_after == []
    assert tasks[2]["status"] == "pending"  # C never dispatched
    assert tasks[0]["status"] == "blocked"  # A never flipped back to pending


def test_validation_blocked_ids_and_transitive_dependents_stay_out_of_runnable_queue() -> None:
    """Closure, persistent typed kind, and no within-session pending flip."""
    tasks = [
        _frontier_task("A", complexity=7),
        _frontier_task("B", depends_on=["A"]),
        _frontier_task("C", depends_on=["B"]),
        _frontier_task("D"),
    ]
    finalize_data = {"tasks": tasks}

    # Both blocked rows carry status=blocked from the merge layer; the
    # explicit user-action blocker on D -> prerequisite_blocked (genuine).
    tasks[0]["status"] = "blocked"
    tasks[3]["status"] = "blocked"
    tasks[3]["blocked_by_user_action_ids"] = ["UA-1"]
    _park_blocked_task_dispositions(
        finalize_data,
        newly_blocked_task_ids=["A", "D"],
        current_invocation_id="inv-7",
    )
    assert tasks[0]["blocked_reason"] == "validation_blocked"
    assert tasks[3]["blocked_reason"] == "prerequisite_blocked"
    assert _has_genuine_task_level_blocker(tasks[3]) is True
    assert _has_genuine_task_level_blocker(tasks[0]) is False

    # Transitive closure of the validation block: A plus B and C. D is a
    # genuine prerequisite block and stays parked too.
    closed = _dependency_closed_blocked_task_ids(tasks, ["A"])
    assert closed == {"A", "B", "C"}

    state, args = _frontier_state_and_args()
    runnable = _recompute_runnable_batches(
        finalize_data,
        completed_task_ids=set(),
        state=state,  # type: ignore[arg-type]
        args=args,
    )
    # No runnable frontier remains: A/B/C in the closure, D parked.
    assert runnable == []

    # Re-parking the same invocation must not flip rows back to pending.
    _park_blocked_task_dispositions(
        finalize_data,
        newly_blocked_task_ids=["A"],
        current_invocation_id="inv-7",
    )
    assert tasks[0]["status"] == "blocked"
    assert tasks[0]["blocked_reason"] == "validation_blocked"
    assert tasks[3]["status"] == "blocked"
    assert tasks[3]["blocked_reason"] == "prerequisite_blocked"


# ---------------------------------------------------------------------------
# Occurrence 4c0190500877: accepted-evidence backfill during replay
# (codex consult 2026-08-17T06:4xZ; engine patch in execute/merge.py
# _merge_validated_entries preserve_accepted branch).
# Requirements proven below:
#   1. an accepted evidence-empty target receives files/commands from a
#      scoped terminal `done` record;
#   2. a later `blocked` record cannot demote it or replace its evidence;
#   3. existing target evidence is never overwritten;
#   4. replay of the proven terminal wave leaves T10/T13 done with durable
#      evidence (chain phase-coverage no longer re-blocks).
# ---------------------------------------------------------------------------


def _merge_entries(
    targets: dict[str, dict],
    entries: list[dict],
    *,
    preserve_accepted: bool = True,
) -> list[str]:
    from arnold_pipelines.megaplan.execute.merge import _merge_validated_entries

    issues: list[str] = []
    _merge_validated_entries(
        entries,
        targets_by_id=targets,
        id_field="task_id",
        merge_fields=("status", "executor_notes", "files_changed", "commands_run"),
        issues=issues,
        label="task_updates",
        preserve_accepted=preserve_accepted,
    )
    return issues


def test_accepted_evidence_empty_target_backfills_terminal_done_evidence() -> None:
    """Requirement 1: terminal accepted incoming row corroborates accepted target."""
    target = {"id": "T10_impl", "status": "done"}
    targets = {"T10_impl": target}
    issues = _merge_entries(
        targets,
        [
            {
                "task_id": "T10_impl",
                "status": "done",
                "executor_notes": "proven terminal wave",
                "files_changed": ["arnold_pipelines/megaplan/cloud/a.py"],
                "commands_run": ["pytest -q tests/cloud"],
                "head_sha": "15b881cb4",
            }
        ],
    )
    assert target["status"] == "done"  # never demoted
    assert target["files_changed"] == ["arnold_pipelines/megaplan/cloud/a.py"]
    assert target["commands_run"] == ["pytest -q tests/cloud"]
    assert target["head_sha"] == "15b881cb4"
    assert any("status preserved; missing terminal evidence backfilled" in i for i in issues)


def test_later_blocked_shadow_record_cannot_demote_or_replace_evidence() -> None:
    """Requirement 2: non-terminal shadow (batch-6 blocked) never wins."""
    target = {"id": "T10_impl", "status": "done", "files_changed": ["a.py"], "commands_run": ["t"]}
    targets = {"T10_impl": target}
    issues = _merge_entries(
        targets,
        [
            {
                "task_id": "T10_impl",
                "status": "blocked",
                "executor_notes": "stale batch-6 overlay",
                "files_changed": ["stale.py"],
                "commands_run": ["stale-cmd"],
            }
        ],
    )
    assert target["status"] == "done"
    assert target["files_changed"] == ["a.py"]
    assert target["commands_run"] == ["t"]
    assert "stale.py" not in target["files_changed"]
    assert any("Preserved accepted" in i for i in issues)


def test_accepted_backfill_never_overwrites_existing_durable_evidence() -> None:
    """Requirement 3: durable evidence already present is left untouched."""
    target = {
        "id": "T14_impl",
        "status": "done",
        "files_changed": ["existing.py"],
        "commands_run": ["existing-cmd"],
    }
    targets = {"T14_impl": target}
    _merge_entries(
        targets,
        [
            {
                "task_id": "T14_impl",
                "status": "done",
                "executor_notes": "later wave",
                "files_changed": ["later.py"],
                "commands_run": ["later-cmd"],
                "head_sha": "deadbeef",
            }
        ],
    )
    assert target["files_changed"] == ["existing.py"]
    assert target["commands_run"] == ["existing-cmd"]
    assert "later.py" not in target["files_changed"]


def test_replay_leaves_evidence_empty_accepted_tasks_durable(
    tmp_path: Path,
) -> None:
    """Requirement 4: end-to-end replay backfills T10/T13 evidence via the
    proven terminal wave (batch-1 done records with envelopes) while the stale
    batch-6 blocked shadow stays inert — exactly the occurrence 4c0190500877
    case."""
    state = {
        "name": "megaplan-run",
        "created_at": "2026-08-17T00:00:00Z",
        "current_state": "finalized",
        "iteration": 3,
        "config": {"mode": "code"},
        "sessions": {},
        "history": [],
        "meta": {},
        "plan_versions": [{"hash": "sha256:plan-revision"}],
        "active_step": {"run_id": "coordinator-attempt", "attempt": 2},
    }
    finalize_data = {
        "tasks": [
            {"id": "T10_impl", "status": "done"},
            {"id": "T13_impl", "status": "done"},
            {"id": "T12_impl", "status": "skipped"},
        ],
        "sense_checks": [],
        "user_actions": [],
    }

    def write_terminal_wave(
        batch_number: int,
        task_id: str,
        files_changed: list[str],
        commands_run: list[str],
    ) -> None:
        """Write a scoped, enveloped, proven terminal `done` record."""
        artifact_path = _prepare_scoped_batch_checkpoint(
            tmp_path,
            batch_number=batch_number,
            task_ids=[task_id],
            sense_check_ids=[],
            state=state,
            finalize_data=finalize_data,
        )
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        identity = DispatchIdentity.create(
            dispatch_id=f"megaplan-run:execute:batch:{task_id}",
            run_id="megaplan-run",
            run_revision="sha256:plan-revision",
            coordinator_attempt_id="coordinator-attempt",
            fence_token=2,
            subject_ids=(task_id,),
            capabilities=(TASK_RESULT_CAPABILITY,),
            prerequisite_digest=f"{task_id}-prerequisite-digest",
            worker_id=f"megaplan-execute-batch-{task_id}",
        )
        entry = {
            "task_id": task_id,
            "status": "done",
            "executor_notes": "terminal wave",
            "files_changed": files_changed,
            "commands_run": commands_run,
            "head_sha": "15b881cb4",
        }
        evidence = EvidenceEnvelope(
            evidence_id=f"{task_id}:evidence",
            run_id=identity.run_id,
            run_revision=identity.run_revision,
            evidence_type="megaplan.task_update",
            source="test",
            payload={"entry": entry},
        )
        attempt = TaskAttempt(
            attempt_id=f"{task_id}:attempt",
            run_id=identity.run_id,
            run_revision=identity.run_revision,
            subject_id=task_id,
            grant_id=identity.dispatch_id,
            coordinator_attempt_id=identity.coordinator_attempt_id,
            fence_token=identity.fence_token,
            ordinal=1,
        )
        claim = TaskClaim(
            claim_id=f"{task_id}:claim",
            run_id=identity.run_id,
            run_revision=identity.run_revision,
            subject_id=task_id,
            attempt_id=attempt.attempt_id,
            grant_id=identity.dispatch_id,
            coordinator_attempt_id=identity.coordinator_attempt_id,
            fence_token=identity.fence_token,
            claim_type=TASK_COMPLETION_CLAIM,
            evidence_ids=(evidence.evidence_id,),
            idempotency_key=f"{task_id}:claim",
            payload={"entry": entry},
        )
        envelope = ResultEnvelope(
            dispatch=identity,
            attempt=attempt,
            claim=claim,
            evidence=(evidence,),
        )
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
        payload[DISPATCH_IDENTITY_KEY] = identity.to_dict()
        payload[RESULT_ENVELOPES_KEY] = [envelope.to_dict()]
        payload["task_updates"] = [entry]
        payload["sense_check_acknowledgments"] = []
        artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    # Proven terminal wave (batch-1): T10_impl + T13_impl done with evidence.
    write_terminal_wave(
        1,
        "T10_impl",
        ["cloud/maintenance_recovery.py"],
        ["pytest -q tests/cloud"],
    )
    write_terminal_wave(
        1,
        "T13_impl",
        ["cloud/maintenance_canary.py"],
        ["pytest -q tests/cloud"],
    )
    # Stale shadow (batch-6): T10_impl blocked — must NOT demote or replace.
    shadow_path = _prepare_scoped_batch_checkpoint(
        tmp_path,
        batch_number=6,
        task_ids=["T10_impl"],
        sense_check_ids=[],
        state=state,
        finalize_data=finalize_data,
    )
    shadow_payload = json.loads(shadow_path.read_text(encoding="utf-8"))
    shadow_payload["task_updates"] = [
        {
            "task_id": "T10_impl",
            "status": "blocked",
            "executor_notes": "stale shadow",
            "files_changed": ["stale.py"],
            "commands_run": ["stale-cmd"],
        }
    ]
    shadow_path.write_text(json.dumps(shadow_payload), encoding="utf-8")

    _replay_proven_batch_artifacts(
        plan_dir=tmp_path,
        finalize_data=finalize_data,
        known_task_ids=["T10_impl", "T13_impl", "T12_impl"],
        known_sense_check_ids=[],
        mode="code",
        state=state,
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert tasks["T10_impl"]["status"] == "done"
    assert tasks["T10_impl"]["files_changed"] == ["cloud/maintenance_recovery.py"]
    assert tasks["T10_impl"]["commands_run"] == ["pytest -q tests/cloud"]
    assert tasks["T10_impl"]["head_sha"] == "15b881cb4"
    assert tasks["T13_impl"]["status"] == "done"
    assert tasks["T13_impl"]["files_changed"] == ["cloud/maintenance_canary.py"]
    assert tasks["T13_impl"]["head_sha"] == "15b881cb4"
    assert tasks["T12_impl"]["status"] == "skipped"
    # The stale shadow never leaked in.
    assert "stale.py" not in tasks["T10_impl"]["files_changed"]


def test_authority_accepted_blocked_row_backfills_evidence_without_demotion() -> None:
    """Authority-accepted row with a stale 'blocked' projection backfills
    evidence into an evidence-empty accepted target without demoting it
    (occurrence 4c0190500877: batch-6 T10_impl row is authority-accepted)."""
    target = {"id": "T10_impl", "status": "done"}
    targets = {"T10_impl": target}
    issues = _merge_entries(
        targets,
        [
            {
                "task_id": "T10_impl",
                "status": "blocked",
                "executor_notes": "stale projection, authority accepted",
                "files_changed": ["arnold_pipelines/megaplan/cloud/a.py"],
                "commands_run": ["pytest -q tests/cloud"],
                "head_sha": "15b881cb4",
                "authority_validation": {"outcome": "accepted"},
            }
        ],
    )
    assert target["status"] == "done"  # never demoted
    assert target["files_changed"] == ["arnold_pipelines/megaplan/cloud/a.py"]
    assert target["commands_run"] == ["pytest -q tests/cloud"]
    assert target["head_sha"] == "15b881cb4"
    # executor_notes is durable audit/research evidence: an authority-accepted
    # row's notes backfill into the empty target field (occurrence 4c1e5073ca7c).
    assert target["executor_notes"] == "stale projection, authority accepted"
    assert any("status preserved; missing terminal evidence backfilled" in i for i in issues)


@pytest.mark.parametrize("outcome", ["rejected", "quarantined", "superseded-or-conflicting"])
def test_authority_rejected_or_quarantined_blocked_row_does_not_backfill(
    outcome: str,
) -> None:
    """A blocked row whose authority did NOT accept it stays inert: no evidence
    leaks, target stays terminal and evidence-empty."""
    target = {"id": "T13_impl", "status": "done"}
    targets = {"T13_impl": target}
    issues = _merge_entries(
        targets,
        [
            {
                "task_id": "T13_impl",
                "status": "blocked",
                "executor_notes": "real policy failure",
                "files_changed": ["leak.py"],
                "commands_run": ["leak-cmd"],
                "head_sha": "deadbeef",
                "authority_validation": {"outcome": outcome},
            }
        ],
    )
    assert target["status"] == "done"
    assert target.get("files_changed") is None
    assert target.get("commands_run") is None
    assert target.get("head_sha") is None
    assert target.get("executor_notes") is None  # notes never leak from rejected rows


def test_authority_accepted_blocked_row_never_overwrites_existing_evidence() -> None:
    """Field-local guard: existing target evidence wins; empty target fields may
    still be backfilled from an authority-accepted blocked row."""
    target = {
        "id": "T10_impl",
        "status": "done",
        "files_changed": ["existing.py"],
        "commands_run": [],
        "executor_notes": "existing substantive notes already on target",
    }
    targets = {"T10_impl": target}
    _merge_entries(
        targets,
        [
            {
                "task_id": "T10_impl",
                "status": "blocked",
                "files_changed": ["intruder.py"],
                "commands_run": ["pytest -q tests/cloud"],
                "head_sha": "15b881cb4",
                "executor_notes": "different incoming notes must not win",
                "authority_validation": {"outcome": "accepted"},
            }
        ],
    )
    assert target["files_changed"] == ["existing.py"]  # never replaced
    assert target["commands_run"] == ["pytest -q tests/cloud"]  # empty field filled
    assert target["head_sha"] == "15b881cb4"
    # existing notes win; the field-local empty-target guard is preserved
    assert target["executor_notes"] == "existing substantive notes already on target"


def test_authority_accepted_audit_row_backfills_substantive_executor_notes() -> None:
    """A done kind=audit target with empty notes receives the authority-accepted
    entry's substantive executor_notes (occurrence 4c1e5073ca7c: T8_proof)."""
    target = {"id": "T8_proof", "status": "done", "kind": "audit"}
    targets = {"T8_proof": target}
    source_notes = (
        "Verified T8_impl against its contract with the full narrow selector "
        "(1 run of max_runs=2, timeout 120s): "
        "tests/arnold_pipelines/megaplan/test_maintenance_verification.py => "
        "27 passed, 0 failures in 0.16s; byte-matching the T8_impl receipt "
        "baseline (27/27), so no new failures were introduced and no "
        "pre-existing baseline failures were chased. The implementation "
        "satisfies the Plan Step 7 contract: evaluate_verification returns "
        "only the closed outcomes open/unknown/incoherent/failed_control/"
        "verified with typed reasons."
    )
    issues = _merge_entries(
        targets,
        [
            {
                "task_id": "T8_proof",
                "status": "done",
                "executor_notes": source_notes,
                "commands_run": [
                    "timeout 120s python -m pytest tests/arnold_pipelines/megaplan/test_maintenance_verification.py"
                ],
                "head_sha": "43142b0e3",
                "authority_validation": {"outcome": "accepted"},
            }
        ],
    )
    assert target["status"] == "done"  # never demoted
    assert target["executor_notes"] == source_notes  # byte-equal backfill
    assert len(target["executor_notes"].strip()) >= 100  # audit evidence shape
    assert target["commands_run"]
    from arnold_pipelines.megaplan.execute.quality import _has_audit_or_research_evidence

    assert _has_audit_or_research_evidence(target)
    assert any("status preserved; missing terminal evidence backfilled" in i for i in issues)


def test_authority_rejected_audit_row_notes_do_not_reach_scoped_validator(tmp_path: Path) -> None:
    """Scoped-validator integration: a rejected or quarantined row with long
    notes must NOT reach the merge backfill even when terminal (codex §B)."""
    import pytest as _pytest

    from arnold_pipelines.megaplan.execute.merge import (
        _merge_scoped_batch_artifact_through_validator,
    )

    for outcome, reason in (
        ("rejected", "grant_denied"),
        ("quarantined", "missing_dispatch_identity"),
    ):
        state = {
            "name": "megaplan-run",
            "created_at": "2026-08-17T00:00:00Z",
            "current_state": "finalized",
            "iteration": 3,
            "config": {"mode": "code"},
            "sessions": {},
            "history": [],
            "meta": {},
            "plan_versions": [{"hash": "sha256:plan-revision"}],
            "active_step": {"run_id": "coordinator-attempt", "attempt": 2},
        }
        finalize_data = {
            "tasks": [{"id": "T8_proof", "status": "done", "kind": "audit"}],
            "sense_checks": [],
            "user_actions": [],
        }
        from arnold_pipelines.megaplan.execute.batch import (
            _prepare_scoped_batch_checkpoint,
        )

        artifact_path = _prepare_scoped_batch_checkpoint(
            tmp_path / outcome,
            batch_number=7,
            task_ids=["T8_proof"],
            sense_check_ids=[],
            state=state,
            finalize_data=finalize_data,
        )
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        payload["task_updates"] = [
            {
                "task_id": "T8_proof",
                "status": "done",
                "executor_notes": "x" * 300,  # long notes, but not authority-accepted
                "files_changed": [],
                "commands_run": ["pytest -q tests/cloud"],
            }
        ]
        # Force the validator to reject/quarantine this row (no valid envelope).
        artifact_path.write_text(json.dumps(payload), encoding="utf-8")
        result = _merge_scoped_batch_artifact_through_validator(
            plan_dir=tmp_path / outcome,
            artifact_path=artifact_path,
            payload=payload,
            finalize_data=finalize_data,
            known_task_ids=["T8_proof"],
            known_sense_check_ids=[],
            mode="code",
            state=state,
            preserve_accepted=True,
            require_dispatch_wbc=False,
        )
        # Either quarantined (never merged) or merged without notes leaking.
        if result.quarantine is not None:
            continue
        task = finalize_data["tasks"][0]
        assert task.get("executor_notes") is None
        assert task.get("commands_run") is None


def test_replay_backfills_audit_notes_via_scoped_enveloped_row(tmp_path: Path) -> None:
    """End-to-end replay: a scoped, enveloped batch-7 done update for an
    audit-kind target lands substantive executor_notes and the per-kind quality
    predicate passes — the recovery-critical regression for T8_proof."""
    state = {
        "name": "megaplan-run",
        "created_at": "2026-08-17T00:00:00Z",
        "current_state": "finalized",
        "iteration": 3,
        "config": {"mode": "code"},
        "sessions": {},
        "history": [],
        "meta": {},
        "plan_versions": [{"hash": "sha256:plan-revision"}],
        "active_step": {"run_id": "coordinator-attempt", "attempt": 2},
    }
    finalize_data = {
        "tasks": [
            {"id": "T8_proof", "status": "done", "kind": "audit"},
            {"id": "T9", "status": "done"},
        ],
        "sense_checks": [],
        "user_actions": [],
    }
    source_notes = (
        "Verified T8_impl against its contract with the full narrow selector: "
        "27 passed, 0 failures; byte-matching the T8_impl receipt baseline "
        "(27/27); no new failures introduced; the harness-owned post-execute "
        "verification remains authoritative; the suite was not looped. The "
        "implementation satisfies the Plan Step 7 contract with typed reasons."
    )
    artifact_path = _prepare_scoped_batch_checkpoint(
        tmp_path,
        batch_number=7,
        task_ids=["T8_proof"],
        sense_check_ids=[],
        state=state,
        finalize_data=finalize_data,
    )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    identity = DispatchIdentity.create(
        dispatch_id="megaplan-run:execute:batch:7:8e8a64d621ef",
        run_id="megaplan-run",
        run_revision="sha256:plan-revision",
        coordinator_attempt_id="coordinator-attempt",
        fence_token=2,
        subject_ids=("T8_proof",),
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest="T8_proof-prerequisite-digest",
        worker_id="megaplan-execute-batch-7",
    )
    entry = {
        "task_id": "T8_proof",
        "status": "done",
        "executor_notes": source_notes,
        "files_changed": [],
        "commands_run": [
            "timeout 120s python -m pytest tests/arnold_pipelines/megaplan/test_maintenance_verification.py"
        ],
        "head_sha": "43142b0e3",
    }
    evidence = EvidenceEnvelope(
        evidence_id="T8_proof:evidence",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        evidence_type="megaplan.task_update",
        source="test",
        payload={"entry": entry},
    )
    attempt = TaskAttempt(
        attempt_id="T8_proof:attempt",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        subject_id="T8_proof",
        grant_id=identity.dispatch_id,
        coordinator_attempt_id=identity.coordinator_attempt_id,
        fence_token=identity.fence.token,
        ordinal=1,
    )
    claim = TaskClaim(
        claim_id="T8_proof:claim",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        subject_id="T8_proof",
        attempt_id=attempt.attempt_id,
        grant_id=identity.dispatch_id,
        coordinator_attempt_id=identity.coordinator_attempt_id,
        fence_token=identity.fence.token,
        claim_type=TASK_COMPLETION_CLAIM,
        evidence_ids=(evidence.evidence_id,),
        idempotency_key="T8_proof:claim",
        payload={"entry": entry},
    )
    envelope = ResultEnvelope(
        dispatch=identity,
        attempt=attempt,
        claim=claim,
        evidence=(evidence,),
    )
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
    payload[DISPATCH_IDENTITY_KEY] = identity.to_dict()
    payload[RESULT_ENVELOPES_KEY] = [envelope.to_dict()]
    payload["task_updates"] = [entry]
    payload["sense_check_acknowledgments"] = []
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    _replay_proven_batch_artifacts(
        plan_dir=tmp_path,
        finalize_data=finalize_data,
        known_task_ids=["T8_proof", "T9"],
        known_sense_check_ids=[],
        mode="code",
        state=state,
    )
    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    assert tasks["T8_proof"]["status"] == "done"
    assert tasks["T8_proof"]["executor_notes"] == source_notes
    assert len(tasks["T8_proof"]["executor_notes"].strip()) >= 100
    assert tasks["T8_proof"]["commands_run"]
    from arnold_pipelines.megaplan.execute.quality import _has_audit_or_research_evidence

    assert _has_audit_or_research_evidence(tasks["T8_proof"])
