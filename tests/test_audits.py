from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines import megaplan
import arnold.pipelines.megaplan._core
import arnold.pipelines.megaplan.cli as megaplan_cli

from tests.conftest import make_args_factory, run_main_json


def test_global_setup_creates_files(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    result = megaplan.handle_setup_global(force=False, home=home)
    assert result["success"] is True
    skill_path = home / ".claude" / "skills" / "megaplan" / "SKILL.md"
    assert skill_path.exists()


def test_global_setup_skips_not_installed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = megaplan.handle_setup_global(force=False, home=home)
    assert result["success"] is False
    assert all(r.get("skipped", False) or r.get("reason") == "not installed" for r in result["installed"])


def test_global_setup_idempotent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    megaplan.handle_setup_global(force=False, home=home)
    result2 = megaplan.handle_setup_global(force=False, home=home)
    assert result2["success"] is True
    assert any(r.get("skipped") for r in result2["installed"])


def test_global_setup_force_overwrites(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    megaplan.handle_setup_global(force=False, home=home)
    result = megaplan.handle_setup_global(force=True, home=home)
    assert result["success"] is True
    # Force should NOT skip
    claude_result = next(r for r in result["installed"] if r.get("agent") == "claude")
    assert claude_result.get("skipped") is False


def test_global_setup_multiple_agents(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir(parents=True)
    result = megaplan.handle_setup_global(force=False, home=home)
    assert result["success"] is True
    agents_installed = [r["agent"] for r in result["installed"] if not r.get("skipped", False) and r.get("reason") != "not installed"]
    assert "claude" in agents_installed
    assert "codex" in agents_installed


def test_global_setup_installs_codex_subagent_appendix(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)

    result = megaplan.handle_setup_global(force=False, home=home)

    assert result["success"] is True
    skill_path = home / ".codex" / "skills" / "megaplan" / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")
    assert "Before the first CLI call, resolve a working launcher and reuse it for the whole run." in content
    assert "command presence alone is not enough" in content
    assert "Only use bare `megaplan ...` if that exact form already succeeded during this check." in content
    assert "This appendix is Codex-specific." in content
    assert "`spawn_agent`" in content
    assert "`wait_agent`" in content
    assert "`resume_agent`" in content
    assert "`send_input`" in content
    assert "`close_agent`" in content


def test_load_save_config_roundtrip(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan._core import load_config, save_config
    config = {"agents": {"plan": "codex"}, "custom": True}
    save_config(config, tmp_path)
    loaded = load_config(tmp_path)
    assert loaded == config


def test_load_config_corrupt_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from arnold.pipelines.megaplan._core import config_dir, load_config
    config_path = config_dir(tmp_path) / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("not valid json!!!", encoding="utf-8")
    result = load_config(tmp_path)
    assert result == {}


def test_config_dir_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from arnold.pipelines.megaplan._core import config_dir
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config_dir() == tmp_path / "xdg" / "megaplan"


def test_setup_global_writes_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr(megaplan.cli, "detect_available_agents", lambda: ["claude"])
    result = megaplan.handle_setup_global(force=False, home=home)
    assert "config_path" in result
    assert "routing" in result


def test_step_command_help_and_parser_shape(capsys: pytest.CaptureFixture[str]) -> None:
    parser = megaplan.cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["step", "--help"])

    help_text = capsys.readouterr().out
    parsed = parser.parse_args(["step", "add", "--plan", "demo", "--after", "S3", "Add docs"])

    assert "add" in help_text
    assert "remove" in help_text
    assert "move" in help_text
    assert parsed.command == "step"
    assert parsed.step_action == "add"
    assert parsed.plan == "demo"
    assert parsed.after == "S3"
    assert parsed.description == "Add docs"
    assert megaplan.cli.COMMAND_HANDLERS["step"] is megaplan.handle_step


def test_init_produces_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    response = megaplan.handle_init(root, make_args_factory(project_dir)())
    assert response["success"] is True
    assert "plan" in response
    assert response["state"] == megaplan.STATE_INITIALIZED


def test_list_returns_empty(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    ensure_runtime_layout(root)
    response = megaplan.handle_list(root, Namespace(plan=None, no_tree=True))
    assert response["plans"] == []


def test_invalid_command_returns_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    exit_code = megaplan.main(["init", "--project-dir", str(tmp_path), "test idea"])
    assert exit_code == 0  # init should succeed


def test_debt_list_on_empty_registry_returns_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / ".megaplan").mkdir()

    exit_code, payload = run_main_json(["debt", "list"], cwd=root, capsys=capsys, monkeypatch=monkeypatch)

    assert exit_code == 0
    assert payload["success"] is True
    assert payload["step"] == "debt"
    assert payload["action"] == "list"
    assert payload["details"]["entries"] == []
    assert payload["details"]["by_subsystem"] == []


def test_debt_add_and_list_increment_matching_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / ".megaplan").mkdir()

    exit_code, add_one = run_main_json(
        [
            "debt",
            "add",
            "--subsystem",
            "timeout-recovery",
            "--concern",
            "Timeout recovery: Retry backoff is missing",
            "--flag-ids",
            "FLAG-001",
            "--plan",
            "plan-a",
        ],
        cwd=root,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert exit_code == 0
    assert add_one["details"]["entry"]["id"] == "DEBT-001"

    exit_code, _add_two = run_main_json(
        [
            "debt",
            "add",
            "--subsystem",
            "timeout-recovery",
            "--concern",
            "Timeout recovery: retry backoff is missing",
            "--flag-ids",
            "FLAG-002",
            "--plan",
            "plan-b",
        ],
        cwd=root,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert exit_code == 0

    exit_code, payload = run_main_json(["debt", "list"], cwd=root, capsys=capsys, monkeypatch=monkeypatch)

    assert exit_code == 0
    assert len(payload["details"]["entries"]) == 1
    entry = payload["details"]["entries"][0]
    assert entry["occurrence_count"] == 2
    assert entry["flag_ids"] == ["FLAG-001", "FLAG-002"]
    assert entry["plan_ids"] == ["plan-a", "plan-b"]
    assert payload["details"]["by_subsystem"][0]["subsystem"] == "timeout-recovery"


def test_debt_resolve_hides_entry_from_default_list_but_not_all(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / ".megaplan").mkdir()

    _exit_code, add_payload = run_main_json(
        [
            "debt",
            "add",
            "--subsystem",
            "observation",
            "--concern",
            "Observation: Missing event logging",
            "--flag-ids",
            "FLAG-010",
            "--plan",
            "plan-a",
        ],
        cwd=root,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    debt_id = add_payload["details"]["entry"]["id"]

    exit_code, resolve_payload = run_main_json(
        ["debt", "resolve", debt_id, "--plan", "plan-b"],
        cwd=root,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert exit_code == 0
    assert resolve_payload["details"]["entry"]["resolved"] is True
    assert resolve_payload["details"]["entry"]["resolved_by"] == "plan-b"

    exit_code, list_payload = run_main_json(["debt", "list"], cwd=root, capsys=capsys, monkeypatch=monkeypatch)
    assert exit_code == 0
    assert list_payload["details"]["entries"] == []

    exit_code, list_all_payload = run_main_json(["debt", "list", "--all"], cwd=root, capsys=capsys, monkeypatch=monkeypatch)
    assert exit_code == 0
    assert len(list_all_payload["details"]["entries"]) == 1
    assert list_all_payload["details"]["entries"][0]["resolved"] is True


def test_setup_local_creates_agents_file(tmp_path: Path) -> None:
    args = Namespace(
        local=True,
        target_dir=str(tmp_path),
        force=False,
    )
    response = megaplan.handle_setup(args)
    assert response["success"] is True
    assert (tmp_path / "AGENTS.md").exists()


def test_config_show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    args = Namespace(config_action="show")
    response = megaplan.handle_config(args)
    assert response["success"] is True
    assert "routing" in response


def test_config_set_and_reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    set_args = Namespace(config_action="set", key="agents.plan", value="codex")
    response = megaplan.handle_config(set_args)
    assert response["success"] is True
    assert response["value"] == "codex"

    reset_args = Namespace(config_action="reset")
    response = megaplan.handle_config(reset_args)
    assert response["success"] is True


def test_config_set_invalid_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    args = Namespace(config_action="set", key="badkey", value="codex")
    with pytest.raises(megaplan.CliError, match="agents"):
        megaplan.handle_config(args)


def test_config_set_invalid_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    args = Namespace(config_action="set", key="agents.nosuchstep", value="codex")
    with pytest.raises(megaplan.CliError, match="Unknown step"):
        megaplan.handle_config(args)


def test_config_set_invalid_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    args = Namespace(config_action="set", key="agents.plan", value="nosuchagent")
    with pytest.raises(megaplan.CliError, match="Unknown agent"):
        megaplan.handle_config(args)
