from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

import megaplan.worktrees.registry as registry_module
from megaplan.worktrees import (
    ANCHORED_TAIL_TRUNCATION,
    BROKEN_CHAIN,
    DIGEST_MISMATCH,
    LOCK_FAILURE,
    MALFORMED_JSON,
    MISSING_ANCHOR,
    MISSING_REGISTRY,
    WRITE_FAILURE,
    RegistryError,
    IDENTITY_MISMATCH,
    append_registry_entry,
    custody_paths,
    read_registry_entries,
    validate_registry,
)


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def test_registry_appends_canonical_hash_linked_entries_and_head(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    first = append_registry_entry(
        project_dir,
        "run-1",
        "task_started",
        {"task_id": "T6"},
        task_id="T6",
        timestamp="2026-05-21T20:00:00Z",
    )
    second = append_registry_entry(
        project_dir,
        "run-1",
        "task_finished",
        {"status": "done"},
        task_id="T6",
        timestamp="2026-05-21T20:01:00Z",
    )

    paths = custody_paths(project_dir)
    assert paths.registry_lock("run-1").exists()
    assert first["sequence"] == 1
    assert first["schema_version"] == 2
    assert first["task_key"].startswith("t6-")
    assert "task_id" not in first
    assert first["identity"]["task_key"] == first["task_key"]
    assert first["identity"]["original_task_id_encoding"] == "base64url-utf8-v1"
    assert first["prev_hash"] is None
    assert second["sequence"] == 2
    assert second["task_key"] == first["task_key"]
    assert second["prev_hash"] == first["entry_hash"]
    assert second["entry_hash"].startswith("sha256:")

    lines = paths.registry_jsonl("run-1").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(": " not in line for line in lines)
    assert json.loads(lines[0]) == first
    assert json.loads(lines[1]) == second

    head = json.loads(paths.registry_head("run-1").read_text(encoding="utf-8"))
    assert head["entry_count"] == 2
    assert head["head_hash"] == second["entry_hash"]
    assert head["registry_path"] == str(paths.registry_jsonl("run-1"))
    assert head["anchor_digest"].startswith("sha256:")

    validation = validate_registry(project_dir, "run-1")
    assert validation.ok is True
    assert validation.errors == []
    assert read_registry_entries(project_dir, "run-1") == [first, second]


def test_registry_concurrent_appends_are_serialized_under_writer_lock(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"

    def append_one(index: int) -> dict:
        return append_registry_entry(
            project_dir,
            "run-1",
            "task_event",
            {"index": index},
            task_id=f"T{index}",
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        written = list(pool.map(append_one, range(12)))

    validation = validate_registry(project_dir, "run-1")
    paths = custody_paths(project_dir)
    head = json.loads(paths.registry_head("run-1").read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.errors == []
    assert len(validation.entries) == 12
    assert sorted(entry["payload"]["index"] for entry in validation.entries) == list(range(12))
    assert all("task_key" in entry and "task_id" not in entry for entry in validation.entries)
    assert [entry["sequence"] for entry in validation.entries] == list(range(1, 13))
    assert validation.entries[0]["prev_hash"] is None
    for previous, current in zip(validation.entries, validation.entries[1:]):
        assert current["prev_hash"] == previous["entry_hash"]
    assert head["entry_count"] == 12
    assert head["head_hash"] == validation.entries[-1]["entry_hash"]
    assert sorted(entry["entry_hash"] for entry in written) == sorted(
        entry["entry_hash"] for entry in validation.entries
    )


def test_registry_validation_reports_missing_registry_and_anchor(tmp_path: Path) -> None:
    validation = validate_registry(tmp_path / "repo", "run-1")

    assert validation.ok is False
    assert [error.code for error in validation.errors] == [MISSING_REGISTRY, MISSING_ANCHOR]


def test_registry_validation_reports_missing_anchor(tmp_path: Path) -> None:
    paths = custody_paths(tmp_path / "repo")
    paths.registry_jsonl("run-1").parent.mkdir(parents=True)
    paths.registry_jsonl("run-1").write_text("", encoding="utf-8")

    validation = validate_registry(tmp_path / "repo", "run-1")

    assert [error.code for error in validation.errors] == [MISSING_ANCHOR]
    with pytest.raises(RegistryError) as excinfo:
        read_registry_entries(tmp_path / "repo", "run-1")
    assert excinfo.value.code == MISSING_ANCHOR


def test_registry_validation_reports_malformed_registry_json(tmp_path: Path) -> None:
    paths = custody_paths(tmp_path / "repo")
    paths.registry_jsonl("run-1").parent.mkdir(parents=True)
    paths.registry_jsonl("run-1").write_text("{not json}\n", encoding="utf-8")
    paths.registry_head("run-1").write_text('{"entry_count":0,"tail_hash":null}\n', encoding="utf-8")

    validation = validate_registry(tmp_path / "repo", "run-1")

    assert validation.errors[0].code == MALFORMED_JSON
    assert validation.errors[0].line == 1


def test_registry_validation_reports_broken_chain(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    first = append_registry_entry(project_dir, "run-1", "one", {"n": 1})
    second = append_registry_entry(project_dir, "run-1", "two", {"n": 2})
    paths = custody_paths(project_dir)
    second["prev_hash"] = "sha256:" + "0" * 64
    second["entry_hash"] = registry_module._entry_digest(second)
    _write_jsonl(paths.registry_jsonl("run-1"), [first, second])

    validation = validate_registry(project_dir, "run-1")

    assert validation.errors[0].code == BROKEN_CHAIN
    assert validation.errors[0].line == 2


def test_registry_validation_reports_digest_mismatch_for_tampering(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    first = append_registry_entry(project_dir, "run-1", "one", {"n": 1})
    paths = custody_paths(project_dir)
    first["payload"]["n"] = 999
    _write_jsonl(paths.registry_jsonl("run-1"), [first])

    validation = validate_registry(project_dir, "run-1")

    assert validation.errors[0].code == DIGEST_MISMATCH
    assert validation.errors[0].line == 1


def test_registry_validation_reports_digest_mismatch_for_head_anchor_tampering(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    append_registry_entry(project_dir, "run-1", "one", {"n": 1})
    paths = custody_paths(project_dir)
    head = json.loads(paths.registry_head("run-1").read_text(encoding="utf-8"))
    head["registry_path"] = str(paths.registry_jsonl("other-run"))
    paths.registry_head("run-1").write_text(json.dumps(head, sort_keys=True), encoding="utf-8")

    validation = validate_registry(project_dir, "run-1")

    assert validation.errors[0].code == DIGEST_MISMATCH


def test_registry_accepts_legacy_v1_task_id_entries(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    paths = custody_paths(project_dir)
    entry = {
        "schema_version": 1,
        "run_id": "run-1",
        "sequence": 1,
        "timestamp": "2026-05-21T20:00:00Z",
        "entry_type": "legacy",
        "task_id": "T6",
        "prev_hash": None,
        "payload": {},
    }
    entry["entry_hash"] = registry_module._entry_digest(entry)
    _write_jsonl(paths.registry_jsonl("run-1"), [entry])
    registry_module._write_head(
        paths.registry_head("run-1"),
        registry_path=paths.registry_jsonl("run-1"),
        run_id="run-1",
        entry_count=1,
        head_hash=entry["entry_hash"],
        timestamp="2026-05-21T20:00:00Z",
    )

    validation = validate_registry(project_dir, "run-1")

    assert validation.ok is True
    assert validation.entries == [entry]


def test_registry_v2_rejects_raw_top_level_task_id(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    paths = custody_paths(project_dir)
    entry = {
        "schema_version": 2,
        "run_id": "run-1",
        "sequence": 1,
        "timestamp": "2026-05-21T20:00:00Z",
        "entry_type": "bad",
        "task_id": "T6",
        "task_key": "t6-1111111111111111",
        "prev_hash": None,
        "payload": {},
    }
    entry["entry_hash"] = registry_module._entry_digest(entry)
    _write_jsonl(paths.registry_jsonl("run-1"), [entry])
    registry_module._write_head(
        paths.registry_head("run-1"),
        registry_path=paths.registry_jsonl("run-1"),
        run_id="run-1",
        entry_count=1,
        head_hash=entry["entry_hash"],
        timestamp="2026-05-21T20:00:00Z",
    )

    validation = validate_registry(project_dir, "run-1")

    assert validation.ok is False
    assert validation.errors[0].code == IDENTITY_MISMATCH
    assert "task_key" in validation.errors[0].message


def test_registry_validation_reports_anchored_tail_truncation(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    first = append_registry_entry(project_dir, "run-1", "one", {"n": 1})
    append_registry_entry(project_dir, "run-1", "two", {"n": 2})
    paths = custody_paths(project_dir)
    _write_jsonl(paths.registry_jsonl("run-1"), [first])

    validation = validate_registry(project_dir, "run-1")

    assert validation.errors[0].code == ANCHORED_TAIL_TRUNCATION


def test_registry_append_reports_lock_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_flock(_fd: int, _operation: int) -> None:
        raise OSError("lock unavailable")

    monkeypatch.setattr(registry_module.fcntl, "flock", fail_flock)

    with pytest.raises(RegistryError) as excinfo:
        append_registry_entry(tmp_path / "repo", "run-1", "one", {})

    assert excinfo.value.code == LOCK_FAILURE


def test_registry_append_reports_head_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_atomic_write_json(_path: Path, _payload: dict) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(registry_module, "atomic_write_json", fail_atomic_write_json)

    with pytest.raises(RegistryError) as excinfo:
        append_registry_entry(tmp_path / "repo", "run-1", "one", {})

    assert excinfo.value.code == WRITE_FAILURE
