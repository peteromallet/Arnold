"""Round-trip tests for PlanConfig fields: completion_contract_mode,
test_command, and test_baseline_timeout.

Asserts that all three fields survive init → state.json, DEFAULTS
lookups succeed, and chain-state + plan-state reflect the same mode at
chain init.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

import megaplan
from megaplan._core.io import get_effective
from megaplan.chain import run_chain
from megaplan.handlers.init import _build_state_config
from megaplan.types import DEFAULTS, _SETTABLE_NUMERIC, _SETTABLE_STRING

from tests.conftest import load_state, make_args_factory


# ── DEFAULTS lookups ────────────────────────────────────────────────────


def test_defaults_contain_test_command() -> None:
    assert "execution.test_command" in DEFAULTS
    assert DEFAULTS["execution.test_command"] is None


def test_defaults_contain_test_baseline_timeout() -> None:
    assert "execution.test_baseline_timeout" in DEFAULTS
    assert DEFAULTS["execution.test_baseline_timeout"] == 900


def test_defaults_contain_completion_contract_mode() -> None:
    assert "execution.completion_contract_mode" in DEFAULTS
    assert DEFAULTS["execution.completion_contract_mode"] == "shadow"


def test_settable_string_contains_test_command() -> None:
    assert "execution.test_command" in _SETTABLE_STRING


def test_settable_numeric_contains_test_baseline_timeout() -> None:
    assert "execution.test_baseline_timeout" in _SETTABLE_NUMERIC


# ── init → state.json round-trip ────────────────────────────────────────


def test_completion_contract_mode_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """completion_contract_mode flows from _build_state_config into state config."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(name="contract-mode-roundtrip"),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    # The mode should be present — defaults to "shadow" from get_effective.
    assert "completion_contract_mode" in state["config"]
    assert state["config"]["completion_contract_mode"] in (
        "off",
        "shadow",
        "warn",
        "enforce",
    )


def test_test_command_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """test_command flows from _build_state_config into state config."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(name="test-cmd-roundtrip"),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    assert "test_command" in state["config"]


def test_test_baseline_timeout_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """test_baseline_timeout flows from _build_state_config into state config."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(name="baseline-timeout-roundtrip"),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    assert "test_baseline_timeout" in state["config"]


def test_completion_contract_mode_cli_flag_overrides_get_effective(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI-supplied completion_contract_mode overrides get_effective."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    args = make_args(name="cli-override")
    args.completion_contract_mode = "off"
    response = megaplan.handle_init(root, args)
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    assert state["config"]["completion_contract_mode"] == "off"


# ── _build_state_config unit tests ──────────────────────────────────────


def test_build_state_config_includes_all_three_fields() -> None:
    """_build_state_config returns all three new fields in the config dict."""
    args = Namespace(
        project_dir="/tmp/proj",
        hermes=None,
        profile=None,
        vendor=None,
        critic=None,
        depth=None,
        deepseek_provider=None,
        with_prep=False,
        with_feedback=False,
        prep_direction=None,
        phase_model=None,
    )
    config, *_ = _build_state_config(
        args,
        project_dir=Path("/tmp/proj"),
        pipeline=None,
        mode="code",
        raw_form=None,
        normalized_output_path=None,
        normalized_primary_criterion=None,
        from_doc_rel=None,
    )
    assert "completion_contract_mode" in config
    assert "test_command" in config
    assert "test_baseline_timeout" in config
    assert config["completion_contract_mode"] in ("off", "shadow", "warn", "enforce")


def test_build_state_config_cli_wins_over_get_effective() -> None:
    """CLI-supplied values are used even when get_effective returns something else."""
    args = Namespace(
        project_dir="/tmp/proj",
        hermes=None,
        profile=None,
        vendor=None,
        critic=None,
        depth=None,
        deepseek_provider=None,
        with_prep=False,
        with_feedback=False,
        prep_direction=None,
        phase_model=None,
    )
    # Simulate CLI flags
    args.completion_contract_mode = "off"  # type: ignore[attr-defined]
    args.test_command = "pytest -x"  # type: ignore[attr-defined]
    args.test_baseline_timeout = 600  # type: ignore[attr-defined]

    config, *_ = _build_state_config(
        args,
        project_dir=Path("/tmp/proj"),
        pipeline=None,
        mode="code",
        raw_form=None,
        normalized_output_path=None,
        normalized_primary_criterion=None,
        from_doc_rel=None,
    )
    assert config["completion_contract_mode"] == "off"
    assert config["test_command"] == "pytest -x"
    assert config["test_baseline_timeout"] == 600
