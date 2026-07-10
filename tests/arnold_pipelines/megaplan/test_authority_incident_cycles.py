from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import execute_batch_artifact_path
from arnold_pipelines.megaplan.authority.batch_scope import BATCH_SCOPE_KEY, BatchScope
from arnold_pipelines.megaplan.execute.batch import _replay_proven_batch_artifacts
from arnold_pipelines.megaplan.execute.merge import reconcile_latest_execution_batch


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "runauthority"
    / "vibecomfy_split_authority.json"
)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _write_finalize(plan_dir: Path, fixture: dict[str, Any]) -> None:
    (plan_dir / "finalize.json").write_text(
        json.dumps(copy.deepcopy(fixture["finalize"])),
        encoding="utf-8",
    )


def _write_dispatch(plan_dir: Path, dispatch: dict[str, Any]) -> Path:
    scope = BatchScope.create(
        batch_number=dispatch["batch_number"],
        task_ids=dispatch["task_ids"],
        sense_check_ids=dispatch["sense_check_ids"],
    )
    payload = copy.deepcopy(dispatch["payload"])
    payload[BATCH_SCOPE_KEY] = scope.to_dict()
    path = execute_batch_artifact_path(
        plan_dir,
        dispatch["batch_number"],
        dispatch["task_ids"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_legacy(plan_dir: Path, legacy: dict[str, Any]) -> Path:
    path = plan_dir / f"execution_batch_{legacy['batch_number']}.json"
    path.write_text(json.dumps(copy.deepcopy(legacy["payload"])), encoding="utf-8")
    return path


def _records_by_id(finalize: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {record["id"]: record for record in finalize[key]}


def _quarantines(plan_dir: Path) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
    ]
    return [
        record["payload"]["quarantine"]
        for record in records
        if record.get("kind") == "authority_divergence"
        and isinstance(record.get("payload", {}).get("quarantine"), dict)
    ]


def test_complete_replay_freezes_split_authority_corruption_cycle(tmp_path: Path) -> None:
    fixture = _fixture()
    finalize = copy.deepcopy(fixture["finalize"])
    dispatch_paths = [_write_dispatch(tmp_path, item) for item in fixture["dispatches"]]
    legacy_path = _write_legacy(tmp_path, fixture["legacy"])

    replayed = _replay_proven_batch_artifacts(
        plan_dir=tmp_path,
        finalize_data=finalize,
        known_task_ids=["T1", "T2", "T3"],
        known_sense_check_ids=["SC1", "SC2", "SC3"],
        mode="creative",
        state={"config": {"mode": "creative"}},
    )

    tasks = _records_by_id(finalize, "tasks")
    checks = _records_by_id(finalize, "sense_checks")
    assert len(replayed) == 2
    assert tasks["T1"]["status"] == "done"
    assert tasks["T1"]["sections_written"] == ["allowed_one"]
    assert tasks["T2"]["status"] == "blocked"
    assert tasks["T2"]["sections_written"] == ["allowed_two"]
    assert tasks["T3"] == fixture["finalize"]["tasks"][2]
    assert checks["SC1"]["executor_note"] == "batch one proven"
    assert checks["SC2"]["executor_note"] == "batch two proven"
    assert checks["SC3"]["executor_note"] == "unchanged"
    assert all(path.is_file() for path in dispatch_paths)

    quarantines = _quarantines(tmp_path)
    assert len(quarantines) == 1
    assert quarantines[0]["reason"] == "missing_batch_scope"
    assert quarantines[0]["source_path"] == str(legacy_path)
    assert quarantines[0]["message"]


def test_failure_boundary_reconcile_obeys_scope_and_quarantines_legacy(
    tmp_path: Path,
) -> None:
    fixture = _fixture()
    _write_finalize(tmp_path, fixture)
    _write_dispatch(tmp_path, fixture["dispatches"][1])

    reconciled = reconcile_latest_execution_batch(
        tmp_path,
        {"config": {"mode": "creative"}},
    )

    finalize_path = tmp_path / "finalize.json"
    after_scoped = json.loads(finalize_path.read_text(encoding="utf-8"))
    tasks = _records_by_id(after_scoped, "tasks")
    checks = _records_by_id(after_scoped, "sense_checks")
    assert reconciled["reconciled"] is True
    assert reconciled["total_task_count"] == 1
    assert reconciled["total_sense_check_count"] == 1
    assert tasks["T1"] == fixture["finalize"]["tasks"][0]
    assert tasks["T2"]["status"] == "blocked"
    assert tasks["T3"] == fixture["finalize"]["tasks"][2]
    assert checks["SC1"]["executor_note"] == ""
    assert checks["SC2"]["executor_note"] == "batch two proven"
    assert checks["SC3"]["executor_note"] == "unchanged"

    legacy_path = _write_legacy(tmp_path, fixture["legacy"])
    before_legacy = finalize_path.read_bytes()
    quarantined = reconcile_latest_execution_batch(
        tmp_path,
        {"config": {"mode": "creative"}},
    )

    assert quarantined["reconciled"] is False
    assert quarantined["authority_status"] == "quarantined"
    assert quarantined["quarantine"]["source_path"] == str(legacy_path)
    assert quarantined["quarantine"]["reason"] == "missing_batch_scope"
    assert finalize_path.read_bytes() == before_legacy
    assert _quarantines(tmp_path) == [quarantined["quarantine"]]
