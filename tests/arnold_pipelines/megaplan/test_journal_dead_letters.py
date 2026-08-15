from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan._core import io as journal_io
from arnold_pipelines.megaplan.store import file as store_file


def _dead_letters(root: Path) -> list[dict]:
    payloads = []
    for path in sorted(journal_io.journal_dead_letter_dir(root).glob("*.json")):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def test_commit_failure_writes_replayable_dead_letter_and_alert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "records" / "item.json"
    tx_id = "tx-dead-letter"
    journal_io.prepare_journal_transaction(
        tmp_path,
        tx_id,
        writes=[journal_io.journal_bytes_write(target, b'{"ok": true}', tx_id=tx_id)],
    )

    def fail_rename(_src: Path, _dest: Path) -> None:
        raise RuntimeError("simulated apply failure")

    monkeypatch.setattr(journal_io, "_rename_with_fsync", fail_rename)

    with pytest.raises(RuntimeError, match="simulated apply failure"):
        journal_io.commit_journal_transaction(tmp_path, tx_id)

    dead_letters = _dead_letters(tmp_path)
    assert len(dead_letters) == 1
    dead_letter = dead_letters[0]
    assert dead_letter["kind"] == "megaplan.journal.dead_letter"
    assert dead_letter["tx_id"] == tx_id
    assert dead_letter["phase"] == "commit"
    assert dead_letter["target_paths"] == [str(target)]
    assert dead_letter["operation_metadata"]["writes"][0]["target_path"] == str(target)
    assert dead_letter["source_digests"]["writes"][0]["content_sha256"].startswith("sha256:")
    assert dead_letter["prepare_payload"]["writes"][0]["content_storage"] == "base64"
    assert dead_letter["exception"] == {
        "class": "RuntimeError",
        "message": "simulated apply failure",
    }

    alert = json.loads(
        journal_io.journal_dead_letter_alert_path(tmp_path).read_text(encoding="utf-8")
    )
    assert alert["kind"] == "megaplan.journal.dead_letter_alert"
    assert alert["tx_id"] == tx_id
    assert alert["artifact"].endswith(".json")
    assert Path(alert["artifact"]).is_file()
    assert json.loads(Path(alert["artifact"]).read_text(encoding="utf-8")) == dead_letter


def test_file_store_recovery_failure_writes_dead_letter_alert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_recover(_root: Path) -> dict[str, list[str]]:
        raise RuntimeError("simulated recovery failure")

    monkeypatch.setattr(store_file, "recover_journal", fail_recover)

    with pytest.raises(RuntimeError, match="simulated recovery failure"):
        store_file.FileStore(tmp_path)

    dead_letters = _dead_letters(tmp_path)
    assert len(dead_letters) == 1
    dead_letter = dead_letters[0]
    assert dead_letter["tx_id"] == "file-store-recovery"
    assert dead_letter["phase"] == "file_store_recovery"
    assert dead_letter["prepare_payload"]["operation"] == "FileStore._recover_all_journals"
    assert dead_letter["exception"]["class"] == "RuntimeError"

    alert = json.loads(
        journal_io.journal_dead_letter_alert_path(tmp_path).read_text(encoding="utf-8")
    )
    assert alert["phase"] == "file_store_recovery"
    assert alert["exception"]["message"] == "simulated recovery failure"


def test_successful_prepare_and_commit_do_not_write_dead_letter(
    tmp_path: Path,
) -> None:
    target = tmp_path / "records" / "item.json"
    tx_id = "tx-success"
    journal_io.prepare_journal_transaction(
        tmp_path,
        tx_id,
        writes=[journal_io.journal_bytes_write(target, b'{"ok": true}', tx_id=tx_id)],
    )

    assert journal_io.journal_prepare_path(tmp_path, tx_id).is_file()
    journal_io.commit_journal_transaction(tmp_path, tx_id)

    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}
    assert not journal_io.journal_prepare_path(tmp_path, tx_id).exists()
    assert not journal_io.journal_commit_path(tmp_path, tx_id).exists()
    assert not journal_io.journal_dead_letter_alert_path(tmp_path).exists()
    assert _dead_letters(tmp_path) == []


def test_recovery_replays_committed_transaction_without_dead_letter(
    tmp_path: Path,
) -> None:
    target = tmp_path / "records" / "item.json"
    tx_id = "tx-replay"
    journal_io.prepare_journal_transaction(
        tmp_path,
        tx_id,
        writes=[journal_io.journal_bytes_write(target, b'{"ok": true}', tx_id=tx_id)],
    )
    journal_io.write_journal_commit_marker(tmp_path, tx_id)

    result = journal_io.recover_journal(tmp_path)

    assert result["replayed"] == [tx_id]
    assert result["discarded"] == []
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}
    assert not journal_io.journal_prepare_path(tmp_path, tx_id).exists()
    assert not journal_io.journal_commit_path(tmp_path, tx_id).exists()
    assert not journal_io.journal_dead_letter_alert_path(tmp_path).exists()
    assert _dead_letters(tmp_path) == []


def test_recovery_discards_uncommitted_transaction_without_dead_letter(
    tmp_path: Path,
) -> None:
    target = tmp_path / "records" / "item.json"
    tx_id = "tx-discard"
    journal_io.prepare_journal_transaction(
        tmp_path,
        tx_id,
        writes=[journal_io.journal_bytes_write(target, b'{"ok": true}', tx_id=tx_id)],
    )

    result = journal_io.recover_journal(tmp_path)

    assert result["replayed"] == []
    assert result["discarded"] == [tx_id]
    assert not target.exists()
    assert not journal_io.journal_prepare_path(tmp_path, tx_id).exists()
    assert not journal_io.journal_commit_path(tmp_path, tx_id).exists()
    assert not journal_io.journal_dead_letter_alert_path(tmp_path).exists()
    assert _dead_letters(tmp_path) == []
