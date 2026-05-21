"""Smoke tests for handle_init's joke-mode arg validation (--mode/--output).

T14 (0.23): retained as LEGACY-path coverage in the explicit joke
three-way split. See ``tests/test_joke_mode_smoke.py`` module docstring
for the full split (LEGACY here + NEW ``tests/pipelines/test_creative_pipeline.py``
+ DEPRECATION ``tests/test_mode_deprecation.py``). Keeping all three is
required by USER DECISION 2.
"""
from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli
from megaplan.types import CliError


def _bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

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
    return root, project_dir


def _args(project_dir: Path, **overrides: object) -> Namespace:
    data: dict[str, object] = {
        "plan": None,
        "idea": "joke-mode test",
        "name": None,
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": "standard",
        "agent": None,
        "mode": "code",
        "output": None,
        "primary_criterion": None,
        "from_doc": None,
        "hermes": None,
    }
    data.update(overrides)
    return Namespace(**data)


def _load_state(root: Path, plan_name: str) -> dict:
    plan_dir = megaplan.plans_root(root) / plan_name
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


def test_joke_mode_accepts_relative_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    response = megaplan.handle_init(
        root,
        _args(project_dir, name="joke-plan", mode="joke", output="scenes/cafe.md"),
    )
    state = _load_state(root, response["plan"])
    assert state["config"]["mode"] == "joke"
    assert state["config"]["form"] == "joke"
    assert state["config"]["output_path"] == "scenes/cafe.md"


def test_joke_mode_requires_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(root, _args(project_dir, mode="joke", output=None))
    assert info.value.code == "invalid_args"
    assert "--output" in str(info.value)


def test_joke_mode_persists_primary_criterion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    response = megaplan.handle_init(
        root,
        _args(
            project_dir,
            name="joke-primary-criterion",
            mode="joke",
            output="scenes/cafe.md",
            primary_criterion="weirdest coherent",
        ),
    )
    state = _load_state(root, response["plan"])
    assert state["config"]["mode"] == "joke"
    assert state["config"]["primary_criterion"] == "weirdest coherent"


def test_primary_criterion_is_rejected_outside_joke_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            _args(
                project_dir,
                mode="doc",
                output="docs/design.md",
                primary_criterion="weirdest coherent",
            ),
        )
    assert info.value.code == "invalid_args"
    assert "--primary-criterion" in str(info.value)
