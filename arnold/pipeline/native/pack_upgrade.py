"""Deliberate re-pin planning and application for shared native packs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.pipeline.native.pack_diff import DiffReport, diff_pack_exports
from arnold.pipeline.native.pack_index import DependentRecord
from arnold.pipeline.native.pack_metadata import LockfileEntry, PackLockfile
from arnold.pipeline.native.pack_registry import PackRegistry, RegisteredPackExport


class PackUpgradeError(RuntimeError):
    """Raised when a deliberate re-pin cannot be applied."""


@dataclass(frozen=True)
class TransitiveImpact:
    """One dependent program affected by a proposed re-pin."""

    program_stable_id: str | None
    program_name: str
    call_site_paths: tuple[str, ...] = ()
    lockfile_entry: LockfileEntry | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"program_name": self.program_name}
        if self.program_stable_id is not None:
            result["program_stable_id"] = self.program_stable_id
        if self.call_site_paths:
            result["call_site_paths"] = list(self.call_site_paths)
        if self.lockfile_entry is not None:
            result["lockfile_entry"] = self.lockfile_entry.to_dict()
        return result

    @classmethod
    def from_dependent_record(cls, record: DependentRecord) -> "TransitiveImpact":
        return cls(
            program_stable_id=record.program_stable_id,
            program_name=record.program_name,
            call_site_paths=record.call_site_paths,
            lockfile_entry=record.lockfile_entry,
        )


@dataclass(frozen=True)
class PackUpgradePlan:
    """Diff report plus proposed lockfile mutation for one deliberate re-pin."""

    stable_id: str
    current_lockfile_entry: LockfileEntry
    proposed_lockfile_entry: LockfileEntry
    diff_report: DiffReport
    proposed_lockfile: PackLockfile
    current_registration: RegisteredPackExport
    target_registration: RegisteredPackExport
    transitive_impacts: tuple[TransitiveImpact, ...] = ()
    blocked_reason: str | None = None

    @property
    def can_apply(self) -> bool:
        return self.blocked_reason is None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "stable_id": self.stable_id,
            "current_lockfile_entry": self.current_lockfile_entry.to_dict(),
            "proposed_lockfile_entry": self.proposed_lockfile_entry.to_dict(),
            "diff_report": self.diff_report.to_dict(),
            "proposed_lockfile": self.proposed_lockfile.to_dict(),
            "current_registration": {
                "pack_id": self.current_registration.pack_id,
                "version": self.current_registration.version,
                "stable_id": self.current_registration.stable_id,
                "interface_hash": self.current_registration.interface_hash,
            },
            "target_registration": {
                "pack_id": self.target_registration.pack_id,
                "version": self.target_registration.version,
                "stable_id": self.target_registration.stable_id,
                "interface_hash": self.target_registration.interface_hash,
            },
            "transitive_impacts": [impact.to_dict() for impact in self.transitive_impacts],
            "can_apply": self.can_apply,
        }
        if self.blocked_reason is not None:
            result["blocked_reason"] = self.blocked_reason
        return result


def plan_pack_repin(
    *,
    registry: PackRegistry,
    lockfile: PackLockfile,
    stable_id: str,
    target_version: str,
) -> PackUpgradePlan:
    """Plan a deliberate re-pin for one dependency without mutating inputs."""
    if not stable_id:
        raise ValueError("stable_id must be non-empty")
    if not target_version:
        raise ValueError("target_version must be non-empty")

    current_resolved = registry.resolve_entry(stable_id, lockfile=lockfile)
    if current_resolved.lockfile_entry is None:
        raise PackUpgradeError(
            f"missing current lockfile entry for stable_id {stable_id!r}"
        )

    target_registration = _select_target_registration(
        registry=registry,
        stable_id=stable_id,
        target_version=target_version,
    )
    proposed_entry = target_registration.to_lockfile_entry()
    diff_report = diff_pack_exports(
        old_export=current_resolved.export,
        new_export=target_registration.export,
        old_program=current_resolved.program,
        new_program=target_registration.program,
    )
    proposed_lockfile = _replace_lockfile_entry(
        lockfile=lockfile,
        stable_id=stable_id,
        replacement=proposed_entry,
    )

    blocked_reason: str | None = None
    if diff_report.has_breaking_changes:
        blocked_reason = (
            f"breaking changes detected for stable_id {stable_id!r}; "
            "deliberate re-pin is blocked"
        )

    return PackUpgradePlan(
        stable_id=stable_id,
        current_lockfile_entry=current_resolved.lockfile_entry,
        proposed_lockfile_entry=proposed_entry,
        diff_report=diff_report,
        proposed_lockfile=proposed_lockfile,
        current_registration=current_resolved.registration,
        target_registration=target_registration,
        transitive_impacts=_transitive_impacts_for(registry, stable_id),
        blocked_reason=blocked_reason,
    )


def apply_pack_repin(
    *,
    registry: PackRegistry,
    lockfile: PackLockfile,
    stable_id: str,
    target_version: str,
) -> PackLockfile:
    """Apply a non-breaking deliberate re-pin and return the new lockfile."""
    plan = plan_pack_repin(
        registry=registry,
        lockfile=lockfile,
        stable_id=stable_id,
        target_version=target_version,
    )
    if not plan.can_apply:
        raise PackUpgradeError(plan.blocked_reason or "deliberate re-pin is blocked")
    return plan.proposed_lockfile


def _select_target_registration(
    *,
    registry: PackRegistry,
    stable_id: str,
    target_version: str,
) -> RegisteredPackExport:
    matches = [
        registration
        for registration in registry.registrations_for(stable_id)
        if registration.version == target_version
    ]
    if not matches:
        versions = ", ".join(
            repr(registration.version)
            for registration in registry.registrations_for(stable_id)
        )
        raise LookupError(
            f"unregistered target version for stable_id {stable_id!r}: "
            f"{target_version!r}; registered versions are [{versions}]"
        )
    if len(matches) != 1:
        raise LookupError(
            f"ambiguous registered export for stable_id {stable_id!r} at "
            f"target version {target_version!r}"
        )
    return matches[0]


def _replace_lockfile_entry(
    *,
    lockfile: PackLockfile,
    stable_id: str,
    replacement: LockfileEntry,
) -> PackLockfile:
    entries = []
    replaced = False
    for entry in lockfile.entries:
        if entry.stable_id == stable_id:
            if replaced:
                raise LookupError(
                    f"ambiguous lockfile entries for stable_id {stable_id!r}: "
                    "cannot propose a deliberate re-pin"
                )
            entries.append(replacement)
            replaced = True
            continue
        entries.append(entry)
    if not replaced:
        raise LookupError(
            f"missing lockfile entry for stable_id {stable_id!r} in PackLockfile"
        )
    return PackLockfile(
        manifest_stable_id=lockfile.manifest_stable_id,
        manifest_version=lockfile.manifest_version,
        entries=tuple(entries),
    )


def _transitive_impacts_for(
    registry: PackRegistry,
    stable_id: str,
) -> tuple[TransitiveImpact, ...]:
    return tuple(
        TransitiveImpact.from_dependent_record(record)
        for record in registry.reverse_index.transitive_dependents_of(stable_id)
    )


__all__ = [
    "PackUpgradeError",
    "PackUpgradePlan",
    "TransitiveImpact",
    "apply_pack_repin",
    "plan_pack_repin",
]
