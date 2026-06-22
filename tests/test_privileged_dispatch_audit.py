"""Static guardrails for the M2b privileged-dispatch migration.

This audit intentionally checks files, not individual functions. It locks the
consumer-level migration contract:

- migrated consumers must not fall back to privileged planning-control imports;
- public control/status callers must pass an explicit binding or plugin id;
- migrated consumers must not regress to direct registry ``run_phase`` style
  dispatch; and
- any future parked-path annotation must use ``# m2b-parked: <reason>`` and
  cannot appear in core override/control/status files.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

PLANNING_IMPLEMENTATION_FILES = {
    "arnold/pipelines/megaplan/planning/__init__.py",
    "arnold/pipelines/megaplan/planning/control_binding.py",
    "arnold/pipelines/megaplan/planning/operations.py",
}

MIGRATED_CONSUMER_FILES = {
    "arnold/pipelines/megaplan/auto.py",
    "arnold/pipelines/megaplan/control_interface.py",
    "arnold/pipelines/megaplan/control.py",
    "arnold/pipelines/megaplan/handlers/override.py",
    "arnold/pipelines/megaplan/observability/introspect.py",
    "arnold/pipelines/megaplan/cli/status_view.py",
    "arnold/pipelines/megaplan/cli/arnold.py",
    "arnold/pipelines/megaplan/_core/workflow.py",
    "arnold/pipelines/megaplan/_pipeline/run_cli.py",
    "arnold/pipelines/megaplan/supervisor/ladder.py",
    "arnold/pipelines/megaplan/supervisor/chain_runner.py",
}

CORE_NO_PARK_FILES = {
    "arnold/pipelines/megaplan/control.py",
    "arnold/pipelines/megaplan/control_interface.py",
    "arnold/pipelines/megaplan/handlers/override.py",
    "arnold/pipelines/megaplan/observability/introspect.py",
    "arnold/pipelines/megaplan/cli/status_view.py",
}

PARKED_ANNOTATION = "# m2b-parked:"


def _repo_file(rel_path: str) -> Path:
    return REPO_ROOT / rel_path


def _source(rel_path: str) -> str:
    return _repo_file(rel_path).read_text(encoding="utf-8")


def _tree(rel_path: str) -> ast.AST:
    return ast.parse(_source(rel_path), filename=rel_path)


def _imports_planning_control_surface(rel_path: str) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(_tree(rel_path)):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported = {alias.name for alias in node.names}
            if module == "arnold_pipelines.megaplan.planning.control_binding" and (
                {"planning_control_binding", "planning_run_state_view"} & imported
            ):
                violations.append(
                    f"{rel_path}:{node.lineno}: direct import from {module}"
                )
            if module == "arnold_pipelines.megaplan.planning" and (
                {"planning_control_binding", "planning_run_state_view"} & imported
            ):
                violations.append(
                    f"{rel_path}:{node.lineno}: direct import from {module}"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "arnold_pipelines.megaplan.planning.control_binding":
                    violations.append(
                        f"{rel_path}:{node.lineno}: direct import of {alias.name}"
                    )
    return violations


def _read_valid_targets_calls_without_explicit_binding(rel_path: str) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(_tree(rel_path)):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "read_valid_targets":
            continue
        has_binding_kw = any(
            keyword.arg in {"binding", "plugin_id"} for keyword in node.keywords
        )
        if len(node.args) < 2 and not has_binding_kw:
            violations.append(
                f"{rel_path}:{node.lineno}: read_valid_targets() missing explicit binding/plugin_id"
            )
    return violations


def _parked_annotations(rel_path: str) -> list[str]:
    violations: list[str] = []
    for lineno, line in enumerate(_source(rel_path).splitlines(), start=1):
        if PARKED_ANNOTATION not in line:
            continue
        reason = line.split(PARKED_ANNOTATION, 1)[1].strip()
        if rel_path in CORE_NO_PARK_FILES:
            violations.append(
                f"{rel_path}:{lineno}: core control/status/override files cannot carry {PARKED_ANNOTATION}"
            )
        elif not reason:
            violations.append(
                f"{rel_path}:{lineno}: parked annotation must carry an explicit reason"
            )
    return violations


def test_migrated_consumers_do_not_directly_import_planning_control_surface() -> None:
    violations: list[str] = []
    for rel_path in sorted(MIGRATED_CONSUMER_FILES):
        if rel_path in PLANNING_IMPLEMENTATION_FILES:
            continue
        violations.extend(_imports_planning_control_surface(rel_path))

    assert violations == []


def test_read_valid_targets_callers_pass_explicit_binding_or_plugin_id() -> None:
    caller_files = (
        "arnold/pipelines/megaplan/cli/status_view.py",
        "arnold/pipelines/megaplan/observability/introspect.py",
        "arnold/pipelines/megaplan/supervisor/ladder.py",
    )
    violations: list[str] = []
    for rel_path in caller_files:
        violations.extend(_read_valid_targets_calls_without_explicit_binding(rel_path))

    assert violations == []


def test_migrated_consumers_do_not_reintroduce_privileged_dispatch_literals() -> None:
    forbidden_literals = {
        "arnold/pipelines/megaplan/auto.py": (
            "PipelineRegistry(",
            ".run_phase(",
            "handle_override(",
            "_override_abort(",
            "_override_force_proceed(",
        ),
        "arnold/pipelines/megaplan/control_interface.py": (
            'binding="planning"',
            "binding='planning'",
            'plugin_id="planning"',
            "plugin_id='planning'",
        ),
        "arnold/pipelines/megaplan/_core/workflow.py": ("PipelineRegistry(", ".run_phase("),
        "arnold/pipelines/megaplan/_pipeline/run_cli.py": ("PipelineRegistry(", ".run_phase("),
    }

    violations: list[str] = []
    for rel_path, needles in forbidden_literals.items():
        source = _source(rel_path)
        for needle in needles:
            if needle in source:
                violations.append(f"{rel_path}: found forbidden literal {needle!r}")

    assert violations == []


def test_m2b_parked_annotations_require_reasons_and_stay_out_of_core_paths() -> None:
    violations: list[str] = []
    for rel_path in sorted(MIGRATED_CONSUMER_FILES):
        violations.extend(_parked_annotations(rel_path))

    assert violations == []
