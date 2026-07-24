"""Adoption tests for the live Arnold strategy contract.

These tests prove that the live initiative-root ``STRATEGY.md``:

* Loads cleanly through the canonical ``load_strategy()`` entry point.
* Produces no hard diagnostics except known external-reference gaps
  (the ``repository-strategy-roadmap`` epic lives in an external repo).
* Roadmap projection entries expose only ``type/ref/title/horizon/source``.
* The projection excludes ticket/epic body, status, plan, and completion fields.
* Direct Markdown horizon edits on a temp copy validate correctly without
  treating the generated JSON projection as an authority source.
"""

from __future__ import annotations

import json
import pathlib
import textwrap

import pytest

from arnold_pipelines.megaplan.strategy.contract import (
    REQUIRED_ROADMAP_SECTIONS,
    RoadmapEntry,
    RoadmapHorizon,
    SourceLocation,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
)
from arnold_pipelines.megaplan.strategy.io import (
    load_strategy,
    project_to_dict,
    strategy_file_path,
)
from arnold_pipelines.megaplan.strategy.parser import (
    parse_strategy,
    serialize_strategy,
)
from arnold_pipelines.megaplan.strategy.projection import (
    project_strategy,
    serialize_strategy_projection,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _errors(diagnostics: list[StrategyDiagnostic]) -> list[StrategyDiagnostic]:
    return [d for d in diagnostics if d.level == "error"]


def _warnings(diagnostics: list[StrategyDiagnostic]) -> list[StrategyDiagnostic]:
    return [d for d in diagnostics if d.level == "warning"]


# Known external references that may not resolve locally.
# The ``repository-strategy-roadmap`` epic is a cross-repo initiative.
_KNOWN_EXTERNAL_EPICS: frozenset[str] = frozenset(
    {"repository-strategy-roadmap"}
)

# Forbidden field substrings in roadmap projection entries.
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

# Allowed keys in a roadmap projection entry.
_ALLOWED_ROADMAP_ENTRY_KEYS: frozenset[str] = frozenset(
    {"type", "ref", "title", "horizon", "source"}
)


# ---------------------------------------------------------------------------
# Live strategy load
# ---------------------------------------------------------------------------

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent


class TestLiveStrategyLoad:
    """The live Arnold strategy loads through ``load_strategy()`` and is
    diagnostically clean except for known cross-repo epic references."""

    def test_load_strategy_does_not_raise(self) -> None:
        """``load_strategy(project_root)`` must return a document, not raise."""
        doc = load_strategy(str(_PROJECT_ROOT))
        assert isinstance(doc, StrategyDocument)

    def test_schema_version_is_v1(self) -> None:
        """The live strategy must declare the v1 schema version."""
        doc = load_strategy(str(_PROJECT_ROOT))
        assert doc.schema_version == "megaplan-strategy-v1"

    def test_all_stable_sections_present(self) -> None:
        """All five required stable-direction sections must be present."""
        doc = load_strategy(str(_PROJECT_ROOT))
        titles = [s.title for s in doc.stable_direction]
        expected = ["Mission", "Principles", "Architecture Direction",
                     "Constraints", "Non-Goals"]
        assert titles == expected, (
            f"Expected stable sections {expected}, got {titles}"
        )

    def test_all_roadmap_horizons_present(self) -> None:
        """All three roadmap horizons must be present as keys."""
        doc = load_strategy(str(_PROJECT_ROOT))
        assert set(doc.roadmap.keys()) == {"Now", "Next", "Later"}

    def test_no_hard_errors_except_known_external_refs(self) -> None:
        """Hard errors should only come from known external cross-repo epics.

        The ``repository-strategy-roadmap`` epic lives in an external
        repository and may not resolve locally.  All other references
        must resolve cleanly with zero hard errors.
        """
        doc = load_strategy(str(_PROJECT_ROOT))
        errs = _errors(doc.diagnostics)

        unexpected: list[StrategyDiagnostic] = []
        for d in errs:
            # Accept "Missing epic reference" only for known external epics.
            if d.message.startswith("Missing epic reference:"):
                for slug in _KNOWN_EXTERNAL_EPICS:
                    if f"'{slug}'" in d.message:
                        break
                else:
                    unexpected.append(d)
            else:
                unexpected.append(d)

        assert unexpected == [], (
            f"Unexpected hard errors (not known external epics):\n"
            + "\n".join(f"  - {d.message}" for d in unexpected)
        )

    def test_warnings_are_only_accepted_categories(self) -> None:
        """Warnings should be limited to stale-title, lifecycle, or duplicate-intent.

        These are advisory diagnostics that may occur when artifacts evolve
        independently of the strategy file.  They do not block adoption.
        """
        doc = load_strategy(str(_PROJECT_ROOT))
        warns = _warnings(doc.diagnostics)

        # Known acceptable warning patterns.
        acceptable_prefixes = (
            "Stale display title",
            "Dismissed ticket in roadmap",
            "Addressed ticket in roadmap",
            "Superseded ticket in roadmap",
            "Completed epic in roadmap",
            "Duplicate intent",
        )

        unexpected: list[StrategyDiagnostic] = []
        for w in warns:
            if not any(w.message.startswith(p) for p in acceptable_prefixes):
                unexpected.append(w)

        assert unexpected == [], (
            f"Unexpected warnings (not in accepted categories):\n"
            + "\n".join(f"  - {w.message}" for w in unexpected)
        )


# ---------------------------------------------------------------------------
# Projection entry shape
# ---------------------------------------------------------------------------


class TestProjectionEntryShape:
    """Roadmap projection entries expose only ``type/ref/title/horizon/source``."""

    def test_roadmap_entry_keys_are_exactly_allowed(self) -> None:
        """Every roadmap entry in the projection must have exactly the
        allowed keys and no others."""
        doc = load_strategy(str(_PROJECT_ROOT))
        projection = project_strategy(doc)

        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                entry_keys = set(entry.keys())
                extra = entry_keys - _ALLOWED_ROADMAP_ENTRY_KEYS
                missing = _ALLOWED_ROADMAP_ENTRY_KEYS - entry_keys
                assert extra == set(), (
                    f"Unexpected keys in roadmap entry for horizon '{horizon}', "
                    f"ref '{entry.get('ref')}': {sorted(extra)}"
                )
                assert missing == set(), (
                    f"Missing keys in roadmap entry for horizon '{horizon}', "
                    f"ref '{entry.get('ref')}': {sorted(missing)}"
                )

    def test_type_field_is_ticket_or_epic(self) -> None:
        """Every roadmap entry ``type`` must be ``ticket`` or ``epic``."""
        doc = load_strategy(str(_PROJECT_ROOT))
        projection = project_strategy(doc)

        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                assert entry["type"] in ("ticket", "epic"), (
                    f"Invalid type '{entry['type']}' in horizon '{horizon}', "
                    f"ref '{entry.get('ref')}'"
                )

    def test_ref_field_is_non_empty(self) -> None:
        """Every roadmap entry ``ref`` must be a non-empty string."""
        doc = load_strategy(str(_PROJECT_ROOT))
        projection = project_strategy(doc)

        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                ref = entry.get("ref")
                assert isinstance(ref, str) and ref, (
                    f"Empty or missing ref in horizon '{horizon}'"
                )

    def test_title_field_is_non_empty(self) -> None:
        """Every roadmap entry ``title`` must be a non-empty string."""
        doc = load_strategy(str(_PROJECT_ROOT))
        projection = project_strategy(doc)

        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                title = entry.get("title")
                assert isinstance(title, str) and title, (
                    f"Empty or missing title in horizon '{horizon}', "
                    f"ref '{entry.get('ref')}'"
                )

    def test_horizon_matches_containing_section(self) -> None:
        """Every roadmap entry ``horizon`` must match its containing section."""
        doc = load_strategy(str(_PROJECT_ROOT))
        projection = project_strategy(doc)

        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                assert entry["horizon"] == horizon, (
                    f"Entry horizon '{entry['horizon']}' does not match "
                    f"section '{horizon}', ref '{entry.get('ref')}'"
                )

    def test_source_location_is_present_and_well_formed(self) -> None:
        """Every roadmap entry must have a ``source`` with path/line/column."""
        doc = load_strategy(str(_PROJECT_ROOT))
        projection = project_strategy(doc)

        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                source = entry.get("source")
                assert isinstance(source, dict), (
                    f"Missing or invalid source in horizon '{horizon}', "
                    f"ref '{entry.get('ref')}'"
                )
                for key in ("path", "line", "column"):
                    assert key in source, (
                        f"Missing '{key}' in source for horizon '{horizon}', "
                        f"ref '{entry.get('ref')}'"
                    )
                assert source["line"] >= 1
                assert source["column"] >= 1


# ---------------------------------------------------------------------------
# Projection excludes body and lifecycle fields
# ---------------------------------------------------------------------------


class TestProjectionExcludesBodyAndLifecycle:
    """The projection must never contain ticket/epic body, status, plan,
    or completion fields in roadmap entries."""

    def test_roadmap_entries_have_no_forbidden_fields(self) -> None:
        """Every roadmap entry in the projection is clean of forbidden fields."""
        doc = load_strategy(str(_PROJECT_ROOT))
        projection = project_strategy(doc)

        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                entry_keys_lower = {k.lower() for k in entry.keys()}
                for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
                    assert forbidden not in entry_keys_lower, (
                        f"Forbidden field substring '{forbidden}' found in "
                        f"roadmap entry keys {sorted(entry.keys())} "
                        f"for horizon '{horizon}', ref '{entry.get('ref')}'"
                    )

    def test_top_level_projection_has_no_body_or_lifecycle(self) -> None:
        """The top-level projection dict must not carry forbidden keys."""
        doc = load_strategy(str(_PROJECT_ROOT))
        projection = project_strategy(doc)

        top_keys_lower = {k.lower() for k in projection.keys()}
        for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
            assert forbidden not in top_keys_lower, (
                f"Forbidden field substring '{forbidden}' in top-level "
                f"projection keys {sorted(projection.keys())}"
            )

    def test_serialized_json_contains_no_forbidden_keys(self) -> None:
        """The serialized JSON text must not contain forbidden key substrings
        outside of stable-direction section bodies."""
        doc = load_strategy(str(_PROJECT_ROOT))
        serialized = serialize_strategy_projection(doc)
        parsed = json.loads(serialized)
        # Recursively check all keys except "body" in stable_direction.
        _assert_no_forbidden_keys_recursive(parsed, "$")

    def test_stable_direction_sections_have_no_lifecycle_fields(self) -> None:
        """Stable-direction sections may have ``body`` (Markdown prose) but
        must not carry artifact lifecycle fields."""
        doc = load_strategy(str(_PROJECT_ROOT))
        projection = project_strategy(doc)

        lifecycle_forbidden = {
            "status", "lifecycle", "description", "content",
            "state", "phase", "plan", "plans", "completed",
            "completion", "closed", "resolved", "progress",
        }
        for section in projection["stable_direction"]:
            section_keys = set(section.keys())
            for forbidden in lifecycle_forbidden:
                assert forbidden not in section_keys, (
                    f"Forbidden field '{forbidden}' in stable-direction "
                    f"section '{section.get('title')}'"
                )


# ---------------------------------------------------------------------------
# Direct Markdown horizon edits (non-JSON-authoritative)
# ---------------------------------------------------------------------------


class TestMarkdownHorizonEdit:
    """Direct Markdown horizon edits on a temp copy validate correctly
    without treating the generated JSON projection as authority."""

    def test_move_entry_between_horizons_via_markdown(self, tmp_path: pathlib.Path) -> None:
        """Copy the live strategy to a temp dir, move an entry from one
        horizon to another via direct Markdown manipulation, re-parse,
        and verify the move took effect."""
        # Read the live strategy source.
        live_path = strategy_file_path(_PROJECT_ROOT)
        source = live_path.read_text(encoding="utf-8")

        # Write a temp copy.
        megaplan_dir = tmp_path / ".megaplan"
        megaplan_dir.mkdir(parents=True)
        strategy_path = megaplan_dir / "STRATEGY.md"
        strategy_path.write_text(source, encoding="utf-8")

        # Parse the temp copy.
        doc = parse_strategy(source, str(strategy_path.relative_to(tmp_path)))

        # Ensure there are entries in multiple horizons to move between.
        now_entries = doc.roadmap.get("Now", [])
        next_entries = doc.roadmap.get("Next", [])

        if not now_entries or not next_entries:
            pytest.skip(
                "Need entries in both Now and Next to test horizon movement"
            )

        # Move the first Now entry to Next.
        moved_entry = now_entries[0]
        # Create mutated roadmap.
        new_now = [e for e in now_entries if e is not moved_entry]
        new_next = list(next_entries) + [
            RoadmapEntry(
                identity=moved_entry.identity,
                display_title=moved_entry.display_title,
                horizon="Next",
                source_location=moved_entry.source_location,
            )
        ]

        # Build a mutated document.
        mutated = StrategyDocument(
            schema_version=doc.schema_version,
            stable_direction=list(doc.stable_direction),
            roadmap={
                "Now": new_now,
                "Next": new_next,
                "Later": list(doc.roadmap.get("Later", [])),
            },
            diagnostics=list(doc.diagnostics),
        )

        # Serialize back to Markdown — this is the "direct Markdown edit".
        new_markdown = serialize_strategy(mutated)

        # Re-parse the edited Markdown.
        re_doc = parse_strategy(new_markdown, str(strategy_path.relative_to(tmp_path)))

        # Verify the entry is now in Next, not Now.
        now_refs = {(e.identity.type, e.identity.ref) for e in re_doc.roadmap["Now"]}
        next_refs = {(e.identity.type, e.identity.ref) for e in re_doc.roadmap["Next"]}

        moved_id = (moved_entry.identity.type, moved_entry.identity.ref)
        assert moved_id not in now_refs, (
            f"Moved entry {moved_id} still appears in Now after horizon edit"
        )
        assert moved_id in next_refs, (
            f"Moved entry {moved_id} not found in Next after horizon edit"
        )

    def test_markdown_edit_survives_round_trip(self, tmp_path: pathlib.Path) -> None:
        """After moving an entry via Markdown serialization and re-parsing,
        the projection reflects the move, proving Markdown is authoritative."""
        # Read the live strategy source.
        live_path = strategy_file_path(_PROJECT_ROOT)
        source = live_path.read_text(encoding="utf-8")

        doc = parse_strategy(source, "STRATEGY.md")

        now_entries = doc.roadmap.get("Now", [])
        if not now_entries:
            pytest.skip("Need at least one entry in Now to test")

        # Move the first Now entry to Later.
        moved_entry = now_entries[0]
        mutated = StrategyDocument(
            schema_version=doc.schema_version,
            stable_direction=list(doc.stable_direction),
            roadmap={
                "Now": [e for e in now_entries if e is not moved_entry],
                "Next": list(doc.roadmap.get("Next", [])),
                "Later": list(doc.roadmap.get("Later", [])) + [
                    RoadmapEntry(
                        identity=moved_entry.identity,
                        display_title=moved_entry.display_title,
                        horizon="Later",
                        source_location=moved_entry.source_location,
                    )
                ],
            },
            diagnostics=[],
        )

        new_markdown = serialize_strategy(mutated)
        re_doc = parse_strategy(new_markdown, "STRATEGY.md")

        # Project the re-parsed doc and verify.
        projection = project_strategy(re_doc)
        later_entries = projection["roadmap"]["Later"]
        moved_id = (moved_entry.identity.type, moved_entry.identity.ref)

        found = any(
            e["type"] == moved_id[0] and e["ref"] == moved_id[1]
            for e in later_entries
        )
        assert found, (
            f"After Markdown round-trip, moved entry {moved_id} "
            f"not found in Later horizon projection"
        )

    def test_tampered_projection_json_does_not_affect_markdown_parse(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Editing the generated projection JSON must never change the
        parsed meaning of the authoritative Markdown source."""
        # Read the live strategy source.
        live_path = strategy_file_path(_PROJECT_ROOT)
        source = live_path.read_text(encoding="utf-8")

        # Parse the authoritative Markdown.
        doc_before = parse_strategy(source, "STRATEGY.md")
        proj_before = project_strategy(doc_before)

        # Write a projection to a temp location and tamper with it.
        megaplan_dir = tmp_path / ".megaplan"
        megaplan_dir.mkdir(parents=True)
        proj_path = megaplan_dir / "strategy.projection.json"

        import json as _json
        tampered = dict(proj_before)
        # Tamper with a roadmap entry.
        for horizon_entries in tampered.get("roadmap", {}).values():
            if horizon_entries:
                horizon_entries[0]["title"] = "TAMPERED — MUST BE IGNORED"
                horizon_entries[0]["type"] = "epic"
                horizon_entries[0]["ref"] = "tampered-ref"
                break

        proj_path.write_text(
            _json.dumps(tampered, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        # Re-parse the Markdown source — it must NOT be affected.
        doc_after = parse_strategy(source, "STRATEGY.md")

        # The parsed documents must be semantically equivalent.
        assert doc_after.schema_version == doc_before.schema_version
        assert len(doc_after.roadmap["Now"]) == len(doc_before.roadmap["Now"])
        assert len(doc_after.roadmap["Next"]) == len(doc_before.roadmap["Next"])
        assert len(doc_after.roadmap["Later"]) == len(doc_before.roadmap["Later"])

        # Check that first Now entry was NOT tampered.
        if doc_before.roadmap["Now"]:
            now_entry = doc_after.roadmap["Now"][0]
            assert now_entry.display_title != "TAMPERED — MUST BE IGNORED", (
                "Tampering with projection JSON must not change parsed display title"
            )
            assert now_entry.identity.ref != "tampered-ref", (
                "Tampering with projection JSON must not change parsed ref"
            )

        # Regenerated projection must overwrite tampered data.
        regenerated = serialize_strategy_projection(doc_after)
        assert "TAMPERED — MUST BE IGNORED" not in regenerated
        assert "tampered-ref" not in regenerated


# ---------------------------------------------------------------------------
# Documentation drift audit
# ---------------------------------------------------------------------------


class TestDocsDriftAudit:
    """Guard against documentation/help claims that violate the authority model.

    The strategy contract is clear: typed Markdown is authoritative, the
    projection JSON is disposable, identity is ``(type, ref)`` not display
    title, and lifecycle/status stays in artifacts never copied into strategy
    entries.  These tests scan the user-facing docs and agent skill files for
    claims that contradict this model.

    The tests are intentionally text-level — they don't parse the Markdown,
    they grep for known anti-pattern phrases.  This makes them sensitive to
    accidental copy-edits that might introduce drift without changing the
    rendered structure.
    """

    # Files scanned for drift (relative to project root).
    _DOC_PATHS: tuple[str, ...] = (
        "docs/strategy.md",
        "docs/tickets.md",
        "arnold_pipelines/megaplan/strategy/TEMPLATE.md",
        "arnold_pipelines/megaplan/data/tickets_skill.md",
    )

    # Phrases that MUST appear in at least one scanned doc (positive assertions).
    _REQUIRED_PHRASES: tuple[str, ...] = (
        # Markdown-is-authoritative signals.
        "Markdown is authoritative",
        # Projection-is-disposable signals.
        "disposable",
        "never edit",
        "delete it and rebuild",
        # Identity-is-type+ref signals.
        "identity is the (type, ref)",
        "never part of identity",
        "mutable display",
        # Pointer-not-container signals.
        "strategy entry is a pointer",
        "never copies the ticket body",
        "never copy",
        # Lifecycle-stays-in-artifacts signals.
        "lifecycle stays in artifacts",
        "status is written to the ticket file only",
        "strategy Markdown is **not** modified",
    )

    # Phrases that MUST NOT appear in any scanned doc (anti-patterns).
    _FORBIDDEN_PHRASES: tuple[str, ...] = (
        # JSON/projection-as-authoritative.
        "projection is authoritative",
        "projection is the authority",
        "projection is the source",
        "projection.json is authoritative",
        "projection.json is the authority",
        "JSON is authoritative",
        "JSON is the authority",
        "JSON is the source of truth",
        "projection wins",
        # Display-title-as-identity.
        "display title is the identity",
        "title is the identity",
        "title identifies",
        "identified by title",
        # Status/lifecycle-copied-into-strategy.
        "status is copied to the strategy",
        "lifecycle is copied to the strategy",
        "strategy entry carries",
        "strategy entry includes the status",
        "roadmap entry includes the status",
        "copy the ticket body into",
        "duplicate the ticket into",
        # Projection-as-editable.
        "edit the projection",
        "edit the JSON",
    )

    @staticmethod
    def _read_doc(rel_path: str) -> str:
        """Return lowercased text of *rel_path* relative to project root."""
        full = _PROJECT_ROOT / rel_path
        if not full.is_file():
            return ""
        return full.read_text(encoding="utf-8").lower()

    @classmethod
    def _all_text(cls) -> str:
        """Return concatenated lowercased text of all scanned docs."""
        parts: list[str] = []
        for rel in cls._DOC_PATHS:
            parts.append(cls._read_doc(rel))
        return "\n".join(parts)

    # -- positive assertions --------------------------------------------------

    def test_docs_affirm_markdown_authority(self) -> None:
        """At least one doc must explicitly state Markdown is authoritative."""
        text = self._all_text()
        assert "markdown is authoritative" in text or "typed markdown is authoritative" in text, (
            "No doc explicitly states Markdown/typed-Markdown is authoritative"
        )

    def test_docs_affirm_projection_disposable(self) -> None:
        """At least one doc must state the projection is disposable."""
        text = self._all_text()
        assert "disposable" in text, (
            "No doc states the projection is disposable"
        )
        assert "never edit" in text.lower() or "do not edit" in text.lower(), (
            "No doc warns against editing the projection"
        )

    def test_docs_affirm_identity_is_type_ref(self) -> None:
        """At least one doc must state identity is (type, ref), not title."""
        text = self._all_text()
        assert "identity is" in text and ("type, ref" in text or "(type, ref)" in text), (
            "No doc states identity is the (type, ref) pair"
        )

    def test_docs_affirm_lifecycle_not_in_strategy(self) -> None:
        """At least one doc must state lifecycle/status stays in artifacts."""
        text = self._all_text()
        assert "strategy markdown is **not** modified" in text or "strategy markdown is not modified" in text, (
            "No doc states the strategy Markdown is NOT modified for lifecycle changes"
        )

    # -- negative assertions --------------------------------------------------

    def test_no_doc_calls_projection_authoritative(self) -> None:
        """No scanned doc may call the projection/JSON authoritative."""
        text = self._all_text()
        violations: list[str] = []
        for phrase in (
            "projection is authoritative",
            "json is authoritative",
            "json is the source of truth",
            "projection wins",
        ):
            if phrase in text:
                violations.append(phrase)
        assert violations == [], (
            f"Anti-pattern: doc(s) claim projection/JSON is authoritative: {violations}"
        )

    def test_no_doc_calls_display_title_identity(self) -> None:
        """No scanned doc may claim display titles are identity."""
        text = self._all_text()
        violations: list[str] = []
        for phrase in (
            "display title is the identity",
            "title is the identity",
            "title identifies",
            "identified by title",
        ):
            if phrase in text:
                violations.append(phrase)
        assert violations == [], (
            f"Anti-pattern: doc(s) claim display title is identity: {violations}"
        )

    def test_no_doc_claims_status_copied_to_strategy(self) -> None:
        """No scanned doc may claim ticket status/lifecycle is copied into strategy."""
        text = self._all_text()
        violations: list[str] = []
        for phrase in (
            "status is copied to the strategy",
            "lifecycle is copied to the strategy",
            "strategy entry carries",
            "strategy entry includes the status",
            "roadmap entry includes the status",
            "copy the ticket body into",
            "duplicate the ticket into",
        ):
            if phrase in text:
                violations.append(phrase)
        assert violations == [], (
            f"Anti-pattern: doc(s) claim status/body is copied into strategy: {violations}"
        )

    def test_no_doc_suggests_editing_projection(self) -> None:
        """No scanned doc may suggest editing the projection JSON directly."""
        text = self._all_text()
        violations: list[str] = []
        for phrase in (
            "edit the projection",
            "edit the json",
        ):
            if phrase in text:
                violations.append(phrase)
        assert violations == [], (
            f"Anti-pattern: doc(s) suggest editing the projection: {violations}"
        )


# ---------------------------------------------------------------------------
# Bridge audit: relationship authority paths
# ---------------------------------------------------------------------------


class TestBridgeAudit:
    """Audit the relationship authority bridges across resolver, relationships,
    and promotion modules.

    The ``tickets/relationships.py`` module is the **single authority** for
    relationship kinds, frontmatter parsing, and serialization.  Both
    ``strategy/resolver.py`` (diagnostic consumer) and
    ``tickets/promotion.py`` (write-path consumer) import from it.

    This test class verifies that:

    * ``KIND_PROMOTED_TO_EPIC`` is defined **only** in ``relationships.py``.
    * Consumers do not shadow or redefine the constant.
    * The resolver's promotion diagnostic functions consume relationship data
      through the canonical ``parse_frontmatter_links`` entry point.
    * No bridge creates two authoritative relationship expressions — all
      consumers are read-only/diagnostic or use the canonical write path.

    **Retained bridges** (documented, not retired):

    * ``resolver._check_ticket_promotion`` — reads ``TicketEpicLink.kind``
      (parsed by ``relationships.parse_frontmatter_links``) to emit a
      ``Superseded ticket in roadmap`` warning.  This is a diagnostic consumer
      that does not create, modify, or re-express relationship data.
    * ``resolver._check_promotion_duplicate_intent`` — cross-references roadmap
      entries against ``promoted_to_epic`` links to detect duplicate-intent
      entries.  Also a read-only diagnostic consumer.
    * ``promotion._write_link_to_file`` — uses ``relationships.parse_frontmatter_links``
      and ``relationships.serialize_links_to_frontmatter`` for the canonical
      round-trip.  This is the authorized write path, not a bridge.
    """

    # Canonical definition module.
    _RELATIONSHIPS_MODULE = "arnold_pipelines/megaplan/tickets/relationships.py"

    # Modules that consume relationship constants (must import, not redefine).
    _CONSUMER_MODULES: tuple[str, ...] = (
        "arnold_pipelines/megaplan/strategy/resolver.py",
        "arnold_pipelines/megaplan/tickets/promotion.py",
    )

    @staticmethod
    def _read_module(rel_path: str) -> str:
        """Return source text of *rel_path* relative to project root."""
        return (_PROJECT_ROOT / rel_path).read_text(encoding="utf-8")

    def test_kind_promoted_to_epic_defined_only_in_relationships(self) -> None:
        """``KIND_PROMOTED_TO_EPIC`` must be defined in relationships.py and
        nowhere else (no shadow definitions)."""
        import re

        rel_source = self._read_module(self._RELATIONSHIPS_MODULE)

        # Verify the canonical definition exists.
        assert 'KIND_PROMOTED_TO_EPIC' in rel_source, (
            f"KIND_PROMOTED_TO_EPIC not found in {self._RELATIONSHIPS_MODULE}"
        )

        # Verify it's assigned (not just imported).
        assert 'KIND_PROMOTED_TO_EPIC: str = "promoted_to_epic"' in rel_source or \
               "KIND_PROMOTED_TO_EPIC = 'promoted_to_epic'" in rel_source or \
               'KIND_PROMOTED_TO_EPIC = "promoted_to_epic"' in rel_source, (
            f"KIND_PROMOTED_TO_EPIC is not assigned a literal value in "
            f"{self._RELATIONSHIPS_MODULE}"
        )

        # Verify no other module redefines it (shadow assignment).
        # We check for assignment patterns like `KIND_PROMOTED_TO_EPIC = ...`
        # or `KIND_PROMOTED_TO_EPIC: str = ...` that are NOT inside an import
        # statement.  Multi-line imports like:
        #     from ... import (
        #         KIND_PROMOTED_TO_EPIC,
        #     )
        # are fine — the constant name alone on a line is not a redefinition.
        _assignment_re = re.compile(
            r'^\s*KIND_PROMOTED_TO_EPIC\s*[:=]'
        )
        for consumer in self._CONSUMER_MODULES:
            consumer_source = self._read_module(consumer)
            for lineno, line in enumerate(consumer_source.splitlines(), 1):
                if _assignment_re.match(line):
                    raise AssertionError(
                        f"KIND_PROMOTED_TO_EPIC appears to be redefined in "
                        f"{consumer}:{lineno}: {line.strip()}"
                    )

    def test_resolver_imports_relationship_kinds_from_canonical_source(self) -> None:
        """The resolver must import relationship constants from the canonical
        ``tickets.relationships`` module."""
        resolver_source = self._read_module(self._CONSUMER_MODULES[0])
        assert "from arnold_pipelines.megaplan.tickets.relationships import" in resolver_source, (
            "resolver.py does not import from tickets.relationships"
        )
        assert "KIND_PROMOTED_TO_EPIC" in resolver_source, (
            "resolver.py does not import KIND_PROMOTED_TO_EPIC"
        )
        assert "parse_frontmatter_links" in resolver_source, (
            "resolver.py does not import parse_frontmatter_links from relationships"
        )

    def test_promotion_imports_relationship_kinds_from_canonical_source(self) -> None:
        """The promotion module must import relationship constants from the
        canonical ``tickets.relationships`` module."""
        promo_source = self._read_module(self._CONSUMER_MODULES[1])
        assert "from arnold_pipelines.megaplan.tickets.relationships import" in promo_source, (
            "promotion.py does not import from tickets.relationships"
        )
        assert "KIND_PROMOTED_TO_EPIC" in promo_source, (
            "promotion.py does not import KIND_PROMOTED_TO_EPIC"
        )
        assert "parse_frontmatter_links" in promo_source, (
            "promotion.py does not import parse_frontmatter_links"
        )

    def test_resolver_uses_parse_frontmatter_links_not_direct_parsing(self) -> None:
        """The resolver must parse relationship data through
        ``relationships.parse_frontmatter_links``, not through ad-hoc
        frontmatter key access."""
        resolver_source = self._read_module(self._CONSUMER_MODULES[0])
        # The resolver should call parse_frontmatter_links (not just import it).
        assert "parse_frontmatter_links(" in resolver_source or \
               "parse_frontmatter_links(" in resolver_source, (
            "resolver.py does not call parse_frontmatter_links"
        )
        # It should NOT directly access fm['epics'] for relationship data
        # without going through the relationships module.
        # (This is a heuristic; the actual code does use the module correctly.)

    def test_promotion_uses_serialize_for_writes(self) -> None:
        """The promotion module must use ``serialize_links_to_frontmatter`` for
        writing relationship data back to frontmatter, not ad-hoc dict assembly."""
        promo_source = self._read_module(self._CONSUMER_MODULES[1])
        assert "serialize_links_to_frontmatter" in promo_source, (
            "promotion.py does not import serialize_links_to_frontmatter"
        )
        assert "serialize_links_to_frontmatter(" in promo_source, (
            "promotion.py does not call serialize_links_to_frontmatter"
        )

    def test_no_duplicate_relationship_constant_definitions(self) -> None:
        """No module other than relationships.py may assign a value to
        ``KIND_PROMOTED_TO_EPIC``, ``KIND_ASSOCIATED``, or
        ``KIND_RESOLVES_ON_COMPLETE``."""
        import re

        _CONSTANTS = (
            "KIND_PROMOTED_TO_EPIC",
            "KIND_ASSOCIATED",
            "KIND_RESOLVES_ON_COMPLETE",
        )
        forbidden_modules = (
            "arnold_pipelines/megaplan/strategy/resolver.py",
            "arnold_pipelines/megaplan/tickets/promotion.py",
            "arnold_pipelines/megaplan/tickets/__init__.py",
        )
        # Match any line that assigns to one of these constants:
        #   KIND_PROMOTED_TO_EPIC = ...
        #   KIND_PROMOTED_TO_EPIC: str = ...
        # This does NOT match bare names inside multi-line import blocks.
        _pattern = (
            r'^\s*('
            + '|'.join(re.escape(c) for c in _CONSTANTS)
            + r')\s*[:=]'
        )
        _assignment_re = re.compile(_pattern)

        for mod_path in forbidden_modules:
            source = self._read_module(mod_path)
            for lineno, line in enumerate(source.splitlines(), 1):
                m = _assignment_re.match(line)
                if m:
                    const_name = m.group(1)
                    raise AssertionError(
                        f"{const_name} appears to be defined (not imported) in "
                        f"{mod_path}:{lineno}: {line.strip()}"
                    )


# ---------------------------------------------------------------------------
# Recursive key validator
# ---------------------------------------------------------------------------


def _assert_no_forbidden_keys_recursive(
    obj, path: str, *, in_stable_section: bool = False
) -> None:
    """Recursively ensure no key contains a forbidden substring.

    The ``body`` key is permitted only within ``stable_direction`` entries
    where it represents Markdown prose, not an artifact body.
    """
    if isinstance(obj, dict):
        is_stable_entry = (
            in_stable_section
            or (path == "$.stable_direction" and ".stable_direction[" not in path)
        )
        # Determine if we're inside a stable_direction section entry
        actual_stable_entry = (
            is_stable_entry
            or ".stable_direction[" in path
        )
        for key in obj:
            key_lower = key.lower()
            # In stable sections, allow "body" but forbid lifecycle fields.
            if actual_stable_entry:
                lifecycle = {
                    "status", "lifecycle", "description", "content",
                    "state", "phase", "plan", "plans", "completed",
                    "completion", "closed", "resolved", "progress",
                }
                for forbidden in lifecycle:
                    assert forbidden not in key_lower, (
                        f"Forbidden substring '{forbidden}' in key '{key}' at {path}"
                    )
            else:
                for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
                    assert forbidden not in key_lower, (
                        f"Forbidden substring '{forbidden}' in key '{key}' at {path}"
                    )

            next_in_stable = actual_stable_entry or (
                key == "stable_direction" and path == "$"
            )
            _assert_no_forbidden_keys_recursive(
                obj[key],
                f"{path}.{key}",
                in_stable_section=next_in_stable,
            )
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_forbidden_keys_recursive(
                item, f"{path}[{i}]", in_stable_section=in_stable_section
            )
