from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.observability.events import (
    event_signature_summary,
    format_signature_line,
)


def _write_events(path: Path, events: list[dict]) -> Path:
    with open(path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    return path


def test_event_signature_summary_counts_kind_reason_pairs(tmp_path: Path) -> None:
    ndjson = _write_events(
        tmp_path / "events.ndjson",
        [
            {"seq": 0, "ts_utc": "2026-07-05T00:21:37+00:00", "kind": "authority_divergence", "payload": {"reason": "stale_evidence:head_mismatch"}},
            {"seq": 1, "ts_utc": "2026-07-05T00:21:38+00:00", "kind": "authority_divergence", "payload": {"reason": "stale_evidence:head_mismatch"}},
            {"seq": 2, "ts_utc": "2026-07-05T00:21:39+00:00", "kind": "authority_divergence", "payload": {"reason": "stale_evidence:head_mismatch"}},
            {"seq": 3, "ts_utc": "2026-07-05T00:22:00+00:00", "kind": "authority_divergence", "payload": {"reason": "pr_stale"}},
            {"seq": 4, "ts_utc": "2026-07-05T00:23:00+00:00", "kind": "llm_call_error", "payload": {"message": "quota exceeded"}},
            {"seq": 5, "ts_utc": "2026-07-05T00:24:00+00:00", "kind": "state_written", "payload": {}},
        ],
    )
    sigs = event_signature_summary(events_path=ndjson)
    assert sigs[0]["kind"] == "authority_divergence"
    assert sigs[0]["reason"] == "stale_evidence:head_mismatch"
    assert sigs[0]["count"] == 3
    assert sigs[0]["last_seq"] == 2
    # descending by count
    assert [s["count"] for s in sigs] == sorted((s["count"] for s in sigs), reverse=True)


def test_event_signature_summary_missing_file_returns_empty(tmp_path: Path) -> None:
    assert event_signature_summary(events_path=tmp_path / "nope.ndjson") == []
    assert event_signature_summary() == []  # neither plan_dir nor events_path


def test_event_signature_summary_malformed_lines_skipped(tmp_path: Path) -> None:
    ndjson = tmp_path / "events.ndjson"
    with open(ndjson, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"seq": 0, "ts_utc": "2026-07-05T00:00:00+00:00", "kind": "x", "payload": {"reason": "r"}}) + "\n")
        fh.write("NOT JSON\n")
        fh.write(json.dumps({"seq": 1, "ts_utc": "2026-07-05T00:00:01+00:00", "kind": "x", "payload": {"reason": "r"}}) + "\n")
    sigs = event_signature_summary(events_path=ndjson)
    assert len(sigs) == 1
    assert sigs[0]["count"] == 2  # malformed line skipped, not fatal


def test_event_signature_summary_since_seq_filters(tmp_path: Path) -> None:
    ndjson = _write_events(
        tmp_path / "events.ndjson",
        [
            {"seq": 1, "ts_utc": "2026-07-05T00:00:01+00:00", "kind": "a", "payload": {"reason": "r"}},
            {"seq": 2, "ts_utc": "2026-07-05T00:00:02+00:00", "kind": "a", "payload": {"reason": "r"}},
            {"seq": 3, "ts_utc": "2026-07-05T00:00:03+00:00", "kind": "b", "payload": {"reason": "r"}},
            {"seq": 4, "ts_utc": "2026-07-05T00:00:04+00:00", "kind": "b", "payload": {"reason": "r"}},
        ],
    )
    sigs = event_signature_summary(events_path=ndjson, since_seq=2)
    assert {s["kind"] for s in sigs} == {"b"}  # only seq 3,4


def test_event_signature_summary_kinds_filter(tmp_path: Path) -> None:
    ndjson = _write_events(
        tmp_path / "events.ndjson",
        [
            {"seq": 0, "ts_utc": "2026-07-05T00:00:00+00:00", "kind": "a", "payload": {"reason": "r"}},
            {"seq": 1, "ts_utc": "2026-07-05T00:00:01+00:00", "kind": "b", "payload": {"reason": "r"}},
        ],
    )
    sigs = event_signature_summary(events_path=ndjson, kinds=["b"])
    assert [s["kind"] for s in sigs] == ["b"]


def test_format_signature_line_empty() -> None:
    assert format_signature_line([]) == ""


def test_format_signature_line_formats_count_and_ts() -> None:
    line = format_signature_line(
        [{"kind": "authority_divergence", "reason": "head_mismatch", "count": 293, "last_ts": "2026-07-05T00:21:37+00:00", "last_seq": 293}]
    )
    assert line.startswith("signatures: ")
    assert "authority_divergence/head_mismatch x293" in line
    assert "00:21Z" in line


def test_format_signature_line_truncates_to_max_items() -> None:
    sigs = [{"kind": f"k{i}", "reason": "r", "count": i, "last_ts": "", "last_seq": i} for i in range(5)]
    line = format_signature_line(sigs, max_items=2)
    assert line.count("x") == 2  # only two items rendered
