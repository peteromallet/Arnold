from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from arnold.pipelines.megaplan import chain as chain_module 
from arnold.pipelines.megaplan.cloud.cli import (
    _classify_effective_status,
    _marker_dir,
    build_cloud_parser,
    cloud_chain_status_payload,
    run_cloud_cli,
)
from arnold.pipelines.megaplan.cloud.spec import (
    ChainSubSpec,
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RailwaySpec,
    RepoSpec,
    ResourcesSpec,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_cloud_parser(subparsers)
    return parser


def _cloud_spec(*, mode: str = "idle", remote_chain_spec: str | None = None) -> CloudSpec:
    return CloudSpec(
        provider="railway",
        repo=RepoSpec(
            url="https://github.com/example/app.git",
            branch="main",
            workspace="/workspace/app",
        ),
        agents={"default": "codex"},
        codex=CodexSpec(model="ops-model", reasoning="medium"),
        mode=mode,
        megaplan=MegaplanSpec(ref="main"),
        resources=ResourcesSpec(volume="agent-volume", port=8080),
        secrets={},
        railway=RailwaySpec(service="agent", session="agent", project=None),
        chain=ChainSubSpec(spec=remote_chain_spec) if remote_chain_spec is not None else None,
        toolchains=[],
    )


def _write_chain_spec(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "seed": {"plan": "seed-plan-20260421"},
                "milestones": [
                    {"label": "m1", "idea": "/workspace/app/ideas/one.txt"},
                    {"label": "m2", "idea": "/workspace/app/ideas/two.txt"},
                ],
            }
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Stub provider (extended for T8 with status_payload, ssh_exec)
# ---------------------------------------------------------------------------


class _StubProvider:
    """Stub provider that can record reads and optionally emulate probes."""

    def __init__(
        self,
        payloads: dict[str, str],
        *,
        status_payload_result: dict | None = None,
        ssh_exec_result: subprocess.CompletedProcess[str] | None = None,
    ) -> None:
        self.payloads = payloads
        self.reads: list[str] = []
        self._status_payload_result = status_payload_result or {}
        self._ssh_exec_result = ssh_exec_result or subprocess.CompletedProcess(
            ["echo", "dead"], 1, "", ""
        )
        self.commands: list[str] = []

    def read_remote_file(self, path: str) -> str:
        self.reads.append(path)
        return self.payloads[path]

    def status_payload(self, *, plan: str, workspace: str) -> dict:
        self.commands.append(f"status_payload({plan}, {workspace})")
        return self._status_payload_result

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        self.commands.append(f"ssh_exec({command})")
        return self._ssh_exec_result


def _write_chain_state(spec_path: Path) -> None:
    chain_module.save_chain_state(
        spec_path,
        chain_module.ChainState(
            current_milestone_index=1,
            current_plan_name="plan-for-m2",
            last_state="done",
            completed=[{"label": "m1", "plan": "plan-for-m1", "status": "done"}],
        ),
    )


# ---- Helper for asserting key retention + additive keys ----


def _assert_retained_keys(payload: dict, remote_spec: str) -> None:
    """Verify all original top-level keys are present (backward-compatible)."""
    for key in ("success", "spec", "milestone_count", "seed_plan", "chain_state", "summary"):
        assert key in payload, f"missing backward-compatible key: {key}"
    assert payload["success"] is True
    assert payload["spec"] == remote_spec


# ---------------------------------------------------------------------------
# Existing tests (updated for T8 backward compatibility)
# ---------------------------------------------------------------------------


def test_cloud_status_chain_honors_explicit_remote_spec_and_matches_local_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    _write_chain_state(local_spec_path)

    remote_spec = "/workspace/app/chain.yaml"
    provider = _StubProvider(
        {
            remote_spec: local_spec_path.read_text(encoding="utf-8"),
            str(chain_module._state_path_for(Path(remote_spec))): json.dumps(
                chain_module.load_chain_state(local_spec_path).to_dict()
            ),
        }
    )
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    (_marker_dir(cloud_yaml_path) / "last_chain.json").write_text(
        json.dumps({"remote_spec": "/workspace/app/ignored-by-override.yaml"}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli.load_spec",
        lambda _path: _cloud_spec(mode="chain", remote_chain_spec="/workspace/app/fallback.yaml"),
    )
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: provider)

    args = parser.parse_args(
        [
            "cloud",
            "status",
            "--chain",
            "--remote-spec",
            remote_spec,
            "--cloud-yaml",
            str(cloud_yaml_path),
        ]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    # Backward-compatible: all original keys plus additive sections.
    _assert_retained_keys(payload, remote_spec)
    for new_key in ("effective_status", "policy", "sync", "plan_status", "runner", "logs", "pr"):
        assert new_key in payload, f"missing additive key: {new_key}"
    # Core values must still match.
    assert payload["milestone_count"] == 2
    assert payload["seed_plan"] == "seed-plan-20260421"
    # Read order must be: state first, then spec.
    assert provider.reads[0] == str(chain_module._state_path_for(Path(remote_spec)))
    assert provider.reads[1] == remote_spec
    assert "Current milestone: m2 (index 1)" in captured.err


def test_cloud_status_chain_uses_marker_before_cloud_yaml_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    _write_chain_state(local_spec_path)
    remote_spec = "/workspace/app/from-marker.yaml"
    provider = _StubProvider(
        {
            remote_spec: local_spec_path.read_text(encoding="utf-8"),
            str(chain_module._state_path_for(Path(remote_spec))): json.dumps(
                chain_module.load_chain_state(local_spec_path).to_dict()
            ),
        }
    )
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    (_marker_dir(cloud_yaml_path) / "last_chain.json").write_text(
        json.dumps({"remote_spec": remote_spec}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli.load_spec",
        lambda _path: _cloud_spec(mode="chain", remote_chain_spec="/workspace/app/from-cloud-yaml.yaml"),
    )
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: provider)

    args = parser.parse_args(["cloud", "status", "--chain", "--cloud-yaml", str(cloud_yaml_path)])
    assert run_cloud_cli(tmp_path, args) == 0

    payload = json.loads(capsys.readouterr().out)
    _assert_retained_keys(payload, remote_spec)
    assert provider.reads[0] == str(chain_module._state_path_for(Path(remote_spec)))


def test_cloud_status_chain_falls_back_to_cloud_yaml_chain_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    _write_chain_state(local_spec_path)
    remote_spec = "/workspace/app/from-cloud-yaml.yaml"
    provider = _StubProvider(
        {
            remote_spec: local_spec_path.read_text(encoding="utf-8"),
            str(chain_module._state_path_for(Path(remote_spec))): json.dumps(
                chain_module.load_chain_state(local_spec_path).to_dict()
            ),
        }
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli.load_spec",
        lambda _path: _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
    )
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: provider)

    args = parser.parse_args(["cloud", "status", "--chain"])
    assert run_cloud_cli(tmp_path, args) == 0

    payload = json.loads(capsys.readouterr().out)
    _assert_retained_keys(payload, remote_spec)
    # State file must be read first, then spec (runtime policy may also be read).
    assert provider.reads[0] == str(chain_module._state_path_for(Path(remote_spec)))
    assert remote_spec in provider.reads


def test_cloud_status_chain_errors_when_no_remote_spec_can_be_resolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec())
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: _StubProvider({}))

    args = parser.parse_args(["cloud", "status", "--chain"])
    assert run_cloud_cli(tmp_path, args) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "missing_remote_spec"
    assert "run `cloud chain <spec>` first" in payload["message"]


# ---------------------------------------------------------------------------
# T8: classification tests using _StubProvider with probes
# ---------------------------------------------------------------------------


def _make_chain_state(**overrides) -> chain_module.ChainState:
    """Create a ChainState with default values, then apply *overrides*."""
    defaults = {
        "current_milestone_index": 0,
        "current_plan_name": "running-plan-20260520",
        "last_state": "done",
        "completed": [],
        "pr_number": None,
        "pr_state": None,
        "branch_head": None,
        "pr_head": None,
        "last_pushed_commit": None,
        "dirty_flag": False,
        "sync_state": "clean",
    }
    defaults.update(overrides)
    return chain_module.ChainState(**defaults)


def test_classify_effective_status_running() -> None:
    """Plan is running and runner is alive → 'running'."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "running"},
        runner={"status": "alive"},
        pr={},
        sync={"sync_state": "clean"},
    )
    assert result == "running"


def test_classify_effective_status_running_unknown_runner() -> None:
    """Plan reports running but runner status is unknown → 'running' (benefit of doubt)."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "in_progress"},
        runner={"status": "unknown"},
        pr={},
        sync={"sync_state": "clean"},
    )
    assert result == "running"


def test_classify_effective_status_awaiting_pr_merge() -> None:
    """Chain state explicitly in awaiting_pr_merge → 'awaiting_pr_merge'."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(last_state="awaiting_pr_merge"),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "planned"},
        runner={"status": "dead"},
        pr={"pr_number": 5, "pr_state": "awaiting_merge"},
        sync={"sync_state": "clean"},
    )
    assert result == "awaiting_pr_merge"


def test_classify_effective_status_human_prerequisite() -> None:
    """prerequisite_policy is 'required', no running plan → 'human_prerequisite'."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(last_state="done"),
        effective={"prerequisite_policy": "required", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "planned"},
        runner={"status": "dead"},
        pr={},
        sync={"sync_state": "clean"},
    )
    assert result == "human_prerequisite"


def test_classify_effective_status_quality_gate() -> None:
    """validation_policy is 'required', no running plan → 'quality_gate'."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(last_state="done"),
        effective={"prerequisite_policy": "none", "validation_policy": "required"},
        milestone_count=1,
        plan_status={"status": "planned"},
        runner={"status": "dead"},
        pr={},
        sync={"sync_state": "clean"},
    )
    assert result == "quality_gate"


def test_classify_effective_status_stale_bookkeeping() -> None:
    """No current plan, no runner → 'stale_bookkeeping'."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(current_plan_name=None, last_state=None),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "missing"},
        runner={"status": "dead"},
        pr={},
        sync={"sync_state": None},
    )
    assert result == "stale_bookkeeping"


def test_classify_effective_status_stale_bookkeeping_with_stale_sync() -> None:
    """Sync state is stale and no runner → 'stale_bookkeeping'."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(last_state="done"),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "planned"},
        runner={"status": "dead"},
        pr={},
        sync={"sync_state": "stale"},
    )
    assert result == "stale_bookkeeping"


def test_classify_effective_status_complete() -> None:
    """All milestones processed → 'complete' (terminal, checked before runner)."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(current_milestone_index=2, current_plan_name=None, last_state="done"),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=2,
        plan_status={"status": "missing"},
        runner={"status": "dead"},
        pr={},
        sync={"sync_state": None},
    )
    assert result == "complete"


def test_cloud_status_payload_contains_all_additive_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cloud_chain_status_payload must include all new sections."""
    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    _write_chain_state(local_spec_path)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _StubProvider(
        {
            remote_spec: local_spec_path.read_text(encoding="utf-8"),
            str(chain_module._state_path_for(Path(remote_spec))): json.dumps(
                chain_module.load_chain_state(local_spec_path).to_dict()
            ),
        },
        status_payload_result={"status": "planned", "state": "planned"},
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    payload = cloud_chain_status_payload(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    _assert_retained_keys(payload, remote_spec)
    for key in ("effective_status", "policy", "sync", "plan_status", "runner", "logs", "pr"):
        assert key in payload, f"missing additive key: {key}"
    # New additive sections from T5/T8/T11/T12 (not breaking existing legacy assertions).
    for key in ("provider_consistency", "human_verification", "resolved_workspace", "resolved_session"):
        assert key in payload, f"missing new additive key: {key}"
    assert "chain_log" in payload.get("logs", {}), "missing logs.chain_log key"

    # Read-only: provider should not have issued mutating commands.
    for cmd in provider.commands:
        assert "write" not in cmd.lower()
        assert "sed" not in cmd.lower()
        assert "rm" not in cmd.lower()
        assert "gh" not in cmd.lower()


def test_cloud_status_no_current_plan_reports_plan_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no current plan exists, plan_status reports 'missing'."""
    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    # Write state with no current plan.
    chain_module.save_chain_state(
        local_spec_path,
        chain_module.ChainState(
            current_milestone_index=0,
            current_plan_name=None,
            last_state=None,
            completed=[],
        ),
    )
    remote_spec = "/workspace/app/chain.yaml"

    provider = _StubProvider(
        {
            remote_spec: local_spec_path.read_text(encoding="utf-8"),
            str(chain_module._state_path_for(Path(remote_spec))): json.dumps(
                chain_module.load_chain_state(local_spec_path).to_dict()
            ),
        },
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    payload = cloud_chain_status_payload(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert payload["plan_status"]["status"] == "missing"
    assert payload["plan_status"]["reason"] == "no current plan"
    assert payload["effective_status"] == "stale_bookkeeping"


def test_cloud_status_runner_alive_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ssh_exec reports alive tmux session, runner shows 'alive'."""
    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    _write_chain_state(local_spec_path)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _StubProvider(
        {
            remote_spec: local_spec_path.read_text(encoding="utf-8"),
            str(chain_module._state_path_for(Path(remote_spec))): json.dumps(
                chain_module.load_chain_state(local_spec_path).to_dict()
            ),
        },
        ssh_exec_result=subprocess.CompletedProcess(["echo", "alive"], 0, "alive\n", ""),
        status_payload_result={"status": "running", "state": "running"},
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    payload = cloud_chain_status_payload(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert payload["runner"]["status"] == "alive"
    assert payload["runner"]["session"] == "megaplan-chain"
    assert payload["effective_status"] == "running"


def test_cloud_status_missing_provider_methods_graceful(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When provider lacks status_payload / ssh_exec, sections return structured unknown."""
    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    _write_chain_state(local_spec_path)
    remote_spec = "/workspace/app/chain.yaml"

    # Provider with ONLY read_remote_file (no status_payload / ssh_exec).
    class _MinimalProvider:
        def __init__(self):
            self.reads: list[str] = []

        def read_remote_file(self, path: str) -> str:
            self.reads.append(path)
            return {
                remote_spec: local_spec_path.read_text(encoding="utf-8"),
                str(chain_module._state_path_for(Path(remote_spec))): json.dumps(
                    chain_module.load_chain_state(local_spec_path).to_dict()
                ),
            }[path]

    provider = _MinimalProvider()

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    payload = cloud_chain_status_payload(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    _assert_retained_keys(payload, remote_spec)
    # plan_status: provider has no status_payload → try_provider_method returns unavailable
    assert payload["plan_status"]["status"] in ("unavailable", "running")
    # runner: provider has no ssh_exec → falls back to "runner probe not implemented"
    assert payload["runner"]["status"] == "unavailable"
    assert "probe" in payload["runner"]["reason"] or "not implemented" in payload["runner"]["reason"]


# ---------------------------------------------------------------------------
# T4: Supervisor tests — extend _StubProvider with ordered command recording
# ---------------------------------------------------------------------------


class _SupervisorStubProvider:
    """Stub provider with ordered command recording for supervisor tests.

    Unlike ``_StubProvider``, this variant accepts a **list** of
    ``ssh_exec_results`` and returns them in FIFO order, so tests can
    assert exact remote command order.
    """

    def __init__(
        self,
        payloads: dict[str, str],
        *,
        status_payload_result: dict | None = None,
        ssh_exec_results: list | None = None,
    ) -> None:
        self.payloads = payloads
        self.reads: list[str] = []
        self.commands: list[str] = []
        self._status_payload_result = status_payload_result or {}
        self._ssh_exec_results = list(ssh_exec_results or [])
        self._ssh_exec_index = 0

    def read_remote_file(self, path: str) -> str:
        self.commands.append(f"read_remote_file({path})")
        self.reads.append(path)
        return self.payloads[path]

    def status_payload(self, *, plan: str, workspace: str) -> dict:
        self.commands.append(f"status_payload({plan}, {workspace})")
        return self._status_payload_result

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        self.commands.append(f"ssh_exec({command})")
        if self._ssh_exec_index < len(self._ssh_exec_results):
            result = self._ssh_exec_results[self._ssh_exec_index]
            self._ssh_exec_index += 1
            return result
        # Fallback: dead / unavailable
        return subprocess.CompletedProcess(["echo", "dead"], 1, "", "")


# -- ssh_exec result factories ------------------------------------------------


def _ssh_alive() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["echo", "alive"], 0, "alive\n", "")


def _ssh_dead() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["echo", "dead"], 1, "", "")


def _ssh_stat_ok(mtime: int = 1234567890, size: int = 5000) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["stat"], 0, f"{mtime} {size}\n", "")


def _ssh_stat_unavailable() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["stat"], 1, "", "unavailable")


def _ssh_sync_ok() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["python3"], 0, "", "")


def _ssh_pr_state(state: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["gh"], 0, f"{state}\n", "")


def _ssh_restart_ok() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        ["tmux"], 0, "restarted megaplan-chain session\n", ""
    )


def _ssh_hv_ok(
    *,
    pending: int = 0,
    verified: int = 2,
    all_deferred_must_verified: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Valid ``verify-human --list --json`` output for the stub provider."""
    payload = json.dumps(
        {
            "pending": pending,
            "verified": verified,
            "rows": [
                {
                    "criterion_idx": 0,
                    "criterion": "Test criterion 0",
                    "priority": "must",
                    "latest_verdict": "pass",
                    "status": "verified",
                },
                {
                    "criterion_idx": 1,
                    "criterion": "Test criterion 1",
                    "priority": "must",
                    "latest_verdict": "pass",
                    "status": "verified",
                },
            ],
            "all_deferred_must_verified": all_deferred_must_verified,
            "semantics": "latest_verdict",
        }
    )
    return subprocess.CompletedProcess(["python3"], 0, payload + "\n", "")


# -- helpers for building chain state dicts ----------------------------------


def _chain_state_dict(**overrides: object) -> dict:
    defaults: dict = {
        "current_milestone_index": 0,
        "current_plan_name": "running-plan-20260520",
        "last_state": "done",
        "completed": [],
        "pr_number": None,
        "pr_state": None,
        "branch_head": None,
        "pr_head": None,
        "last_pushed_commit": None,
        "dirty_flag": False,
        "sync_state": "clean",
    }
    defaults.update(overrides)
    return defaults


def _write_chain_spec_milestones(path: Path, milestone_count: int = 2) -> None:
    milestones = [
        {"label": f"m{i + 1}", "idea": f"/workspace/app/ideas/{i + 1}.txt"}
        for i in range(milestone_count)
    ]
    path.write_text(
        yaml.safe_dump({"seed": {"plan": "seed-plan-20260421"}, "milestones": milestones}),
        encoding="utf-8",
    )


def _supervisor_provider(
    *,
    local_spec_path: Path,
    remote_spec: str,
    chain_state_overrides: dict | None = None,
    plan_status: dict | None = None,
    ssh_exec_results: list | None = None,
) -> _SupervisorStubProvider:
    """Build a ``_SupervisorStubProvider`` wired for one supervisor tick."""
    state_json = json.dumps(_chain_state_dict(**(chain_state_overrides or {})))
    payloads: dict[str, str] = {
        remote_spec: local_spec_path.read_text(encoding="utf-8"),
        str(chain_module._state_path_for(Path(remote_spec))): state_json,
    }
    return _SupervisorStubProvider(
        payloads,
        status_payload_result=plan_status or {"status": "planned", "state": "planned"},
        ssh_exec_results=ssh_exec_results,
    )


def _assert_no_mutation_commands(commands: list[str]) -> None:
    """Verify that no destructive / mutation commands appear in the log."""
    for cmd in commands:
        assert "chain start" not in cmd or "--one" not in cmd, (
            f"unexpected mutation command: {cmd}"
        )
        assert "tmux kill-session" not in cmd, f"unexpected kill-session: {cmd}"
        assert "tmux new-session" not in cmd, f"unexpected new-session: {cmd}"


def _assert_sync_before_chain_start(commands: list[str]) -> None:
    """All ``_capture_sync_state`` calls appear before any ``chain start --one``."""
    sync_indices = [
        i for i, c in enumerate(commands) if "_capture_sync_state" in c
    ]
    chain_indices = [
        i for i, c in enumerate(commands) if "chain start" in c and "--one" in c
    ]
    for ci in chain_indices:
        for si in sync_indices:
            assert si < ci, (
                f"sync refresh (index {si}) must precede chain start --one (index {ci})"
            )


# -- T4 (a): running chain → noop --------------------------------------------


def test_supervisor_running_chain_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running chain: supervisor returns noop, does NOT emit ``chain start --one``."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": "active-plan",
            "last_state": "running",
        },
        plan_status={"status": "running", "state": "active"},
        ssh_exec_results=[
            _ssh_alive(),   # runner probe (first status read)
            _ssh_stat_ok(),  # log stat
            _ssh_hv_ok(),    # human verification probe (first status read)
            _ssh_sync_ok(),  # sync refresh
            _ssh_alive(),   # runner probe (re-read)
            _ssh_stat_ok(),  # log stat (re-read)
            _ssh_hv_ok(),    # human verification probe (re-read)
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["effective_status"] == "running"
    assert report["next_action"] == "noop"
    assert report["acted"] is False
    assert report["refused_reason"] is None

    _assert_no_mutation_commands(provider.commands)
    _assert_sync_before_chain_start(provider.commands)


# -- T4 (b): completed chain → done ------------------------------------------


def test_supervisor_completed_chain_done(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completed chain (all milestones done): supervisor returns done, no mutation."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 2,  # >= milestone_count
            "current_plan_name": None,
            "last_state": "done",
        },
        plan_status={"status": "missing", "reason": "no current plan"},
        ssh_exec_results=[
            _ssh_dead(),          # runner probe
            _ssh_stat_unavailable(),  # log stat
            _ssh_sync_ok(),       # sync refresh
            _ssh_dead(),          # re-read runner probe
            _ssh_stat_unavailable(),  # re-read log stat
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["effective_status"] == "complete"
    assert report["next_action"] == "done"
    assert report["acted"] is False
    assert report["refused_reason"] is None
    _assert_no_mutation_commands(provider.commands)


# -- T4 (c): human_prerequisite blocked → no mutation ------------------------


def test_supervisor_human_prerequisite_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """human_prerequisite: supervisor blocks, no mutation."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    # Write a chain spec with prerequisite_policy = required so that
    # effective_chain_policy returns prerequisite_policy: required.
    local_spec_path.write_text(
        yaml.safe_dump(
            {
                "seed": {"plan": "seed-plan-20260421"},
                "milestones": [
                    {"label": "m1", "idea": "/workspace/app/ideas/1.txt"},
                    {"label": "m2", "idea": "/workspace/app/ideas/2.txt"},
                ],
                "prerequisite_policy": "required",
            }
        ),
        encoding="utf-8",
    )

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": "plan-for-m1",
            "last_state": "done",
        },
        plan_status={"status": "planned", "state": "planned"},
        ssh_exec_results=[
            _ssh_dead(),          # runner probe
            _ssh_stat_unavailable(),  # log stat
            _ssh_hv_ok(),          # human verification probe (first status read)
            _ssh_sync_ok(),       # sync refresh
            _ssh_dead(),          # re-read runner probe
            _ssh_stat_unavailable(),  # re-read log stat
            _ssh_hv_ok(),          # human verification probe (re-read)
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["effective_status"] == "human_prerequisite"
    assert report["next_action"] == "blocked"
    assert report["acted"] is False
    assert "human prerequisite policy" in (report["refused_reason"] or "")
    _assert_no_mutation_commands(provider.commands)


# -- T4 (d): quality_gate blocked → no mutation ------------------------------


def test_supervisor_quality_gate_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """quality_gate: supervisor blocks, no mutation."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    # Write a chain spec with validation_policy = required.
    local_spec_path.write_text(
        yaml.safe_dump(
            {
                "seed": {"plan": "seed-plan-20260421"},
                "milestones": [
                    {"label": "m1", "idea": "/workspace/app/ideas/1.txt"},
                    {"label": "m2", "idea": "/workspace/app/ideas/2.txt"},
                ],
                "validation_policy": "required",
            }
        ),
        encoding="utf-8",
    )

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": "plan-for-m1",
            "last_state": "done",
        },
        plan_status={"status": "planned", "state": "planned"},
        ssh_exec_results=[
            _ssh_dead(),              # runner probe
            _ssh_stat_unavailable(),  # log stat
            _ssh_hv_ok(),              # human verification probe (first status read)
            _ssh_sync_ok(),           # sync refresh
            _ssh_dead(),              # re-read runner probe
            _ssh_stat_unavailable(),  # re-read log stat
            _ssh_hv_ok(),              # human verification probe (re-read)
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["effective_status"] == "quality_gate"
    assert report["next_action"] == "blocked"
    assert report["acted"] is False
    assert "validation policy" in (report["refused_reason"] or "")
    _assert_no_mutation_commands(provider.commands)


# -- T4 (e): dead megaplan-chain stale_bookkeeping → restart ------------------


def test_supervisor_stale_bookkeeping_dead_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stale_bookkeeping + dead runner: supervisor restarts tmux and runs one tick."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": None,
            "last_state": None,
            "sync_state": None,
        },
        plan_status={"status": "missing", "reason": "no current plan"},
        ssh_exec_results=[
            _ssh_dead(),              # runner probe (first status read)
            _ssh_stat_unavailable(),  # log stat
            _ssh_sync_ok(),           # sync refresh
            _ssh_dead(),              # re-read runner probe
            _ssh_stat_unavailable(),  # re-read log stat
            _ssh_restart_ok(),        # tmux restart
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["effective_status"] == "stale_bookkeeping"
    assert report["next_action"] == "restart"
    assert report["acted"] is True
    assert report["refused_reason"] is None

    # Sync refresh must precede chain start --one
    _assert_sync_before_chain_start(provider.commands)

    # Verify restart command shape
    restart_cmds = [c for c in provider.commands if "tmux kill-session" in c or "tmux new-session" in c]
    assert len(restart_cmds) >= 1, f"expected tmux restart commands in {provider.commands}"
    # The restart command should contain chain start --one
    chain_one_cmds = [c for c in provider.commands if "chain start" in c and "--one" in c]
    assert len(chain_one_cmds) >= 1, f"expected chain start --one in {provider.commands}"


# -- T4 (f): merged PR await → advance with chain start --one -----------------


def test_supervisor_merged_pr_advance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """awaiting_pr_merge + PR merged: supervisor advances with ``chain start --one``."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": "plan-for-m1",
            "last_state": "awaiting_pr_merge",
            "pr_number": 42,
            "pr_state": "open",
            "pr_head": "abc123",
        },
        plan_status={"status": "planned", "state": "awaiting_merge"},
        ssh_exec_results=[
            _ssh_dead(),          # runner probe (first status read)
            _ssh_stat_ok(),       # log stat
            _ssh_hv_ok(),          # human verification probe (first status read)
            _ssh_sync_ok(),       # sync refresh
            _ssh_dead(),          # re-read runner probe
            _ssh_stat_ok(),       # re-read log stat
            _ssh_hv_ok(),          # human verification probe (re-read)
            _ssh_pr_state("merged"),  # PR probe → merged
            _ssh_restart_ok(),    # tmux restart with chain start --one
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["effective_status"] == "awaiting_pr_merge"
    assert report["next_action"] == "advance"
    assert report["acted"] is True
    assert report["refused_reason"] is None

    # Sync refresh must precede chain start --one
    _assert_sync_before_chain_start(provider.commands)

    # Verify chain start --one appears
    chain_one_cmds = [c for c in provider.commands if "chain start" in c and "--one" in c]
    assert len(chain_one_cmds) >= 1, f"expected chain start --one in {provider.commands}"


# -- T4 (g): unmerged PR await → block ---------------------------------------


def test_supervisor_unmerged_pr_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """awaiting_pr_merge + PR unmerged: supervisor blocks, no mutation."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": "plan-for-m1",
            "last_state": "awaiting_pr_merge",
            "pr_number": 42,
            "pr_state": "open",
            "pr_head": "abc123",
        },
        plan_status={"status": "planned", "state": "awaiting_merge"},
        ssh_exec_results=[
            _ssh_dead(),         # runner probe (first status read)
            _ssh_stat_ok(),      # log stat
            _ssh_hv_ok(),         # human verification probe (first status read)
            _ssh_sync_ok(),      # sync refresh
            _ssh_dead(),         # re-read runner probe
            _ssh_stat_ok(),      # re-read log stat
            _ssh_hv_ok(),         # human verification probe (re-read)
            _ssh_pr_state("open"),  # PR probe → still open
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["effective_status"] == "awaiting_pr_merge"
    assert report["next_action"] == "blocked"
    assert report["acted"] is False
    assert "PR #42" in (report["refused_reason"] or "")
    assert "state=open" in (report["refused_reason"] or "")
    _assert_no_mutation_commands(provider.commands)


# ---------------------------------------------------------------------------
# T15: Supervisor invariant tests — no destructive / synthesized commands
# ---------------------------------------------------------------------------


def _assert_no_destructive_supervisor_commands(commands: list[str]) -> None:
    """Verify that no supervisor restart/advance/wake command contains
    force-push, reset, branch deletion, synthesized verification, or
    quality-gate bypass."""
    destructive_patterns = [
        ("force.push", "force-push"),
        ("git push --force", "force-push"),
        ("git push -f", "force-push"),
        ("git reset", "reset"),
        ("git branch -D", "branch deletion"),
        ("git branch --delete", "branch deletion"),
        ("git push origin --delete", "branch deletion"),
        ("synthesize", "synthesized verification"),
        ("verification.*record", "synthesized verification record (supervisor never writes)"),
    ]
    import re
    for cmd in commands:
        cmd_lower = cmd.lower()
        for pattern, label in destructive_patterns:
            if re.search(pattern, cmd_lower):
                raise AssertionError(
                    f"Supervisor command contains {label}: {cmd!r}"
                )


def test_supervisor_invariant_no_destructive_commands_in_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No destructive commands appear in a noop supervisor tick."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": "active-plan",
            "last_state": "running",
        },
        plan_status={"status": "running", "state": "active"},
        ssh_exec_results=[
            _ssh_alive(),   # runner probe
            _ssh_stat_ok(),  # log stat
            _ssh_hv_ok(),    # human verification probe (first status read)
            _ssh_sync_ok(),  # sync refresh
            _ssh_alive(),   # re-read runner
            _ssh_stat_ok(),  # re-read log stat
            _ssh_hv_ok(),    # human verification probe (re-read)
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["acted"] is False
    _assert_no_destructive_supervisor_commands(provider.commands)


def test_supervisor_invariant_no_destructive_commands_in_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No destructive commands appear during a stale_bookkeeping restart."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": None,
            "last_state": None,
            "sync_state": None,
        },
        plan_status={"status": "missing", "reason": "no current plan"},
        ssh_exec_results=[
            _ssh_dead(),              # runner probe
            _ssh_stat_unavailable(),  # log stat
            _ssh_sync_ok(),           # sync refresh
            _ssh_dead(),              # re-read runner probe
            _ssh_stat_unavailable(),  # re-read log stat
            _ssh_restart_ok(),        # tmux restart
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["acted"] is True
    assert report["next_action"] == "restart"
    _assert_no_destructive_supervisor_commands(provider.commands)


def test_supervisor_invariant_no_destructive_commands_in_advance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No destructive commands appear during a PR-merge advance."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": "plan-for-m1",
            "last_state": "awaiting_pr_merge",
            "pr_number": 42,
            "pr_state": "open",
            "pr_head": "abc123",
        },
        plan_status={"status": "planned", "state": "awaiting_merge"},
        ssh_exec_results=[
            _ssh_dead(),          # runner probe
            _ssh_stat_ok(),       # log stat
            _ssh_hv_ok(),          # human verification probe (first status read)
            _ssh_sync_ok(),       # sync refresh
            _ssh_dead(),          # re-read runner probe
            _ssh_stat_ok(),       # re-read log stat
            _ssh_hv_ok(),          # human verification probe (re-read)
            _ssh_pr_state("merged"),  # PR probe → merged
            _ssh_restart_ok(),    # tmux restart with chain start --one
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["acted"] is True
    assert report["next_action"] == "advance"
    _assert_no_destructive_supervisor_commands(provider.commands)


def test_supervisor_invariant_no_destructive_commands_in_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No destructive commands appear when supervisor blocks (quality_gate)."""
    from arnold.pipelines.megaplan.cloud.supervise import cloud_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    # Write a chain spec with validation_policy = required.
    local_spec_path.write_text(
        yaml.safe_dump(
            {
                "seed": {"plan": "seed-plan-20260421"},
                "milestones": [
                    {"label": "m1", "idea": "/workspace/app/ideas/1.txt"},
                    {"label": "m2", "idea": "/workspace/app/ideas/2.txt"},
                ],
                "validation_policy": "required",
            }
        ),
        encoding="utf-8",
    )

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": "plan-for-m1",
            "last_state": "done",
        },
        plan_status={"status": "planned", "state": "planned"},
        ssh_exec_results=[
            _ssh_dead(),              # runner probe
            _ssh_stat_unavailable(),  # log stat
            _ssh_hv_ok(),              # human verification probe (first status read)
            _ssh_sync_ok(),           # sync refresh
            _ssh_dead(),              # re-read runner probe
            _ssh_stat_unavailable(),  # re-read log stat
            _ssh_hv_ok(),              # human verification probe (re-read)
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    assert report["success"] is True
    assert report["acted"] is False
    assert report["next_action"] == "blocked"
    _assert_no_destructive_supervisor_commands(provider.commands)


# -- T4: stdout / stderr convention test -------------------------------------


def test_supervise_tick_stdout_json_stderr_human(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``_run_supervise_tick`` writes JSON to stdout and human summary to stderr."""
    from arnold.pipelines.megaplan.cloud.cli import _run_supervise_tick

    local_spec_path = tmp_path / "chain.yaml"
    _write_chain_spec_milestones(local_spec_path, milestone_count=2)
    remote_spec = "/workspace/app/chain.yaml"

    provider = _supervisor_provider(
        local_spec_path=local_spec_path,
        remote_spec=remote_spec,
        chain_state_overrides={
            "current_milestone_index": 0,
            "current_plan_name": "active-plan",
            "last_state": "running",
        },
        plan_status={"status": "running", "state": "active"},
        ssh_exec_results=[
            _ssh_alive(),   # runner probe
            _ssh_stat_ok(),  # log stat
            _ssh_hv_ok(),    # human verification probe (first status read)
            _ssh_sync_ok(),  # sync refresh
            _ssh_alive(),   # re-read runner
            _ssh_stat_ok(),  # re-read log stat
            _ssh_hv_ok(),    # human verification probe (re-read)
        ],
    )

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda _root, _args, _spec: remote_spec,
    )

    exit_code = _run_supervise_tick(
        tmp_path,
        argparse.Namespace(chain=True, remote_spec=None),
        _cloud_spec(mode="chain", remote_chain_spec=remote_spec),
        provider,
    )

    captured = capsys.readouterr()

    # JSON on stdout
    report = json.loads(captured.out)
    for key in (
        "success",
        "event",
        "spec",
        "effective_status",
        "next_action",
        "acted",
        "refused_reason",
        "runner",
        "sync",
        "pr",
        "logs",
    ):
        assert key in report, f"missing key in JSON stdout: {key}"
    # New additive sections (provider_consistency and extra_repo_sync are always
    # present in tick reports since T13; sync_refresh and human_verification are
    # conditionally present — check they exist when the status path emits them).
    for key in ("provider_consistency", "extra_repo_sync"):
        assert key in report, f"missing new additive key in tick report: {key}"
    assert report["success"] is True
    assert exit_code == 0

    # Human summary on stderr
    assert "supervisor tick:" in captured.err
    assert "acted=" in captured.err
    assert "next_action=" in captured.err


# ---------------------------------------------------------------------------
# T2: ChainState serialization backward-compatibility tests
# ---------------------------------------------------------------------------


def test_chain_state_old_json_missing_new_fields_loads_with_defaults() -> None:
    """Old state JSON without extra_repos/chain_session/resolved_workspace/
    extra_repo_sync loads with compatible defaults."""
    old_json = {
        "current_milestone_index": 0,
        "current_plan_name": "plan-1",
        "last_state": "done",
        "pr_number": None,
        "pr_state": None,
        "completed": [],
        "branch_head": None,
        "pr_head": None,
        "last_pushed_commit": None,
        "dirty_flag": False,
        "sync_state": None,
    }
    state = chain_module.ChainState.from_dict(old_json)
    assert state.extra_repos == []
    assert state.chain_session is None
    assert state.resolved_workspace is None
    assert state.extra_repo_sync == []
    # Legacy keys unchanged
    assert state.current_milestone_index == 0
    assert state.current_plan_name == "plan-1"


def test_chain_state_new_fields_roundtrip_legacy_keys_unchanged() -> None:
    """New fields round-trip through to_dict/from_dict alongside existing
    branch/PR sync fields without changing legacy keys."""
    state = chain_module.ChainState(
        current_milestone_index=1,
        current_plan_name="plan-m2",
        last_state="running",
        pr_number=5,
        pr_state="open",
        completed=[{"label": "m1", "plan": "p1", "status": "done"}],
        branch_head="abc123",
        pr_head="def456",
        last_pushed_commit="abc123",
        dirty_flag=False,
        sync_state="clean",
        extra_repos=["/workspace/lib"],
        chain_session="my-session",
        resolved_workspace="/workspace/app",
        extra_repo_sync=[{"path": "/workspace/lib", "branch_head": "ghi789", "dirty_flag": False, "sync_state": "clean"}],
    )
    d = state.to_dict()
    # Legacy keys present and unchanged
    assert d["current_milestone_index"] == 1
    assert d["current_plan_name"] == "plan-m2"
    assert d["last_state"] == "running"
    assert d["pr_number"] == 5
    assert d["pr_state"] == "open"
    assert d["branch_head"] == "abc123"
    assert d["pr_head"] == "def456"
    assert d["last_pushed_commit"] == "abc123"
    assert d["dirty_flag"] is False
    assert d["sync_state"] == "clean"
    # New keys present
    assert d["extra_repos"] == ["/workspace/lib"]
    assert d["chain_session"] == "my-session"
    assert d["resolved_workspace"] == "/workspace/app"
    assert d["extra_repo_sync"] == [{"path": "/workspace/lib", "branch_head": "ghi789", "dirty_flag": False, "sync_state": "clean"}]

    # Round-trip back
    rt = chain_module.ChainState.from_dict(d)
    assert rt.extra_repos == ["/workspace/lib"]
    assert rt.chain_session == "my-session"
    assert rt.resolved_workspace == "/workspace/app"
    assert rt.extra_repo_sync == [{"path": "/workspace/lib", "branch_head": "ghi789", "dirty_flag": False, "sync_state": "clean"}]
    assert rt.current_milestone_index == 1
    assert rt.current_plan_name == "plan-m2"
    assert rt.pr_number == 5


def test_chain_state_malformed_extra_repos_not_list_falls_back() -> None:
    """Malformed extra_repos (not a list) falls back to [] and does not
    corrupt required state."""
    bad_json = {
        "current_milestone_index": 2,
        "current_plan_name": "plan-final",
        "last_state": "done",
        "pr_number": None,
        "pr_state": None,
        "completed": [],
        "extra_repos": "not-a-list",
        "chain_session": None,
        "resolved_workspace": None,
        "extra_repo_sync": None,
    }
    state = chain_module.ChainState.from_dict(bad_json)
    assert state.extra_repos == []
    assert state.current_milestone_index == 2
    assert state.current_plan_name == "plan-final"


def test_chain_state_malformed_extra_repos_non_string_element_falls_back() -> None:
    """Malformed extra_repos (contains non-string element) falls back to []."""
    bad_json = {
        "current_milestone_index": 0,
        "current_plan_name": None,
        "last_state": None,
        "pr_number": None,
        "pr_state": None,
        "completed": [],
        "extra_repos": [123, "/workspace/lib"],
    }
    state = chain_module.ChainState.from_dict(bad_json)
    assert state.extra_repos == []


def test_chain_state_malformed_extra_repo_sync_not_list_falls_back() -> None:
    """Malformed extra_repo_sync (not a list) falls back to [] and does not
    corrupt required state."""
    bad_json = {
        "current_milestone_index": 0,
        "current_plan_name": None,
        "last_state": None,
        "pr_number": None,
        "pr_state": None,
        "completed": [],
        "extra_repos": [],
        "extra_repo_sync": "not-a-list",
    }
    state = chain_module.ChainState.from_dict(bad_json)
    assert state.extra_repo_sync == []
    assert state.current_milestone_index == 0


def test_chain_state_malformed_chain_session_empty_falls_back() -> None:
    """Empty chain_session string falls back to None."""
    bad_json = {
        "current_milestone_index": 0,
        "current_plan_name": None,
        "last_state": None,
        "pr_number": None,
        "pr_state": None,
        "completed": [],
        "chain_session": "   ",
        "resolved_workspace": None,
        "extra_repos": [],
        "extra_repo_sync": [],
    }
    state = chain_module.ChainState.from_dict(bad_json)
    assert state.chain_session is None


def test_chain_state_malformed_resolved_workspace_empty_falls_back() -> None:
    """Empty resolved_workspace string falls back to None."""
    bad_json = {
        "current_milestone_index": 0,
        "current_plan_name": None,
        "last_state": None,
        "pr_number": None,
        "pr_state": None,
        "completed": [],
        "chain_session": None,
        "resolved_workspace": "",
        "extra_repos": [],
        "extra_repo_sync": [],
    }
    state = chain_module.ChainState.from_dict(bad_json)
    assert state.resolved_workspace is None


def test_chain_state_malformed_chain_session_not_string_falls_back() -> None:
    """Non-string chain_session falls back to None."""
    bad_json = {
        "current_milestone_index": 0,
        "current_plan_name": None,
        "last_state": None,
        "pr_number": None,
        "pr_state": None,
        "completed": [],
        "chain_session": 42,
        "resolved_workspace": None,
        "extra_repos": [],
        "extra_repo_sync": [],
    }
    state = chain_module.ChainState.from_dict(bad_json)
    assert state.chain_session is None


def test_chain_state_new_fields_dont_corrupt_legacy_values() -> None:
    """Round-tripping new fields must not alter any legacy key values in to_dict."""
    original = chain_module.ChainState(
        current_milestone_index=1,
        current_plan_name="plan-m2",
        last_state="running",
        pr_number=42,
        pr_state="open",
        completed=[{"label": "m1"}],
        branch_head="abc",
        pr_head="def",
        last_pushed_commit="abc",
        dirty_flag=True,
        sync_state="dirty",
        extra_repos=["/extra"],
        chain_session="sess",
        resolved_workspace="/ws",
        extra_repo_sync=[],
    )
    d = original.to_dict()
    # Verify legacy keys are exactly the original values
    assert d["current_milestone_index"] == 1
    assert d["current_plan_name"] == "plan-m2"
    assert d["last_state"] == "running"
    assert d["pr_number"] == 42
    assert d["pr_state"] == "open"
    assert d["branch_head"] == "abc"
    assert d["dirty_flag"] is True
    assert d["sync_state"] == "dirty"


# ─────────────────────────────────────────────────────────────────────
# T12: _classify_effective_status — awaiting_human_verify classification
# ─────────────────────────────────────────────────────────────────────


def test_classify_awaiting_human_verify_hv_none() -> None:
    """hv=None → fail closed as awaiting_human_verify."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "awaiting_human_verify"},
        runner={"status": "alive"},
        pr={},
        sync={"sync_state": "clean"},
        human_verification=None,
    )
    assert result == "awaiting_human_verify"


def test_classify_awaiting_human_verify_hv_unavailable() -> None:
    """hv status != 'available' → fail closed as awaiting_human_verify."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "awaiting_human_verify"},
        runner={"status": "alive"},
        pr={},
        sync={"sync_state": "clean"},
        human_verification={"status": "unavailable", "reason": "no ssh_exec"},
    )
    assert result == "awaiting_human_verify"


def test_classify_awaiting_human_verify_wrong_semantics() -> None:
    """hv semantics != 'latest_verdict' → fail closed."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "awaiting_human_verify"},
        runner={"status": "alive"},
        pr={},
        sync={"sync_state": "clean"},
        human_verification={
            "status": "available",
            "semantics": "legacy",
            "all_deferred_must_verified": True,
        },
    )
    assert result == "awaiting_human_verify"


def test_classify_awaiting_human_verify_pending_criteria() -> None:
    """available + latest_verdict but criteria NOT all passed → awaiting."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "awaiting_human_verify"},
        runner={"status": "alive"},
        pr={},
        sync={"sync_state": "clean"},
        human_verification={
            "status": "available",
            "semantics": "latest_verdict",
            "all_deferred_must_verified": False,
            "pending": 2,
            "verified": 1,
        },
    )
    assert result == "awaiting_human_verify"


def test_classify_awaiting_human_verify_all_passed_runner_alive() -> None:
    """All verified + runner alive → 'running'."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "awaiting_human_verify"},
        runner={"status": "alive"},
        pr={},
        sync={"sync_state": "clean"},
        human_verification={
            "status": "available",
            "semantics": "latest_verdict",
            "all_deferred_must_verified": True,
            "pending": 0,
            "verified": 2,
        },
    )
    assert result == "running"


def test_classify_awaiting_human_verify_all_passed_runner_dead() -> None:
    """All verified + runner dead → 'stale_bookkeeping' (recoverable)."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "awaiting_human_verify"},
        runner={"status": "dead"},
        pr={},
        sync={"sync_state": "clean"},
        human_verification={
            "status": "available",
            "semantics": "latest_verdict",
            "all_deferred_must_verified": True,
            "pending": 0,
            "verified": 2,
        },
    )
    assert result == "stale_bookkeeping"


def test_classify_awaiting_human_verify_all_passed_runner_unavailable() -> None:
    """All verified + runner unavailable → 'stale_bookkeeping' (recoverable)."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "awaiting_human_verify"},
        runner={"status": "unavailable"},
        pr={},
        sync={"sync_state": "clean"},
        human_verification={
            "status": "available",
            "semantics": "latest_verdict",
            "all_deferred_must_verified": True,
            "pending": 0,
            "verified": 2,
        },
    )
    assert result == "stale_bookkeeping"


def test_classify_awaiting_human_verify_omitted_param() -> None:
    """Backward-compatible: omitted human_verification still works."""
    result = _classify_effective_status(
        chain_state=_make_chain_state(),
        effective={"prerequisite_policy": "none", "validation_policy": "none"},
        milestone_count=1,
        plan_status={"status": "awaiting_human_verify"},
        runner={"status": "alive"},
        pr={},
        sync={"sync_state": "clean"},
        # human_verification omitted — defaults to None
    )
    assert result == "awaiting_human_verify"
