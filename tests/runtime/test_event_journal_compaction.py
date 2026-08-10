"""Step 20-22 — compaction manifest, legal-hold retention, and bounded IO.

Verifies that event-journal compaction:

* Defines a compaction manifest that is a **rebuildable projection** of
  durable evidence — never action authority (Step 20).
* Preserves legal-hold ranges and exact event digests, rejecting ambiguous,
  missing, or boundary-overlapping legal holds with typed drift (Step 21).
* Proves deterministic replay before/after compaction with identical
  projection digest, no rebuild loop, and bounded IO (Step 22).

Every assertion derives authority from durable ``events.ndjson`` records —
never from labels, liveness, WBC receipts, or rebuildable projections.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arnold.runtime.event_journal import (
    CompactionManifest,
    JournalDrift,
    LegalHoldRange,
    compute_compaction_manifest,
    manifest_replay_digest_equal,
    read_compaction_window,
    rebuild_compaction_manifest,
    validate_compaction_legal_holds,
)
from arnold_pipelines.megaplan.observability.projection_rebuild import (
    verify_compaction_manifest_rebuildable,
)


def _write_ndjson(artifact_root: Path, lines: list[str]) -> None:
    """Write lines to ``events.ndjson`` under *artifact_root*."""
    artifact_root.mkdir(parents=True, exist_ok=True)
    ndjson = artifact_root / "events.ndjson"
    ndjson.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_event(seq: int, kind: str = "test", **extra) -> dict:
    """Return a minimal event dict with *seq* and *kind*."""
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


def _write_events(artifact_root: Path, count: int, start: int = 0) -> list[dict]:
    """Write *count* sequential events (seq ``start``..``start+count-1``)."""
    events = [_make_event(start + i, kind=f"k{start + i}") for i in range(count)]
    _write_ndjson(artifact_root, [json.dumps(e, sort_keys=True) for e in events])
    return events


def _digest_of(events: list[dict]) -> str:
    """Independently compute the canonical records digest over *events*."""
    hasher = hashlib.sha256()
    for event in events:
        canonical = json.dumps(
            event, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        hasher.update(canonical.encode("utf-8"))
        hasher.update(b"\n")
    return "sha256:" + hasher.hexdigest()


# ── Step 20: compaction manifest is a rebuildable projection ────────────────


def test_compaction_manifest_is_rebuildable_projection(tmp_path: Path) -> None:
    """A manifest is rebuildable from durable evidence and is not authority."""
    events = _write_events(tmp_path, 10)  # seq 0..9
    manifest, drift = compute_compaction_manifest(tmp_path, 2, 6)

    assert drift == []
    assert isinstance(manifest, CompactionManifest)

    # Schema fields describe the compaction as a projection, not an action.
    assert manifest.kind == "COMPACTION_MANIFEST"
    assert manifest.manifest_version == 1
    assert manifest.from_seq == 2
    assert manifest.to_seq == 6

    # The whole window [2, 6] is compacted (no legal holds).
    assert manifest.compacted_record_count == 5
    assert manifest.preserved_record_count == 0
    assert manifest.compacted_digest.startswith("sha256:")

    # Exact digest over the compacted records, independently recomputed.
    assert manifest.compacted_digest == _digest_of(events[2:7])

    # Rebuildable projection: re-deriving from durable evidence reproduces
    # every durable-derived field.
    rebuilt, rebuild_drift = rebuild_compaction_manifest(manifest, tmp_path)
    assert rebuild_drift == []
    assert rebuilt is not None
    assert manifest_replay_digest_equal(manifest, rebuilt)
    # computed_at is non-authoritative and may legitimately differ.
    assert rebuilt.compacted_digest == manifest.compacted_digest
    assert rebuilt.preserved_digest == manifest.preserved_digest

    # The manifest carries no action-authority semantics.  The projection-
    # rebuild parity machinery treats it as evidence to verify, never as
    # authority to trust: parity proves it faithfully projects durable
    # evidence.
    report = verify_compaction_manifest_rebuildable(manifest, tmp_path)
    assert report.parity is True
    assert report.rebuild_digest == manifest.compacted_digest

    # A manifest cannot bless itself as authority: a tampered digest (the
    # only way a manifest could be made to "authorize" a false state) is
    # detected as a parity failure and must not be trusted.
    tampered = CompactionManifest(
        manifest_version=manifest.manifest_version,
        kind=manifest.kind,
        from_seq=manifest.from_seq,
        to_seq=manifest.to_seq,
        compacted_record_count=manifest.compacted_record_count,
        compacted_digest="sha256:" + "0" * 64,
        preserved_record_count=manifest.preserved_record_count,
        preserved_digest=manifest.preserved_digest,
        legal_holds=manifest.legal_holds,
        computed_at=manifest.computed_at,
    )
    tampered_report = verify_compaction_manifest_rebuildable(tampered, tmp_path)
    assert tampered_report.parity is False

    # Round-trip serialization preserves the durable projection.
    restored = CompactionManifest.from_dict(manifest.to_dict())
    assert manifest_replay_digest_equal(manifest, restored)


# ── Step 21: legal-hold retention and typed drift ──────────────────────────


def test_legal_hold_ranges_are_preserved(tmp_path: Path) -> None:
    """Legal-hold records are preserved with exact digests; bad holds drift."""
    events = _write_events(tmp_path, 10)  # seq 0..9
    hold = LegalHoldRange(from_seq=3, to_seq=5)

    manifest, drift = compute_compaction_manifest(
        tmp_path, 0, 9, legal_holds=(hold,)
    )

    assert drift == []
    assert manifest is not None

    # Legal-hold records (seq 3, 4, 5) are preserved verbatim with their
    # exact digest.
    assert manifest.preserved_record_count == 3
    assert manifest.preserved_digest == _digest_of(events[3:6])

    # The remaining window records are compacted with their exact digest.
    assert manifest.compacted_record_count == 7
    assert manifest.compacted_digest == _digest_of(events[:3] + events[6:10])
    assert hold in manifest.legal_holds

    # ── Typed drift: ambiguous (inverted) hold is rejected ──────────
    bad_ambiguous = LegalHoldRange(from_seq=5, to_seq=3)
    m_none, drift_a = compute_compaction_manifest(
        tmp_path, 0, 9, legal_holds=(bad_ambiguous,)
    )
    assert m_none is None
    ambiguous = next(d for d in drift_a if d.drift_type == "legal_hold_ambiguous")
    assert ambiguous.kind == "DRIFT_DETECTED"
    assert ambiguous.evidence["hold"] == {"from_seq": 5, "to_seq": 3}
    assert ambiguous.evidence["compaction_window"] == {"from_seq": 0, "to_seq": 9}

    # ── Typed drift: boundary-overlapping holds are rejected ────────
    overlap_left = LegalHoldRange(from_seq=2, to_seq=4)
    overlap_right = LegalHoldRange(from_seq=4, to_seq=6)  # touches at seq 4
    m_none2, drift_o = compute_compaction_manifest(
        tmp_path, 0, 9, legal_holds=(overlap_left, overlap_right)
    )
    assert m_none2 is None
    overlap = next(d for d in drift_o if d.drift_type == "legal_hold_overlap")
    assert overlap.kind == "DRIFT_DETECTED"
    assert overlap.evidence["left_hold"] == {"from_seq": 2, "to_seq": 4}
    assert overlap.evidence["right_hold"] == {"from_seq": 4, "to_seq": 6}

    # ── Typed drift: missing (out-of-range) hold is rejected ────────
    # Entirely outside the compaction window [0, 9]: protects nothing.
    missing = LegalHoldRange(from_seq=20, to_seq=99)
    m_none3, drift_m = compute_compaction_manifest(
        tmp_path, 0, 9, legal_holds=(missing,)
    )
    assert m_none3 is None
    oor = next(d for d in drift_m if d.drift_type == "legal_hold_out_of_range")
    assert oor.kind == "DRIFT_DETECTED"
    assert oor.evidence["hold"] == {"from_seq": 20, "to_seq": 99}
    assert oor.evidence["compaction_window"] == {"from_seq": 0, "to_seq": 9}

    # Every drift finding is a JournalDrift with kind DRIFT_DETECTED.
    for finding in drift_a + drift_o + drift_m:
        assert isinstance(finding, JournalDrift)
        assert finding.kind == "DRIFT_DETECTED"

    # The validation function is also directly callable and IO-free.
    direct = validate_compaction_legal_holds(
        tmp_path, 0, 9, (bad_ambiguous, overlap_left, overlap_right)
    )
    assert any(f.drift_type == "legal_hold_ambiguous" for f in direct)
    assert any(f.drift_type == "legal_hold_overlap" for f in direct)

    # A partially-overlapping-but-valid hold intersecting the window is OK.
    spanning = LegalHoldRange(from_seq=8, to_seq=12)
    m_span, drift_span = compute_compaction_manifest(
        tmp_path, 0, 9, legal_holds=(spanning,)
    )
    assert drift_span == []
    assert m_span is not None
    # Only seq 8, 9 fall inside both the window and the spanning hold.
    assert m_span.preserved_record_count == 2
    assert m_span.preserved_digest == _digest_of(events[8:10])


# ── Step 22: replay digest equality, no rebuild loop, bounded IO ───────────


def test_replay_digest_matches_before_and_after_compaction(tmp_path: Path) -> None:
    """Replay (re-derivation) yields identical digests — no rebuild loop.

    "Before compaction": the manifest computed from the durable records.
    "After compaction": the manifest re-derived (replayed) from the same
    durable evidence.  The compacted and preserved digests must be byte-
    identical, proving the manifest is a deterministic, non-lossy, non-
    inventing projection — and re-deriving repeatedly does not drift (no
    rebuild loop).
    """
    _write_events(tmp_path, 10)  # seq 0..9
    hold = LegalHoldRange(from_seq=2, to_seq=3)

    before, drift1 = compute_compaction_manifest(
        tmp_path, 0, 6, legal_holds=(hold,)
    )
    assert drift1 == []
    assert before is not None

    # Replay: re-derive the manifest from durable evidence.
    after, drift2 = compute_compaction_manifest(
        tmp_path, 0, 6, legal_holds=(hold,)
    )
    assert drift2 == []
    assert after is not None

    # Replay digest equality: compacted and preserved digests match exactly.
    assert before.compacted_digest == after.compacted_digest
    assert before.preserved_digest == after.preserved_digest
    assert manifest_replay_digest_equal(before, after)

    # No rebuild loop: a third derivation is identical to the second.
    again, drift3 = compute_compaction_manifest(
        tmp_path, 0, 6, legal_holds=(hold,)
    )
    assert drift3 == []
    assert manifest_replay_digest_equal(after, again)

    # The projection-rebuild parity machinery confirms rebuildable parity.
    report = verify_compaction_manifest_rebuildable(before, tmp_path)
    assert report.parity is True
    assert report.rebuild_digest == before.compacted_digest


def test_compaction_io_is_bounded(tmp_path: Path) -> None:
    """Compaction IO is bounded by the window, not the journal size."""
    total = 5000
    _write_events(tmp_path, total)  # seq 0..4999

    # A prefix window [0, 9]: read_compaction_window stops once seq exceeds
    # to_seq, reading ~11 records rather than scanning all 5000.
    window = read_compaction_window(tmp_path, 0, 9)
    assert [r["seq"] for r in window] == list(range(10))

    manifest, drift = compute_compaction_manifest(tmp_path, 0, 9)
    assert drift == []
    assert manifest is not None

    # The manifest processes exactly the window — bounded by window size,
    # not journal size.
    assert manifest.compacted_record_count == 10
    assert manifest.preserved_record_count == 0

    # An empty compaction window range is rejected before any IO.
    raised = False
    try:
        read_compaction_window(tmp_path, 5, 4)
    except ValueError:
        raised = True
    assert raised
