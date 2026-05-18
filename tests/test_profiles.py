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
        "deepseek_provider": None,
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
        "deepseek_provider": None,
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
        "apex.toml",
        "all-open.toml",
        "all-deepseek-pro.toml",
        "all-deepseek-pro-direct.toml",
        "all-deepseek-flash.toml",
        "all-fireworks-deepseek.toml",
    }.issubset(package_entries)

    profiles = imported_load_profiles(home=tmp_path / "home", project_dir=tmp_path / "project")

    assert imported_apply_profile_expansion is apply_profile_expansion
    assert {
        "apex",
        "all-open",
        "all-deepseek-pro",
        "all-deepseek-pro-direct",
        "all-deepseek-flash",
        "all-fireworks-deepseek",
    }.issubset(profiles)


def test_load_profiles_user_and_project_layers_replace_lower_priority_profiles(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    builtins_only = load_profiles(home=home, project_dir=project_dir)
    assert {
        "apex",
        "all-open",
        "all-deepseek-pro",
        "all-deepseek-pro-direct",
        "all-deepseek-flash",
        "all-fireworks-deepseek",
    }.issubset(builtins_only)

    user_path = home / ".config" / "megaplan" / "profiles.toml"
    _write_profiles(
        user_path,
        """
        [profiles.apex]
        execute = "codex"

        [profiles.user-only]
        review = "claude"
        """,
    )

    user_layer = load_profiles(home=home, project_dir=project_dir)
    assert user_layer["apex"] == {"execute": "codex"}
    assert user_layer["user-only"] == {"review": "claude"}

    project_path = project_dir / ".megaplan" / "profiles.toml"
    _write_profiles(
        project_path,
        """
        [profiles.apex]
        execute = "hermes:deepseek/deepseek-v3"

        [profiles.project-only]
        plan = "codex"
        """,
    )

    project_layer = load_profiles(home=home, project_dir=project_dir)
    assert project_layer["apex"] == {"execute": "hermes:deepseek/deepseek-v3"}
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

    with patch("megaplan.workers._impl._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)
    assert agent == "claude"
    assert model is None

    profile_only = _worker_args(profile="all-open")
    apply_profile_expansion(profile_only, None)

    with patch("megaplan.workers._impl._is_agent_available", return_value=True):
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
    # all-open's profile default for `plan` is hermes:fireworks:accounts/fireworks/models/kimi-k2p6;
    # the CLI override pins it to claude.
    init_args = _worker_args(profile="all-open", phase_model=["plan=claude"])
    apply_profile_expansion(init_args, None)

    # init resolves plan -> claude in-process (first-match-wins).
    with patch("megaplan.workers._impl._is_agent_available", return_value=True):
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
    with patch("megaplan.workers._impl._is_agent_available", return_value=True):
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

    with patch("megaplan.workers._impl._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)
    assert agent == "hermes"
    assert model == "glm-5.1"
    assert args.profile == "all-open"


def test_all_deepseek_pro_profile_defaults_to_direct_deepseek_v4_pro(
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

    with patch("megaplan.workers._impl._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)

    assert agent == "hermes"
    assert model == "deepseek:deepseek-v4-pro"


def test_all_deepseek_pro_profile_can_explicitly_use_fireworks_deepseek_v4_pro(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: tmp_path / ".config" / "megaplan",
    )

    args = _worker_args(profile="all-deepseek-pro", deepseek_provider="fireworks")
    apply_profile_expansion(args, None)

    with patch("megaplan.workers._impl._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)

    assert agent == "hermes"
    assert model == "fireworks:accounts/fireworks/models/deepseek-v4-pro"


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

    with patch("megaplan.workers._impl._is_agent_available", return_value=True):
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
    assert "apex" in exc_info.value.message


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


def test_handle_init_persists_deepseek_provider_in_state(
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
        _init_args(project_dir, profile="partnered", deepseek_provider="direct"),
    )
    state_path = megaplan.plans_root(root) / response["plan"] / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert state["config"]["deepseek_provider"] == "direct"


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


# ---------------------------------------------------------------------------
# --vendor / --critic flag behavior
# ---------------------------------------------------------------------------


def _phase_models_to_map(phase_models: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pm in phase_models:
        if "=" not in pm:
            continue
        step, spec = pm.split("=", 1)
        out.setdefault(step, spec)  # first wins (matches resolve_agent_mode)
    return out


def _isolate_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin both the profiles loader's ``config_dir`` and the vendor-config
    default to test-controlled paths. Without this, a developer with a real
    ~/.config/megaplan/config.toml on disk would have their setting leak into
    the test."""
    fake_home_config = tmp_path / ".config" / "megaplan"
    monkeypatch.setattr(profiles_module, "config_dir", lambda home=None: fake_home_config)
    # Vendor default uses the user-config module; pin that to "claude" so
    # tests that rely on the default behavior are deterministic regardless
    # of dev-machine state.
    monkeypatch.setattr(profiles_module, "_resolve_default_vendor", lambda: "claude")


def test_vendor_codex_flips_premium_slots_on_all_claude(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="all-claude")
    args.vendor = "codex"

    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # all-claude has plan=claude, execute=claude, etc — all should become codex.
    for phase in ("plan", "prep", "critique", "revise", "gate", "finalize", "execute", "review"):
        assert resolved[phase] == "codex", (
            f"--vendor codex should have flipped {phase} from claude to codex; "
            f"got {resolved[phase]!r}"
        )


def test_vendor_codex_preserves_effort_tier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--vendor codex on an inline claude:medium profile should produce
    codex:medium everywhere — effort tier preserved through the swap."""
    _isolate_user_config(tmp_path, monkeypatch)

    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """
        [profiles.medium-claude]
        plan = "claude:medium"
        prep = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        critique = "codex:medium"
        revise = "claude:medium"
        gate = "claude:medium"
        finalize = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        execute = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        loop_plan = "claude:medium"
        loop_execute = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        review = "codex:medium"
        tiebreaker_researcher = "claude:medium"
        tiebreaker_challenger = "codex:medium"

        [profiles.medium-codex]
        plan = "codex:medium"
        prep = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        critique = "claude:medium"
        revise = "codex:medium"
        gate = "codex:medium"
        finalize = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        execute = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        loop_plan = "codex:medium"
        loop_execute = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        review = "claude:medium"
        tiebreaker_researcher = "codex:medium"
        tiebreaker_challenger = "claude:medium"
        """,
    )

    args = _worker_args(profile="medium-claude")
    args.vendor = "codex"

    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # plan/revise/gate were claude:medium → codex:medium.
    assert resolved["plan"] == "codex:medium"
    assert resolved["revise"] == "codex:medium"
    assert resolved["gate"] == "codex:medium"
    # Critique was already codex:medium — --vendor codex is monotonic ("make
    # this codex"), so it stays codex:medium.
    assert resolved["critique"] == "codex:medium"
    # Hermes deepseek prep stays on the default direct provider.
    assert resolved["prep"] == "hermes:deepseek:deepseek-v4-pro"

    # Sanity check on the inverse: medium-codex --vendor claude should
    # collapse everything premium to claude:medium.
    args2 = _worker_args(profile="medium-codex")
    args2.vendor = "claude"
    apply_profile_expansion(args2, None)
    resolved2 = _phase_models_to_map(args2.phase_model)
    assert resolved2["plan"] == "claude:medium"
    assert resolved2["critique"] == "claude:medium"
    assert resolved2["revise"] == "claude:medium"


def test_vendor_claude_is_noop_on_all_claude(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args_with_flag = _worker_args(profile="all-claude")
    args_with_flag.vendor = "claude"
    apply_profile_expansion(args_with_flag, None)

    args_no_flag = _worker_args(profile="all-claude")
    apply_profile_expansion(args_no_flag, None)

    assert _phase_models_to_map(args_with_flag.phase_model) == _phase_models_to_map(
        args_no_flag.phase_model
    )


def test_vendor_is_noop_on_profile_without_premium_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """all-deepseek-pro has no claude/codex slots — --vendor flag must be a
    silent no-op (no error, no change to the resolved phase map)."""
    _isolate_user_config(tmp_path, monkeypatch)

    baseline = _worker_args(profile="all-deepseek-pro")
    apply_profile_expansion(baseline, None)

    flagged = _worker_args(profile="all-deepseek-pro")
    flagged.vendor = "codex"
    apply_profile_expansion(flagged, None)

    assert _phase_models_to_map(baseline.phase_model) == _phase_models_to_map(
        flagged.phase_model
    )


def test_vendor_locked_profile_silently_ignores_vendor_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--vendor against a vendor_locked profile is a silent no-op: the
    locked profile's existing model assignments win, no error raised."""
    _isolate_user_config(tmp_path, monkeypatch)

    # Drop a vendor-locked profile into the user layer (we don't modify
    # built-in TOMLs in this change).
    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """
        [profiles.locked]
        vendor_locked = true
        plan = "claude"
        prep = "claude"
        critique = "codex"
        revise = "claude"
        gate = "claude"
        finalize = "claude"
        execute = "codex"
        loop_plan = "claude"
        loop_execute = "codex"
        review = "codex"
        tiebreaker_researcher = "codex"
        tiebreaker_challenger = "codex"
        """,
    )

    baseline = _worker_args(profile="locked")
    apply_profile_expansion(baseline, None)

    flagged = _worker_args(profile="locked")
    flagged.vendor = "codex"
    apply_profile_expansion(flagged, None)

    assert _phase_models_to_map(baseline.phase_model) == _phase_models_to_map(
        flagged.phase_model
    )


def test_vendor_locked_profile_silently_ignores_critic_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--critic against a vendor_locked profile is a silent no-op."""
    _isolate_user_config(tmp_path, monkeypatch)

    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """
        [profiles.locked]
        vendor_locked = true
        plan = "claude"
        prep = "claude"
        critique = "codex"
        revise = "claude"
        gate = "claude"
        finalize = "claude"
        execute = "codex"
        loop_plan = "claude"
        loop_execute = "codex"
        review = "codex"
        tiebreaker_researcher = "codex"
        tiebreaker_challenger = "codex"
        """,
    )

    baseline = _worker_args(profile="locked")
    apply_profile_expansion(baseline, None)

    flagged = _worker_args(profile="locked")
    flagged.critic = "kimi"
    apply_profile_expansion(flagged, None)

    assert _phase_models_to_map(baseline.phase_model) == _phase_models_to_map(
        flagged.phase_model
    )


def test_vendor_locked_profile_runs_without_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A vendor-locked profile must still resolve when neither flag is
    passed — locking is opt-out, not block-everything."""
    _isolate_user_config(tmp_path, monkeypatch)

    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """
        [profiles.locked]
        vendor_locked = true
        plan = "claude"
        prep = "claude"
        critique = "codex"
        revise = "claude"
        gate = "claude"
        finalize = "claude"
        execute = "codex"
        loop_plan = "claude"
        loop_execute = "codex"
        review = "codex"
        tiebreaker_researcher = "codex"
        tiebreaker_challenger = "codex"
        """,
    )

    args = _worker_args(profile="locked")
    apply_profile_expansion(args, None)

    resolved = _phase_models_to_map(args.phase_model)
    assert resolved["plan"] == "claude"
    assert resolved["critique"] == "codex"


def _write_medium_claude_profile(tmp_path: Path) -> None:
    """Write an inline claude:medium-author / codex:medium-critic profile
    used by the vendor/critic rewrite tests below."""
    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """
        [profiles.medium-claude]
        plan = "claude:medium"
        prep = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        critique = "codex:medium"
        revise = "claude:medium"
        gate = "claude:medium"
        finalize = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        execute = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        loop_plan = "claude:medium"
        loop_execute = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
        review = "codex:medium"
        tiebreaker_researcher = "claude:medium"
        tiebreaker_challenger = "codex:medium"
        """,
    )


def test_critic_kimi_rewrites_critique_and_review_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)
    _write_medium_claude_profile(tmp_path)

    args = _worker_args(profile="medium-claude")
    args.critic = "kimi"

    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    assert resolved["critique"] == "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"
    assert resolved["review"] == "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"
    # Author phases preserved.
    assert resolved["plan"] == "claude:medium"
    assert resolved["revise"] == "claude:medium"
    assert resolved["gate"] == "claude:medium"


def test_critic_cross_uses_opposite_of_resolved_vendor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--vendor codex --critic cross: vendor flips all premium to codex,
    then critic 'cross' flips just critique+review back to the *other*
    premium (claude). Effort tier preserved on each phase."""
    _isolate_user_config(tmp_path, monkeypatch)
    _write_medium_claude_profile(tmp_path)

    args = _worker_args(profile="medium-claude")
    args.vendor = "codex"
    args.critic = "cross"

    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # Author phases swapped to codex by --vendor.
    assert resolved["plan"] == "codex:medium"
    assert resolved["revise"] == "codex:medium"
    assert resolved["gate"] == "codex:medium"
    # Critic phases: medium-claude has critique=codex:medium. --vendor codex
    # leaves codex slots alone, so critique stays codex:medium after the
    # vendor pass. Then --critic cross: vendor="codex", so other="claude",
    # flipping critique+review to claude:medium.
    assert resolved["critique"] == "claude:medium"
    assert resolved["review"] == "claude:medium"


def test_critic_cross_with_default_claude_vendor_flips_critic_to_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default vendor=claude (no CLI flag) + --critic cross on all-claude:
    everything stays claude *except* critique+review, which become codex."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="all-claude")
    args.critic = "cross"

    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    assert resolved["plan"] == "claude"
    assert resolved["execute"] == "claude"
    assert resolved["critique"] == "codex"
    assert resolved["review"] == "codex"


def test_critic_errors_when_profile_lacks_critique_or_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """
        [profiles.partial]
        plan = "claude"
        execute = "claude"
        """,
    )

    args = _worker_args(profile="partial")
    args.critic = "kimi"

    with pytest.raises(CliError) as exc_info:
        apply_profile_expansion(args, None)

    assert exc_info.value.code == "invalid_critic"


def test_config_default_vendor_honored_when_flag_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When --vendor isn't passed, ~/.config/megaplan/config.toml's
    [defaults].vendor is consulted."""
    fake_home_config = tmp_path / ".config" / "megaplan"
    monkeypatch.setattr(profiles_module, "config_dir", lambda home=None: fake_home_config)

    # Point user_config at the same directory so its config.toml read
    # hits our test file.
    from megaplan._core import user_config as user_config_module
    monkeypatch.setattr(user_config_module, "config_dir", lambda home=None: fake_home_config)

    fake_home_config.mkdir(parents=True, exist_ok=True)
    (fake_home_config / "config.toml").write_text(
        '[defaults]\nvendor = "codex"\n', encoding="utf-8"
    )

    args = _worker_args(profile="all-claude")
    apply_profile_expansion(args, None)

    resolved = _phase_models_to_map(args.phase_model)
    # Config default = codex, so claude flips to codex.
    assert resolved["plan"] == "codex"
    assert resolved["execute"] == "codex"


def test_cli_vendor_flag_overrides_config_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_home_config = tmp_path / ".config" / "megaplan"
    monkeypatch.setattr(profiles_module, "config_dir", lambda home=None: fake_home_config)
    from megaplan._core import user_config as user_config_module
    monkeypatch.setattr(user_config_module, "config_dir", lambda home=None: fake_home_config)

    fake_home_config.mkdir(parents=True, exist_ok=True)
    (fake_home_config / "config.toml").write_text(
        '[defaults]\nvendor = "codex"\n', encoding="utf-8"
    )

    # Config says codex, CLI says claude → CLI wins.
    # Use all-claude so vendor swap is exercised — apex is vendor-locked.
    args = _worker_args(profile="all-claude")
    args.vendor = "claude"
    apply_profile_expansion(args, None)

    resolved = _phase_models_to_map(args.phase_model)
    # all-claude has all claude slots; --vendor claude is a no-op so they stay
    # claude even though the config default would have flipped them to codex.
    assert resolved["plan"] == "claude"
    assert resolved["critique"] == "claude"
    assert resolved["execute"] == "claude"


def test_persisted_vendor_in_state_picked_up_by_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """auto.py spawns step subprocesses without re-passing --vendor. The
    persisted state.config.vendor must be honored so the rewrite stays
    consistent across phases."""
    _isolate_user_config(tmp_path, monkeypatch)

    persisted_state = {
        "config": {
            "profile": "all-claude",
            "vendor": "codex",
        }
    }

    # Subprocess: no CLI flags re-passed.
    args = _worker_args(profile=None)
    apply_profile_expansion(args, None, state=persisted_state)

    resolved = _phase_models_to_map(args.phase_model)
    assert resolved["plan"] == "codex"
    assert resolved["execute"] == "codex"


def test_unknown_metadata_key_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unrecognised top-level keys in a profile table still error out the
    way they did before — only the explicitly-allowed metadata keys
    (currently just vendor_locked) skip phase validation."""
    _isolate_user_config(tmp_path, monkeypatch)

    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """
        [profiles.weird]
        plan = "claude"
        not_a_phase_or_metadata = "claude"
        """,
    )

    with pytest.raises(CliError) as exc_info:
        load_profiles(home=None, project_dir=tmp_path / "project")

    assert exc_info.value.code == "invalid_profile"
    assert "not_a_phase_or_metadata" in exc_info.value.message


# ---------------------------------------------------------------------------
# Tier-named catalog (solo / directed / partnered / premium / apex)
# ---------------------------------------------------------------------------


DEEPSEEK = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
DEEPSEEK_DIRECT = "hermes:deepseek:deepseek-v4-pro"
KIMI = "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"

_TIER_NAMES = ("solo", "directed", "partnered", "premium", "apex")


def test_new_tier_profiles_all_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    catalog = load_profiles(home=tmp_path / "home", project_dir=tmp_path / "project")
    for name in _TIER_NAMES:
        assert name in catalog, f"missing tier profile {name!r}: catalog={sorted(catalog)}"


def test_solo_profile_resolves_to_deepseek_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="solo")
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # solo runs DeepSeek end-to-end (including critique/review); no Kimi slot.
    for phase in (
        "plan",
        "prep",
        "critique",
        "revise",
        "gate",
        "finalize",
        "execute",
        "loop_plan",
        "loop_execute",
        "review",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
    ):
        assert resolved[phase] == DEEPSEEK_DIRECT, f"solo.{phase} should be DeepSeek, got {resolved[phase]!r}"


def test_solo_profile_is_noop_under_vendor_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """solo has no premium slots, so --vendor codex must not change anything."""
    _isolate_user_config(tmp_path, monkeypatch)

    baseline = _worker_args(profile="solo")
    apply_profile_expansion(baseline, None)

    flagged = _worker_args(profile="solo")
    flagged.vendor = "codex"
    apply_profile_expansion(flagged, None)

    assert _phase_models_to_map(baseline.phase_model) == _phase_models_to_map(
        flagged.phase_model
    )


def test_directed_profile_default_resolves_with_claude_plan_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="directed")
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # Claude on plan + loop_plan + tiebreakers.
    assert resolved["plan"] == "claude:low"
    assert resolved["loop_plan"] == "claude:low"
    assert resolved["tiebreaker_researcher"] == "claude:low"
    assert resolved["tiebreaker_challenger"] == "claude:low"
    # DeepSeek on the mechanical block + critique + review.
    for phase in ("prep", "critique", "revise", "gate", "finalize", "execute", "loop_execute", "review"):
        assert resolved[phase] == DEEPSEEK_DIRECT


def test_directed_profile_flips_to_codex_under_vendor_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="directed")
    args.vendor = "codex"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    assert resolved["plan"] == "codex:low", (
        f"directed + --vendor codex should flip plan from claude:low to codex:low; "
        f"got {resolved['plan']!r}"
    )
    assert resolved["loop_plan"] == "codex:low"
    assert resolved["tiebreaker_researcher"] == "codex:low"
    assert resolved["tiebreaker_challenger"] == "codex:low"
    # Mechanical phases + critique + review untouched (DeepSeek).
    for phase in ("prep", "critique", "revise", "gate", "finalize", "execute", "loop_execute", "review"):
        assert resolved[phase] == DEEPSEEK_DIRECT


def test_partnered_profile_default_resolves_with_claude_reasoning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered")
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    for phase in (
        "plan",
        "critique",
        "revise",
        "review",
        "loop_plan",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
    ):
        assert resolved[phase] == "claude:low", (
            f"partnered.{phase} should be claude:low, got {resolved[phase]!r}"
        )
    for phase in ("prep", "gate", "finalize", "execute", "loop_execute"):
        assert resolved[phase] == DEEPSEEK_DIRECT


def test_partnered_profile_flips_all_premium_under_vendor_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered")
    args.vendor = "codex"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    for phase in (
        "plan",
        "critique",
        "revise",
        "review",
        "loop_plan",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
    ):
        assert resolved[phase] == "codex:low", (
            f"partnered.{phase} under --vendor codex should be codex:low, got {resolved[phase]!r}"
        )
    # Mechanical phases stay DeepSeek.
    for phase in ("prep", "gate", "finalize", "execute", "loop_execute"):
        assert resolved[phase] == DEEPSEEK_DIRECT


def test_partnered_critic_kimi_overrides_critique_and_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered")
    args.critic = "kimi"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    assert resolved["critique"] == KIMI
    assert resolved["review"] == KIMI
    # Author phases preserved on the default (claude) vendor.
    assert resolved["plan"] == "claude:low"
    assert resolved["revise"] == "claude:low"


def test_partnered_critic_cross_with_default_claude_flips_critic_to_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default vendor=claude (no --vendor flag) + --critic cross: critique and
    review should flip to codex while everything else stays claude."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered")
    args.critic = "cross"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    assert resolved["critique"] == "codex:low"
    assert resolved["review"] == "codex:low"
    # Author phases stay claude.
    assert resolved["plan"] == "claude:low"
    assert resolved["revise"] == "claude:low"
    # Mechanical phases stay DeepSeek.
    assert resolved["execute"] == DEEPSEEK_DIRECT


def test_deepseek_provider_direct_rewrites_partnered_mechanical_phases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered", deepseek_provider="direct")
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    for phase in ("prep", "gate", "finalize", "execute", "loop_execute"):
        assert resolved[phase] == DEEPSEEK_DIRECT
    assert resolved["plan"] == "claude:low"
    assert resolved["critique"] == "claude:low"
    assert resolved["review"] == "claude:low"


def test_deepseek_provider_direct_composes_with_vendor_and_depth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered", deepseek_provider="direct")
    args.vendor = "codex"
    args.depth = "high"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    for phase in (
        "plan",
        "revise",
        "loop_plan",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
    ):
        assert resolved[phase] == "codex:high"
    assert resolved["critique"] == "codex:low"
    assert resolved["review"] == "codex:low"
    for phase in ("prep", "gate", "finalize", "execute", "loop_execute"):
        assert resolved[phase] == DEEPSEEK_DIRECT


def test_persisted_deepseek_provider_in_state_picked_up_by_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    persisted_state = {
        "config": {
            "profile": "partnered",
            "deepseek_provider": "direct",
        }
    }

    args = _worker_args(profile=None)
    apply_profile_expansion(args, None, state=persisted_state)
    resolved = _phase_models_to_map(args.phase_model)

    assert resolved["execute"] == DEEPSEEK_DIRECT
    assert resolved["prep"] == DEEPSEEK_DIRECT


def test_premium_profile_is_all_claude_low(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="premium")
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    for phase in (
        "plan",
        "prep",
        "critique",
        "revise",
        "gate",
        "finalize",
        "execute",
        "loop_plan",
        "loop_execute",
        "review",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
    ):
        assert resolved[phase] == "claude:low", (
            f"premium.{phase} should be claude:low, got {resolved[phase]!r}"
        )


def test_premium_profile_flips_to_codex_under_vendor_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="premium")
    args.vendor = "codex"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    for phase in (
        "plan",
        "prep",
        "critique",
        "revise",
        "gate",
        "finalize",
        "execute",
        "loop_plan",
        "loop_execute",
        "review",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
    ):
        assert resolved[phase] == "codex:low"


def test_apex_resolves_to_canonical_claude_codex_split(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apex (tier 5) is the canonical Claude-author / Codex-critic split.
    vendor_locked is metadata, not a phase, and must not leak into the
    resolved map."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="apex")
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # Spot-check the canonical split.
    assert resolved["plan"] == "claude"
    assert resolved["critique"] == "codex"
    assert resolved["execute"] == "codex"
    assert resolved["review"] == "codex"
    # vendor_locked must not be a phase entry.
    assert "vendor_locked" not in resolved


def test_apex_silently_ignores_vendor_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--vendor against apex is a silent no-op (vendor_locked)."""
    _isolate_user_config(tmp_path, monkeypatch)

    baseline = _worker_args(profile="apex")
    apply_profile_expansion(baseline, None)

    flagged = _worker_args(profile="apex")
    flagged.vendor = "codex"
    apply_profile_expansion(flagged, None)

    assert _phase_models_to_map(baseline.phase_model) == _phase_models_to_map(
        flagged.phase_model
    )


def test_apex_silently_ignores_critic_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--critic against apex is a silent no-op (vendor_locked)."""
    _isolate_user_config(tmp_path, monkeypatch)

    baseline = _worker_args(profile="apex")
    apply_profile_expansion(baseline, None)

    flagged = _worker_args(profile="apex")
    flagged.critic = "kimi"
    apply_profile_expansion(flagged, None)

    assert _phase_models_to_map(baseline.phase_model) == _phase_models_to_map(
        flagged.phase_model
    )


def test_apex_runs_without_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """vendor-locking is opt-out only: apex must still resolve when no
    --vendor / --critic flag is passed."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="apex")
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    assert resolved["plan"] == "claude"
    assert resolved["critique"] == "codex"
    assert resolved["execute"] == "codex"


# ---------------------------------------------------------------------------
# --depth flag behavior
# ---------------------------------------------------------------------------


_AUTHOR_PHASES = (
    "plan",
    "revise",
    "loop_plan",
    "tiebreaker_researcher",
    "tiebreaker_challenger",
)
_CRITIC_PHASES = ("critique", "gate", "review")
_MECHANICAL_PHASES = ("prep", "finalize", "execute", "loop_execute")


def test_depth_rewrites_author_phases_on_partnered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--depth high on partnered: every author-side claude:low becomes
    claude:high; critic phases (critique, review) stay claude:low;
    mechanical phases (DeepSeek) untouched."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered")
    args.depth = "high"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    for phase in _AUTHOR_PHASES:
        assert resolved[phase] == "claude:high", (
            f"--depth high on partnered should rewrite {phase} to claude:high; "
            f"got {resolved[phase]!r}"
        )
    # critique + review plateau at the existing depth.
    assert resolved["critique"] == "claude:low"
    assert resolved["review"] == "claude:low"
    # Mechanical phases (DeepSeek/hermes) — depth doesn't touch them beyond
    # the default provider rewrite.
    assert resolved["prep"] == "hermes:deepseek:deepseek-v4-pro"
    assert resolved["finalize"] == "hermes:deepseek:deepseek-v4-pro"
    assert resolved["execute"] == "hermes:deepseek:deepseek-v4-pro"


def test_depth_rewrites_author_phases_on_premium(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--depth medium on premium: only author phases bump to claude:medium;
    critic and mechanical phases keep their existing values."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="premium")
    args.depth = "medium"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    for phase in _AUTHOR_PHASES:
        assert resolved[phase] == "claude:medium", (
            f"--depth medium on premium should rewrite {phase} to claude:medium; "
            f"got {resolved[phase]!r}"
        )
    # Critic phases stay at the profile's existing :low.
    for phase in _CRITIC_PHASES:
        assert resolved[phase] == "claude:low", (
            f"critic phase {phase} should stay claude:low; got {resolved[phase]!r}"
        )
    # Mechanical phases stay at the profile's existing :low (premium is
    # single-vendor claude end-to-end, but depth shouldn't have touched these).
    for phase in _MECHANICAL_PHASES:
        assert resolved[phase] == "claude:low", (
            f"mechanical phase {phase} should stay claude:low; got {resolved[phase]!r}"
        )


def test_depth_is_noop_on_solo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """solo has no claude/codex slots on author phases — --depth must be a
    silent no-op."""
    _isolate_user_config(tmp_path, monkeypatch)

    baseline = _worker_args(profile="solo")
    apply_profile_expansion(baseline, None)

    flagged = _worker_args(profile="solo")
    flagged.depth = "high"
    apply_profile_expansion(flagged, None)

    assert _phase_models_to_map(baseline.phase_model) == _phase_models_to_map(
        flagged.phase_model
    )


def test_depth_after_vendor_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--vendor codex --depth high on partnered: vendor flips claude→codex
    first, then depth rewrites author phases to codex:high."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered")
    args.vendor = "codex"
    args.depth = "high"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    for phase in _AUTHOR_PHASES:
        assert resolved[phase] == "codex:high", (
            f"--vendor codex --depth high should produce codex:high on {phase}; "
            f"got {resolved[phase]!r}"
        )
    # Critic phases swapped to codex by --vendor but depth didn't bump them.
    assert resolved["critique"] == "codex:low"
    assert resolved["review"] == "codex:low"


def test_depth_honored_on_vendor_locked_apex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--depth max on apex (vendor_locked): author phases bump while
    critic + mechanical stay at default effort. vendor_locked is about
    vendor identity, not depth.

    Note: apex's tiebreaker_* slots are bare ``codex`` (critic side of
    the Claude/Codex split), so --depth still rewrites them — depth runs
    on author phases regardless of *which* premium vendor occupies the
    slot. The critic-vs-author asymmetry is enforced by phase name, not
    by which vendor is filling it."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="apex")
    args.depth = "max"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # plan / revise / loop_plan are bare "claude" → "claude:max".
    assert resolved["plan"] == "claude:max"
    assert resolved["revise"] == "claude:max"
    assert resolved["loop_plan"] == "claude:max"
    # tiebreaker_* slots are bare "codex" in apex — author-phase rewrite
    # bumps them to codex:max (depth is by-phase, not by-vendor).
    assert resolved["tiebreaker_researcher"] == "codex:max"
    assert resolved["tiebreaker_challenger"] == "codex:max"
    # Critic phases (codex) are untouched — they plateau at default effort.
    assert resolved["critique"] == "codex"
    assert resolved["review"] == "codex"
    # Mechanical phases untouched.
    assert resolved["execute"] == "codex"
    assert resolved["prep"] == "claude"
    assert resolved["finalize"] == "claude"


def test_depth_invalid_value_rejected_at_argparse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--depth ultra is rejected by argparse choices= before the loader
    ever sees it."""
    from megaplan.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([
            "init",
            "--project-dir", str(tmp_path),
            "--profile", "partnered",
            "--depth", "ultra",
            "an idea",
        ])


def test_deepseek_provider_invalid_value_rejected_at_argparse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([
            "init",
            "--project-dir", str(tmp_path),
            "--profile", "partnered",
            "--deepseek-provider", "openrouter",
            "an idea",
        ])


# ---------------------------------------------------------------------------
# Shannon agent spec validation
# ---------------------------------------------------------------------------


def test_shannon_accepted_as_valid_agent_spec() -> None:
    """shannon is a valid agent spec for profiles."""
    from megaplan.types import parse_agent_spec
    agent, model = parse_agent_spec("shannon")
    assert agent == "shannon"
    assert model is None


def test_shannon_rejected_when_misspelled() -> None:
    """Misspelled agent specs are rejected."""
    from megaplan.types import parse_agent_spec
    agent, _ = parse_agent_spec("shanon")  # parse_agent_spec accepts any agent name
    assert agent == "shanon"  # parser is lenient; validation happens elsewhere


def test_known_agents_includes_shannon() -> None:
    from megaplan.types import KNOWN_AGENTS
    assert "shannon" in KNOWN_AGENTS
