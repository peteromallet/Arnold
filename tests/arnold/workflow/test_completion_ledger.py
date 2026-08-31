"""Tests for DivergenceEntry, DivergenceLedger, append-entry, hash chain, narrow.

Exercises append-only semantics, hash chain integrity, and narrowing
functionality.

.. caution::
   This package is **experimental and non-authoritative** — see
   :mod:`arnold.workflow.completion` for the full disclaimer.
"""

from __future__ import annotations

import pytest

from arnold.workflow.completion.ledger import (
    DivergenceEntry,
    DivergenceLedger,
    append_entry,
    compute_entry_hash,
    narrow_entry,
    validate_ledger_chain,
)


# ---------------------------------------------------------------------------
# DivergenceEntry — construction and invariants
# ---------------------------------------------------------------------------


class TestDivergenceEntry:
    """DivergenceEntry dataclass construction and validation."""

    def test_basic_construction(self) -> None:
        """Minimal DivergenceEntry with required fields."""
        entry = DivergenceEntry(
            entry_id="entry-001",
            spec_hash="sha256:" + "a" * 64,
            binding_hash="sha256:" + "b" * 64,
        )
        assert entry.entry_id == "entry-001"
        assert entry.spec_hash == "sha256:" + "a" * 64
        assert entry.binding_hash == "sha256:" + "b" * 64
        assert entry.entry_hash.startswith("sha256:")
        assert entry.previous_entry_hash == ""

    def test_auto_computes_entry_hash(self) -> None:
        """Entry hash is auto-computed when not provided."""
        entry = DivergenceEntry(
            entry_id="entry-auto",
            spec_hash="sha256:" + "a" * 64,
            binding_hash="sha256:" + "b" * 64,
        )
        expected = compute_entry_hash(
            entry_id="entry-auto",
            spec_hash="sha256:" + "a" * 64,
            binding_hash="sha256:" + "b" * 64,
            previous_entry_hash="",
        )
        assert entry.entry_hash == expected

    def test_requires_entry_id(self) -> None:
        """ValueError on empty entry_id."""
        with pytest.raises(ValueError, match="entry_id"):
            DivergenceEntry(
                entry_id="",
                spec_hash="sha256:" + "a" * 64,
                binding_hash="sha256:" + "b" * 64,
            )

    def test_requires_sha256_prefix(self) -> None:
        """ValueError on non-sha256 prefixed entry_hash."""
        with pytest.raises(ValueError, match="sha256:"):
            DivergenceEntry(
                entry_id="entry-bad-hash",
                spec_hash="sha256:" + "a" * 64,
                binding_hash="sha256:" + "b" * 64,
                entry_hash="md5:abc123",
            )

    def test_round_trip(self) -> None:
        """Round-trip through to_dict and from_dict."""
        entry = DivergenceEntry(
            entry_id="entry-rt",
            spec_hash="sha256:" + "c" * 64,
            binding_hash="sha256:" + "d" * 64,
        )
        data = entry.to_dict()
        restored = DivergenceEntry.from_dict(data)
        assert restored.entry_hash == entry.entry_hash
        assert restored.entry_id == entry.entry_id
        assert restored.spec_hash == entry.spec_hash
        assert restored.binding_hash == entry.binding_hash

    def test_preserves_previous_entry_hash(self) -> None:
        """Previous entry hash is preserved in serialization."""
        entry = DivergenceEntry(
            entry_id="entry-chain",
            spec_hash="sha256:" + "e" * 64,
            binding_hash="sha256:" + "f" * 64,
            previous_entry_hash="sha256:prev_hash_placeholder_abcdef1234567890abcdef1234567890abcdef",
        )
        data = entry.to_dict()
        assert "previous_entry_hash" in data
        restored = DivergenceEntry.from_dict(data)
        assert restored.previous_entry_hash == entry.previous_entry_hash


# ---------------------------------------------------------------------------
# DivergenceLedger — append-only container
# ---------------------------------------------------------------------------


class TestDivergenceLedger:
    """DivergenceLedger container."""

    def test_empty_ledger(self) -> None:
        """Empty ledger has no entries."""
        ledger = DivergenceLedger()
        assert len(ledger) == 0
        assert ledger.entries == ()

    def test_ledger_with_entries(self) -> None:
        """Ledger preserves entries in order."""
        entry = DivergenceEntry(
            entry_id="entry-ledger-1",
            spec_hash="sha256:" + "g" * 64,
            binding_hash="sha256:" + "h" * 64,
        )
        ledger = DivergenceLedger(entries=(entry,))
        assert len(ledger) == 1
        assert ledger.entries[0].entry_id == "entry-ledger-1"

    def test_round_trip(self) -> None:
        """Ledger round-trips through to_dict and from_dict."""
        entry = DivergenceEntry(
            entry_id="entry-lrt",
            spec_hash="sha256:" + "i" * 64,
            binding_hash="sha256:" + "j" * 64,
        )
        ledger = DivergenceLedger(entries=(entry,))
        data = ledger.to_dict()
        restored = DivergenceLedger.from_dict(data)
        assert len(restored) == 1
        assert restored.entries[0].entry_id == entry.entry_id
        assert restored.entries[0].entry_hash == entry.entry_hash


# ---------------------------------------------------------------------------
# append_entry — appending to the ledger
# ---------------------------------------------------------------------------


class TestAppendEntry:
    """append_entry maintains hash chain."""

    def test_append_to_empty(self) -> None:
        """Appending to empty ledger creates genesis entry."""
        ledger = DivergenceLedger()
        new_ledger = append_entry(
            ledger,
            entry_id="entry-genesis",
            spec_hash="sha256:" + "k" * 64,
            binding_hash="sha256:" + "l" * 64,
        )
        assert len(new_ledger) == 1
        assert new_ledger.entries[0].entry_id == "entry-genesis"
        assert new_ledger.entries[0].previous_entry_hash == ""

    def test_append_chains_hash(self) -> None:
        """Appended entry references previous entry's hash."""
        ledger = DivergenceLedger()
        ledger = append_entry(
            ledger,
            entry_id="entry-first",
            spec_hash="sha256:" + "m" * 64,
            binding_hash="sha256:" + "n" * 64,
        )
        ledger = append_entry(
            ledger,
            entry_id="entry-second",
            spec_hash="sha256:" + "o" * 64,
            binding_hash="sha256:" + "p" * 64,
        )
        assert len(ledger) == 2
        assert ledger.entries[1].previous_entry_hash == ledger.entries[0].entry_hash

    def test_immutability(self) -> None:
        """Original ledger is not mutated."""
        original = DivergenceLedger()
        _ = append_entry(
            original,
            entry_id="entry-immutable",
            spec_hash="sha256:" + "q" * 64,
            binding_hash="sha256:" + "r" * 64,
        )
        assert len(original) == 0

    def test_multiple_appends(self) -> None:
        """Multiple appends build a chain."""
        ledger = DivergenceLedger()
        for i in range(3):
            ledger = append_entry(
                ledger,
                entry_id=f"entry-{i}",
                spec_hash="sha256:" + str(i) * 64,
                binding_hash="sha256:" + str(i + 10) * 64,
            )
        assert len(ledger) == 3


# ---------------------------------------------------------------------------
# validate_ledger_chain — hash chain integrity
# ---------------------------------------------------------------------------


class TestValidateLedgerChain:
    """validate_ledger_chain integrity check."""

    def test_valid_chain(self) -> None:
        """Valid hash chain passes validation."""
        ledger = DivergenceLedger()
        ledger = append_entry(
            ledger,
            entry_id="entry-v1",
            spec_hash="sha256:" + "s" * 64,
            binding_hash="sha256:" + "t" * 64,
        )
        ledger = append_entry(
            ledger,
            entry_id="entry-v2",
            spec_hash="sha256:" + "u" * 64,
            binding_hash="sha256:" + "v" * 64,
        )
        validate_ledger_chain(ledger)  # Should not raise

    def test_empty_ledger_valid(self) -> None:
        """Empty ledger passes validation."""
        validate_ledger_chain(DivergenceLedger())  # Should not raise

    def test_broken_genesis(self) -> None:
        """Genesis entry with non-empty previous_entry_hash raises."""
        broken_entry = DivergenceEntry(
            entry_id="entry-broken-genesis",
            spec_hash="sha256:" + "w" * 64,
            binding_hash="sha256:" + "x" * 64,
            previous_entry_hash="sha256:previous_should_be_empty_0123456789abcdef0123456789abcdef0123",
            entry_hash="sha256:abc123def4567890abcdef1234567890abcdef1234567890abcdef",
        )
        ledger = DivergenceLedger(entries=(broken_entry,))
        with pytest.raises(ValueError, match="previous_entry_hash"):
            validate_ledger_chain(ledger)

    def test_broken_chain(self) -> None:
        """Mismatched previous_entry_hash raises."""
        ledger = DivergenceLedger()
        ledger = append_entry(
            ledger,
            entry_id="entry-chain-a",
            spec_hash="sha256:" + "y" * 64,
            binding_hash="sha256:" + "z" * 64,
        )
        # Manually create a broken entry
        broken = DivergenceEntry(
            entry_id="entry-broken-link",
            spec_hash="sha256:" + "a" * 64,
            binding_hash="sha256:" + "b" * 64,
            previous_entry_hash="sha256:wrong_hash_value_000000000000000000000000000000000000000000",
        )
        ledger = DivergenceLedger(entries=ledger.entries + (broken,))
        with pytest.raises(ValueError, match="previous_entry_hash"):
            validate_ledger_chain(ledger)


# ---------------------------------------------------------------------------
# narrow_entry — append-only selectors and updates
# ---------------------------------------------------------------------------


class TestNarrowEntry:
    """narrow_entry preserves stable occurrences while updating one occurrence."""

    def _ledger_with_entries(self) -> DivergenceLedger:
        """Helper: create a ledger with two entries."""
        ledger = DivergenceLedger()
        ledger = append_entry(
            ledger,
            entry_id="entry-narrow-a",
            spec_hash="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            binding_hash="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        ledger = append_entry(
            ledger,
            entry_id="entry-narrow-b",
            spec_hash="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            binding_hash="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        )
        return ledger

    def test_no_filters_returns_all(self) -> None:
        """No filters returns all entries."""
        ledger = self._ledger_with_entries()
        narrowed = narrow_entry(ledger)
        assert len(narrowed) == 2

    def test_filter_by_spec_hash(self) -> None:
        """A selector-only call never removes unrelated entries."""
        ledger = self._ledger_with_entries()
        narrowed = narrow_entry(
            ledger,
            spec_hash="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        assert [entry.entry_id for entry in narrowed.entries] == [
            "entry-narrow-a", "entry-narrow-b"
        ]
        assert narrowed == ledger

    def test_filter_by_binding_hash(self) -> None:
        """Binding selectors also preserve the complete ledger."""
        ledger = self._ledger_with_entries()
        narrowed = narrow_entry(
            ledger,
            binding_hash="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        )
        assert [entry.entry_id for entry in narrowed.entries] == [
            "entry-narrow-a", "entry-narrow-b"
        ]

    def test_filter_by_entry_id(self) -> None:
        """An entry selector does not filter the stable-occurrence ledger."""
        ledger = self._ledger_with_entries()
        narrowed = narrow_entry(ledger, entry_id="entry-narrow-a")
        assert narrowed.entries == ledger.entries

    def test_compound_filter(self) -> None:
        """Compound selectors preserve order and all stable IDs."""
        ledger = self._ledger_with_entries()
        narrowed = narrow_entry(
            ledger,
            spec_hash="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            entry_id="entry-narrow-a",
        )
        assert narrowed.entries == ledger.entries

    def test_no_match_returns_empty(self) -> None:
        """A selector miss is a non-destructive no-op."""
        ledger = self._ledger_with_entries()
        narrowed = narrow_entry(
            ledger,
            spec_hash="sha256:nonexistent_hash_value_0000000000000000000000000000000000000000",
        )
        assert narrowed == ledger

    def test_update_preserves_siblings_and_original(self) -> None:
        """Updating one occurrence keeps siblings and leaves input immutable."""
        ledger = self._ledger_with_entries()
        updated = narrow_entry(
            ledger,
            entry_id="entry-narrow-a",
            updated={"evidence_refs": ("evidence:one",)},
        )
        assert [entry.entry_id for entry in updated.entries] == [
            "entry-narrow-a", "entry-narrow-b"
        ]
        assert updated.entries[1].spec_hash == ledger.entries[1].spec_hash
        assert updated.entries[0].evidence_refs == ("evidence:one",)
        assert ledger.entries[0].evidence_refs == ()
        validate_ledger_chain(updated)

    def test_update_can_resolve_by_stable_selectors(self) -> None:
        """A unique spec selector identifies the occurrence being updated."""
        ledger = self._ledger_with_entries()
        updated = narrow_entry(
            ledger,
            spec_hash=ledger.entries[1].spec_hash,
            updated={"disposition": "accepted"},
        )
        assert updated.entries[1].disposition.value == "accepted"
        assert [entry.entry_id for entry in updated.entries] == [
            "entry-narrow-a", "entry-narrow-b"
        ]
        validate_ledger_chain(updated)

    def test_update_requires_unique_target(self) -> None:
        """An update without a unique stable target fails closed."""
        ledger = self._ledger_with_entries()
        with pytest.raises(ValueError, match="exactly one"):
            narrow_entry(ledger, updated={"disposition": "accepted"})
        with pytest.raises(ValueError, match="exactly one"):
            narrow_entry(
                ledger,
                spec_hash="sha256:nonexistent_hash_value_0000000000000000000000000000000000000000",
                updated={"disposition": "accepted"},
            )
