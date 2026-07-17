from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident import subagent
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.provenance import DELEGATION_CONTEXT_ENV


class _DetachedProcess:
    pid = 4321


@pytest.fixture(autouse=True)
def _isolate_resident_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)


@pytest.mark.parametrize(
    ("model_spec", "backend", "runtime_model"),
    [
        ("hermes:glm-5.2", "hermes", "zhipu:glm-5.2"),
        ("codex:gpt-5.6-terra", "codex", "gpt-5.6-terra"),
        ("claude:opus", "claude", "opus"),
    ],
)
def test_auto_route_creates_one_durable_provider_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_spec: str,
    backend: str,
    runtime_model: str,
) -> None:
    launches: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        launches.append(list(argv))
        return _DetachedProcess()

    monkeypatch.setattr(subagent.subprocess, "Popen", fake_popen)
    result = asyncio.run(
        subagent.launch_subagent_task(
            ResidentConfig(),
            task=f"bounded {backend} smoke",
            description=f"Run the bounded {backend} smoke",
            project_dir=str(tmp_path),
            model=model_spec,
        )
    )

    manifest = json.loads(Path(result.manifest_path or "").read_text(encoding="utf-8"))
    assert result.status == "running"
    assert manifest["backend"] == backend
    assert manifest["model"] == runtime_model
    assert manifest["model_spec"] == (
        "hermes:zhipu:glm-5.2" if backend == "hermes" else model_spec
    )
    assert manifest["provider_route"] == {
        "backend": backend,
        "runtime_model": runtime_model,
        "model_spec": manifest["model_spec"],
    }
    assert launches and "--run-managed" in launches[0]


def test_explicit_mismatch_fails_before_manifest_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subagent.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("mismatched route started a process"),
    )

    with pytest.raises(ValueError, match="backend/model mismatch"):
        asyncio.run(
            subagent.launch_subagent_task(
                ResidentConfig(),
                task="must not launch",
                project_dir=str(tmp_path),
                backend="codex",
                model="hermes:glm-5.2",
            )
        )

    assert not (tmp_path / ".megaplan/plans/resident-subagents").exists()


def test_hermes_auto_route_preserves_discord_custody_and_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subagent.subprocess,
        "Popen",
        lambda *args, **kwargs: _DetachedProcess(),
    )
    result = asyncio.run(
        subagent.launch_subagent_task(
            ResidentConfig(),
            task="durable Hermes work",
            description="Run durable Hermes work",
            project_dir=str(tmp_path),
            model="hermes:glm-5.2",
            launch_origin={
                "transport": "discord",
                "applicability": "applicable",
                "resident_conversation_id": "rconv_providerroute1",
                "source_record_id": "msg_providerroute1",
                "conversation_key": "discord:dm:123456789012345678",
                "discord_message_id": "987654321098765432",
                "reply_to_message_id": "987654321098765432",
                "dm_user_id": "123456789012345678",
                "source_kind": "discord_inbound_message",
            },
        )
    )

    manifest = json.loads(Path(result.manifest_path or "").read_text(encoding="utf-8"))
    assert manifest["backend"] == "hermes"
    assert manifest["launch_provenance"]["source_record_id"] == "msg_providerroute1"
    assert manifest["completion_delivery"]["transport"] == "discord"
    assert manifest["completion_delivery"]["status"] == "pending"


def _worker_manifest(tmp_path: Path, *, backend: str, model: str) -> Path:
    run_dir = tmp_path / backend
    run_dir.mkdir()
    prompt_path = run_dir / "prompt.md"
    prompt_path.write_text("Reply with the single word READY.", encoding="utf-8")
    result_path = run_dir / "result.md"
    log_path = run_dir / "run.log"
    log_path.touch()
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "arnold-managed-agent-run-v2",
                "run_kind": "resident_delegated_agent",
                "custodian": "arnold.megaplan.managed_agent",
                "run_id": backend,
                "status": "running",
                "prompt_path": str(prompt_path),
                "result_path": str(result_path),
                "log_path": str(log_path),
                "project_dir": str(tmp_path),
                "backend": backend,
                "model": model,
                "reasoning_effort": "medium",
                "provider_options": {
                    "toolsets": "file",
                    "max_tokens": 128,
                    "timeout_s": 30,
                },
                "status_history": [],
                "completion_delivery": {"status": "not_applicable"},
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


@pytest.mark.parametrize(
    ("backend", "model", "launcher_name", "effective_uid", "permission_flag"),
    [
        ("hermes", "zhipu:glm-5.2", "launch_hermes_agent.py", 0, None),
        ("claude", "opus", "launch_claude_agent.py", 0, "--permission-mode"),
        (
            "claude",
            "opus",
            "launch_claude_agent.py",
            1000,
            "--dangerously-skip-permissions",
        ),
    ],
)
def test_managed_worker_dispatches_non_codex_provider_and_captures_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
    model: str,
    launcher_name: str,
    effective_uid: int,
    permission_flag: str | None,
) -> None:
    manifest_path = _worker_manifest(tmp_path, backend=backend, model=model)
    captured: dict[str, object] = {}

    class _Worker:
        pid = 222

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    def fake_popen(argv, **kwargs):
        captured["argv"] = list(argv)
        output = kwargs.get("stdout")
        assert output is not None
        output.write(b"READY\n")
        output.flush()
        return _Worker()

    monkeypatch.setattr(subagent.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(subagent.os, "geteuid", lambda: effective_uid)

    assert subagent._run_managed_manifest(manifest_path) == 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    argv = captured["argv"]
    assert isinstance(argv, list)
    assert any(str(item).endswith(launcher_name) for item in argv)
    assert model in argv
    if permission_flag is not None:
        assert permission_flag in argv
    if backend == "claude" and effective_uid == 0:
        assert argv[argv.index("--permission-mode") + 1] == "auto"
        assert "--dangerously-skip-permissions" not in argv
    assert manifest["status"] == "completed"
    assert Path(manifest["result_path"]).read_text(encoding="utf-8").strip() == "READY"


def test_managed_non_codex_worker_rejects_empty_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _worker_manifest(
        tmp_path, backend="hermes", model="zhipu:glm-5.2"
    )

    class _Worker:
        pid = 222

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(
        subagent.subprocess, "Popen", lambda *args, **kwargs: _Worker()
    )

    assert subagent._run_managed_manifest(manifest_path) == 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert "no final response" in manifest["error"]
