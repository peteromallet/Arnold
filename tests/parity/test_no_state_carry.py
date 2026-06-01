"""M6 guard: planning STATE_* symbols must not become shared mechanisms."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TYPES_PATH = REPO_ROOT / "megaplan/types.py"

STATE_OWNER_OR_ADAPTER_FILES = frozenset(
    {
        "megaplan/__init__.py",
        "megaplan/_core/__init__.py",
        "megaplan/_core/state.py",
        "megaplan/_core/workflow.py",
        "megaplan/_core/workflow_data.py",
        "megaplan/_legacy_subprocess/__init__.py",
        "megaplan/auto.py",
        "megaplan/chain/__init__.py",
        "megaplan/cli/__init__.py",
        "megaplan/cli/feedback.py",
        "megaplan/cli/status_view.py",
        "megaplan/execute/_binding/reducer.py",
        "megaplan/execute/batch.py",
        "megaplan/execute/step_edit.py",
        "megaplan/execute/timeout.py",
        "megaplan/handlers/critique.py",
        "megaplan/handlers/execute.py",
        "megaplan/handlers/finalize.py",
        "megaplan/handlers/gate.py",
        "megaplan/handlers/init.py",
        "megaplan/handlers/override.py",
        "megaplan/handlers/plan.py",
        "megaplan/handlers/review.py",
        "megaplan/handlers/tiebreaker.py",
        "megaplan/handlers/verifiability.py",
        "megaplan/planning/control_binding.py",
    }
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _planning_state_symbols() -> frozenset[str]:
    tree = ast.parse(_source(TYPES_PATH), filename=_relative(TYPES_PATH))
    symbols: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("STATE_"):
                    symbols.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.startswith("STATE_"):
                symbols.add(node.target.id)
    return frozenset(symbols)


def _state_identifier_refs(path: Path, state_symbols: frozenset[str]) -> list[str]:
    tree = ast.parse(_source(path), filename=_relative(path))
    refs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.name
                asname = alias.asname or alias.name
                if name in state_symbols or asname in state_symbols:
                    refs.append(f"{node.lineno}:import:{name}")
        elif isinstance(node, ast.Name) and node.id in state_symbols:
            refs.append(f"{node.lineno}:name:{node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in state_symbols:
            refs.append(f"{node.lineno}:attr:{node.attr}")
    return refs


def test_no_planning_state_symbols_escape_state_owners_or_adapters() -> None:
    """Allow state-machine owners and the planning-owned binding adapter only."""
    state_symbols = _planning_state_symbols()
    violations: list[str] = []

    for path in sorted((REPO_ROOT / "megaplan").rglob("*.py")):
        rel_path = _relative(path)
        if rel_path == "megaplan/types.py" or rel_path.startswith("megaplan/agent/"):
            continue
        refs = _state_identifier_refs(path, state_symbols)
        if refs and rel_path not in STATE_OWNER_OR_ADAPTER_FILES:
            violations.append(f"{rel_path}: {', '.join(refs)}")

    assert violations == [], (
        "Planning STATE_* identifiers leaked outside state owners/adapters. "
        "Use RunOutcome/ControlBinding or a binding-local projection instead:\n"
        + "\n".join(violations)
    )


def test_shared_mechanism_surfaces_do_not_bind_to_planning_state_symbols() -> None:
    """The shared M5c/M6 mechanism surfaces stay app-vocabulary free."""
    state_symbols = _planning_state_symbols()
    mechanism_surfaces = (
        "megaplan/control_interface.py",
        "megaplan/run_outcome.py",
        "megaplan/_pipeline/pattern_types.py",
        "megaplan/_pipeline/pattern_dynamic.py",
        "megaplan/_pipeline/pattern_joins.py",
        "megaplan/_pipeline/pattern_topology.py",
        "megaplan/_pipeline/patterns.py",
        "megaplan/_pipeline/subloop.py",
        "megaplan/_pipeline/builder.py",
    )
    violations = {
        rel_path: _state_identifier_refs(REPO_ROOT / rel_path, state_symbols)
        for rel_path in mechanism_surfaces
    }
    violations = {path: refs for path, refs in violations.items() if refs}

    assert violations == {}, (
        "Shared mechanism surfaces must not carry planning STATE_* symbols: "
        f"{violations}"
    )
