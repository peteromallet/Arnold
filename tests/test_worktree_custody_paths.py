from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest

from megaplan.worktrees import (
    custody_paths,
    custody_report_dir,
    custody_report_path,
    ensure_megaplan_worktrees_ignored,
    patch_bundle_dir,
    patch_manifest_path,
    patch_payload_path,
    patch_task_dir,
    registry_head_path,
    registry_jsonl_path,
    registry_lock_path,
    scratch_task_worktree_path,
    scratch_worktree_path,
    scratch_worktree_root_path,
    secret_scan_report_path,
    validate_run_id,
    validate_task_id,
)


def test_custody_paths_are_project_level_and_centralized(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    plan_dir = project_dir / ".megaplan" / "plans" / "plan-1"
    plan_dir.mkdir(parents=True)
    paths = custody_paths(project_dir)

    assert paths.custody_root == project_dir / ".megaplan" / "worktrees"
    assert paths.registry_dir == project_dir / ".megaplan" / "worktrees" / "registry"
    assert paths.patches_dir == project_dir / ".megaplan" / "worktrees" / "patches"
    assert paths.reports_dir == project_dir / ".megaplan" / "worktrees" / "custody-reports"
    assert paths.secrets_dir == project_dir / ".megaplan" / "worktrees" / "secrets"
    assert paths.scratch_worktrees_dir == project_dir / ".megaplan-worktrees"

    assert paths.registry_jsonl("run_1") == paths.registry_dir / "run_1.jsonl"
    assert paths.registry_head("run_1") == paths.registry_dir / "run_1.head.json"
    assert paths.registry_lock("run_1") == paths.registry_dir / "run_1.lock"
    assert paths.patch_run_dir("run_1") == paths.patches_dir / "run_1"
    assert paths.patch_task_dir("run_1", "T5") == paths.patches_dir / "run_1" / "task-T5"
    assert paths.patch_manifest("run_1", "T5") == paths.patch_task_dir("run_1", "T5") / "manifest.json"
    assert paths.patch_payload("run_1", "T5") == paths.patch_task_dir("run_1", "T5") / "bundle.patch"
    assert paths.custody_report_dir("run_1") == paths.reports_dir / "run_1"
    assert paths.custody_report("run_1") == paths.reports_dir / "run_1" / "report.json"
    assert paths.secret_scan_report("run_1", "T5") == paths.secrets_dir / "run_1" / "task-T5.json"
    assert paths.scratch_worktree("run_1", "T5") == project_dir / ".megaplan-worktrees" / "run_1" / "task-T5"
    assert paths.scratch_task_worktree("run_1", "t5-abc123") == project_dir / ".megaplan-worktrees" / "run_1" / "task-t5-abc123"

    for path in [
        paths.registry_jsonl("run_1"),
        paths.registry_head("run_1"),
        paths.registry_lock("run_1"),
        paths.patch_manifest("run_1", "T5"),
        paths.patch_payload("run_1", "T5"),
        paths.custody_report("run_1"),
        paths.secret_scan_report("run_1", "T5"),
    ]:
        assert plan_dir not in path.parents


def test_narrow_module_helpers_delegate_to_central_layout(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    paths = custody_paths(project_dir)

    assert registry_jsonl_path(project_dir, "run-2") == paths.registry_jsonl("run-2")
    assert registry_head_path(project_dir, "run-2") == paths.registry_head("run-2")
    assert registry_lock_path(project_dir, "run-2") == paths.registry_lock("run-2")
    assert patch_bundle_dir(project_dir, "run-2") == paths.patch_run_dir("run-2")
    assert patch_task_dir(project_dir, "run-2", "T5") == paths.patch_task_dir("run-2", "T5")
    assert patch_manifest_path(project_dir, "run-2", "T5") == paths.patch_manifest("run-2", "T5")
    assert patch_payload_path(project_dir, "run-2", "T5") == paths.patch_payload("run-2", "T5")
    assert custody_report_dir(project_dir) == paths.reports_dir
    assert custody_report_path(project_dir, "run-2") == paths.custody_report("run-2")
    assert secret_scan_report_path(project_dir, "run-2", "T5") == paths.secret_scan_report("run-2", "T5")
    assert scratch_worktree_root_path(project_dir) == paths.scratch_worktrees_dir
    assert scratch_worktree_path(project_dir, "run-2", "T5") == paths.scratch_worktree("run-2", "T5")
    assert scratch_task_worktree_path(project_dir, "run-2", "t5-abc123") == paths.scratch_task_worktree("run-2", "t5-abc123")


@pytest.mark.parametrize(
    "bad_id",
    ["", ".", "..", ".hidden", "run/id", "run\\id", "run id", "run:id", "$run", "a" * 81],
)
def test_custody_ids_reject_pathlike_or_unallowlisted_values(bad_id: str) -> None:
    with pytest.raises(ValueError):
        validate_run_id(bad_id)
    with pytest.raises(ValueError):
        validate_task_id(bad_id)


def test_custody_ids_accept_conservative_allowlist() -> None:
    assert validate_run_id("run-ABC_123") == "run-ABC_123"
    assert validate_task_id("T5") == "T5"


def test_ensure_megaplan_worktrees_ignored_is_idempotent(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    gitignore = project_dir / ".gitignore"
    gitignore.write_text("__pycache__/\n.megaplan-worktrees/\n", encoding="utf-8")

    assert ensure_megaplan_worktrees_ignored(project_dir) == gitignore
    assert ensure_megaplan_worktrees_ignored(project_dir) == gitignore

    assert gitignore.read_text(encoding="utf-8").splitlines().count(".megaplan-worktrees/") == 1


def test_ensure_megaplan_worktrees_ignored_creates_missing_gitignore(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    gitignore = ensure_megaplan_worktrees_ignored(project_dir)

    assert gitignore == project_dir.resolve() / ".gitignore"
    assert gitignore.read_text(encoding="utf-8") == ".megaplan-worktrees/\n"


def test_worktrees_package_does_not_import_execute_dispatch() -> None:
    for module_name in [
        "megaplan.worktrees",
        "megaplan.execute.core",
        "megaplan.execute.migration",
    ]:
        sys.modules.pop(module_name, None)

    importlib.import_module("megaplan.worktrees")

    assert "megaplan.execute.core" not in sys.modules
    assert "megaplan.execute.migration" not in sys.modules


def test_worktree_custody_modules_do_not_reference_execute_dispatch() -> None:
    modules = [
        importlib.import_module("megaplan.worktrees"),
        importlib.import_module("megaplan.worktrees.paths"),
        importlib.import_module("megaplan.worktrees.lifecycle"),
        importlib.import_module("megaplan.worktrees.registry"),
        importlib.import_module("megaplan.worktrees.patches"),
        importlib.import_module("megaplan.worktrees.report"),
        importlib.import_module("megaplan.worktrees.secrets"),
    ]
    forbidden = ["megaplan.execute", "handle_execute", "execute.core"]

    for module in modules:
        source = inspect.getsource(module)
        assert not any(token in source for token in forbidden)
