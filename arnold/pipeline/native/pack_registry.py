"""Explicit pack registration and fail-closed lockfile resolution.

The registry is process-local and additive: callers explicitly register pack
manifests plus compiled :class:`NativeProgram` providers up front, and later
resolve exported units by stable ID without importing implementation modules.

Resolution is fail-closed. A dependency pin must match a registered export by:

* stable ID
* exact manifest version
* exact interface hash

Any missing, ambiguous, mismatched, or unregistered condition raises a clear
diagnostic before execution can proceed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.native.pack_index import PackReverseIndex
from arnold.pipeline.native.pack_metadata import (
    ExportEntry,
    LockfileEntry,
    PackLockfile,
    PackManifest,
    compute_interface_hash,
)
from arnold.pipeline.native.pack_validation import validate_shared_pack_closure


class _Registry:
    """Base registry that fails closed on unregistered keys."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[RegisteredPackExport]] = {}

    def register(self, key: str, handler: "RegisteredPackExport") -> None:
        if not key:
            raise ValueError("registry key must be non-empty")
        self._handlers.setdefault(key, []).append(handler)

    def get(self, key: str) -> tuple["RegisteredPackExport", ...]:
        try:
            return tuple(self._handlers[key])
        except KeyError as exc:
            raise LookupError(f"unregistered pack export stable_id: {key!r}") from exc

    def has(self, key: str) -> bool:
        return key in self._handlers


@dataclass(frozen=True)
class RegisteredPackExport:
    """A single registered exported unit from a pack manifest."""

    manifest: PackManifest
    export: ExportEntry
    program: NativeProgram
    interface_hash: str

    @property
    def stable_id(self) -> str:
        return self.export.stable_id

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def pack_id(self) -> str:
        return self.manifest.stable_id or self.manifest.name

    def to_lockfile_entry(self) -> LockfileEntry:
        return LockfileEntry(
            stable_id=self.stable_id,
            version=self.version,
            interface_hash=self.interface_hash,
        )


@dataclass(frozen=True)
class ResolvedPackExport:
    """The result of a successful pack export resolution."""

    registration: RegisteredPackExport
    lockfile_entry: LockfileEntry | None = None

    @property
    def manifest(self) -> PackManifest:
        return self.registration.manifest

    @property
    def export(self) -> ExportEntry:
        return self.registration.export

    @property
    def program(self) -> NativeProgram:
        return self.registration.program

    @property
    def interface_hash(self) -> str:
        return self.registration.interface_hash


@dataclass
class PackRegistry(_Registry):
    """Explicit pack registry with fail-closed lockfile-based resolution."""

    reverse_index: PackReverseIndex = field(default_factory=PackReverseIndex)

    def __post_init__(self) -> None:
        super().__init__()

    def register_pack(
        self,
        manifest: PackManifest,
        providers: Mapping[str, NativeProgram],
    ) -> None:
        """Register *manifest* plus compiled program providers explicitly.

        The *providers* mapping must contain one compiled :class:`NativeProgram`
        for every exported stable ID in *manifest*, and no unexported extras.
        """
        manifest_exports = {export.stable_id: export for export in manifest.exports}
        provider_ids = set(providers)

        missing = sorted(set(manifest_exports) - provider_ids)
        if missing:
            raise LookupError(
                "missing provider registration for manifest exports: "
                + ", ".join(repr(item) for item in missing)
            )

        extras = sorted(provider_ids - set(manifest_exports))
        if extras:
            raise LookupError(
                "provider registration includes unexported stable_id values: "
                + ", ".join(repr(item) for item in extras)
            )

        registrations: list[RegisteredPackExport] = []
        for export in manifest.exports:
            program = providers[export.stable_id]
            validate_shared_pack_closure(
                program,
                pack_id=manifest.stable_id or manifest.name,
                export_stable_id=export.stable_id,
            )
            registration = self._build_registration(
                manifest=manifest,
                export=export,
                program=program,
            )
            self._ensure_unique_version(registration)
            registrations.append(registration)

        for registration in registrations:
            super().register(registration.stable_id, registration)

        # Pack dependencies are declared at the manifest boundary; registration
        # seeds the reverse index with coarse "this export depends on that ID"
        # records, and later resolution calls enrich them with lockfile pins and
        # concrete call-site paths when available.
        for dependency in manifest.dependencies:
            for export in manifest.exports:
                self.reverse_index.register(
                    dependency_stable_id=dependency.stable_id,
                    program_stable_id=export.stable_id,
                    program_name=export.name,
                )

    def resolve(
        self,
        stable_id: str,
        *,
        lockfile: PackLockfile | None = None,
        dependent_program: NativeProgram | None = None,
        dependent_name: str | None = None,
        dependent_stable_id: str | None = None,
        call_site_paths: tuple[str, ...] = (),
    ) -> NativeProgram:
        """Resolve a compiled program by stable ID, failing closed on bad pins."""
        return self.resolve_entry(
            stable_id,
            lockfile=lockfile,
            dependent_program=dependent_program,
            dependent_name=dependent_name,
            dependent_stable_id=dependent_stable_id,
            call_site_paths=call_site_paths,
        ).program

    def resolve_entry(
        self,
        stable_id: str,
        *,
        lockfile: PackLockfile | None = None,
        dependent_program: NativeProgram | None = None,
        dependent_name: str | None = None,
        dependent_stable_id: str | None = None,
        call_site_paths: tuple[str, ...] = (),
    ) -> ResolvedPackExport:
        """Resolve a registered export and optionally record reverse deps."""
        if not stable_id:
            raise ValueError("stable_id must be non-empty")

        candidates = self.get(stable_id)
        lockfile_entry: LockfileEntry | None = None

        if lockfile is None:
            registration = self._resolve_without_lockfile(stable_id, candidates)
        else:
            lockfile_entry = self._select_lockfile_entry(stable_id, lockfile)
            registration = self._resolve_with_lockfile(
                stable_id,
                candidates,
                lockfile_entry,
            )

        resolved = ResolvedPackExport(
            registration=registration,
            lockfile_entry=lockfile_entry,
        )
        self._record_resolution(
            stable_id=stable_id,
            lockfile_entry=lockfile_entry,
            dependent_program=dependent_program,
            dependent_name=dependent_name,
            dependent_stable_id=dependent_stable_id,
            call_site_paths=call_site_paths,
        )
        return resolved

    def registered_versions(self, stable_id: str) -> tuple[str, ...]:
        """Return registered versions for *stable_id* in registration order."""
        if not stable_id:
            return ()
        if not self.has(stable_id):
            return ()
        return tuple(entry.version for entry in self.get(stable_id))

    def registrations_for(self, stable_id: str) -> tuple[RegisteredPackExport, ...]:
        """Return registered exports for *stable_id*, or an empty tuple."""
        if not stable_id or not self.has(stable_id):
            return ()
        return self.get(stable_id)

    def _build_registration(
        self,
        *,
        manifest: PackManifest,
        export: ExportEntry,
        program: NativeProgram,
    ) -> RegisteredPackExport:
        if program.stable_id not in (None, export.stable_id):
            raise ValueError(
                f"provider stable_id mismatch for export {export.stable_id!r}: "
                f"program has {program.stable_id!r}"
            )

        export_hash = compute_interface_hash(
            stable_id=export.stable_id,
            inputs_schema=export.inputs_schema,
            outputs_schema=export.outputs_schema,
        )
        program_hash = compute_interface_hash(
            stable_id=export.stable_id,
            inputs_schema=program.inputs_schema,
            outputs_schema=program.outputs_schema,
        )
        if export_hash != program_hash:
            raise ValueError(
                f"provider interface mismatch for export {export.stable_id!r} in "
                f"pack {manifest.stable_id or manifest.name!r}: manifest hash "
                f"{export_hash!r} does not match provider hash {program_hash!r}"
            )

        return RegisteredPackExport(
            manifest=manifest,
            export=export,
            program=program,
            interface_hash=export_hash,
        )

    def _ensure_unique_version(self, registration: RegisteredPackExport) -> None:
        if not self.has(registration.stable_id):
            return
        duplicates = [
            candidate
            for candidate in self.get(registration.stable_id)
            if candidate.version == registration.version
        ]
        if duplicates:
            raise LookupError(
                f"ambiguous registration for stable_id {registration.stable_id!r}: "
                f"version {registration.version!r} is already registered"
            )

    def _resolve_without_lockfile(
        self,
        stable_id: str,
        candidates: tuple[RegisteredPackExport, ...],
    ) -> RegisteredPackExport:
        if len(candidates) != 1:
            versions = ", ".join(repr(candidate.version) for candidate in candidates)
            raise LookupError(
                f"ambiguous registered pack export for stable_id {stable_id!r}: "
                f"versions [{versions}] require an exact PackLockfile pin"
            )
        return candidates[0]

    def _select_lockfile_entry(
        self,
        stable_id: str,
        lockfile: PackLockfile,
    ) -> LockfileEntry:
        matches = [entry for entry in lockfile.entries if entry.stable_id == stable_id]
        if not matches:
            raise LookupError(
                f"missing lockfile entry for stable_id {stable_id!r} in PackLockfile"
            )
        if len(matches) != 1:
            versions = ", ".join(repr(entry.version) for entry in matches)
            raise LookupError(
                f"ambiguous lockfile entries for stable_id {stable_id!r}: "
                f"versions [{versions}]"
            )
        return matches[0]

    def _resolve_with_lockfile(
        self,
        stable_id: str,
        candidates: tuple[RegisteredPackExport, ...],
        lockfile_entry: LockfileEntry,
    ) -> RegisteredPackExport:
        version_matches = [
            candidate
            for candidate in candidates
            if candidate.version == lockfile_entry.version
        ]
        if not version_matches:
            registered_versions = ", ".join(repr(candidate.version) for candidate in candidates)
            raise LookupError(
                f"unregistered pinned version for stable_id {stable_id!r}: "
                f"lockfile requires version {lockfile_entry.version!r}, "
                f"registered versions are [{registered_versions}]"
            )
        if len(version_matches) != 1:
            raise LookupError(
                f"ambiguous registered export for stable_id {stable_id!r} at "
                f"version {lockfile_entry.version!r}"
            )

        registration = version_matches[0]
        if registration.interface_hash != lockfile_entry.interface_hash:
            raise LookupError(
                f"interface hash mismatch for stable_id {stable_id!r}: "
                f"lockfile expects {lockfile_entry.interface_hash!r} at version "
                f"{lockfile_entry.version!r}, but registered export has "
                f"{registration.interface_hash!r}"
            )
        return registration

    def _record_resolution(
        self,
        *,
        stable_id: str,
        lockfile_entry: LockfileEntry | None,
        dependent_program: NativeProgram | None,
        dependent_name: str | None,
        dependent_stable_id: str | None,
        call_site_paths: tuple[str, ...],
    ) -> None:
        if lockfile_entry is None:
            return

        program_stable_id = dependent_program.stable_id if dependent_program else dependent_stable_id
        program_name = dependent_program.name if dependent_program else dependent_name
        if not program_name:
            return

        self.reverse_index.register(
            dependency_stable_id=stable_id,
            program_stable_id=program_stable_id,
            program_name=program_name,
            call_site_paths=call_site_paths,
            lockfile_entry=lockfile_entry,
        )


__all__ = [
    "PackRegistry",
    "RegisteredPackExport",
    "ResolvedPackExport",
]
