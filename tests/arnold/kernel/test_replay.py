from __future__ import annotations

from pathlib import Path

import pytest

from arnold.kernel import (
    LegacyAliasRecord,
    NDJsonEventJournal,
    QuarantineRecord,
    ReplayCursor,
    ReplayDecision,
    ReplayResolution,
    SuspensionCursor,
    SuspensionRecord,
    SuspensionState,
    SuspendCapabilityRoute,
    compute_expected_hash,
    resolve_cursor,
    validate_artifact_content_hashes,
    validate_event_sequence_against_cursor,
    validate_replay_cursor,
    validate_resume_payload,
    validate_suspension_record,
)
from arnold.kernel.capabilities import CapabilityId, DispatchKey
from arnold.kernel.events import EventEnvelope, EventFamily, ManifestReference
from arnold.kernel.ids import ReentryId


def _hash(char: str) -> str:
    return "sha256:" + char * 64


def _event(
    kind: str,
    sequence: int,
    node_ref: str = "n1",
    scope_stack: tuple[str, ...] = (),
) -> EventEnvelope:
    return EventEnvelope(
        event_id=f"e{sequence}",
        family=EventFamily.NODE_LIFECYCLE,
        kind=kind,
        manifest=ManifestReference(alias="demo", manifest_hash=_hash("a")),
        run_id="run-1",
        payload_schema_hash=_hash("b"),
        payload={"node_ref": node_ref},
        sequence=sequence,
        scope_stack=scope_stack,
    )


def test_native_manifest_hash_matches_without_aliases() -> None:
    cursor = ReplayCursor(manifest_hash=_hash("a"), event_sequence=0)
    resolution = resolve_cursor(cursor, native_manifest_hash=_hash("a"))

    assert resolution.resolution.decision is ReplayDecision.REUSE
    assert resolution.cursor == cursor
    assert resolution.quarantine is None


def test_legacy_alias_resolves_after_native_miss() -> None:
    cursor = ReplayCursor(manifest_hash=_hash("b"), event_sequence=0)
    aliases = {
        _hash("b"): LegacyAliasRecord(
            alias="legacy-pipeline",
            source_manifest_hash=_hash("b"),
            target_manifest_hash=_hash("a"),
        ),
    }
    resolution = resolve_cursor(cursor, native_manifest_hash=_hash("a"), legacy_aliases=aliases)

    assert resolution.resolution.decision is ReplayDecision.ALIAS
    assert resolution.cursor is not None
    assert resolution.cursor.manifest_hash == _hash("a")
    assert resolution.resolution.alias_manifest_hash == _hash("a")


def test_missing_legacy_alias_is_quarantined() -> None:
    cursor = ReplayCursor(manifest_hash=_hash("c"), event_sequence=0)
    resolution = resolve_cursor(cursor, native_manifest_hash=_hash("a"), run_id="run-1")

    assert resolution.resolution.decision is ReplayDecision.QUARANTINE
    assert resolution.cursor is None
    assert resolution.quarantine is not None
    assert isinstance(resolution.quarantine, QuarantineRecord)
    assert "missing legacy alias" in resolution.quarantine.reason


def test_unsafe_legacy_alias_is_quarantined() -> None:
    cursor = ReplayCursor(manifest_hash=_hash("b"), event_sequence=0)
    aliases = {
        _hash("b"): LegacyAliasRecord(
            alias="arnold_pipelines.megaplan:bad",
            source_manifest_hash=_hash("b"),
            target_manifest_hash=_hash("a"),
        ),
    }
    resolution = resolve_cursor(cursor, native_manifest_hash=_hash("a"), legacy_aliases=aliases)

    assert resolution.resolution.decision is ReplayDecision.QUARANTINE
    assert "unsafe" in resolution.resolution.reason


def test_wildcard_legacy_alias_is_quarantined() -> None:
    cursor = ReplayCursor(manifest_hash=_hash("b"), event_sequence=0)
    aliases = {
        _hash("b"): LegacyAliasRecord(
            alias="legacy*",
            source_manifest_hash=_hash("b"),
            target_manifest_hash=_hash("a"),
        ),
    }
    resolution = resolve_cursor(cursor, native_manifest_hash=_hash("a"), legacy_aliases=aliases)

    assert resolution.resolution.decision is ReplayDecision.QUARANTINE


def test_cursor_scope_stack_validation() -> None:
    cursor = ReplayCursor(
        manifest_hash=_hash("a"),
        scope_stack=("parent", "child"),
        artifact_root="/tmp/root",
        event_sequence=3,
    )
    validation = validate_replay_cursor(
        cursor,
        expected_manifest_hash=_hash("a"),
        expected_artifact_root="/tmp/root",
        max_event_sequence=5,
    )

    assert validation.decision is ReplayDecision.REUSE


def test_cursor_manifest_hash_mismatch_is_quarantined() -> None:
    cursor = ReplayCursor(manifest_hash=_hash("a"))
    validation = validate_replay_cursor(
        cursor,
        expected_manifest_hash=_hash("z"),
    )

    assert validation.decision is ReplayDecision.QUARANTINE
    assert "manifest_hash" in validation.reason


def test_cursor_event_sequence_past_journal_max_is_quarantined() -> None:
    cursor = ReplayCursor(manifest_hash=_hash("a"), event_sequence=10)
    validation = validate_replay_cursor(
        cursor,
        expected_manifest_hash=_hash("a"),
        max_event_sequence=5,
    )

    assert validation.decision is ReplayDecision.QUARANTINE
    assert "event_sequence" in validation.reason


def test_event_sequence_after_cursor_is_monotonic() -> None:
    cursor = ReplayCursor(manifest_hash=_hash("a"), event_sequence=1)
    events = (_event("node-started", 2), _event("node-completed", 3))
    validation = validate_event_sequence_against_cursor(events, cursor)

    assert validation.decision is ReplayDecision.REUSE


def test_event_sequence_before_cursor_is_quarantined() -> None:
    cursor = ReplayCursor(manifest_hash=_hash("a"), event_sequence=5)
    events = (_event("node-started", 3),)
    validation = validate_event_sequence_against_cursor(events, cursor)

    assert validation.decision is ReplayDecision.QUARANTINE
    assert "not after" in validation.reason


def test_artifact_content_hash_validation(tmp_path: Path) -> None:
    artifact = tmp_path / "note.txt"
    artifact.write_bytes(b"hello")
    expected = compute_expected_hash(b"hello")

    result = validate_artifact_content_hashes(
        {"note": artifact},
        {"note": expected},
    )
    assert result.decision is ReplayDecision.REUSE


def test_missing_artifact_for_hash_validation_is_quarantined(tmp_path: Path) -> None:
    result = validate_artifact_content_hashes(
        {},
        {"note": compute_expected_hash(b"hello")},
    )
    assert result.decision is ReplayDecision.QUARANTINE
    assert "missing" in result.reason


def test_hash_mismatch_is_quarantined(tmp_path: Path) -> None:
    artifact = tmp_path / "note.txt"
    artifact.write_bytes(b"world")

    result = validate_artifact_content_hashes(
        {"note": artifact},
        {"note": compute_expected_hash(b"hello")},
    )
    assert result.decision is ReplayDecision.QUARANTINE
    assert "mismatch" in result.reason


def test_nested_scope_cursor_is_valid() -> None:
    cursor = ReplayCursor(
        manifest_hash=_hash("a"),
        reentry_id="resume-1",
        scope_stack=("sha256:" + "s" * 64, "child-node"),
        event_sequence=7,
    )
    validation = validate_replay_cursor(
        cursor,
        expected_manifest_hash=_hash("a"),
        max_event_sequence=7,
    )
    assert validation.decision is ReplayDecision.REUSE


def test_suspension_record_validation() -> None:
    route = SuspendCapabilityRoute(
        route_id="operator",
        dispatch_key=DispatchKey(CapabilityId("human", "review")),
        reentry_id=ReentryId("resume-1"),
    )
    record = SuspensionRecord(
        run_id="run-1",
        manifest_hash=_hash("a"),
        node_ref="review",
        route=route,
        state=SuspensionState.PENDING,
    )
    result = validate_suspension_record(
        record,
        expected_manifest_hash=_hash("a"),
        allowed_states={SuspensionState.PENDING},
    )
    assert result.decision is ReplayDecision.REUSE


def test_resume_payload_without_schema_is_accepted() -> None:
    validation = validate_resume_payload({"answer": 42}, resume_schema_hash=None)
    assert validation.ok


def test_resume_payload_with_missing_validator_is_rejected() -> None:
    validation = validate_resume_payload(
        {"answer": 42},
        resume_schema_hash=_hash("s"),
        validator=None,
    )
    assert not validation.ok
    assert "no validator registered" in validation.reason


def test_resume_payload_validator_can_accept() -> None:
    validation = validate_resume_payload(
        {"answer": 42},
        resume_schema_hash=_hash("s"),
        validator=lambda p: "answer" in p,
    )
    assert validation.ok


def test_replay_cursor_rejects_invalid_manifest_hash() -> None:
    with pytest.raises(ValueError, match="manifest_hash"):
        ReplayCursor(manifest_hash="not-a-hash")


def test_replay_cursor_rejects_negative_sequence() -> None:
    with pytest.raises(ValueError, match="event_sequence"):
        ReplayCursor(manifest_hash=_hash("a"), event_sequence=-1)


def test_resolve_cursor_with_journal(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    journal.append(_event("node-started", 0))
    journal.append(_event("node-completed", 1))

    cursor = ReplayCursor(
        manifest_hash=_hash("a"),
        event_sequence=1,
        artifact_root=str(tmp_path),
    )
    validation = validate_replay_cursor(
        cursor,
        expected_manifest_hash=_hash("a"),
        expected_artifact_root=str(tmp_path),
        max_event_sequence=journal.read()[-1].sequence,
    )
    assert validation.decision is ReplayDecision.REUSE
