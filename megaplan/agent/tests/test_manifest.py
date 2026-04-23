import json
import multiprocessing
from pathlib import Path

import pytest

import evals.manifest as manifest_module
from evals.manifest import TaskManifest


def _claim_batch_in_process(
    manifest_path: str,
    worker_id: str,
    batch_size: int,
    queue,
) -> None:
    manifest = TaskManifest.load(manifest_path)
    queue.put(manifest.claim_batch(worker_id, batch_size))


def test_create_and_load(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"

    created = TaskManifest.create(manifest_path, ["task-a", "task-b", "task-c"])
    loaded = TaskManifest.load(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert created.lock_path == manifest_path.parent / "manifest.json.lock"
    assert payload["version"] == 1
    assert payload["total_tasks"] == 3
    assert set(payload["tasks"]) == {"task-a", "task-b", "task-c"}
    assert loaded.summary() == {
        "total_tasks": 3,
        "pending": 3,
        "claimed": 0,
        "done": 0,
    }


def test_claim_batch_returns_distinct_pending_tasks(tmp_path: Path) -> None:
    manifest = TaskManifest.create(tmp_path / "manifest.json", ["a", "b", "c", "d", "e"])

    first_claim = manifest.claim_batch("worker-0", 2)
    second_claim = manifest.claim_batch("worker-1", 2)
    payload = json.loads(manifest.path.read_text(encoding="utf-8"))

    assert first_claim == ["a", "b"]
    assert second_claim == ["c", "d"]
    assert set(first_claim).isdisjoint(second_claim)
    assert payload["tasks"]["a"]["status"] == "claimed"
    assert payload["tasks"]["a"]["worker"] == "worker-0"
    assert payload["tasks"]["c"]["worker"] == "worker-1"
    assert manifest.unclaimed_count() == 1


def test_concurrent_claims_use_processes_without_overlap(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    TaskManifest.create(manifest_path, [f"task-{i}" for i in range(6)])

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(
            target=_claim_batch_in_process,
            args=(str(manifest_path), f"worker-{i}", 2, queue),
        )
        for i in range(3)
    ]

    for process in processes:
        process.start()

    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    claimed_batches = [queue.get(timeout=5) for _ in processes]
    claimed_ids = [instance_id for batch in claimed_batches for instance_id in batch]

    assert len(claimed_ids) == 6
    assert len(set(claimed_ids)) == 6
    assert TaskManifest.load(manifest_path).summary()["claimed"] == 6


def test_mark_done_updates_status_and_metadata(tmp_path: Path) -> None:
    manifest = TaskManifest.create(tmp_path / "manifest.json", ["task-a"])

    assert manifest.claim_batch("worker-0", 1) == ["task-a"]
    manifest.mark_done("task-a", "worker-0")
    payload = json.loads(manifest.path.read_text(encoding="utf-8"))

    assert payload["tasks"]["task-a"]["status"] == "done"
    assert payload["tasks"]["task-a"]["worker"] == "worker-0"
    assert "claimed_at" in payload["tasks"]["task-a"]
    assert "done_at" in payload["tasks"]["task-a"]


def test_all_done_tracks_pending_claimed_done_lifecycle(tmp_path: Path) -> None:
    manifest = TaskManifest.create(tmp_path / "manifest.json", ["task-a", "task-b"])

    assert manifest.all_done() is False
    claimed = manifest.claim_batch("worker-0", 2)
    assert claimed == ["task-a", "task-b"]
    assert manifest.all_done() is False

    for instance_id in claimed:
        manifest.mark_done(instance_id, "worker-0")

    assert manifest.all_done() is True


def test_done_task_ids_only_returns_completed_tasks(tmp_path: Path) -> None:
    manifest = TaskManifest.create(tmp_path / "manifest.json", ["task-a", "task-b", "task-c"])

    assert manifest.claim_batch("worker-0", 2) == ["task-a", "task-b"]
    manifest.mark_done("task-a", "worker-0")

    assert manifest.done_task_ids() == {"task-a"}


def test_next_worker_id_advances_from_existing_manifest_workers(tmp_path: Path) -> None:
    manifest = TaskManifest.create(tmp_path / "manifest.json", ["task-a", "task-b", "task-c"])

    assert manifest.claim_batch("worker-0", 1) == ["task-a"]
    assert manifest.claim_batch("worker-2", 1) == ["task-b"]

    assert manifest.next_worker_id() == "worker-3"


def test_requeue_dead_claimed_only_requeues_dead_worker_pids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = TaskManifest.create(tmp_path / "manifest.json", ["task-a", "task-b", "task-c"])
    payload = json.loads(manifest.path.read_text(encoding="utf-8"))
    payload["tasks"]["task-a"] = {"status": "claimed", "worker": "worker-0", "worker_pid": 111}
    payload["tasks"]["task-b"] = {"status": "claimed", "worker": "worker-1", "worker_pid": 222}
    payload["tasks"]["task-c"] = {"status": "done", "worker": "worker-2"}
    manifest.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    pidfile_path = tmp_path / "_pidfile.json"
    pidfile_path.write_text('{"workers": []}\n', encoding="utf-8")
    monkeypatch.setattr(manifest_module, "_pid_alive", lambda pid: pid == 111)

    requeued = manifest.requeue_dead_claimed(pidfile_path)
    updated = json.loads(manifest.path.read_text(encoding="utf-8"))

    assert requeued == ["task-b"]
    assert updated["tasks"]["task-a"]["status"] == "claimed"
    assert updated["tasks"]["task-a"]["worker_pid"] == 111
    assert updated["tasks"]["task-b"]["status"] == "pending"
    assert "worker" not in updated["tasks"]["task-b"]
    assert "worker_pid" not in updated["tasks"]["task-b"]
    assert updated["tasks"]["task-c"]["status"] == "done"


def test_requeue_dead_claimed_requeues_all_claimed_without_pidfile(tmp_path: Path) -> None:
    manifest = TaskManifest.create(tmp_path / "manifest.json", ["task-a", "task-b", "task-c"])
    payload = json.loads(manifest.path.read_text(encoding="utf-8"))
    payload["tasks"]["task-a"] = {"status": "claimed", "worker": "worker-0", "worker_pid": 111}
    payload["tasks"]["task-b"] = {"status": "claimed", "worker": "worker-1", "worker_pid": 222}
    payload["tasks"]["task-c"] = {"status": "done", "worker": "worker-2"}
    manifest.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    requeued = manifest.requeue_dead_claimed(tmp_path / "_missing_pidfile.json")
    updated = json.loads(manifest.path.read_text(encoding="utf-8"))

    assert requeued == ["task-a", "task-b"]
    assert updated["tasks"]["task-a"]["status"] == "pending"
    assert updated["tasks"]["task-b"]["status"] == "pending"
    assert updated["tasks"]["task-c"]["status"] == "done"
