from __future__ import annotations

from pathlib import Path

import pytest

from arnold.execution.resume import ResumeRequest, prepare_resume
from arnold.kernel import (
    LegacyAliasRecord,
    ReplayCursor,
    SuspensionRecord,
    SuspensionState,
    SuspendCapabilityRoute,
)
from arnold.kernel.capabilities import CapabilityId, DispatchKey
from arnold.kernel.ids import ReentryId
from arnold.manifest import WorkflowManifest, WorkflowNode


def _hash(char: str) -> str:
    return "sha256:" + char * 64


def _manifest() -> WorkflowManifest:
    return WorkflowManifest(
        id="demo",
        nodes=(WorkflowNode(id="start", kind="noop"),),
    )


def _cursor(manifest_hash: str, tmp_path: Path) -> ReplayCursor:
    return ReplayCursor(
        manifest_hash=manifest_hash,
        artifact_root=str(tmp_path),
    )


def test_prepare_resume_accepts_native_cursor(tmp_path: Path) -> None:
    manifest = _manifest()
    cursor = _cursor(manifest.manifest_hash, tmp_path)
    request = ResumeRequest(run_id="run-1", cursor=cursor)

    outcome = prepare_resume(
        manifest,
        request,
        artifact_root=tmp_path,
    )

    assert outcome.ok
    assert outcome.manifest_cursor is not None
    assert outcome.manifest_cursor.coordinate.manifest_hash == manifest.manifest_hash


def test_prepare_resume_prefers_native_cursor_over_aliases(tmp_path: Path) -> None:
    manifest = _manifest()
    cursor = _cursor(manifest.manifest_hash, tmp_path)
    request = ResumeRequest(run_id="run-1", cursor=cursor)

    outcome = prepare_resume(
        manifest,
        request,
        artifact_root=tmp_path,
        legacy_aliases={
            manifest.manifest_hash: LegacyAliasRecord(
                alias="arnold_pipelines.megaplan:unsafe",
                source_manifest_hash=manifest.manifest_hash or "",
                target_manifest_hash=_hash("c"),
            ),
        },
    )

    assert outcome.ok
    assert outcome.replay_resolution is not None
    assert outcome.manifest_cursor is not None
    assert outcome.manifest_cursor.coordinate.manifest_hash == manifest.manifest_hash


def test_prepare_resume_quarantines_manifest_hash_mismatch(tmp_path: Path) -> None:
    manifest = _manifest()
    cursor = _cursor(_hash("c"), tmp_path)
    request = ResumeRequest(run_id="run-1", cursor=cursor)

    outcome = prepare_resume(
        manifest,
        request,
        artifact_root=tmp_path,
    )

    assert not outcome.ok
    assert "manifest_hash" in (outcome.quarantine_reason or "").lower()


def test_prepare_resume_resolves_safe_legacy_alias_and_preserves_cursor_fields(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    legacy_hash = _hash("c")
    cursor = ReplayCursor(
        manifest_hash=legacy_hash,
        reentry_id="resume-1",
        scope_stack=("parent", "child"),
        artifact_root=str(tmp_path),
        event_sequence=None,
    )
    request = ResumeRequest(run_id="run-1", cursor=cursor)

    outcome = prepare_resume(
        manifest,
        request,
        artifact_root=tmp_path,
        legacy_aliases={
            legacy_hash: LegacyAliasRecord(
                alias="legacy-planning",
                source_manifest_hash=legacy_hash,
                target_manifest_hash=manifest.manifest_hash or "",
            ),
        },
    )

    assert outcome.ok
    assert outcome.manifest_cursor is not None
    assert outcome.manifest_cursor.coordinate.manifest_hash == manifest.manifest_hash
    assert outcome.manifest_cursor.reentry_id == "resume-1"
    assert outcome.replay_resolution is not None


def test_prepare_resume_preserves_manifest_coordinate_fields(tmp_path: Path) -> None:
    manifest = _manifest()
    cursor = ReplayCursor(
        manifest_hash=manifest.manifest_hash,
        reentry_id="resume-1",
        scope_stack=("scope-a", "scope-b"),
        artifact_root=str(tmp_path),
        event_sequence=None,
    )
    request = ResumeRequest(run_id="run-1", cursor=cursor)

    outcome = prepare_resume(manifest, request, artifact_root=tmp_path)

    assert outcome.ok
    assert outcome.manifest_cursor is not None
    assert outcome.manifest_cursor.coordinate.alias == "demo"
    assert outcome.manifest_cursor.coordinate.manifest_hash == manifest.manifest_hash
    assert outcome.manifest_cursor.reentry_id == "resume-1"


def test_prepare_resume_quarantines_unsafe_legacy_alias(tmp_path: Path) -> None:
    manifest = _manifest()
    legacy_hash = _hash("c")
    request = ResumeRequest(run_id="run-1", cursor=_cursor(legacy_hash, tmp_path))

    outcome = prepare_resume(
        manifest,
        request,
        artifact_root=tmp_path,
        legacy_aliases={
            legacy_hash: LegacyAliasRecord(
                alias="arnold_pipelines.megaplan:legacy",
                source_manifest_hash=legacy_hash,
                target_manifest_hash=manifest.manifest_hash or "",
            ),
        },
    )

    assert not outcome.ok
    assert "unsafe legacy alias" in (outcome.quarantine_reason or "")


def test_prepare_resume_validates_suspension_record_and_payload(tmp_path: Path) -> None:
    manifest = _manifest()
    cursor = _cursor(manifest.manifest_hash, tmp_path)
    request = ResumeRequest(run_id="run-1", cursor=cursor, resume_payload={"answer": 42})
    route = SuspendCapabilityRoute(
        route_id="operator",
        dispatch_key=DispatchKey(CapabilityId("human", "review")),
        reentry_id=ReentryId("resume-1"),
        payload_schema_hash=_hash("p"),
    )
    suspension = SuspensionRecord(
        run_id="run-1",
        manifest_hash=manifest.manifest_hash,
        node_ref="start",
        route=route,
        state=SuspensionState.PENDING,
    )

    outcome = prepare_resume(
        manifest,
        request,
        artifact_root=tmp_path,
        suspension_record=suspension,
        resume_schema_hash=_hash("s"),
        resume_validator=lambda p: "answer" in p,
    )

    assert outcome.ok
    assert outcome.suspension is not None
    assert outcome.suspension.node_ref == "start"


def test_prepare_resume_quarantines_reentry_mismatch(tmp_path: Path) -> None:
    manifest = _manifest()
    cursor = ReplayCursor(
        manifest_hash=manifest.manifest_hash,
        reentry_id="wrong-reentry",
        artifact_root=str(tmp_path),
    )
    request = ResumeRequest(run_id="run-1", cursor=cursor, resume_payload={"answer": 42})
    route = SuspendCapabilityRoute(
        route_id="operator",
        dispatch_key=DispatchKey(CapabilityId("human", "review")),
        reentry_id=ReentryId("resume-1"),
    )
    suspension = SuspensionRecord(
        run_id="run-1",
        manifest_hash=manifest.manifest_hash,
        node_ref="start",
        route=route,
        state=SuspensionState.PENDING,
    )

    outcome = prepare_resume(
        manifest,
        request,
        artifact_root=tmp_path,
        suspension_record=suspension,
    )

    assert not outcome.ok
    assert "reentry_id" in (outcome.quarantine_reason or "")


def test_prepare_resume_rejects_invalid_resume_payload(tmp_path: Path) -> None:
    manifest = _manifest()
    cursor = _cursor(manifest.manifest_hash, tmp_path)
    request = ResumeRequest(run_id="run-1", cursor=cursor, resume_payload={})
    route = SuspendCapabilityRoute(
        route_id="operator",
        dispatch_key=DispatchKey(CapabilityId("human", "review")),
        reentry_id=ReentryId("resume-1"),
    )
    suspension = SuspensionRecord(
        run_id="run-1",
        manifest_hash=manifest.manifest_hash,
        node_ref="start",
        route=route,
        state=SuspensionState.PENDING,
    )

    outcome = prepare_resume(
        manifest,
        request,
        artifact_root=tmp_path,
        suspension_record=suspension,
        resume_schema_hash=_hash("s"),
        resume_validator=lambda p: "answer" in p,
    )

    assert not outcome.ok
    assert "validation" in (outcome.quarantine_reason or "").lower()


def test_prepare_resume_rejects_resumed_suspension(tmp_path: Path) -> None:
    manifest = _manifest()
    cursor = _cursor(manifest.manifest_hash, tmp_path)
    request = ResumeRequest(run_id="run-1", cursor=cursor)
    route = SuspendCapabilityRoute(
        route_id="operator",
        dispatch_key=DispatchKey(CapabilityId("human", "review")),
        reentry_id=ReentryId("resume-1"),
    )
    suspension = SuspensionRecord(
        run_id="run-1",
        manifest_hash=manifest.manifest_hash,
        node_ref="start",
        route=route,
        state=SuspensionState.RESUMED,
    )

    outcome = prepare_resume(
        manifest,
        request,
        artifact_root=tmp_path,
        suspension_record=suspension,
    )

    assert not outcome.ok
    assert "state" in (outcome.quarantine_reason or "").lower()
