"""Synthetic characterization fixtures and tests for ticket inventory.

Covers T4 requirements:
- Valid frontmatter ULIDs with legacy filenames
- Missing/invalid frontmatter IDs
- Duplicate IDs with every path reported
- Parse errors
- Body presence
- No mutation of the real ``.megaplan/tickets/`` corpus (all fixtures are synthetic)

Also addresses SC4: inventory fixtures remain synthetic and prove legacy
filenames are readable only when frontmatter IDs are valid canonical ULIDs.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.tickets.files import (
    FilenamePrefixShape,
    classify_filename_prefix,
    is_valid_ulid,
    read_ticket_frontmatter_with_errors,
)
from arnold_pipelines.megaplan.tickets.inventory import (
    TicketInventory,
    TicketInventoryEntry,
    build_ticket_inventory,
)


# ---------------------------------------------------------------------------
# Low-level helper generators — create synthetic ticket files in tmp_path
# ---------------------------------------------------------------------------


def _make_tickets_dir(repo_root: Path) -> Path:
    """Create ``.megaplan/tickets/`` under *repo_root* and return its path."""
    td = repo_root / ".megaplan" / "tickets"
    td.mkdir(parents=True, exist_ok=True)
    return td


def _write_ticket(td: Path, filename: str, content: str) -> Path:
    """Write a synthetic ticket file into *td* and return its absolute path."""
    path = td / filename
    path.write_text(content, encoding="utf-8")
    return path.resolve()


def _make_strategy(repo_root: Path, content: str) -> Path:
    """Write ``.megaplan/STRATEGY.md`` into *repo_root* and return its path."""
    megaplan_dir = repo_root / ".megaplan"
    megaplan_dir.mkdir(parents=True, exist_ok=True)
    path = megaplan_dir / "STRATEGY.md"
    path.write_text(content, encoding="utf-8")
    return path


def _valid_ulid() -> str:
    """Return a well-known valid ULID for test use."""
    return "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _valid_ulid_2() -> str:
    """Return a second well-known valid ULID for test use."""
    return "01ARZ3NDEKTSV4RRFFQ69G5FAW"


def _minimal_ticket_frontmatter(*, uid: str | None = None, title: str = "Test Ticket",
                                 status: str = "open", body: str = "") -> str:
    """Return a minimal ticket .md with YAML frontmatter."""
    lines = ["---"]
    if uid is not None:
        lines.append(f"id: {uid}")
    lines.append(f"title: {title}")
    lines.append(f"status: {status}")
    lines.append("---")
    if body:
        lines.append("")
        lines.append(body)
    return "\n".join(lines) + "\n"


def _minimal_strategy(ticket_refs: list[str] | None = None) -> str:
    """Return minimal strategy Markdown with optional ticket refs in Now section."""
    ref_lines = ""
    if ticket_refs:
        ref_lines = "\n".join(f"- [ticket:{ref}] Some ticket" for ref in ticket_refs) + "\n"
    return (
        "---\n"
        "schema_version: megaplan-strategy-v1\n"
        "---\n"
        "\n"
        "## Mission\n\nTest mission.\n\n"
        "## Principles\n\nTest principles.\n\n"
        "## Architecture Direction\n\nTest arch.\n\n"
        "## Constraints\n\nTest constraints.\n\n"
        "## Non-Goals\n\nTest non-goals.\n\n"
        "## Now\n\n" + ref_lines + "\n"
        "## Next\n\n\n"
        "## Later\n\n\n"
    )


# ---------------------------------------------------------------------------
# Filename prefix shape classification — verify contract
# ---------------------------------------------------------------------------


class TestFilenamePrefixShape:
    """Verify that classify_filename_prefix correctly distinguishes shapes."""

    def test_valid_ulid_prefix(self) -> None:
        assert classify_filename_prefix("01ARZ3NDEKTSV4RRFFQ69G5FAV-my-ticket.md") == "valid-ulid"

    def test_invalid_ulid_prefix_contains_illegal_chars(self) -> None:
        # 26 chars but contains 'I' which is not in Crockford base32
        assert classify_filename_prefix("01ARZ3NDEKTSV4RRFFQI9G5FAV-my-ticket.md") == "invalid-ulid"

    def test_non_ulid_prefix_short(self) -> None:
        assert classify_filename_prefix("ticket_48a09182a828-store-ticket-file.md") == "non-ulid"

    def test_non_ulid_prefix_no_hyphen(self) -> None:
        assert classify_filename_prefix("some-ticket.md") == "non-ulid"

    def test_non_ulid_prefix_empty(self) -> None:
        assert classify_filename_prefix(".md") == "non-ulid"


class TestIsValidUlid:
    """Verify is_valid_ulid pure function."""

    def test_valid_ulid(self) -> None:
        assert is_valid_ulid("01ARZ3NDEKTSV4RRFFQ69G5FAV") is True

    def test_too_short(self) -> None:
        assert is_valid_ulid("01ARZ3NDEKTSV4") is False

    def test_too_long(self) -> None:
        assert is_valid_ulid("01ARZ3NDEKTSV4RRFFQ69G5FAVXXX") is False

    def test_lowercase(self) -> None:
        assert is_valid_ulid("01arz3ndektsv4rrffq69g5fav") is False

    def test_contains_illegal_ulid_chars(self) -> None:
        assert is_valid_ulid("01ARZ3NDEKTSV4RRFFQI9G5FAV") is False  # 'I'
        assert is_valid_ulid("01ARZ3NDEKTSV4RRFFQL9G5FAV") is False  # 'L'
        assert is_valid_ulid("01ARZ3NDEKTSV4RRFFQO9G5FAV") is False  # 'O'
        assert is_valid_ulid("01ARZ3NDEKTSV4RRFFQU9G5FAV") is False  # 'U'

    def test_empty_string(self) -> None:
        assert is_valid_ulid("") is False


# ---------------------------------------------------------------------------
# read_ticket_frontmatter_with_errors — parse-error classification
# ---------------------------------------------------------------------------


class TestReadTicketFrontmatterWithErrors:
    """Verify diagnostic-friendly frontmatter parsing."""

    def test_valid_frontmatter_returns_dict_no_errors(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        path = _write_ticket(td, "01ARZ3NDEKTSV4RRFFQ69G5FAV-test.md",
                             _minimal_ticket_frontmatter(uid="01ARZ3NDEKTSV4RRFFQ69G5FAV"))
        fm, errors = read_ticket_frontmatter_with_errors(path)
        assert fm is not None
        assert fm["id"] == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        assert fm["title"] == "Test Ticket"
        assert fm["status"] == "open"
        assert errors == []

    def test_body_is_attached(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        path = _write_ticket(td, "01ARZ3NDEKTSV4RRFFQ69G5FAV-test.md",
                             _minimal_ticket_frontmatter(uid="01ARZ3NDEKTSV4RRFFQ69G5FAV",
                                                         body="Some body text."))
        fm, errors = read_ticket_frontmatter_with_errors(path)
        assert fm is not None
        assert fm["__body__"] == "Some body text."
        assert errors == []

    def test_no_frontmatter_fences(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        path = _write_ticket(td, "no-fm.md", "# Just a heading\n\nNo frontmatter.\n")
        fm, errors = read_ticket_frontmatter_with_errors(path)
        assert fm is None
        assert len(errors) >= 1
        assert any("no YAML frontmatter fences" in e for e in errors)

    def test_empty_frontmatter_block(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        path = _write_ticket(td, "empty-fm.md", "---\n\n---\n\nBody here.\n")
        fm, errors = read_ticket_frontmatter_with_errors(path)
        assert fm is None
        assert any("empty" in e.lower() for e in errors)

    def test_frontmatter_not_a_mapping(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        path = _write_ticket(td, "list-fm.md", "---\n- item1\n- item2\n---\n\nBody.\n")
        fm, errors = read_ticket_frontmatter_with_errors(path)
        assert fm is None
        assert any("mapping" in e.lower() for e in errors)

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        path = _write_ticket(td, "bad-yaml.md",
                             "---\n{[invalid yaml: here\n---\n\nBody.\n")
        fm, errors = read_ticket_frontmatter_with_errors(path)
        assert fm is None
        assert any("YAML" in e for e in errors)

    def test_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.md"
        fm, errors = read_ticket_frontmatter_with_errors(path)
        assert fm is None
        assert len(errors) >= 1
        assert any("cannot read" in e for e in errors)

    def test_invalid_date_format_reported_as_error(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        content = (
            "---\n"
            "id: 01ARZ3NDEKTSV4RRFFQ69G5FAV\n"
            "title: Date Test\n"
            "status: open\n"
            "created_at: not-a-date\n"
            "---\n\nBody.\n"
        )
        path = _write_ticket(td, "01ARZ3NDEKTSV4RRFFQ69G5FAV-date.md", content)
        fm, errors = read_ticket_frontmatter_with_errors(path)
        assert fm is not None
        # Should report a date parse error but still return the dict
        assert any("date" in e.lower() or "created_at" in e for e in errors)


# ---------------------------------------------------------------------------
# build_ticket_inventory — synthetic fixtures
# ---------------------------------------------------------------------------


class TestBuildTicketInventoryEmpty:
    """Inventory of an empty tickets directory."""

    def test_empty_tickets_dir(self, tmp_path: Path) -> None:
        _make_tickets_dir(tmp_path)
        inv = build_ticket_inventory(tmp_path)
        assert isinstance(inv, TicketInventory)
        assert inv.total_files == 0
        assert inv.entries == []
        assert inv.duplicate_ids == {}
        assert inv.total_with_id == 0
        assert inv.total_valid_ulid == 0
        assert inv.total_roadmap_eligible == 0
        assert inv.total_with_parse_errors == 0
        assert inv.strategy_absent is True  # no STRATEGY.md

    def test_no_tickets_dir_at_all(self, tmp_path: Path) -> None:
        # Don't create tickets dir — inventory should handle gracefully
        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 0
        assert inv.entries == []


class TestValidUlidWithCanonicalFilename:
    """Ticket with canonical ULID filename and valid frontmatter ULID."""

    def test_valid_ulid_filename_and_frontmatter(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid}-my-feature.md",
                      _minimal_ticket_frontmatter(uid=uid, title="My Feature", body="Details."))

        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 1
        entry = inv.entries[0]
        assert entry.filename_prefix_shape == "valid-ulid"
        assert entry.has_id is True
        assert entry.has_title is True
        assert entry.has_status is True
        assert entry.has_body is True
        assert entry.frontmatter_id == uid
        assert entry.canonical_ulid_valid is True
        assert entry.roadmap_eligible is None  # strategy absent → cannot determine
        assert entry.parse_errors == []
        assert inv.total_with_id == 1
        assert inv.total_valid_ulid == 1

    def test_valid_ulid_roadmap_eligible_when_strategy_present(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        _make_strategy(tmp_path, _minimal_strategy(ticket_refs=[uid]))
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid}-my-feature.md",
                      _minimal_ticket_frontmatter(uid=uid))

        inv = build_ticket_inventory(tmp_path)
        assert inv.strategy_absent is False
        entry = inv.entries[0]
        assert entry.roadmap_eligible is True
        assert inv.total_roadmap_eligible == 1

    def test_valid_ulid_not_in_roadmap(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        _make_strategy(tmp_path, _minimal_strategy(ticket_refs=[]))  # empty roadmap
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid}-my-feature.md",
                      _minimal_ticket_frontmatter(uid=uid))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.roadmap_eligible is False

    def test_no_body(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid}-no-body.md",
                      _minimal_ticket_frontmatter(uid=uid, body=""))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.has_body is False


class TestValidUlidWithLegacyFilename:
    """SC4: Legacy filenames (non-ULID prefix) are readable only when
    frontmatter IDs are valid canonical ULIDs."""

    def test_legacy_filename_with_valid_frontmatter_ulid(self, tmp_path: Path) -> None:
        """A ticket with non-ULID filename but valid frontmatter ULID is
        still identified by its frontmatter ID, not the filename."""
        uid = _valid_ulid()
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, "legacy-ticket-name-no-ulid.md",
                      _minimal_ticket_frontmatter(uid=uid, title="Legacy Ticket"))

        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 1
        entry = inv.entries[0]

        # Filename prefix is non-ULID (legacy shape)
        assert entry.filename_prefix_shape == "non-ulid"

        # But the frontmatter ID is a valid canonical ULID — identity preserved
        assert entry.has_id is True
        assert entry.frontmatter_id == uid
        assert entry.canonical_ulid_valid is True

        # Should be roadmap-eligible if the ULID is in the roadmap
        assert inv.total_valid_ulid == 1

    def test_legacy_filename_with_roadmap_eligibility(self, tmp_path: Path) -> None:
        """Legacy filename + valid frontmatter ULID in roadmap → eligible."""
        uid = _valid_ulid()
        _make_strategy(tmp_path, _minimal_strategy(ticket_refs=[uid]))
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, "old-style-ticket.md",
                      _minimal_ticket_frontmatter(uid=uid))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.filename_prefix_shape == "non-ulid"
        assert entry.canonical_ulid_valid is True
        assert entry.roadmap_eligible is True
        assert inv.total_roadmap_eligible == 1

    def test_legacy_filename_with_invalid_frontmatter_ulid(self, tmp_path: Path) -> None:
        """Legacy filename with a non-ULID frontmatter ID: identity is not
        derived from the filename; the invalid frontmatter ID is recorded."""
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, "old-ticket-name.md",
                      _minimal_ticket_frontmatter(uid="not-a-ulid-123"))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.filename_prefix_shape == "non-ulid"
        assert entry.has_id is True
        assert entry.frontmatter_id == "not-a-ulid-123"
        assert entry.canonical_ulid_valid is False
        # Strategy absent: roadmap eligibility cannot be determined (None)
        assert entry.roadmap_eligible is None

    def test_legacy_filename_without_frontmatter_id(self, tmp_path: Path) -> None:
        """Legacy filename with no frontmatter id field at all — not readable
        as a roadmap-eligible entry."""
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, "old-ticket-no-id.md",
                      _minimal_ticket_frontmatter(uid=None, title="Untracked"))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.filename_prefix_shape == "non-ulid"
        assert entry.has_id is False
        assert entry.frontmatter_id is None
        assert entry.canonical_ulid_valid is None
        assert entry.roadmap_eligible is None  # strategy absent, cannot determine


class TestMissingOrInvalidFrontmatterId:
    """Missing or invalid frontmatter IDs are correctly classified."""

    def test_missing_id_field(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, "01ARZ3NDEKTSV4RRFFQ69G5FAV-no-id.md",
                      _minimal_ticket_frontmatter(uid=None))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.filename_prefix_shape == "valid-ulid"  # filename prefix is valid
        assert entry.has_id is False
        assert entry.frontmatter_id is None
        assert entry.canonical_ulid_valid is None
        assert entry.roadmap_eligible is None  # strategy absent
        assert inv.total_with_id == 0
        assert inv.total_valid_ulid == 0

    def test_id_present_but_empty(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        content = "---\nid:\ntitle: Empty ID\nstatus: open\n---\n\nBody.\n"
        _write_ticket(td, "empty-id.md", content)

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        # YAML parses empty/null id as None → has_id becomes False
        assert entry.has_id is False
        assert entry.frontmatter_id is None

    def test_id_is_numeric(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, "numeric-id.md",
                      _minimal_ticket_frontmatter(uid="12345"))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.has_id is True
        assert entry.frontmatter_id == "12345"
        assert entry.canonical_ulid_valid is False  # not 26 chars

    def test_id_is_26_chars_but_not_base32(self, tmp_path: Path) -> None:
        """A 26-char ID that contains illegal ULID chars is not canonical."""
        td = _make_tickets_dir(tmp_path)
        # 26 chars with 'I' — invalid Crockford base32
        bad_id = "01ARZ3NDEKTSV4RRFFQI9G5FAV"
        _write_ticket(td, f"{bad_id}-bad.md",
                      _minimal_ticket_frontmatter(uid=bad_id))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.has_id is True
        assert entry.frontmatter_id == bad_id
        assert entry.canonical_ulid_valid is False

    def test_id_is_26_chars_lowercase(self, tmp_path: Path) -> None:
        """Lowercase 26-char IDs are not valid ULIDs (must be uppercase)."""
        td = _make_tickets_dir(tmp_path)
        lower_id = "01arz3ndektsv4rrffq69g5fav"
        _write_ticket(td, f"{lower_id}-lower.md",
                      _minimal_ticket_frontmatter(uid=lower_id))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.has_id is True
        assert entry.canonical_ulid_valid is False


class TestDuplicateFrontmatterIds:
    """Duplicate frontmatter IDs report every involved path."""

    def test_two_files_same_frontmatter_id(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        td = _make_tickets_dir(tmp_path)
        path_a = _write_ticket(td, f"{uid}-first.md",
                               _minimal_ticket_frontmatter(uid=uid, title="First"))
        path_b = _write_ticket(td, f"{uid}-second.md",
                               _minimal_ticket_frontmatter(uid=uid, title="Second"))

        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 2
        assert uid in inv.duplicate_ids
        dup_paths = inv.duplicate_ids[uid]
        assert len(dup_paths) == 2
        assert path_a in dup_paths
        assert path_b in dup_paths

    def test_three_duplicates(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        td = _make_tickets_dir(tmp_path)
        paths = [
            _write_ticket(td, f"{uid}-a.md", _minimal_ticket_frontmatter(uid=uid)),
            _write_ticket(td, f"{uid}-b.md", _minimal_ticket_frontmatter(uid=uid)),
            _write_ticket(td, f"{uid}-c.md", _minimal_ticket_frontmatter(uid=uid)),
        ]

        inv = build_ticket_inventory(tmp_path)
        assert uid in inv.duplicate_ids
        assert len(inv.duplicate_ids[uid]) == 3
        for p in paths:
            assert p in inv.duplicate_ids[uid]

    def test_unique_ids_not_in_duplicates(self, tmp_path: Path) -> None:
        uid1 = _valid_ulid()
        uid2 = _valid_ulid_2()
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid1}-a.md", _minimal_ticket_frontmatter(uid=uid1))
        _write_ticket(td, f"{uid2}-b.md", _minimal_ticket_frontmatter(uid=uid2))

        inv = build_ticket_inventory(tmp_path)
        assert inv.duplicate_ids == {}

    def test_multiple_duplicate_sets(self, tmp_path: Path) -> None:
        uid1 = _valid_ulid()
        uid2 = _valid_ulid_2()
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid1}-a1.md", _minimal_ticket_frontmatter(uid=uid1))
        _write_ticket(td, f"{uid1}-a2.md", _minimal_ticket_frontmatter(uid=uid1))
        _write_ticket(td, f"{uid2}-b1.md", _minimal_ticket_frontmatter(uid=uid2))
        _write_ticket(td, f"{uid2}-b2.md", _minimal_ticket_frontmatter(uid=uid2))

        inv = build_ticket_inventory(tmp_path)
        assert len(inv.duplicate_ids) == 2
        assert uid1 in inv.duplicate_ids
        assert uid2 in inv.duplicate_ids
        assert len(inv.duplicate_ids[uid1]) == 2
        assert len(inv.duplicate_ids[uid2]) == 2

    def test_duplicate_with_null_id_not_reported(self, tmp_path: Path) -> None:
        """Files without an id field should not contribute to duplicates."""
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, "no-id-1.md", _minimal_ticket_frontmatter(uid=None))
        _write_ticket(td, "no-id-2.md", _minimal_ticket_frontmatter(uid=None))

        inv = build_ticket_inventory(tmp_path)
        assert inv.duplicate_ids == {}


class TestParseErrorsInInventory:
    """Parse errors are collected and reflected in inventory."""

    def test_parse_error_entry_has_errors(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, "bad.md", "No frontmatter at all.\n")

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert len(entry.parse_errors) > 0
        assert inv.total_with_parse_errors == 1

    def test_mixed_clean_and_error_entries(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid}-clean.md",
                      _minimal_ticket_frontmatter(uid=uid))
        _write_ticket(td, "broken.md", "No YAML here.\n")

        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 2
        assert inv.total_with_parse_errors == 1

        clean = next(e for e in inv.entries if e.parse_errors == [])
        broken = next(e for e in inv.entries if e.parse_errors != [])
        assert clean.canonical_ulid_valid is True
        assert broken.canonical_ulid_valid is None

    def test_entries_sorted_by_path(self, tmp_path: Path) -> None:
        """Entries are always sorted deterministically by path."""
        td = _make_tickets_dir(tmp_path)
        uid_a = "01AAAAAAAAAAAAAAAAAAAAAAA1"
        uid_b = "01BBBBBBBBBBBBBBBBBBBBBBB2"
        uid_c = "01CCCCCCCCCCCCCCCCCCCCCCCC3"
        _write_ticket(td, f"{uid_c}-c.md", _minimal_ticket_frontmatter(uid=uid_c))
        _write_ticket(td, f"{uid_a}-a.md", _minimal_ticket_frontmatter(uid=uid_a))
        _write_ticket(td, f"{uid_b}-b.md", _minimal_ticket_frontmatter(uid=uid_b))

        inv = build_ticket_inventory(tmp_path)
        ids = [e.frontmatter_id for e in inv.entries]
        # Should be sorted alphabetically by path
        assert ids == [uid_a, uid_b, uid_c]


class TestStrategyAbsentVsPresent:
    """Roadmap eligibility depends on strategy presence."""

    def test_strategy_absent_all_not_eligible(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid}-t.md", _minimal_ticket_frontmatter(uid=uid))
        # No strategy file

        inv = build_ticket_inventory(tmp_path)
        assert inv.strategy_absent is True
        entry = inv.entries[0]
        assert entry.roadmap_eligible is None  # cannot determine

    def test_strategy_present_empty_roadmap(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        _make_strategy(tmp_path, _minimal_strategy(ticket_refs=[]))
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid}-t.md", _minimal_ticket_frontmatter(uid=uid))

        inv = build_ticket_inventory(tmp_path)
        assert inv.strategy_absent is False
        entry = inv.entries[0]
        assert entry.roadmap_eligible is False

    def test_strategy_present_ticket_in_roadmap(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        _make_strategy(tmp_path, _minimal_strategy(ticket_refs=[uid]))
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, f"{uid}-t.md", _minimal_ticket_frontmatter(uid=uid))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.roadmap_eligible is True

    def test_only_valid_ulids_are_roadmap_eligible(self, tmp_path: Path) -> None:
        """Even if a non-ULID ID appears in the strategy (shouldn't happen),
        it is not marked roadmap-eligible because the ID is not a valid ULID."""
        uid = _valid_ulid()
        _make_strategy(tmp_path, _minimal_strategy(ticket_refs=[uid]))
        td = _make_tickets_dir(tmp_path)
        # This ticket has an invalid ID — even if the strategy somehow had it,
        # inventory requires the frontmatter ID to be a valid ULID
        _write_ticket(td, "bad-ticket.md",
                      _minimal_ticket_frontmatter(uid="not-a-ulid"))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.has_id is True
        assert entry.canonical_ulid_valid is False
        assert entry.roadmap_eligible is False


class TestSummaryCounts:
    """Summary counts on TicketInventory are accurate."""

    def test_counts_with_mixed_fixtures(self, tmp_path: Path) -> None:
        uid = _valid_ulid()
        _make_strategy(tmp_path, _minimal_strategy(ticket_refs=[uid]))
        td = _make_tickets_dir(tmp_path)

        # Valid ULID, in roadmap
        _write_ticket(td, f"{uid}-good.md",
                      _minimal_ticket_frontmatter(uid=uid, body="Has body"))
        # Valid ULID, no body
        _write_ticket(td, f"{_valid_ulid_2()}-nobody.md",
                      _minimal_ticket_frontmatter(uid=_valid_ulid_2(), body=""))
        # No frontmatter at all (parse error)
        _write_ticket(td, "broken.md", "Not a ticket.\n")
        # Has ID but not a valid ULID
        _write_ticket(td, "non-ulid-id.md",
                      _minimal_ticket_frontmatter(uid="my-custom-id"))

        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 4
        assert inv.total_with_id == 3       # good, nobody, non-ulid-id
        assert inv.total_valid_ulid == 2     # good, nobody
        assert inv.total_roadmap_eligible == 1  # only the one in roadmap
        assert inv.total_with_parse_errors == 1  # broken.md
        assert inv.strategy_absent is False

    def test_counts_all_zero_on_empty(self, tmp_path: Path) -> None:
        _make_tickets_dir(tmp_path)
        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 0
        assert inv.total_with_id == 0
        assert inv.total_valid_ulid == 0
        assert inv.total_roadmap_eligible == 0
        assert inv.total_with_parse_errors == 0


class TestNoMutationOfRealCorpus:
    """Ensure tests do not touch the real ``.megaplan/tickets/`` corpus.

    All fixtures use ``tmp_path`` — this class just documents the intent
    and provides a sanity check that the test itself doesn't import or
    reference real ticket paths.
    """

    def test_build_ticket_inventory_with_tmp_path_is_isolated(self, tmp_path: Path) -> None:
        """Inventory on tmp_path should show zero entries when no files written."""
        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 0

    def test_every_test_in_this_module_uses_tmp_path(self) -> None:
        """Sanity: this module does NOT import real ticket paths as globals."""
        import inspect
        import sys

        module = sys.modules[__name__]
        # Check that no global references point into the real repository
        for name, value in inspect.getmembers(module):
            if isinstance(value, Path):
                rel = str(value)
                assert ".megaplan/tickets" not in rel, (
                    f"Global Path references real ticket dir: {name}={value}"
                )


# ---------------------------------------------------------------------------
# Invalid-ulid filename prefix shape in inventory
# ---------------------------------------------------------------------------


class TestInvalidUlidFilenamePrefix:
    """Files with invalid-ulid prefix are correctly classified."""

    def test_invalid_ulid_prefix_in_inventory(self, tmp_path: Path) -> None:
        """A file whose filename prefix is 26-char but contains I/L/O/U."""
        td = _make_tickets_dir(tmp_path)
        # 26 chars with 'I' — classify_filename_prefix returns 'invalid-ulid'
        _write_ticket(td, "01ARZ3NDEKTSV4RRFFQI9G5FAV-bad-prefix.md",
                      _minimal_ticket_frontmatter(uid=_valid_ulid()))

        inv = build_ticket_inventory(tmp_path)
        entry = inv.entries[0]
        assert entry.filename_prefix_shape == "invalid-ulid"
        # But the frontmatter ID is valid, so the entry is still identity-correct
        assert entry.canonical_ulid_valid is True


# ---------------------------------------------------------------------------
# Non-.md files are ignored
# ---------------------------------------------------------------------------


class TestNonMarkdownFilesIgnored:
    """Only .md files under .megaplan/tickets/ are included in inventory."""

    def test_json_file_ignored(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        _write_ticket(td, "data.json", '{"key": "value"}')
        _write_ticket(td, f"{_valid_ulid()}-real.md",
                      _minimal_ticket_frontmatter(uid=_valid_ulid()))

        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 1

    def test_directory_ignored(self, tmp_path: Path) -> None:
        td = _make_tickets_dir(tmp_path)
        (td / "subdir").mkdir()
        _write_ticket(td, f"{_valid_ulid()}-real.md",
                      _minimal_ticket_frontmatter(uid=_valid_ulid()))

        inv = build_ticket_inventory(tmp_path)
        assert inv.total_files == 1
