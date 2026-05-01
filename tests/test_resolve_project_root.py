"""Regression tests for ``--project-dir`` overriding CWD-based root discovery.

Background: ``megaplan init`` (and other handlers that take ``root``) used to
resolve the project root via ``_find_megaplan_root(Path.cwd())`` regardless of
``--project-dir``. That collided when bake-off sibling worktrees living under
a directory that contained a stray ``.megaplan/`` ancestor — every parallel
``init`` would walk up to the same root and race on ``duplicate_plan``. See
``megaplan/bakeoff/orchestrator.py:_init_profile`` for the spawning side.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli
from megaplan.cli import _resolve_project_root
from megaplan.types import CliError


def _bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config"

    def _config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)


def test_resolve_project_root_prefers_project_dir(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    args = argparse.Namespace(project_dir=str(project_dir))

    resolved = _resolve_project_root(args)

    assert resolved == project_dir.resolve()


def test_resolve_project_root_rejects_missing_project_dir(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    args = argparse.Namespace(project_dir=str(missing))

    with pytest.raises(CliError) as info:
        _resolve_project_root(args)

    assert info.value.code == "invalid_project_dir"


def test_resolve_project_root_falls_back_when_flag_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_path / "fallback"
    project_dir.mkdir()
    (project_dir / ".megaplan").mkdir()
    monkeypatch.chdir(project_dir)
    args = argparse.Namespace()  # no project_dir attribute at all

    resolved = _resolve_project_root(args)

    assert resolved == project_dir.resolve()


def test_main_init_writes_plan_under_project_dir_not_cwd_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reproduces the bake-off collision: CWD-walk hits a stray ``.megaplan``
    in an ancestor, but ``--project-dir`` should win and the plan must land
    under that directory.
    """
    _bootstrap(tmp_path, monkeypatch)

    # Decoy ancestor: cwd lives under <ancestor>/cwd, and <ancestor>/.megaplan
    # exists. Without the fix, _find_megaplan_root(cwd) walks up and returns
    # <ancestor>, so the plan lands at <ancestor>/.megaplan/plans/...
    ancestor = tmp_path / "ancestor"
    ancestor.mkdir()
    (ancestor / ".megaplan").mkdir()
    cwd = ancestor / "cwd"
    cwd.mkdir()

    project_dir = tmp_path / "isolated-project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.chdir(cwd)

    exit_code = megaplan.main(
        [
            "init",
            "--project-dir",
            str(project_dir),
            "--name",
            "isolated-plan",
            "test idea",
        ]
    )
    assert exit_code == 0

    plan_dir = project_dir / ".megaplan" / "plans" / "isolated-plan"
    assert plan_dir.is_dir(), (
        f"plan should land under --project-dir, but {plan_dir} does not exist"
    )
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["config"]["project_dir"] == str(project_dir.resolve())

    # And the decoy ancestor must NOT have grown a plans/isolated-plan dir.
    decoy_plan = ancestor / ".megaplan" / "plans" / "isolated-plan"
    assert not decoy_plan.exists(), (
        f"plan leaked into CWD-walk ancestor at {decoy_plan}"
    )


def test_main_init_parallel_project_dirs_do_not_collide(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two sequential `init` calls with the same plan name but distinct
    --project-dir values must each succeed under their own root. This is the
    minimal repro of the bake-off duplicate_plan race — without the fix, both
    inits would target the same CWD-walked root and the second would fail.
    """
    _bootstrap(tmp_path, monkeypatch)

    ancestor = tmp_path / "ancestor"
    ancestor.mkdir()
    (ancestor / ".megaplan").mkdir()
    cwd = ancestor / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    project_a = tmp_path / "worktree-a"
    project_b = tmp_path / "worktree-b"
    for pd in (project_a, project_b):
        pd.mkdir()
        (pd / ".git").mkdir()

    shared_name = "shared-experiment-id"

    for project_dir in (project_a, project_b):
        capsys.readouterr()  # drain
        exit_code = megaplan.main(
            [
                "init",
                "--project-dir",
                str(project_dir),
                "--name",
                shared_name,
                "test idea",
            ]
        )
        assert exit_code == 0, capsys.readouterr().out
        assert (project_dir / ".megaplan" / "plans" / shared_name).is_dir()
