"""T12 — Import-scan coverage for evidence-pack and retired examples.

Ensures both evidence-pack packages (canonical + shim) contain no forbidden
graph-era surfaces and the retired ``_deliberation_example`` package cannot
silently return:

* ``arnold.workflow.dsl`` — the legacy DSL import surface.
* ``PipelineBuilder`` — the legacy fluent builder.
* ``AgentStep`` — the legacy agent step class.
* ``ContractStatus`` hook inspection — importing ``ContractStatus`` inside a
  file that also imports from ``arnold.execution.hooks`` (the graph-era hook
  protocol).

Checks are performed via AST import analysis plus plain-text symbol scans
so that even commented-out or docstring references do not escape detection
(any reference is a potential copy-paste risk for future contributors).
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

# ── Target packages ─────────────────────────────────────────────────────────

_CANONICAL_EVIDENCE_PACK = Path("arnold/pipelines/evidence_pack")
_SHIM_EVIDENCE_PACK = Path("arnold_pipelines/evidence_pack")
_RETIRED_DELIBERATION_EXAMPLE = Path("arnold/pipelines/_deliberation_example")
_RETIRED_DELIBERATION_EXAMPLE_MODULE = "arnold.pipelines._deliberation_example"

_TARGET_PACKAGES: tuple[Path, ...] = (
    _CANONICAL_EVIDENCE_PACK,
    _SHIM_EVIDENCE_PACK,
)

# ── Forbidden surfaces ─────────────────────────────────────────────────────

#: Graph-era DSL module that must never appear as an import.
FORBIDDEN_DSL_MODULE = "arnold.workflow.dsl"

#: Graph-era symbols that must never appear in source text (any reference,
#: even in comments/docstrings, is a risk of copy-paste reintroduction).
FORBIDDEN_SYMBOLS: tuple[str, ...] = ("PipelineBuilder", "AgentStep")

#: Graph-era hook protocol that, when combined with ``ContractStatus``,
#: indicates a legacy hook-inspection pattern.
FORBIDDEN_EXECUTION_HOOKS_PREFIX = "arnold.execution.hooks"


# ── Helpers ─────────────────────────────────────────────────────────────────


def _collect_python_files(pkg: Path) -> list[Path]:
    """Return all ``.py`` files under *pkg*, sorted for determinism."""
    return sorted(pkg.rglob("*.py"))


def _ast_imports(path: Path) -> set[str]:
    """Return the set of module names imported (statically) by *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _imports_forbidden_dsl(path: Path) -> set[str]:
    """Return any ``arnold.workflow.dsl`` (or sub-module) imports in *path*."""
    return {
        name
        for name in _ast_imports(path)
        if name == FORBIDDEN_DSL_MODULE or name.startswith(FORBIDDEN_DSL_MODULE + ".")
    }


def _symbols_in_text(path: Path) -> set[str]:
    """Return any of ``FORBIDDEN_SYMBOLS`` found anywhere in the file text."""
    text = path.read_text(encoding="utf-8")
    return {sym for sym in FORBIDDEN_SYMBOLS if sym in text}


def _has_contract_status_hook_inspection(path: Path) -> bool:
    """Return True if *path* imports both ``ContractStatus`` and graph-era hooks.

    "ContractStatus hook inspection" means a file that inspects
    ``ContractStatus`` (from any module) while also importing from
    ``arnold.execution.hooks`` — the graph-era hook protocol.  The native
    hook protocol uses ``arnold.pipeline.native.hooks`` and may legitimately
    reference ``ContractStatus``; that is *not* flagged.
    """
    imports = _ast_imports(path)
    has_exec_hooks = any(
        name == FORBIDDEN_EXECUTION_HOOKS_PREFIX
        or name.startswith(FORBIDDEN_EXECUTION_HOOKS_PREFIX + ".")
        for name in imports
    )
    if not has_exec_hooks:
        return False

    text = path.read_text(encoding="utf-8")
    return "ContractStatus" in text


# ── Tests ───────────────────────────────────────────────────────────────────


def test_evidence_pack_packages_have_no_forbidden_dsl_imports() -> None:
    """No file imports ``arnold.workflow.dsl`` (or any sub-module)."""
    violations: dict[str, list[str]] = {}
    for pkg in _TARGET_PACKAGES:
        for py_file in _collect_python_files(pkg):
            forbidden = _imports_forbidden_dsl(py_file)
            if forbidden:
                violations[str(py_file)] = sorted(forbidden)

    assert not violations, (
        f"Files import forbidden graph-era DSL module "
        f"'{FORBIDDEN_DSL_MODULE}':\n"
        + "\n".join(f"  {f}: {v}" for f, v in violations.items())
    )


def test_evidence_pack_packages_have_no_pipeline_builder_or_agent_step() -> None:
    """No file contains ``PipelineBuilder`` or ``AgentStep`` in source text."""
    violations: dict[str, list[str]] = {}
    for pkg in _TARGET_PACKAGES:
        for py_file in _collect_python_files(pkg):
            found = _symbols_in_text(py_file)
            if found:
                violations[str(py_file)] = sorted(found)

    assert not violations, (
        "Files contain forbidden graph-era symbols "
        f"({FORBIDDEN_SYMBOLS}):\n"
        + "\n".join(f"  {f}: {v}" for f, v in violations.items())
    )


def test_evidence_pack_packages_have_no_contract_status_hook_inspection() -> None:
    """No file combines ``ContractStatus`` with ``arnold.execution.hooks`` imports.

    Only the graph-era ``arnold.execution.hooks`` + ``ContractStatus``
    combination is forbidden.
    """
    violations: list[str] = []
    for pkg in _TARGET_PACKAGES:
        for py_file in _collect_python_files(pkg):
            if _has_contract_status_hook_inspection(py_file):
                violations.append(str(py_file))

    assert not violations, (
        "Files combine ContractStatus with graph-era execution hooks "
        f"('{FORBIDDEN_EXECUTION_HOOKS_PREFIX}'):\n"
        + "\n".join(f"  {f}" for f in violations)
    )


def test_retired_deliberation_example_is_absent_and_nonimportable() -> None:
    """The archived graph-era example must not re-enter the runtime package."""
    assert not _RETIRED_DELIBERATION_EXAMPLE.exists(), (
        f"retired runtime package returned: {_RETIRED_DELIBERATION_EXAMPLE}"
    )
    assert importlib.util.find_spec(_RETIRED_DELIBERATION_EXAMPLE_MODULE) is None
