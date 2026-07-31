from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import yaml

from arnold_pipelines.megaplan.chain.spec import ChainState, save_chain_state
from arnold_pipelines.megaplan.cloud.providers.local import LocalProvider
from arnold_pipelines.megaplan.cloud.providers.on_box import OnBoxProvider
from arnold_pipelines.megaplan.cloud.providers.ssh import SshProvider
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    LocalSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)
from arnold_pipelines.megaplan.cloud.supervise import cloud_supervise_tick
from arnold_pipelines.megaplan.cloud.wrapper_acceptance_gate import check_wrapper_acceptance_gate
from arnold_pipelines.megaplan.custody.process_adapter_wbc import process_adapter_wbc_dir


def _records(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _cloud_spec(tmp_path: Path, *, provider: str) -> CloudSpec:
    return CloudSpec(
        provider=provider,
        repo=RepoSpec(
            url="https://github.com/example/app.git",
            workspace=str((tmp_path / "workspace").resolve()),
            workspace_explicit=True,
        ),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        local=LocalSpec(),
        ssh=SshSpec(host="example.test"),
    )


def test_local_provider_ssh_exec_records_process_adapter_wbc(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class TestLocalProvider(LocalProvider):
        def _deploy_dir(self) -> Path:
            path = tmp_path / "deploy"
            path.mkdir(parents=True, exist_ok=True)
            return path

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.providers.local.shutil.which",
        lambda _name: "docker",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.providers.local.subprocess.run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "ok\n", ""),
    )

    provider = TestLocalProvider(_cloud_spec(tmp_path, provider="local"))
    provider.ssh_exec("echo ok")

    sidecar = process_adapter_wbc_dir(
        tmp_path / "deploy",
        producer_family="cloud_provider_adapter",
        adapter_name="TestLocalProvider",
    )
    records = _records(sidecar / "events.ndjson")

    assert [record["payload"]["boundary_event"] for record in records] == ["started", "terminal"]
    assert records[0]["payload"]["surface"] == "ssh_exec"
    assert records[-1]["payload"]["indeterminate_hooks"] == {
        "signal": "reserved_for_m10_hardening",
        "crash": "reserved_for_m10_hardening",
    }


def test_on_box_provider_records_process_adapter_wbc(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.providers.on_box.subprocess.run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "ok\n", ""),
    )

    provider = OnBoxProvider(_cloud_spec(tmp_path, provider="ssh"))
    provider.ssh_exec("echo ok")

    sidecar = process_adapter_wbc_dir(
        workspace,
        producer_family="cloud_provider_adapter",
        adapter_name="OnBoxProvider",
    )
    records = _records(sidecar / "events.ndjson")

    assert [record["payload"]["boundary_event"] for record in records] == ["started", "terminal"]
    assert records[-1]["payload"]["status"] == "completed"


def test_ssh_provider_ssh_exec_records_process_adapter_wbc(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.providers.ssh.shutil.which",
        lambda name: name,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.providers.ssh.tempfile.gettempdir",
        lambda: str(tmp_path),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.providers.ssh.subprocess.run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "ok\n", ""),
    )

    provider = SshProvider(_cloud_spec(tmp_path, provider="ssh"))
    provider.ssh_exec("pwd")

    sidecar = process_adapter_wbc_dir(
        tmp_path / "arnold-process-adapter-wbc" / "ssh",
        producer_family="cloud_provider_adapter",
        adapter_name="SshProvider",
    )
    records = _records(sidecar / "events.ndjson")

    assert [record["payload"]["boundary_event"] for record in records] == ["started", "terminal"]
    assert records[0]["payload"]["surface"] == "ssh_exec"


def test_wrapper_acceptance_gate_records_closed_process_adapter_wbc(tmp_path: Path) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "milestones": [{"label": "M5A", "idea": "m5a.md"}],
                "successors": [
                    {
                        "chain_spec_path": "next/chain.yaml",
                        "label": "M6",
                        "require_accepted_transaction": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    state = ChainState(
        current_milestone_index=0,
        completion_contract_mode="enforce",
        completed=[
            {
                "label": "M5A",
                "plan": "m5a-plan",
                "milestone_index": 0,
                "transaction_id": "tx-001",
                "snapshot_hash": "sha256:test",
                "source_commit_ref": "a" * 40,
                "runtime_identity": "ci-main",
                "acceptance_receipt": {
                    "transaction_id": "tx-001",
                    "snapshot_hash": "sha256:test",
                    "milestone_label": "M5A",
                    "milestone_index": 0,
                    "plan_name": "m5a-plan",
                },
            }
        ],
    )
    save_chain_state(spec_path, state)

    result = check_wrapper_acceptance_gate(
        str(spec_path),
        workspace=str(tmp_path),
        caller_kind="watchdog",
    )

    sidecar = process_adapter_wbc_dir(
        tmp_path,
        producer_family="cloud_wrapper_adapter",
        adapter_name="wrapper_acceptance_gate",
    )
    records = _records(sidecar / "events.ndjson")

    assert result["gate_open"] is False
    assert records[-1]["payload"]["status"] == "gate_closed"
    assert records[-1]["payload"]["outcome"] == "blocked"


def test_cloud_supervise_tick_records_process_adapter_wbc(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli.cloud_chain_status_payload",
        lambda *_args, **_kwargs: {
            "effective_status": "running",
            "runner": {"status": "running"},
            "sync": {},
            "pr": {},
            "logs": {},
            "provider_consistency": {},
            "chain_state": {},
        },
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._resolve_remote_chain_spec",
        lambda *_args, **_kwargs: "/workspace/app/chain.yaml",
    )

    report = cloud_supervise_tick(
        tmp_path,
        argparse.Namespace(session="demo"),
        SimpleNamespace(provider="ssh", repo=SimpleNamespace(workspace="/workspace/app")),
        SimpleNamespace(),
    )

    sidecar = process_adapter_wbc_dir(
        tmp_path,
        producer_family="cloud_supervision_adapter",
        adapter_name="cloud_supervise_tick",
    )
    records = _records(sidecar / "events.ndjson")

    assert report["next_action"] == "noop"
    assert records[-1]["payload"]["status"] == "running"
    assert records[-1]["payload"]["outcome"] == "succeeded"
