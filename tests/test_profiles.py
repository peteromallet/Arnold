from __future__ import annotations

import json
from argparse import Namespace
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

import pytest

import megaplan
import megaplan.profiles as profiles_module
from megaplan.profiles import (
    CANONICAL_PREP_MODELS,
    apply_profile_expansion,
    load_profiles,
)
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


def test_profile_expansion_resolves_prep_models_with_canonical_fallback_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_profiles(
        project_dir / ".megaplan" / "profiles.toml",
        """
        [profiles.legacy-prep]
        prep = "claude"
        plan = "claude"
        feedback = "claude:low"
        """,
    )

    args = _worker_args(profile="legacy-prep")
    apply_profile_expansion(args, project_dir)

    assert args.prep_models == CANONICAL_PREP_MODELS
    trace = args.prep_model_resolver_trace
    assert trace["flat_prep_input"] == "claude"
    assert trace["resolved_stage_models"] == CANONICAL_PREP_MODELS
    assert trace["canonical_fallback_used"] == {
        "triage": True,
        "fanout": True,
        "distill": True,
    }


@pytest.mark.parametrize(
    ("profile_name", "expected_flat", "expected_models", "expected_fallback"),
    [
        (
            "all-claude",
            "claude",
            CANONICAL_PREP_MODELS,
            {"triage": True, "fanout": True, "distill": True},
        ),
        (
            "premium",
            "claude:low",
            CANONICAL_PREP_MODELS,
            {"triage": True, "fanout": True, "distill": True},
        ),
        (
            "all-codex",
            "codex",
            {
                "triage": "codex",
                "fanout": CANONICAL_PREP_MODELS["fanout"],
                "distill": "codex",
            },
            {"triage": False, "fanout": True, "distill": False},
        ),
        (
            "all-open",
            "hermes:fireworks:accounts/fireworks/models/kimi-k2p6",
            CANONICAL_PREP_MODELS,
            {"triage": True, "fanout": True, "distill": True},
        ),
    ],
)
def test_builtin_profiles_smoke_stage_aware_prep_fallbacks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile_name: str,
    expected_flat: str,
    expected_models: dict[str, str],
    expected_fallback: dict[str, bool],
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile=profile_name)
    apply_profile_expansion(args, None)

    assert args.prep_models == expected_models
    assert args.prep_model_resolver_trace["flat_prep_input"] == expected_flat
    assert args.prep_model_resolver_trace["resolved_stage_models"] == expected_models
    assert args.prep_model_resolver_trace["canonical_fallback_used"] == expected_fallback


def test_profile_expansion_prefers_explicit_prep_models_subtable_over_flat_prep(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_profiles(
        project_dir / ".megaplan" / "profiles.toml",
        """
        [profiles.explicit-prep]
        vendor_locked = true
        prep = "codex"
        plan = "claude"
        feedback = "claude:low"

        [profiles.explicit-prep.prep_models]
        triage = "hermes:deepseek:deepseek-v4-pro"
        fanout = "hermes:deepseek:deepseek-v4-flash"
        distill = "codex:medium"
        """,
    )

    args = _worker_args(profile="explicit-prep")
    apply_profile_expansion(args, project_dir)

    assert args.prep_models == {
        "triage": "hermes:deepseek:deepseek-v4-pro",
        "fanout": "hermes:deepseek:deepseek-v4-flash",
        "distill": "codex:medium",
    }
    assert args.prep_model_resolver_trace["flat_prep_input"] == "codex"
    assert args.prep_model_resolver_trace["explicit_prep_models"] == args.prep_models
    assert args.prep_model_resolver_trace["canonical_fallback_used"] == {
        "triage": False,
        "fanout": False,
        "distill": False,
    }


def test_profile_expansion_inherits_prep_models_and_falls_back_omitted_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_profiles(
        project_dir / ".megaplan" / "profiles.toml",
        """
        [profiles.parent-prep]
        prep = "claude"
        plan = "claude"
        feedback = "claude:low"

        [profiles.parent-prep.prep_models]
        triage = "codex:gpt-5.4"

        [profiles.child-prep]
        extends = "system:parent-prep"
        prep = "hermes:deepseek:deepseek-v4-pro"

        [profiles.child-prep.prep_models]
        fanout = "hermes:deepseek:deepseek-v4-flash"
        """,
    )

    args = _worker_args(profile="child-prep")
    apply_profile_expansion(args, project_dir)

    assert args.prep_models == {
        "triage": "codex:gpt-5.4",
        "fanout": "hermes:deepseek:deepseek-v4-flash",
        "distill": "hermes:deepseek:deepseek-v4-pro",
    }
    assert args.prep_model_resolver_trace["flat_prep_input"] == "hermes:deepseek:deepseek-v4-pro"
    assert args.prep_model_resolver_trace["canonical_fallback_used"] == {
        "triage": False,
        "fanout": False,
        "distill": True,
    }


def test_vendor_codex_routes_flat_claude_prep_to_codex_triage_and_distill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="all-claude", vendor="codex")
    apply_profile_expansion(args, None)

    assert args.prep_models == {
        "triage": "codex",
        "fanout": CANONICAL_PREP_MODELS["fanout"],
        "distill": "codex",
    }
    assert args.prep_model_resolver_trace["flat_prep_input"] == "codex"
    assert args.prep_model_resolver_trace["canonical_fallback_used"] == {
        "triage": False,
        "fanout": True,
        "distill": False,
    }


@pytest.mark.parametrize("spec", ["claude:low", "shannon:opus"])
def test_profile_loader_rejects_write_capable_prep_model_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spec: str,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_profiles(
        project_dir / ".megaplan" / "profiles.toml",
        f"""
        [profiles.bad-prep]
        plan = "claude"

        [profiles.bad-prep.prep_models]
        triage = "{spec}"
        """,
    )

    with pytest.raises(CliError) as exc_info:
        load_profiles(project_dir=project_dir)

    assert exc_info.value.code == "invalid_profile"
    assert "prep_models.triage" in exc_info.value.message


def test_handle_init_persists_resolved_prep_model_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    _isolate_user_config(tmp_path, monkeypatch)

    response = megaplan.handle_init(
        root,
        _init_args(project_dir, profile="all-codex", vendor="codex", name="prep-model-state"),
    )
    state_path = megaplan.plans_root(root) / response["plan"] / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert state["config"]["prep_models"]["triage"] == "codex"
    assert state["config"]["prep_model_resolver_trace"]["flat_prep_input"] == "codex"
    assert state["config"]["prep_model_resolver_trace"]["resolved_stage_models"]["fanout"] == (
        "hermes:deepseek:deepseek-v4-flash"
    )


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


def test_all_codex_resolves_to_codex_without_vendor_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: `--profile all-codex` with no `--vendor` and no user
    config must keep codex phases. Without vendor-locking, the silent
    default-vendor fallback ("claude") rewrote every codex slot, turning
    `all-codex` into all-claude across an entire sprint.
    """
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="all-codex")
    args.depth = "medium"
    apply_profile_expansion(args, None)

    resolved = _phase_models_to_map(args.phase_model)
    for phase in ("plan", "prep", "critique", "revise", "gate", "finalize",
                  "execute", "loop_plan", "loop_execute", "review",
                  "tiebreaker_researcher", "tiebreaker_challenger"):
        agent = resolved[phase].split(":", 1)[0]
        assert agent == "codex", (
            f"{phase} expected codex but got {resolved[phase]!r}"
        )
    assert resolved["feedback"] == "claude:low"


def test_vendor_codex_without_profile_selects_all_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(vendor="codex")
    apply_profile_expansion(args, None)

    resolved = _phase_models_to_map(args.phase_model)
    assert args.profile == "all-codex"
    assert getattr(args, "tier_models", None) is None
    for phase in ("plan", "prep", "critique", "revise", "gate", "finalize",
                  "execute", "loop_plan", "loop_execute", "review",
                  "tiebreaker_researcher", "tiebreaker_challenger"):
        assert resolved[phase].split(":", 1)[0] == "codex"


def test_state_vendor_codex_without_profile_selects_all_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args()
    state = {"config": {"vendor": "codex"}}
    apply_profile_expansion(args, None, state=state)

    resolved = _phase_models_to_map(args.phase_model)
    assert args.profile == "all-codex"
    assert resolved["execute"] == "codex"


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

    # Claude on plan + loop_plan + tiebreakers + finalize (finalize raised to opus-4-7 for rater>=dispatchee).
    assert resolved["plan"] == "claude:low"
    assert resolved["loop_plan"] == "claude:low"
    assert resolved["tiebreaker_researcher"] == "claude:low"
    assert resolved["tiebreaker_challenger"] == "claude:low"
    assert resolved["finalize"] == "claude:claude-opus-4-7"
    # DeepSeek on the remaining mechanical block + critique + review.
    for phase in ("prep", "critique", "revise", "gate", "execute", "loop_execute", "review"):
        assert resolved[phase] == DEEPSEEK_DIRECT


def test_directed_profile_flips_to_codex_under_vendor_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--vendor codex on directed maps the tier_models.execute Claude pins to
    their Codex model pins (sonnet→codex:gpt-5.4, opus→codex:gpt-5.5) instead of
    raising; the premium finalize (now claude-opus-4-7) flips to codex:gpt-5.5."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="directed")
    args.vendor = "codex"
    apply_profile_expansion(args, None)
    tiers = args.tier_models["execute"]
    assert tiers[4] == "codex:gpt-5.4"
    assert tiers[5] == "codex:gpt-5.5"
    resolved = _phase_models_to_map(args.phase_model)
    assert resolved["finalize"] == "codex:gpt-5.5"


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
    # finalize is now claude:low (premium finalize).
    assert resolved["finalize"] == "claude:low"
    for phase in ("prep", "gate", "execute", "loop_execute"):
        assert resolved[phase] == DEEPSEEK_DIRECT


def test_partnered_profile_flips_all_premium_under_vendor_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--vendor codex on partnered flips the premium reasoning phases to codex
    and maps the tier_models.execute Claude pins to their Codex model pins
    (sonnet→codex:gpt-5.4, opus→codex:gpt-5.5) instead of raising."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered")
    args.vendor = "codex"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)
    assert resolved["plan"] == "codex:low"
    assert resolved["finalize"] == "codex:low"
    tiers = args.tier_models["execute"]
    assert tiers[4] == "codex:gpt-5.4"
    assert tiers[5] == "codex:gpt-5.5"


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

    # finalize is now claude:low (premium finalize); remaining mechanical phases stay DeepSeek.
    assert resolved["finalize"] == "claude:low"
    for phase in ("prep", "gate", "execute", "loop_execute"):
        assert resolved[phase] == DEEPSEEK_DIRECT
    assert resolved["plan"] == "claude:low"
    assert resolved["critique"] == "claude:low"
    assert resolved["review"] == "claude:low"


def test_deepseek_provider_direct_composes_with_vendor_and_depth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--deepseek-provider direct + --vendor codex + --depth high on partnered
    compose: the DeepSeek pro tiers swap to the direct provider, the Claude
    Sonnet/Opus tiers map to codex:gpt-5.4/gpt-5.5 model pins, and depth applies to authors."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered", deepseek_provider="direct")
    args.vendor = "codex"
    args.depth = "high"
    apply_profile_expansion(args, None)
    tiers = args.tier_models["execute"]
    # DeepSeek pro tiers → direct provider; Claude pins → codex model pins.
    assert tiers[2] == DEEPSEEK_DIRECT
    assert tiers[3] == DEEPSEEK_DIRECT
    assert tiers[4] == "codex:gpt-5.4"
    assert tiers[5] == "codex:gpt-5.5"
    resolved = _phase_models_to_map(args.phase_model)
    assert resolved["plan"] == "codex:high"


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
    """--vendor codex on premium maps the tier_models.execute Claude pins to
    their Codex model pins (sonnet→codex:gpt-5.4, opus→codex:gpt-5.5),
    matching the variable-codex routing convention, instead of raising."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="premium")
    args.vendor = "codex"
    apply_profile_expansion(args, None)
    tiers = args.tier_models["execute"]
    # premium routing: 1=pro, 2=pro, 3=sonnet, 4=opus, 5=opus → codex model pins
    assert tiers[3] == "codex:gpt-5.4"
    assert tiers[4] == "codex:gpt-5.5"
    assert tiers[5] == "codex:gpt-5.5"


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
    assert resolved["execute"] == "hermes:deepseek:deepseek-v4-pro"
    # finalize is now claude:low (premium finalize); depth doesn't touch mechanical phases.
    assert resolved["finalize"] == "claude:low"


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
    """--vendor codex --depth high on partnered: the tier_models.execute Claude
    pins map to their Codex model pins (sonnet→codex:gpt-5.4, opus→codex:gpt-5.5)
    rather than raising, and --depth still applies to the author phases."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="partnered")
    args.vendor = "codex"
    args.depth = "high"
    apply_profile_expansion(args, None)
    tiers = args.tier_models["execute"]
    # partnered routing: 4=sonnet, 5=opus → codex model pins
    assert tiers[4] == "codex:gpt-5.4"
    assert tiers[5] == "codex:gpt-5.5"


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
# Model-pin preservation and conflict tests (T11)
# ---------------------------------------------------------------------------


def test_depth_preserves_model_pins_in_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--depth on a spec with an explicit model pin preserves the model
    and only rewrites effort.  codex:gpt-5.3-codex:low → codex:gpt-5.3-codex:high."""
    _isolate_user_config(tmp_path, monkeypatch)

    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """\
        [profiles.pinned]
        plan = "codex:gpt-5.3-codex:low"
        prep = "hermes:deepseek:deepseek-v4-pro"
        critique = "claude:low"
        revise = "codex:gpt-5.3-codex:low"
        gate = "claude:low"
        finalize = "hermes:deepseek:deepseek-v4-pro"
        execute = "hermes:deepseek:deepseek-v4-pro"
        loop_plan = "codex:gpt-5.3-codex:low"
        loop_execute = "hermes:deepseek:deepseek-v4-pro"
        review = "claude:low"
        tiebreaker_researcher = "codex:gpt-5.3-codex:low"
        tiebreaker_challenger = "claude:low"
        """,
    )

    args = _worker_args(profile="pinned")
    args.vendor = "codex"  # Stay on codex to avoid vendor-swap conflict on pinned models
    args.depth = "high"
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # Model pins preserved, effort upgraded
    assert resolved["plan"] == "codex:gpt-5.3-codex:high", (
        f"--depth high should preserve model pin gpt-5.3-codex; "
        f"got {resolved['plan']!r}"
    )
    assert resolved["revise"] == "codex:gpt-5.3-codex:high"
    assert resolved["loop_plan"] == "codex:gpt-5.3-codex:high"
    assert resolved["tiebreaker_researcher"] == "codex:gpt-5.3-codex:high"
    # Non-pinned codex:low (critic phase) — depth does NOT rewrite critic phases
    assert resolved["critique"] == "codex:low"
    assert resolved["gate"] == "codex:low"  # gate is NOT an author phase, depth doesn't touch it


def test_vendor_swap_raises_conflict_for_model_pinned_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--vendor codex on a profile whose claude phases have explicit model
    pins must raise vendor_swap_model_conflict naming the phase and spec."""
    _isolate_user_config(tmp_path, monkeypatch)

    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """\
        [profiles.claude-pinned]
        plan = "claude:sonnet-4.6:high"
        prep = "hermes:deepseek:deepseek-v4-pro"
        critique = "codex:high"
        revise = "claude:sonnet-4.6:high"
        gate = "claude:high"
        finalize = "hermes:deepseek:deepseek-v4-pro"
        execute = "hermes:deepseek:deepseek-v4-pro"
        loop_plan = "claude:sonnet-4.6:high"
        loop_execute = "hermes:deepseek:deepseek-v4-pro"
        review = "codex:high"
        tiebreaker_researcher = "claude:sonnet-4.6:high"
        tiebreaker_challenger = "codex:high"
        """,
    )

    args = _worker_args(profile="claude-pinned")
    args.vendor = "codex"

    with pytest.raises(CliError) as exc_info:
        apply_profile_expansion(args, None)
    assert exc_info.value.code == "vendor_swap_model_conflict"
    # Error should name the offending phase and the spec string
    message = str(exc_info.value)
    assert "plan" in message, f"Error should name phase 'plan': {message}"
    assert "sonnet-4.6" in message, f"Error should name model 'sonnet-4.6': {message}"


def test_critic_cross_raises_conflict_for_model_pinned_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--critic cross on a profile whose critique/review have explicit
    model pins must raise vendor_swap_model_conflict naming the phase."""
    _isolate_user_config(tmp_path, monkeypatch)

    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """\
        [profiles.critic-pinned]
        plan = "codex:high"
        prep = "hermes:deepseek:deepseek-v4-pro"
        critique = "claude:sonnet-4.6:high"
        revise = "codex:high"
        gate = "codex:high"
        finalize = "hermes:deepseek:deepseek-v4-pro"
        execute = "hermes:deepseek:deepseek-v4-pro"
        loop_plan = "codex:high"
        loop_execute = "hermes:deepseek:deepseek-v4-pro"
        review = "claude:sonnet-4.6:high"
        tiebreaker_researcher = "codex:high"
        tiebreaker_challenger = "claude:high"
        """,
    )

    args = _worker_args(profile="critic-pinned")
    args.vendor = "codex"  # post-vendor vendor is codex, cross → claude... but critique is already claude
    # Actually we need vendor swap to trigger the cross. Let's try vendor=claude so
    # post-vendor vendor=claude, cross→codex, but critique/review are claude:sonnet-4.6
    # which would cross-swap to codex:sonnet-4.6 → conflict!
    args.vendor = "claude"
    args.critic = "cross"

    with pytest.raises(CliError) as exc_info:
        apply_profile_expansion(args, None)
    assert exc_info.value.code == "vendor_swap_model_conflict"
    message = str(exc_info.value)
    # Should name the phase and spec — the conflict is on critique/review, not plan
    assert ("critique" in message or "review" in message), (
        f"Error should name phase 'critique' or 'review': {message}"
    )
    assert "sonnet-4.6" in message, f"Error should name model 'sonnet-4.6': {message}"


def test_reserved_effort_token_disambiguation_in_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reserved effort tokens like 'low', 'high' etc. must be treated as
    effort, not model, when used in profile specs like claude:low."""
    _isolate_user_config(tmp_path, monkeypatch)

    fake_home_config = tmp_path / ".config" / "megaplan"
    _write_profiles(
        fake_home_config / "profiles.toml",
        """\
        [profiles.effort-only]
        plan = "claude:low"
        prep = "hermes:deepseek:deepseek-v4-pro"
        critique = "codex:low"
        revise = "claude:low"
        gate = "claude:low"
        finalize = "hermes:deepseek:deepseek-v4-pro"
        execute = "hermes:deepseek:deepseek-v4-pro"
        loop_plan = "claude:low"
        loop_execute = "hermes:deepseek:deepseek-v4-pro"
        review = "codex:low"
        tiebreaker_researcher = "claude:low"
        tiebreaker_challenger = "codex:low"
        """,
    )

    args = _worker_args(profile="effort-only")
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # claude:low should resolve as agent=claude, model=None, effort=low
    # The phase_model entry should be like "plan=claude:low"
    assert resolved["plan"] == "claude:low", (
        f"claude:low should stay as claude:low (effort-only); got {resolved['plan']!r}"
    )
    # codex:low gets vendor-swapped to claude:low when default vendor is claude
    assert resolved["critique"] == "claude:low"
    assert resolved["review"] == "claude:low"

    # Now apply --depth high on the same profile with vendor=codex
    # so the critique codex:low stays codex and plateaus
    args2 = _worker_args(profile="effort-only")
    args2.vendor = "codex"
    args2.depth = "high"
    apply_profile_expansion(args2, None)
    resolved2 = _phase_models_to_map(args2.phase_model)

    assert resolved2["plan"] == "codex:high", (
        f"--depth high on codex:low should produce codex:high; "
        f"got {resolved2['plan']!r}"
    )
    assert resolved2["critique"] == "codex:low", (
        f"critique should plateau at existing effort:low; got {resolved2['critique']!r}"
    )


def test_builtin_profile_resolution_with_default_model_pins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Built-in profiles (like all-claude) resolve bare claude specs with
    default models via parse_agent_spec + resolved_default_model_for_agent."""
    _isolate_user_config(tmp_path, monkeypatch)

    # all-claude has bare claude specs — these should get default model resolution
    args = _worker_args(profile="all-claude")
    apply_profile_expansion(args, None)
    resolved = _phase_models_to_map(args.phase_model)

    # The spec strings in phase_model should be bare "claude" (not three-part)
    # but resolve_agent_mode will fill in the default model at runtime
    for phase in ("plan", "prep", "critique", "revise", "gate", "finalize", "execute", "review"):
        spec = resolved.get(phase)
        assert spec is not None, f"Phase '{phase}' missing from resolved map"
        # Bare claude specs are just "claude" — no model suffix
        if spec == "claude" or spec == "codex":
            pass  # valid bare spec
        else:
            # If there's a model, parse_agent_spec should handle it
            from megaplan.types import parse_agent_spec
            parsed = parse_agent_spec(spec)
            assert parsed.agent in ("claude", "codex", "hermes", "shannon"), (
                f"Unexpected agent in spec '{spec}' for phase '{phase}'"
            )

    # all-deepseek-pro has hermes specs — these are fine
    args2 = _worker_args(profile="all-deepseek-pro")
    apply_profile_expansion(args2, None)
    resolved2 = _phase_models_to_map(args2.phase_model)
    for phase, spec in resolved2.items():
        from megaplan.types import parse_agent_spec
        parsed = parse_agent_spec(spec)
        assert parsed.agent is not None, (
            f"Could not parse spec '{spec}' for phase '{phase}'"
        )


# ---------------------------------------------------------------------------
# Shannon agent spec validation
# ---------------------------------------------------------------------------


def test_shannon_accepted_as_valid_agent_spec() -> None:
    """shannon is a valid agent spec for profiles."""
    from megaplan.types import parse_agent_spec
    spec = parse_agent_spec("shannon")
    assert spec.agent == "shannon"
    assert spec.model is None


def test_shannon_rejected_when_misspelled() -> None:
    """Misspelled agent specs are rejected."""
    from megaplan.types import parse_agent_spec
    spec = parse_agent_spec("shanon")  # parse_agent_spec accepts any agent name
    assert spec.agent == "shanon"  # parser is lenient; validation happens elsewhere


def test_known_agents_includes_shannon() -> None:
    from megaplan.types import KNOWN_AGENTS
    assert "shannon" in KNOWN_AGENTS


# ---------------------------------------------------------------------------
# Tier model metadata parsing, validation, and inheritance (T6)
# ---------------------------------------------------------------------------


def test_extract_tier_models_nested_toml_table() -> None:
    """Nested TOML tables are normalised to {phase: {tier: spec}}."""
    from megaplan.profiles import _extract_tier_models

    raw = {"execute": {"1": "hermes:deepseek-flash", "2": "hermes:deepseek-pro"}}
    result = _extract_tier_models(raw)
    assert result == {"execute": {1: "hermes:deepseek-flash", 2: "hermes:deepseek-pro"}}


def test_extract_tier_models_flattened_dotted_keys() -> None:
    """Already re-nested flattened keys are handled identically."""
    from megaplan.profiles import _extract_tier_models

    # Simulating what _split_profile_dict re-nests from pipeline-local
    raw = {"execute": {"1": "hermes:deepseek-flash", "3": "hermes:deepseek-pro"}}
    result = _extract_tier_models(raw)
    assert result == {"execute": {1: "hermes:deepseek-flash", 3: "hermes:deepseek-pro"}}


def test_extract_tier_models_string_tier_keys_converted_to_int() -> None:
    """String tier keys like '1' are converted to int 1."""
    from megaplan.profiles import _extract_tier_models

    raw = {"execute": {"1": "hermes:deepseek-flash", "5": "codex:high"}}
    result = _extract_tier_models(raw)
    assert result == {"execute": {1: "hermes:deepseek-flash", 5: "codex:high"}}


def test_extract_tier_models_non_dict_returns_empty() -> None:
    """Non-dict input returns empty dict."""
    from megaplan.profiles import _extract_tier_models
    assert _extract_tier_models(None) == {}
    assert _extract_tier_models("not a dict") == {}
    assert _extract_tier_models([]) == {}


def test_validate_tier_models_rejects_unknown_phase() -> None:
    """Unknown phase names in tier_models are rejected."""
    from megaplan.profiles import _validate_tier_models
    from megaplan.types import CliError

    with pytest.raises(CliError, match="unknown phase 'bogus'"):
        _validate_tier_models("test.toml", "test-profile", {"bogus": {1: "claude:low"}})


def test_validate_tier_models_rejects_tier_key_out_of_range() -> None:
    """Tier keys must be 1..5."""
    from megaplan.profiles import _validate_tier_models
    from megaplan.types import CliError

    with pytest.raises(CliError, match="tier key must be an integer 1..5"):
        _validate_tier_models("test.toml", "test-profile", {"execute": {0: "claude:low"}})

    with pytest.raises(CliError, match="tier key must be an integer 1..5"):
        _validate_tier_models("test.toml", "test-profile", {"execute": {6: "claude:low"}})


def test_validate_tier_models_rejects_non_integer_tier_key() -> None:
    """Non-integer tier keys like 'x' are rejected by _validate_tier_models."""
    from megaplan.profiles import _extract_tier_models, _validate_tier_models
    from megaplan.types import CliError

    raw = {"execute": {"x": "claude:low"}}
    tier_data = _extract_tier_models(raw)
    with pytest.raises(CliError, match="tier key must be an integer 1..5"):
        _validate_tier_models("test.toml", "test-profile", tier_data)


def test_validate_tier_models_rejects_unknown_agent() -> None:
    """Unknown agents in tier specs are rejected."""
    from megaplan.profiles import _validate_tier_models
    from megaplan.types import CliError

    with pytest.raises(CliError, match="unknown agent 'bogus-agent'"):
        _validate_tier_models("test.toml", "test-profile", {"execute": {1: "bogus-agent:low"}})


def test_validate_tier_models_rejects_non_string_spec() -> None:
    """Non-string tier specs are rejected by _validate_tier_models."""
    from megaplan.profiles import _extract_tier_models, _validate_tier_models
    from megaplan.types import CliError

    raw = {"execute": {"1": 123}}
    tier_data = _extract_tier_models(raw)
    # _extract_tier_models now passes through; _validate_tier_models must reject.
    with pytest.raises(CliError, match="expected a string agent spec"):
        _validate_tier_models("test.toml", "test-profile", tier_data)


def test_extract_tier_models_rejects_non_dict_tier_map_when_path_provided() -> None:
    """Non-dict tier entries (e.g. a list) must raise CliError at profile
    load time when path/profile_name are supplied."""
    from megaplan.profiles import _extract_tier_models
    from megaplan.types import CliError

    with pytest.raises(CliError, match="tier entry must be a TOML table"):
        _extract_tier_models({"execute": [1, 2, 3]}, path="test.toml", profile_name="test")


def test_extract_tier_models_rejects_non_str_phase_key_when_path_provided() -> None:
    """Non-string phase keys must raise CliError at profile load time
    when path/profile_name are supplied."""
    from megaplan.profiles import _extract_tier_models
    from megaplan.types import CliError

    with pytest.raises(CliError, match="phase key must be a string"):
        _extract_tier_models({123: {"1": "claude"}}, path="test.toml", profile_name="test")


def test_extract_tier_models_non_dict_tier_map_no_path_still_skips() -> None:
    """Without path/profile_name, non-dict tier maps are silently skipped
    (backward compat for already-validated data paths)."""
    from megaplan.profiles import _extract_tier_models

    result = _extract_tier_models({"execute": [1, 2, 3]})
    assert result == {}


def test_extract_tier_models_non_str_phase_no_path_still_skips() -> None:
    """Without path/profile_name, non-string phase keys are silently skipped
    (backward compat for already-validated data paths)."""
    from megaplan.profiles import _extract_tier_models

    result = _extract_tier_models({123: {"1": "claude"}})
    assert result == {}


def test_extract_tier_models_non_dict_with_path_raises() -> None:
    """Non-dict input (string) with path/profile_name raises CliError."""
    from megaplan.profiles import _extract_tier_models
    from megaplan.types import CliError

    with pytest.raises(CliError, match="expected a TOML table for tier_models"):
        _extract_tier_models("bad", path="test.toml", profile_name="test")


def test_extract_tier_models_non_dict_list_with_path_raises() -> None:
    """Non-dict input (list) with path/profile_name raises CliError."""
    from megaplan.profiles import _extract_tier_models
    from megaplan.types import CliError

    with pytest.raises(CliError, match="expected a TOML table for tier_models"):
        _extract_tier_models([1, 2, 3], path="test.toml", profile_name="test")


def test_split_profile_dict_rejects_two_part_tier_key() -> None:
    """Flattened key 'tier_models.execute' (2 parts, missing tier) raises CliError."""
    from megaplan.profiles import _split_profile_dict
    from megaplan.types import CliError

    with pytest.raises(CliError, match="malformed tier_models key"):
        _split_profile_dict("test.toml", "test", {"tier_models.execute": "claude"})


def test_split_profile_dict_rejects_four_part_tier_key() -> None:
    """Flattened key 'tier_models.execute.1.extra' (4 parts) raises CliError."""
    from megaplan.profiles import _split_profile_dict
    from megaplan.types import CliError

    with pytest.raises(CliError, match="malformed tier_models key"):
        _split_profile_dict("test.toml", "test", {"tier_models.execute.1.extra": "claude"})


def test_split_profile_dict_extracts_flattened_tier_models() -> None:
    """Flattened tier_models.execute.1 keys are re-nested into metadata."""
    from megaplan.profiles import _split_profile_dict

    flat = {
        "vendor_locked": True,
        "tier_models.execute.1": "hermes:deepseek-flash",
        "tier_models.execute.5": "claude:high",
        "plan": "claude:low",
    }
    phase_map, metadata = _split_profile_dict("test.toml", "test", flat)
    assert "tier_models" not in phase_map
    assert "tier_models.execute.1" not in phase_map
    assert metadata["vendor_locked"] is True
    assert metadata["tier_models"] == {
        "execute": {"1": "hermes:deepseek-flash", "5": "claude:high"}
    }
    assert phase_map == {"plan": "claude:low"}


def test_split_profile_dict_nested_tier_models() -> None:
    """Nested tier_models dict is placed in metadata directly."""
    from megaplan.profiles import _split_profile_dict

    nested = {
        "vendor_locked": True,
        "tier_models": {"execute": {"1": "hermes:deepseek-flash", "5": "claude:high"}},
        "plan": "claude:low",
    }
    phase_map, metadata = _split_profile_dict("test.toml", "test", nested)
    assert metadata["tier_models"] == {"execute": {"1": "hermes:deepseek-flash", "5": "claude:high"}}
    assert phase_map == {"plan": "claude:low"}


def test_resolve_tier_models_inheritance_child_overrides_parent() -> None:
    """Child tier overrides parent for the same phase+tier."""
    from megaplan.profiles import _resolve_tier_models_with_inheritance

    system_profiles = {
        "parent": {"plan": "claude:low"},
        "child": {"plan": "claude:low"},
    }
    system_metadata = {
        "parent": {
            "tier_models": {"execute": {
                1: "hermes:deepseek-flash",
                5: "claude:high",
            }},
        },
        "child": {
            "extends": "system:parent",
            "tier_models": {"execute": {
                5: "codex:high",
            }},
        },
    }
    pipeline_local_profiles: dict[str, dict[str, str]] = {}
    pipeline_local_metadata: dict[str, dict[str, Any]] = {}

    result = _resolve_tier_models_with_inheritance(
        "child",
        system_profiles=system_profiles,
        system_metadata=system_metadata,
        pipeline_local_profiles=pipeline_local_profiles,
        pipeline_local_metadata=pipeline_local_metadata,
    )
    assert result == {"execute": {1: "hermes:deepseek-flash", 5: "codex:high"}}


def test_resolve_tier_models_inheritance_no_parent_tiers() -> None:
    """Profile without extends returns its own tier_models."""
    from megaplan.profiles import _resolve_tier_models_with_inheritance

    system_profiles = {"solo": {"plan": "claude:low"}}
    system_metadata = {
        "solo": {
            "tier_models": {"execute": {1: "hermes:deepseek-flash"}},
        },
    }
    pipeline_local_profiles: dict[str, dict[str, str]] = {}
    pipeline_local_metadata: dict[str, dict[str, Any]] = {}

    result = _resolve_tier_models_with_inheritance(
        "solo",
        system_profiles=system_profiles,
        system_metadata=system_metadata,
        pipeline_local_profiles=pipeline_local_profiles,
        pipeline_local_metadata=pipeline_local_metadata,
    )
    assert result == {"execute": {1: "hermes:deepseek-flash"}}


# ---------------------------------------------------------------------------
# T7/T8: Tier model rewrite tests
# ---------------------------------------------------------------------------


def test_vendor_rewrite_propagates_to_tier_entries() -> None:
    """--vendor codex swaps only premium (claude/codex) tier entries; DeepSeek tiers pass through."""
    from megaplan.profiles import apply_vendor_rewrite

    tier_models = {"execute": {1: "hermes:deepseek-flash", 3: "hermes:deepseek-pro", 4: "claude:medium", 5: "claude:high"}}
    profile = {"plan": "claude:low"}

    _result = apply_vendor_rewrite(profile, "codex", tier_models=tier_models)

    # DeepSeek tiers unchanged
    assert tier_models["execute"][1] == "hermes:deepseek-flash"
    assert tier_models["execute"][3] == "hermes:deepseek-pro"
    # Premium tiers flipped
    assert tier_models["execute"][4] == "codex:medium"
    assert tier_models["execute"][5] == "codex:high"


def test_deepseek_provider_rewrite_propagates_to_tier_entries() -> None:
    """--deepseek-provider direct swaps canonical Fireworks DeepSeek specs in tier entries."""
    from megaplan.profiles import apply_deepseek_provider_rewrite

    FIREWORKS_DS = "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"
    tier_models = {"execute": {1: FIREWORKS_DS, 5: "claude:high"}}
    profile = {"plan": FIREWORKS_DS}

    _result = apply_deepseek_provider_rewrite(profile, "direct", tier_models=tier_models)

    # DeepSeek tier swapped to direct
    assert "deepseek:deepseek-v4-pro" in tier_models["execute"][1]
    # Premium tier unchanged
    assert tier_models["execute"][5] == "claude:high"


def test_depth_rewrite_propagates_to_tier_entries_author_phases_only() -> None:
    """--depth rewrites tier entries for author phases (e.g. plan) but not execute."""
    from megaplan.profiles import apply_depth_rewrite

    tier_models = {
        "plan": {1: "claude:low", 4: "claude:medium"},
        "execute": {1: "hermes:deepseek-flash", 4: "claude:medium"},  # execute is not author-phase
    }
    profile = {"plan": "claude:low", "execute": "hermes:deepseek-flash"}

    _result = apply_depth_rewrite(profile, "high", tier_models=tier_models)

    # Author phase tiers rewritten
    assert tier_models["plan"][1] == "claude:high"
    assert tier_models["plan"][4] == "claude:high"
    # Execute phase tiers NOT touched (not an author phase)
    assert tier_models["execute"][1] == "hermes:deepseek-flash"
    assert tier_models["execute"][4] == "claude:medium"


def test_named_vendor_tier_drift_raises_profile_resolution_mismatch() -> None:
    """A variable-codex tier 4 of claude:medium must raise profile_resolution_mismatch."""
    from megaplan.profiles import _validate_named_profile_invariants

    with pytest.raises(CliError, match="expected codex"):
        _validate_named_profile_invariants(
            "variable-codex",
            {"plan": "codex:low"},
            tier_models={"execute": {4: "claude:medium"}},
        )


def test_named_vendor_tier_drift_passes_when_correct() -> None:
    """A variable-codex profile with correct codex tier entries passes validation."""
    from megaplan.profiles import _validate_named_profile_invariants

    # Should not raise
    _validate_named_profile_invariants(
        "variable-codex",
        {"plan": "codex:low"},
        tier_models={"execute": {4: "codex:medium", 5: "codex:high"}},
    )


def test_apply_profile_expansion_attaches_tier_models_to_args(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A profile with tier_models metadata sets args.tier_models after expansion."""
    _isolate_user_config(tmp_path, monkeypatch)

    # Write a local profile with tier_models metadata
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    profiles_path = project_dir / ".megaplan" / "profiles.toml"
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_path.write_text("""
[profiles.tier-test]
vendor_locked = false
plan = "claude:low"
execute = "hermes:deepseek-flash"
feedback = "claude:low"

[profiles.tier-test.tier_models.execute]
1 = "hermes:deepseek-flash"
2 = "hermes:deepseek-pro"
3 = "hermes:deepseek-pro"
4 = "claude:medium"
5 = "claude:high"
""", encoding="utf-8")

    args = _worker_args(profile="tier-test")
    apply_profile_expansion(args, project_dir)

    assert hasattr(args, "tier_models")
    assert args.tier_models is not None
    assert "execute" in args.tier_models
    assert args.tier_models["execute"][1] == "hermes:deepseek-flash"
    assert args.tier_models["execute"][4] == "claude:medium"
    assert args.tier_models["execute"][5] == "claude:high"


def test_apply_profile_expansion_cli_execute_override_strips_tier_execute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When CLI --phase-model execute=... is present, tier_models.execute is stripped."""
    _isolate_user_config(tmp_path, monkeypatch)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    profiles_path = project_dir / ".megaplan" / "profiles.toml"
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_path.write_text("""
[profiles.tier-test]
vendor_locked = false
plan = "claude:low"
execute = "hermes:deepseek-flash"
feedback = "claude:low"

[profiles.tier-test.tier_models.execute]
1 = "hermes:deepseek-flash"
4 = "claude:medium"
5 = "claude:high"
""", encoding="utf-8")

    args = _worker_args(profile="tier-test", phase_model=["execute=codex:high"])
    apply_profile_expansion(args, project_dir)

    # tier_models should exist but execute should be stripped
    assert args.tier_models is None or "execute" not in (args.tier_models or {})


def test_explicit_agent_overrides_persisted_phase_model_recovery_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)
    state = {
        "config": {
            "phase_model": ["execute=hermes:deepseek:deepseek-v4-pro"],
        }
    }
    args = _worker_args(agent="codex", phase_model=[])

    apply_profile_expansion(args, None, state=state)

    with patch("megaplan.workers._impl.shutil.which", return_value="/usr/bin/codex"):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)
    assert agent == "codex"
    assert model is None


def test_live_phase_model_still_beats_explicit_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_user_config(tmp_path, monkeypatch)
    args = _worker_args(
        agent="codex",
        phase_model=["execute=hermes:deepseek:deepseek-v4-pro"],
    )

    apply_profile_expansion(args, None)

    with patch("megaplan.workers._impl._is_agent_available", return_value=True):
        agent, _mode, _refreshed, model = resolve_agent_mode("execute", args)
    assert agent == "hermes"
    assert model == "deepseek:deepseek-v4-pro"


def test_apply_profile_expansion_flat_profile_no_tier_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A profile without [tier_models] section sets args.tier_models to None.
    The five main profiles (solo/directed/partnered/premium/apex) now all have
    tier_models. Use all-deepseek-pro which is a flat profile with no tiers."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="all-deepseek-pro")
    apply_profile_expansion(args, None)

    assert getattr(args, "tier_models", None) is None


def test_vendor_rewrite_tier_entries_tier_models_none_does_not_crash() -> None:
    """Passing tier_models=None does not crash (backward compat)."""
    from megaplan.profiles import apply_vendor_rewrite

    result = apply_vendor_rewrite({"plan": "claude:low"}, "codex")
    assert result["plan"] == "codex:low"


def test_deepseek_provider_rewrite_tier_models_none_does_not_crash() -> None:
    """Passing tier_models=None does not crash (backward compat)."""
    from megaplan.profiles import apply_deepseek_provider_rewrite

    result = apply_deepseek_provider_rewrite(
        {"plan": "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro"}, "direct"
    )
    assert "deepseek:deepseek-v4-pro" in result["plan"]


def test_depth_rewrite_tier_models_none_does_not_crash() -> None:
    """Passing tier_models=None does not crash (backward compat)."""
    from megaplan.profiles import apply_depth_rewrite

    result = apply_depth_rewrite({"plan": "claude:low"}, "high")
    assert result["plan"] == "claude:high"


def test_validate_named_profile_invariants_tier_models_none_does_not_crash() -> None:
    """Passing tier_models=None to _validate_named_profile_invariants does not crash."""
    from megaplan.profiles import _validate_named_profile_invariants

    # Should not raise
    _validate_named_profile_invariants("all-codex", {"plan": "codex:low"}, tier_models=None)


def test_validate_named_profile_invariants_empty_tier_models_does_not_crash() -> None:
    """Empty tier_models dict is harmless."""
    from megaplan.profiles import _validate_named_profile_invariants

    # Should not raise
    _validate_named_profile_invariants("all-codex", {"plan": "codex:low"}, tier_models={})


def test_locked_variable_codex_ignores_vendor_flag_tier_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A vendor_locked=true profile ignores --vendor on tier entries just like phase entries."""
    _isolate_user_config(tmp_path, monkeypatch)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    profiles_path = project_dir / ".megaplan" / "profiles.toml"
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_path.write_text("""
[profiles.locked-tier]
vendor_locked = true
plan = "codex:low"
execute = "codex:medium"
feedback = "claude:low"

[profiles.locked-tier.tier_models.execute]
1 = "hermes:deepseek-flash"
4 = "codex:medium"
5 = "codex:high"
""", encoding="utf-8")

    args = _worker_args(profile="locked-tier", vendor="claude")
    apply_profile_expansion(args, project_dir)

    resolved = _phase_models_to_map(args.phase_model)
    # Phase entries should still be codex (locked)
    assert resolved["plan"] == "codex:low"
    assert resolved["execute"] == "codex:medium"
    # Tier entries should still be codex on premium tiers (locked)
    if args.tier_models:
        assert args.tier_models["execute"][4] == "codex:medium"
        assert args.tier_models["execute"][5] == "codex:high"
        # DeepSeek tiers unchanged
        assert "deepseek" in args.tier_models["execute"][1]


# ---------------------------------------------------------------------------
# Config / provenance snapshot tests
# ---------------------------------------------------------------------------


def test_init_saves_tier_models_when_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When args.tier_models is set, init handler persists it in state.config.tier_models."""
    from megaplan.handlers.init import handle_init

    _isolate_user_config(tmp_path, monkeypatch)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_profiles(
        project_dir / ".megaplan" / "profiles.toml",
        """
[profiles.tm-init]
vendor_locked = false
plan = "claude:low"
execute = "hermes:deepseek-flash"
feedback = "claude:low"

[profiles.tm-init.tier_models.execute]
1 = "hermes:deepseek-flash"
4 = "claude:medium"
5 = "claude:high"
""",
    )

    root = tmp_path / "root"
    root.mkdir()
    plan_root = root / ".megaplan" / "plans"
    plan_root.mkdir(parents=True)

    args = _init_args(project_dir, profile="tm-init", name="tier-state-test", mode="code",
                       auto_approve=True, robustness="standard")
    apply_profile_expansion(args, project_dir)

    # Create the plan directory and run handle_init with a root that already exists
    import megaplan._core.io as io_module
    monkeypatch.setattr(io_module, "plans_root", lambda r: plan_root)

    response = handle_init(root, args)
    assert response["success"]

    state_path = plan_root / "tier-state-test" / "state.json"
    state = json.loads(state_path.read_text())
    assert state["config"].get("tier_models") is not None
    assert state["config"]["tier_models"]["execute"]["4"] == "claude:medium"


def test_snapshot_cli_provenance_includes_tier_models() -> None:
    """_snapshot_cli_provenance includes tier_models when present in config."""
    from megaplan.handlers.shared import _snapshot_cli_provenance

    state = {
        "config": {
            "profile": "variable",
            "mode": "code",
            "tier_models": {"execute": {1: "hermes:deepseek-flash", 5: "claude:high"}},
        }
    }
    snap = _snapshot_cli_provenance(state)
    assert "tier_models" in snap
    assert snap["tier_models"]["execute"][1] == "hermes:deepseek-flash"


def test_snapshot_cli_provenance_omits_tier_models_when_absent() -> None:
    """_snapshot_cli_provenance does not include tier_models when not in config."""
    from megaplan.handlers.shared import _snapshot_cli_provenance

    state = {"config": {"profile": "partnered", "mode": "code"}}
    snap = _snapshot_cli_provenance(state)
    assert "tier_models" not in snap


# ---------------------------------------------------------------------------
# T10: Comprehensive profile loading, inheritance, validation, rewrite tests
# (gap-filling beyond what T6/T7/T8 already covered above)
# ---------------------------------------------------------------------------


def test_partnered_byte_identical_across_independent_expansions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two independent `--profile partnered` expansions produce byte-identical
    phase_model lists and consistent tier_models metadata."""
    _isolate_user_config(tmp_path, monkeypatch)

    args_a = _worker_args(profile="partnered")
    apply_profile_expansion(args_a, None)

    args_b = _worker_args(profile="partnered")
    apply_profile_expansion(args_b, None)

    assert args_a.phase_model == args_b.phase_model
    # partnered now has tier_models.execute for complexity routing.
    assert getattr(args_a, "tier_models", None) is not None
    assert getattr(args_b, "tier_models", None) is not None

    # Verify expected values are present (regression guard)
    resolved = _phase_models_to_map(args_a.phase_model)
    for phase in ("plan", "critique", "revise", "review", "loop_plan",
                   "tiebreaker_researcher", "tiebreaker_challenger"):
        assert resolved[phase] == "claude:low"
    # finalize is now claude:low (premium finalize).
    assert resolved["finalize"] == "claude:low"
    for phase in ("prep", "gate", "execute", "loop_execute"):
        assert resolved[phase] == DEEPSEEK_DIRECT


def test_all_codex_byte_identical_across_independent_expansions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two independent `--profile all-codex` expansions produce byte-identical
    phase_model lists and no tier_models metadata."""
    _isolate_user_config(tmp_path, monkeypatch)

    args_a = _worker_args(profile="all-codex")
    apply_profile_expansion(args_a, None)

    args_b = _worker_args(profile="all-codex")
    apply_profile_expansion(args_b, None)

    assert args_a.phase_model == args_b.phase_model
    assert getattr(args_a, "tier_models", None) is None
    assert getattr(args_b, "tier_models", None) is None

    # Verify every non-feedback phase resolves to codex
    resolved = _phase_models_to_map(args_a.phase_model)
    for phase in ("plan", "prep", "critique", "revise", "gate", "finalize",
                  "execute", "loop_plan", "loop_execute", "review",
                  "tiebreaker_researcher", "tiebreaker_challenger"):
        agent = resolved[phase].split(":", 1)[0]
        assert agent == "codex", f"{phase} expected codex, got {resolved[phase]!r}"
    assert resolved["feedback"] == "claude:low"


def test_all_codex_no_tier_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """all-codex does not gain tier_models metadata — flat profiles stay flat."""
    _isolate_user_config(tmp_path, monkeypatch)
    from megaplan.profiles import load_profile_metadata

    all_meta = load_profile_metadata(home=tmp_path / "home",
                                      project_dir=tmp_path / "project")
    meta = all_meta.get("all-codex", {})
    assert meta.get("tier_models") is None


def test_partnered_no_tier_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """partnered now has tier_models metadata (execute complexity routing added)."""
    _isolate_user_config(tmp_path, monkeypatch)
    from megaplan.profiles import load_profile_metadata

    all_meta = load_profile_metadata(home=tmp_path / "home",
                                      project_dir=tmp_path / "project")
    meta = all_meta.get("partnered", {})
    # partnered now has tier_models.execute for per-task complexity routing.
    assert meta.get("tier_models") is not None
    assert "execute" in meta["tier_models"]


def test_pipeline_local_tier_metadata_inheritance_and_merge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline-local profile tier metadata is inherited from parent and
    merged with child overrides, then validated."""
    _isolate_user_config(tmp_path, monkeypatch)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    profiles_path = project_dir / ".megaplan" / "profiles.toml"
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_path.write_text("""\
[profiles.child-tier]
extends = "system:partnered"
vendor_locked = false
plan = "claude:low"
execute = "hermes:deepseek:deepseek-v4-flash"
feedback = "claude:low"

[profiles.child-tier.tier_models.execute]
1 = "hermes:deepseek:deepseek-v4-flash"
4 = "claude:medium"
5 = "claude:high"
""", encoding="utf-8")

    from megaplan.profiles import load_profile_metadata

    all_meta = load_profile_metadata(home=tmp_path / "home",
                                      project_dir=project_dir)
    meta = all_meta.get("child-tier", {})
    assert meta is not None
    tier_models = meta.get("tier_models")
    assert tier_models is not None
    assert tier_models["execute"][1] == "hermes:deepseek:deepseek-v4-flash"
    assert tier_models["execute"][4] == "claude:medium"
    assert tier_models["execute"][5] == "claude:high"


def test_pipeline_local_tier_metadata_validation_rejects_malformed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline-local tier metadata with unknown agent rejects at load time."""
    _isolate_user_config(tmp_path, monkeypatch)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    profiles_path = project_dir / ".megaplan" / "profiles.toml"
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_path.write_text("""\
[profiles.bad-tier]
plan = "claude:low"
execute = "hermes:deepseek:deepseek-v4-flash"
feedback = "claude:low"

[profiles.bad-tier.tier_models.execute]
1 = "bogus-agent:low"
""", encoding="utf-8")

    from megaplan.profiles import load_profile_metadata

    with pytest.raises(CliError, match="unknown agent"):
        load_profile_metadata(home=tmp_path / "home",
                               project_dir=project_dir)


# ---------------------------------------------------------------------------
# T16: Profile compatibility regression tests
# ---------------------------------------------------------------------------


def test_variable_profile_vendor_codex_rewrites_premium_tiers_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--vendor codex --profile variable` rewrites premium tier entries
    4 and 5 to codex but leaves DeepSeek tiers 1-3 unchanged."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="variable", vendor="codex")
    apply_profile_expansion(args, None)

    tier_models = getattr(args, "tier_models", None)
    assert tier_models is not None, "variable profile should have tier_models"
    execute_tiers = tier_models.get("execute")
    assert execute_tiers is not None, "variable profile should have execute tiers"

    # DeepSeek tiers 1-3 unchanged
    assert "deepseek" in execute_tiers[1], f"tier 1 should be DeepSeek, got {execute_tiers[1]!r}"
    assert "deepseek" in execute_tiers[2], f"tier 2 should be DeepSeek, got {execute_tiers[2]!r}"
    assert "deepseek" in execute_tiers[3], f"tier 3 should be DeepSeek, got {execute_tiers[3]!r}"
    # Premium tiers 4-5 flipped to codex (variable.toml has claude:low / bare claude;
    # vendor swap preserves the effort suffix, so tier 4 → codex:low, tier 5 → codex)
    assert execute_tiers[4].startswith("codex"), f"tier 4 should be codex, got {execute_tiers[4]!r}"
    assert execute_tiers[5].startswith("codex"), f"tier 5 should be codex, got {execute_tiers[5]!r}"


def test_variable_codex_locked_ignores_vendor_claude(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--profile variable-codex --vendor claude` silently ignores the
    vendor flip and keeps codex on premium tiers."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="variable-codex", vendor="claude")
    apply_profile_expansion(args, None)

    tier_models = getattr(args, "tier_models", None)
    assert tier_models is not None
    execute_tiers = tier_models.get("execute")
    assert execute_tiers is not None

    # Premium tiers should still be codex (locked)
    assert execute_tiers[4].startswith("codex"), (
        f"tier 4 should be codex (locked), got {execute_tiers[4]!r}"
    )
    assert execute_tiers[5].startswith("codex"), (
        f"tier 5 should be codex (locked), got {execute_tiers[5]!r}"
    )
    # Phase entries should also still be codex
    resolved = _phase_models_to_map(args.phase_model)
    assert resolved["execute"].startswith("codex"), (
        f"execute phase should be codex (locked), got {resolved['execute']!r}"
    )


def test_variable_profile_loads_without_vendor_has_claude_premium_tiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--profile variable` without --vendor has Claude on premium tiers 4-5."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="variable")
    apply_profile_expansion(args, None)

    tier_models = getattr(args, "tier_models", None)
    assert tier_models is not None
    execute_tiers = tier_models.get("execute")
    assert execute_tiers is not None

    assert execute_tiers[4].startswith("claude"), (
        f"tier 4 should be claude (default premium), got {execute_tiers[4]!r}"
    )
    assert execute_tiers[5].startswith("claude"), (
        f"tier 5 should be claude (default premium), got {execute_tiers[5]!r}"
    )


def test_variable_claude_profile_has_claude_premium_tiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--profile variable-claude` has Claude on premium tiers 4-5 and is locked."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="variable-claude")
    apply_profile_expansion(args, None)

    tier_models = getattr(args, "tier_models", None)
    assert tier_models is not None
    execute_tiers = tier_models.get("execute")
    assert execute_tiers is not None

    assert execute_tiers[4].startswith("claude"), (
        f"tier 4 should be claude, got {execute_tiers[4]!r}"
    )
    assert execute_tiers[5].startswith("claude"), (
        f"tier 5 should be claude, got {execute_tiers[5]!r}"
    )

    # Verify locked — vendor flag should be silently ignored
    args2 = _worker_args(profile="variable-claude", vendor="codex")
    apply_profile_expansion(args2, None)
    tier_models2 = getattr(args2, "tier_models", None)
    assert tier_models2 is not None
    execute_tiers2 = tier_models2.get("execute")
    assert execute_tiers2 is not None
    assert execute_tiers2[4].startswith("claude"), (
        f"locked profile should keep claude on tier 4, got {execute_tiers2[4]!r}"
    )


def test_variable_codex_profile_has_codex_premium_tiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--profile variable-codex` has codex:medium on tier 4 and codex:high on tier 5."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="variable-codex")
    apply_profile_expansion(args, None)

    tier_models = getattr(args, "tier_models", None)
    assert tier_models is not None
    execute_tiers = tier_models.get("execute")
    assert execute_tiers is not None

    assert execute_tiers[4] == "codex:medium", (
        f"tier 4 should be codex:medium, got {execute_tiers[4]!r}"
    )
    assert execute_tiers[5] == "codex:high", (
        f"tier 5 should be codex:high, got {execute_tiers[5]!r}"
    )


def test_variable_codex_deepseek_tiers_match_partnered_convention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """variable-codex DeepSeek tiers use the same canonical specs as partnered."""
    _isolate_user_config(tmp_path, monkeypatch)

    args = _worker_args(profile="variable-codex")
    apply_profile_expansion(args, None)

    tier_models = getattr(args, "tier_models", None)
    assert tier_models is not None
    execute_tiers = tier_models.get("execute")
    assert execute_tiers is not None

    # Tier 1 should be deepseek-flash
    assert "deepseek" in execute_tiers[1]
    assert "flash" in execute_tiers[1]
    # Tiers 2-3 should be deepseek-pro (canonical partnered Fireworks or direct)
    for t in (2, 3):
        assert "deepseek" in execute_tiers[t]
        assert "v4-pro" in execute_tiers[t]
