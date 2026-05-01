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
    monkeypatch.setattr(megaplan._core.shutil, "which", lambda name: "/usr/bin/mock")
    monkeypatch.setattr(io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)
    return root, project_dir


def _args(project_dir: Path, **overrides: object) -> Namespace:
    data: dict[str, object] = {
        "plan": None,
        "idea": "creative mode test",
        "name": None,
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": "standard",
        "agent": None,
        "mode": "creative",
        "form": "joke",
        "output": "out.md",
        "primary_criterion": None,
        "from_doc": None,
        "hermes": None,
    }
    data.update(overrides)
    return Namespace(**data)


def _load_state(root: Path, plan_name: str) -> dict:
    return json.loads((megaplan.plans_root(root) / plan_name / "state.json").read_text(encoding="utf-8"))


def test_creative_joke_init_persists_form(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    response = megaplan.handle_init(root, _args(project_dir, name="creative-joke", form="joke", output="jokes/j.md"))
    state = _load_state(root, response["plan"])

    assert state["config"]["mode"] == "creative"
    assert state["config"]["form"] == "joke"
    assert state["config"]["output_path"] == "jokes/j.md"


def test_creative_requires_form(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(root, _args(project_dir, form=None))

    assert info.value.code == "invalid_args"
    assert "--form" in str(info.value)


def test_creative_poem_accepts_primary_criterion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project_dir = _bootstrap(tmp_path, monkeypatch)
    response = megaplan.handle_init(
        root,
        _args(
            project_dir,
            name="creative-poem",
            form="poem",
            output="poems/p.md",
            primary_criterion="tightest image",
        ),
    )
    state = _load_state(root, response["plan"])

    assert state["config"]["form"] == "poem"
    assert state["config"]["primary_criterion"] == "tightest image"
