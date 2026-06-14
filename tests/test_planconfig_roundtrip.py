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

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan._core.io import get_effective
from arnold.pipelines.megaplan.chain import run_chain
from arnold.pipelines.megaplan.handlers.init import _build_state_config
from arnold.pipelines.megaplan.types import DEFAULTS, _SETTABLE_ENUM, _SETTABLE_NUMERIC, _SETTABLE_STRING

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


def test_defaults_contain_full_suite_backstop_mode() -> None:
    assert "execution.full_suite_backstop_mode" in DEFAULTS
    assert DEFAULTS["execution.full_suite_backstop_mode"] == "shadow"


def test_settable_string_contains_test_command() -> None:
    assert "execution.test_command" in _SETTABLE_STRING


def test_settable_numeric_contains_test_baseline_timeout() -> None:
    assert "execution.test_baseline_timeout" in _SETTABLE_NUMERIC


def test_settable_enum_contains_full_suite_backstop_mode() -> None:
    assert _SETTABLE_ENUM["execution.full_suite_backstop_mode"] == (
        "off",
        "shadow",
        "enforce",
    )


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
    assert state["config"]["full_suite_backstop_mode"] in (
        "off",
        "shadow",
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
    args.full_suite_backstop_mode = "enforce"
    response = megaplan.handle_init(root, args)
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    assert state["config"]["completion_contract_mode"] == "off"
    assert state["config"]["full_suite_backstop_mode"] == "enforce"


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
    assert "full_suite_backstop_mode" in config
    assert "test_command" in config
    assert "test_baseline_timeout" in config
    assert config["completion_contract_mode"] in ("off", "shadow", "warn", "enforce")
    assert config["full_suite_backstop_mode"] in ("off", "shadow", "enforce")


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
    args.full_suite_backstop_mode = "enforce"  # type: ignore[attr-defined]
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
    assert config["full_suite_backstop_mode"] == "enforce"
    assert config["test_command"] == "pytest -x"
    assert config["test_baseline_timeout"] == 600


# ── Project-scoped config TOML tests (T4) ─────────────────────────────────


def _write_project_toml(project_dir: Path, content: str) -> Path:
    """Write a project TOML config file and return its path."""
    cfg_dir = project_dir / ".megaplan"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.toml"
    cfg_path.write_text(content, encoding="utf-8")
    return cfg_path


def test_build_state_config_uses_project_toml_test_command(
    tmp_path: Path,
) -> None:
    """_build_state_config reads test_command from project .megaplan/config.toml
    when CLI --test-command is absent."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_project_toml(
        project_dir,
        "[execution]\ntest_command = \"project-cmd\"\n",
    )

    args = Namespace(
        project_dir=str(project_dir),
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
        project_dir=project_dir,
        pipeline=None,
        mode="code",
        raw_form=None,
        normalized_output_path=None,
        normalized_primary_criterion=None,
        from_doc_rel=None,
    )
    assert config["test_command"] == "project-cmd"


def test_build_state_config_cli_overrides_project_toml_test_command(
    tmp_path: Path,
) -> None:
    """Explicit CLI --test-command wins over project .megaplan/config.toml."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_project_toml(
        project_dir,
        "[execution]\ntest_command = \"project-cmd\"\n",
    )

    args = Namespace(
        project_dir=str(project_dir),
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
    args.test_command = "cli-cmd"  # type: ignore[attr-defined]

    config, *_ = _build_state_config(
        args,
        project_dir=project_dir,
        pipeline=None,
        mode="code",
        raw_form=None,
        normalized_output_path=None,
        normalized_primary_criterion=None,
        from_doc_rel=None,
    )
    assert config["test_command"] == "cli-cmd"


def test_project_toml_critic_model_blocks_profile_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project TOML critic_model is explicit — profile metadata is NOT consulted."""
    import megaplan.handlers.init as init_mod

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_project_toml(
        project_dir,
        "[execution]\ncritic_model = \"project-model\"\n",
    )

    # Mock load_profile_metadata: if consulted, it would return a different model.
    monkeypatch.setattr(
        init_mod,
        "load_profile_metadata",
        lambda home=None, project_dir=None: {"partnered": {"critic_model": "profile-model"}},
    )

    args = Namespace(
        project_dir=str(project_dir),
        hermes=None,
        profile="partnered",
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
        project_dir=project_dir,
        pipeline=None,
        mode="code",
        raw_form=None,
        normalized_output_path=None,
        normalized_primary_criterion=None,
        from_doc_rel=None,
    )
    # Project TOML value wins — profile is never consulted.
    assert config["critic_model"] == "project-model"
    # Project-sourced values are treated as explicit.
    assert config["critic_model_explicit"] is True


def test_project_toml_adaptive_critique_blocks_profile_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project TOML adaptive_critique is explicit — profile metadata is NOT consulted."""
    import megaplan.handlers.init as init_mod

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_project_toml(
        project_dir,
        "[execution]\nadaptive_critique = true\n",
    )

    # Mock load_profile_metadata: if consulted, it would return a different value.
    monkeypatch.setattr(
        init_mod,
        "load_profile_metadata",
        lambda home=None, project_dir=None: {"partnered": {"adaptive_critique": False}},
    )

    args = Namespace(
        project_dir=str(project_dir),
        hermes=None,
        profile="partnered",
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
        project_dir=project_dir,
        pipeline=None,
        mode="code",
        raw_form=None,
        normalized_output_path=None,
        normalized_primary_criterion=None,
        from_doc_rel=None,
    )
    # Project TOML value wins — profile is never consulted.
    assert config["adaptive_critique"] is True
