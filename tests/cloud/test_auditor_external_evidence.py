from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path
from typing import Any


def _module() -> Any:
    return importlib.import_module("arnold_pipelines.megaplan.cloud.auditor_external_evidence")


def _completed(
    args: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init")
    _git(path, "config", "user.email", "tests@example.invalid")
    _git(path, "config", "user.name", "Cloud Tests")
    tracked = path / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
    tracked.mkdir(parents=True, exist_ok=True)
    (tracked / "arnold-watchdog").write_text("echo watchdog\n", encoding="utf-8")
    (path / "tests" / "arnold_pipelines" / "megaplan").mkdir(parents=True, exist_ok=True)
    (path / "tests" / "arnold_pipelines" / "megaplan" / "test_import_smoke.py").write_text(
        "def test_import_smoke() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    (path / ".megaplan").mkdir(parents=True, exist_ok=True)
    (path / ".megaplan" / "local-only.txt").write_text("ignored bookkeeping\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial fixture")


def test_collect_ci_health_reports_red_for_failing_base_branch_runs() -> None:
    module = _module()
    calls: list[list[str]] = []

    def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:4] == ["gh", "run", "list", "--branch"]:
            return _completed(
                args,
                stdout=json.dumps(
                    [
                        {
                            "databaseId": 101,
                            "headBranch": "main",
                            "status": "completed",
                            "conclusion": "failure",
                            "workflowName": "main-ci",
                            "url": "https://example.invalid/runs/101",
                        },
                        {
                            "databaseId": 102,
                            "headBranch": "main",
                            "status": "completed",
                            "conclusion": "success",
                            "workflowName": "lint",
                            "url": "https://example.invalid/runs/102",
                        },
                    ]
                ),
            )
        if args[:3] == ["gh", "pr", "checks"]:
            return _completed(args, stdout="build\tfail\tlink\n")
        raise AssertionError(f"unexpected command: {args}")

    result = module.collect_ci_health(Path("/repo"), base_branch="main", runner=runner)

    assert result["status"] == "red"
    assert result["available"] is True
    assert result["base_branch"] == "main"
    assert result["failing_run_count"] == 1
    assert result["failed_checks"]
    assert ["gh", "run", "list", "--branch", "main"] == calls[0][:5]


def test_collect_ci_health_reports_green_when_main_is_healthy() -> None:
    module = _module()
    calls: list[list[str]] = []

    def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:4] == ["gh", "run", "list", "--branch"]:
            return _completed(
                args,
                stdout=json.dumps(
                    [
                        {
                            "databaseId": 201,
                            "headBranch": "main",
                            "status": "completed",
                            "conclusion": "success",
                            "workflowName": "main-ci",
                            "url": "https://example.invalid/runs/201",
                        }
                    ]
                ),
            )
        if args[:3] == ["gh", "pr", "checks"]:
            return _completed(args, stdout="build\tpass\tlink\nlint\tpass\tlink\n")
        raise AssertionError(f"unexpected command: {args}")

    result = module.collect_ci_health(Path("/repo"), base_branch="main", runner=runner)

    assert result["status"] == "green"
    assert result["available"] is True
    assert result["failing_run_count"] == 0
    assert result["failed_checks"] == []
    assert any(call[:3] == ["gh", "pr", "checks"] for call in calls)


def test_pr_health_is_not_red_from_unrelated_base_failure() -> None:
    module = _module()

    def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        if args[:4] == ["gh", "run", "list", "--branch"]:
            return _completed(
                args,
                stdout=json.dumps(
                    [{"status": "completed", "conclusion": "failure", "workflowName": "base-ci"}]
                ),
            )
        if args[:3] == ["gh", "pr", "checks"]:
            return _completed(args, stdout="build\tpass\tlink\n")
        raise AssertionError(f"unexpected command: {args}")

    result = module.collect_ci_health(
        Path("/repo"), base_branch="release", pr_number=255, runner=runner
    )

    assert result["status"] == "green"
    assert result["pr_status"] == "green"
    assert result["base_status"] == "red"
    assert result["failing_run_count"] == 1
    assert result["base_branch"] == "release"


def test_collect_ci_health_reports_unavailable_when_gh_cannot_run() -> None:
    module = _module()

    def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(args[0])

    result = module.collect_ci_health(Path("/repo"), base_branch="main", runner=runner)

    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert result["reason"] == "gh_unavailable"


def test_collect_engine_tree_reports_red_for_dirty_shared_files_and_divergent_mirror(
    tmp_path: Path,
) -> None:
    module = _module()
    primary = tmp_path / "primary"
    sibling = tmp_path / "sibling"
    _init_repo(primary)
    subprocess.run(
        ["git", "clone", str(primary), str(sibling)],
        capture_output=True,
        text=True,
        check=True,
    )
    _git(sibling, "config", "user.email", "tests@example.invalid")
    _git(sibling, "config", "user.name", "Cloud Tests")
    (sibling / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-watchdog").write_text(
        "echo sibling divergence\n",
        encoding="utf-8",
    )
    _git(sibling, "add", ".")
    _git(sibling, "commit", "-m", "sibling diverged")

    (primary / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-watchdog").write_text(
        "echo dirty primary\n",
        encoding="utf-8",
    )
    (primary / ".megaplan" / "local-only.txt").write_text("still ignored\n", encoding="utf-8")

    result = module.collect_engine_tree_evidence(
        primary,
        workspace_root=tmp_path,
        candidate_mirror_roots=[primary, sibling],
    )

    assert result["status"] == "red"
    assert result["available"] is True
    assert "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog" in result["dirty_paths"]
    assert ".megaplan/local-only.txt" not in result["dirty_paths"]
    assert result["divergent_mirrors"]
    assert result["impacted_consumers"]


def test_collect_engine_tree_reports_green_for_clean_matching_mirrors(tmp_path: Path) -> None:
    module = _module()
    primary = tmp_path / "primary"
    sibling = tmp_path / "sibling"
    _init_repo(primary)
    subprocess.run(
        ["git", "clone", str(primary), str(sibling)],
        capture_output=True,
        text=True,
        check=True,
    )

    result = module.collect_engine_tree_evidence(
        primary,
        workspace_root=tmp_path,
        candidate_mirror_roots=[primary, sibling],
    )

    assert result["status"] == "green"
    assert result["available"] is True
    assert result["dirty_paths"] == []
    assert result["divergent_mirrors"] == []
    assert result["impacted_consumers"] == []


def test_collect_engine_tree_reports_unavailable_when_git_status_is_unavailable() -> None:
    module = _module()

    def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(args[0])

    result = module.collect_engine_tree_evidence(
        Path("/repo"),
        workspace_root=Path("/workspace"),
        candidate_mirror_roots=[Path("/repo")],
        runner=runner,
    )

    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert result["reason"] == "git_unavailable"
