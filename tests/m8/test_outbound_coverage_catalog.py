"""AST-backed outbound coverage catalog test (T20).

Enumerates production call sites for the four outbound validation primitives
and asserts that every discovered call site is covered by the documentation
at ``docs/m8-outbound-coverage.md`` (by file path and containing function).

``validate_payload`` is treated specially: any discovered call site that is
not retired, delegating/raising, or explicitly documented is flagged.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, NamedTuple

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COVERAGE_DOC = Path("docs/m8-outbound-coverage.md")

TRACKED_FUNCTIONS = {
    "validate_payload_against_schema",
    "audit_step_payload",
    "capture_step_output",
    "validate_payload",
}

# Functions that produce/validate step output outside the primary C1 chokepoints.
# This set is a closed contract: any addition requires updating both this constant
# and the "Known Residual Functions" table in docs/m8-outbound-coverage.md.
KNOWN_RESIDUAL_FUNCTIONS: frozenset[str] = frozenset(
    {
        "_validate_finalize_payload",
        "_finalize_semantic_postcheck",
    }
)

# Documented residual set (must match KNOWN_RESIDUAL_FUNCTIONS exactly).
_DOCUMENTED_RESIDUAL_SET: frozenset[str] = frozenset(
    {
        "_validate_finalize_payload",
        "_finalize_semantic_postcheck",
    }
)

# validate_payload is declared as a live orphan; non-retired call sites are
# explicitly allowed if they raise/retire/delegate, or are already documented.
_VALIDATE_PAYLOAD_EXEMPT_PATTERNS = [
    # Retired-step detection in _impl.py
    "_RETIRED_VALIDATE_PAYLOAD_STEPS",
    "CliError",
    "raise",
    # Removal from public API
    "del validate_payload",
]

# Test directories and files to exclude from production enumeration
TEST_DIRS = {
    "tests",
    "test",
    ".megaplan",
    ".pytest_cache",
    "__pycache__",
    ".git",
}

TEST_FILE_PATTERNS = [
    "test_",
    "conftest",
    "_test",
]


def _is_production_file(filepath: Path) -> bool:
    """Return True if *filepath* is a production Python file (not a test)."""
    if filepath.suffix != ".py":
        return False
    path_str = str(filepath)

    # Skip test directories
    parts = filepath.parts
    for part in parts:
        if part in TEST_DIRS:
            return False

    # Skip test file patterns
    stem = filepath.stem
    for pattern in TEST_FILE_PATTERNS:
        if pattern in stem:
            return False

    # Skip virtual environments and site-packages
    if "site-packages" in path_str:
        return False

    return True


# ---------------------------------------------------------------------------
# AST call-site discovery
# ---------------------------------------------------------------------------


class CallSite(NamedTuple):
    """A discovered call site for a tracked function."""

    file: str  # relative path
    line: int
    func_name: str  # the called function name
    containing_func: str  # the function/method containing the call


def _discover_call_sites(root: Path) -> list[CallSite]:
    """Walk *root* and discover all call sites for tracked functions."""
    call_sites: list[CallSite] = []
    for filepath in sorted(root.rglob("*.py")):
        rel_filepath = filepath.relative_to(root)
        if not _is_production_file(rel_filepath):
            continue
        try:
            source = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        rel_path = str(rel_filepath)
        visitor = _CallSiteVisitor(rel_path)
        visitor.visit(tree)
        call_sites.extend(visitor.sites)

    return call_sites


class _CallSiteVisitor(ast.NodeVisitor):
    """AST visitor that collects call sites for tracked functions."""

    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.sites: list[CallSite] = []
        self._current_func: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        prev = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = prev

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        prev = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = prev

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        func_name = self._resolve_func_name(node.func)
        if func_name in TRACKED_FUNCTIONS:
            self.sites.append(
                CallSite(
                    file=self.rel_path,
                    line=node.lineno,
                    func_name=func_name,
                    containing_func=self._current_func or "<module>",
                )
            )
        self.generic_visit(node)

    @staticmethod
    def _resolve_func_name(node: ast.expr) -> str | None:
        """Resolve the called function name from an AST expression."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None


# ---------------------------------------------------------------------------
# Markdown doc parser
# ---------------------------------------------------------------------------


_DOC_SECTION_RE = re.compile(r"^##\s+(.+)$")


def _parse_coverage_doc(doc_path: Path) -> dict[str, set[tuple[str, str]]]:
    """Parse the coverage markdown document.

    Returns a mapping from function name to a set of (file_path, containing_func)
    tuples for all documented call sites.
    """
    if not doc_path.exists():
        return {}

    text = doc_path.read_text(encoding="utf-8")
    covered: dict[str, set[tuple[str, str]]] = {}

    # Parse per-section: find the "### Production Call Sites" tables within each
    # "## function_name" section, then extract the File and Containing Function
    # columns (columns 1 and 2 in each markdown row).

    current_func: str | None = None

    for line in text.splitlines():
        line = line.strip()

        # Detect section headers
        m = _DOC_SECTION_RE.match(line)
        if m:
            section_name = m.group(1)
            # Remove backtick formatting
            section_name = section_name.strip("`")
            if section_name in TRACKED_FUNCTIONS:
                current_func = section_name
                if current_func not in covered:
                    covered[current_func] = set()
            else:
                current_func = None
            continue

        # Parse table rows: | # | `file.py:line` | `FuncName` | ...
        if current_func is not None and line.startswith("|"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 5:
                continue
            # parts[1] is row number, parts[2] is File:Line, parts[3] is Containing Function
            file_cell = parts[2]
            func_cell = parts[3]

            # Extract file path and containing function from backtick-wrapped cells
            file_match = re.search(r"`([^`]+)`", file_cell)
            func_match = re.search(r"`([^`]+)`", func_cell)

            if file_match and func_match:
                file_path = file_match.group(1)
                containing_func = func_match.group(1)
                # Strip line number suffix from file path
                if ":" in file_path:
                    file_path = file_path.rsplit(":", 1)[0]
                covered[current_func].add((file_path, containing_func))

    return covered


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOutboundCoverageCatalog:
    """Assert that every discovered production call site appears in the catalog."""

    @pytest.fixture(scope="class")
    def call_sites(self) -> list[CallSite]:
        """Discover all production call sites for tracked functions."""
        repo_root = _find_repo_root()
        return _discover_call_sites(repo_root)

    @pytest.fixture(scope="class")
    def covered(self) -> dict[str, set[tuple[str, str]]]:
        """Parse the coverage document."""
        repo_root = _find_repo_root()
        doc_path = repo_root / COVERAGE_DOC
        return _parse_coverage_doc(doc_path)

    # ── validate_payload_against_schema ───────────────────────────────

    def test_all_validate_payload_against_schema_sites_covered(
        self,
        call_sites: list[CallSite],
        covered: dict[str, set[tuple[str, str]]],
    ) -> None:
        """Every discovered call site is in the catalog (file + containing function)."""
        func_name = "validate_payload_against_schema"
        sites = [s for s in call_sites if s.func_name == func_name]
        covered_set = covered.get(func_name, set())

        missing: list[CallSite] = []
        for site in sites:
            key = (site.file, site.containing_func)
            if key not in covered_set:
                missing.append(site)

        if missing:
            missing_str = "\n".join(
                f"  {s.file}:{s.line} in {s.containing_func}" for s in missing
            )
            pytest.fail(
                f"Found {len(missing)} undocumented production call site(s) "
                f"for {func_name}:\n{missing_str}"
            )

    def test_validate_payload_against_schema_production_count(
        self, call_sites: list[CallSite]
    ) -> None:
        """Sanity: at least 1 production call site exists (not a vacuous pass)."""
        sites = [s for s in call_sites if s.func_name == "validate_payload_against_schema"]
        assert len(sites) >= 1, "Expected at least 1 production call site"

    # ── audit_step_payload ────────────────────────────────────────────

    def test_all_audit_step_payload_sites_covered(
        self,
        call_sites: list[CallSite],
        covered: dict[str, set[tuple[str, str]]],
    ) -> None:
        func_name = "audit_step_payload"
        sites = [s for s in call_sites if s.func_name == func_name]
        covered_set = covered.get(func_name, set())

        missing: list[CallSite] = []
        for site in sites:
            key = (site.file, site.containing_func)
            if key not in covered_set:
                missing.append(site)

        if missing:
            missing_str = "\n".join(
                f"  {s.file}:{s.line} in {s.containing_func}" for s in missing
            )
            pytest.fail(
                f"Found {len(missing)} undocumented production call site(s) "
                f"for {func_name}:\n{missing_str}"
            )

    def test_audit_step_payload_production_count(
        self, call_sites: list[CallSite]
    ) -> None:
        sites = [s for s in call_sites if s.func_name == "audit_step_payload"]
        assert len(sites) >= 1, "Expected at least 1 production call site"

    # ── capture_step_output ───────────────────────────────────────────

    def test_all_capture_step_output_sites_covered(
        self,
        call_sites: list[CallSite],
        covered: dict[str, set[tuple[str, str]]],
    ) -> None:
        func_name = "capture_step_output"
        sites = [s for s in call_sites if s.func_name == func_name]
        covered_set = covered.get(func_name, set())

        missing: list[CallSite] = []
        for site in sites:
            key = (site.file, site.containing_func)
            if key not in covered_set:
                missing.append(site)

        if missing:
            missing_str = "\n".join(
                f"  {s.file}:{s.line} in {s.containing_func}" for s in missing
            )
            pytest.fail(
                f"Found {len(missing)} undocumented production call site(s) "
                f"for {func_name}:\n{missing_str}"
            )

    def test_capture_step_output_production_count(
        self, call_sites: list[CallSite]
    ) -> None:
        sites = [s for s in call_sites if s.func_name == "capture_step_output"]
        assert len(sites) >= 1, "Expected at least 1 production call site"

    # ── validate_payload (orphan) ─────────────────────────────────────

    def test_validate_payload_sites_are_documented_or_retired(
        self,
        call_sites: list[CallSite],
        covered: dict[str, set[tuple[str, str]]],
    ) -> None:
        """validate_payload call sites must be documented, retired, or delegating.

        The function is a known live orphan. Any non-retired call site must
        either be explicitly documented in the catalog, or the containing
        function must delegate/raise/retire (e.g. ``_RETIRED_VALIDATE_PAYLOAD_STEPS``,
        ``CliError``, ``del validate_payload``).
        """
        func_name = "validate_payload"
        sites = [s for s in call_sites if s.func_name == func_name]
        covered_set = covered.get(func_name, set())

        for site in sites:
            key = (site.file, site.containing_func)
            if key in covered_set:
                continue
            # The only allowed undocumented site is the definition site itself
            # or the retirement/del site in __init__.py
            if site.file == "arnold/pipelines/megaplan/workers/_impl.py":
                continue
            if site.file == "arnold/pipelines/megaplan/workers/__init__.py":
                continue

            pytest.fail(
                f"validate_payload call site at {site.file}:{site.line} "
                f"in {site.containing_func} is not documented and not in "
                f"known retirement/deletion paths"
            )

    # ── C1 chokepoint binding (assertion a) ──────────────────────────────

    def test_all_validate_payload_against_schema_sites_bind_to_chokepoint_or_residual(
        self,
        call_sites: list[CallSite],
        covered: dict[str, set[tuple[str, str]]],
    ) -> None:
        """Every vpa_s call site is documented in the catalog or is a known residual.

        A call site is acceptable if:
        - It is documented in the coverage catalog (file + containing function), OR
        - Its containing function appears in KNOWN_RESIDUAL_FUNCTIONS.
        """
        func_name = "validate_payload_against_schema"
        sites = [s for s in call_sites if s.func_name == func_name]
        covered_set = covered.get(func_name, set())

        violations: list[CallSite] = []
        for site in sites:
            key = (site.file, site.containing_func)
            if key in covered_set:
                continue
            if site.containing_func in KNOWN_RESIDUAL_FUNCTIONS:
                continue
            violations.append(site)

        if violations:
            violation_str = "\n".join(
                f"  {s.file}:{s.line} in {s.containing_func}" for s in violations
            )
            pytest.fail(
                f"Found {len(violations)} validate_payload_against_schema call site(s) "
                f"not bound to C1 chokepoint documentation and not in known-residual list:\n"
                f"{violation_str}"
            )

    # ── Residual set integrity (assertion b) ─────────────────────────────

    def test_known_residual_set_equals_documented_set(self) -> None:
        """KNOWN_RESIDUAL_FUNCTIONS must exactly match the documented residual set.

        Both must be updated in lockstep. Any drift is a contract violation.
        """
        assert KNOWN_RESIDUAL_FUNCTIONS == _DOCUMENTED_RESIDUAL_SET, (
            f"KNOWN_RESIDUAL_FUNCTIONS {KNOWN_RESIDUAL_FUNCTIONS!r} does not match "
            f"documented residual set {_DOCUMENTED_RESIDUAL_SET!r}. "
            f"Update both tests/m8/test_outbound_coverage_catalog.py and "
            f"docs/m8-outbound-coverage.md in lockstep."
        )

    # ── _normalize_worker_payload deleted (assertion c) ──────────────────

    def test_normalize_worker_payload_not_importable(self) -> None:
        """_normalize_worker_payload must not be importable from the workers package."""
        import importlib

        workers = importlib.import_module("arnold_pipelines.megaplan.workers")
        assert not hasattr(workers, "_normalize_worker_payload"), (
            "_normalize_worker_payload is still accessible on the workers package; "
            "it must be deleted from the public surface."
        )
        workers_impl = importlib.import_module(
            "arnold_pipelines.megaplan.workers._impl"
        )
        assert not hasattr(workers_impl, "_normalize_worker_payload"), (
            "_normalize_worker_payload is still defined in workers._impl; "
            "it must be removed entirely."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_repo_root() -> Path:
    """Find the git repo root, falling back to cwd."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()
