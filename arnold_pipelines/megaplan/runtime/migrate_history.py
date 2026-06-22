"""One-shot historical migration from legacy ``state.json`` to manifest events.

Reads legacy ``state.json``, receipts, capsules, gate signals, execution/review
artifacts, locks, and old resume cursors.  Emits manifest checkpoints,
events/artifact bindings where migration is required, or archives/quarantines
with operator-visible rationale.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold.kernel.artifacts import FileBackedArtifactStore
from arnold.kernel.events import EventEnvelope, EventFamily, ManifestReference
from arnold.kernel.journal import NDJsonEventJournal

from arnold_pipelines.megaplan.content_types import (
    GATE_SIGNAL_CONTENT_TYPE,
    RECEIPT_CONTENT_TYPE,
    STATE_ARTIFACT_CONTENT_TYPE,
    ArtifactAdapterContext,
    write_gate_signal_artifact,
    write_receipt_artifact,
    write_state_artifact,
)


# ---------------------------------------------------------------------------
# Migration result carriers
# ---------------------------------------------------------------------------

@dataclass
class MigrationQuarantineRecord:
    """An item that could not be migrated and was quarantined."""

    path: Path
    reason: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "reason": self.reason,
            "rationale": self.rationale,
        }


@dataclass
class MigrationResult:
    """Result of migrating a legacy plan directory."""

    migrated: bool
    plan_name: str
    events_emitted: int
    artifacts_emitted: list[dict[str, Any]] = field(default_factory=list)
    quarantine: list[MigrationQuarantineRecord] = field(default_factory=list)
    archive_dir: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "migrated": self.migrated,
            "plan_name": self.plan_name,
            "events_emitted": self.events_emitted,
            "artifacts_emitted": self.artifacts_emitted,
            "quarantine": [q.to_dict() for q in self.quarantine],
            "archive_dir": str(self.archive_dir) if self.archive_dir else None,
        }


# ---------------------------------------------------------------------------
# Legacy readers
# ---------------------------------------------------------------------------

def read_legacy_state(plan_dir: Path) -> dict[str, Any] | None:
    """Read legacy ``state.json`` if present."""

    path = plan_dir / "state.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"cannot read legacy state.json at {plan_dir}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def find_legacy_receipts(plan_dir: Path) -> list[Path]:
    """Return legacy receipt files (``receipt_*.json``)."""

    return sorted(plan_dir.glob("receipt_*.json"))


def find_legacy_gate_signals(plan_dir: Path) -> list[Path]:
    """Return legacy gate signal files (``gate_signals_v*.json``)."""

    return sorted(plan_dir.glob("gate_signals_v*.json"))


def find_legacy_capsules(plan_dir: Path) -> list[Path]:
    """Return legacy capsule files."""

    return sorted(plan_dir.glob("*.capsule.json")) + sorted(plan_dir.glob("capsule_*.json"))


def find_legacy_locks(plan_dir: Path) -> list[Path]:
    """Return lock files."""

    return sorted(p for p in plan_dir.glob("*.lock") if p.is_file())


def find_legacy_resume_cursor(plan_dir: Path) -> Path | None:
    """Return the legacy resume cursor file if present."""

    path = plan_dir / "resume_cursor.json"
    return path if path.exists() else None


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------

def _archive_legacy_files(
    plan_dir: Path,
    archive_dir: Path,
    files: list[Path],
) -> None:
    archive_dir.mkdir(parents=True, exist_ok=True)
    for source in files:
        dest = archive_dir / source.name
        if dest.exists():
            dest = archive_dir / f"{source.name}.{source.stat().st_mtime_ns}"
        shutil.copy2(source, dest)


def _emit_state_artifact(
    ctx: ArtifactAdapterContext,
    state: Mapping[str, Any],
) -> dict[str, Any]:
    binding = write_state_artifact(ctx, state=state)
    return {
        "artifact_id": binding.artifact_id,
        "relative_path": binding.relative_path,
        "content_type_id": STATE_ARTIFACT_CONTENT_TYPE,
    }


def _emit_receipt_artifacts(
    ctx: ArtifactAdapterContext,
    receipt_paths: list[Path],
) -> list[dict[str, Any]]:
    emitted: list[dict[str, Any]] = []
    for path in receipt_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        binding = write_receipt_artifact(
            ctx,
            step=str(data.get("step", path.stem)),
            success=bool(data.get("success", True)),
            summary=str(data.get("summary", "")),
            artifacts=list(data.get("artifacts", [])),
            artifact_id=path.stem,
        )
        emitted.append({
            "artifact_id": binding.artifact_id,
            "relative_path": binding.relative_path,
            "content_type_id": RECEIPT_CONTENT_TYPE,
        })
    return emitted


def _emit_gate_signal_artifacts(
    ctx: ArtifactAdapterContext,
    signal_paths: list[Path],
) -> list[dict[str, Any]]:
    emitted: list[dict[str, Any]] = []
    for path in signal_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        version = int(path.stem.split("_v")[-1]) if "_v" in path.stem else 1
        binding = write_gate_signal_artifact(
            ctx,
            version=version,
            signals=data.get("signals", {}),
            robustness=data.get("robustness", "standard"),
            preflight_results=data.get("preflight_results", {}),
            unresolved_flags=list(data.get("unresolved_flags", [])),
            warnings=list(data.get("warnings", [])),
        )
        emitted.append({
            "artifact_id": binding.artifact_id,
            "relative_path": binding.relative_path,
            "content_type_id": GATE_SIGNAL_CONTENT_TYPE,
        })
    return emitted


def _journal_checkpoint(
    artifact_root: Path,
    plan_name: str,
    state: Mapping[str, Any],
    *,
    manifest_hash: str = "sha256:" + "0" * 64,
) -> int:
    """Write a minimal migration checkpoint event to the manifest journal."""

    journal = NDJsonEventJournal(artifact_root)
    event = EventEnvelope(
        event_id=f"migration:{plan_name}",
        family=EventFamily.NODE_LIFECYCLE,
        kind="migration_checkpoint",
        manifest=ManifestReference(alias="megaplan", manifest_hash=manifest_hash),
        run_id=f"migration:{plan_name}",
        payload_schema_hash="sha256:" + "0" * 64,
        payload={
            "plan_name": plan_name,
            "legacy_state": {
                "name": state.get("name"),
                "current_state": state.get("current_state"),
                "iteration": state.get("iteration"),
            },
        },
        scope_stack=(),
        artifact_root=str(artifact_root),
    )
    journal.append(event)
    return 1


def migrate_legacy_plan_directory(
    plan_dir: Path,
    *,
    artifact_root: Path | None = None,
    archive: bool = True,
) -> MigrationResult:
    """Migrate a legacy plan directory to manifest checkpoints and artifacts.

    ``state.json`` is treated as a migration input only.  Surviving data is
    written as versioned artifacts under ``artifact_root``; everything else is
    archived or quarantined with rationale.
    """

    plan_dir = Path(plan_dir)
    artifact_root = Path(artifact_root) if artifact_root else plan_dir / ".manifest"
    artifact_root.mkdir(parents=True, exist_ok=True)

    state = read_legacy_state(plan_dir)
    if state is None:
        return MigrationResult(
            migrated=False,
            plan_name=plan_dir.name,
            events_emitted=0,
            quarantine=[
                MigrationQuarantineRecord(
                    path=plan_dir,
                    reason="missing_state_json",
                    rationale="No state.json found; nothing to migrate.",
                )
            ],
        )

    plan_name = str(state.get("name", plan_dir.name))
    ctx = ArtifactAdapterContext(plan_dir=plan_dir, artifact_root=artifact_root)

    artifacts_emitted: list[dict[str, Any]] = []
    quarantine: list[MigrationQuarantineRecord] = []

    # State artifact (read-only sunset projection)
    artifacts_emitted.append(_emit_state_artifact(ctx, state))

    # Receipts
    receipt_paths = find_legacy_receipts(plan_dir)
    artifacts_emitted.extend(_emit_receipt_artifacts(ctx, receipt_paths))

    # Gate signals
    signal_paths = find_legacy_gate_signals(plan_dir)
    artifacts_emitted.extend(_emit_gate_signal_artifacts(ctx, signal_paths))

    # Capsules: archive, do not re-emit as primary artifacts
    capsule_paths = find_legacy_capsules(plan_dir)
    if capsule_paths:
        quarantine.extend(
            MigrationQuarantineRecord(
                path=p,
                reason="capsule_archived",
                rationale="Capsules are preserved in the legacy plan dir and referenced from archive; not re-emitted as manifest artifacts.",
            )
            for p in capsule_paths
        )

    # Locks: archive, do not migrate
    lock_paths = find_legacy_locks(plan_dir)
    if lock_paths:
        quarantine.extend(
            MigrationQuarantineRecord(
                path=p,
                reason="lock_archived",
                rationale="Advisory lock files are runtime state; they are archived but not migrated as authority.",
            )
            for p in lock_paths
        )

    # Resume cursor: archive; cursor authority moves to journal-derived coordinates
    resume_cursor_path = find_legacy_resume_cursor(plan_dir)
    if resume_cursor_path:
        quarantine.append(
            MigrationQuarantineRecord(
                path=resume_cursor_path,
                reason="cursor_archived",
                rationale="Legacy resume cursor is archived; manifest runtime derives cursors from journal sequence and manifest coordinates.",
            )
        )

    # Archive legacy inputs if requested
    archive_dir: Path | None = None
    if archive:
        archive_dir = artifact_root / "archive"
        to_archive = [
            *receipt_paths,
            *signal_paths,
            *capsule_paths,
            *lock_paths,
        ]
        if resume_cursor_path:
            to_archive.append(resume_cursor_path)
        if to_archive:
            _archive_legacy_files(plan_dir, archive_dir, to_archive)

    # Emit a migration checkpoint event
    events_emitted = _journal_checkpoint(artifact_root, plan_name, state)

    return MigrationResult(
        migrated=True,
        plan_name=plan_name,
        events_emitted=events_emitted,
        artifacts_emitted=artifacts_emitted,
        quarantine=quarantine,
        archive_dir=archive_dir,
    )


__all__ = [
    "MigrationQuarantineRecord",
    "MigrationResult",
    "migrate_legacy_plan_directory",
]
