from __future__ import annotations

import json
from argparse import Namespace
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

import pytest

import megaplan
import megaplan.profiles as profiles_module
from megaplan.profiles import apply_profile_expansion, load_profiles
from megaplan.types import CliError
from megaplan.workers import resolve_agent_mode


def _write_profiles(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _worker_args(**overrides: object) -> Namespace:
    data: dict[str, object] = {
        "agent": None,
        "confirm_self_review": False,
        "ephemeral": False,
        "fresh": False,
        "hermes": None,
        "persist": False,
        "phase_model": [],
        "profile": None,
    }
    data.update(overrides)
    return Namespace(**data)


def _init_args(project_dir: Path, **overrides: object) -> Namespace:
    data: dict[str, object] = {
        "agent": None,
        "auto_approve": False,
        "auto_start": False,
        "from_doc": None,
        "hermes": None,
        "idea": "profile-backed idea",
        "idea_file": None,
        "mode": "code",
        "name": "profile-state",
        "output": None,
        "phase_model": [],
        "primary_criterion": None,
        "profile": None,
        "project_dir": str(project_dir),
        "robustness": "standard",
    }
    data.update(overrides)
    return Namespace(**data)


def test_profiles_package_layout_and_builtins_only(tmp_path: Path) -> None:
    from megaplan.profiles import apply_profile_expansion as imported_apply_profile_expansion
    from megaplan.profiles import load_profiles as imported_load_profiles

    package_entries = {
        entry.name
        for entry in files("megaplan.profiles").iterdir()
        if entry.is_file()
    }
    assert {
        "standard.toml",
        "all-open.toml",
        "all-deepseek-pro.toml",
        "all-deepseek-flash.toml",
        "all-fireworks-deepseek.toml",
    }.issubset(package_entries)

    profiles = imported_load_profiles(home=tmp_path / "home", project_dir=tmp_path / "project")

    assert imported_apply_profile_expansion is apply_profile_expansion
    assert {
        "standard",
        "all-open",
        "all-deepseek-pro",
        "all-deepseek-flash",
        "all-fireworks-deepseek",
    }.issubset(profiles)


def test_load_profiles_user_and_project_layers_replace_lower_priority_profiles(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    builtins_only = load_profiles(home=home, project_dir=project_dir)
    assert {
        "standard",
        "all-open",
        "all-deepseek-pro",
        "all-deepseek-flash",
        "all-fireworks-deepseek",
    }.issubset(builtins_only)

    user_path = home / ".config" / "megaplan" / "profiles.toml"
    _write_profiles(
        user_path,
        """
        [profiles.standard]
        execute = "codex"

        [profiles.user-only]
        review = "claude"
        """,
    )

    user_layer = load_profiles(home=home, project_dir=project_dir)
    assert user_layer["standard"] == {"execute": "codex"}
    assert user_layer["user-only"] == {"review": "claude"}

    project_path = project_dir / ".megaplan" / "profiles.toml"
    _write_profiles(
        project_path,
        """
        [profiles.standard]
        execute = "hermes:deepseek/deepseek-v3"

        [profiles.project-only]
        plan = "codex"
        """,
    )

    project_layer = load_profiles(home=home, project_dir=project_dir)
    assert project_layer["standard"] == {"execute": "hermes:deepseek/deepseek-v3"}
    assert project_layer["user-only"] == {"review": "claude"}
    assert project_layer["project-only"] == {"plan": "codex"}


def test_load_profiles_rejects_invalid_phase_key_with_path_and_key(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bad_path = home / ".config" / "megaplan" / "profiles.toml"
    _write_profiles(
        bad_path,
        """
        [profiles.bad]
        not_a_phase = "claude"
        """,
    )

    with pytest.raises(CliError) as exc_info:
        load_profiles(home=home, project_dir=tmp_path / "project")

    assert exc_info.value.code == "invalid_profile"
    assert str(bad_path) in exc_info.value.message
    assert "not_a_phase" in exc_info.value.message


def test_load_profiles_rejects_invalid_agent_spec(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bad_path = home / ".config" / "megaplan" / "profiles.toml"
    _write_profiles(
        bad_path,
        """
        [profiles.bad]
        execute = "foo:bar"
        """,
    )

    with pytest.raises(CliError) as exc_info:
        load_profiles(home=home, project_dir=tmp_path / "project")

    assert exc_info.value.code == "invalid_profile"
    assert str(bad_path) in exc_info.value.message
    assert "foo" in exc_info.value.message


def test_apply_profile_expansion_preserves_ad_hoc_precedence_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: tmp_path / ".config" / "megaplan",
    )

    args = _worker_args(profile="all-open", phase_model=["execute=claude"])

    apply_profile_expansion(args, None)
    expanded_once = list(args.phase_model)
    apply_profile_expansion(args, None)

    assert args.phase_model == expanded_once

    with patch("megaplan.workers._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)
    assert agent == "claude"
    assert model is None

    profile_only = _worker_args(profile="all-open")
    apply_profile_expansion(profile_only, None)

    with patch("megaplan.workers._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", profile_only)
    assert agent == "hermes"
    assert model == "glm-5.1"


def test_apply_profile_expansion_persisted_cli_override_beats_profile_default_on_step_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: when init persists a CLI --phase-model override that the
    profile also specifies, a later step subprocess (which auto.py spawns
    without re-passing CLI flags) must honor the persisted CLI override,
    not the profile default.
    """
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: tmp_path / ".config" / "megaplan",
    )

    # Step 1: simulate `megaplan init --profile all-open --phase-model plan=claude`.
    # all-open's profile default for `plan` is hermes:moonshotai/kimi-k2.6;
    # the CLI override pins it to claude.
    init_args = _worker_args(profile="all-open", phase_model=["plan=claude"])
    apply_profile_expansion(init_args, None)

    # init resolves plan -> claude in-process (first-match-wins).
    with patch("megaplan.workers._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("plan", init_args)
    assert agent == "claude"
    assert model is None

    # Step 2: persist the expanded list into plan state, as handlers/init.py would.
    persisted_state = {
        "config": {
            "profile": "all-open",
            "phase_model": list(init_args.phase_model),
        }
    }

    # Step 3: simulate the step subprocess auto.py spawns: profile is in state,
    # but `args.phase_model` is empty because the CLI flags weren't re-passed.
    step_args = _worker_args(profile=None, phase_model=[])
    apply_profile_expansion(step_args, None, state=persisted_state)

    # Persisted CLI override must beat the profile default.
    with patch("megaplan.workers._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("plan", step_args)
    assert agent == "claude", (
        f"Step subprocess clobbered persisted CLI override: resolved plan to "
        f"{agent!r} with model={model!r} instead of claude. "
        f"phase_model={step_args.phase_model!r}"
    )
    assert model is None

    # And: the override entry must precede any profile entry for the same phase
    # in the resolved list, since resolve_agent_mode is first-match-wins.
    plan_entries = [pm for pm in step_args.phase_model if pm.startswith("plan=")]
    assert plan_entries, f"expected a plan= entry, got {step_args.phase_model!r}"
    assert plan_entries[0] == "plan=claude", (
        f"persisted CLI override must appear before profile default; got {plan_entries!r}"
    )


def test_apply_profile_expansion_falls_back_to_state_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: tmp_path / ".config" / "megaplan",
    )

    args = _worker_args(profile=None, phase_model=[])
    state = {"config": {"project_dir": str(tmp_path), "profile": "all-open"}}

    apply_profile_expansion(args, None, state=state)

    with patch("megaplan.workers._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)
    assert agent == "hermes"
    assert model == "glm-5.1"
    assert args.profile == "all-open"


def test_all_deepseek_pro_profile_uses_native_deepseek_v4_pro(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: tmp_path / ".config" / "megaplan",
    )

    args = _worker_args(profile="all-deepseek-pro")
    apply_profile_expansion(args, None)

    with patch("megaplan.workers._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)

    assert agent == "hermes"
    assert model == "deepseek:deepseek-v4-pro"


@pytest.mark.parametrize(
    ("profile_name", "expected_model"),
    [
        ("all-deepseek-flash", "deepseek:deepseek-v4-flash"),
        (
            "all-fireworks-deepseek",
            "fireworks:accounts/fireworks/models/deepseek-v3p2",
        ),
    ],
)
def test_provider_profiles_use_expected_native_model(
    profile_name: str,
    expected_model: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: tmp_path / ".config" / "megaplan",
    )

    args = _worker_args(profile=profile_name)
    apply_profile_expansion(args, None)

    with patch("megaplan.workers._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)

    assert agent == "hermes"
    assert model == expected_model


def test_apply_profile_expansion_unknown_profile_lists_known_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: tmp_path / ".config" / "megaplan",
    )

    with pytest.raises(CliError) as exc_info:
        apply_profile_expansion(Namespace(profile="nope", phase_model=[]), None)

    assert exc_info.value.code == "unknown_profile"
    assert "all-open" in exc_info.value.message
    assert "standard" in exc_info.value.message


def test_handle_init_persists_profile_name_in_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: tmp_path / ".config" / "megaplan",
    )

    response = megaplan.handle_init(
        root,
        _init_args(project_dir, profile="all-open"),
    )
    state_path = megaplan.plans_root(root) / response["plan"] / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert state["config"]["profile"] == "all-open"


def test_handle_config_profiles_list_and_show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    user_config_dir = tmp_path / ".config" / "megaplan"
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(profiles_module, "config_dir", lambda home=None: user_config_dir)

    _write_profiles(
        user_config_dir / "profiles.toml",
        """
        [profiles.user-only]
        review = "claude"
        """,
    )
    _write_profiles(
        project_dir / ".megaplan" / "profiles.toml",
        """
        [profiles.project-only]
        execute = "codex"
        """,
    )

    listed = megaplan.handle_config(
        Namespace(config_action="profiles", profiles_action="list")
    )
    shown = megaplan.handle_config(
        Namespace(config_action="profiles", profiles_action="show", name="all-open")
    )

    assert listed["success"] is True
    assert listed["action"] == "profiles"
    assert listed["profiles_action"] == "list"
    assert {entry["source"] for entry in listed["profiles"]} == {"built-in", "user", "project"}
    assert ("all-open", "built-in") in {
        (entry["name"], entry["source"]) for entry in listed["profiles"]
    }

    assert shown["success"] is True
    assert shown["action"] == "profiles"
    assert shown["profiles_action"] == "show"
    assert shown["name"] == "all-open"
    assert shown["profile"]["execute"] == "hermes:glm-5.1"
    assert shown["profile"]["review"] == "hermes:glm-5.1"
