"""Append-only, content-addressed divergence ledger.

The ledger records one stable occurrence for every parity difference.  A
narrowing pass may add evidence or change disposition for that occurrence; it
never filters unrelated entries out of the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Mapping

from arnold.workflow.completion.hashing import hash_canonical


class DivergenceKind(StrEnum):
    """The bounded source categories for a parity divergence."""

    OLD_SYSTEM_DEFECT = "old_system_defect"
    KERNEL_DEFECT = "kernel_defect"
    INTENTIONAL_DIFFERENCE = "intentional_difference"


class DivergenceDisposition(StrEnum):
    """Lifecycle disposition of a stable divergence occurrence."""

    OPEN = "open"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    RESOLVED = "resolved"


def _divergence_entry_hash_payload(
    entry_id: str,
    spec_hash: str,
    binding_hash: str,
    kind: DivergenceKind,
    description: str,
    blocking: bool,
    evidence_refs: tuple[str, ...],
    disposition: DivergenceDisposition,
    supersession_lineage: tuple[str, ...],
    ledger_version: str,
    previous_entry_hash: str,
) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "spec_hash": spec_hash,
        "binding_hash": binding_hash,
        "kind": kind.value,
        "description": description,
        "blocking": blocking,
        "evidence_refs": list(evidence_refs),
        "disposition": disposition.value,
        "supersession_lineage": list(supersession_lineage),
        "ledger_version": ledger_version,
        "previous_entry_hash": previous_entry_hash,
    }


def compute_entry_hash(
    entry_id: str,
    spec_hash: str,
    binding_hash: str,
    kind: DivergenceKind | str = DivergenceKind.INTENTIONAL_DIFFERENCE,
    description: str = "unspecified divergence",
    blocking: bool = False,
    evidence_refs: tuple[str, ...] = (),
    disposition: DivergenceDisposition | str = DivergenceDisposition.OPEN,
    supersession_lineage: tuple[str, ...] = (),
    ledger_version: str = "arnold.completion.divergence.v1",
    previous_entry_hash: str = "",
) -> str:
    """Return the SHA-256 identity of every divergence entry field."""
    return hash_canonical(
        _divergence_entry_hash_payload(
            entry_id,
            spec_hash,
            binding_hash,
            DivergenceKind(kind),
            description,
            blocking,
            tuple(evidence_refs),
            DivergenceDisposition(disposition),
            tuple(supersession_lineage),
            ledger_version,
            previous_entry_hash,
        )
    )


@dataclass(frozen=True)
class DivergenceEntry:
    """One immutable, stable-occurrence parity divergence record."""

    entry_id: str
    spec_hash: str
    """Related spec hash in required ``sha256:`` + 64-hex format."""

    binding_hash: str
    """Related binding hash in required ``sha256:`` + 64-hex format."""

    kind: DivergenceKind = DivergenceKind.INTENTIONAL_DIFFERENCE
    description: str = "unspecified divergence"
    blocking: bool = False
    evidence_refs: tuple[str, ...] = ()
    disposition: DivergenceDisposition = DivergenceDisposition.OPEN
    supersession_lineage: tuple[str, ...] = ()
    ledger_version: str = "arnold.completion.divergence.v1"
    entry_hash: str = ""
    """This entry's content hash in required ``sha256:`` + 64-hex format."""

    previous_entry_hash: str = ""
    """Prior entry-chain hash in ``sha256:`` + 64-hex format, or empty at genesis."""

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            object.__setattr__(self, "kind", DivergenceKind(self.kind))
        if isinstance(self.disposition, str):
            object.__setattr__(
                self, "disposition", DivergenceDisposition(self.disposition)
            )
        object.__setattr__(self, "evidence_refs", tuple(str(v) for v in self.evidence_refs))
        object.__setattr__(
            self,
            "supersession_lineage",
            tuple(str(v) for v in self.supersession_lineage),
        )
        for field_name, value in {
            "entry_id": self.entry_id,
            "spec_hash": self.spec_hash,
            "binding_hash": self.binding_hash,
            "description": self.description,
            "ledger_version": self.ledger_version,
        }.items():
            if not value:
                raise ValueError(f"DivergenceEntry.{field_name} must be non-empty")
        if not self.entry_hash:
            object.__setattr__(
                self,
                "entry_hash",
                compute_entry_hash(
                    self.entry_id,
                    self.spec_hash,
                    self.binding_hash,
                    self.kind,
                    self.description,
                    self.blocking,
                    self.evidence_refs,
                    self.disposition,
                    self.supersession_lineage,
                    self.ledger_version,
                    self.previous_entry_hash,
                ),
            )
        if not self.entry_hash.startswith("sha256:"):
            raise ValueError("DivergenceEntry.entry_hash must start with 'sha256:'")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "spec_hash": self.spec_hash,
            "binding_hash": self.binding_hash,
            "kind": self.kind.value,
            "description": self.description,
            "blocking": self.blocking,
            "evidence_refs": list(self.evidence_refs),
            "disposition": self.disposition.value,
            "supersession_lineage": list(self.supersession_lineage),
            "ledger_version": self.ledger_version,
            "entry_hash": self.entry_hash,
            "previous_entry_hash": self.previous_entry_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DivergenceEntry:
        return cls(
            entry_id=str(data["entry_id"]),
            spec_hash=str(data["spec_hash"]),
            binding_hash=str(data["binding_hash"]),
            kind=DivergenceKind(data["kind"]),
            description=str(data["description"]),
            blocking=bool(data["blocking"]),
            evidence_refs=tuple(str(v) for v in data.get("evidence_refs", ())),
            disposition=DivergenceDisposition(data.get("disposition", "open")),
            supersession_lineage=tuple(
                str(v) for v in data.get("supersession_lineage", ())
            ),
            ledger_version=str(
                data.get("ledger_version", "arnold.completion.divergence.v1")
            ),
            entry_hash=str(data.get("entry_hash", "")),
            previous_entry_hash=str(data.get("previous_entry_hash", "")),
        )


def compute_ledger_hash(
    entries: tuple[DivergenceEntry, ...],
    ledger_version: str,
) -> str:
    """Return the content-addressed identity of an ordered ledger."""
    return hash_canonical(
        {
            "entries": [entry.to_dict() for entry in entries],
            "ledger_version": ledger_version,
        }
    )


@dataclass(frozen=True)
class DivergenceLedger:
    """An ordered stable-occurrence ledger with an aggregate content hash."""

    entries: tuple[DivergenceEntry, ...] = ()
    ledger_version: str = "arnold.completion.divergence.v1"
    ledger_hash: str = ""
    """Aggregate ledger hash in required ``sha256:`` + 64-hex format."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        if not self.ledger_version:
            raise ValueError("DivergenceLedger.ledger_version must be non-empty")
        if not self.ledger_hash:
            object.__setattr__(
                self,
                "ledger_hash",
                compute_ledger_hash(self.entries, self.ledger_version),
            )
        if not self.ledger_hash.startswith("sha256:"):
            raise ValueError("DivergenceLedger.ledger_hash must start with 'sha256:'")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "ledger_version": self.ledger_version,
            "ledger_hash": self.ledger_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DivergenceLedger:
        return cls(
            entries=tuple(
                DivergenceEntry.from_dict(entry)
                if isinstance(entry, Mapping)
                else entry
                for entry in data.get("entries", ())
            ),
            ledger_version=str(
                data.get("ledger_version", "arnold.completion.divergence.v1")
            ),
            ledger_hash=str(data.get("ledger_hash", "")),
        )

    def __len__(self) -> int:
        return len(self.entries)


def append_entry(
    ledger: DivergenceLedger,
    new_entry: DivergenceEntry | None = None,
    **entry_fields: Any,
) -> DivergenceLedger:
    """Append one new occurrence while deriving its chain predecessor."""
    if new_entry is None:
        new_entry = DivergenceEntry(**entry_fields)
    previous_entry_hash = ledger.entries[-1].entry_hash if ledger.entries else ""
    if new_entry.previous_entry_hash not in ("", previous_entry_hash):
        raise ValueError("New divergence entry has an incompatible previous_entry_hash")
    chained_entry = replace(
        new_entry,
        previous_entry_hash=previous_entry_hash,
        entry_hash="",
    )
    return DivergenceLedger(
        entries=ledger.entries + (chained_entry,),
        ledger_version=ledger.ledger_version,
    )


_NARROWABLE_FIELDS = frozenset({
    "evidence_refs",
    "disposition",
    "supersession_lineage",
})


def narrow_entry(
    ledger: DivergenceLedger,
    entry_id: str | None = None,
    updated: Mapping[str, Any] | DivergenceEntry | None = None,
    *,
    spec_hash: str | None = None,
    binding_hash: str | None = None,
) -> DivergenceLedger:
    """Narrow one occurrence without deleting or replacing any occurrence.

    Only evidence, disposition, and supersession lineage may change.  The
    changed entry and its successors are re-hashed to retain a contiguous
    lineage, while every stable entry ID and its position are preserved.
    """
    if updated is None:
        return ledger
    matching_indexes = _matching_indexes(
        ledger, entry_id=entry_id, spec_hash=spec_hash, binding_hash=binding_hash
    )
    if len(matching_indexes) != 1:
        raise ValueError(
            "narrow_entry update requires exactly one matching divergence entry"
        )
    index = matching_indexes[0]
    existing = ledger.entries[index]
    if isinstance(updated, DivergenceEntry):
        immutable_fields = (
            "entry_id", "spec_hash", "binding_hash", "kind", "description",
            "blocking", "ledger_version",
        )
        if any(getattr(updated, name) != getattr(existing, name) for name in immutable_fields):
            raise ValueError("narrow_entry cannot replace a stable occurrence")
        changes: Mapping[str, Any] = {
            "evidence_refs": updated.evidence_refs,
            "disposition": updated.disposition,
            "supersession_lineage": updated.supersession_lineage,
        }
    else:
        changes = _normalise_changes(updated)
    narrowed = _updated_entry(existing, changes)
    return _rebuild_ledger(ledger, index, narrowed)


def _matching_indexes(
    ledger: DivergenceLedger,
    *,
    entry_id: str | None,
    spec_hash: str | None,
    binding_hash: str | None,
) -> list[int]:
    """Return indexes matching all supplied stable-occurrence selectors."""
    return [
        index
        for index, entry in enumerate(ledger.entries)
        if (entry_id is None or entry.entry_id == entry_id)
        and (spec_hash is None or entry.spec_hash == spec_hash)
        and (binding_hash is None or entry.binding_hash == binding_hash)
    ]


def _normalise_changes(updated: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the mutable narrowing fields and return them unchanged."""
    unknown_fields = set(updated) - _NARROWABLE_FIELDS
    if unknown_fields:
        raise ValueError(
            "narrow_entry only updates evidence_refs, disposition, or "
            f"supersession_lineage; got {sorted(unknown_fields)!r}"
        )
    return updated


def _updated_entry(
    existing: DivergenceEntry,
    changes: Mapping[str, Any],
) -> DivergenceEntry:
    """Build a re-hashable entry containing only allowed mutable changes."""
    return replace(
        existing,
        evidence_refs=tuple(
            str(value) for value in changes.get("evidence_refs", existing.evidence_refs)
        ),
        disposition=DivergenceDisposition(
            changes.get("disposition", existing.disposition)
        ),
        supersession_lineage=tuple(
            str(value)
            for value in changes.get(
                "supersession_lineage", existing.supersession_lineage
            )
        ),
        entry_hash="",
    )


def _rebuild_ledger(
    ledger: DivergenceLedger,
    changed_index: int,
    changed_entry: DivergenceEntry,
) -> DivergenceLedger:
    """Rebuild the immutable chain from the changed occurrence onward."""
    rebuilt: list[DivergenceEntry] = []
    previous_entry_hash = ""
    for current_index, entry in enumerate(ledger.entries):
        candidate = changed_entry if current_index == changed_index else entry
        candidate = replace(
            candidate,
            previous_entry_hash=previous_entry_hash,
            entry_hash="",
        )
        rebuilt.append(candidate)
        previous_entry_hash = candidate.entry_hash
    return DivergenceLedger(
        entries=tuple(rebuilt),
        ledger_version=ledger.ledger_version,
    )


def validate_ledger_chain(ledger: DivergenceLedger) -> None:
    """Validate every entry hash, predecessor link, and aggregate hash."""
    previous_entry_hash = ""
    for index, entry in enumerate(ledger.entries):
        if entry.previous_entry_hash != previous_entry_hash:
            raise ValueError(
                f"DivergenceLedger chain broken at index {index}: expected "
                f"previous_entry_hash={previous_entry_hash!r}, got "
                f"{entry.previous_entry_hash!r}"
            )
        expected_hash = compute_entry_hash(
            entry.entry_id,
            entry.spec_hash,
            entry.binding_hash,
            entry.kind,
            entry.description,
            entry.blocking,
            entry.evidence_refs,
            entry.disposition,
            entry.supersession_lineage,
            entry.ledger_version,
            entry.previous_entry_hash,
        )
        if entry.entry_hash != expected_hash:
            raise ValueError(f"DivergenceLedger entry hash mismatch at index {index}")
        previous_entry_hash = entry.entry_hash
    expected_ledger_hash = compute_ledger_hash(ledger.entries, ledger.ledger_version)
    if ledger.ledger_hash != expected_ledger_hash:
        raise ValueError("DivergenceLedger aggregate hash mismatch")
