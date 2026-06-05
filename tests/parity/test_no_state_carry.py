"""M6 guard: planning STATE_* symbols must not become shared mechanisms."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TYPES_PATH = REPO_ROOT / "arnold/pipelines/megaplan/types.py"

STATE_OWNER_OR_ADAPTER_FILES = frozenset(
    {
        "arnold/pipelines/megaplan/__init__.py",
        "arnold/pipelines/megaplan/_core/__init__.py",
        "arnold/pipelines/megaplan/_core/state.py",
        "arnold/pipelines/megaplan/_core/workflow.py",
        "arnold/pipelines/megaplan/_core/workflow_data.py",
        "arnold/pipelines/megaplan/_legacy_subprocess/__init__.py",
        "arnold/pipelines/megaplan/auto.py",
        "arnold/pipelines/megaplan/chain/__init__.py",
        "arnold/pipelines/megaplan/cli/__init__.py",
        "arnold/pipelines/megaplan/cli/feedback.py",
        "arnold/pipelines/megaplan/cli/status_view.py",
        "arnold/pipelines/megaplan/execute/_binding/reducer.py",
        "arnold/pipelines/megaplan/execute/batch.py",
        "arnold/pipelines/megaplan/execute/step_edit.py",
        "arnold/pipelines/megaplan/execute/timeout.py",
        "arnold/pipelines/megaplan/handlers/critique.py",
        "arnold/pipelines/megaplan/handlers/execute.py",
        "arnold/pipelines/megaplan/handlers/finalize.py",
        "arnold/pipelines/megaplan/handlers/gate.py",
        "arnold/pipelines/megaplan/handlers/init.py",
        "arnold/pipelines/megaplan/handlers/override.py",
        "arnold/pipelines/megaplan/handlers/plan.py",
        "arnold/pipelines/megaplan/handlers/review.py",
        "arnold/pipelines/megaplan/handlers/tiebreaker.py",
        "arnold/pipelines/megaplan/handlers/verifiability.py",
        "arnold/pipelines/megaplan/planning/control_binding.py",
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

    for path in sorted((REPO_ROOT / "arnold" / "pipelines" / "megaplan").rglob("*.py")):
        rel_path = _relative(path)
        if rel_path == "arnold/pipelines/megaplan/types.py" or rel_path.startswith("arnold/pipelines/megaplan/agent/"):
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
        "arnold/pipelines/megaplan/control_interface.py",
        "arnold/pipelines/megaplan/run_outcome.py",
        "arnold/pipelines/megaplan/_pipeline/pattern_types.py",
        "arnold/pipelines/megaplan/_pipeline/pattern_dynamic.py",
        "arnold/pipelines/megaplan/_pipeline/pattern_joins.py",
        "arnold/pipelines/megaplan/_pipeline/pattern_topology.py",
        "arnold/pipelines/megaplan/_pipeline/patterns.py",
        "arnold/pipelines/megaplan/_pipeline/subloop.py",
        "arnold/pipelines/megaplan/_pipeline/builder.py",
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
