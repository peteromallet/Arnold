"""Projection tests for the v1 strategy document.

These tests prove that:

* ``project_strategy`` and ``serialize_strategy_projection`` produce
  byte-for-byte deterministic output given the same parsed document.
* The projection never leaks ticket/epic bodies or lifecycle-status fields.
* The golden JSON fixture on disk matches the current projector output
  exactly, byte-for-byte.
* The ``write_strategy_projection`` helper correctly writes and can
  round-trip through the projector.
* Editing only ``.megaplan/strategy.projection.json`` cannot change the
  parsed meaning of the canonical Markdown source (non-authoritative).
* Diagnostics from parsing and validation are faithfully represented
  in the projection, including source locations.
"""

from __future__ import annotations

import json
import pathlib
import textwrap

import pytest

from arnold_pipelines.megaplan.strategy.contract import (
    PROJECTION_SCHEMA_VERSION,
    REQUIRED_ROADMAP_SECTIONS,
    REQUIRED_STABLE_SECTIONS,
    SCHEMA_VERSION,
    RoadmapEntry,
    SourceLocation,
    StrategyDiagnostic,
    StrategyDocument,
    StrategyIdentity,
    StrategySection,
)
from arnold_pipelines.megaplan.strategy.parser import parse_strategy
from arnold_pipelines.megaplan.strategy.projection import (
    project_strategy,
    serialize_strategy_projection,
    write_strategy_projection,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    item_type: str,
    ref: str,
    display_title: str,
    horizon: str,
    *,
    path: str = "test.md",
    line: int = 42,
) -> RoadmapEntry:
    """Factory for a bare :class:`RoadmapEntry` with a fixed source location."""
    return RoadmapEntry(
        identity=StrategyIdentity(type=item_type, ref=ref),  # type: ignore[arg-type]
        display_title=display_title,
        horizon=horizon,  # type: ignore[arg-type]
        source_location=SourceLocation(path=path, line=line, column=1),
    )


def _make_section(
    title: str,
    body: str,
    *,
    path: str = "test.md",
    line: int = 1,
) -> StrategySection:
    """Factory for a :class:`StrategySection`."""
    return StrategySection(
        title=title,
        body=body,
        source_location=SourceLocation(path=path, line=line, column=1),
    )


def _make_doc(
    *,
    roadmap: dict | None = None,
    stable_direction: list[StrategySection] | None = None,
    diagnostics: list[StrategyDiagnostic] | None = None,
    schema_version: str = SCHEMA_VERSION,
) -> StrategyDocument:
    """Factory for a minimal :class:`StrategyDocument`."""
    if roadmap is None:
        roadmap = {h: [] for h in REQUIRED_ROADMAP_SECTIONS}
    return StrategyDocument(
        schema_version=schema_version,
        stable_direction=stable_direction if stable_direction is not None else [],
        roadmap=roadmap,
        diagnostics=diagnostics if diagnostics is not None else [],
    )


def _golden_source() -> str:
    """Return the canonical golden strategy v1 Markdown source."""
    golden_path = pathlib.Path(__file__).parent / "golden" / "strategy_v1.md"
    return golden_path.read_text()


def _golden_projection_json() -> str:
    """Return the expected golden projection JSON (byte-for-byte)."""
    golden_path = pathlib.Path(__file__).parent / "golden" / "strategy_v1_projection.json"
    return golden_path.read_text()


# Forbidden field substrings — these must never appear in projection output
# *except* in stable-direction sections where "body" is the Markdown prose body
# (not an artifact body).
_FORBIDDEN_FIELD_SUBSTRINGS: tuple[str, ...] = (
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

# The subset of forbidden substrings that apply to stable-direction sections.
# "body" is intentionally excluded here — stable-direction sections carry
# Markdown prose in their "body" field, not artifact bodies.
_STABLE_SECTION_FORBIDDEN: tuple[str, ...] = (
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


# ---------------------------------------------------------------------------
# Byte-for-byte rebuild determinism
# ---------------------------------------------------------------------------


class TestProjectionDeterminism:
    """``serialize_strategy_projection`` produces byte-for-byte identical output."""

    def test_ten_round_trips_produce_identical_output(self) -> None:
        """Projecting the same parsed document 10 times gives the same bytes."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        outputs = {serialize_strategy_projection(doc) for _ in range(10)}
        assert len(outputs) == 1, (
            f"Non-deterministic! Got {len(outputs)} distinct outputs "
            f"across 10 projections."
        )

    def test_separate_parse_calls_with_same_source_deterministic(self) -> None:
        """Different parse() -> project() cycles produce the same bytes."""
        source = _golden_source()
        results = set()
        for _ in range(5):
            doc = parse_strategy(source, "strategy.md")
            results.add(serialize_strategy_projection(doc))
        assert len(results) == 1, (
            f"Expected 1 unique output across 5 parse+project cycles, "
            f"got {len(results)}"
        )

    def test_minimal_document_is_deterministic(self) -> None:
        """Even a minimal empty document must produce deterministic output."""
        doc = _make_doc()
        results = {serialize_strategy_projection(doc) for _ in range(10)}
        assert len(results) == 1

    def test_serialize_strategy_projection_terminates_with_newline(self) -> None:
        """The serialized projection always ends with a single newline."""
        doc = _make_doc()
        output = serialize_strategy_projection(doc)
        assert output.endswith("\n"), "Projection must end with a newline"
        assert not output.endswith("\n\n"), "Projection must end with exactly one newline"

    def test_project_strategy_dict_is_json_serializable(self) -> None:
        """``project_strategy`` output can be passed directly to ``json.dumps``."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        projection = project_strategy(doc)
        # Should not raise
        serialized = json.dumps(projection, indent=2, sort_keys=True, ensure_ascii=False)
        assert isinstance(serialized, str)
        assert len(serialized) > 0


# ---------------------------------------------------------------------------
# Golden output: byte-for-byte match with committed fixture
# ---------------------------------------------------------------------------


class TestProjectionGoldenOutput:
    """The golden JSON fixture on disk must match the projector output exactly."""

    def test_golden_projection_file_exists_and_is_valid_json(self) -> None:
        """The golden projection fixture is valid JSON."""
        raw = _golden_projection_json()
        parsed = json.loads(raw)
        assert parsed["schema_version"] == PROJECTION_SCHEMA_VERSION

    def test_golden_projection_matches_projector_byte_for_byte(self) -> None:
        """The projector output must match the committed golden JSON exactly."""
        # Use a consistent relative path so the golden file is portable.
        # The golden JSON fixture stores "tests/arnold_pipelines/megaplan/golden/strategy_v1.md".
        golden_relative_path = (
            "tests/arnold_pipelines/megaplan/golden/strategy_v1.md"
        )
        doc_from_disk = parse_strategy(_golden_source(), golden_relative_path)
        actual = serialize_strategy_projection(doc_from_disk)
        expected = _golden_projection_json()
        assert actual == expected, (
            "Projector output does not match golden JSON.\n"
            f"Expected length: {len(expected)}, got: {len(actual)}\n"
            "If the projector logic changed intentionally, regenerate the golden file."
        )

    def test_golden_projection_is_valid_utf8(self) -> None:
        """The golden projection must be valid UTF-8."""
        raw = _golden_projection_json()
        raw.encode("utf-8")  # should not raise

    def test_golden_projection_has_no_trailing_whitespace(self) -> None:
        """The golden projection must not have trailing whitespace on any line."""
        raw = _golden_projection_json()
        for i, line in enumerate(raw.split("\n"), start=1):
            assert line == line.rstrip(), (
                f"Line {i} has trailing whitespace: {line!r}"
            )


# ---------------------------------------------------------------------------
# No artifact body or lifecycle-status fields in projection
# ---------------------------------------------------------------------------


class TestProjectionNoBodyOrLifecycle:
    """The projection must never contain ticket/epic body or lifecycle fields."""

    def test_roadmap_entries_have_no_body_or_lifecycle_fields(self) -> None:
        """Every roadmap entry in the projection must be clean of forbidden fields."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        projection = project_strategy(doc)
        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                entry_keys_lower = {k.lower() for k in entry.keys()}
                for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
                    assert forbidden not in entry_keys_lower, (
                        f"Forbidden field substring '{forbidden}' found in "
                        f"roadmap entry keys {sorted(entry.keys())} "
                        f"for horizon '{horizon}', entry ref '{entry.get('ref')}'"
                    )

    def test_stable_direction_sections_have_no_lifecycle_fields(self) -> None:
        """Stable-direction sections must not carry artifact lifecycle fields.

        The ``body`` field on stable-direction sections is the Markdown prose
        body, NOT an artifact body — it is intentionally present.  But no
        lifecycle-oriented fields (status, state, phase, etc.) may appear.
        """
        doc = parse_strategy(_golden_source(), "strategy.md")
        projection = project_strategy(doc)
        for section in projection["stable_direction"]:
            section_keys = set(section.keys())
            for forbidden in _STABLE_SECTION_FORBIDDEN:
                assert forbidden not in section_keys, (
                    f"Forbidden field '{forbidden}' found in stable-direction "
                    f"section '{section.get('title')}'"
                )

    def test_top_level_projection_has_no_body_or_lifecycle(self) -> None:
        """The top-level projection dict must not carry forbidden keys."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        projection = project_strategy(doc)
        top_keys_lower = {k.lower() for k in projection.keys()}
        for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
            assert forbidden not in top_keys_lower, (
                f"Forbidden field substring '{forbidden}' found in "
                f"top-level projection keys {sorted(projection.keys())}"
            )

    def test_validation_summary_has_no_body_or_lifecycle(self) -> None:
        """The validation_summary block must not leak body or lifecycle data."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="error",
                message="Test error",
                source_location=SourceLocation(path="x.md", line=1, column=1),
            )
        ])
        projection = project_strategy(doc)
        summary = projection["validation_summary"]
        summary_keys_lower = {k.lower() for k in summary.keys()}
        for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
            assert forbidden not in summary_keys_lower, (
                f"Forbidden field '{forbidden}' in validation_summary keys"
            )

    def test_diagnostics_list_has_no_body_or_lifecycle(self) -> None:
        """Each diagnostic entry must not leak body/lifecycle data."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="error",
                message="Missing reference",
                source_location=SourceLocation(path="x.md", line=1, column=1),
            )
        ])
        projection = project_strategy(doc)
        for diag in projection["diagnostics"]:
            diag_keys_lower = {k.lower() for k in diag.keys()}
            for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
                assert forbidden not in diag_keys_lower, (
                    f"Forbidden field '{forbidden}' in diagnostic entry"
                )

    def test_serialized_json_contains_no_forbidden_keys(self) -> None:
        """``serialize_strategy_projection`` text must not contain forbidden keys."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        serialized = serialize_strategy_projection(doc)
        parsed = json.loads(serialized)
        # Recursively check all keys at all levels.
        # The "body" key is allowed only in stable_direction sections
        # (it's Markdown prose, not artifact body).
        self._assert_no_forbidden_keys(parsed, path="$", in_stable_section=False)

    @staticmethod
    def _assert_no_forbidden_keys(
        obj, path: str, *, in_stable_section: bool = False
    ) -> None:
        """Recursively ensure no key contains a forbidden substring.

        The ``body`` key is permitted only within ``stable_direction`` entries
        where it represents Markdown prose, not an artifact body.
        """
        if isinstance(obj, dict):
            # Determine if we're inside a stable_direction section entry
            is_stable_entry = path.endswith("]") and ".stable_direction[" in path
            for key in obj:
                key_lower = key.lower()
                forbidden_list = _STABLE_SECTION_FORBIDDEN if is_stable_entry else _FORBIDDEN_FIELD_SUBSTRINGS
                for forbidden in forbidden_list:
                    assert forbidden not in key_lower, (
                        f"Forbidden substring '{forbidden}' in key '{key}' at {path}"
                    )
                next_in_stable = (
                    is_stable_entry
                    or (key == "stable_direction" and path == "$")
                )
                TestProjectionNoBodyOrLifecycle._assert_no_forbidden_keys(
                    obj[key],
                    f"{path}.{key}",
                    in_stable_section=next_in_stable,
                )
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                TestProjectionNoBodyOrLifecycle._assert_no_forbidden_keys(
                    item, f"{path}[{i}]", in_stable_section=in_stable_section
                )


# ---------------------------------------------------------------------------
# Write helper: round-trip and filesystem behavior
# ---------------------------------------------------------------------------


class TestProjectionWriteHelper:
    """``write_strategy_projection`` correctly persists the projection."""

    def test_write_creates_file(self, tmp_path: pathlib.Path) -> None:
        """Writing a projection creates the file at the expected path."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        output_path = write_strategy_projection(doc, str(tmp_path))
        assert output_path.exists()
        expected = tmp_path / ".megaplan" / "strategy.projection.json"
        assert output_path == expected

    def test_write_output_matches_serialize_strategy_projection(self, tmp_path: pathlib.Path) -> None:
        """The written file content matches ``serialize_strategy_projection`` exactly."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        expected_bytes = serialize_strategy_projection(doc)
        output_path = write_strategy_projection(doc, str(tmp_path))
        actual = output_path.read_text()
        assert actual == expected_bytes

    def test_write_creates_parent_directories(self, tmp_path: pathlib.Path) -> None:
        """``write_strategy_projection`` creates `.megaplan/` if needed."""
        # Ensure the .megaplan directory does not exist yet
        megaplan_dir = tmp_path / ".megaplan"
        assert not megaplan_dir.exists()
        doc = _make_doc()
        write_strategy_projection(doc, str(tmp_path))
        assert megaplan_dir.is_dir()

    def test_write_overwrites_existing_file(self, tmp_path: pathlib.Path) -> None:
        """Writing twice overwrites the existing file."""
        doc1 = parse_strategy(_golden_source(), "strategy.md")
        write_strategy_projection(doc1, str(tmp_path))

        # Write a different document
        doc2 = _make_doc(
            diagnostics=[
                StrategyDiagnostic(
                    level="error",
                    message="New error",
                    source_location=SourceLocation(path="e.md", line=1, column=1),
                )
            ]
        )
        write_strategy_projection(doc2, str(tmp_path))

        actual = (tmp_path / ".megaplan" / "strategy.projection.json").read_text()
        expected = serialize_strategy_projection(doc2)
        assert actual == expected

    def test_write_round_trip_via_read_and_parse(self, tmp_path: pathlib.Path) -> None:
        """Write projection, read it back, verify it's valid JSON with correct schema."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        output_path = write_strategy_projection(doc, str(tmp_path))
        raw = output_path.read_text()
        parsed = json.loads(raw)
        assert parsed["schema_version"] == PROJECTION_SCHEMA_VERSION
        assert parsed["source_version"] == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Non-authoritative: editing the projection cannot change parsed strategy
# ---------------------------------------------------------------------------


class TestProjectionNonAuthoritative:
    """The projection is disposable — editing it cannot alter parsed meaning."""

    def test_editing_projection_json_does_not_change_parser_output(self, tmp_path: pathlib.Path) -> None:
        """Parsing the canonical Markdown gives the same result regardless of
        what is in ``strategy.projection.json``."""
        source = _golden_source()
        doc_before = parse_strategy(source, "strategy.md")

        # Write a projection to the expected path
        write_strategy_projection(doc_before, str(tmp_path))

        # Now tamper with the projection JSON — change a roadmap entry title
        proj_path = tmp_path / ".megaplan" / "strategy.projection.json"
        tampered = json.loads(proj_path.read_text())
        tampered["roadmap"]["Now"][0]["title"] = "TAMPERED TITLE — SHOULD BE IGNORED"
        tampered["roadmap"]["Now"][0]["type"] = "epic"  # should also be ignored
        tampered["schema_version"] = "megaplan-strategy-projection-v99"
        proj_path.write_text(json.dumps(tampered, indent=2, sort_keys=True) + "\n")

        # Re-parse the Markdown source — it must NOT be affected
        doc_after = parse_strategy(source, "strategy.md")

        # The parsed document must be identical to before
        assert doc_after.schema_version == doc_before.schema_version
        assert len(doc_after.roadmap["Now"]) == len(doc_before.roadmap["Now"])
        now_entry = doc_after.roadmap["Now"][0]
        assert now_entry.identity.type == "ticket", (
            f"Tampering with projection JSON must not change parsed type; "
            f"got '{now_entry.identity.type}'"
        )
        assert now_entry.display_title != "TAMPERED TITLE — SHOULD BE IGNORED", (
            "Tampering with projection JSON must not change parsed display title"
        )

        # The projection itself, when regenerated, should overwrite the tampered file
        regenerated = serialize_strategy_projection(doc_after)
        assert "TAMPERED TITLE" not in regenerated
        assert "megaplan-strategy-projection-v99" not in regenerated

    def test_parser_never_reads_projection_json(self) -> None:
        """The parser module must never reference ``strategy.projection.json``."""
        import inspect
        from arnold_pipelines.megaplan.strategy import parser as parser_mod
        source_code = inspect.getsource(parser_mod)
        assert "strategy.projection.json" not in source_code, (
            "Parser source must not reference strategy.projection.json — "
            "the projection is never read as authority."
        )
        assert "strategy_projection" not in source_code, (
            "Parser source must not reference strategy_projection — "
            "the projection is never read as authority."
        )

    def test_contract_module_never_reads_projection_json(self) -> None:
        """The contract module must never reference ``strategy.projection.json``."""
        import inspect
        from arnold_pipelines.megaplan.strategy import contract as contract_mod
        source_code = inspect.getsource(contract_mod)
        assert "strategy.projection.json" not in source_code, (
            "Contract module must not reference strategy.projection.json"
        )

    def test_resolver_never_reads_projection_json(self) -> None:
        """The resolver module must never *read* projection as input authority.

        Docstrings may mention ``strategy.projection.json`` to explain that it
        is NOT read, but the resolver must never import from the projection
        module or open the projection file.
        """
        import inspect
        from arnold_pipelines.megaplan.strategy import resolver as resolver_mod
        source_code = inspect.getsource(resolver_mod)

        # The resolver must not import the projection module.
        assert "from .projection import" not in source_code, (
            "Resolver must not import from projection module"
        )
        assert "from arnold_pipelines.megaplan.strategy.projection import" not in source_code, (
            "Resolver must not import from projection module"
        )
        # The resolver must not open/read the projection file path.
        assert "STRATEGY_PROJECTION_PATH" not in source_code, (
            "Resolver must not reference STRATEGY_PROJECTION_PATH"
        )

    def test_deleting_projection_json_does_not_affect_parser(self, tmp_path: pathlib.Path) -> None:
        """Even if the projection file is absent, the parser works identically."""
        source = _golden_source()
        doc_with_proj = parse_strategy(source, "strategy.md")

        # Write and then delete the projection
        write_strategy_projection(doc_with_proj, str(tmp_path))
        proj_path = tmp_path / ".megaplan" / "strategy.projection.json"
        proj_path.unlink()

        doc_without_proj = parse_strategy(source, "strategy.md")
        assert doc_without_proj.schema_version == doc_with_proj.schema_version
        assert (
            len(doc_without_proj.roadmap["Now"])
            == len(doc_with_proj.roadmap["Now"])
        )
        assert doc_without_proj.diagnostics == doc_with_proj.diagnostics


# ---------------------------------------------------------------------------
# Projection with diagnostics
# ---------------------------------------------------------------------------


class TestProjectionWithDiagnostics:
    """Diagnostics from parsing and validation are faithfully projected."""

    def test_clean_document_has_empty_diagnostics_and_clean_summary(self) -> None:
        """A clean document projects with empty diagnostics and clean=True."""
        doc = _make_doc()
        projection = project_strategy(doc)
        assert projection["diagnostics"] == []
        assert projection["validation_summary"]["error_count"] == 0
        assert projection["validation_summary"]["warning_count"] == 0
        assert projection["validation_summary"]["total_diagnostics"] == 0
        assert projection["validation_summary"]["clean"] is True

    def test_error_diagnostics_are_projected_with_source(self) -> None:
        """Error diagnostics appear with level, message, and source location."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="error",
                message="Missing reference: ticket ABC",
                source_location=SourceLocation(path="test.md", line=42, column=3),
            )
        ])
        projection = project_strategy(doc)
        assert len(projection["diagnostics"]) == 1
        diag = projection["diagnostics"][0]
        assert diag["level"] == "error"
        assert diag["message"] == "Missing reference: ticket ABC"
        assert diag["source"] == {"path": "test.md", "line": 42, "column": 3}
        assert projection["validation_summary"]["error_count"] == 1
        assert projection["validation_summary"]["warning_count"] == 0
        assert projection["validation_summary"]["total_diagnostics"] == 1
        assert projection["validation_summary"]["clean"] is False

    def test_warning_diagnostics_are_projected_with_source(self) -> None:
        """Warning diagnostics appear with level, message, and source location."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="warning",
                message="Stale display title for ticket ABC",
                source_location=SourceLocation(path="test.md", line=99, column=1),
            )
        ])
        projection = project_strategy(doc)
        assert len(projection["diagnostics"]) == 1
        diag = projection["diagnostics"][0]
        assert diag["level"] == "warning"
        assert diag["message"] == "Stale display title for ticket ABC"
        assert diag["source"] == {"path": "test.md", "line": 99, "column": 1}
        assert projection["validation_summary"]["error_count"] == 0
        assert projection["validation_summary"]["warning_count"] == 1
        assert projection["validation_summary"]["total_diagnostics"] == 1
        assert projection["validation_summary"]["clean"] is False

    def test_diagnostic_without_source_location_has_null_source(self) -> None:
        """A diagnostic with no source location projects ``source: null``."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="error",
                message="File not found: .megaplan/STRATEGY.md",
                source_location=None,
            )
        ])
        projection = project_strategy(doc)
        diag = projection["diagnostics"][0]
        assert diag["source"] is None

    def test_mixed_errors_and_warnings(self) -> None:
        """Mixed diagnostics are counted correctly by severity."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="error",
                message="Error 1",
                source_location=SourceLocation(path="a.md", line=1, column=1),
            ),
            StrategyDiagnostic(
                level="error",
                message="Error 2",
                source_location=SourceLocation(path="b.md", line=2, column=1),
            ),
            StrategyDiagnostic(
                level="warning",
                message="Warning 1",
                source_location=SourceLocation(path="c.md", line=3, column=1),
            ),
        ])
        projection = project_strategy(doc)
        assert projection["validation_summary"]["error_count"] == 2
        assert projection["validation_summary"]["warning_count"] == 1
        assert projection["validation_summary"]["total_diagnostics"] == 3
        assert projection["validation_summary"]["clean"] is False
        assert len(projection["diagnostics"]) == 3

    def test_malformed_source_diagnostics_are_projected(self) -> None:
        """Parsing a malformed Markdown produces diagnostics in the projection."""
        source = textwrap.dedent("""\
        ---
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

        - [story:STORY-1] Unsupported type

        ## Next

        ## Later
        """)
        doc = parse_strategy(source, "test.md")
        projection = project_strategy(doc)
        # Should have at least one diagnostic about unsupported type
        assert len(projection["diagnostics"]) >= 1
        assert projection["validation_summary"]["clean"] is False
        # Verify the diagnostic has the right shape
        for diag in projection["diagnostics"]:
            assert "level" in diag
            assert "message" in diag
            assert "source" in diag


# ---------------------------------------------------------------------------
# Projection structural invariants
# ---------------------------------------------------------------------------


class TestProjectionStructureInvariants:
    """The projection JSON has a stable structure that tooling can rely on."""

    def test_top_level_keys_are_exactly_expected(self) -> None:
        """The top-level projection dict has exactly the documented keys."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        projection = project_strategy(doc)
        expected_keys = {
            "schema_version",
            "source_version",
            "stable_direction",
            "roadmap",
            "diagnostics",
            "validation_summary",
        }
        assert set(projection.keys()) == expected_keys, (
            f"Top-level keys {sorted(projection.keys())} != {sorted(expected_keys)}"
        )

    def test_schema_version_is_projection_schema(self) -> None:
        """The projection declares its own schema version."""
        doc = _make_doc()
        projection = project_strategy(doc)
        assert projection["schema_version"] == PROJECTION_SCHEMA_VERSION

    def test_source_version_is_source_document_version(self) -> None:
        """The projection declares the source document schema version."""
        doc = _make_doc(schema_version=SCHEMA_VERSION)
        projection = project_strategy(doc)
        assert projection["source_version"] == SCHEMA_VERSION

    def test_roadmap_has_all_required_horizons(self) -> None:
        """The projection roadmap always has Now, Next, and Later keys."""
        doc = _make_doc()
        projection = project_strategy(doc)
        assert set(projection["roadmap"].keys()) == set(REQUIRED_ROADMAP_SECTIONS)

    def test_roadmap_horizons_are_ordered(self) -> None:
        """Roadmap horizons appear in Now, Next, Later order.

        The projection dict preserves insertion order (Python 3.7+).
        The serialized JSON with ``sort_keys=True`` will have keys in
        alphabetical order (Later, Next, Now), but the *values* for each
        horizon still contain the correct horizon label.
        """
        doc = parse_strategy(_golden_source(), "strategy.md")
        projection = project_strategy(doc)
        horizon_keys = list(projection["roadmap"].keys())
        assert horizon_keys == list(REQUIRED_ROADMAP_SECTIONS), (
            f"Roadmap horizon order {horizon_keys} != {list(REQUIRED_ROADMAP_SECTIONS)}"
        )
        # Verify serialized output contains all three horizons
        serialized = serialize_strategy_projection(doc)
        parsed = json.loads(serialized)
        assert set(parsed["roadmap"].keys()) == set(REQUIRED_ROADMAP_SECTIONS), (
            "Serialized projection must contain all three roadmap horizons"
        )

    def test_roadmap_entry_has_all_required_fields(self) -> None:
        """Each roadmap entry has type, ref, title, horizon, and source."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        projection = project_strategy(doc)
        required_entry_keys = {"type", "ref", "title", "horizon", "source"}
        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                assert set(entry.keys()) == required_entry_keys, (
                    f"Roadmap entry keys {sorted(entry.keys())} != "
                    f"{sorted(required_entry_keys)} in horizon '{horizon}'"
                )

    def test_roadmap_entry_source_has_path_line_column(self) -> None:
        """Each roadmap entry source has path, line, and column."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        projection = project_strategy(doc)
        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                source = entry["source"]
                assert set(source.keys()) == {"path", "line", "column"}
                assert isinstance(source["line"], int)
                assert isinstance(source["column"], int)
                assert source["line"] >= 1
                assert source["column"] >= 1

    def test_stable_direction_section_has_title_body_source(self) -> None:
        """Each stable-direction section has title, body, and source."""
        doc = parse_strategy(_golden_source(), "strategy.md")
        projection = project_strategy(doc)
        required_keys = {"title", "body", "source"}
        for section in projection["stable_direction"]:
            assert set(section.keys()) == required_keys, (
                f"Section keys {sorted(section.keys())} != {sorted(required_keys)}"
            )
            assert isinstance(section["body"], str)

    def test_validation_summary_has_expected_keys(self) -> None:
        """Validation summary has error_count, warning_count, total_diagnostics, clean."""
        doc = _make_doc()
        projection = project_strategy(doc)
        expected_keys = {"error_count", "warning_count", "total_diagnostics", "clean"}
        assert set(projection["validation_summary"].keys()) == expected_keys

    def test_clean_flag_is_true_only_when_no_diagnostics(self) -> None:
        """``clean`` is True iff total_diagnostics == 0."""
        # Clean case
        doc_clean = _make_doc()
        proj_clean = project_strategy(doc_clean)
        assert proj_clean["validation_summary"]["clean"] is True

        # Dirty case
        doc_dirty = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="error",
                message="Error",
                source_location=SourceLocation(path="x.md", line=1, column=1),
            )
        ])
        proj_dirty = project_strategy(doc_dirty)
        assert proj_dirty["validation_summary"]["clean"] is False

    def test_diagnostic_level_is_always_error_or_warning(self) -> None:
        """Every projected diagnostic has level 'error' or 'warning'."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="error",
                message="Err",
                source_location=SourceLocation(path="a.md", line=1, column=1),
            ),
            StrategyDiagnostic(
                level="warning",
                message="Warn",
                source_location=SourceLocation(path="b.md", line=2, column=1),
            ),
        ])
        projection = project_strategy(doc)
        for diag in projection["diagnostics"]:
            assert diag["level"] in ("error", "warning"), (
                f"Unexpected diagnostic level: {diag['level']}"
            )


# ---------------------------------------------------------------------------
# Projection with lifecycle diagnostics
# ---------------------------------------------------------------------------


class TestProjectionLifecycleDiagnostics:
    """Lifecycle diagnostics are projected faithfully while roadmap entries
    remain free of mutable artifact status fields."""

    _VALID_ULID = "01KT50AZRMK5X890TQ565DDB5V"

    def test_lifecycle_warnings_appear_in_projection_diagnostics(self) -> None:
        """Lifecycle warnings (dismissed, addressed, superseded, completed)
        are projected as regular diagnostic entries."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="warning",
                message="Dismissed ticket in roadmap: ticket 'ABC' ('Fix auth') has been dismissed.",
                source_location=SourceLocation(path="strategy.md", line=42, column=1),
            ),
            StrategyDiagnostic(
                level="warning",
                message="Superseded ticket in roadmap: ticket 'DEF' ('Old feature') has been promoted to epic(s) 'my-epic'.",
                source_location=SourceLocation(path="strategy.md", line=44, column=1),
            ),
            StrategyDiagnostic(
                level="warning",
                message="Completed epic in roadmap: epic 'done-epic' ('Done') is in state 'archived'.",
                source_location=SourceLocation(path="strategy.md", line=46, column=1),
            ),
            StrategyDiagnostic(
                level="warning",
                message="Duplicate intent: ticket 'ABC' and its promoted epic 'my-epic' both appear in the roadmap.",
                source_location=None,
            ),
        ])
        projection = project_strategy(doc)
        assert len(projection["diagnostics"]) == 4
        assert projection["validation_summary"]["warning_count"] == 4
        assert projection["validation_summary"]["error_count"] == 0
        assert projection["validation_summary"]["total_diagnostics"] == 4
        assert projection["validation_summary"]["clean"] is False

        # Each diagnostic has the expected structure
        for diag in projection["diagnostics"]:
            assert "level" in diag
            assert "message" in diag
            assert "source" in diag
            assert diag["level"] == "warning"

    def test_lifecycle_diagnostics_dont_add_fields_to_roadmap_entries(
        self,
    ) -> None:
        """Even when lifecycle diagnostics exist, roadmap entries in the
        projection must only contain type/ref/title/horizon/source."""
        doc = _make_doc(
            roadmap={
                "Now": [
                    _make_entry("ticket", self._VALID_ULID, "Fix auth", "Now"),
                    _make_entry("epic", "my-epic", "My Epic", "Now"),
                ],
                "Next": [],
                "Later": [],
            },
            diagnostics=[
                StrategyDiagnostic(
                    level="warning",
                    message="Dismissed ticket in roadmap: ticket '...' has been dismissed.",
                    source_location=SourceLocation(path="s.md", line=1, column=1),
                ),
                StrategyDiagnostic(
                    level="warning",
                    message="Completed epic in roadmap: epic 'my-epic' is in state 'archived'.",
                    source_location=SourceLocation(path="s.md", line=2, column=1),
                ),
            ],
        )
        projection = project_strategy(doc)
        required_keys = {"type", "ref", "title", "horizon", "source"}
        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                assert set(entry.keys()) == required_keys, (
                    f"Roadmap entry keys {sorted(entry.keys())} != "
                    f"{sorted(required_keys)} in horizon '{horizon}' "
                    f"(diagnostics exist but must not leak into entries)"
                )

    def test_projection_with_lifecycle_diagnostics_is_deterministic(
        self,
    ) -> None:
        """The same lifecycle diagnostics produce byte-for-byte identical
        projections across multiple calls."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="warning",
                message="Superseded ticket in roadmap: ticket 'X' has been promoted to epic(s) 'Y'.",
                source_location=SourceLocation(path="s.md", line=5, column=1),
            ),
            StrategyDiagnostic(
                level="error",
                message="Duplicate intent: ticket 'X' and its promoted epic 'Y' both appear in the roadmap.",
                source_location=None,
            ),
        ])
        outputs = {serialize_strategy_projection(doc) for _ in range(5)}
        assert len(outputs) == 1, (
            f"Non-deterministic projection with lifecycle diagnostics: "
            f"got {len(outputs)} distinct outputs"
        )

    def test_serialized_json_with_lifecycle_diagnostics_excludes_forbidden_keys(
        self,
    ) -> None:
        """Even with lifecycle diagnostic content, the serialized projection
        must not contain mutable artifact status keys."""
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="warning",
                message="Dismissed ticket in roadmap: ticket 'DISMISSED-ONE' has been dismissed.",
                source_location=SourceLocation(path="s.md", line=1, column=1),
            ),
            StrategyDiagnostic(
                level="warning",
                message="Completed epic in roadmap: epic 'done' is in state 'archived'.",
                source_location=SourceLocation(path="s.md", line=2, column=1),
            ),
        ])
        serialized = serialize_strategy_projection(doc)
        parsed = json.loads(serialized)

        # Recursively check all keys using the existing helper
        TestProjectionNoBodyOrLifecycle._assert_no_forbidden_keys(
            parsed, path="$", in_stable_section=False
        )

    def test_lifecycle_diagnostic_messages_are_verbatim_in_projection(
        self,
    ) -> None:
        """Lifecycle diagnostic messages appear verbatim in the projection."""
        msg = (
            "Dismissed ticket in roadmap: ticket '01KT50AZRMK5X890TQ565DDB5V' "
            "('Fix auth timeout') has been dismissed.  "
            "Consider removing it from the roadmap."
        )
        doc = _make_doc(diagnostics=[
            StrategyDiagnostic(
                level="warning",
                message=msg,
                source_location=SourceLocation(path="s.md", line=42, column=1),
            ),
        ])
        projection = project_strategy(doc)
        assert projection["diagnostics"][0]["message"] == msg

    def test_roadmap_entries_exclude_status_even_with_lifecycle_diagnostics(
        self,
    ) -> None:
        """Regression: ensure that roadmap entry content never includes
        'status', 'state', 'completed', etc. even when diagnostics contain
        those words."""
        doc = _make_doc(
            roadmap={
                "Now": [
                    _make_entry("ticket", self._VALID_ULID, "Fix auth", "Now"),
                    _make_entry("epic", "my-epic", "My Epic", "Now"),
                ],
                "Next": [],
                "Later": [],
            },
            diagnostics=[
                StrategyDiagnostic(
                    level="warning",
                    message=(
                        "Dismissed ticket in roadmap: status=dismissed, "
                        "state=closed, completed=true — these words must not "
                        "leak into roadmap entries."
                    ),
                    source_location=SourceLocation(path="s.md", line=1, column=1),
                ),
            ],
        )
        projection = project_strategy(doc)
        for horizon, entries in projection["roadmap"].items():
            for entry in entries:
                for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
                    assert forbidden not in {k.lower() for k in entry.keys()}, (
                        f"Forbidden substring '{forbidden}' in roadmap entry "
                        f"keys {sorted(entry.keys())} after lifecycle diagnostics"
                    )
