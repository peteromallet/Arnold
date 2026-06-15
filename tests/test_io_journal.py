from __future__ import annotations

import json
import os
import time
from pathlib import Path

from arnold.pipelines.megaplan._core.io import (
    append_framed_json_transaction,
    commit_journal_transaction,
    framed_json_record_bytes,
    journal_blob_promotion,
    journal_bytes_write,
    journal_event_log,
    journal_text_write,
    prepare_journal_transaction,
    read_committed_framed_json_records,
    recover_journal,
    scrub_stale_staging_files,
    write_journal_commit_marker,
)


def test_framed_json_scanner_ignores_incomplete_tail(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    append_framed_json_transaction(
        events_path,
        "tx-1",
        [{"event_type": "status_changed", "summary": "committed"}],
    )

    with events_path.open("ab") as handle:
        handle.write(framed_json_record_bytes({"tx_id": "tx-2", "event_type": "_tx_begin"}))
        partial = framed_json_record_bytes({"tx_id": "tx-2", "event_type": "partial", "summary": "tail"})
        handle.write(partial[:-3])

    assert read_committed_framed_json_records(events_path) == [
        {"tx_id": "tx-1", "event_type": "status_changed", "summary": "committed"},
    ]


def test_recover_journal_discards_uncommitted_prepare(tmp_path: Path) -> None:
    root = tmp_path / "epic"
    target = root / "state.json"
    events_path = root / "events.jsonl"

    prepare_journal_transaction(
        root,
        "tx-discard",
        writes=[journal_text_write(target, json.dumps({"status": "pending"}) + "\n", tx_id="tx-discard")],
        event_logs=[journal_event_log(events_path, [{"event_type": "pending", "summary": "ignored"}])],
    )

    result = recover_journal(root)

    assert result["discarded"] == ["tx-discard"]
    assert result["replayed"] == []
    assert not target.exists()
    assert read_committed_framed_json_records(events_path) == []


def test_recover_journal_replays_committed_transaction(tmp_path: Path) -> None:
    root = tmp_path / "epic"
    target = root / "state.json"
    events_path = root / "events.jsonl"

    prepare_journal_transaction(
        root,
        "tx-replay",
        writes=[journal_text_write(target, json.dumps({"status": "done"}) + "\n", tx_id="tx-replay")],
        event_logs=[journal_event_log(events_path, [{"event_type": "done", "summary": "replayed"}])],
    )
    write_journal_commit_marker(root, "tx-replay")

    result = recover_journal(root)

    assert result["replayed"] == ["tx-replay"]
    assert json.loads(target.read_text(encoding="utf-8")) == {"status": "done"}
    assert read_committed_framed_json_records(events_path) == [
        {"tx_id": "tx-replay", "event_type": "done", "summary": "replayed"},
    ]
    assert not any((root / "_journal").glob("*.prepare.json"))


def test_recover_journal_compacts_oversized_state_change_event(tmp_path: Path) -> None:
    root = tmp_path / "epic"
    events_path = root / "events.jsonl"
    huge_state = {"event": {"kind": "state_written", "payload": "x" * (2 * 1024 * 1024)}}

    prepare_journal_transaction(
        root,
        "tx-large-event",
        event_logs=[
            journal_event_log(
                events_path,
                [
                    {
                        "event_type": "state_change",
                        "summary": "state_written emitted",
                        "post_state": huge_state,
                    }
                ],
            )
        ],
    )
    write_journal_commit_marker(root, "tx-large-event")

    result = recover_journal(root)

    assert result["replayed"] == ["tx-large-event"]
    [record] = read_committed_framed_json_records(events_path)
    assert record["event_type"] == "state_change"
    assert record["post_state"]["_omitted_for_framed_log"] is True
    assert record["post_state"]["original_size_bytes"] > 2 * 1024 * 1024
    assert record["post_state"]["sha256"]


def test_commit_journal_transaction_promotes_blob_and_metadata(tmp_path: Path) -> None:
    root = tmp_path / "epic"
    blob_dir = root / "blobs" / "blob-1"
    payload = b"hello blob"
    metadata = {"blob_id": "blob-1", "content_type": "text/plain"}

    prepare_journal_transaction(
        root,
        "tx-blob",
        blobs=[journal_blob_promotion(blob_dir, payload, extension="txt", metadata=metadata)],
        writes=[journal_bytes_write(root / "receipt.bin", b"ok", tx_id="tx-blob")],
    )

    commit_journal_transaction(root, "tx-blob")

    assert (blob_dir / "data.txt").read_bytes() == payload
    assert json.loads((blob_dir / "meta.json").read_text(encoding="utf-8")) == metadata
    assert not (blob_dir / "data.staging").exists()
    assert (root / "receipt.bin").read_bytes() == b"ok"


def test_scrub_stale_staging_files_removes_old_entries_only(tmp_path: Path) -> None:
    blobs_root = tmp_path / "blobs"
    old_staging = blobs_root / "old" / "data.staging"
    fresh_staging = blobs_root / "fresh" / "data.staging"
    old_staging.parent.mkdir(parents=True)
    fresh_staging.parent.mkdir(parents=True)
    old_staging.write_bytes(b"old")
    fresh_staging.write_bytes(b"fresh")

    stale_time = time.time() - 7200
    os.utime(old_staging, (stale_time, stale_time))

    removed = scrub_stale_staging_files(blobs_root)

    assert removed == [old_staging]
    assert not old_staging.exists()
    assert fresh_staging.exists()
