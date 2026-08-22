from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.cloud.cli import cloud_chain_status_payload
from arnold_pipelines.megaplan.cloud.current_target_liveness import SCHEMA
from arnold_pipelines.megaplan.cloud.providers.ssh import (
    SshProvider,
    _megaplan_status_module_command,
)
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)
from arnold_pipelines.megaplan.cloud.supervise import cloud_supervise_tick
from arnold_pipelines.megaplan.types import CliError


REMOTE_SPEC = "/workspace/demo/app/.megaplan/initiatives/demo/chain.yaml"
WORKSPACE = "/workspace/demo/app"
SESSION = "demo-session"
PLAN = "demo-plan"


def _liveness(state: str) -> dict:
    known = state in {"live", "dead"}
    return {
        "schema": SCHEMA,
        "state": state,
        "live": state == "live",
        "dead": state == "dead",
        "known": known,
        "source": "matched_local_process_identity",
        "reason": "test exact process incarnation",
        "identity": {
            "source": "marker",
            "pid": 4242,
            "pid_namespace_id": "pid:[runner-container]",
            "process_start_identity": "boot-id:123",
        },
        "lease": {},
        "diagnostics": [],
        "control_permitted": known,
        "mutation_permitted": known,
        "escalation_permitted": known,
        "retrigger_permitted": known,
    }


def _current_target(state: str) -> dict:
    return {
        "schema_version": 2,
        "session": SESSION,
        "target_session": SESSION,
        "current_refs": {
            "workspace": WORKSPACE,
            "remote_spec": REMOTE_SPEC,
            "current_plan_name": PLAN,
        },
        "marker": {
            "present": True,
            "session": SESSION,
            "workspace": WORKSPACE,
            "remote_spec": REMOTE_SPEC,
        },
        "plan_state": {"present": True, "name": PLAN},
        "current_target_liveness": _liveness(state),
    }


def _spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace=WORKSPACE),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="example"),
    )


class _Provider:
    def __init__(self, *, canonical_state: str, raw_probe: str) -> None:
        self.raw_probe = raw_probe
        self.plan_status = {
            "status": "running",
            "current_target": _current_target(canonical_state),
        }
        self.chain_state = chain_module.ChainState(
            current_milestone_index=0,
            current_plan_name=PLAN,
            last_state="prepped",
            resolved_workspace=WORKSPACE,
            chain_session=SESSION,
        )

    def read_remote_file(self, path: str) -> str:
        if path == REMOTE_SPEC:
            return "milestones:\n  - label: m1\n    idea: idea.md\n"
        if path == str(chain_module._state_path_for(Path(REMOTE_SPEC))):
            return json.dumps(self.chain_state.to_dict())
        raise OSError(path)

    def status_payload(
        self, *, plan: str | None, workspace: str, session: str | None = None
    ) -> dict:
        assert (plan, workspace, session) == (PLAN, WORKSPACE, SESSION)
        return dict(self.plan_status)

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        if "tmux has-session" in command:
            return subprocess.CompletedProcess([], 0, self.raw_probe, "")
        if command.startswith("stat "):
            return subprocess.CompletedProcess([], 0, "unavailable\n", "")
        if "verify-human" in command:
            return subprocess.CompletedProcess([], 0, "{}", "")
        return subprocess.CompletedProcess([], 1, "", "unexpected")


def _status(*, canonical_state: str, raw_probe: str) -> dict:
    return cloud_chain_status_payload(
        Path("/repo"),
        argparse.Namespace(remote_spec=REMOTE_SPEC, cloud_yaml=None),
        _spec(),
        _Provider(canonical_state=canonical_state, raw_probe=raw_probe),
    )


def test_ssh_status_command_can_never_select_native_arnold_cli() -> None:
    command = _megaplan_status_module_command(
        workspace=WORKSPACE,
        plan=PLAN,
        runtime_root="/workspace/runtime-candidates/arnold-deadbeef",
        runtime_revision="a" * 40,
        session=SESSION,
    )

    assert "python -P -m arnold_pipelines.megaplan status" in command
    assert "python -P -m arnold_pipelines.megaplan.cloud.runtime_provenance" in command
    assert "PYTHONPATH=/workspace/runtime-candidates/arnold-deadbeef" in command
    assert " arnold status" not in command


def test_ssh_chain_status_does_not_fallback_when_session_runtime_is_unreadable() -> None:
    provider = object.__new__(SshProvider)
    provider._spec = _spec()
    provider.read_remote_file = lambda _path: (_ for _ in ()).throw(  # type: ignore[method-assign]
        CliError("provider_failed", "missing marker")
    )

    with pytest.raises(CliError) as exc_info:
        provider.status_payload(plan=PLAN, workspace=WORKSPACE, session=SESSION)

    assert exc_info.value.code == "status_runtime_binding_unavailable"


@pytest.mark.parametrize(
    ("canonical_state", "raw_probe", "expected"),
    [
        ("live", "dead\n", "alive"),
        ("dead", "process_alive\n", "dead"),
        ("unknown", "tmux_alive\n", "unknown"),
    ],
)
def test_raw_process_disagreement_never_changes_canonical_runner(
    canonical_state: str, raw_probe: str, expected: str
) -> None:
    payload = _status(canonical_state=canonical_state, raw_probe=raw_probe)

    assert payload["runner"]["status"] == expected
    assert payload["runner"]["authority"] == "canonical_current_target"
    assert payload["tmux_evidence"]["authoritative"] is False
    assert payload["process_evidence"]["authoritative"] is False


def _supervisor_payload(runner: dict, *, status: str = "stale_bookkeeping") -> dict:
    return {
        "effective_status": status,
        "resolved_workspace": WORKSPACE,
        "resolved_session": SESSION,
        "resolved_context": {"extra_repos": []},
        "runner": runner,
        "sync": {},
        "pr": {},
        "logs": {},
        "provider_consistency": {},
        "chain_state": {"current_plan_name": PLAN, "extra_repo_sync": []},
        "human_verification": {"status": "unavailable"},
    }


class _SupervisorProvider:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return subprocess.CompletedProcess([], 0, "", "")


def test_supervisor_never_restarts_when_canonical_liveness_is_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = {
        "authority": "canonical_current_target",
        "exact_target": True,
        "mutation_permitted": False,
        "state": "unknown",
        "status": "unknown",
        "diagnostic_process_status": "dead",
    }
    monkeypatch.setenv("ARNOLD_AUTONOMY", "1")
    monkeypatch.setenv("ARNOLD_REPAIR_TRIGGER_ENABLED", "1")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli.cloud_chain_status_payload",
        lambda *_a, **_k: _supervisor_payload(runner),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda *_a, **_k: REMOTE_SPEC,
    )
    provider = _SupervisorProvider()

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(session=SESSION),
        SimpleNamespace(provider="ssh", repo=SimpleNamespace(workspace=WORKSPACE)),
        provider,
    )

    assert report["acted"] is False
    assert report["next_action"] == "blocked"
    # Stale-bookkeeping refusal names the canonical liveness verdict it needs.
    assert "canonical current-target liveness is not known" in report["refused_reason"]
    assert provider.commands == []


def test_supervisor_does_not_advance_merged_pr_on_unknown_liveness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = {
        "authority": "canonical_current_target",
        "exact_target": True,
        "mutation_permitted": False,
        "state": "unknown",
        "status": "unknown",
        "diagnostic_process_status": "dead",
    }
    payload = _supervisor_payload(runner, status="awaiting_pr_merge")
    payload["pr"] = {"pr_number": 42}
    monkeypatch.setenv("ARNOLD_AUTONOMY", "1")
    monkeypatch.setenv("ARNOLD_REPAIR_TRIGGER_ENABLED", "1")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli.cloud_chain_status_payload",
        lambda *_a, **_k: payload,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda *_a, **_k: REMOTE_SPEC,
    )
    provider = _SupervisorProvider()
    provider.ssh_exec = lambda command: (
        provider.commands.append(command)
        or subprocess.CompletedProcess([], 0, "merged\n", "")
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(session=SESSION),
        SimpleNamespace(provider="ssh", repo=SimpleNamespace(workspace=WORKSPACE)),
        provider,
    )

    assert report["acted"] is False
    assert "cannot advance" in report["refused_reason"]
    assert len(provider.commands) == 1
    assert "gh pr view" in provider.commands[0]
    assert all("tmux new-session" not in command for command in provider.commands)
