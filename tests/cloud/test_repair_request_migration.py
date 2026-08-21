from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from argparse import Namespace

from arnold_pipelines.megaplan.cloud.cli import run_cloud_cli
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_requests


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    # Every state-writing test uses these disposable roots, never a project or
    # candidate/live runtime root.
    source = tmp_path / "disposable-source" / ".megaplan" / "repair-queue"
    target = tmp_path / "disposable-target" / ".megaplan" / "repair-queue"
    assert "disposable-source" in str(source)
    assert "disposable-target" in str(target)
    assert "/workspace" not in str(source)
    assert "/workspace" not in str(target)
    return source, target


def _seed(source: Path, count: int) -> list[dict[str, object]]:
    request_dir = source / "requests"
    request_dir.mkdir(parents=True)
    records = []
    for index in range(count):
        record = {
            "schema_version": 1,
            "kind": "repair_request",
            "request_id": f"request-{index}",
            "problem_signature": {"blocked_task_id": f"T{index}"},
        }
        (request_dir / f"{index:03d}.json").write_text(
            json.dumps(record, sort_keys=True), encoding="utf-8"
        )
        records.append(record)
    return records


def _request(source: Path, target: Path, *, migration_id: str = "migration-1", max_requests: int = 100):
    return repair_requests.MigrationRequest.for_roots(
        migration_id=migration_id,
        source_queue_root=source,
        target_queue_root=target,
        max_requests=max_requests,
        requester_identity="operator:test",
        request_timestamp="2026-08-21T00:00:00Z",
    )


def test_operator_request_retains_originals_and_replay_is_noop(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    _seed(source, 2)
    request = _request(source, target)

    receipt = repair_requests.migrate_stranded_requests(request)
    replay = repair_requests.migrate_stranded_requests(request)

    assert isinstance(receipt, repair_requests.MigrationReceipt)
    assert receipt.terminal_state == "completed"
    assert receipt.request_digest == repair_requests.migration_request_digest(request)
    assert receipt.fence_epoch == replay.fence_epoch
    assert receipt.receipt_digest == replay.receipt_digest
    assert receipt.adopted_request_ids == ("request-0", "request-1")
    assert receipt.retained_original_proof["all_adopted_originals_retained"] is True
    assert sorted(path.name for path in (source / "requests").glob("*.json")) == [
        "000.json",
        "001.json",
    ]
    assert sorted(path.name for path in (target / "requests").glob("*.json")) == [
        "000.json",
        "001.json",
    ]


def test_concurrent_operator_attempts_serialize_to_one_receipt(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    _seed(source, 4)
    request = _request(source, target)

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: repair_requests.migrate_stranded_requests(request), range(2)))

    assert receipts[0].receipt_digest == receipts[1].receipt_digest
    assert receipts[0].fence_epoch == receipts[1].fence_epoch
    assert len(list((target / "requests").glob("*.json"))) == 4
    assert len(list((target / repair_requests.MIGRATION_STORE_DIR_NAME).rglob("*.json"))) >= 2


def test_partial_migration_resumes_after_mid_item_interruption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, target = _roots(tmp_path)
    _seed(source, 1)
    request = _request(source, target)
    original_persist = repair_requests._migration_persist_state
    calls = 0

    def fail_after_initial_receipt(path: Path, state: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated interruption after target publication")
        return original_persist(path, state)

    monkeypatch.setattr(repair_requests, "_migration_persist_state", fail_after_initial_receipt)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        repair_requests.migrate_stranded_requests(request)
    monkeypatch.setattr(repair_requests, "_migration_persist_state", original_persist)

    resumed = repair_requests.migrate_stranded_requests(request)
    assert resumed.terminal_state == "completed"
    assert resumed.adopted_request_ids == ("request-0",)
    assert (source / "requests" / "000.json").is_file()
    assert (target / "requests" / "000.json").is_file()


def test_max_requests_is_bounded_and_resume_keeps_high_water_mark(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    _seed(source, 3)
    request = _request(source, target, max_requests=2)

    first = repair_requests.migrate_stranded_requests(request)
    assert first.terminal_state == "partial"
    assert len(first.adopted_request_ids) == 2
    assert len(list((target / "requests").glob("*.json"))) == 2
    high_water_mark = first.source_high_water_mark

    second = repair_requests.migrate_stranded_requests(request)
    assert second.terminal_state == "completed"
    assert second.source_high_water_mark == high_water_mark
    assert len(second.adopted_request_ids) == 3
    assert len(list((target / "requests").glob("*.json"))) == 3

def test_mismatched_identity_is_rejected_before_any_write(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    _seed(source, 1)
    good = _request(source, target)

    # Constructing a changed identity with the old digest must fail closed.
    with pytest.raises(repair_requests.MigrationRequestError, match="identity/digest"):
        repair_requests.MigrationRequest(
            migration_id=good.migration_id,
            source_queue_root=good.source_queue_root,
            target_queue_root=good.target_queue_root,
            source_identity="wrong-source",
            source_digest=good.source_digest,
            target_identity=good.target_identity,
            target_digest=good.target_digest,
            max_requests=good.max_requests,
            requester_identity=good.requester_identity,
            request_timestamp=good.request_timestamp,
        )
    assert not (target / "requests").exists()
    assert not (target / repair_requests.MIGRATION_STORE_DIR_NAME).exists()


def test_observer_reads_do_not_trigger_migration(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    _seed(source, 1)

    observed = repair_requests.iter_repair_requests(source)

    assert [item["request_id"] for item in observed] == ["request-0"]
    assert not (target / "requests").exists()
    assert not (target / repair_requests.MIGRATION_STORE_DIR_NAME).exists()

def test_only_explicit_operator_cli_invokes_migration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source, target = _roots(tmp_path)
    _seed(source, 1)
    request = _request(source, target, migration_id="cli-migration")
    request_path = tmp_path / "operator-request.json"
    request_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")

    result = run_cloud_cli(
        tmp_path,
        Namespace(cloud_action="migrate-repair-requests", request=str(request_path)),
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["success"] is True
    assert output["action"] == "migrate-repair-requests"
    assert output["receipt"]["terminal_state"] == "completed"
