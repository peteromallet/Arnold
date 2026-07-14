"""Model-level contract tests for the v1 strategy types.

These tests prove the North Star invariants defined in the strategy
contract: exactly two executable item types, identity as ``(type, ref)``,
and the absence of artifact body or lifecycle-status fields on any
strategy model.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest

from arnold_pipelines.megaplan.strategy.contract import (
    REQUIRED_ROADMAP_SECTIONS,
    REQUIRED_STABLE_SECTIONS,
    SCHEMA_VERSION,
    RoadmapEntry,
    RoadmapItemType,
    SourceLocation,
    StrategyDocument,
    StrategyIdentity,
    StrategySection,
)
from arnold_pipelines.megaplan.strategy.parser import (
    parse_strategy,
    serialize_strategy,
)


# ---------------------------------------------------------------------------
# Executable item vocabulary
# ---------------------------------------------------------------------------


class TestExecutableItemVocabulary:
    """The executable item vocabulary is exactly ``ticket`` and ``epic``."""

    def test_roadmap_item_type_is_literal(self) -> None:
        """RoadmapItemType must be a typing.Literal, not a plain str alias."""
        origin = typing.get_origin(RoadmapItemType)
        assert origin is typing.Literal, (
            f"RoadmapItemType origin is {origin}, expected typing.Literal"
        )

    def test_literal_contains_exactly_ticket_and_epic(self) -> None:
        """The literal MUST contain exactly 'ticket' and 'epic' — no more, no less."""
        args = set(typing.get_args(RoadmapItemType))
        expected = {"ticket", "epic"}
        assert args == expected, (
            f"RoadmapItemType args are {sorted(args)}, expected {sorted(expected)}. "
            "Adding a third executable item type would violate the v1 contract."
        )

    def test_no_other_literals_are_valid(self) -> None:
        """Verify that attempting to assign a third value is caught by the type system."""
        # This is a static assertion: the test documents that the literal
        # has exactly two members.  Runtime attempts to construct a
        # StrategyIdentity with a third type would fail type-checking.
        args = typing.get_args(RoadmapItemType)
        assert len(args) == 2, (
            f"RoadmapItemType has {len(args)} members; expected exactly 2 (ticket, epic)"
        )


# ---------------------------------------------------------------------------
# Identity: (type, ref)
# ---------------------------------------------------------------------------


class TestStrategyIdentityShape:
    """Identity is exactly ``(type, ref)`` — no extra fields."""

    def test_field_names_are_exactly_type_and_ref(self) -> None:
        """StrategyIdentity must have exactly ``type`` and ``ref`` fields."""
        fields = {f.name for f in dataclasses.fields(StrategyIdentity)}
        expected = {"type", "ref"}
        assert fields == expected, (
            f"StrategyIdentity fields are {sorted(fields)}, "
            f"expected {sorted(expected)}. "
            "Identity must be the (type, ref) pair — nothing else."
        )

    def test_type_field_is_roadmap_item_type(self) -> None:
        """The ``type`` field must resolve to RoadmapItemType."""
        field = next(f for f in dataclasses.fields(StrategyIdentity) if f.name == "type")
        # The field type annotation may be a string or the actual type
        resolved = field.type
        assert resolved is RoadmapItemType or resolved == "RoadmapItemType", (
            f"StrategyIdentity.type field type is {resolved}, expected RoadmapItemType"
        )

    def test_ref_field_is_str(self) -> None:
        """The ``ref`` field must be a plain ``str``."""
        field = next(f for f in dataclasses.fields(StrategyIdentity) if f.name == "ref")
        # With ``from __future__ import annotations`` the field type may be the
        # string "str" rather than the str type object.
        assert field.type in (str, "str"), (
            f"StrategyIdentity.ref field type is {field.type!r}, expected str or 'str'"
        )

    def test_identity_construction(self) -> None:
        """Smoke-test that identity can be constructed with the expected fields."""
        identity = StrategyIdentity(type="ticket", ref="TICKET-001")
        assert identity.type == "ticket"
        assert identity.ref == "TICKET-001"

    def test_identity_is_frozen(self) -> None:
        """StrategyIdentity must be immutable."""
        identity = StrategyIdentity(type="epic", ref="EPIC-001")
        with pytest.raises(dataclasses.FrozenInstanceError):
            identity.ref = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# No artifact body or lifecycle-status fields
# ---------------------------------------------------------------------------


# Fields whose presence would indicate a body or lifecycle leak.
_FORBIDDEN_FIELD_SUBSTRINGS: tuple[str, ...] = (
    "body",
    "status",
    "lifecycle",
    "description",
    "content",
    "state",
    "phase",
    "plan",
    "plans",
    "completed",
    "completion",
    "closed",
    "resolved",
    "progress",
)


def _assert_no_forbidden_fields(cls: type, class_name: str) -> None:
    """Assert that *cls* has no fields matching any forbidden substring."""
    field_names = {f.name for f in dataclasses.fields(cls)}
    for name in field_names:
        lower = name.lower()
        for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
            assert forbidden not in lower, (
                f"{class_name}.{name} matches forbidden pattern '{forbidden}'. "
                "The v1 strategy model must not carry artifact body or "
                "lifecycle-status fields."
            )


class TestNoBodyOrLifecycleFields:
    """The strategy model has no artifact body or lifecycle-status fields."""

    def test_roadmap_entry_no_body_or_lifecycle(self) -> None:
        """RoadmapEntry must not carry body, status, or lifecycle fields."""
        _assert_no_forbidden_fields(RoadmapEntry, "RoadmapEntry")

    def test_strategy_document_no_body_or_lifecycle(self) -> None:
        """StrategyDocument must not carry body, status, or lifecycle fields."""
        _assert_no_forbidden_fields(StrategyDocument, "StrategyDocument")

    def test_strategy_section_no_body_or_lifecycle(self) -> None:
        """StrategySection must not carry lifecycle fields beyond its Markdown body."""
        # StrategySection *does* have a ``body`` field for the Markdown content,
        # but that is NOT an artifact body — it's the raw Markdown text of the
        # stable-direction section.  We verify that field exists and is a str,
        # and that no *other* forbidden fields leak in.
        field_names = {f.name for f in dataclasses.fields(StrategySection)}
        assert "body" in field_names, "StrategySection must have a body field for Markdown text"
        assert "title" in field_names
        assert "source_location" in field_names

        # Now check for anything lifecycle-y beyond the expected Markdown body.
        lifecycle_fields = {"status", "lifecycle", "state", "phase", "plan", "plans",
                            "completed", "completion", "closed", "resolved", "progress"}
        for name in field_names:
            assert name not in lifecycle_fields, (
                f"StrategySection.{name} is a lifecycle-status field — not allowed. "
                "StrategySection may carry Markdown body text, not artifact lifecycle data."
            )

    def test_strategy_identity_no_body_or_lifecycle(self) -> None:
        """StrategyIdentity must only have type and ref — no body/status."""
        _assert_no_forbidden_fields(StrategyIdentity, "StrategyIdentity")

    def test_roadmap_entry_exact_fields(self) -> None:
        """RoadmapEntry must have exactly: identity, display_title, horizon, source_location."""
        field_names = {f.name for f in dataclasses.fields(RoadmapEntry)}
        expected = {"identity", "display_title", "horizon", "source_location"}
        assert field_names == expected, (
            f"RoadmapEntry fields are {sorted(field_names)}, "
            f"expected {sorted(expected)}"
        )

    def test_strategy_document_exact_fields(self) -> None:
        """StrategyDocument must have exactly: schema_version, stable_direction, roadmap, diagnostics."""
        field_names = {f.name for f in dataclasses.fields(StrategyDocument)}
        expected = {"schema_version", "stable_direction", "roadmap", "diagnostics"}
        assert field_names == expected, (
            f"StrategyDocument fields are {sorted(field_names)}, "
            f"expected {sorted(expected)}"
        )


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------


class TestStrategyModelIsFrozen:
    """All strategy models are frozen dataclasses."""

    def test_strategy_document_is_dataclass(self) -> None:
        assert dataclasses.is_dataclass(StrategyDocument)

    def test_strategy_document_is_frozen(self) -> None:
        doc = StrategyDocument(
            schema_version="megaplan-strategy-v1",
            stable_direction=[],
            roadmap={"Now": [], "Next": [], "Later": []},
            diagnostics=[],
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            doc.schema_version = "hacked"  # type: ignore[misc]

    def test_roadmap_entry_is_frozen(self) -> None:
        entry = RoadmapEntry(
            identity=StrategyIdentity(type="ticket", ref="T-1"),
            display_title="A ticket",
            horizon="Now",
            source_location=SourceLocation(path="test.md", line=1, column=1),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.horizon = "Later"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Parser golden coverage
# ---------------------------------------------------------------------------


_STRATEGY_V1_FIXTURE_SOURCE = """---
schema_version: megaplan-strategy-v1
---

## Mission

Provide a reliable, self-service platform.

## Principles

- Determinism over convenience.
- Identity over display.

## Architecture Direction

Layered architecture with strategy as single source of truth.

## Constraints

- Python 3.11+.
- YAML frontmatter only.

## Non-Goals

- Automatic synchronization.
- Real-time dashboard.

## Now

- [ticket:01KT50AZRMK5X890TQ565DDB5V] Fix auth timeout
- [epic:strategy-roadmap] Strategy contract

## Next

- [ticket:01KT50AZRMK5X890TQ565DDB5W] Rate-limiting middleware

## Later

- [epic:multi-tenant] Tenant isolation
"""


class TestGoldenCanonicalParsing:
    """Parse the canonical golden v1 strategy and verify zero-diagnostic clean parse."""

    def test_golden_file_on_disk_parses_clean(self) -> None:
        """The golden fixture file on disk must parse with zero diagnostics."""
        import pathlib
        golden_path = pathlib.Path(__file__).parent / "golden" / "strategy_v1.md"
        source = golden_path.read_text()
        doc = parse_strategy(source, str(golden_path))
        assert doc.diagnostics == [], (
            f"Golden file produced diagnostics: {doc.diagnostics}"
        )

    def test_golden_parse_has_zero_diagnostics(self) -> None:
        """A complete, well-formed v1 strategy must parse with zero diagnostics."""
        doc = parse_strategy(_STRATEGY_V1_FIXTURE_SOURCE, "test.md")
        assert doc.diagnostics == [], (
            f"Expected zero diagnostics but got: {doc.diagnostics}"
        )

    def test_golden_parse_preserves_schema_version(self) -> None:
        doc = parse_strategy(_STRATEGY_V1_FIXTURE_SOURCE, "test.md")
        assert doc.schema_version == SCHEMA_VERSION, (
            f"Expected '{SCHEMA_VERSION}', got '{doc.schema_version}'"
        )

    def test_golden_parse_all_stable_sections_present(self) -> None:
        doc = parse_strategy(_STRATEGY_V1_FIXTURE_SOURCE, "test.md")
        titles = [s.title for s in doc.stable_direction]
        assert titles == list(REQUIRED_STABLE_SECTIONS), (
            f"Expected stable sections {list(REQUIRED_STABLE_SECTIONS)}, "
            f"got {titles}"
        )

    def test_golden_parse_stable_sections_have_bodies(self) -> None:
        doc = parse_strategy(_STRATEGY_V1_FIXTURE_SOURCE, "test.md")
        for section in doc.stable_direction:
            assert section.body.strip(), (
                f"Section '{section.title}' has empty body; "
                f"golden fixture should supply non-empty bodies"
            )

    def test_golden_parse_roadmap_entry_counts(self) -> None:
        doc = parse_strategy(_STRATEGY_V1_FIXTURE_SOURCE, "test.md")
        assert len(doc.roadmap["Now"]) == 2
        assert len(doc.roadmap["Next"]) == 1
        assert len(doc.roadmap["Later"]) == 1

    def test_golden_parse_roadmap_identities(self) -> None:
        doc = parse_strategy(_STRATEGY_V1_FIXTURE_SOURCE, "test.md")
        now_identities = [(e.identity.type, e.identity.ref) for e in doc.roadmap["Now"]]
        assert ("ticket", "01KT50AZRMK5X890TQ565DDB5V") in now_identities
        assert ("epic", "strategy-roadmap") in now_identities

    def test_golden_parse_roadmap_horizons_are_correct(self) -> None:
        doc = parse_strategy(_STRATEGY_V1_FIXTURE_SOURCE, "test.md")
        for entry in doc.roadmap["Now"]:
            assert entry.horizon == "Now"
        for entry in doc.roadmap["Next"]:
            assert entry.horizon == "Next"
        for entry in doc.roadmap["Later"]:
            assert entry.horizon == "Later"

    def test_golden_parse_source_locations_are_populated(self) -> None:
        doc = parse_strategy(_STRATEGY_V1_FIXTURE_SOURCE, "test.md")
        for section in doc.stable_direction:
            assert section.source_location.path == "test.md"
            assert section.source_location.line >= 1
        for entries in doc.roadmap.values():
            for entry in entries:
                assert entry.source_location.path == "test.md"
                assert entry.source_location.line >= 1


class TestMalformedBullets:
    """Parser must diagnose malformed roadmap bullets at source locations."""

    def test_empty_ref_produces_diagnostic(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

Test.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

- [ticket:] Missing ref

## Next

## Later
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        # Should have at least one error about missing ref
        assert len(errors) >= 1, f"Expected at least one error for empty ref, got {errors}"
        ref_errors = [e for e in errors if "Missing reference" in e.message or "empty" in e.message.lower()]
        assert len(ref_errors) >= 1, (
            f"Expected diagnostic about missing/empty ref, got: {errors}"
        )

    def test_invalid_item_type_produces_diagnostic(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

Test.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

- [story:STORY-1] A story (not ticket/epic)

## Next

## Later
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        type_errors = [e for e in errors if "story" in e.message.lower() or "Unsupported item type" in e.message]
        assert len(type_errors) >= 1, (
            f"Expected diagnostic about unsupported item type 'story', got: {errors}"
        )

    def test_malformed_bullet_with_no_title(self) -> None:
        """A bullet with correct brackets but no display title after ']' is malformed."""
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

Test.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

- [ticket:ABC]

## Next

## Later
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        bullet_errors = [e for e in errors if "Malformed roadmap bullet" in e.message]
        assert len(bullet_errors) >= 1, (
            f"Expected at least one malformed bullet diagnostic, got: {errors}"
        )

    def test_malformed_bullet_has_source_location(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

Test.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

- [ticket:] Missing ref

## Next

## Later
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        ref_errors = [
            e for e in errors
            if "Missing reference" in e.message or "Malformed" in e.message
        ]
        for diag in ref_errors:
            assert diag.source_location is not None, (
                f"Diagnostic must have a source location: {diag}"
            )
            assert diag.source_location.path == "test.md"
            assert diag.source_location.line >= 1


class TestUnsupportedSchemaVersions:
    """Parser must diagnose unsupported or missing schema versions."""

    def test_missing_frontmatter_diagnostic(self) -> None:
        source = """# No frontmatter

## Mission

Test body.
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        fm_errors = [e for e in errors if "frontmatter" in e.message.lower()]
        assert len(fm_errors) >= 1, (
            f"Expected missing-frontmatter diagnostic, got: {errors}"
        )

    def test_unclosed_frontmatter_diagnostic(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1

## Mission

Test body.
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        unclosed = [e for e in errors if "Unclosed" in e.message]
        assert len(unclosed) >= 1, (
            f"Expected unclosed-frontmatter diagnostic, got: {errors}"
        )

    def test_unsupported_schema_version_diagnostic(self) -> None:
        source = """---
schema_version: megaplan-strategy-v2
---

## Mission

Test body.
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        version_errors = [e for e in errors if "Unsupported schema_version" in e.message]
        assert len(version_errors) >= 1, (
            f"Expected unsupported-schema-version diagnostic, got: {errors}"
        )

    def test_wrong_schema_version_is_present_but_parsed(self) -> None:
        """Even with wrong version, the parser must return a StrategyDocument."""
        source = """---
schema_version: megaplan-strategy-v2
---

## Mission

Test body.
"""
        doc = parse_strategy(source, "test.md")
        assert doc.schema_version == "megaplan-strategy-v2"
        errors = [d for d in doc.diagnostics if d.level == "error"]
        assert any("Unsupported schema_version" in e.message for e in errors)

    def test_invalid_yaml_frontmatter_diagnostic(self) -> None:
        source = """---
schema_version: [this is invalid YAML}
---

## Mission

Test.
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        yaml_errors = [e for e in errors if "YAML" in e.message or "Invalid" in e.message]
        assert len(yaml_errors) >= 1, (
            f"Expected invalid-YAML diagnostic, got: {errors}"
        )


class TestMissingRequiredSections:
    """Parser must diagnose missing required stable-direction or roadmap sections."""

    def test_missing_single_stable_section(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

## Next

## Later
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        missing = [e for e in errors if "Missing required stable-direction" in e.message]
        assert len(missing) >= 1, (
            f"Expected missing-stable-section diagnostic, got: {errors}"
        )
        # Specifically missing "Principles"
        principles_errors = [e for e in missing if "Principles" in e.message]
        assert len(principles_errors) >= 1, (
            f"Expected diagnostic about missing 'Principles', got: {missing}"
        )

    def test_missing_roadmap_section(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

Test.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

## Next
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        missing = [e for e in errors if "Missing required roadmap" in e.message]
        assert len(missing) >= 1, (
            f"Expected missing-roadmap-section diagnostic, got: {errors}"
        )

    def test_missing_all_sections_diagnoses_all(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1
---
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        missing_stable = [e for e in errors if "Missing required stable-direction" in e.message]
        missing_roadmap = [e for e in errors if "Missing required roadmap" in e.message]
        assert len(missing_stable) == len(REQUIRED_STABLE_SECTIONS), (
            f"Expected {len(REQUIRED_STABLE_SECTIONS)} missing-stable diagnostics, "
            f"got {len(missing_stable)}: {missing_stable}"
        )
        assert len(missing_roadmap) == len(REQUIRED_ROADMAP_SECTIONS), (
            f"Expected {len(REQUIRED_ROADMAP_SECTIONS)} missing-roadmap diagnostics, "
            f"got {len(missing_roadmap)}: {missing_roadmap}"
        )

    def test_unrecognised_section_diagnostic(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

Test.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Unknown Section

Some content.

## Now

## Next

## Later
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        unsupported = [e for e in errors if "Unsupported section" in e.message]
        assert len(unsupported) >= 1, (
            f"Expected unsupported-section diagnostic, got: {errors}"
        )
        assert "Unknown Section" in unsupported[0].message


class TestTypedBulletsOutsideRoadmap:
    """Parser must diagnose typed bullets appearing in stable-direction sections."""

    def test_typed_bullet_in_stable_section_produces_diagnostic(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

- [ticket:T-1] This bullet should not be here
Some prose.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

## Next

## Later
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        outside = [e for e in errors if "outside a roadmap section" in e.message]
        assert len(outside) >= 1, (
            f"Expected typed-bullet-outside-roadmap diagnostic, got: {errors}"
        )

    def test_typed_bullet_in_constraints_produces_diagnostic(self) -> None:
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

Test.

## Principles

Test.

## Architecture Direction

Test.

## Constraints

- [epic:thing] An epic bullet in Constraints

## Non-Goals

Test.

## Now

## Next

## Later
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        outside = [e for e in errors if "outside a roadmap section" in e.message]
        assert len(outside) >= 1, (
            f"Expected typed-bullet-outside-roadmap diagnostic for Constraints, got: {errors}"
        )

    def test_untyped_bullet_in_stable_section_no_diagnostic(self) -> None:
        """Regular Markdown bullets (without [type:ref]) are fine anywhere."""
        source = """---
schema_version: megaplan-strategy-v1
---

## Mission

- This is a regular bullet
- Another regular bullet point

## Principles

Test.

## Architecture Direction

Test.

## Constraints

Test.

## Non-Goals

Test.

## Now

## Next

## Later
"""
        doc = parse_strategy(source, "test.md")
        errors = [d for d in doc.diagnostics if d.level == "error"]
        outside = [e for e in errors if "outside a roadmap" in e.message]
        assert outside == [], (
            f"Regular bullets should not trigger roadmap-outside diagnostic: {outside}"
        )


_STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP = """---
schema_version: megaplan-strategy-v1
---

## Mission

Provide a reliable, self-service platform for planning and governing AI-driven work.

## Principles

- Determinism over convenience.
- Fail closed on ambiguity.

## Architecture Direction

Layered architecture with the strategy Markdown as single source of truth.
All downstream projections are disposable.

## Constraints

- Python 3.11+.
- YAML frontmatter only.
- Narrow bullet grammar: ``- [type:ref] title``.

## Non-Goals

- Automatic issue tracker sync for v1.
- Multi-repo strategy federation.

## Now

- [ticket:T-001] Fix authentication timeout in gateway
- [epic:typed-strategy] Implement typed strategy contract

## Next

- [ticket:T-002] Add rate-limiting middleware

## Later

- [epic:observability] Build observability pipeline
"""


class TestSerializerRoundTrip:
    """Serializer must preserve semantics across parse → serialize → re-parse."""

    def test_round_trip_produces_zero_diagnostics(self) -> None:
        source = _STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP
        doc1 = parse_strategy(source, "test.md")
        assert doc1.diagnostics == [], f"First parse must be clean: {doc1.diagnostics}"

        serialized = serialize_strategy(doc1)
        doc2 = parse_strategy(serialized, "test.md")
        assert doc2.diagnostics == [], (
            f"Re-parse after serialize must also be clean: {doc2.diagnostics}"
        )

    def test_round_trip_preserves_schema_version(self) -> None:
        source = _STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP
        doc1 = parse_strategy(source, "test.md")
        doc2 = parse_strategy(serialize_strategy(doc1), "test.md")
        assert doc2.schema_version == doc1.schema_version == SCHEMA_VERSION

    def test_round_trip_preserves_stable_section_count(self) -> None:
        source = _STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP
        doc1 = parse_strategy(source, "test.md")
        doc2 = parse_strategy(serialize_strategy(doc1), "test.md")
        assert len(doc2.stable_direction) == len(doc1.stable_direction)

    def test_round_trip_preserves_stable_section_titles(self) -> None:
        source = _STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP
        doc1 = parse_strategy(source, "test.md")
        doc2 = parse_strategy(serialize_strategy(doc1), "test.md")
        titles1 = [s.title for s in doc1.stable_direction]
        titles2 = [s.title for s in doc2.stable_direction]
        assert titles2 == titles1

    def test_round_trip_preserves_stable_section_body_semantics(self) -> None:
        """Stable-direction body text is preserved semantically (whitespace may vary)."""
        source = _STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP
        doc1 = parse_strategy(source, "test.md")
        doc2 = parse_strategy(serialize_strategy(doc1), "test.md")
        for s1, s2 in zip(doc1.stable_direction, doc2.stable_direction):
            # Bodies should be semantically equivalent: strip trailing whitespace
            assert s2.body.strip() == s1.body.strip() or s2.body.strip() in s1.body.strip() or s1.body.strip() in s2.body.strip(), (
                f"Body mismatch for '{s1.title}':\n"
                f"  original: {s1.body!r}\n"
                f"  round-trip: {s2.body!r}"
            )

    def test_round_trip_preserves_roadmap_entry_count(self) -> None:
        source = _STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP
        doc1 = parse_strategy(source, "test.md")
        doc2 = parse_strategy(serialize_strategy(doc1), "test.md")
        for horizon in ("Now", "Next", "Later"):
            assert len(doc2.roadmap[horizon]) == len(doc1.roadmap[horizon]), (
                f"Entry count mismatch for {horizon}"
            )

    def test_round_trip_preserves_roadmap_identity(self) -> None:
        source = _STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP
        doc1 = parse_strategy(source, "test.md")
        doc2 = parse_strategy(serialize_strategy(doc1), "test.md")
        for horizon in ("Now", "Next", "Later"):
            ids1 = {(e.identity.type, e.identity.ref) for e in doc1.roadmap[horizon]}
            ids2 = {(e.identity.type, e.identity.ref) for e in doc2.roadmap[horizon]}
            assert ids2 == ids1, (
                f"Identity mismatch for {horizon}: {ids1.symmetric_difference(ids2)}"
            )

    def test_round_trip_preserves_display_titles(self) -> None:
        source = _STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP
        doc1 = parse_strategy(source, "test.md")
        doc2 = parse_strategy(serialize_strategy(doc1), "test.md")
        for horizon in ("Now", "Next", "Later"):
            titles1 = {e.display_title for e in doc1.roadmap[horizon]}
            titles2 = {e.display_title for e in doc2.roadmap[horizon]}
            assert titles2 == titles1, (
                f"Display title mismatch for {horizon}: "
                f"{titles1.symmetric_difference(titles2)}"
            )

    def test_round_trip_preserves_horizon_assignment(self) -> None:
        source = _STRATEGY_V1_FIXTURE_SOURCE_ROUNDTRIP
        doc1 = parse_strategy(source, "test.md")
        doc2 = parse_strategy(serialize_strategy(doc1), "test.md")
        for entry in doc2.roadmap["Now"]:
            assert entry.horizon == "Now"
        for entry in doc2.roadmap["Next"]:
            assert entry.horizon == "Next"
        for entry in doc2.roadmap["Later"]:
            assert entry.horizon == "Later"
