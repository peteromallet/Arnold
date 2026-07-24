"""Validator and resolver tests for the v1 strategy document.

These tests prove that:

* ``validate_strategy`` catches format-level problems:
  - invalid ticket ULIDs, non-canonical epic refs, duplicates, unsupported types.
* ``resolve_strategy`` catches repository-level problems:
  - missing artifacts, stale display titles.
* Both tickets and epics are accepted independently in ``Now``, ``Next``, and
  ``Later`` when references are valid.
"""

from __future__ import annotations

import pathlib
import textwrap

import pytest

from arnold_pipelines.megaplan.strategy.contract import (
    RoadmapEntry,
    RoadmapHorizon,
    SourceLocation,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
)
from arnold_pipelines.megaplan.strategy.resolver import resolve_strategy
from arnold_pipelines.megaplan.strategy.validation import validate_strategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    item_type: str,
    ref: str,
    display_title: str,
    horizon: RoadmapHorizon,
    *,
    path: str = "test.md",
    line: int = 42,
) -> RoadmapEntry:
    """Factory for a bare :class:`RoadmapEntry` with a fixed source location."""
    return RoadmapEntry(
        identity=StrategyIdentity(type=item_type, ref=ref),  # type: ignore[arg-type]
        display_title=display_title,
        horizon=horizon,
        source_location=SourceLocation(path=path, line=line, column=1),
    )


def _make_doc(
    roadmap: dict[RoadmapHorizon, list[RoadmapEntry]] | None = None,
    *,
    diagnostics: list[StrategyDiagnostic] | None = None,
    schema_version: str = "megaplan-strategy-v1",
) -> StrategyDocument:
    """Factory for a minimal :class:`StrategyDocument`."""
    if roadmap is None:
        roadmap = {"Now": [], "Next": [], "Later": []}
    return StrategyDocument(
        schema_version=schema_version,
        stable_direction=[],
        roadmap=roadmap,
        diagnostics=diagnostics if diagnostics is not None else [],
    )


def _errors(doc: StrategyDocument) -> list[StrategyDiagnostic]:
    return [d for d in doc.diagnostics if d.level == "error"]


def _warnings(doc: StrategyDocument) -> list[StrategyDiagnostic]:
    return [d for d in doc.diagnostics if d.level == "warning"]


# A valid 26-character Crockford-base32 ULID (uppercase, no I/L/O/U).
_VALID_ULID = "01KT50AZRMK5X890TQ565DDB5V"


# ---------------------------------------------------------------------------
# Ticket ref (ULID) validation
# ---------------------------------------------------------------------------


class TestValidateTicketRefs:
    """``validate_strategy`` checks that ticket refs are well-formed ULIDs."""

    def test_valid_ulid_passes(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        assert _errors(result) == [], f"Unexpected errors: {_errors(result)}"

    def test_too_short_ref_is_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("ticket", "SHORT", "Fix auth", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        ref_errors = [e for e in _errors(result) if "Invalid ticket ref" in e.message]
        assert len(ref_errors) >= 1, f"Expected invalid-ticket-ref error, got: {_errors(result)}"

    def test_lowercase_ulid_is_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID.lower(), "Fix auth", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        ref_errors = [e for e in _errors(result) if "Invalid ticket ref" in e.message]
        assert len(ref_errors) >= 1

    def test_ulid_with_illegal_chars_is_error(self) -> None:
        """ULIDs must be Crockford base32 — no I, L, O, or U."""
        for bad_char in ("I", "L", "O", "U"):
            bad_ulid = _VALID_ULID[:25] + bad_char  # 26 chars, last one is illegal
            doc = _make_doc({
                "Now": [_make_entry("ticket", bad_ulid, "Fix auth", "Now")],
                "Next": [],
                "Later": [],
            })
            result = validate_strategy(doc)
            ref_errors = [e for e in _errors(result) if "Invalid ticket ref" in e.message]
            assert len(ref_errors) >= 1, (
                f"Expected error for ULID with '{bad_char}', got: {_errors(result)}"
            )

    def test_empty_ticket_ref_is_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("ticket", "", "Fix auth", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        ref_errors = [e for e in _errors(result)
                      if "Missing reference" in e.message or "empty" in e.message.lower()]
        assert len(ref_errors) >= 1

    def test_valid_ulid_has_source_location(self) -> None:
        """Invalid-ticket-ref diagnostics must carry a source location."""
        doc = _make_doc({
            "Now": [_make_entry("ticket", "bad", "Fix auth", "Now", path="s.md", line=12)],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        ref_errors = [e for e in _errors(result) if "Invalid ticket ref" in e.message]
        for diag in ref_errors:
            assert diag.source_location is not None
            assert diag.source_location.path == "s.md"
            assert diag.source_location.line == 12


# ---------------------------------------------------------------------------
# Epic ref (canonical slug) validation
# ---------------------------------------------------------------------------


class TestValidateEpicRefs:
    """``validate_strategy`` checks that epic refs are canonical initiative slugs."""

    def test_canonical_slug_passes(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("epic", "my-initiative", "My Initiative", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        assert _errors(result) == []

    def test_canonical_slug_with_dots_passes(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("epic", "v1.2.0", "Version 1.2.0", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        assert _errors(result) == []

    def test_uppercase_slug_is_noncanonical_error(self) -> None:
        # "My-Initiative" has uppercase — slugify_initiative lowercases it.
        doc = _make_doc({
            "Now": [_make_entry("epic", "My-Initiative", "My Initiative", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        epic_errors = [e for e in _errors(result)
                       if "epic ref" in e.message.lower() or "canonical" in e.message.lower()]
        assert len(epic_errors) >= 1, f"Expected non-canonical error, got: {_errors(result)}"

    def test_spaces_in_slug_is_noncanonical_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("epic", "my initiative", "My Initiative", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        epic_errors = [e for e in _errors(result)
                       if "epic ref" in e.message.lower() or "canonical" in e.message.lower()]
        assert len(epic_errors) >= 1

    def test_leading_hyphen_is_noncanonical_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("epic", "-leading", "Leading", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        epic_errors = [e for e in _errors(result)
                       if "epic ref" in e.message.lower() or "canonical" in e.message.lower()]
        assert len(epic_errors) >= 1

    def test_trailing_dot_is_noncanonical_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("epic", "trailing.", "Trailing", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        epic_errors = [e for e in _errors(result)
                       if "epic ref" in e.message.lower() or "canonical" in e.message.lower()]
        assert len(epic_errors) >= 1

    def test_noncanonical_epic_ref_has_source_location(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("epic", "Bad Slug", "Bad", "Now", path="e.md", line=77)],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        epic_errors = [e for e in _errors(result)
                       if "epic ref" in e.message.lower() or "canonical" in e.message.lower()]
        for diag in epic_errors:
            assert diag.source_location is not None
            assert diag.source_location.path == "e.md"
            assert diag.source_location.line == 77

    def test_empty_epic_ref_is_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("epic", "", "Missing ref", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        ref_errors = [e for e in _errors(result)
                      if "Missing reference" in e.message or "empty" in e.message.lower()]
        assert len(ref_errors) >= 1


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


class TestValidateDuplicates:
    """``validate_strategy`` rejects duplicate ``(type, ref)`` pairs across horizons."""

    def test_duplicate_across_horizons_is_error(self) -> None:
        entry = _make_entry("ticket", _VALID_ULID, "Fix auth", "Now")
        doc = _make_doc({
            "Now": [entry],
            "Next": [_make_entry("ticket", _VALID_ULID, "Fix auth", "Next")],
            "Later": [],
        })
        result = validate_strategy(doc)
        dup_errors = [e for e in _errors(result) if "Duplicate" in e.message]
        assert len(dup_errors) >= 1, f"Expected duplicate error, got: {_errors(result)}"

    def test_duplicate_within_same_horizon_is_error(self) -> None:
        """Even within the same horizon, duplicates are rejected."""
        doc = _make_doc({
            "Now": [
                _make_entry("epic", "my-epic", "My Epic", "Now"),
                _make_entry("epic", "my-epic", "My Epic", "Now"),
            ],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        dup_errors = [e for e in _errors(result) if "Duplicate" in e.message]
        assert len(dup_errors) >= 1

    def test_same_ref_different_type_not_duplicate(self) -> None:
        """A ticket and epic can share the same ref string — identity is (type, ref)."""
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Ticket", "Now")],
            "Next": [_make_entry("epic", _VALID_ULID, "Epic", "Next")],
            "Later": [],
        })
        result = validate_strategy(doc)
        dup_errors = [e for e in _errors(result) if "Duplicate" in e.message]
        assert dup_errors == [], f"Different types should not be duplicates: {dup_errors}"

    def test_no_false_positive_for_unique_entries(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "A", "Now")],
            "Next": [_make_entry("ticket", "01KT50AZRMK5X890TQ565DDB5W", "B", "Next")],
            "Later": [_make_entry("epic", "my-epic", "C", "Later")],
        })
        result = validate_strategy(doc)
        dup_errors = [e for e in _errors(result) if "Duplicate" in e.message]
        assert dup_errors == []

    def test_duplicate_error_identifies_both_horizons(self) -> None:
        entry1 = _make_entry("ticket", _VALID_ULID, "Fix auth", "Now")
        entry2 = _make_entry("ticket", _VALID_ULID, "Fix auth", "Later")
        doc = _make_doc({
            "Now": [entry1],
            "Next": [],
            "Later": [entry2],
        })
        result = validate_strategy(doc)
        dup_errors = [e for e in _errors(result) if "Duplicate" in e.message]
        assert len(dup_errors) >= 1
        msg = dup_errors[0].message
        assert "Now" in msg and "Later" in msg, (
            f"Duplicate error should name both horizons: {msg}"
        )


# ---------------------------------------------------------------------------
# Unsupported item types
# ---------------------------------------------------------------------------


class TestValidateUnsupportedTypes:
    """``validate_strategy`` rejects item types other than ``ticket`` and ``epic``."""

    def test_story_type_is_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("story", "STORY-1", "A story", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        type_errors = [e for e in _errors(result) if "Unsupported item type" in e.message]
        assert len(type_errors) >= 1

    def test_task_type_is_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("task", "T-1", "A task", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        type_errors = [e for e in _errors(result) if "Unsupported item type" in e.message]
        assert len(type_errors) >= 1

    def test_bug_type_is_error(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("bug", "BUG-1", "A bug", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        type_errors = [e for e in _errors(result) if "Unsupported item type" in e.message]
        assert len(type_errors) >= 1

    def test_unsupported_type_has_source_location(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("feature", "F-1", "Feature", "Now", path="f.md", line=99)],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        type_errors = [e for e in _errors(result) if "Unsupported item type" in e.message]
        for diag in type_errors:
            assert diag.source_location is not None
            assert diag.source_location.path == "f.md"
            assert diag.source_location.line == 99


# ---------------------------------------------------------------------------
# Horizon and type independence
# ---------------------------------------------------------------------------


class TestHorizonTypeIndependence:
    """Both ``ticket`` and ``epic`` entries are accepted in any horizon."""

    _TICKET_ULID_1 = "01KT50AZRMK5X890TQ565DDB5V"
    _TICKET_ULID_2 = "01KT50AZRMK5X890TQ565DDB5W"
    _TICKET_ULID_3 = "01KT50AZRMK5X890TQ565DDB5X"

    def test_ticket_in_now_passes(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("ticket", self._TICKET_ULID_1, "Now ticket", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        assert _errors(result) == []

    def test_ticket_in_next_passes(self) -> None:
        doc = _make_doc({
            "Now": [],
            "Next": [_make_entry("ticket", self._TICKET_ULID_1, "Next ticket", "Next")],
            "Later": [],
        })
        result = validate_strategy(doc)
        assert _errors(result) == []

    def test_ticket_in_later_passes(self) -> None:
        doc = _make_doc({
            "Now": [],
            "Next": [],
            "Later": [_make_entry("ticket", self._TICKET_ULID_1, "Later ticket", "Later")],
        })
        result = validate_strategy(doc)
        assert _errors(result) == []

    def test_epic_in_now_passes(self) -> None:
        doc = _make_doc({
            "Now": [_make_entry("epic", "now-epic", "Now epic", "Now")],
            "Next": [],
            "Later": [],
        })
        result = validate_strategy(doc)
        assert _errors(result) == []

    def test_epic_in_next_passes(self) -> None:
        doc = _make_doc({
            "Now": [],
            "Next": [_make_entry("epic", "next-epic", "Next epic", "Next")],
            "Later": [],
        })
        result = validate_strategy(doc)
        assert _errors(result) == []

    def test_epic_in_later_passes(self) -> None:
        doc = _make_doc({
            "Now": [],
            "Next": [],
            "Later": [_make_entry("epic", "later-epic", "Later epic", "Later")],
        })
        result = validate_strategy(doc)
        assert _errors(result) == []

    def test_tickets_and_epics_interleaved_across_horizons(self) -> None:
        """All three horizons can contain a mix of tickets and epics."""
        doc = _make_doc({
            "Now": [
                _make_entry("ticket", self._TICKET_ULID_1, "Now ticket", "Now"),
                _make_entry("epic", "now-epic", "Now epic", "Now"),
            ],
            "Next": [
                _make_entry("ticket", self._TICKET_ULID_2, "Next ticket", "Next"),
                _make_entry("epic", "next-epic", "Next epic", "Next"),
            ],
            "Later": [
                _make_entry("ticket", self._TICKET_ULID_3, "Later ticket", "Later"),
                _make_entry("epic", "later-epic", "Later epic", "Later"),
            ],
        })
        result = validate_strategy(doc)
        assert _errors(result) == [], f"Unexpected errors: {_errors(result)}"


# ---------------------------------------------------------------------------
# Resolver: missing references
# ---------------------------------------------------------------------------


class TestResolveMissingReferences:
    """``resolve_strategy`` emits hard errors for artifacts that don't exist."""

    def test_missing_ticket_is_error(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)  # creates .megaplan/tickets/ with no ticket files
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        missing = [e for e in _errors(result) if "Missing ticket reference" in e.message]
        assert len(missing) >= 1, f"Expected missing-ticket error, got: {_errors(result)}"

    def test_missing_epic_is_error(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        doc = _make_doc({
            "Now": [_make_entry("epic", "nonexistent-epic", "Nope", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        missing = [e for e in _errors(result) if "Missing epic reference" in e.message]
        assert len(missing) >= 1, f"Expected missing-epic error, got: {_errors(result)}"

    def test_missing_ref_has_source_location(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth", "Now", path="s.md", line=55)],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        missing = [e for e in _errors(result) if "Missing ticket reference" in e.message]
        for diag in missing:
            assert diag.source_location is not None
            assert diag.source_location.path == "s.md"
            assert diag.source_location.line == 55

    def test_existing_ticket_no_missing_error(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout", "Fix auth timeout")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        missing = [e for e in _errors(result) if "Missing ticket reference" in e.message]
        assert missing == [], f"Ticket exists, should not be missing: {missing}"

    def test_existing_epic_no_missing_error(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [_make_entry("epic", "my-epic", "My Epic", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        missing = [e for e in _errors(result) if "Missing epic reference" in e.message]
        assert missing == [], f"Epic exists, should not be missing: {missing}"


# ---------------------------------------------------------------------------
# Resolver: stale display titles
# ---------------------------------------------------------------------------


class TestResolveStaleTitles:
    """``resolve_strategy`` emits warnings when display titles are out of date."""

    def test_stale_ticket_title_is_warning(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout", "Fix auth timeout")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Old title", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        stale = [w for w in _warnings(result) if "Stale display title" in w.message]
        assert len(stale) >= 1, f"Expected stale-title warning, got: {_warnings(result)}"

    def test_matching_ticket_title_no_warning(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout", "Fix auth timeout")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        stale = [w for w in _warnings(result) if "Stale display title" in w.message]
        assert stale == [], f"Matching title should not warn: {stale}"

    def test_stale_epic_title_is_warning(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [_make_entry("epic", "my-epic", "Old Epic Title", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        stale = [w for w in _warnings(result) if "Stale display title" in w.message]
        assert len(stale) >= 1, f"Expected stale-title warning, got: {_warnings(result)}"

    def test_matching_epic_title_no_warning(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [_make_entry("epic", "my-epic", "My Epic", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        stale = [w for w in _warnings(result) if "Stale display title" in w.message]
        assert stale == [], f"Matching title should not warn: {stale}"

    def test_stale_title_warning_has_source_location(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout", "Fix auth timeout")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Old title", "Now", path="s.md", line=33)],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        stale = [w for w in _warnings(result) if "Stale display title" in w.message]
        for diag in stale:
            assert diag.source_location is not None
            assert diag.source_location.path == "s.md"
            assert diag.source_location.line == 33

    def test_epic_without_readme_no_title_warning(self, tmp_path: pathlib.Path) -> None:
        """If an initiative dir exists but has no README.md, no stale-title warning."""
        _prepare_repo(tmp_path)
        initiatives_dir = tmp_path / ".megaplan" / "initiatives" / "bare-epic"
        initiatives_dir.mkdir(parents=True, exist_ok=True)
        doc = _make_doc({
            "Now": [_make_entry("epic", "bare-epic", "Some Title", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        # Should NOT be a missing error (directory exists), and
        # should NOT be a stale-title warning (no title to compare).
        missing = [e for e in _errors(result) if "Missing epic reference" in e.message]
        stale = [w for w in _warnings(result) if "Stale display title" in w.message]
        assert missing == [], f"Epic dir exists, should not be missing: {missing}"
        assert stale == [], f"No README, no title to compare: {stale}"


# ---------------------------------------------------------------------------
# Resolver: valid resolution
# ---------------------------------------------------------------------------


class TestResolveValidResolution:
    """Full resolution with valid artifacts should produce zero new diagnostics."""

    def test_valid_ticket_resolution_no_errors(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout", "Fix auth timeout")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        assert _errors(result) == [], f"Unexpected errors: {_errors(result)}"
        assert _warnings(result) == [], f"Unexpected warnings: {_warnings(result)}"

    def test_valid_epic_resolution_no_errors(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [_make_entry("epic", "my-epic", "My Epic", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        assert _errors(result) == [], f"Unexpected errors: {_errors(result)}"
        assert _warnings(result) == [], f"Unexpected warnings: {_warnings(result)}"

    def test_mixed_ticket_and_epic_resolution(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout", "Fix auth timeout")
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [
                _make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now"),
                _make_entry("epic", "my-epic", "My Epic", "Now"),
            ],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        assert _errors(result) == [], f"Unexpected errors: {_errors(result)}"
        assert _warnings(result) == [], f"Unexpected warnings: {_warnings(result)}"

    def test_mixed_with_stale_titles(self, tmp_path: pathlib.Path) -> None:
        """Stale titles produce warnings and do not block resolution."""
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout", "Fix auth timeout")
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [
                _make_entry("ticket", _VALID_ULID, "Old ticket title", "Now"),
                _make_entry("epic", "my-epic", "Old epic title", "Now"),
            ],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        # Stale titles are warnings, not errors.
        assert _errors(result) == [], f"Stale titles should not be errors: {_errors(result)}"
        stale = [w for w in _warnings(result) if "Stale display title" in w.message]
        assert len(stale) == 2, f"Expected 2 stale-title warnings, got: {stale}"


# ---------------------------------------------------------------------------
# Resolver: lifecycle diagnostics — ticket status
# ---------------------------------------------------------------------------


class TestResolveTicketLifecycle:
    """``resolve_strategy`` emits warnings for dismissed/addressed tickets
    and promoted/superseded tickets."""

    def test_dismissed_ticket_is_warning(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout",
                       "Fix auth timeout", status="dismissed")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        dismissed = [w for w in _warnings(result)
                     if "Dismissed ticket" in w.message]
        assert len(dismissed) >= 1, (
            f"Expected 'Dismissed ticket' warning, got: {_warnings(result)}"
        )

    def test_addressed_ticket_is_warning(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout",
                       "Fix auth timeout", status="addressed")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        addressed = [w for w in _warnings(result)
                     if "Addressed ticket" in w.message]
        assert len(addressed) >= 1, (
            f"Expected 'Addressed ticket' warning, got: {_warnings(result)}"
        )

    def test_open_ticket_no_lifecycle_warning(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout",
                       "Fix auth timeout", status="open")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        lifecycle = [w for w in _warnings(result)
                     if "dismissed" in w.message.lower()
                     or "addressed" in w.message.lower()
                     or "superseded" in w.message.lower()]
        assert lifecycle == [], (
            f"Open ticket should not get lifecycle warnings: {lifecycle}"
        )

    def test_superseded_ticket_is_warning(self, tmp_path: pathlib.Path) -> None:
        """A ticket with a promoted_to_epic link should get a superseded warning."""
        _prepare_repo(tmp_path)
        _write_ticket_with_epics(
            tmp_path, _VALID_ULID, "fix-auth-timeout",
            "Fix auth timeout", status="open",
            epics=[{"epic_id": "my-epic", "resolves_on_complete": True,
                    "kind": "promoted_to_epic", "provenance": "promotion:test"}],
        )
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        superseded = [w for w in _warnings(result)
                      if "Superseded ticket" in w.message]
        assert len(superseded) >= 1, (
            f"Expected 'Superseded ticket' warning, got: {_warnings(result)}"
        )

    def test_ticket_with_associated_link_no_superseded_warning(
        self, tmp_path: pathlib.Path,
    ) -> None:
        """A ticket with only an 'associated' link should not get superseded."""
        _prepare_repo(tmp_path)
        _write_ticket_with_epics(
            tmp_path, _VALID_ULID, "fix-auth-timeout",
            "Fix auth timeout", status="open",
            epics=[{"epic_id": "my-epic", "resolves_on_complete": False,
                    "kind": "associated"}],
        )
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        superseded = [w for w in _warnings(result)
                      if "Superseded ticket" in w.message]
        assert superseded == [], (
            f"Associated ticket should not be superseded: {superseded}"
        )

    def test_dismissed_ticket_warning_has_source_location(
        self, tmp_path: pathlib.Path,
    ) -> None:
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout",
                       "Fix auth timeout", status="dismissed")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout",
                                "Now", path="s.md", line=55)],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        dismissed = [w for w in _warnings(result)
                     if "Dismissed ticket" in w.message]
        for diag in dismissed:
            assert diag.source_location is not None
            assert diag.source_location.path == "s.md"
            assert diag.source_location.line == 55


# ---------------------------------------------------------------------------
# Resolver: lifecycle diagnostics — epic completion
# ---------------------------------------------------------------------------


class TestResolveEpicLifecycle:
    """``resolve_strategy`` emits warnings for completed/archived epics."""

    def test_completed_epic_is_warning(self, tmp_path: pathlib.Path) -> None:
        _prepare_repo(tmp_path)
        _write_initiative_with_state(tmp_path, "my-epic", "My Epic", "archived")
        doc = _make_doc({
            "Now": [_make_entry("epic", "my-epic", "My Epic", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        completed = [w for w in _warnings(result)
                     if "Completed epic" in w.message]
        assert len(completed) >= 1, (
            f"Expected 'Completed epic' warning, got: {_warnings(result)}"
        )

    def test_non_archived_epic_no_lifecycle_warning(
        self, tmp_path: pathlib.Path,
    ) -> None:
        _prepare_repo(tmp_path)
        _write_initiative_with_state(tmp_path, "my-epic", "My Epic", "sprinting")
        doc = _make_doc({
            "Now": [_make_entry("epic", "my-epic", "My Epic", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        completed = [w for w in _warnings(result)
                     if "Completed epic" in w.message]
        assert completed == [], (
            f"Active epic should not get completed warning: {completed}"
        )

    def test_completed_epic_via_filesystem_marker(
        self, tmp_path: pathlib.Path,
    ) -> None:
        """An epic with a COMPLETED marker file should warn."""
        _prepare_repo(tmp_path)
        init_dir = tmp_path / ".megaplan" / "initiatives" / "done-epic"
        init_dir.mkdir(parents=True, exist_ok=True)
        (init_dir / "README.md").write_text("# Done Epic\n\nDesc.\n", encoding="utf-8")
        (init_dir / "COMPLETED.md").write_text("done\n", encoding="utf-8")
        doc = _make_doc({
            "Now": [_make_entry("epic", "done-epic", "Done Epic", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        completed = [w for w in _warnings(result)
                     if "Completed epic" in w.message]
        assert len(completed) >= 1, (
            f"Expected 'Completed epic' from filesystem marker, got: {_warnings(result)}"
        )

    def test_completed_epic_warning_has_source_location(
        self, tmp_path: pathlib.Path,
    ) -> None:
        _prepare_repo(tmp_path)
        _write_initiative_with_state(tmp_path, "my-epic", "My Epic", "archived")
        doc = _make_doc({
            "Now": [_make_entry("epic", "my-epic", "My Epic",
                                "Now", path="e.md", line=77)],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        completed = [w for w in _warnings(result)
                     if "Completed epic" in w.message]
        for diag in completed:
            assert diag.source_location is not None
            assert diag.source_location.path == "e.md"
            assert diag.source_location.line == 77


# ---------------------------------------------------------------------------
# Resolver: duplicate-intent (ticket + epic for same promoted work)
# ---------------------------------------------------------------------------


class TestResolveDuplicateIntent:
    """``resolve_strategy`` warns when both a ticket and its promoted epic
    appear in the roadmap."""

    def test_ticket_and_promoted_epic_both_in_roadmap_is_warning(
        self, tmp_path: pathlib.Path,
    ) -> None:
        _prepare_repo(tmp_path)
        _write_ticket_with_epics(
            tmp_path, _VALID_ULID, "fix-auth-timeout",
            "Fix auth timeout", status="open",
            epics=[{"epic_id": "my-epic", "resolves_on_complete": True,
                    "kind": "promoted_to_epic", "provenance": "promotion:test"}],
        )
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [
                _make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now"),
                _make_entry("epic", "my-epic", "My Epic", "Now"),
            ],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        dup_intent = [w for w in _warnings(result)
                      if "Duplicate intent" in w.message]
        assert len(dup_intent) >= 1, (
            f"Expected 'Duplicate intent' warning, got: {_warnings(result)}"
        )

    def test_ticket_without_promoted_epic_in_roadmap_no_warning(
        self, tmp_path: pathlib.Path,
    ) -> None:
        """Only the ticket is in roadmap; the epic is not — no duplicate intent."""
        _prepare_repo(tmp_path)
        _write_ticket_with_epics(
            tmp_path, _VALID_ULID, "fix-auth-timeout",
            "Fix auth timeout", status="open",
            epics=[{"epic_id": "my-epic", "resolves_on_complete": True,
                    "kind": "promoted_to_epic", "provenance": "promotion:test"}],
        )
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        dup_intent = [w for w in _warnings(result)
                      if "Duplicate intent" in w.message]
        assert dup_intent == [], (
            f"Epic not in roadmap, should not be duplicate intent: {dup_intent}"
        )

    def test_promoted_epic_without_ticket_no_duplicate_warning(
        self, tmp_path: pathlib.Path,
    ) -> None:
        """Only the epic is in roadmap; ticket not — no duplicate intent."""
        _prepare_repo(tmp_path)
        _write_ticket(tmp_path, _VALID_ULID, "fix-auth-timeout",
                       "Fix auth timeout", status="open")
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [_make_entry("epic", "my-epic", "My Epic", "Now")],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        dup_intent = [w for w in _warnings(result)
                      if "Duplicate intent" in w.message]
        assert dup_intent == [], (
            f"No promoted ticket in roadmap, should not be duplicate intent: {dup_intent}"
        )

    def test_duplicate_intent_names_both_horizons(
        self, tmp_path: pathlib.Path,
    ) -> None:
        """Duplicate-intent message should include both horizon names."""
        _prepare_repo(tmp_path)
        _write_ticket_with_epics(
            tmp_path, _VALID_ULID, "fix-auth-timeout",
            "Fix auth timeout", status="open",
            epics=[{"epic_id": "my-epic", "resolves_on_complete": True,
                    "kind": "promoted_to_epic", "provenance": "promotion:test"}],
        )
        _write_initiative(tmp_path, "my-epic", "My Epic")
        doc = _make_doc({
            "Now": [_make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now")],
            "Next": [_make_entry("epic", "my-epic", "My Epic", "Next")],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        dup_intent = [w for w in _warnings(result)
                      if "Duplicate intent" in w.message]
        assert len(dup_intent) >= 1
        msg = dup_intent[0].message
        assert "Now" in msg and "Next" in msg, (
            f"Duplicate intent should name both horizons: {msg}"
        )

    def test_multiple_promoted_epics_duplicate_detected(
        self, tmp_path: pathlib.Path,
    ) -> None:
        """A ticket promoted to multiple epics — duplicate intent for each."""
        _prepare_repo(tmp_path)
        _write_ticket_with_epics(
            tmp_path, _VALID_ULID, "fix-auth-timeout",
            "Fix auth timeout", status="open",
            epics=[
                {"epic_id": "epic-a", "resolves_on_complete": True,
                 "kind": "promoted_to_epic", "provenance": "p:a"},
                {"epic_id": "epic-b", "resolves_on_complete": True,
                 "kind": "promoted_to_epic", "provenance": "p:b"},
            ],
        )
        _write_initiative(tmp_path, "epic-a", "Epic A")
        _write_initiative(tmp_path, "epic-b", "Epic B")
        doc = _make_doc({
            "Now": [
                _make_entry("ticket", _VALID_ULID, "Fix auth timeout", "Now"),
                _make_entry("epic", "epic-a", "Epic A", "Now"),
                _make_entry("epic", "epic-b", "Epic B", "Now"),
            ],
            "Next": [],
            "Later": [],
        })
        result = resolve_strategy(doc, str(tmp_path))
        dup_intents = [w for w in _warnings(result)
                       if "Duplicate intent" in w.message]
        assert len(dup_intents) >= 2, (
            f"Expected 2 duplicate intent warnings for 2 promoted epics, "
            f"got {len(dup_intents)}: {dup_intents}"
        )


# ---------------------------------------------------------------------------
# Fixture helpers — set up minimal repo layout under tmp_path
# ---------------------------------------------------------------------------


def _prepare_repo(root: pathlib.Path) -> None:
    """Create the minimal ``.megaplan`` directory structure."""
    (root / ".megaplan" / "tickets").mkdir(parents=True, exist_ok=True)
    (root / ".megaplan" / "initiatives").mkdir(parents=True, exist_ok=True)


def _write_ticket(
    root: pathlib.Path,
    ulid: str,
    slug: str,
    title: str,
    *,
    status: str = "open",
) -> None:
    """Write a minimal ticket ``.md`` file with YAML frontmatter."""
    ticket_path = root / ".megaplan" / "tickets" / f"{ulid}-{slug}.md"
    content = textwrap.dedent(f"""\
    ---
    id: {ulid}
    title: {title}
    status: {status}
    ---

    # {title}

    Ticket body.
    """)
    ticket_path.write_text(content, encoding="utf-8")


def _write_ticket_with_epics(
    root: pathlib.Path,
    ulid: str,
    slug: str,
    title: str,
    *,
    status: str = "open",
    epics: list[dict] | None = None,
) -> None:
    """Write a ticket file with an ``epics`` list in the YAML frontmatter."""
    import yaml

    ticket_path = root / ".megaplan" / "tickets" / f"{ulid}-{slug}.md"
    fm = {
        "id": ulid,
        "title": title,
        "status": status,
    }
    if epics:
        fm["epics"] = epics
    content = f"---\n{yaml.dump(fm, allow_unicode=True, sort_keys=False)}---\n\n# {title}\n\nTicket body.\n"
    ticket_path.write_text(content, encoding="utf-8")


def _write_initiative(
    root: pathlib.Path,
    slug: str,
    title: str,
) -> None:
    """Write a minimal initiative directory with a README.md."""
    init_dir = root / ".megaplan" / "initiatives" / slug
    init_dir.mkdir(parents=True, exist_ok=True)
    readme = init_dir / "README.md"
    readme.write_text(f"# {title}\n\nInitiative description.\n", encoding="utf-8")


def _write_initiative_with_state(
    root: pathlib.Path,
    slug: str,
    title: str,
    state: str,
) -> None:
    """Write an initiative with a chain.yaml that declares its state."""
    import yaml

    init_dir = root / ".megaplan" / "initiatives" / slug
    init_dir.mkdir(parents=True, exist_ok=True)
    readme = init_dir / "README.md"
    readme.write_text(f"# {title}\n\nInitiative description.\n", encoding="utf-8")
    chain = init_dir / "chain.yaml"
    chain.write_text(
        yaml.dump({"state": state}, allow_unicode=True), encoding="utf-8"
    )
