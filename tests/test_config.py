from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import megaplan
import megaplan.cli as cli_module
import megaplan._core.io as io_module
import megaplan.profiles as profiles_module
from megaplan._core import get_effective
from megaplan.profiles import DEFAULT_AGENT_ROUTING
from megaplan.types import CliError, DEFAULTS


@pytest.fixture
def isolated_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_path = tmp_path / ".config" / "megaplan"

    def fake_config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setattr(io_module, "config_dir", fake_config_dir)
    monkeypatch.setattr(cli_module, "config_dir", fake_config_dir)
    return config_path


def test_get_effective_returns_default(isolated_config_dir: Path) -> None:
    assert not (isolated_config_dir / "config.json").exists()
    assert get_effective("execution", "worker_timeout_seconds") == DEFAULTS["execution.worker_timeout_seconds"]


def test_max_critique_concurrency_default_covers_full_core_checks(
    isolated_config_dir: Path,
) -> None:
    # The 'full' robustness tier defines 6 core sub-checks. A default fanout
    # below that count forces serial batches and triples critique wall time
    # (see ticket 01KS03H13JWMVSED6V4584P1P3). Lock the default at the core
    # check count so a regression here can't quietly bring back the 25-min
    # critique grind.
    from megaplan.audits.robustness import checks_for_robustness

    full_core_checks = checks_for_robustness("full")
    default = get_effective("orchestration", "max_critique_concurrency")
    assert default >= len(full_core_checks), (
        f"max_critique_concurrency default ({default}) must cover the "
        f"'full' robustness core check count ({len(full_core_checks)}) "
        "to avoid serialized critique batches"
    )
    assert default == DEFAULTS["orchestration.max_critique_concurrency"]


def test_get_effective_returns_override(isolated_config_dir: Path) -> None:
    isolated_config_dir.mkdir(parents=True, exist_ok=True)
    (isolated_config_dir / "config.json").write_text(
        json.dumps({"execution": {"worker_timeout_seconds": 1234}}),
        encoding="utf-8",
    )

    assert get_effective("execution", "worker_timeout_seconds") == 1234


def test_config_set_numeric(isolated_config_dir: Path) -> None:
    response = megaplan.handle_config(
        Namespace(
            config_action="set",
            key="execution.worker_timeout_seconds",
            value="3600",
        )
    )

    assert response["success"] is True
    assert response["value"] == 3600
    saved = json.loads((isolated_config_dir / "config.json").read_text(encoding="utf-8"))
    assert saved["execution"]["worker_timeout_seconds"] == 3600
    assert isinstance(saved["execution"]["worker_timeout_seconds"], int)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("YeS", True),
        ("on", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("No", False),
        ("off", False),
    ],
)
def test_config_set_execution_auto_approve_bool_tokens(
    isolated_config_dir: Path,
    value: str,
    expected: bool,
) -> None:
    response = megaplan.handle_config(
        Namespace(
            config_action="set",
            key="execution.auto_approve",
            value=value,
        )
    )

    assert response["success"] is True
    assert response["value"] is expected
    saved = json.loads((isolated_config_dir / "config.json").read_text(encoding="utf-8"))
    assert saved["execution"]["auto_approve"] is expected


def test_config_set_execution_auto_approve_invalid_token(isolated_config_dir: Path) -> None:
    with pytest.raises(
        megaplan.CliError,
        match=r"execution\.auto_approve must be one of: true, false, 1, 0, yes, no, on, off",
    ):
        megaplan.handle_config(
            Namespace(
                config_action="set",
                key="execution.auto_approve",
                value="maybe",
            )
        )


@pytest.mark.parametrize("value", ["tiny", "light", "standard", "robust", "superrobust"])
def test_config_set_execution_robustness_enum(
    isolated_config_dir: Path,
    value: str,
) -> None:
    response = megaplan.handle_config(
        Namespace(
            config_action="set",
            key="execution.robustness",
            value=value,
        )
    )

    assert response["success"] is True
    assert response["value"] == value
    saved = json.loads((isolated_config_dir / "config.json").read_text(encoding="utf-8"))
    assert saved["execution"]["robustness"] == value


def test_config_set_execution_robustness_invalid_value(isolated_config_dir: Path) -> None:
    with pytest.raises(
        megaplan.CliError,
        match=r"execution\.robustness must be one of: bare, light, full, thorough, extreme, tiny, standard, robust, superrobust",
    ):
        megaplan.handle_config(
            Namespace(
                config_action="set",
                key="execution.robustness",
                value="turbo",
            )
        )


def test_config_set_invalid_key(isolated_config_dir: Path) -> None:
    with pytest.raises(megaplan.CliError, match=r"Unknown config key 'foo\.bar'"):
        megaplan.handle_config(
            Namespace(
                config_action="set",
                key="foo.bar",
                value="1",
            )
        )


def test_config_set_invalid_type(isolated_config_dir: Path) -> None:
    with pytest.raises(
        megaplan.CliError,
        match=r"execution\.worker_timeout_seconds must be an integer",
    ):
        megaplan.handle_config(
            Namespace(
                config_action="set",
                key="execution.worker_timeout_seconds",
                value="notanumber",
            )
        )


def test_config_set_orchestration_mode(isolated_config_dir: Path) -> None:
    response = megaplan.handle_config(
        Namespace(
            config_action="set",
            key="orchestration.mode",
            value="inline",
        )
    )

    assert response["success"] is True
    assert response["value"] == "inline"
    saved = json.loads((isolated_config_dir / "config.json").read_text(encoding="utf-8"))
    assert saved["orchestration"]["mode"] == "inline"


def test_config_set_orchestration_mode_invalid(isolated_config_dir: Path) -> None:
    with pytest.raises(
        megaplan.CliError,
        match=r"orchestration\.mode must be 'inline' or 'subagent'",
    ):
        megaplan.handle_config(
            Namespace(
                config_action="set",
                key="orchestration.mode",
                value="bogus",
            )
        )


def test_build_parser_init_flags_are_tristate() -> None:
    from megaplan.cli import build_parser

    parser = build_parser()

    parsed = parser.parse_args(["init", "--project-dir", "/tmp", "idea"])
    explicit = parser.parse_args(
        ["init", "--project-dir", "/tmp", "--auto-approve", "--robustness", "robust", "idea"]
    )

    assert parsed.auto_approve is None
    assert parsed.robustness is None
    assert explicit.auto_approve is True
    assert explicit.robustness == "robust"


def test_handle_init_uses_config_defaults_when_flags_omitted(isolated_config_dir: Path, tmp_path: Path) -> None:
    isolated_config_dir.mkdir(parents=True, exist_ok=True)
    (isolated_config_dir / "config.json").write_text(
        json.dumps({"execution": {"auto_approve": True, "robustness": "robust"}}),
        encoding="utf-8",
    )
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()

    response = megaplan.handle_init(
        root,
        Namespace(
            project_dir=str(project_dir),
            name="config-backed-init",
            auto_approve=None,
            robustness=None,
            hermes=None,
            phase_model=[],
            idea="idea",
        ),
    )
    state = json.loads((root / ".megaplan" / "plans" / response["plan"] / "state.json").read_text(encoding="utf-8"))

    assert response["auto_approve"] is True
    # Legacy ``robust`` in stored config is normalized to canonical ``thorough``.
    assert response["robustness"] == "thorough"
    assert state["config"]["auto_approve"] is True
    assert state["config"]["robustness"] == "thorough"


def test_handle_init_explicit_robustness_beats_config_default(
    isolated_config_dir: Path,
    tmp_path: Path,
) -> None:
    isolated_config_dir.mkdir(parents=True, exist_ok=True)
    (isolated_config_dir / "config.json").write_text(
        json.dumps({"execution": {"auto_approve": True, "robustness": "robust"}}),
        encoding="utf-8",
    )
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()

    response = megaplan.handle_init(
        root,
        Namespace(
            project_dir=str(project_dir),
            name="explicit-robustness-init",
            auto_approve=None,
            robustness="light",
            hermes=None,
            phase_model=[],
            idea="idea",
        ),
    )
    state = json.loads((root / ".megaplan" / "plans" / response["plan"] / "state.json").read_text(encoding="utf-8"))

    assert response["auto_approve"] is True
    assert response["robustness"] == "light"
    assert state["config"]["auto_approve"] is True
    assert state["config"]["robustness"] == "light"


def test_handle_config_use_profile_writes_all_phase_keys_and_preserves_unrelated(
    isolated_config_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Make sure user-layer profiles.toml lookup also goes through the isolated dir
    # so a stray real ~/.config/megaplan/profiles.toml can't contaminate the test.
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: isolated_config_dir,
    )

    isolated_config_dir.mkdir(parents=True, exist_ok=True)
    config_path = isolated_config_dir / "config.json"
    # Pre-seed unrelated keys to verify they survive, plus a stale agents.plan
    # value to verify it gets overwritten by the profile.
    config_path.write_text(
        json.dumps(
            {
                "execution": {"auto_approve": True, "robustness": "robust"},
                "agents": {"plan": "codex"},
            }
        ),
        encoding="utf-8",
    )

    response = megaplan.handle_config(
        Namespace(config_action="use-profile", name="apex")
    )

    assert response["success"] is True
    assert response["action"] == "use-profile"
    assert response["profile"] == "apex"
    # All 12 phases from DEFAULT_AGENT_ROUTING should be present in `applied`.
    assert set(response["applied"].keys()) == set(DEFAULT_AGENT_ROUTING.keys())

    on_disk = json.loads(config_path.read_text(encoding="utf-8"))

    # Unrelated section preserved verbatim.
    assert on_disk["execution"] == {"auto_approve": True, "robustness": "robust"}

    # Every phase from the apex profile written, and the stale plan value
    # was overwritten.
    for phase in DEFAULT_AGENT_ROUTING:
        assert phase in on_disk["agents"]
    assert on_disk["agents"]["plan"] == "claude"
    # Spec values from `config profiles show apex` should match what was
    # written to disk.
    shown = megaplan.handle_config(
        Namespace(config_action="profiles", profiles_action="show", name="apex")
    )
    assert on_disk["agents"] == shown["profile"]


def test_handle_config_use_profile_unknown_profile_raises(
    isolated_config_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: isolated_config_dir,
    )

    with pytest.raises(CliError) as exc_info:
        megaplan.handle_config(
            Namespace(config_action="use-profile", name="definitely-not-a-profile")
        )

    assert exc_info.value.code == "unknown_profile"
    # The error message should list at least one known built-in profile so the
    # user can recover without consulting docs.
    assert "apex" in exc_info.value.message


# ---------------------------------------------------------------------------
# Shannon config validation
# ---------------------------------------------------------------------------


def test_config_accepts_shannon_as_agent() -> None:
    """Config agent overrides accept 'shannon'."""
    from megaplan.profiles import KNOWN_AGENTS
    assert "shannon" in KNOWN_AGENTS


def _init_adaptive(
    *,
    isolated_config_dir: Path,
    tmp_path: Path,
    profile: str | None,
    cli_flag: bool | None,
    config_value: bool | None,
) -> bool:
    """Run handle_init with the given inputs and return the seeded
    config['adaptive_critique']."""
    isolated_config_dir.mkdir(parents=True, exist_ok=True)
    cfg: dict = {"execution": {}}
    if config_value is not None:
        cfg["execution"]["adaptive_critique"] = config_value
    (isolated_config_dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir(exist_ok=True)
    project_dir.mkdir(exist_ok=True)
    response = megaplan.handle_init(
        root,
        Namespace(
            project_dir=str(project_dir),
            name="adaptive-init",
            auto_approve=None,
            robustness=None,
            hermes=None,
            phase_model=[],
            idea="idea",
            profile=profile,
            adaptive_critique=cli_flag,
        ),
    )
    state = json.loads(
        (root / ".megaplan" / "plans" / response["plan"] / "state.json").read_text(encoding="utf-8")
    )
    return state["config"]["adaptive_critique"]


def test_adaptive_critique_on_by_default_for_partnered(
    isolated_config_dir: Path, tmp_path: Path
) -> None:
    """Premium-bearing profile: profile-level adaptive_critique=true wins when
    nothing is pinned (no CLI flag, no explicit config)."""
    assert _init_adaptive(
        isolated_config_dir=isolated_config_dir,
        tmp_path=tmp_path,
        profile="partnered",
        cli_flag=None,
        config_value=None,
    ) is True


def test_adaptive_critique_off_by_default_for_open_only_profile(
    isolated_config_dir: Path, tmp_path: Path
) -> None:
    """Open-only profile (no premium slot, no adaptive_critique field) must NOT
    get adaptive critique on by default — it would force a premium evaluator
    key into a deliberately key-free setup."""
    assert _init_adaptive(
        isolated_config_dir=isolated_config_dir,
        tmp_path=tmp_path,
        profile="all-open",
        cli_flag=None,
        config_value=None,
    ) is False


def test_adaptive_critique_off_by_default_for_solo(
    isolated_config_dir: Path, tmp_path: Path
) -> None:
    assert _init_adaptive(
        isolated_config_dir=isolated_config_dir,
        tmp_path=tmp_path,
        profile="solo",
        cli_flag=None,
        config_value=None,
    ) is False


def test_adaptive_critique_explicit_config_beats_profile_default(
    isolated_config_dir: Path, tmp_path: Path
) -> None:
    """User pinning adaptive_critique=false in config overrides the partnered
    profile's true default."""
    assert _init_adaptive(
        isolated_config_dir=isolated_config_dir,
        tmp_path=tmp_path,
        profile="partnered",
        cli_flag=None,
        config_value=False,
    ) is False


def test_adaptive_critique_cli_flag_forces_on_for_open_profile(
    isolated_config_dir: Path, tmp_path: Path
) -> None:
    """Explicit --adaptive-critique still force-enables, even on an open-only
    profile (the user opted in deliberately)."""
    assert _init_adaptive(
        isolated_config_dir=isolated_config_dir,
        tmp_path=tmp_path,
        profile="all-open",
        cli_flag=True,
        config_value=None,
    ) is True
