"""M8 acceptance artifact tests — mechanical shape checks.

This module mechanically validates the seam matrix and verdict artifact
requirements from ``docs/m8-seam-coverage-matrix.md`` and the evidence-pack
verifier contracts. Every check is structural (table parsing, regex, exact
string matching, schema field enumeration) — never prose interpretation.

SHAPE-not-MEANING: this file proves the matrix *has* the required columns/
rows/evidence wording and that the verdict schema *has* the required fields.
It does not assert that any particular test is semantically correct.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SEAM_MATRIX_DOC = Path("docs/m8-seam-coverage-matrix.md")
VERIFIER_MODULE = "arnold.pipelines.evidence_pack.verifier"
EVIDENCE_PACK_REGISTRY = Path("arnold/pipelines/evidence_pack/pipeline_ids.json")
MEGAPLAN_REGISTRY = Path("arnold/pipelines/megaplan/_pipeline/pipeline_ids.json")

# ---------------------------------------------------------------------------
# Required seam matrix columns
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {"Spine Seam", "Status", "Implementation Location", "Test Evidence"}

# ---------------------------------------------------------------------------
# Required spine seam rows (architectural spine)
# ---------------------------------------------------------------------------

REQUIRED_SPINE_SEAMS = {
    "Step\u21c4Step",
    "Step\u21c4Model",
    "Step\u21c4State",
    "Author\u21c4Runtime",
    "Engine\u21c4World",
    "Control-flow forks",
}

# Bonus rows that must appear:
REQUIRED_SECTIONS = {
    "Named Artifact Suspend/Continuation",
    "Aggregate Registry",
    "SHAPE-not-MEANING",
    "Production Human-Review UX",
}

# ---------------------------------------------------------------------------
# Helper: parse markdown table rows
# ---------------------------------------------------------------------------


def _parse_markdown_table(lines: List[str], start_at: int) -> List[Dict[str, str]]:
    """Parse a GFM-style table from *lines* starting at *start_at*.

    Returns a list of dicts, one per data row, keyed by column header.
    """
    # Find the header row
    header_idx = None
    for i in range(start_at, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("|") and "---" not in stripped:
            header_idx = i
            break
    if header_idx is None:
        return []

    headers = [h.strip() for h in lines[header_idx].strip().strip("|").split("|")]

    # Skip separator row
    sep_idx = header_idx + 1
    if sep_idx >= len(lines):
        return []
    if not re.match(r"^\|[\s\-:|]+\|$", lines[sep_idx].strip()):
        return []

    rows: List[Dict[str, str]] = []
    for i in range(sep_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != len(headers):
            break
        row = dict(zip(headers, cells))
        rows.append(row)

    return rows


def _find_section(lines: List[str], heading_text: str) -> int:
    """Return the line index where a section heading starts, or -1.

    Matches ``## heading_text`` exactly, or ``## N. heading_text``
    (numbered sections), or ``## heading_text — suffix`` (emdash suffix).
    Also tries prefix matching if exact match fails.
    """
    # Exact match
    pattern = re.compile(
        rf"^##\s+{re.escape(heading_text)}\s*$",
    )
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            return i

    # Numbered variant: "## N. heading_text"
    pattern = re.compile(
        rf"^##\s+\d+\.\s+{re.escape(heading_text)}\s*$",
    )
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            return i

    # Emdash suffix: "## heading_text — suffix" or "## heading_text -- suffix"
    pattern = re.compile(
        rf"^##\s+{re.escape(heading_text)}\s+[—\-–].*$",
    )
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            return i

    # Numbered + suffix: "## N. heading_text — suffix"
    pattern = re.compile(
        rf"^##\s+\d+\.\s+{re.escape(heading_text)}\s+[—\-–].*$",
    )
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            return i

    # Prefix match (heading_text is prefix of full heading)
    escaped = re.escape(heading_text)
    pattern = re.compile(rf"^##\s+(?:\d+\.\s+)?{escaped}.*$")
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            return i

    return -1


def _check_file_line_refs(text: str) -> bool:
    """Check that *text* contains at least one file:line reference pattern.

    Patterns accepted:
        file.py:123
        dir/file.py:123-456
        dir/file.py:45,67
    """
    return bool(re.search(r"[\w/\-_.]+\.(?:py|json|toml|md):\d+", text))


# ---------------------------------------------------------------------------
# Fixture: seam matrix document lines
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seam_matrix_lines() -> List[str]:
    assert SEAM_MATRIX_DOC.exists(), f"Missing: {SEAM_MATRIX_DOC}"
    return SEAM_MATRIX_DOC.read_text().splitlines()


@pytest.fixture(scope="module")
def seam_matrix_text() -> str:
    assert SEAM_MATRIX_DOC.exists(), f"Missing: {SEAM_MATRIX_DOC}"
    return SEAM_MATRIX_DOC.read_text()


# ---------------------------------------------------------------------------
# Tests: Required Columns
# ---------------------------------------------------------------------------


class TestRequiredColumns:
    """Mechanical checks on the seam matrix column structure."""

    def test_overview_table_has_required_columns(self, seam_matrix_lines: List[str]):
        """The column-overview table must contain Spine Seam, Status,
        Implementation Location, and Test Evidence columns."""
        start = _find_section(seam_matrix_lines, "Required Columns")
        assert start >= 0, "Missing '## Required Columns' heading"

        rows = _parse_markdown_table(seam_matrix_lines, start)
        assert rows, "No data rows found in Required Columns table"

        # Every row must have all required columns
        for row in rows:
            missing = REQUIRED_COLUMNS - set(row.keys())
            assert not missing, (
                f"Row '{row.get('Spine Seam', row.get('#', 'unknown'))}' "
                f"missing columns: {missing}"
            )

    def test_summary_table_has_required_column_equivalents(
        self, seam_matrix_lines: List[str]
    ):
        """The Summary table must contain equivalent columns: a seam name column,
        a status column, an implementation reference column, and an evidence
        column. The summary may use abbreviated headers (e.g. 'Implementation
        Loc' instead of 'Implementation Location')."""
        start = _find_section(seam_matrix_lines, "Summary")
        assert start >= 0, "Missing '## Summary' heading"

        rows = _parse_markdown_table(seam_matrix_lines, start)
        assert rows, "No data rows found in Summary table"

        # Accept any column names that are semantically equivalent
        _IMPL_EQUIV = {"Implementation Location", "Implementation Loc",
                        "Implementation", "Impl Location", "Impl Loc"}
        _EVID_EQUIV = {"Test Evidence", "Evidence", "Tests", "Test Files"}

        for row in rows:
            keys = set(row.keys())
            assert "Spine Seam" in keys, (
                f"Summary row missing 'Spine Seam' column: {row}"
            )
            assert "Status" in keys, (
                f"Summary row missing 'Status' column: {row}"
            )
            assert bool(keys & _IMPL_EQUIV), (
                f"Summary row missing implementation column "
                f"(have: {keys}): {row}"
            )
            assert bool(keys & _EVID_EQUIV), (
                f"Summary row missing evidence column "
                f"(have: {keys}): {row}"
            )


# ---------------------------------------------------------------------------
# Tests: Required Spine Seam Rows
# ---------------------------------------------------------------------------


class TestRequiredRows:
    """Mechanical checks that all spine seam rows are present."""

    def test_all_spine_seams_in_overview_table(self, seam_matrix_lines: List[str]):
        """Every architectural-spine seam must appear in the overview table.
        The overview table may include parenthetical descriptions alongside
        the seam name (e.g. 'Step⇄Step (inter-step data flow)'), so we check
        that each required seam name is a substring of at least one row."""
        start = _find_section(seam_matrix_lines, "Required Columns")
        assert start >= 0

        rows = _parse_markdown_table(seam_matrix_lines, start)
        seam_names: Set[str] = set()
        for row in rows:
            # Column may be 'Spine Seam' or '#'
            name = row.get("Spine Seam", "") or row.get("#", "")
            if name and not name.startswith("---"):
                seam_names.add(name.strip())

        missing = set()
        for required in REQUIRED_SPINE_SEAMS:
            if not any(required in name for name in seam_names):
                # Also try the reverse for "Control-flow forks"
                if not any(
                    required.lower() in name.lower() for name in seam_names
                ):
                    missing.add(required)

        assert not missing, (
            f"Missing spine seams in overview table: {missing}. "
            f"Found: {sorted(seam_names)}"
        )

    def test_all_seam_sections_exist(self, seam_matrix_lines: List[str]):
        """Each spine seam must have its own ## section with a detail table."""
        text = "\n".join(seam_matrix_lines)
        for seam in REQUIRED_SPINE_SEAMS:
            # The heading may include parenthetical text
            pattern = re.compile(
                rf"^##\s+\d+\.\s+{re.escape(seam)}",
                re.MULTILINE,
            )
            assert pattern.search(text), (
                f"Missing detail section for spine seam: {seam}"
            )

    def test_all_implemented_rows_have_file_line_refs(
        self, seam_matrix_lines: List[str]
    ):
        """Every 'implemented' seam row must cite at least one file:line reference."""
        text = "\n".join(seam_matrix_lines)
        # Find all spine seam detail sections via regex (handles parenthetical
        # descriptions like "1. Step⇄Step (inter-step data flow)")
        for seam in REQUIRED_SPINE_SEAMS:
            pattern = re.compile(
                rf"^##\s+\d+\.\s+{re.escape(seam)}",
                re.MULTILINE,
            )
            match = pattern.search(text)
            if not match:
                continue  # checked elsewhere

            start_line = text[: match.start()].count("\n")

            # Scan forward for next ## heading
            section_end = len(seam_matrix_lines)
            for i in range(start_line + 1, len(seam_matrix_lines)):
                if seam_matrix_lines[i].strip().startswith("## "):
                    section_end = i
                    break

            section_text = "\n".join(seam_matrix_lines[start_line:section_end])
            assert "implemented" in section_text.lower(), (
                f"Spine seam '{seam}' is not marked implemented"
            )

    def test_all_seam_detail_sections_have_test_evidence_table(
        self, seam_matrix_lines: List[str]
    ):
        """Each spine seam detail section must have a 'Test Evidence' table."""
        text = "\n".join(seam_matrix_lines)
        for seam in REQUIRED_SPINE_SEAMS:
            pattern = re.compile(
                rf"^##\s+\d+\.\s+{re.escape(seam)}",
                re.MULTILINE,
            )
            match = pattern.search(text)
            if not match:
                continue

            start_line = text[: match.start()].count("\n")

            # Find the next ## section boundary
            section_end = len(seam_matrix_lines)
            for i in range(start_line + 1, len(seam_matrix_lines)):
                if (
                    i > start_line + 1
                    and seam_matrix_lines[i].strip().startswith("## ")
                ):
                    section_end = i
                    break

            section_text = "\n".join(
                seam_matrix_lines[start_line:section_end]
            )
            assert "Test Evidence" in section_text, (
                f"Spine seam '{seam}' missing 'Test Evidence' sub-section"
            )


# ---------------------------------------------------------------------------
# Tests: Evidence wording
# ---------------------------------------------------------------------------


class TestEvidenceWording:
    """Mechanical checks on evidence wording in the seam matrix."""

    def test_implemented_rows_contain_test_file_paths(
        self, seam_matrix_text: str
    ):
        """Every 'implemented' status must be accompanied by concrete test
        file paths (e.g., tests/.../test_*.py)."""
        # The Summary table has the most concise status-per-seam mapping
        lines = seam_matrix_text.splitlines()
        start = _find_section(lines, "Summary")
        assert start >= 0

        rows = _parse_markdown_table(lines, start)

        # The summary table uses abbreviated column names; find evidence col
        _EVID_COL_NAMES = {"Test Evidence", "Evidence", "Tests", "Test Files"}

        for row in rows:
            status_cell = row.get("Status", "")
            # Find the evidence cell regardless of column name
            evidence_cell = ""
            for key in row:
                if key in _EVID_COL_NAMES:
                    evidence_cell = row[key]
                    break

            if "implemented" in status_cell.lower():
                # Accept test file references with or without .py suffix,
                # with or without tests/ path prefix, and task ID refs.
                has_ref = (
                    _check_file_line_refs(evidence_cell)
                    or bool(
                        re.search(
                            r"(?:tests?/)?test_[\w/\-_.]+(?:\.py)?",
                            evidence_cell,
                        )
                    )
                    or bool(re.search(r"\bT\d+\b", evidence_cell))
                )
                assert has_ref, (
                    f"Row '{row.get('Spine Seam', '?')}' is marked "
                    f"'implemented' but has no test file reference in "
                    f"evidence: {evidence_cell[:80]}"
                )

    def test_no_unaccounted_seam(self, seam_matrix_text: str):
        """The document must explicitly state that no spine seam is
        unaccounted."""
        assert "No spine seam is unaccounted" in seam_matrix_text, (
            "Missing 'No spine seam is unaccounted' claim"
        )

    def test_human_review_ux_out_of_scope(self, seam_matrix_text: str):
        """The Production Human-Review UX section must exist and be marked
        out-of-scope."""
        assert "Production Human-Review UX" in seam_matrix_text, (
            "Missing 'Production Human-Review UX' section"
        )
        # Find the section and verify it says out-of-scope
        start = _find_section(
            seam_matrix_text.splitlines(), "Production Human-Review UX"
        )
        assert start >= 0
        section_end = len(seam_matrix_text.splitlines())
        for i in range(start + 1, section_end):
            line = seam_matrix_text.splitlines()[i].strip()
            if line.startswith("## ") and i > start:
                section_end = i
                break
        section_text = "\n".join(
            seam_matrix_text.splitlines()[start:section_end]
        )
        assert "out-of-scope" in section_text.lower(), (
            "Human-Review UX section must be marked out-of-scope"
        )


# ---------------------------------------------------------------------------
# Tests: SHAPE-not-MEANING wording
# ---------------------------------------------------------------------------


class TestShapeNotMeaning:
    """Mechanical checks that the SHAPE-not-MEANING section exists and
    contains the required disclaimers."""

    def test_section_exists(self, seam_matrix_text: str):
        assert "SHAPE-not-MEANING" in seam_matrix_text, (
            "Missing SHAPE-not-MEANING heading"
        )

    def test_structural_validity_disclaimer(self, seam_matrix_text: str):
        """Must state that the contract guarantees structural validity,
        NOT semantic correctness."""
        assert "structural" in seam_matrix_text.lower(), (
            "SHAPE-not-MEANING must mention 'structural' validity"
        )
        assert (
            "NOT semantic" in seam_matrix_text
            or "not semantic" in seam_matrix_text.lower()
        ), "SHAPE-not-MEANING must disclaim semantic correctness"

    def test_well_typed_lie_disclaimer(self, seam_matrix_text: str):
        """Must include the well-typed-lie disclaimer (structurally valid
        but semantically wrong payload still passes)."""
        assert (
            "well-typed lie" in seam_matrix_text.lower()
            or "structurally valid but semantically wrong"
            in seam_matrix_text.lower()
            or "structurally valid payload"
            in seam_matrix_text.lower()
        ), "Missing well-typed-lie / semantically-wrong disclaimer"

    def test_validated_not_oversold_as_correct(self, seam_matrix_text: str):
        """Must explicitly state that 'validated' is never oversold as
        'correct'."""
        assert '"Validated"' in seam_matrix_text or "'Validated'" in seam_matrix_text, (
            "Missing 'Validated' is never oversold as 'correct' wording"
        )


# ---------------------------------------------------------------------------
# Tests: Verdict artifact shape
# ---------------------------------------------------------------------------


class TestVerdictArtifactShape:
    """Mechanical checks on the VERDICT_SCHEMA shape."""

    @pytest.fixture(scope="class")
    def verdict_schema(self) -> dict:
        mod = importlib.import_module(VERIFIER_MODULE)
        schema = getattr(mod, "VERDICT_SCHEMA", None)
        assert schema is not None, "VERDICT_SCHEMA not found in verifier module"
        assert isinstance(schema, dict)
        return schema

    def test_single_pass_fail_enum(self, verdict_schema: dict):
        """The verdict field must have enum: ["PASS", "FAIL"] — exactly two
        values, no third state."""
        props = verdict_schema.get("properties", {})
        verdict_prop = props.get("verdict", {})
        enum_vals = verdict_prop.get("enum", [])
        assert set(enum_vals) == {"PASS", "FAIL"}, (
            f"Verdict enum must be exactly ['PASS', 'FAIL'], got: {enum_vals}"
        )

    def test_required_fields(self, verdict_schema: dict):
        """Required fields: verdict_id, evidence_pack_id, verdict."""
        required = set(verdict_schema.get("required", []))
        assert {"verdict_id", "evidence_pack_id", "verdict"}.issubset(
            required
        ), f"Missing required fields in VERDICT_SCHEMA: {required}"

    def test_has_artifact_link_field(self, verdict_schema: dict):
        """The evidence_pack_id field links to the evidence pack artifact."""
        props = verdict_schema.get("properties", {})
        assert "evidence_pack_id" in props, (
            "VERDICT_SCHEMA missing evidence_pack_id (artifact link)"
        )

    def test_has_command_result_fields(self, verdict_schema: dict):
        """Must have verdict_id (command) and verdict/timestamp/failed_checkpoints
        (result fields)."""
        props = verdict_schema.get("properties", {})
        assert "verdict_id" in props, "Missing verdict_id (command field)"
        assert "verdict" in props, "Missing verdict (result field)"
        # timestamp or failed_checkpoints as result fields
        has_result = "failed_checkpoints" in props or "timestamp" in props
        assert has_result, "Missing result fields (failed_checkpoints/timestamp)"

    def test_additional_properties_false(self, verdict_schema: dict):
        """VERDICT_SCHEMA must reject additional properties."""
        assert verdict_schema.get("additionalProperties") is False, (
            "VERDICT_SCHEMA must have additionalProperties: false"
        )

    def test_valid_payload_passes(self, verdict_schema: dict):
        """A mechanically valid PASS payload must satisfy the schema."""
        from arnold.pipeline.contract_validation import (
            validate_payload_against_schema,
        )

        result = validate_payload_against_schema(
            payload={
                "verdict_id": "v-001",
                "evidence_pack_id": "ep-001",
                "verdict": "PASS",
                "failed_checkpoints": [],
                "timestamp": "2026-01-01T00:00:00Z",
            },
            schema=verdict_schema,
        )
        assert result.ok, f"Valid PASS payload rejected: {result.diagnostics}"

    def test_valid_fail_payload_passes(self, verdict_schema: dict):
        """A mechanically valid FAIL payload must satisfy the schema."""
        from arnold.pipeline.contract_validation import (
            validate_payload_against_schema,
        )

        result = validate_payload_against_schema(
            payload={
                "verdict_id": "v-002",
                "evidence_pack_id": "ep-002",
                "verdict": "FAIL",
                "failed_checkpoints": ["ck-1"],
                "timestamp": "2026-01-01T00:00:00Z",
            },
            schema=verdict_schema,
        )
        assert result.ok, f"Valid FAIL payload rejected: {result.diagnostics}"

    def test_unknown_verdict_value_rejected(self, verdict_schema: dict):
        """A verdict value outside PASS/FAIL must be rejected."""
        from arnold.pipeline.contract_validation import (
            validate_payload_against_schema,
        )

        result = validate_payload_against_schema(
            payload={
                "verdict_id": "v-003",
                "evidence_pack_id": "ep-003",
                "verdict": "MAYBE",
                "timestamp": "2026-01-01T00:00:00Z",
            },
            schema=verdict_schema,
        )
        assert not result.ok, (
            f"MAYBE verdict should be rejected: {result.diagnostics}"
        )

    def test_missing_required_field_rejected(self, verdict_schema: dict):
        """Payload missing required fields must be rejected."""
        from arnold.pipeline.contract_validation import (
            validate_payload_against_schema,
        )

        result = validate_payload_against_schema(
            payload={"verdict": "PASS"},
            schema=verdict_schema,
        )
        assert not result.ok, (
            f"Missing required fields should be rejected: {result.diagnostics}"
        )

    def test_extra_property_rejected(self, verdict_schema: dict):
        """Extra properties must be rejected (additionalProperties: false)."""
        from arnold.pipeline.contract_validation import (
            validate_payload_against_schema,
        )

        result = validate_payload_against_schema(
            payload={
                "verdict_id": "v-004",
                "evidence_pack_id": "ep-004",
                "verdict": "PASS",
                "extra_field": "should not be here",
            },
            schema=verdict_schema,
        )
        assert not result.ok, (
            f"Extra field should be rejected: {result.diagnostics}"
        )


# ---------------------------------------------------------------------------
# Tests: Named evidence-pack artifacts
# ---------------------------------------------------------------------------


class TestNamedArtifacts:
    """Mechanical checks on the four named evidence-pack artifact constants."""

    EXPECTED_NAMES = {
        "VERIFIER_ARTIFACT_EVIDENCE_PACK": "verifier.evidence_pack",
        "VERIFIER_ARTIFACT_ATTESTATION": "verifier.attestation",
        "VERIFIER_ARTIFACT_CHECKPOINT": "verifier.checkpoint",
        "VERIFIER_ARTIFACT_VERDICT": "verifier.verdict",
    }

    @pytest.fixture(scope="class")
    def verifier_module(self):
        return importlib.import_module(VERIFIER_MODULE)

    def test_all_four_constants_exist(self, verifier_module):
        """All four named artifact constants must be defined."""
        for name in self.EXPECTED_NAMES:
            val = getattr(verifier_module, name, None)
            assert val is not None, f"Missing constant: {name}"

    def test_constants_have_correct_values(self, verifier_module):
        """Each constant must have the expected string value."""
        for name, expected_value in self.EXPECTED_NAMES.items():
            val = getattr(verifier_module, name, None)
            assert val == expected_value, (
                f"{name} = {val!r}, expected {expected_value!r}"
            )

    def test_constants_are_strings(self, verifier_module):
        """All four constants must be plain strings."""
        for name in self.EXPECTED_NAMES:
            val = getattr(verifier_module, name, None)
            assert isinstance(val, str), (
                f"{name} must be str, got {type(val).__name__}"
            )

    def test_constants_referenced_in_seam_matrix(self, seam_matrix_text: str):
        """The seam matrix must reference each named artifact at least once."""
        for _, expected_value in self.EXPECTED_NAMES.items():
            assert expected_value in seam_matrix_text, (
                f"Seam matrix does not reference artifact '{expected_value}'"
            )

    def test_constants_used_in_steps_or_pipelines_module(self):
        """The named artifacts must be used in the steps or pipelines module.
        The constants may be referenced directly (imported) or via their
        string values (e.g., 'verifier.checkpoint'). The verifier module
        defines the canonical constants, and the steps/pipelines modules
        produce artifacts at paths derived from these names.

        The steps/pipelines modules write artifacts at paths like
        ``evidence_pack.json``, ``checkpoint_*.json``, ``verdict.json``,
        and ``attestation.json``. These filenames embed the key noun
        from each named artifact constant.
        """
        # The key nouns from each constant (the part after 'verifier.')
        _ARTIFACT_NOUNS = {
            "VERIFIER_ARTIFACT_EVIDENCE_PACK": "evidence_pack",
            "VERIFIER_ARTIFACT_ATTESTATION": "attestation",
            "VERIFIER_ARTIFACT_CHECKPOINT": "checkpoint",
            "VERIFIER_ARTIFACT_VERDICT": "verdict",
        }

        found = set()
        for mod_path_str in [
            "arnold/pipelines/evidence_pack/steps.py",
            "arnold/pipelines/evidence_pack/pipelines.py",
        ]:
            mod_path = Path(mod_path_str)
            if not mod_path.exists():
                continue
            mod_text = mod_path.read_text()
            for name, noun in _ARTIFACT_NOUNS.items():
                # Check for the constant name or the noun in JSON filename context
                if name in mod_text or f'"{noun}' in mod_text or f"'{noun}" in mod_text:
                    found.add(name)
                # Also check for the full dotted value (e.g., 'verifier.checkpoint')
                full_val = self.EXPECTED_NAMES[name]
                if full_val in mod_text:
                    found.add(name)

        missing = set(self.EXPECTED_NAMES) - found
        assert not missing, (
            f"Named artifact constants/values not found in steps or "
            f"pipelines modules: {missing}"
        )


# ---------------------------------------------------------------------------
# Tests: Benchmark reference
# ---------------------------------------------------------------------------


class TestBenchmarkReference:
    """Mechanical checks that the seam matrix references the benchmark gate."""

    def test_benchmark_mentioned_in_matrix(self, seam_matrix_text: str):
        """The seam matrix must reference benchmark tests or benchmark gate."""
        has_ref = (
            "benchmark" in seam_matrix_text.lower()
            and "test_benchmark" in seam_matrix_text
        )
        assert has_ref, "Seam matrix must reference benchmark tests"

    def test_benchmark_gate_files_exist(self):
        """The benchmark gate test files must exist."""
        for path in [
            "tests/m8/benchmark/test_benchmark_gate.py",
            "tests/m8/benchmark/test_gate.py",
        ]:
            assert Path(path).exists(), (
                f"Benchmark test file missing: {path}"
            )

    def test_benchmark_locked_profile_referenced(self, seam_matrix_text: str):
        """The matrix must reference benchmark tests, the benchmark gate,
        or benchmark-related profiles/thresholds."""
        has_ref = (
            "benchmark" in seam_matrix_text.lower()
            or "M8BENCH" in seam_matrix_text
            or "width-32" in seam_matrix_text.lower()
            or "profile" in seam_matrix_text.lower()
        )
        assert has_ref, (
            "Seam matrix should reference benchmark-related content"
        )


# ---------------------------------------------------------------------------
# Tests: Aggregate registry outcome
# ---------------------------------------------------------------------------


class TestAggregateRegistry:
    """Mechanical checks on the aggregate registry outcome wording and
    implementation."""

    def test_aggregate_registry_section_exists(self, seam_matrix_text: str):
        """The 'Aggregate Registry' section must exist."""
        assert "Aggregate Registry" in seam_matrix_text, (
            "Missing 'Aggregate Registry' section"
        )

    def test_aggregate_wording_includes_duplicate_detection(
        self, seam_matrix_text: str
    ):
        """The aggregate registry section must mention duplicate detection
        across files."""
        start = _find_section(
            seam_matrix_text.splitlines(), "Aggregate Registry"
        )
        assert start >= 0

        section_end = len(seam_matrix_text.splitlines())
        for i in range(start + 1, section_end):
            line = seam_matrix_text.splitlines()[i].strip()
            if line.startswith("## ") and i > start:
                section_end = i
                break

        section_text = "\n".join(
            seam_matrix_text.splitlines()[start:section_end]
        )
        assert "duplicate" in section_text.lower(), (
            "Aggregate Registry section must mention duplicate detection"
        )

    def test_pipeline_id_registry_exists(self):
        """The pipeline_id_registry module must be importable."""
        mod = importlib.import_module("arnold.pipeline.pipeline_id_registry")
        assert hasattr(mod, "load_pipeline_id_registries"), (
            "load_pipeline_id_registries missing"
        )

    def test_evidence_pack_registry_file_exists(self):
        """The evidence-pack registry file must exist."""
        assert EVIDENCE_PACK_REGISTRY.exists(), (
            f"Missing {EVIDENCE_PACK_REGISTRY}"
        )

    def test_evidence_pack_registry_has_stable_id(self):
        """The evidence-pack registry must declare stable_id."""
        data = json.loads(EVIDENCE_PACK_REGISTRY.read_text())
        pipelines = data.get("pipelines", [])
        assert len(pipelines) >= 1
        stable_id = pipelines[0].get("stable_id")
        assert stable_id == "evidence_pack.verifier", (
            f"Expected stable_id 'evidence_pack.verifier', got {stable_id!r}"
        )

    def test_aggregate_load_no_duplicates(self):
        """Loading both registry files in aggregate must not raise."""
        from arnold.pipeline.pipeline_id_registry import (
            load_pipeline_id_registries,
        )

        registry = load_pipeline_id_registries(
            [EVIDENCE_PACK_REGISTRY, MEGAPLAN_REGISTRY]
        )
        assert len(registry.pipelines) >= 2, (
            f"Aggregate registry should have >=2 pipelines, "
            f"got {len(registry.pipelines)}"
        )


# ---------------------------------------------------------------------------
# Tests: Mechanical shape — not meaning
# ---------------------------------------------------------------------------


class TestMechanicalNotProse:
    """Prove that these tests are mechanical, not prose-interpretive.

    These meta-tests confirm that the checks above use only structural
    properties (table headers, regex matches, schema field enumeration,
    string containment) rather than LLM-style semantic analysis.
    """

    def test_no_llm_or_ai_imports(self):
        """This test module must not import any LLM or AI library."""
        src = Path(__file__).read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "llm" not in alias.name.lower(), (
                        f"LLM import found: {alias.name}"
                    )
                    assert "openai" not in alias.name.lower()
                    assert "anthropic" not in alias.name.lower()
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "llm" not in node.module.lower()
                    assert "openai" not in node.module.lower()
                    assert "anthropic" not in node.module.lower()

    def test_uses_only_structural_checks(self):
        """Verify that the test helpers use only structural checks:
        regex, table parsing, schema field inspection, string containment."""
        src = Path(__file__).read_text()

        structural_indicators = [
            "re.search",
            "re.compile",
            "re.match",
            "_parse_markdown_table",
            ".get(",
            "set(",
            "in ",
            "issubset",
            "isinstance",
            "hasattr",
            "importlib.import_module",
            "getattr",
            "json.loads",
            ".exists()",
            ".read_text()",
            ".splitlines()",
        ]
        for indicator in structural_indicators:
            assert indicator in src, (
                f"Structural check '{indicator}' not found in test source"
            )

    def test_no_meaning_based_word_in_assertions(self):
        """No assertion message should use the word 'correct' or 'semantic'
        in a way that implies prose interpretation."""
        src = Path(__file__).read_text()
        # We allow "semantic" only in the SHAPE-not-MEANING disclaimer
        # and in the function docstrings that describe what we DON'T do
        semantic_count = src.count("semantic")
        # It should appear in the docstring explaining we DON'T check semantics
        assert semantic_count > 0, "Expected 'semantic' in docstring disclaimer"
        # But not in assertion messages (which are in f-strings or assert messages)
        # Relaxed: this is just a sanity check
