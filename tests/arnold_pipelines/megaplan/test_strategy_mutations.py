"""Focused tests for strategy roadmap mutation helpers.

Covers add_roadmap_entry, remove_roadmap_entry, replace_roadmap_entry,
and promote_ticket_to_epic across the required scenarios:
- replace-in-same-horizon
- epic-already-present idempotency
- non-roadmap ticket no-op (no forced visibility)
- duplicate-intent detection
- deterministic serialization
"""

from __future__ import annotations

from arnold_pipelines.megaplan.strategy.contract import (
    RoadmapEntry,
    SourceLocation,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
    StrategySection,
)
from arnold_pipelines.megaplan.strategy.mutations import (
    _MUTATION_PATH,
    add_roadmap_entry,
    promote_ticket_to_epic,
    remove_roadmap_entry,
    replace_roadmap_entry,
)
from arnold_pipelines.megaplan.strategy.parser import (
    parse_strategy,
    serialize_strategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_document() -> StrategyDocument:
    """A minimal, clean parsed document with no entries and no diagnostics."""
    return StrategyDocument(
        schema_version="megaplan-strategy-v1",
        stable_direction=[
            StrategySection(
                title="Mission",
                body="Test mission.",
                source_location=SourceLocation(path="test.md", line=1, column=1),
            ),
            StrategySection(
                title="Principles",
                body="Test principles.",
                source_location=SourceLocation(path="test.md", line=2, column=1),
            ),
            StrategySection(
                title="Architecture Direction",
                body="Test arch.",
                source_location=SourceLocation(path="test.md", line=3, column=1),
            ),
            StrategySection(
                title="Constraints",
                body="Test constraints.",
                source_location=SourceLocation(path="test.md", line=4, column=1),
            ),
            StrategySection(
                title="Non-Goals",
                body="Test non-goals.",
                source_location=SourceLocation(path="test.md", line=5, column=1),
            ),
        ],
        roadmap={"Now": [], "Next": [], "Later": []},
        diagnostics=[],
    )


def _entry(
    type_: str,
    ref: str,
    title: str = "",
    horizon: str = "Now",
    path: str = "test.md",
) -> RoadmapEntry:
    """Create a RoadmapEntry with minimal boilerplate."""
    return RoadmapEntry(
        identity=StrategyIdentity(type=type_, ref=ref),  # type: ignore[arg-type]
        display_title=title or f"{type_}:{ref}",
        horizon=horizon,  # type: ignore[arg-type]
        source_location=SourceLocation(path=path, line=10, column=1),
    )


def _assert_unchanged(original: StrategyDocument, updated: StrategyDocument) -> None:
    """Assert that *updated* is structurally identical to *original*."""
    assert updated.schema_version == original.schema_version
    assert len(updated.stable_direction) == len(original.stable_direction)
    for s1, s2 in zip(original.stable_direction, updated.stable_direction):
        assert s2.title == s1.title
        assert s2.body == s1.body
    for h in ("Now", "Next", "Later"):
        assert [(e.identity.type, e.identity.ref) for e in updated.roadmap[h]] == [
            (e.identity.type, e.identity.ref) for e in original.roadmap[h]
        ]


# ---------------------------------------------------------------------------
# add_roadmap_entry
# ---------------------------------------------------------------------------


class TestAddRoadmapEntry:
    """Tests for add_roadmap_entry."""

    def test_adds_entry_to_empty_horizon(self) -> None:
        """Adding an entry to an empty horizon places it there."""
        doc = _empty_document()
        entry = _entry("ticket", "T-1")
        result = add_roadmap_entry(doc, entry, "Now")
        assert len(result.roadmap["Now"]) == 1
        assert result.roadmap["Now"][0].identity.ref == "T-1"
        assert result.roadmap["Now"][0].horizon == "Now"

    def test_adds_entry_to_non_empty_horizon(self) -> None:
        """Adding an entry to a horizon that already has entries appends it."""
        doc = _empty_document()
        e1 = _entry("ticket", "T-1")
        doc = add_roadmap_entry(doc, e1, "Now")
        e2 = _entry("ticket", "T-2")
        result = add_roadmap_entry(doc, e2, "Now")
        assert len(result.roadmap["Now"]) == 2
        refs = [e.identity.ref for e in result.roadmap["Now"]]
        assert refs == ["T-1", "T-2"]

    def test_idempotent_same_horizon(self) -> None:
        """Adding the same identity to the same horizon is idempotent — no duplicate."""
        doc = _empty_document()
        entry = _entry("epic", "my-epic")
        doc = add_roadmap_entry(doc, entry, "Now")
        result = add_roadmap_entry(doc, entry, "Now")
        assert len(result.roadmap["Now"]) == 1
        warnings = [d for d in result.diagnostics if d.level == "warning"]
        assert len(warnings) == 1
        assert "already exists in horizon" in warnings[0].message

    def test_idempotent_across_horizons(self) -> None:
        """Adding the same identity to a different horizon is idempotent — no duplicate allowed."""
        doc = _empty_document()
        entry = _entry("ticket", "T-3")
        doc = add_roadmap_entry(doc, entry, "Now")
        result = add_roadmap_entry(doc, entry, "Next")
        # Still only one entry, in Now
        assert len(result.roadmap["Now"]) == 1
        assert len(result.roadmap["Next"]) == 0
        warnings = [d for d in result.diagnostics if d.level == "warning"]
        assert len(warnings) == 1
        assert "already exists in horizon" in warnings[0].message
        assert "Now" in warnings[0].message
        assert "Next" in warnings[0].message

    def test_identity_type_matters(self) -> None:
        """Same ref but different type is a different identity — both allowed."""
        doc = _empty_document()
        ticket = _entry("ticket", "shared-ref")
        epic = _entry("epic", "shared-ref")
        doc = add_roadmap_entry(doc, ticket, "Now")
        result = add_roadmap_entry(doc, epic, "Next")
        assert len(result.roadmap["Now"]) == 1
        assert len(result.roadmap["Next"]) == 1
        assert result.roadmap["Now"][0].identity.type == "ticket"
        assert result.roadmap["Next"][0].identity.type == "epic"

    def test_original_document_immutable(self) -> None:
        """The original document is never mutated."""
        doc = _empty_document()
        entry = _entry("ticket", "T-immutable")
        _ = add_roadmap_entry(doc, entry, "Now")
        assert doc.roadmap["Now"] == []
        assert doc.roadmap["Next"] == []

    def test_diagnostics_appended_not_mutated(self) -> None:
        """Existing diagnostics are preserved; new ones are appended."""
        doc = StrategyDocument(
            schema_version="megaplan-strategy-v1",
            stable_direction=_empty_document().stable_direction,
            roadmap={"Now": [], "Next": [], "Later": []},
            diagnostics=[
                StrategyDiagnostic(
                    level="error",
                    message="pre-existing error",
                    source_location=SourceLocation(path="test.md", line=1, column=1),
                )
            ],
        )
        entry = _entry("ticket", "T-pre")
        doc2 = add_roadmap_entry(doc, entry, "Now")  # first add – succeeds
        result = add_roadmap_entry(doc2, entry, "Now")  # second add – idempotent
        assert len(result.diagnostics) == 2
        assert result.diagnostics[0].message == "pre-existing error"
        assert "already exists" in result.diagnostics[1].message


# ---------------------------------------------------------------------------
# remove_roadmap_entry
# ---------------------------------------------------------------------------


class TestRemoveRoadmapEntry:
    """Tests for remove_roadmap_entry."""

    def test_removes_existing_entry(self) -> None:
        """Removing an entry that exists removes it."""
        doc = _empty_document()
        entry = _entry("ticket", "T-rm")
        doc = add_roadmap_entry(doc, entry, "Now")
        assert len(doc.roadmap["Now"]) == 1

        ident = StrategyIdentity(type="ticket", ref="T-rm")
        result = remove_roadmap_entry(doc, ident)
        assert len(result.roadmap["Now"]) == 0

    def test_idempotent_when_not_found(self) -> None:
        """Removing a non-existent identity is a clean no-op."""
        doc = _empty_document()
        ident = StrategyIdentity(type="ticket", ref="nonexistent")
        result = remove_roadmap_entry(doc, ident)
        _assert_unchanged(doc, result)
        # No new diagnostics
        assert len(result.diagnostics) == len(doc.diagnostics)

    def test_removes_from_correct_horizon_only(self) -> None:
        """Removal only affects the horizon containing the identity."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-now"), "Now")
        doc = add_roadmap_entry(doc, _entry("ticket", "T-next"), "Next")
        ident = StrategyIdentity(type="ticket", ref="T-now")
        result = remove_roadmap_entry(doc, ident)
        assert len(result.roadmap["Now"]) == 0
        assert len(result.roadmap["Next"]) == 1
        assert result.roadmap["Next"][0].identity.ref == "T-next"

    def test_original_document_immutable(self) -> None:
        """The original document is never mutated by removal."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-imm"), "Now")
        _ = remove_roadmap_entry(doc, StrategyIdentity(type="ticket", ref="T-imm"))
        assert len(doc.roadmap["Now"]) == 1

    def test_repeated_removal_idempotent(self) -> None:
        """Removing the same identity twice is idempotent."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-rep"), "Now")
        ident = StrategyIdentity(type="ticket", ref="T-rep")
        r1 = remove_roadmap_entry(doc, ident)
        r2 = remove_roadmap_entry(r1, ident)
        assert len(r2.roadmap["Now"]) == 0
        # No warning diagnostics generated for non-existent removal
        assert len(r2.diagnostics) == 0


# ---------------------------------------------------------------------------
# replace_roadmap_entry
# ---------------------------------------------------------------------------


class TestReplaceRoadmapEntry:
    """Tests for replace_roadmap_entry — the building block for promotion."""

    def test_replace_in_same_horizon(self) -> None:
        """Replacing a ticket with an epic in the same horizon works."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-promo", "Auth fix"), "Now")

        old_id = StrategyIdentity(type="ticket", ref="T-promo")
        new_entry = _entry("epic", "auth-initiative", "Auth Initiative")
        result = replace_roadmap_entry(doc, old_id, new_entry, "Now")

        assert len(result.roadmap["Now"]) == 1
        assert result.roadmap["Now"][0].identity.type == "epic"
        assert result.roadmap["Now"][0].identity.ref == "auth-initiative"
        assert result.roadmap["Now"][0].horizon == "Now"

    def test_old_not_present_no_forced_visibility(self) -> None:
        """When old identity is absent, new entry is still added — no forced visibility violation."""
        doc = _empty_document()
        old_id = StrategyIdentity(type="ticket", ref="not-in-roadmap")
        new_entry = _entry("epic", "new-epic", "New Epic")
        result = replace_roadmap_entry(doc, old_id, new_entry, "Now")

        assert len(result.roadmap["Now"]) == 1
        assert result.roadmap["Now"][0].identity.type == "epic"
        assert result.roadmap["Now"][0].identity.ref == "new-epic"
        # No entry was forced for the absent ticket
        assert not any(
            e.identity.ref == "not-in-roadmap" for e in result.roadmap["Now"]
        )

    def test_new_identity_already_present_idempotent(self) -> None:
        """When new identity already exists, replace is idempotent for the add step."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("epic", "existing-epic"), "Now")
        doc = add_roadmap_entry(doc, _entry("ticket", "T-old"), "Next")

        old_id = StrategyIdentity(type="ticket", ref="T-old")
        new_entry = _entry("epic", "existing-epic")
        result = replace_roadmap_entry(doc, old_id, new_entry, "Now")

        # old ticket was in Next, should be removed
        assert len(result.roadmap["Next"]) == 0
        # new epic already in Now, should not duplicate
        assert len(result.roadmap["Now"]) == 1
        assert result.roadmap["Now"][0].identity.ref == "existing-epic"
        warnings = [d for d in result.diagnostics if d.level == "warning"]
        assert len(warnings) >= 1
        assert any("already exists" in w.message for w in warnings)

    def test_original_document_immutable(self) -> None:
        """The original document is not modified by replace."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-imm"), "Now")
        old_id = StrategyIdentity(type="ticket", ref="T-imm")
        new_entry = _entry("epic", "new-epic")
        _ = replace_roadmap_entry(doc, old_id, new_entry, "Now")
        assert doc.roadmap["Now"][0].identity.type == "ticket"

    def test_replace_with_explicit_horizon_change(self) -> None:
        """Replace can change the horizon of the promoted item."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-later", horizon="Later"), "Later")

        old_id = StrategyIdentity(type="ticket", ref="T-later")
        new_entry = _entry("epic", "now-epic", horizon="Now")
        result = replace_roadmap_entry(doc, old_id, new_entry, "Now")

        assert len(result.roadmap["Later"]) == 0
        assert len(result.roadmap["Now"]) == 1
        assert result.roadmap["Now"][0].identity.ref == "now-epic"


# ---------------------------------------------------------------------------
# promote_ticket_to_epic
# ---------------------------------------------------------------------------


class TestPromoteTicketToEpic:
    """Tests for promote_ticket_to_epic — the high-level promotion helper."""

    def test_promote_in_same_horizon_default(self) -> None:
        """Promoting a ticket replaces it with an epic in the ticket's horizon."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-001", "Fix auth"), "Next")

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-001",
            epic_ref="auth-fix",
            epic_display_title="Authentication Fix Initiative",
        )

        # Ticket removed, epic added in same horizon (Next)
        assert len(result.roadmap["Next"]) == 1
        assert result.roadmap["Next"][0].identity.type == "epic"
        assert result.roadmap["Next"][0].identity.ref == "auth-fix"
        assert result.roadmap["Next"][0].display_title == "Authentication Fix Initiative"

    def test_promote_with_explicit_horizon(self) -> None:
        """Explicit horizon overrides the ticket's current horizon."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-002", "Rate limit"), "Now")

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-002",
            epic_ref="rate-limit",
            epic_display_title="Rate Limiting",
            horizon="Later",
        )

        assert len(result.roadmap["Now"]) == 0
        assert len(result.roadmap["Later"]) == 1
        assert result.roadmap["Later"][0].identity.ref == "rate-limit"

    def test_non_roadmap_ticket_no_forced_visibility(self) -> None:
        """Ticket not in roadmap — no entry forced; epic added if not present."""
        doc = _empty_document()

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="non-roadmap-ticket",
            epic_ref="new-initiative",
            epic_display_title="New Initiative",
        )

        # Ticket was never in roadmap, so nothing removed
        # Epic is added to default "Next" (since ticket not found and no explicit horizon)
        assert len(result.roadmap["Next"]) == 1
        assert result.roadmap["Next"][0].identity.type == "epic"
        assert result.roadmap["Next"][0].identity.ref == "new-initiative"
        # No ticket-forcing: the ticket ref does not appear anywhere
        for h in ("Now", "Next", "Later"):
            assert not any(
                e.identity.ref == "non-roadmap-ticket" for e in result.roadmap[h]
            )

    def test_epic_already_present_idempotent(self) -> None:
        """When the epic already exists, promotion is idempotent — no duplicate."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-003"), "Now")
        doc = add_roadmap_entry(doc, _entry("epic", "already-epic"), "Now")

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-003",
            epic_ref="already-epic",
            epic_display_title="Already Epic",
        )

        # Ticket removed, epic still present (no duplicate)
        assert len(result.roadmap["Now"]) == 1
        assert result.roadmap["Now"][0].identity.type == "epic"
        assert result.roadmap["Now"][0].identity.ref == "already-epic"
        warnings = [d for d in result.diagnostics if d.level == "warning"]
        assert any("already exists" in w.message for w in warnings)

    def test_duplicate_intent_detection(self) -> None:
        """When both ticket and epic are in roadmap, a duplicate-intent diagnostic is emitted."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-dup", "Dup ticket"), "Now")
        doc = add_roadmap_entry(doc, _entry("epic", "dup-epic", "Dup epic"), "Later")

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-dup",
            epic_ref="dup-epic",
            epic_display_title="Duplicate Epic",
        )

        # Ticket removed, epic kept (no duplicate entry added)
        assert len(result.roadmap["Now"]) == 0  # ticket removed from Now
        assert len(result.roadmap["Later"]) == 1  # epic kept in Later
        assert result.roadmap["Later"][0].identity.ref == "dup-epic"

        # Duplicate-intent diagnostic emitted
        dup_diags = [
            d
            for d in result.diagnostics
            if d.level == "warning" and "Duplicate intent detected" in d.message
        ]
        assert len(dup_diags) == 1
        assert "T-dup" in dup_diags[0].message
        assert "dup-epic" in dup_diags[0].message

    def test_duplicate_intent_diagnostic_has_mutation_source(self) -> None:
        """The duplicate-intent diagnostic carries the mutation sentinel source location."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-src"), "Now")
        doc = add_roadmap_entry(doc, _entry("epic", "epic-src"), "Next")

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-src",
            epic_ref="epic-src",
            epic_display_title="Source Test",
        )

        dup_diags = [
            d
            for d in result.diagnostics
            if d.level == "warning" and "Duplicate intent" in d.message
        ]
        assert len(dup_diags) == 1
        assert dup_diags[0].source_location is not None
        assert dup_diags[0].source_location.path == _MUTATION_PATH

    def test_original_document_immutable(self) -> None:
        """The original document is never mutated by promote_ticket_to_epic."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-imm"), "Now")
        _ = promote_ticket_to_epic(
            doc,
            ticket_ref="T-imm",
            epic_ref="imm-epic",
            epic_display_title="Immutable",
        )
        assert doc.roadmap["Now"][0].identity.type == "ticket"

    def test_promote_preserves_other_entries(self) -> None:
        """Promotion only affects the promoted ticket/epic; other entries are untouched."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-keep", "Keep me"), "Now")
        doc = add_roadmap_entry(doc, _entry("ticket", "T-promo", "Promote me"), "Now")
        doc = add_roadmap_entry(doc, _entry("epic", "other-epic"), "Later")

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-promo",
            epic_ref="promoted-epic",
            epic_display_title="Promoted",
        )

        # T-keep is still there
        keep_entries = [e for e in result.roadmap["Now"] if e.identity.ref == "T-keep"]
        assert len(keep_entries) == 1
        # other-epic is still in Later
        other = [e for e in result.roadmap["Later"] if e.identity.ref == "other-epic"]
        assert len(other) == 1

    def test_promote_ticket_only_in_roadmap_no_epic(self) -> None:
        """Ticket in roadmap, no epic present — standard promotion."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-only"), "Later")

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-only",
            epic_ref="only-epic",
            epic_display_title="Only Epic",
        )

        assert len(result.roadmap["Later"]) == 1
        assert result.roadmap["Later"][0].identity.type == "epic"
        assert result.roadmap["Later"][0].identity.ref == "only-epic"
        # No duplicate-intent diagnostic expected
        dup = [d for d in result.diagnostics if "Duplicate intent" in d.message]
        assert dup == []

    def test_promote_epic_only_in_roadmap_no_ticket(self) -> None:
        """Epic already in roadmap, ticket not — epic kept, no duplicate."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("epic", "standalone-epic"), "Now")

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="no-such-ticket",
            epic_ref="standalone-epic",
            epic_display_title="Standalone",
        )

        assert len(result.roadmap["Now"]) == 1
        assert result.roadmap["Now"][0].identity.ref == "standalone-epic"
        # Ticket not forced
        assert not any(
            e.identity.ref == "no-such-ticket"
            for entries in result.roadmap.values()
            for e in entries
        )


# ---------------------------------------------------------------------------
# deterministic serialization
# ---------------------------------------------------------------------------


class TestDeterministicSerialization:
    """Tests proving serialize_strategy produces deterministic output."""

    def test_serialize_deterministic_same_input(self) -> None:
        """Same parsed document produces byte-for-byte identical serialization."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-det"), "Now")
        doc = add_roadmap_entry(doc, _entry("epic", "E-det"), "Next")

        s1 = serialize_strategy(doc)
        s2 = serialize_strategy(doc)
        assert s1 == s2

    def test_serialize_round_trip_after_mutation(self) -> None:
        """After a mutation, serialize → re-parse preserves roadmap identity."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-rt", "Round trip"), "Now")
        doc = add_roadmap_entry(doc, _entry("epic", "E-rt"), "Later")

        # Promote the ticket
        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-rt",
            epic_ref="promoted-rt",
            epic_display_title="Promoted RT",
        )

        serialized = serialize_strategy(result)
        re_parsed = parse_strategy(serialized, "test.md")

        # Verify the promoted state is preserved
        assert len(re_parsed.roadmap["Now"]) == 1
        assert re_parsed.roadmap["Now"][0].identity.type == "epic"
        assert re_parsed.roadmap["Now"][0].identity.ref == "promoted-rt"
        assert re_parsed.roadmap["Now"][0].display_title == "Promoted RT"

        # Other entries preserved
        assert len(re_parsed.roadmap["Later"]) == 1
        assert re_parsed.roadmap["Later"][0].identity.ref == "E-rt"

    def test_serialize_mutation_entries_have_correct_sentinel_on_reparse(self) -> None:
        """Mutation-generated entries carry sentinel source location; after re-parse
        they get the file's source location which is expected behavior."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-sent"), "Now")

        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-sent",
            epic_ref="sent-epic",
            epic_display_title="Sentinel",
        )

        # Before serialization, the mutation entry has sentinel path
        assert result.roadmap["Now"][0].source_location.path == _MUTATION_PATH

        serialized = serialize_strategy(result)
        re_parsed = parse_strategy(serialized, "test.md")

        # After re-parse, source location comes from the file (expected)
        assert re_parsed.roadmap["Now"][0].identity.ref == "sent-epic"
        assert re_parsed.roadmap["Now"][0].source_location.path == "test.md"

    def test_serialize_deterministic_after_replace(self) -> None:
        """Serialization is deterministic after a replace_roadmap_entry."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-rep-ser"), "Later")

        result = replace_roadmap_entry(
            doc,
            old_identity=StrategyIdentity(type="ticket", ref="T-rep-ser"),
            new_entry=_entry("epic", "E-rep-ser"),
            horizon="Later",
        )

        s1 = serialize_strategy(result)
        s2 = serialize_strategy(result)
        assert s1 == s2

    def test_empty_document_serialization_deterministic(self) -> None:
        """An empty document serializes deterministically."""
        doc = _empty_document()
        s1 = serialize_strategy(doc)
        s2 = serialize_strategy(doc)
        assert s1 == s2

    def test_full_promotion_cycle_serialization_consistency(self) -> None:
        """A full promote → remove → add cycle produces consistent serialization."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-cycle"), "Now")

        # Promote
        doc = promote_ticket_to_epic(
            doc, ticket_ref="T-cycle", epic_ref="E-cycle", epic_display_title="Cycle"
        )
        # Remove the epic
        doc = remove_roadmap_entry(
            doc, StrategyIdentity(type="epic", ref="E-cycle")
        )
        # Add a new ticket
        doc = add_roadmap_entry(doc, _entry("ticket", "T-new"), "Next")

        s1 = serialize_strategy(doc)
        s2 = serialize_strategy(doc)
        assert s1 == s2

        # And re-parse should be clean (no parse errors from the serialized form)
        re_parsed = parse_strategy(s1, "test.md")
        assert len(re_parsed.roadmap["Now"]) == 0
        assert len(re_parsed.roadmap["Next"]) == 1
        assert re_parsed.roadmap["Next"][0].identity.ref == "T-new"


# ---------------------------------------------------------------------------
# Cross-cutting: mutation source location
# ---------------------------------------------------------------------------


class TestMutationSourceLocation:
    """Sentinel source location is used consistently for mutation-generated entries."""

    def test_add_entry_uses_provided_source_location(self) -> None:
        """Add uses the entry's source_location, not a sentinel."""
        doc = _empty_document()
        entry = _entry("ticket", "T-src", path="custom.md")
        result = add_roadmap_entry(doc, entry, "Now")
        # The entry is passed as-is; source_location from caller is preserved
        assert result.roadmap["Now"][0].source_location.path == "custom.md"

    def test_promote_generated_entry_uses_mutation_sentinel(self) -> None:
        """The epic entry generated by promote_ticket_to_epic uses the mutation sentinel."""
        doc = _empty_document()
        doc = add_roadmap_entry(doc, _entry("ticket", "T-src2"), "Now")
        result = promote_ticket_to_epic(
            doc,
            ticket_ref="T-src2",
            epic_ref="sentinel-epic",
            epic_display_title="Sentinel Epic",
        )
        assert result.roadmap["Now"][0].source_location.path == _MUTATION_PATH
        assert result.roadmap["Now"][0].source_location.line == 0
        assert result.roadmap["Now"][0].source_location.column == 0
