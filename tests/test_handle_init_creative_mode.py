from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan.types import CliError


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


def test_creative_joke_init_persists_form(bootstrap_fixture: tuple[Path, Path]) -> None:
    root, project_dir = bootstrap_fixture
    response = megaplan.handle_init(root, _args(project_dir, name="creative-joke", form="joke", output="jokes/j.md"))
    state = _load_state(root, response["plan"])

    assert state["config"]["mode"] == "creative"
    assert state["config"]["form"] == "joke"
    assert state["config"]["output_path"] == "jokes/j.md"


def test_creative_requires_form(bootstrap_fixture: tuple[Path, Path]) -> None:
    root, project_dir = bootstrap_fixture
    with pytest.raises(CliError) as info:
        megaplan.handle_init(root, _args(project_dir, form=None))

    assert info.value.code == "invalid_args"
    assert "--form" in str(info.value)


def test_creative_poem_accepts_primary_criterion(bootstrap_fixture: tuple[Path, Path]) -> None:
    root, project_dir = bootstrap_fixture
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
