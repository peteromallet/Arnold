from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.observability import event_checkpoint
from arnold_pipelines.megaplan.observability.event_checkpoint import (
    EventCheckpointError,
    read_bounded_event_projection,
)


def _write_events(plan_dir: Path, count: int, *, start: int = 0) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    with (plan_dir / "events.ndjson").open("ab") as handle:
        for seq in range(start, start + count):
            event = {
                "seq": seq,
                "kind": "phase_start" if seq % 2 == 0 else "phase_end",
                "phase": "execute",
                "ts_utc": f"2026-07-31T00:00:{seq % 60:02d}+00:00",
                "payload": {"index": seq},
            }
            handle.write(json.dumps(event, sort_keys=True).encode() + b"\n")
    (plan_dir / ".events.seq").write_text(str(start + count - 1), encoding="ascii")


def test_cold_and_incremental_projection_match_full_event_order(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    _write_events(plan_dir, 40)

    cold = read_bounded_event_projection(plan_dir, max_tail_events=100)
    expected = [
        json.loads(line)
        for line in (plan_dir / "events.ndjson").read_text().splitlines()
    ]

    assert list(cold.events) == expected
    assert cold.record_count == 40
    assert cold.last_seq == 39
    assert cold.receipt["mode"] == "cold_rebuild"
    assert cold.receipt["fold_count"] == 40

    _write_events(plan_dir, 3, start=40)
    warm = read_bounded_event_projection(plan_dir, max_tail_events=100)

    assert [event["seq"] for event in warm.events] == list(range(43))
    assert warm.record_count == 43
    assert warm.last_seq == 42
    assert warm.receipt["mode"] == "warm"
    assert warm.receipt["fold_count"] == 3
    assert warm.receipt["bytes_read"] < 1_024


def test_corrupt_checkpoint_fails_closed_or_rebuilds_explicitly(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    _write_events(plan_dir, 5)
    read_bounded_event_projection(plan_dir)
    checkpoint = plan_dir / ".events.supervision-checkpoint.json"
    checkpoint.write_text("{broken", encoding="utf-8")

    with pytest.raises(EventCheckpointError, match="checkpoint_corrupt"):
        read_bounded_event_projection(plan_dir, allow_rebuild=False)

    rebuilt = read_bounded_event_projection(plan_dir, allow_rebuild=True)
    assert rebuilt.receipt["mode"] == "cold_rebuild"
    assert rebuilt.receipt["rebuild_reason"] == "checkpoint_corrupt"
    assert rebuilt.record_count == 5


def test_stale_cursor_and_cross_incarnation_are_rejected(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    _write_events(plan_dir, 8)
    read_bounded_event_projection(plan_dir)
    journal = plan_dir / "events.ndjson"
    journal.write_bytes(journal.read_bytes()[:40])

    with pytest.raises(EventCheckpointError, match="cursor_beyond_journal"):
        read_bounded_event_projection(plan_dir, allow_rebuild=False)

    read_bounded_event_projection(plan_dir, allow_rebuild=True)
    (plan_dir / ".events.store-incarnation").write_text(
        "restored-store\n", encoding="ascii"
    )
    with pytest.raises(EventCheckpointError, match="store_incarnation_mismatch"):
        read_bounded_event_projection(plan_dir, allow_rebuild=False)


@pytest.mark.slow
def test_60k_710mb_sparse_history_warm_read_has_explicit_ceilings(
    tmp_path: Path,
) -> None:
    """Exercise the M11 scale without allocating a 710 MB Python object."""

    plan_dir = tmp_path / "plan"
    event_count = 60_137
    _write_events(plan_dir, event_count)
    initial = read_bounded_event_projection(plan_dir, max_tail_events=32)
    assert initial.record_count == event_count

    journal = plan_dir / "events.ndjson"
    target_size = 710 * 1024 * 1024
    with journal.open("r+b") as handle:
        handle.seek(target_size - 1)
        handle.write(b"\n")

    # Model a durable checkpoint published after a one-time cold compaction:
    # keep the canonical fold result, advance its byte cursor over a sparse
    # historical segment, and recompute the content-addressed anchor/digest.
    checkpoint_path = plan_dir / ".events.supervision-checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    checkpoint["source_offset"] = target_size
    (
        checkpoint["anchor_start"],
        checkpoint["anchor_digest"],
        checkpoint["anchor_length"],
    ) = event_checkpoint._anchor(journal, target_size)
    checkpoint["checkpoint_digest"] = event_checkpoint._checkpoint_digest(checkpoint)
    event_checkpoint._atomic_write(checkpoint_path, checkpoint)

    with journal.open("ab") as handle:
        handle.write(
            json.dumps(
                {
                    "seq": event_count,
                    "kind": "phase_start",
                    "phase": "review",
                    "ts_utc": "2026-07-31T01:00:00+00:00",
                    "payload": {},
                }
            ).encode()
            + b"\n"
        )

    warm = read_bounded_event_projection(plan_dir, max_tail_events=32)
    assert journal.stat().st_size >= target_size
    assert warm.record_count == event_count + 1
    assert warm.last_seq == event_count
    assert warm.receipt["mode"] == "warm"
    assert warm.receipt["fold_count"] == 1
    assert warm.receipt["bytes_read"] < 1_024
    assert warm.receipt["wall_time_seconds"] < 2.0
    assert warm.receipt["rss_delta_bytes"] < 64 * 1024 * 1024
