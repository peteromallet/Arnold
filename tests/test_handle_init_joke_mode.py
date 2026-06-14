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

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan.types import CliError


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
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    response = megaplan.handle_init(
        root,
        _args(project_dir, name="joke-plan", mode="joke", output="scenes/cafe.md"),
    )
    state = _load_state(root, response["plan"])
    assert state["config"]["mode"] == "joke"
    assert state["config"]["form"] == "joke"
    assert state["config"]["output_path"] == "scenes/cafe.md"


def test_joke_mode_requires_output(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    with pytest.raises(CliError) as info:
        megaplan.handle_init(root, _args(project_dir, mode="joke", output=None))
    assert info.value.code == "invalid_args"
    assert "--output" in str(info.value)


def test_joke_mode_persists_primary_criterion(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
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
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
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
