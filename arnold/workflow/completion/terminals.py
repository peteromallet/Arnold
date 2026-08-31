"""Named-exit supersession terminals with complete custody metadata.

Named exits are shadow-only records.  They can describe a supersession but
cannot accept, complete, or otherwise authorize a completion claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from arnold.workflow.completion.hashing import hash_canonical
from arnold.workflow.completion.outcomes import CandidateOutcome


def _named_exit_hash_payload(
    exit_name: str,
    target_loop_id: str,
    source_declaration_ref: str,
    intervening_bindings: tuple[str, ...],
    ordered_unwind_set: tuple[str, ...],
    superseded_spec_hashes: tuple[str, ...],
    previous_exit_hash: str,
) -> dict[str, Any]:
    """Build the complete content-addressed identity payload for a named exit."""
    return {
        "exit_name": exit_name,
        "target_loop_id": target_loop_id,
        "source_declaration_ref": source_declaration_ref,
        "intervening_bindings": list(intervening_bindings),
        "ordered_unwind_set": list(ordered_unwind_set),
        "superseded_spec_hashes": list(superseded_spec_hashes),
        "previous_exit_hash": previous_exit_hash,
    }


def compute_exit_hash(
    exit_name: str,
    target_loop_id: str,
    source_declaration_ref: str,
    intervening_bindings: tuple[str, ...],
    ordered_unwind_set: tuple[str, ...],
    superseded_spec_hashes: tuple[str, ...] = (),
    previous_exit_hash: str = "",
) -> str:
    """Compute a hash over every custody-bearing field of a named exit."""
    return hash_canonical(
        _named_exit_hash_payload(
            exit_name,
            target_loop_id,
            source_declaration_ref,
            intervening_bindings,
            ordered_unwind_set,
            superseded_spec_hashes,
            previous_exit_hash,
        )
    )


@dataclass(frozen=True)
class NamedExit:
    """A supersession record that carries complete unwind custody.

    No field may be omitted: an exit name alone cannot explain what loop was
    exited, where the claim originated, which bindings were crossed, or which
    occurrences were unwound.  The ordered collections are part of identity,
    not merely diagnostic annotations.
    """

    exit_name: str
    target_loop_id: str
    source_declaration_ref: str
    intervening_bindings: tuple[str, ...]
    """Binding hashes, each in ``sha256:`` + 64-hex format."""

    ordered_unwind_set: tuple[str, ...]
    superseded_spec_hashes: tuple[str, ...] = ()
    """Superseded spec hashes, each in ``sha256:`` + 64-hex format."""

    exit_hash: str = ""
    """This exit's content hash in ``sha256:`` + 64-hex format."""

    previous_exit_hash: str = ""
    """Prior exit-chain hash in ``sha256:`` + 64-hex format, or empty at genesis."""

    def __post_init__(self) -> None:
        required_values = {
            "exit_name": self.exit_name,
            "target_loop_id": self.target_loop_id,
            "source_declaration_ref": self.source_declaration_ref,
        }
        for field_name, value in required_values.items():
            if not value:
                raise ValueError(f"NamedExit.{field_name} must be non-empty")
        if not self.intervening_bindings:
            raise ValueError("NamedExit.intervening_bindings must be non-empty")
        if not self.ordered_unwind_set:
            raise ValueError("NamedExit.ordered_unwind_set must be non-empty")
        if any(not binding for binding in self.intervening_bindings):
            raise ValueError("NamedExit.intervening_bindings cannot contain empty hashes")
        if any(not instance for instance in self.ordered_unwind_set):
            raise ValueError("NamedExit.ordered_unwind_set cannot contain empty instances")
        if len(set(self.ordered_unwind_set)) != len(self.ordered_unwind_set):
            raise ValueError("NamedExit.ordered_unwind_set cannot contain duplicates")
        if not self.exit_hash:
            object.__setattr__(
                self,
                "exit_hash",
                compute_exit_hash(
                    self.exit_name,
                    self.target_loop_id,
                    self.source_declaration_ref,
                    self.intervening_bindings,
                    self.ordered_unwind_set,
                    self.superseded_spec_hashes,
                    self.previous_exit_hash,
                ),
            )
        if not self.exit_hash.startswith("sha256:"):
            raise ValueError("NamedExit.exit_hash must start with 'sha256:'")

    def to_dict(self) -> dict[str, Any]:
        """Return a complete deterministic representation."""
        return {
            "exit_name": self.exit_name,
            "target_loop_id": self.target_loop_id,
            "source_declaration_ref": self.source_declaration_ref,
            "intervening_bindings": list(self.intervening_bindings),
            "ordered_unwind_set": list(self.ordered_unwind_set),
            "superseded_spec_hashes": list(self.superseded_spec_hashes),
            "exit_hash": self.exit_hash,
            "previous_exit_hash": self.previous_exit_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NamedExit:
        """Reconstruct a fully-custodied named exit, rejecting omissions."""
        return cls(
            exit_name=str(data["exit_name"]),
            target_loop_id=str(data["target_loop_id"]),
            source_declaration_ref=str(data["source_declaration_ref"]),
            intervening_bindings=tuple(str(v) for v in data["intervening_bindings"]),
            ordered_unwind_set=tuple(str(v) for v in data["ordered_unwind_set"]),
            superseded_spec_hashes=tuple(
                str(v) for v in data.get("superseded_spec_hashes", ())
            ),
            exit_hash=str(data.get("exit_hash", "")),
            previous_exit_hash=str(data.get("previous_exit_hash", "")),
        )


@dataclass(frozen=True)
class NamedExitVerdict:
    """A non-authoritative result of validating a named-exit claim."""

    named_exit: NamedExit
    outcome: CandidateOutcome = CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT
    accepted: bool = False
    failures: tuple[str, ...] = (
        "shadow_only_named_exit_cannot_satisfy_completion",
    )


def superseded_by_named_exit(
    named_exit: NamedExit,
    prior_bindings: tuple[str, ...],
) -> NamedExitVerdict:
    """Validate a named exit and return its shadow-only supersession verdict.

    ``prior_bindings`` must be the complete ordered binding sequence crossed
    before the exit.  A subset would erase custody information and is
    rejected as supersession laundering.
    """
    if tuple(prior_bindings) != named_exit.intervening_bindings:
        raise ValueError(
            "Named-exit supersession rejected: intervening bindings do not "
            "match the complete prior binding sequence"
        )
    return NamedExitVerdict(named_exit=named_exit)


def validate_named_exit_chain(named_exits: tuple[NamedExit, ...]) -> None:
    """Validate custody completeness, content hashes, and chain linkage."""
    previous_hash = ""
    for index, record in enumerate(named_exits):
        expected_hash = compute_exit_hash(
            record.exit_name,
            record.target_loop_id,
            record.source_declaration_ref,
            record.intervening_bindings,
            record.ordered_unwind_set,
            record.superseded_spec_hashes,
            record.previous_exit_hash,
        )
        if record.exit_hash != expected_hash:
            raise ValueError(f"NamedExit hash mismatch at index {index}")
        if record.previous_exit_hash != previous_hash:
            raise ValueError(
                f"NamedExit chain broken at index {index}: expected "
                f"previous_exit_hash={previous_hash!r}, got "
                f"{record.previous_exit_hash!r}"
            )
        previous_hash = record.exit_hash
