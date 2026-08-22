from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentbox.cli import build_parser, main
from agentbox import cli as cli_module

from agentbox.config import AgentBoxConfig
from agentbox.guardian.scheduler import ensure_guardian_tasks
from agentbox.guardian.state import GuardianStateStore


def test_cli_guardian_run_once_executes_one_tick_and_exits(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )

    ensure_guardian_tasks(config, datetime(2026, 1, 1, tzinfo=UTC))

    result = main(["guardian", "run-once", "--json"])

    assert result == 0


def test_cli_guardian_pause_and_resume_persist_across_invocations(
    tmp_path, monkeypatch
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )

    pause_result = main(["guardian", "pause", "--json"])
    assert pause_result == 0

    state = GuardianStateStore(config).read()
    assert state["global_pause"]["paused"] is True

    resume_result = main(["guardian", "resume", "--json"])
    assert resume_result == 0

    state = GuardianStateStore(config).read()
    assert state["global_pause"]["paused"] is False


def test_cli_guardian_status_outputs_valid_json(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )

    ensure_guardian_tasks(config, datetime(2026, 1, 1, tzinfo=UTC))

    result = main(["guardian", "status", "--json"])

    assert result == 0


def test_cli_guardian_parser_has_all_subcommands() -> None:
    parser = build_parser()
    args = parser.parse_args(["guardian", "run-once"])
    assert args.command == "guardian"
    assert args.guardian_command == "run-once"

    args = parser.parse_args(["guardian", "run", "--poll-interval", "30"])
    assert args.guardian_command == "run"
    assert args.poll_interval == 30.0

    args = parser.parse_args(["guardian", "pause"])
    assert args.guardian_command == "pause"

    args = parser.parse_args(["guardian", "resume"])
    assert args.guardian_command == "resume"

    args = parser.parse_args(["guardian", "status", "--json"])
    assert args.guardian_command == "status"
    assert args.json is True


def test_cli_install_omp_agent_installs_packaged_agent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"

    result = main(["install-omp-agent", "arnold", "--target", str(target), "--json"])

    assert result == 0
    installed = target / "arnold.md"
    source = Path(__file__).parents[2] / "agentbox" / "agents" / "arnold.md"
    assert installed.is_file()
    assert installed.read_bytes() == source.read_bytes()


def test_cli_install_omp_agent_name_override_changes_filename_and_frontmatter(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"
    source = (Path(__file__).parents[2] / "agentbox" / "agents" / "arnold.md").read_bytes()

    result = main(
        [
            "install-omp-agent",
            "arnold",
            "--name",
            "my-op",
            "--target",
            str(target),
        ]
    )

    assert result == 0
    installed = (target / "my-op.md").read_bytes()
    assert installed.split(b"---", 2)[2] == source.split(b"---", 2)[2]
    assert b"name: my-op\n" in installed
    assert b"name: arnold\n" not in installed


def test_cli_install_omp_agent_description_override_preserves_name_and_body(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"
    source = (Path(__file__).parents[2] / "agentbox" / "agents" / "arnold.md").read_bytes()

    result = main(
        [
            "install-omp-agent",
            "arnold",
            "--description",
            "Op for X",
            "--target",
            str(target),
        ]
    )

    assert result == 0
    installed = (target / "arnold.md").read_bytes()
    assert installed.split(b"---", 2)[2] == source.split(b"---", 2)[2]
    assert b"name: arnold\n" in installed
    assert b'description: "Op for X"\n' in installed
    assert b'Arnold resident operator' not in installed


@pytest.mark.parametrize(
    ("template_name", "output_name"),
    [
        ("..", None),
        (".", None),
        ("a/b", None),
        ("", None),
        ("arnold", ""),
        ("arnold", "unsafe name"),
    ],
)
def test_cli_install_omp_agent_rejects_unsafe_names(
    tmp_path, monkeypatch, template_name, output_name
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"
    argv = ["install-omp-agent", template_name, "--target", str(target)]
    if output_name is not None:
        argv[2:2] = ["--name", output_name]

    result = main(argv)

    assert result == 1
    assert not target.exists()


def test_cli_install_omp_agent_rejects_existing_target_without_clobbering(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"
    target.mkdir()
    installed = target / "arnold.md"
    original = b"existing content\n"
    installed.write_bytes(original)

    result = main(["install-omp-agent", "arnold", "--target", str(target)])

    assert result == 1
    assert installed.read_bytes() == original

def test_cli_install_omp_agent_race_does_not_clobber_and_cleans_tmp(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"
    installed = target / "arnold.md"
    original_link = cli_module.os.link

    def create_target_before_publish(source, destination, *, follow_symlinks=True):
        Path(destination).write_bytes(b"created concurrently\n")
        return original_link(source, destination, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(cli_module.os, "link", create_target_before_publish)

    result = main(["install-omp-agent", "arnold", "--target", str(target)])

    assert result == 1
    assert installed.read_bytes() == b"created concurrently\n"
    assert list(target.glob(".arnold.md.tmp-*")) == []
    assert capsys.readouterr().err == f"agentbox: target already exists: {installed}\n"


def test_cli_install_omp_agent_rejects_block_scalar_description(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    source = tmp_path / "arnold.md"
    target = tmp_path / "agents"
    monkeypatch.setattr(cli_module, "_packaged_omp_agent_path", lambda name: source)

    for marker in (">", "|"):
        source.write_text(
            f"---\nname: arnold\ndescription: {marker}\n  stale continuation\n---\nbody\n",
            encoding="utf-8",
        )

        result = main(
            [
                "install-omp-agent",
                "arnold",
                "--description",
                "replacement",
                "--target",
                str(target),
            ]
        )

        assert result == 1
        assert not target.exists()
        assert (
            capsys.readouterr().err
            == "agentbox: description override requires a single-line frontmatter scalar\n"
        )


def test_cli_install_omp_agent_rejects_unknown_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )
    target = tmp_path / "agents"

    result = main(["install-omp-agent", "does-not-exist", "--target", str(target), "--json"])

    assert result == 1
    assert not target.exists()


def _write_cli_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )


def test_cli_new_resident_creates_exactly_five_files(tmp_path, monkeypatch, capsys) -> None:
    _write_cli_config(tmp_path, monkeypatch)
    repo = tmp_path / "resident-repo"
    repo.mkdir()

    result = main(["new-resident", "my-op", "--repo", str(repo), "--json"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "my-op"
    assert payload["repo"] == str(repo.resolve())
    assert payload["created"] is True
    files = [Path(path) for path in payload["files"]]
    assert len(files) == 5
    assert all(path.is_file() for path in files)
    assert {path.relative_to(repo) for path in files} == {
        Path(".omp/agents/my-op.md"),
        Path(".agentbox/resident_profile.py"),
        Path(".agentbox/resident.env.example"),
        Path(".agentbox/run-resident"),
        Path(".agentbox/my-op-resident.service"),
    }
    profile = (repo / ".agentbox/resident_profile.py").read_text(encoding="utf-8")
    assert "class MyOpResidentProfile(AgentBoxOperatorProfile):" in profile
    env = (repo / ".agentbox/resident.env.example").read_text(encoding="utf-8")
    assert "DISCORD_BOT_TOKEN=" in env
    assert "MEGAPLAN_RESIDENT_PROFILE" not in env
    assert "MEGAPLAN_RESIDENT_STORE_ROOT" not in env
    assert (repo / ".agentbox/run-resident").stat().st_mode & 0o111 == 0o111


def test_cli_new_resident_refuses_collision_without_partial_files(tmp_path, monkeypatch) -> None:
    _write_cli_config(tmp_path, monkeypatch)
    repo = tmp_path / "resident-repo"
    repo.mkdir()
    existing = repo / ".agentbox" / "resident_profile.py"
    existing.parent.mkdir()
    existing.write_text("keep me\n", encoding="utf-8")

    result = main(["new-resident", "astrid", "--repo", str(repo)])

    assert result == 1
    assert existing.read_text(encoding="utf-8") == "keep me\n"
    assert not (repo / ".omp").exists()
    assert list((repo / ".agentbox").iterdir()) == [existing]


def test_cli_new_resident_description_override_and_prompt_body(tmp_path, monkeypatch) -> None:
    _write_cli_config(tmp_path, monkeypatch)
    repo = tmp_path / "resident-repo"
    repo.mkdir()

    result = main(
        [
            "new-resident",
            "astrid",
            "--repo",
            str(repo),
            "--description",
            "Astrid operations",
        ]
    )

    assert result == 0
    agent = (repo / ".omp/agents/astrid.md").read_text(encoding="utf-8")
    assert 'description: "Astrid operations"' in agent
    assert "This file is the project-owned resident persona." in agent


def test_cli_new_resident_profile_imports_and_reads_agent_body(tmp_path, monkeypatch) -> None:
    _write_cli_config(tmp_path, monkeypatch)
    repo = tmp_path / "resident-repo"
    repo.mkdir()
    assert main(["new-resident", "astrid", "--repo", str(repo)]) == 0

    profile_path = repo / ".agentbox/resident_profile.py"
    spec = importlib.util.spec_from_file_location("generated_resident_profile", profile_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    profile = module.AstridResidentProfile(
        store=None,
        authorizer=None,
        config=None,
        confirmation_manager=None,
    )

    assert profile.system_prompt().startswith("# Resident operator")


def test_cli_new_resident_rolls_back_mid_publication(tmp_path, monkeypatch) -> None:
    _write_cli_config(tmp_path, monkeypatch)
    repo = tmp_path / "resident-repo"
    repo.mkdir()
    original_replace = cli_module.os.replace
    calls = 0

    def fail_on_second_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("publication failure")
        return original_replace(source, destination)

    monkeypatch.setattr(cli_module.os, "replace", fail_on_second_replace)

    result = main(["new-resident", "astrid", "--repo", str(repo)])

    assert result == 1
    assert not any(path.is_file() for path in repo.rglob("*"))
    assert not (repo / ".agentbox").exists() or not any((repo / ".agentbox").iterdir())


_RUN_RESIDENT_STUB_LOG_ENV = "RUN_RESIDENT_STUB_LOG"
_FAKE_LAUNCH_SEED = "/fake/custody/seeds/standalone-fake.json"

_PYTHON_STUB_SOURCE = """#!/bin/sh
{
    echo "==="
    echo "cwd=$PWD"
    printf 'argv:'
    for argument in "$@"; do
        printf ' <%s>' "$argument"
    done
    echo
    echo "seed=${MEGAPLAN_RUNTIME_LAUNCH_SEED-}"
} >> "$RUN_RESIDENT_STUB_LOG"
case "$*" in
    *"resident attest"*)
        if [ -n "${RUN_RESIDENT_STUB_ATTEST_FAIL-}" ]; then
            echo '{"success": false, "error": "runtime_launch_attestation_mismatch", "message": "stub admission failure"}'
            exit 2
        fi
        echo "{seed_path}"
        exit 0
        ;;
esac
exit 0
"""


def _render_run_resident(repo: Path, name: str) -> Path:
    content = cli_module._render_resident_template(
        cli_module._resident_template_path("run-resident.tmpl"),
        {
            "NAME": name,
            "PASCAL_NAME": cli_module._resident_pascal_name(name),
            "DESCRIPTION": '"stub"',
            "REPO": str(repo),
        },
    )
    destination = repo / ".agentbox" / "run-resident"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    destination.chmod(0o755)
    return destination


def _init_launcher_repo(tmp_path: Path, name: str) -> tuple[Path, str]:
    import subprocess

    repo = tmp_path / "resident-repo"
    repo.mkdir()
    _render_run_resident(repo, name)
    env_file = repo / ".agentbox" / f"{name}.env"
    env_file.write_text("DISCORD_BOT_TOKEN=real-token\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo, head


def _install_python_stub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import os

    stub_dir = tmp_path / "python-stub"
    stub_dir.mkdir()
    log_path = tmp_path / "python-stub.log"
    for binary in ("python", "python3"):
        stub = stub_dir / binary
        stub.write_text(
            _PYTHON_STUB_SOURCE.replace("{seed_path}", _FAKE_LAUNCH_SEED),
            encoding="utf-8",
        )
        stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv(_RUN_RESIDENT_STUB_LOG_ENV, str(log_path))


def _read_stub_records(tmp_path: Path) -> list[dict[str, str]]:
    log_path = tmp_path / "python-stub.log"
    if not log_path.exists():
        return []
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line == "===":
            if current:
                records.append(current)
            current = {}
        elif line.startswith("cwd="):
            current["cwd"] = line[len("cwd="):]
        elif line.startswith("argv:"):
            current["argv"] = line[len("argv:"):].lstrip()
        elif line.startswith("seed="):
            current["seed"] = line[len("seed="):]
    if current:
        records.append(current)
    return records


def test_run_resident_attests_head_then_execs_discord_with_seed(tmp_path, monkeypatch) -> None:
    import subprocess

    repo, head = _init_launcher_repo(tmp_path, "demo")
    repo = repo.resolve(strict=True)
    _install_python_stub(monkeypatch, tmp_path)
    launcher = repo / ".agentbox" / "run-resident"

    # Deliberately launched from OUTSIDE the repo: the launcher must resolve
    # and cd to the repository root itself.
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    result = subprocess.run(
        [str(launcher)],
        cwd=outside,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    records = _read_stub_records(tmp_path)
    assert len(records) == 2
    attest_record, discord_record = records
    assert attest_record["cwd"] == str(repo)
    assert (
        f"<-m> <arnold_pipelines.megaplan> <resident> <attest>"
        f" <--repo-root> <{repo}> <--expected-head> <{head}>"
        == attest_record["argv"]
    )
    assert discord_record["cwd"] == str(repo)
    assert (
        f"<-m> <arnold_pipelines.megaplan> <resident> <discord>"
        f" <--store-root> <{repo}/.megaplan/resident>"
        f" <--profile> <.agentbox/resident_profile.py:DemoResidentProfile>"
        == discord_record["argv"]
    )
    assert discord_record["seed"] == _FAKE_LAUNCH_SEED


def test_run_resident_forwards_extra_arguments_to_discord(tmp_path, monkeypatch) -> None:
    import subprocess

    repo, _head = _init_launcher_repo(tmp_path, "demo")
    _install_python_stub(monkeypatch, tmp_path)

    result = subprocess.run(
        [str(repo / ".agentbox" / "run-resident"), "--dry-run"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    records = _read_stub_records(tmp_path)
    assert len(records) == 2
    assert records[1]["argv"].endswith("<--dry-run>")


def test_run_resident_refuses_missing_env_file_before_any_launch(tmp_path, monkeypatch) -> None:
    import subprocess

    repo, _head = _init_launcher_repo(tmp_path, "demo")
    (repo / ".agentbox" / "demo.env").unlink()
    _install_python_stub(monkeypatch, tmp_path)

    result = subprocess.run(
        [str(repo / ".agentbox" / "run-resident")],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "missing" in result.stderr and "demo.env" in result.stderr
    assert _read_stub_records(tmp_path) == []


def test_run_resident_refuses_empty_discord_token_before_any_launch(tmp_path, monkeypatch) -> None:
    import subprocess

    repo, _head = _init_launcher_repo(tmp_path, "demo")
    (repo / ".agentbox" / "demo.env").write_text("DISCORD_BOT_TOKEN=\n", encoding="utf-8")
    _install_python_stub(monkeypatch, tmp_path)

    result = subprocess.run(
        [str(repo / ".agentbox" / "run-resident")],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "DISCORD_BOT_TOKEN is empty" in result.stderr
    assert _read_stub_records(tmp_path) == []


def test_run_resident_propagates_attest_failure_without_starting_discord(tmp_path, monkeypatch) -> None:
    import subprocess

    repo, _head = _init_launcher_repo(tmp_path, "demo")
    _install_python_stub(monkeypatch, tmp_path)
    monkeypatch.setenv("RUN_RESIDENT_STUB_ATTEST_FAIL", "1")

    result = subprocess.run(
        [str(repo / ".agentbox" / "run-resident")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "runtime_launch_attestation_mismatch" in result.stdout + result.stderr
    records = _read_stub_records(tmp_path)
    assert len(records) == 1
    assert "<resident> <attest>" in records[0]["argv"]


def _init_empty_megaplan_repo(tmp_path: Path, name: str) -> Path:
    import subprocess

    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def test_resident_dispatch_creates_only_resident_owned_state(
    tmp_path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan.cli import _main as megaplan_main

    repo = _init_empty_megaplan_repo(tmp_path, "resident-repo")
    monkeypatch.chdir(repo)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_MODE", raising=False)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_STORE_ROOT", raising=False)

    first_exit = megaplan_main(["resident", "health"])

    assert first_exit == 0
    # Resident-owned state is created lazily by the FileStore constructor.
    assert (repo / ".megaplan" / "resident").is_dir()
    # Generic runtime layout must not be materialized by resident dispatch.
    for generic in ("plans", "initiatives", "schemas"):
        assert not (repo / ".megaplan" / generic).exists(), generic
    # Repo editor auto-sync must not run for top-level resident dispatch:
    # an absent .gitattributes stays absent and .vscode/settings.json is
    # never created.
    assert not (repo / ".gitattributes").exists()
    assert not (repo / ".vscode" / "settings.json").exists()

    sentinel_bytes = b"*.png binary\n"
    (repo / ".gitattributes").write_bytes(sentinel_bytes)

    second_exit = megaplan_main(["resident", "health"])

    assert second_exit == 0
    assert (repo / ".gitattributes").read_bytes() == sentinel_bytes


def test_non_resident_dispatch_still_initializes_generic_layout(
    tmp_path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan.cli import _main as megaplan_main

    repo = _init_empty_megaplan_repo(tmp_path, "generic-repo")
    monkeypatch.chdir(repo)
    # Isolate HOME so skill auto-sync cannot touch real user directories.
    home = tmp_path / "isolated-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    exit_code = megaplan_main(["brief", "list"])

    assert exit_code == 0
    for generic in ("plans", "initiatives", "schemas"):
        assert (repo / ".megaplan" / generic).is_dir(), generic
