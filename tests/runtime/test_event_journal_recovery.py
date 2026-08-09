"""Step 19 — sidecar and sequence recovery with DRIFT_DETECTED emission.

Verifies that drift detection derives every finding from durable
append-only evidence (``events.ndjson`` records and the advisory
``.events.seq`` sidecar) and emits ``DRIFT_DETECTED`` on disagreement —
never from labels, liveness, WBC receipts, or rebuildable projections.
"""

from __future__ import annotations

import json
from pathlib import Path

from arnold.runtime.event_journal import (
    JournalDrift,
    detect_journal_drift,
    read_sidecar_seq,
)


def _write_ndjson(artifact_root: Path, lines: list[str]) -> None:
    """Write lines to ``events.ndjson`` under *artifact_root*."""
    artifact_root.mkdir(parents=True, exist_ok=True)
    ndjson = artifact_root / "events.ndjson"
    ndjson.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_event(seq: int, kind: str = "test", **extra) -> dict:
    event: dict = {
        "seq": seq,
        "schema_version": 1,
        "ts_utc": "2026-01-01T00:00:00+00:00",
        "ts_rel_init_s": 0.0,
        "kind": kind,
        "payload": {},
    }
    event.update(extra)
    return event


def _write_sidecar_seq(artifact_root: Path, value: int) -> None:
    (artifact_root / ".events.seq").write_text(str(value), encoding="ascii")


# ── Stale sidecar + sequence reset ─────────────────────────────────────────


def test_stale_sidecar_and_sequence_reset_emit_drift(tmp_path: Path) -> None:
    """Stale sidecar and sequence reset both emit DRIFT_DETECTED from evidence.

    Scenario:
    * Journal records have seq 0, 1, 2, **1** (sequence reset at the tail).
    * The ``.events.seq`` sidecar says 0 (stale — behind the actual last seq).

    Detection must:
    1. Emit a ``stale_sidecar`` finding whose evidence cites the durable
       journal last_seq and digest.
    2. Emit a ``sequence_reset`` finding whose evidence cites the actual
       durable records that prove the non-monotonic step.
    3. Never derive authority from labels, liveness, or rebuilt projections.
    """
    events = [_make_event(0, kind="a"), _make_event(1, kind="b"), _make_event(2, kind="c")]
    # Append a sequence reset: seq goes 2 -> 1 (non-monotonic).
    events.append(_make_event(1, kind="reset"))
    _write_ndjson(tmp_path, [json.dumps(e, sort_keys=True) for e in events])
    _write_sidecar_seq(tmp_path, 0)  # stale: behind durable last_seq (2)

    findings = detect_journal_drift(tmp_path)

    kinds = [f.drift_type for f in findings]
    assert "stale_sidecar" in kinds
    assert "sequence_reset" in kinds

    # Every finding is a JournalDrift with kind == DRIFT_DETECTED.
    for f in findings:
        assert isinstance(f, JournalDrift)
        assert f.kind == "DRIFT_DETECTED"
        assert f.computed_at
        assert isinstance(f.evidence, dict)

    # Stale sidecar evidence is derived from durable content, not the sidecar.
    stale = next(f for f in findings if f.drift_type == "stale_sidecar")
    assert stale.evidence["sidecar_seq"] == 0
    assert stale.evidence["journal_last_seq"] == 2
    assert stale.evidence["journal_record_count"] == 4
    assert stale.evidence["journal_digest"].startswith("sha256:")

    # Sequence reset evidence cites the actual durable records.
    reset = next(f for f in findings if f.drift_type == "sequence_reset")
    assert reset.evidence["prev_seq"] == 2
    assert reset.evidence["this_seq"] == 1
    assert reset.evidence["prev_record"]["kind"] == "c"
    assert reset.evidence["this_record"]["kind"] == "reset"
    assert reset.evidence["journal_digest"].startswith("sha256:")


# ── Future sidecar ─────────────────────────────────────────────────────────


def test_future_sidecar_emit_drift(tmp_path: Path) -> None:
    """Sidecar ahead of durable journal emits future_sidecar drift."""
    events = [_make_event(0), _make_event(1)]
    _write_ndjson(tmp_path, [json.dumps(e, sort_keys=True) for e in events])
    _write_sidecar_seq(tmp_path, 5)  # future: ahead of durable last_seq (1)

    findings = detect_journal_drift(tmp_path)
    future = next(f for f in findings if f.drift_type == "future_sidecar")
    assert future.kind == "DRIFT_DETECTED"
    assert future.evidence["sidecar_seq"] == 5
    assert future.evidence["journal_last_seq"] == 1
    assert future.evidence["journal_record_count"] == 2


# ── Crash gap ──────────────────────────────────────────────────────────────


def test_crash_gap_emit_drift(tmp_path: Path) -> None:
    """A forward seq skip (>1) emits crash_gap drift with missing count."""
    events = [_make_event(0), _make_event(1), _make_event(5, kind="after_crash")]
    _write_ndjson(tmp_path, [json.dumps(e, sort_keys=True) for e in events])
    _write_sidecar_seq(tmp_path, 5)

    findings = detect_journal_drift(tmp_path)
    gap = next(f for f in findings if f.drift_type == "crash_gap")
    assert gap.kind == "DRIFT_DETECTED"
    assert gap.evidence["prev_seq"] == 1
    assert gap.evidence["this_seq"] == 5
    assert gap.evidence["expected_seq"] == 2
    assert gap.evidence["missing_count"] == 3


# ── No drift ───────────────────────────────────────────────────────────────


def test_no_drift_when_journal_consistent(tmp_path: Path) -> None:
    """A healthy journal with a matching sidecar emits no drift."""
    events = [_make_event(i) for i in range(5)]
    _write_ndjson(tmp_path, [json.dumps(e, sort_keys=True) for e in events])
    _write_sidecar_seq(tmp_path, 4)

    assert detect_journal_drift(tmp_path) == []


def test_no_drift_without_sidecar(tmp_path: Path) -> None:
    """Absence of a sidecar is not drift (sidecar is advisory)."""
    events = [_make_event(i) for i in range(3)]
    _write_ndjson(tmp_path, [json.dumps(e, sort_keys=True) for e in events])
    assert detect_journal_drift(tmp_path) == []


def test_no_drift_empty_journal(tmp_path: Path) -> None:
    assert detect_journal_drift(tmp_path) == []


# ── read_sidecar_seq helper ────────────────────────────────────────────────


def test_read_sidecar_seq_missing_returns_none(tmp_path: Path) -> None:
    assert read_sidecar_seq(tmp_path) is None


def test_read_sidecar_seq_reads_value(tmp_path: Path) -> None:
    _write_sidecar_seq(tmp_path, 42)
    assert read_sidecar_seq(tmp_path) == 42


def test_read_sidecar_seq_garbage_returns_none(tmp_path: Path) -> None:
    (tmp_path / ".events.seq").write_text("not-a-number", encoding="ascii")
    assert read_sidecar_seq(tmp_path) is None


# ── JournalDrift serialization ─────────────────────────────────────────────


def test_journal_drift_to_dict_roundtrip(tmp_path: Path) -> None:
    events = [_make_event(0), _make_event(0)]  # sequence reset
    _write_ndjson(tmp_path, [json.dumps(e, sort_keys=True) for e in events])
    findings = detect_journal_drift(tmp_path)
    assert len(findings) == 1
    d = findings[0].to_dict()
    assert d["kind"] == "DRIFT_DETECTED"
    assert d["drift_type"] == "sequence_reset"
    assert "prev_seq" in d["evidence"]
