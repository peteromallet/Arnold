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


def test_no_pending_replay_uses_each_proven_scope_and_quarantines_legacy(
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
    assert len(replayed) == 2
    assert tasks["T1"]["status"] == "blocked"
    assert tasks["T1"]["executor_notes"] == "proven batch-one result"
    assert tasks["T2"]["status"] == "done"
    assert tasks["T3"] == {"id": "T3", "status": "done"}
    assert checks["SC1"]["executor_note"] == "batch one proven"
    assert checks["SC2"]["executor_note"] == "batch two proven"
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
