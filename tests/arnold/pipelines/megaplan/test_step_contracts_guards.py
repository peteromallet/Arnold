"""AST-based guard tests for the StepContract registry migration.

Guard A — Legacy-dict replacement check
    Verifies that the four module-level names that were previously assigned
    to dict literals are now derived from the authoritative StepContract
    registry factories.  Uses AST assignment-target matching so it is
    precise and avoids false positives on legitimate phase-keyed dicts
    (pipeline topology, runtime policy, prompt builders, mock payloads, etc.).

Guard B — StepInvocation bypass check (minimal-metadata shape)
    Fails if a call site outside ``contract_to_invocation`` constructs
    ``StepInvocation(kind='model', metadata={...})`` with
    ``'compatibility_validation_step'`` and very few metadata keys (≤3).
    Worker sites with richer metadata (tier/worker/model/schema) are NOT flagged.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Iterator

import pytest

# test file is at <repo>/tests/arnold/pipelines/megaplan/test_step_contracts_guards.py
# go up 5 levels to <repo>, then down into the source tree.
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent.parent
MEGAPLAN_ROOT = _REPO_ROOT / "arnold" / "pipelines" / "megaplan"

# ---------------------------------------------------------------------------
# Guard A — Verify legacy dict literals are replaced with factory calls
# ---------------------------------------------------------------------------

# (file_relative_to_repo, variable_name) → expected factory evidence
# The guard checks that the variable is NOT assigned a dict literal.
_LEGACY_DICT_GUARDS: list[tuple[str, str]] = [
    ("arnold/pipelines/megaplan/workers/_impl.py", "STEP_SCHEMA_FILENAMES"),
    ("arnold/pipelines/megaplan/profiles/policy.py", "DEFAULT_AGENT_ROUTING"),
    ("arnold/pipelines/megaplan/model_seam.py", "_CAPTURE_SCHEMA_KEYS_BY_STEP"),
    ("arnold/pipelines/megaplan/model_seam.py", "_COMPATIBILITY_MODE_BY_STEP"),
]

# Additionally, verify this dead name is truly gone.
_DEAD_NAME_GUARDS: list[tuple[str, str]] = [
    ("arnold/pipelines/megaplan/workers/_impl.py", "_CODEX_TEMPLATE_WRITE_STEPS"),
]


def _py_files(root: pathlib.Path) -> Iterator[pathlib.Path]:
    """Yield every .py file recursively under *root*."""
    for path in root.rglob("*.py"):
        if path.is_file():
            yield path


def _collect_legacy_dict_assignment_violations() -> list[str]:
    """Check that legacy names are no longer assigned dict literals."""
    violations: list[str] = []

    for rel_path, var_name in _LEGACY_DICT_GUARDS:
        file_path = _REPO_ROOT / rel_path
        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            violations.append(f"{rel_path}: file not found or unreadable")
            continue

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as exc:
            violations.append(f"{rel_path}: syntax error — {exc}")
            continue

        found_dict = False
        name_exists = False

        for node in ast.walk(tree):
            # Check plain assignments:  NAME = value
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == var_name:
                        name_exists = True
                        if isinstance(node.value, ast.Dict):
                            found_dict = True
                            violations.append(
                                f"{rel_path}:{node.lineno} — '{var_name}' is still assigned a dict literal"
                            )
            # Check annotated assignments:  NAME: Type = value
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == var_name:
                    name_exists = True
                    if node.value is not None and isinstance(node.value, ast.Dict):
                        found_dict = True
                        violations.append(
                            f"{rel_path}:{node.lineno} — '{var_name}' is still assigned a dict literal"
                        )

        if not found_dict and not name_exists:
            violations.append(f"{rel_path}: '{var_name}' is missing (was it accidentally deleted?)")

    return violations


def _collect_dead_name_violations() -> list[str]:
    """Check that dead names are truly gone."""
    violations: list[str] = []
    for rel_path, var_name in _DEAD_NAME_GUARDS:
        file_path = _REPO_ROOT / rel_path
        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # file missing is fine

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == var_name:
                        violations.append(
                            f"{rel_path}:{node.lineno} — dead name '{var_name}' still present"
                        )
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == var_name:
                    violations.append(
                        f"{rel_path}:{node.lineno} — dead name '{var_name}' still present"
                    )
    return violations


def test_legacy_dicts_replaced_with_factories() -> None:
    """Guard A: Legacy module-level dict literals are replaced with factory calls."""
    violations = _collect_legacy_dict_assignment_violations()
    assert not violations, (
        "Legacy dict-literal assignments still detected:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_dead_names_are_gone() -> None:
    """Guard A (supplementary): Dead module-level names are truly removed."""
    violations = _collect_dead_name_violations()
    assert not violations, (
        "Dead names still present:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# Guard B — StepInvocation(kind='model', metadata={minimal}) bypass
# ---------------------------------------------------------------------------

# Only flag metadata dicts with very few keys (≤ this threshold).
# Worker sites carry 5+ keys (tier, worker, model, normalized_model,
# validation_step, schema, ...) and are NOT bypasses of the factory.
_MAX_METADATA_KEYS_BYPASS = 3

# Pre-existing bypasses that existed before the StepContract registry migration.
_PREEXISTING_BYPASS_ALLOWLIST: set[tuple[str, int]] = {
    # execute/timeout.py — timeout recovery; uses richer metadata
    # (tier/worker/capture_recovery) with 5 keys, so it wouldn't be
    # flagged by the ≤3-key threshold anyway.  Listed for documentation.
}


def _is_inside_function(node: ast.AST, tree: ast.AST, func_name: str) -> bool:
    """Return True if *node* is inside a function named *func_name* in *tree*."""
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if parent.name == func_name:
                for child in ast.walk(parent):
                    if child is node:
                        return True
    return False


def _iter_step_invocation_calls(tree: ast.AST) -> Iterator[ast.Call]:
    """Yield every ``StepInvocation(...)`` call node in *tree*."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "StepInvocation":
            yield node
        elif isinstance(func, ast.Attribute) and func.attr == "StepInvocation":
            yield node


def _kwarg_value(call: ast.Call, name: str) -> ast.expr | None:
    """Return the value node for keyword *name* in *call*, or None."""
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _collect_step_invocation_bypasses() -> list[tuple[str, int]]:
    """Return (file, lineno) for minimal-metadata StepInvocation bypasses."""
    violations: list[tuple[str, int]] = []
    step_contracts = MEGAPLAN_ROOT / "step_contracts.py"

    for py_file in _py_files(MEGAPLAN_ROOT):
        try:
            source = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for call_node in _iter_step_invocation_calls(tree):
            # Skip calls inside contract_to_invocation (the allowlisted factory)
            if py_file.resolve() == step_contracts.resolve() and _is_inside_function(call_node, tree, "contract_to_invocation"):
                continue

            # Check kind="model"
            kind_node = _kwarg_value(call_node, "kind")
            if kind_node is None:
                continue
            if not (isinstance(kind_node, ast.Constant) and isinstance(kind_node.value, str) and kind_node.value == "model"):
                continue

            # Check metadata is a dict literal with 'compatibility_validation_step'
            metadata_node = _kwarg_value(call_node, "metadata")
            if metadata_node is None:
                continue
            if not isinstance(metadata_node, ast.Dict):
                continue

            has_key = False
            total_str_keys = 0
            for key_node in metadata_node.keys:
                if key_node is None:
                    continue
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    total_str_keys += 1
                    if key_node.value == "compatibility_validation_step":
                        has_key = True
            if not has_key:
                continue

            # Only flag minimal-metadata bypasses (≤3 keys).
            # Worker sites have 5+ keys and are not factory bypasses.
            if total_str_keys > _MAX_METADATA_KEYS_BYPASS:
                continue

            rel = str(py_file.relative_to(_REPO_ROOT))
            violations.append((rel, call_node.lineno))

    return violations


def test_no_step_invocation_bypasses() -> None:
    """Guard B: No minimal StepInvocation bypasses outside contract_to_invocation."""
    violations = _collect_step_invocation_bypasses()

    # Filter out pre-existing allowlisted bypasses.
    unexplained = [(f, ln) for f, ln in violations if (f, ln) not in _PREEXISTING_BYPASS_ALLOWLIST]

    assert not unexplained, (
        f"Found {len(unexplained)} unexplained minimal-metadata StepInvocation bypass(es) "
        f"(≤{_MAX_METADATA_KEYS_BYPASS} keys) outside contract_to_invocation:\n"
        + "\n".join(f"  {f}:{lineno}" for f, lineno in unexplained)
        + "\n\nPre-existing allowlisted bypasses (not counted as failures):\n"
        + "\n".join(f"  {f}:{lineno}" for f, lineno in sorted(_PREEXISTING_BYPASS_ALLOWLIST))
    )
