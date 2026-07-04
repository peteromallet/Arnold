"""Docs/scaffold synchronization tests for M6 composition conformance.

These tests verify:
- Scaffold examples compile and match generated artifact expectations.
- Active paths are scanned for forbidden shim/fallback/direct-manifest/
  native_program authority guidance.
- The legacy ``arnold/pipelines/_template/`` path is not resurrected.
- Docs reference only the active scaffold path.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# ── Active scaffold path (the canonical template) ─────────────────────────
ACTIVE_SCAFFOLD_ROOT = REPO_ROOT / "arnold_pipelines" / "_template"

# ── Legacy scaffold path (MUST NOT exist) ─────────────────────────────────
LEGACY_SCAFFOLD_ROOT = REPO_ROOT / "arnold" / "pipelines" / "_template"

# ── Composition docs to scan for forbidden patterns ───────────────────────
COMPOSITION_DOC_PATHS = (
    Path("docs/arnold/native-composition-contract.md"),
    Path("docs/arnold/authoring-guide.md"),
    Path("docs/arnold/package-authoring-contract.md"),
    Path("docs/arnold/workflow-authoring.md"),
    Path("docs/arnold/creating-a-new-pipeline.md"),
    Path("docs/arnold/native-composition-metadata-plan.md"),
    Path("docs/arnold/python-shaped-authoring-contract.md"),
)

# ── Scaffold files to compile/validate ────────────────────────────────────
SCAFFOLD_PYTHON_FILES = (
    "pipelines.py",
)

# ── Forbidden patterns in docs and scaffold sources ───────────────────────
# Patterns that indicate shim/fallback composition authority.
FORBIDDEN_SHIM_FALLBACK_TERMS = (
    "shim",
    "fallback builder",
    "graph fallback",
    "dual-mode package",
    "compatibility namespace",
    "compatibility shell",
    "_legacy.py",
    "legacy builder",
    "temporary wrapper",
    "--driver graph",
)

# Patterns that indicate direct hand-authored manifest/native_program
# as the source of composition authority instead of decorated source.
FORBIDDEN_DIRECT_AUTHORITY_TERMS = (
    "hand-authored WorkflowManifest",
    "hand-authored NativeProgram",
    "direct IR construction",
    "native_program as source of truth",
    "native_program defines composition",
)

# Aggregated scan terms.
FORBIDDEN_COMPOSITION_TERMS = FORBIDDEN_SHIM_FALLBACK_TERMS + FORBIDDEN_DIRECT_AUTHORITY_TERMS

# ── Terms that indicate a line is intentionally documenting a forbidden
#    pattern for migration/deletion/rejection purposes ─────────────────────
REJECTION_CONTEXT_MARKERS = (
    "do not",
    "do **not**",
    "must not",
    "cannot",
    "forbidden",
    "prohibited",
    "rejected",
    "invalid",
    "legacy",
    "migration",
    "delete",
    "archival",
    "no longer",
    "banned",
    "non-conformant",
    "not conformant",
    "explicitly disallowed",
    "never",
    "tolerated",
    "bridge debt",
    "not the source-authoritative",
)


# ── Helper utilities ──────────────────────────────────────────────────────

def _is_rejection_context(line: str) -> bool:
    """Return True when the line explicitly marks a pattern as rejected."""
    # Normalize markdown bold/italic for matching
    normalized = line.lower()
    normalized = normalized.replace("**", "")
    normalized = normalized.replace("*", "")
    normalized = normalized.replace("__", "")
    return any(marker in normalized for marker in REJECTION_CONTEXT_MARKERS)


def _paragraph_has_rejection(paragraph_lines: list[str]) -> bool:
    """Return True if any line in the paragraph has a rejection marker."""
    return any(_is_rejection_context(line) for line in paragraph_lines)


def _is_table_or_fence_line(stripped: str) -> bool:
    """Return True for markdown table rows or code-fence delimiters."""
    return stripped.startswith("|") or stripped.startswith("```")


def _scan_for_forbidden(line: str, terms: tuple[str, ...]) -> list[str]:
    """Return terms found in *line* (lowercased), excluding rejection context."""
    lowered = line.lower()
    matches: list[str] = []
    for term in terms:
        if term.lower() in lowered:
            matches.append(term)
    return matches


def _paragraphs_from_lines(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Split lines into (start_line, paragraph_lines) groups on blank lines."""
    paragraphs: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start = 1
    for lineno, line in enumerate(lines, start=1):
        if line.strip() == "":
            if current:
                paragraphs.append((start, current))
                current = []
            start = lineno + 1
        else:
            current.append(line)
    if current:
        paragraphs.append((start, current))
    return paragraphs


def _python_files_in(path: Path) -> list[Path]:
    """Return all .py files under *path* recursively."""
    if not path.exists() or not path.is_dir():
        return []
    return sorted(path.rglob("*.py"))


# ── Scaffold compilation / artifact alignment tests ───────────────────────

class TestScaffoldCompiles:
    """Verify scaffold source files are syntactically valid."""

    def test_scaffold_python_files_exist(self) -> None:
        """Every expected scaffold Python file exists under the active path."""
        missing: list[str] = []
        for name in SCAFFOLD_PYTHON_FILES:
            path = ACTIVE_SCAFFOLD_ROOT / name
            if not path.exists():
                missing.append(name)
        assert not missing, (
            f"Missing scaffold files under {ACTIVE_SCAFFOLD_ROOT}: {missing}"
        )

    def test_scaffold_python_files_compile(self) -> None:
        """Every scaffold Python file compiles cleanly with py_compile."""
        failures: list[str] = []
        for py_file in _python_files_in(ACTIVE_SCAFFOLD_ROOT):
            try:
                compile(py_file.read_text(encoding="utf-8"), str(py_file), "exec")
            except SyntaxError as exc:
                failures.append(f"{py_file}: {exc}")
        assert not failures, "Scaffold files with syntax errors:\n" + "\n".join(failures)

    def test_scaffold_python_files_parseable_ast(self) -> None:
        """Every scaffold Python file is AST-parseable."""
        failures: list[str] = []
        for py_file in _python_files_in(ACTIVE_SCAFFOLD_ROOT):
            try:
                ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError as exc:
                failures.append(f"{py_file}: {exc}")
        assert not failures, "Scaffold files with AST errors:\n" + "\n".join(failures)

    def test_scaffold_entrypoint_declares_native_driver(self) -> None:
        """The scaffold __init__.py declares native driver and supported_modes."""
        init_path = ACTIVE_SCAFFOLD_ROOT / "__init__.py"
        assert init_path.exists(), f"Missing {init_path}"
        text = init_path.read_text(encoding="utf-8")
        assert 'driver: tuple[str, str] = ("native"' in text or 'driver=("native"' in text, (
            "Scaffold __init__.py must declare a native driver"
        )
        assert '"native"' in text.split('supported_modes')[1].split('\n')[0] if 'supported_modes' in text else False or any(
            line for line in text.splitlines() if 'supported_modes' in line and '"native"' in line
        ), "Scaffold __init__.py must declare supported_modes including 'native'"

    def test_scaffold_entrypoint_build_pipeline_returns_pipeline_with_native_program(self) -> None:
        """build_pipeline() projects a Pipeline with non-null native_program."""
        init_path = ACTIVE_SCAFFOLD_ROOT / "__init__.py"
        text = init_path.read_text(encoding="utf-8")
        assert "build_pipeline" in text, "Scaffold must define build_pipeline"
        assert "native_program" in text, "Scaffold must reference native_program"
        assert "project_graph" in text or "native_program=native" in text, (
            "Scaffold must project graph with native_program"
        )


class TestScaffoldHasCompositionalFeatures:
    """Verify scaffold has compositional native features (per T20/T21)."""

    def test_scaffold_has_declared_inputs_outputs(self) -> None:
        """Scaffold pipelines.py declares inputs and outputs schemas."""
        p = ACTIVE_SCAFFOLD_ROOT / "pipelines.py"
        text = p.read_text(encoding="utf-8")
        assert "inputs" in text, "Scaffold must declare inputs"
        assert "outputs" in text, "Scaffold must declare outputs"

    def test_scaffold_has_nested_child_workflow(self) -> None:
        """Scaffold uses a nested @workflow child."""
        p = ACTIVE_SCAFFOLD_ROOT / "pipelines.py"
        text = p.read_text(encoding="utf-8")
        assert "@workflow" in text, "Scaffold must declare at least one @workflow"

    def test_scaffold_has_parallel_map_with_path_template(self) -> None:
        """Scaffold uses parallel_map with stable path_template."""
        p = ACTIVE_SCAFFOLD_ROOT / "pipelines.py"
        text = p.read_text(encoding="utf-8")
        assert "parallel_map" in text, "Scaffold must use parallel_map"
        assert "path_template" in text, "Scaffold must use path_template"

    def test_scaffold_has_path_resume_example(self) -> None:
        """Scaffold has a start_from_trace path-resume example."""
        p = ACTIVE_SCAFFOLD_ROOT / "pipelines.py"
        text = p.read_text(encoding="utf-8")
        assert "start_from_trace" in text, "Scaffold must have a path-resume example"

    def test_scaffold_has_repeated_child_call_sites(self) -> None:
        """Scaffold calls a child workflow more than once (repeated call sites)."""
        p = ACTIVE_SCAFFOLD_ROOT / "pipelines.py"
        text = p.read_text(encoding="utf-8")
        # Count yield statements that call review_pass or similar child workflow.
        review_yields = [l for l in text.splitlines() if "yield review_pass" in l or "yield review" in l.lower()]
        assert len(review_yields) >= 2, (
            f"Scaffold should have at least 2 repeated child call sites, found {len(review_yields)}"
        )

    def test_scaffold_uses_stable_ids(self) -> None:
        """Scaffold decorators use literal id= for stable path identity."""
        p = ACTIVE_SCAFFOLD_ROOT / "pipelines.py"
        text = p.read_text(encoding="utf-8")
        assert re.search(r'id\s*=\s*"', text), "Scaffold must have at least one literal id="


# ── Legacy path resurrection guard ────────────────────────────────────────

class TestLegacyScaffoldPathNotResurrected:
    """The legacy ``arnold/pipelines/_template/`` must NOT exist."""

    def test_legacy_scaffold_directory_does_not_exist(self) -> None:
        assert not LEGACY_SCAFFOLD_ROOT.exists(), (
            f"Legacy scaffold path {LEGACY_SCAFFOLD_ROOT} must NOT exist. "
            f"Use the active path: {ACTIVE_SCAFFOLD_ROOT}"
        )

    def test_legacy_scaffold_init_does_not_exist(self) -> None:
        legacy_init = LEGACY_SCAFFOLD_ROOT / "__init__.py"
        assert not legacy_init.exists(), (
            f"Legacy scaffold init {legacy_init} must NOT exist. "
            f"Do not resurrect arnold/pipelines/_template/"
        )

    def test_active_scaffold_does_not_reference_legacy_path(self) -> None:
        """Active scaffold files must not reference the legacy path."""
        violations: list[str] = []
        for py_file in _python_files_in(ACTIVE_SCAFFOLD_ROOT):
            text = py_file.read_text(encoding="utf-8")
            if "arnold/pipelines/_template" in text:
                violations.append(str(py_file.relative_to(REPO_ROOT)))
        assert not violations, (
            f"Active scaffold references legacy path arnold/pipelines/_template/: {violations}"
        )

    def test_skill_md_does_not_reference_legacy_scaffold_path(self) -> None:
        """SKILL.md files in active scaffold must reference only the active path."""
        violations: list[str] = []
        for md_file in sorted(ACTIVE_SCAFFOLD_ROOT.rglob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if "arnold/pipelines/_template" in line and not _is_rejection_context(line):
                    violations.append(f"{md_file.relative_to(REPO_ROOT)}:{lineno}")
        assert not violations, (
            f"SKILL.md references legacy scaffold path: {violations}"
        )


# ── Forbidden pattern scans over docs ─────────────────────────────────────

class TestCompositionDocsForbiddenPatterns:
    """Composition docs must not teach shim/fallback/direct-manifest authority."""

    def test_composition_docs_exist(self) -> None:
        """All tracked composition docs exist."""
        missing: list[str] = []
        for rel in COMPOSITION_DOC_PATHS:
            p = REPO_ROOT / rel
            if not p.exists():
                missing.append(rel.as_posix())
        assert not missing, f"Missing composition docs: {missing}"

    def test_composition_docs_no_shim_fallback(self) -> None:
        """Composition docs must not endorse shim/fallback authority patterns."""
        violations: list[str] = []
        for rel in COMPOSITION_DOC_PATHS:
            p = REPO_ROOT / rel
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            for start, para_lines in _paragraphs_from_lines(text.splitlines()):
                if _paragraph_has_rejection(para_lines):
                    continue
                para_text = " ".join(line.strip() for line in para_lines).lower()
                # Skip paragraphs that describe existing tolerated/compatibility state
                if "still supported" in para_text and "compatibility shell" in para_text:
                    continue
                if "tolerated" in para_text and "bridge debt" in para_text:
                    continue
                for offset, line in enumerate(para_lines):
                    stripped = line.strip()
                    if _is_table_or_fence_line(stripped):
                        continue
                    lineno = start + offset
                    matches = _scan_for_forbidden(line, FORBIDDEN_SHIM_FALLBACK_TERMS)
                    for term in matches:
                        violations.append(f"{rel}:{lineno}: {term!r}")
        assert not violations, (
            "Composition docs contain forbidden shim/fallback terms:\n" + "\n".join(violations)
        )

    def test_composition_docs_no_direct_manifest_authority(self) -> None:
        """Composition docs must not teach direct-manifest or native_program authority."""
        violations: list[str] = []
        for rel in COMPOSITION_DOC_PATHS:
            p = REPO_ROOT / rel
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            bullets_in_toleration: set[int] = set()
            # First pass: find toleration paragraphs whose next paragraph is a bullet list
            all_paragraphs = _paragraphs_from_lines(text.splitlines())
            for i, (start, para_lines) in enumerate(all_paragraphs):
                para_text = " ".join(line.strip() for line in para_lines).lower()
                if ("tolerated" in para_text and "bridge debt" in para_text):
                    # Mark next paragraph's lines as tolerated if it starts with bullet
                    if i + 1 < len(all_paragraphs):
                        next_start, next_lines = all_paragraphs[i + 1]
                        if next_lines and next_lines[0].strip().startswith("-"):
                            for off in range(len(next_lines)):
                                bullets_in_toleration.add(next_start + off)
            for start, para_lines in all_paragraphs:
                if _paragraph_has_rejection(para_lines):
                    continue
                for offset, line in enumerate(para_lines):
                    stripped = line.strip()
                    if _is_table_or_fence_line(stripped):
                        continue
                    lineno = start + offset
                    if lineno in bullets_in_toleration:
                        continue
                    matches = _scan_for_forbidden(line, FORBIDDEN_DIRECT_AUTHORITY_TERMS)
                    for term in matches:
                        violations.append(f"{rel}:{lineno}: {term!r}")
        assert not violations, (
            "Composition docs contain forbidden direct-manifest/native_program authority terms:\n"
            + "\n".join(violations)
        )

    def test_composition_docs_native_program_described_as_substrate(self) -> None:
        """Docs describing native_program must call it a dispatch substrate, not composition authority."""
        doc_paths_to_check = (
            "docs/arnold/native-composition-contract.md",
            "docs/arnold/authoring-guide.md",
        )
        for rel in doc_paths_to_check:
            p = REPO_ROOT / rel
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8").lower()
            # If doc says "source" near "native_program", it must also clarify substrate role.
            if "native_program" in text:
                assert "substrate" in text or "dispatch" in text, (
                    f"{rel} mentions native_program but does not describe it as a dispatch substrate"
                )


# ── Forbidden pattern scans over scaffold ─────────────────────────────────

class TestScaffoldForbiddenPatterns:
    """Scaffold files must not contain shim/fallback/direct-manifest guidance."""

    def test_scaffold_python_no_shim_fallback(self) -> None:
        """Scaffold Python files must not contain shim/fallback terms."""
        violations: list[str] = []
        for py_file in _python_files_in(ACTIVE_SCAFFOLD_ROOT):
            text = py_file.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _is_rejection_context(line):
                    continue
                matches = _scan_for_forbidden(line, FORBIDDEN_SHIM_FALLBACK_TERMS)
                for term in matches:
                    violations.append(f"{py_file.relative_to(REPO_ROOT)}:{lineno}: {term!r}")
        assert not violations, (
            "Scaffold Python files contain forbidden shim/fallback terms:\n" + "\n".join(violations)
        )

    def test_scaffold_python_no_direct_manifest_authority(self) -> None:
        """Scaffold Python files must not contain direct-manifest/native_program authority terms."""
        violations: list[str] = []
        for py_file in _python_files_in(ACTIVE_SCAFFOLD_ROOT):
            text = py_file.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _is_rejection_context(line):
                    continue
                matches = _scan_for_forbidden(line, FORBIDDEN_DIRECT_AUTHORITY_TERMS)
                for term in matches:
                    violations.append(f"{py_file.relative_to(REPO_ROOT)}:{lineno}: {term!r}")
        assert not violations, (
            "Scaffold Python files contain forbidden direct-manifest authority terms:\n"
            + "\n".join(violations)
        )

    def test_scaffold_skill_md_no_shim_fallback(self) -> None:
        """Scaffold SKILL.md files must not contain shim/fallback terms (outside rejection)."""
        violations: list[str] = []
        for md_file in sorted(ACTIVE_SCAFFOLD_ROOT.rglob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            for start, para_lines in _paragraphs_from_lines(text.splitlines()):
                if _paragraph_has_rejection(para_lines):
                    continue
                for offset, line in enumerate(para_lines):
                    stripped = line.strip()
                    if _is_table_or_fence_line(stripped):
                        continue
                    lineno = start + offset
                    matches = _scan_for_forbidden(line, FORBIDDEN_COMPOSITION_TERMS)
                    for term in matches:
                        violations.append(f"{md_file.relative_to(REPO_ROOT)}:{lineno}: {term!r}")
        assert not violations, (
            "Scaffold SKILL.md files contain forbidden terms:\n" + "\n".join(violations)
        )

    def test_scaffold_skill_md_native_program_substrate(self) -> None:
        """Scaffold SKILL.md files describing native_program must call it a dispatch substrate."""
        violations: list[str] = []
        for md_file in sorted(ACTIVE_SCAFFOLD_ROOT.rglob("*.md")):
            text = md_file.read_text(encoding="utf-8").lower()
            if "native_program" in text:
                has_substrate = "substrate" in text or "dispatch" in text
                if not has_substrate:
                    violations.append(str(md_file.relative_to(REPO_ROOT)))
        assert not violations, (
            "Scaffold SKILL.md files mention native_program without describing it as dispatch substrate:\n"
            + "\n".join(violations)
        )


# ── Scaffold / generated artifact alignment ───────────────────────────────

class TestScaffoldMatchesGeneratedArtifacts:
    """Scaffold shape must align with generated/expected artifact expectations."""

    def test_scaffold_native_program_is_compilable(self) -> None:
        """build_native_program() in scaffold is importable and runnable."""
        # This is a smoke test: we import the scaffold module and call build_native_program.
        import sys
        scaffold_dir = str(ACTIVE_SCAFFOLD_ROOT.parent)
        if scaffold_dir not in sys.path:
            sys.path.insert(0, scaffold_dir)
        try:
            from _template.pipelines import build_native_program
            native = build_native_program()
            assert native is not None, "build_native_program() returned None"
            # Check it has expected shape
            assert hasattr(native, "phases") or hasattr(native, "steps") or hasattr(
                native, "entry"
            ), "NativeProgram must have phases/steps/entry attribute"
        except ImportError as exc:
            pytest.skip(f"Scaffold import requires full deps: {exc}")
        except Exception as exc:
            # Allow skip if deps missing; fail on structural issues
            if "No module named" in str(exc) or "cannot import" in str(exc).lower():
                pytest.skip(f"Scaffold import requires full deps: {exc}")
            raise

    def test_scaffold_native_program_has_non_null_native_program(self) -> None:
        """build_pipeline() produces a Pipeline with non-null native_program."""
        import sys
        scaffold_dir = str(ACTIVE_SCAFFOLD_ROOT.parent)
        if scaffold_dir not in sys.path:
            sys.path.insert(0, scaffold_dir)
        try:
            from _template import build_pipeline
            p = build_pipeline()
            assert p.native_program is not None, (
                "build_pipeline() must return Pipeline with non-null native_program"
            )
        except ImportError as exc:
            pytest.skip(f"Scaffold import requires full deps: {exc}")
        except Exception as exc:
            if "No module named" in str(exc) or "cannot import" in str(exc).lower():
                pytest.skip(f"Scaffold import requires full deps: {exc}")
            raise
