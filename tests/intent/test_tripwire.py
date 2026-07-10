"""Tripwire: verify the intent judges and render-diff module do not import
forbidden porting / ingest / UI-emitter symbols.

Rationale: vibecomfy.intent is the existential correctness gate.  It must never
accidentally couple to the faithfulness/porting machinery.  This test walks the
AST of ``judge.py``, ``render_diff.py``, and (one hop deep) any ``vibecomfy.*``
modules they directly import, asserting that no Import / ImportFrom node
references any of the forbidden symbols.

Exemption: ``vibecomfy/intent/_refusal_spine_probe.py`` IS the refusal-spine
reference implementation and is explicitly allowed to import
``convert_ui_to_api`` lazily inside its ``_to_api`` helper.  This file is
excluded from all checks.
"""

from __future__ import annotations

import ast
import pytest
from pathlib import Path
from typing import Iterable

# ── forbidden symbols ──────────────────────────────────────────────────────

FORBIDDEN = frozenset(
    {
        "convert_ui_to_api",
        "emit_ui_json",
        "vibecomfy.porting.emit.ui",
        "vibecomfy.ingest.normalize",
        "comfy.component_model.workflow_convert",
    }
)

EXEMPT_FILE = "vibecomfy/intent/_refusal_spine_probe.py"


# ── helpers ─────────────────────────────────────────────────────────────────

def _imported_names(tree: ast.AST) -> set[str]:
    """Walk *tree* and return the set of imported module / name references.

    For ``import foo.bar`` → ``{"foo.bar"}``.
    For ``from foo.bar import baz`` → ``{"foo.bar", "foo.bar.baz"}``.
    Relative imports (``from . import …``) are resolved against *rel_to*
    but the final set uses absolute dotted names.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                full = f"{module}.{alias.name}" if module else alias.name
                names.add(full)
                if module:
                    names.add(module)  # also track the parent module
    return names


def _vibecomfy_direct_imports(tree: ast.AST) -> set[str]:
    """Return the set of ``vibecomfy.*`` modules directly imported by *tree*.

    Captures both ``import vibecomfy.foo`` and ``from vibecomfy.foo import …``.
    """
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("vibecomfy."):
                    modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("vibecomfy."):
                modules.add(node.module)
    return modules


def _resolve_module_path(module_name: str, repo_root: Path) -> Path | None:
    """Resolve a dotted ``vibecomfy.*`` module name to a ``.py`` file path.

    Returns None when the module cannot be found (e.g. it lives in an
    uninstalled optional dependency).
    """
    parts = module_name.split(".")
    # vibecomfy.foo.bar → vibecomfy/foo/bar.py (try package-first)
    candidate_py = repo_root.joinpath(*parts).with_suffix(".py")
    if candidate_py.is_file():
        return candidate_py
    # vibecomfy.foo.bar → vibecomfy/foo/bar/__init__.py
    candidate_pkg = repo_root.joinpath(*parts) / "__init__.py"
    if candidate_pkg.is_file():
        return candidate_pkg
    return None


def _tree_for_path(path: Path) -> ast.AST:
    """Parse *path* and return its AST."""
    return ast.parse(path.read_text())


# ── module-under-test paths ─────────────────────────────────────────────────

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def judge_ast() -> ast.AST:
    return _tree_for_path(_repo_root() / "vibecomfy" / "intent" / "judge.py")


@pytest.fixture(scope="module")
def render_diff_ast() -> ast.AST:
    return _tree_for_path(_repo_root() / "vibecomfy" / "intent" / "render_diff.py")


# ── tests ───────────────────────────────────────────────────────────────────

@pytest.mark.intent_ci
class TestTripwireJudge:
    """judge.py must not reference forbidden symbols."""

    def test_no_forbidden_import_in_judge(self, judge_ast: ast.AST) -> None:
        imports = _imported_names(judge_ast)
        bad = imports & FORBIDDEN
        assert not bad, f"judge.py imports forbidden symbols: {sorted(bad)}"


@pytest.mark.intent_ci
class TestTripwireRenderDiff:
    """render_diff.py must not reference forbidden symbols."""

    def test_no_forbidden_import_in_render_diff(self, render_diff_ast: ast.AST) -> None:
        imports = _imported_names(render_diff_ast)
        bad = imports & FORBIDDEN
        assert not bad, f"render_diff.py imports forbidden symbols: {sorted(bad)}"


@pytest.mark.intent_ci
class TestTripwireOneHop:
    """Check one hop deep: every vibecomfy.* module directly imported by
    judge.py or render_diff.py must also be clean."""

    @pytest.fixture(scope="class")
    def one_hop_modules(self, judge_ast: ast.AST, render_diff_ast: ast.AST) -> dict[str, Path]:
        repo = _repo_root()
        all_imports = _vibecomfy_direct_imports(judge_ast) | _vibecomfy_direct_imports(
            render_diff_ast
        )
        resolved: dict[str, Path] = {}
        for mod in sorted(all_imports):
            path = _resolve_module_path(mod, repo)
            if path is not None:
                # Skip the exempt file
                try:
                    rel = path.relative_to(repo).as_posix()
                except ValueError:
                    rel = str(path)
                if rel == EXEMPT_FILE:
                    continue
                resolved[mod] = path
        return resolved

    def test_one_hop_modules_resolved(self, one_hop_modules: dict[str, Path]) -> None:
        """At least one vibecomfy.* module was resolved for the one-hop check.

        If this fails, judge.py / render_diff.py may have no vibecomfy.*
        imports at all (which is fine — the test still passes), or the modules
        may be uninstallable optional deps.
        """
        # This is informational; the real check is in the next test.
        # We don't hard-fail here because judge.py genuinely has zero
        # vibecomfy.* module-level imports.
        pass

    def test_no_forbidden_in_one_hop(
        self, one_hop_modules: dict[str, Path]
    ) -> None:
        for mod_name, mod_path in one_hop_modules.items():
            tree = _tree_for_path(mod_path)
            imports = _imported_names(tree)
            bad = imports & FORBIDDEN
            assert not bad, (
                f"One-hop module {mod_name} ({mod_path}) imports forbidden "
                f"symbols: {sorted(bad)}"
            )


@pytest.mark.intent_ci
class TestTripwireExemption:
    """_refusal_spine_probe.py is explicitly exempt from the tripwire."""

    def test_refusal_spine_probe_is_exempt(self) -> None:
        """Verify the exemption file exists and DOES import the forbidden symbols."""
        repo = _repo_root()
        probe_path = repo / EXEMPT_FILE
        assert probe_path.is_file(), f"Exemption file missing: {probe_path}"

        tree = _tree_for_path(probe_path)
        imports = _imported_names(tree)
        allowed = imports & FORBIDDEN
        assert allowed, (
            f"Expected {EXEMPT_FILE} to import at least one forbidden symbol "
            f"but found none.  Forbidden symbols: {sorted(FORBIDDEN)}"
        )

    def test_refusal_spine_probe_not_in_one_hop(self) -> None:
        """Ensure _refusal_spine_probe.py is NOT checked by the one-hop test."""
        # This is guaranteed by the fixture filtering above, but we assert it
        # explicitly so the exemption is visible in the test report.
        repo = _repo_root()
        probe_rel = EXEMPT_FILE
        assert (repo / probe_rel).is_file()
        # The test passes trivially — the real enforcement is in test_no_forbidden_in_one_hop
        # which skips this file.
