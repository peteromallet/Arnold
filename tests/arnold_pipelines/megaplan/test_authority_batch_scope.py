from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.authority.batch_scope import (
    BATCH_SCOPE_KEY,
    BatchScope,
    resolve_batch_scope,
)
from arnold_pipelines.megaplan.execute.batch import (
    _prepare_scoped_batch_checkpoint,
    _replay_proven_batch_artifacts,
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
