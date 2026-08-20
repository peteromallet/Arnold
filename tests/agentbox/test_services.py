from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentbox import services
from agentbox.reset_notifications import list_reset_notifications
from agentbox.services import (
    DISCORD_RESIDENT_RESTART_COMMAND,
    execute_prepared_restart,
    list_services,
    restart_service,
    service_logs,
)
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    COMPATIBILITY_ONLY_KEY,
    MANIFEST_SCHEMA_VERSION,
    load_manifest,
)
from arnold_pipelines.megaplan.resident.provenance import DELEGATION_CONTEXT_ENV


@pytest.fixture(autouse=True)
def _clear_resident_delegation_context(monkeypatch) -> None:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)


class _DetachedProcess:
    pid = 424242


def _fake_detached_popen(*_args, **_kwargs):
    return _DetachedProcess()


def _valid_manifest(runtime_root: str | Path) -> dict[str, object]:
    """A manifest the canonical validator (``load_manifest``) accepts: schema
    "1" with every required top-level and nested key (G5 round 15 — the
    schema-less ``{"epic": {"runtime_root": ...}}`` shape is canonically
    invalid and must never be blessed as a valid manifest)."""
    now = datetime.now(timezone.utc).isoformat()
    root = str(runtime_root)
    return {
        "runtime_id": "agentbox-runtime-test",
        "schema": MANIFEST_SCHEMA_VERSION,
        "generation": 1,
        "epic_id": "agentbox-test-epic",
        "state": "active",
        "owner": "test",
        "base": {
            "ref": "refs/heads/base/editable-install",
            "commit": "0" * 40,
            "editable_install_path": root,
            "venv_path": f"{root}/venv",
        },
        "epic": {
            "branch": "fixer/agentbox-test",
            "worktree_path": root,
            "venv_path": f"{root}/venv",
            "runtime_root": root,
            "expected_head": "0" * 40,
            "repair_bin": f"{root}/venv/bin/arnold-babysitter",
            "deps_lockfile": f"{root}/uv.lock",
        },
        "indirection": {
            "host_path": root,
            "container_path": "/workspace/agentbox-test",
            "mount_table": [],
            "execution_namespace": "agentbox-test-ns",
            "verified_head": "0" * 40,
            "last_verified_at": now,
            "attestation": {
                "module_file": f"{root}/arnold_pipelines/__init__.py",
                "module_digest": "0" * 64,
                "mount_id": "0:42",
            },
        },
        "policy": {
            "policy_sha": "0" * 64,
            "model_policy_sha": "0" * 64,
            "sync_policy": "manifest-only",
        },
        "promotions": [],
        "timestamps": {"created": now, "updated": now, "closed": None},
        "gc_policy": "keep",
        "commands": [],
    }


def test_list_services_returns_expected_service_names() -> None:
    services = list_services()
    names = {service["name"] for service in services}
    assert "arnold-guardian" in names
    assert "agentbox-discord-resident" in names


def test_list_services_returns_unknown_when_systemctl_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)

    services = list_services()

    assert all(service["status"] == "unknown" for service in services)
    assert all(service["loaded"] is None for service in services)
    assert all(service["active"] is None for service in services)


def test_service_logs_returns_ok_false_for_unknown_service() -> None:
    result = service_logs("nonexistent")
    assert result["ok"] is False
    assert "unknown service" in result["error"]


def test_restart_service_returns_ok_false_for_unknown_service() -> None:
    result = restart_service("nonexistent")
    assert result["ok"] is False
    assert "unknown service" in result["error"]


def test_resident_restart_uses_guarded_tmux_pane_without_systemctl(
    monkeypatch,
    tmp_path,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
    )

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[1] == "list-panes":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=(
                    "%39\t1989952\t0\tbash\t"
                    "python -m arnold_pipelines.megaplan resident discord --mode dev\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", _fake_detached_popen)
    monkeypatch.setattr(
        services,
        "_resident_runtime_request",
        lambda: {"runtime_source": "/workspace/runtime", "runtime_revision": "a" * 40},
    )
    monkeypatch.setattr(
        "agentbox.services._wait_for_tmux_resident",
        lambda pane_id, *, old_pane_pid: {
            "ok": True,
            "pane_id": pane_id,
            "old_pane_pid": old_pane_pid,
            "pane_pid": 2000001,
            "resident_pid": 2000002,
        },
    )

    result = restart_service("agentbox-discord-resident", notification_root=tmp_path)

    assert result["ok"] is True
    assert result["backend"] == "tmux"
    assert result["safety"]["stop_scope"] == (
        "canonical Discord resident tmux pane only"
    )
    assert result["accepted"] is True
    assert result["restart_completed"] is False
    assert result["notification"]["acknowledgement"] == {}
    assert calls[0][:5] == [
        "tmux",
        "list-panes",
        "-t",
        "=megaplan-resident-discord",
        "-F",
    ]
    finalized = execute_prepared_restart(
        result["notification"]["notification_id"], notification_root=tmp_path
    )
    assert finalized["ok"] is True
    assert finalized["health"]["resident_pid"] == 2000002
    assert calls[2] == ["tmux", "respawn-pane", "-k", "-t", "%39"]
    state = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert state["restart"]["status"] == "succeeded"


def test_replayed_discord_restart_does_not_launch_second_supervisor(
    monkeypatch, tmp_path
) -> None:
    provenance = {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "resident_conversation_id": "rconv-source",
        "resident_turn_id": "turn-source",
        "source_record_id": "msg-source",
        "conversation_key": "discord:dm:301463647895683072",
        "discord_message_id": "1525445255711952977",
        "reply_to_message_id": "1525445255711952977",
        "dm_user_id": "301463647895683072",
        "source_kind": "discord_inbound_message",
    }
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(provenance))
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "%39\t1989952\t0\tbash\t"
                "python -m arnold_pipelines.megaplan resident discord --mode dev\n"
            ),
            stderr="",
        ),
    )
    launches = []

    def fake_popen(*args, **kwargs):
        launches.append((args, kwargs))
        return _DetachedProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        services,
        "_resident_runtime_request",
        lambda: {"runtime_source": "/workspace/runtime", "runtime_revision": "a" * 40},
    )

    first = restart_service("agentbox-discord-resident", notification_root=tmp_path)
    replay = restart_service("agentbox-discord-resident", notification_root=tmp_path)

    assert first["accepted"] is True
    assert replay["ok"] is True
    assert replay["accepted"] is False
    assert replay["duplicate"] is True
    assert replay["already_processed"] is True
    assert replay["notification"]["notification_id"] == first["notification"]["notification_id"]
    assert len(launches) == 1
    assert len(list(tmp_path.glob("reset-*.json"))) == 1


def test_runtime_request_reads_worktree_revision(tmp_path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    git_dir = tmp_path / "repo.git" / "worktrees" / "runtime"
    common = tmp_path / "repo.git"
    runtime.mkdir()
    git_dir.mkdir(parents=True)
    (runtime / ".git").write_text(f"gitdir: {git_dir}\n")
    (git_dir / "HEAD").write_text("ref: refs/heads/runtime\n")
    (git_dir / "commondir").write_text("../..\n")
    (common / "refs" / "heads").mkdir(parents=True)
    (common / "refs" / "heads" / "runtime").write_text("a" * 40 + "\n")
    manifest = tmp_path / "runtime-manifest.json"
    manifest.write_text(
        json.dumps(_valid_manifest(runtime)),
        encoding="utf-8",
    )
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))

    assert services._resident_runtime_request() == {
        "runtime_source": str(runtime.resolve()),
        "runtime_revision": "a" * 40,
    }


def test_manifest_runtime_root_fails_closed_on_present_but_invalid(
    monkeypatch, tmp_path
) -> None:
    """A PRESENT-but-invalid manifest never binds the resident runtime (G5).

    Only a canonically schema-valid, non-``compatibility_only`` manifest with
    a nonempty ``epic.runtime_root`` yields the root. The schema-less minimal
    shape that previously bound a runtime (``epic.runtime_root`` present but
    no schema), corrupt JSON, an empty root, and a ``compatibility_only``
    pointer all return ``""`` (unbound, fail closed) — matching the T-0024
    absent-vs-invalid contract.
    """

    def root_for(payload: str | None, name: str) -> str:
        path = tmp_path / name
        if payload is not None:
            path.write_text(payload, encoding="utf-8")
        monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(path))
        return services._manifest_runtime_root()

    tree = tmp_path / "tree"
    tree.mkdir()
    valid_payload = _valid_manifest(tree)

    # Schema-valid manifest -> root returned (bound). The canonical validator
    # accepting the fixture proves it is not the schema-less blessed shape.
    valid_path = tmp_path / "valid.json"
    valid_path.write_text(json.dumps(valid_payload), encoding="utf-8")
    assert load_manifest(valid_path).epic["runtime_root"] == str(tree)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(valid_path))
    assert services._manifest_runtime_root() == str(tree)

    # Schema-invalid minimal shape WITH epic.runtime_root -> "" (G5 round 15:
    # the raw-parse reader bound this; the canonical validator refuses it).
    assert root_for(
        json.dumps({"epic": {"runtime_root": str(tree)}}), "schema-invalid.json"
    ) == ""

    # compatibility_only pointer (schema-valid but demoted) -> "".
    assert root_for(
        json.dumps({**valid_payload, COMPATIBILITY_ONLY_KEY: True}),
        "compatibility-only.json",
    ) == ""

    # Corrupt JSON -> "".
    assert root_for("{not valid json", "corrupt.json") == ""

    # Missing file -> "" (genuinely absent stays unbound).
    assert root_for(None, "missing.json") == ""

    # Present but empty runtime_root -> "" (unbound).
    empty_root = dict(valid_payload)
    empty_root["epic"] = {**valid_payload["epic"], "runtime_root": "   "}
    assert root_for(json.dumps(empty_root), "empty-root.json") == ""


def test_resident_systemd_restart_refuses_unbound_manifest(
    monkeypatch, tmp_path
) -> None:
    """A missing, corrupt, root-less, schema-invalid, or compatibility-only
    manifest never launches the restart supervisor.

    The Discord resident restart binds idempotency to the manifest-pinned
    runtime source+revision; with no binding the restart is refused before
    any notification reservation or detached supervisor launch (G5).
    """

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/systemctl")

    def fake_run(argv, **kwargs):
        if argv[1] == "show":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="KillMode=process\nExecStop=\nExecStopPost=\nMainPID=12345\n",
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    launches: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: launches.append(args) or _DetachedProcess(),
    )

    manifest_states = {
        "missing": None,
        "corrupt": "{not valid json",
        "root-less": json.dumps({"epic": {}}),
        "no-epic": json.dumps({}),
        "schema-invalid-with-root": json.dumps({"epic": {"runtime_root": "/tmp/x"}}),
        "compatibility-only": json.dumps(
            {**_valid_manifest(tmp_path / "runtime"), COMPATIBILITY_ONLY_KEY: True}
        ),
    }
    for label, payload in manifest_states.items():
        manifest = tmp_path / f"manifest-{label}.json"
        if payload is not None:
            manifest.write_text(payload, encoding="utf-8")
        monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
        result = restart_service("agentbox-discord-resident", notification_root=tmp_path)

        assert result["ok"] is False, label
        assert result["backend"] == "systemd"
        assert "runtime manifest is missing, corrupt, or root-less" in result["error"]
        assert result["safety"]["stop_scope"] == "resident main process only"
        assert DISCORD_RESIDENT_RESTART_COMMAND in result["fix_command"]

    assert launches == []
    assert list_reset_notifications(notification_root=tmp_path)["records"] == []


def test_resident_tmux_restart_refuses_unbound_manifest(
    monkeypatch, tmp_path
) -> None:
    """The tmux resident path also fails closed without a manifest binding."""

    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "%39\t1989952\t0\tbash\t"
                "python -m arnold_pipelines.megaplan resident discord --mode dev\n"
            ),
            stderr="",
        ),
    )
    launches: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: launches.append(args) or _DetachedProcess(),
    )

    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(tmp_path / "absent-manifest.json"))
    result = restart_service("agentbox-discord-resident", notification_root=tmp_path)

    assert result["ok"] is False
    assert result["backend"] == "tmux"
    assert "runtime manifest is missing, corrupt, or root-less" in result["error"]
    assert result["safety"]["stop_scope"] == "canonical Discord resident tmux pane only"
    assert launches == []
    assert list_reset_notifications(notification_root=tmp_path)["records"] == []


def test_resident_tmux_restart_marks_notification_failed_when_supervisor_cannot_launch(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
    )

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "%39\t1989952\t0\tbash\t"
                "python -m arnold_pipelines.megaplan resident discord --mode dev\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("cannot fork")),
    )
    monkeypatch.setattr(
        services,
        "_resident_runtime_request",
        lambda: {"runtime_source": "/workspace/runtime", "runtime_revision": "a" * 40},
    )

    result = restart_service("agentbox-discord-resident", notification_root=tmp_path)

    assert result["ok"] is False
    state = list_reset_notifications(notification_root=tmp_path)
    assert state["delivery_status_counts"] == {"pending": 1}


def test_resident_tmux_restart_refuses_unrecognized_pane_command(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
    )

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="%39\t1989952\t0\tbash\tpython -m unrelated.worker\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = restart_service("agentbox-discord-resident")

    assert result["ok"] is False
    assert result["backend"] == "tmux"
    assert result["safety"]["command_marker_present"] is False
    assert "does not match" in result["error"]
    assert len(calls) == 1


def test_resident_restart_refuses_unsafe_installed_kill_mode(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/systemctl")

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="KillMode=control-group\nExecStop=\nExecStopPost=\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = restart_service("agentbox-discord-resident")

    assert result["ok"] is False
    assert result["safety"]["required_kill_mode"] == "process"
    assert calls == [
        [
            "systemctl",
            "show",
            "-p",
            "KillMode",
            "-p",
            "ExecStop",
            "-p",
            "ExecStopPost",
            "-p",
            "MainPID",
            "agentbox-discord-resident.service",
        ]
    ]
    assert DISCORD_RESIDENT_RESTART_COMMAND in result["fix_command"]


def test_resident_restart_targets_only_guarded_service(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/systemctl")

    def fake_run(argv, **kwargs):
        calls.append(argv)
        stdout = (
            "KillMode=process\nExecStop=\nExecStopPost=\nMainPID=12345\n"
            if argv[1] == "show"
            else ""
        )
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", _fake_detached_popen)
    monkeypatch.setattr(
        services,
        "_resident_runtime_request",
        lambda: {"runtime_source": "/workspace/runtime", "runtime_revision": "a" * 40},
    )

    result = restart_service("agentbox-discord-resident", notification_root=tmp_path)

    assert result["ok"] is True
    assert result["accepted"] is True
    assert result["safety"]["stop_scope"] == "resident main process only"
    assert result["safety"]["preserves"] == [
        "resident-managed detached subagents",
        "tmux-backed Megaplan and cloud chains",
    ]
    assert calls == [
        [
            "systemctl",
            "show",
            "-p",
            "KillMode",
            "-p",
            "ExecStop",
            "-p",
            "ExecStopPost",
            "-p",
            "MainPID",
            "agentbox-discord-resident.service",
        ],
    ]
    assert result["notification"]["restart"]["status"] == "supervisor_started"
    assert result["notification"]["acknowledgement"] == {}


def test_failed_guarded_restart_never_enables_a_success_confirmation(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/systemctl")

    def fake_run(argv, **kwargs):
        if argv[1] == "show":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="KillMode=process\nExecStop=\nExecStopPost=\nMainPID=12345\n",
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="restart failed")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", _fake_detached_popen)
    monkeypatch.setattr(
        services,
        "_resident_runtime_request",
        lambda: {"runtime_source": "/workspace/runtime", "runtime_revision": "a" * 40},
    )

    result = restart_service("agentbox-discord-resident", notification_root=tmp_path)

    assert result["ok"] is True
    finalized = execute_prepared_restart(
        result["notification"]["notification_id"], notification_root=tmp_path
    )
    assert finalized["ok"] is False
    assert finalized["notification"]["restart"]["status"] == "failed"
    assert finalized["notification"]["delivery"]["status"] == "pending"
    state = list_reset_notifications(notification_root=tmp_path)
    assert state["delivery_status_counts"] == {"pending": 1}


def test_resident_restart_refuses_custom_stop_hook(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/systemctl")

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                "KillMode=process\n"
                "ExecStop={ path=/usr/bin/pkill ; argv[]=/usr/bin/pkill worker ; }\n"
                "ExecStopPost=\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = restart_service("agentbox-discord-resident")

    assert result["ok"] is False
    assert result["safety"]["custom_stop_hooks"] == ["ExecStop"]
    assert "no ExecStop/ExecStopPost hooks" in result["error"]


def test_main_process_stop_preserves_detached_agent_and_cloud_session() -> None:
    """Exercise the process boundary selected by systemd KillMode=process.

    This deliberately signals only the simulated resident main PID. The
    resident-launched worker is session-detached like the managed Codex
    supervisor, while the second process represents an independent tmux/cloud
    session. No live systemd unit, bot, tmux server, or remote host is touched.
    """

    sleeper = "import time; time.sleep(60)"
    resident_script = (
        "import subprocess, sys, time; "
        f"child = subprocess.Popen([sys.executable, '-c', {sleeper!r}], "
        "start_new_session=True); "
        "print(child.pid, flush=True); "
        "time.sleep(60)"
    )
    resident = subprocess.Popen(
        [sys.executable, "-c", resident_script],
        stdout=subprocess.PIPE,
        text=True,
    )
    cloud_session = subprocess.Popen(
        [sys.executable, "-c", sleeper],
        start_new_session=True,
    )
    managed_agent_pid: int | None = None
    try:
        assert resident.stdout is not None
        managed_agent_pid = int(resident.stdout.readline().strip())

        os.kill(resident.pid, signal.SIGTERM)
        resident.wait(timeout=5)

        os.kill(managed_agent_pid, 0)
        assert cloud_session.poll() is None
    finally:
        if resident.poll() is None:
            resident.terminate()
            resident.wait(timeout=5)
        if managed_agent_pid is not None:
            try:
                os.kill(managed_agent_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if cloud_session.poll() is None:
            cloud_session.terminate()
        cloud_session.wait(timeout=5)
