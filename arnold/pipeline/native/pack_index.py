"""Pack reverse dependency index — stable_id → dependent program records.

Provides :class:`PackReverseIndex`, a mutable registry that maps an exported
unit's stable ID to every program that depends on it, recording the
dependent program's identity, call-site paths, and pinned lockfile version
data.  This is the complement of the manifest dependency declarations:
manifests declare *outgoing* dependencies; the reverse index answers *who
depends on me?*
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.pipeline.native.pack_metadata import LockfileEntry


# ── Dependent record ───────────────────────────────────────────────────

@dataclass(frozen=True)
class DependentRecord:
    """A single dependent program entry in the reverse index.

    Captures the identity of a program that depends on a particular
    exported stable ID, together with the call-site paths where the
    dependency is referenced and the pinned lockfile version data
    (if available).
    """

    program_stable_id: str | None
    """Stable identity of the *dependent* program, or ``None``."""

    program_name: str
    """Human-readable name of the dependent program."""

    call_site_paths: tuple[str, ...] = ()
    """Stable call-site paths where this dependency is referenced
    within the dependent program (e.g. ``('root/validate', 'root/build')``).
    """

    lockfile_entry: LockfileEntry | None = None
    """Pinned lockfile entry capturing the exact version and interface
    hash that the dependent has locked.  ``None`` when no lockfile data
    has been registered."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain JSON-compatible dictionary."""
        result: dict[str, Any] = {
            "program_name": self.program_name,
        }
        if self.program_stable_id is not None:
            result["program_stable_id"] = self.program_stable_id
        if self.call_site_paths:
            result["call_site_paths"] = list(self.call_site_paths)
        if self.lockfile_entry is not None:
            result["lockfile_entry"] = self.lockfile_entry.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DependentRecord:
        """Deserialize from a plain dictionary.

        Raises
        ------
        KeyError
            If ``program_name`` is missing.
        """
        return cls(
            program_stable_id=data.get("program_stable_id"),
            program_name=data["program_name"],
            call_site_paths=tuple(data.get("call_site_paths", ())),
            lockfile_entry=(
                LockfileEntry.from_dict(data["lockfile_entry"])
                if "lockfile_entry" in data
                else None
            ),
        )


# ── Reverse index ──────────────────────────────────────────────────────

@dataclass
class PackReverseIndex:
    """Reverse dependency index for pack exports.

    Maps each exported stable ID to the set of programs that depend on it.
    Maintains both a forward map (program → its dependency stable IDs)
    and a reverse map (dependency stable ID → dependent programs) so that
    containment (transitive), ancestor-chain, path-prefix, and
    cross-program queries are all answerable.

    Typical usage::

        index = PackReverseIndex()
        index.register(
            dependency_stable_id="shared_step",
            program_stable_id="my_workflow",
            program_name="my_workflow",
            call_site_paths=("root/step_A",),
            lockfile_entry=LockfileEntry(
                stable_id="shared_step", version="1.0.0",
                interface_hash="sha256:abcd...",
            ),
        )
        deps = index.dependents_of("shared_step")
    """

    # Internal mappings
    _dep_to_dependents: dict[str, list[DependentRecord]] = field(default_factory=dict)
    _program_to_deps: dict[str, list[str]] = field(default_factory=dict)

    # ── Registration ───────────────────────────────────────────────

    def register(
        self,
        dependency_stable_id: str,
        program_stable_id: str | None,
        program_name: str,
        call_site_paths: tuple[str, ...] = (),
        lockfile_entry: LockfileEntry | None = None,
    ) -> None:
        """Register a dependent program for *dependency_stable_id*.

        Multiple calls for the same ``(dependency_stable_id,
        program_stable_id)`` pair are additive — the *call_site_paths*
        from later calls are merged into the existing record and the
        latest *lockfile_entry* wins.

        Parameters
        ----------
        dependency_stable_id:
            The stable ID of the export that the dependent program uses.
        program_stable_id:
            The stable identity of the dependent program, or ``None``.
        program_name:
            Human-readable name of the dependent program.
        call_site_paths:
            Stable call-site paths where the dependency is referenced
            within *program_name*.
        lockfile_entry:
            Pinned lockfile entry for this dependency, or ``None``.
        """
        if not dependency_stable_id:
            raise ValueError("dependency_stable_id must be non-empty")
        if not program_name:
            raise ValueError("program_name must be non-empty")

        key = program_stable_id or program_name

        # Find or create the dependent record
        existing: DependentRecord | None = None
        existing_idx: int | None = None
        dep_list = self._dep_to_dependents.setdefault(dependency_stable_id, [])
        for i, rec in enumerate(dep_list):
            rec_key = rec.program_stable_id or rec.program_name
            if rec_key == key:
                existing = rec
                existing_idx = i
                break

        merged_paths = (
            existing.call_site_paths + call_site_paths
            if existing is not None
            else call_site_paths
        )
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_paths: list[str] = []
        for p in merged_paths:
            if p not in seen:
                seen.add(p)
                unique_paths.append(p)

        record = DependentRecord(
            program_stable_id=program_stable_id,
            program_name=program_name,
            call_site_paths=tuple(unique_paths),
            lockfile_entry=(
                lockfile_entry
                if lockfile_entry is not None
                else (existing.lockfile_entry if existing is not None else None)
            ),
        )

        if existing_idx is not None:
            dep_list[existing_idx] = record
        else:
            dep_list.append(record)

        # Forward map
        fwd_key = program_stable_id or program_name
        fwd_list = self._program_to_deps.setdefault(fwd_key, [])
        if dependency_stable_id not in fwd_list:
            fwd_list.append(dependency_stable_id)

    # ── Queries ────────────────────────────────────────────────────

    def dependents_of(self, stable_id: str) -> tuple[DependentRecord, ...]:
        """Return all programs that directly depend on *stable_id*.

        Returns an empty tuple when *stable_id* is unknown or has no
        registered dependents.
        """
        if not stable_id:
            return ()
        return tuple(self._dep_to_dependents.get(stable_id, ()))

    def transitive_dependents_of(self, stable_id: str) -> tuple[DependentRecord, ...]:
        """Return all transitive dependents of *stable_id* via BFS.

        This is **containment traversal**: if program B depends on A,
        and program C depends on B, then C is a transitive dependent of A.

        Results are returned in BFS order.  The direct dependents come
        first, followed by their dependents, and so on.  Each program
        appears at most once (first encounter wins).
        """
        if not stable_id:
            return ()

        result: list[DependentRecord] = []
        visited: set[str] = set()
        queue: deque[str] = deque([stable_id])

        while queue:
            current_dep_id = queue.popleft()
            for dependent in self.dependents_of(current_dep_id):
                dep_key = dependent.program_stable_id or dependent.program_name
                if dep_key not in visited:
                    visited.add(dep_key)
                    result.append(dependent)
                    queue.append(dep_key)

        return tuple(result)

    def lookup_by_path_prefix(
        self, prefix: str
    ) -> tuple[tuple[str, DependentRecord], ...]:
        """Return ``(dependency_stable_id, DependentRecord)`` pairs where
        **any** call-site path of the dependent starts with *prefix*.

        Results are returned in registration order within each
        dependency stable ID.  An empty tuple is returned when *prefix*
        is empty or has no matches.
        """
        if not prefix:
            return ()

        results: list[tuple[str, DependentRecord]] = []
        for dep_stable_id, records in self._dep_to_dependents.items():
            for rec in records:
                for csp in rec.call_site_paths:
                    if csp.startswith(prefix):
                        results.append((dep_stable_id, rec))
                        break  # one match per record is enough

        return tuple(results)

    def ancestors_of(self, program_stable_id: str | None) -> tuple[str, ...]:
        """Return the dependency chain that *program_stable_id* depends on.

        The chain is walked upward via the forward map: given a program,
        find the stable IDs it depends on, then find what *those* IDs
        depend on, and so on.  Ancestors are returned from direct
        dependencies (nearest) to most-distant transitive dependency.

        Cycle detection prevents infinite loops when dependency graphs
        contain cycles.

        Parameters
        ----------
        program_stable_id:
            The stable identity or name of the dependent program.
            If ``None`` or empty, returns an empty tuple.
        """
        if not program_stable_id:
            return ()

        result: list[str] = []
        visited: set[str] = {program_stable_id}
        queue: deque[str] = deque()

        # Seed with direct dependencies
        direct = self._program_to_deps.get(program_stable_id, [])
        for dep_id in direct:
            if dep_id not in visited:
                visited.add(dep_id)
                result.append(dep_id)
                queue.append(dep_id)

        while queue:
            current = queue.popleft()
            for dep_id in self._program_to_deps.get(current, []):
                if dep_id not in visited:
                    visited.add(dep_id)
                    result.append(dep_id)
                    queue.append(dep_id)

        return tuple(result)

    def cross_program_dependents(
        self, program_stable_id: str
    ) -> tuple[DependentRecord, ...]:
        """Return all programs that depend on *program_stable_id*.

        This is a cross-program reverse dependency query: given a
        program's stable ID, find every other program whose dependency
        declarations include it.  The result is derived by scanning the
        reverse index for dependent records whose registered dependency
        stable ID matches *program_stable_id*.

        Returns an empty tuple when no program depends on the given ID.
        """
        return self.dependents_of(program_stable_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain JSON-compatible dictionary."""
        return {
            "dependents": {
                dep_id: [rec.to_dict() for rec in recs]
                for dep_id, recs in self._dep_to_dependents.items()
            },
            "forward": {
                prog_id: list(dep_ids)
                for prog_id, dep_ids in self._program_to_deps.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PackReverseIndex:
        """Deserialize from a plain dictionary."""
        index = cls()
        for dep_id, rec_list in data.get("dependents", {}).items():
            for rec_data in rec_list:
                record = DependentRecord.from_dict(rec_data)
                index._dep_to_dependents.setdefault(dep_id, []).append(record)
        for prog_id, dep_ids in data.get("forward", {}).items():
            index._program_to_deps[prog_id] = list(dep_ids)
        return index


__all__ = [
    "DependentRecord",
    "PackReverseIndex",
]
