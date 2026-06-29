"""Tests for resume cursor migration from legacy sentinels to manifest hashes."""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.kernel.journal import NDJsonEventJournal
from arnold.kernel.replay import ReplayCursor


class TestResumeMigration:
    def test_canonical_alias_maps_sentinel_to_target_hash(self) -> None:
        from arnold_pipelines.megaplan.runtime.resume_migration import canonical_megaplan_alias

        target = "sha256:" + "a" * 64
        alias = canonical_megaplan_alias(target)
        assert alias.target_manifest_hash == target
        assert alias.source_manifest_hash == "sha256:" + "0" * 64

    def test_resolve_legacy_cursor_with_native_match(self) -> None:
        from arnold_pipelines.megaplan.runtime.resume_migration import resolve_legacy_resume_cursor

        target = "sha256:" + "a" * 64
        cursor = ReplayCursor(manifest_hash=target, event_sequence=12)
        resolved, reason = resolve_legacy_resume_cursor(cursor, target)
        assert resolved is not None
        assert resolved.manifest_hash == target
        assert "native manifest hash matches" in reason

    def test_resolve_legacy_cursor_with_alias(self) -> None:
        from arnold_pipelines.megaplan.runtime.resume_migration import resolve_legacy_resume_cursor

        target = "sha256:" + "a" * 64
        cursor = ReplayCursor(
            manifest_hash="sha256:" + "0" * 64,
            event_sequence=12,
            artifact_root="/tmp/artifacts",
        )
        resolved, reason = resolve_legacy_resume_cursor(cursor, target)
        assert resolved is not None
        assert resolved.manifest_hash == target
        assert resolved.event_sequence == 12
        assert "legacy alias" in reason

    def test_resolution_preserves_quarantine_metadata_for_unsafe_fallback(self) -> None:
        from arnold.kernel.replay import LegacyAliasRecord, ReplayDecision, resolve_cursor

        target = "sha256:" + "a" * 64
        legacy = "sha256:" + "b" * 64
        resolution = resolve_cursor(
            ReplayCursor(manifest_hash=legacy, artifact_root="/tmp/artifacts"),
            native_manifest_hash=target,
            legacy_aliases={
                legacy: LegacyAliasRecord(
                    alias="arnold_pipelines.megaplan:unsafe",
                    source_manifest_hash=legacy,
                    target_manifest_hash=target,
                ),
            },
            run_id="run:test",
        )

        assert resolution.cursor is None
        assert resolution.resolution.decision is ReplayDecision.QUARANTINE
        assert resolution.quarantine is not None
        assert "unsafe legacy alias" in resolution.quarantine.reason

    def test_derive_resume_cursor_from_journal(self, tmp_path: Path) -> None:
        from arnold.kernel.events import EventEnvelope, EventFamily, ManifestReference
        from arnold_pipelines.megaplan.runtime.resume_migration import derive_resume_cursor_from_journal

        journal = NDJsonEventJournal(tmp_path)
        event = EventEnvelope(
            event_id="run:test:1",
            family=EventFamily.NODE_LIFECYCLE,
            kind="node_started",
            manifest=ManifestReference(alias="megaplan", manifest_hash="sha256:" + "b" * 64),
            run_id="run:test",
            payload_schema_hash="sha256:" + "0" * 64,
            payload={"node_ref": "gate"},
        )
        journal.append(event)

        target = "sha256:" + "a" * 64
        cursor = derive_resume_cursor_from_journal(
            artifact_root=tmp_path,
            target_manifest_hash=target,
            node_ref="gate",
        )
        assert cursor.manifest_hash == target
        assert cursor.event_sequence is not None
        assert cursor.artifact_root == str(tmp_path)

    def test_derive_manifest_cursor_from_journal_uses_manifest_coordinate_path(
        self,
        tmp_path: Path,
    ) -> None:
        from arnold.kernel.events import EventEnvelope, EventFamily, ManifestReference
        from arnold_pipelines.megaplan.runtime.resume_migration import (
            derive_manifest_cursor_from_journal,
        )

        journal = NDJsonEventJournal(tmp_path)
        journal.append(
            EventEnvelope(
                event_id="run:test:1",
                family=EventFamily.NODE_LIFECYCLE,
                kind="node_started",
                manifest=ManifestReference(alias="megaplan", manifest_hash="sha256:" + "b" * 64),
                run_id="run:test",
                payload_schema_hash="sha256:" + "0" * 64,
                payload={"node_ref": "execute"},
            )
        )

        target = "sha256:" + "a" * 64
        cursor = derive_manifest_cursor_from_journal(
            artifact_root=tmp_path,
            manifest_id="megaplan",
            manifest_hash=target,
            node_ref="execute",
        )

        assert cursor.coordinate.alias == "megaplan"
        assert cursor.coordinate.manifest_hash == target
        assert cursor.node is not None
        assert cursor.node.id == "execute"

    def test_extract_legacy_resume_cursor_from_state(self) -> None:
        from arnold_pipelines.megaplan.runtime.resume_migration import extract_legacy_resume_cursor

        target = "sha256:" + "a" * 64
        state = {
            "manifest_hash": "sha256:" + "0" * 64,
            "last_event_sequence": 7,
            "scope_stack": ["sub"],
            "reentry_id": "reentry-1",
        }
        resolved, reason = extract_legacy_resume_cursor(
            state,
            target_manifest_hash=target,
            run_id="run:test",
        )
        assert resolved is not None
        assert resolved.manifest_hash == target
        assert resolved.event_sequence == 7
        assert resolved.scope_stack == ("sub",)
