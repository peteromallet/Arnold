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
    assert manifest["provider_contract"]["capabilities"]["persistent_session"] is True
    assert manifest["provider_contract"]["capabilities"]["exact_session_resume"] is True
    for field in (
        "prompt_path",
        "result_path",
        "log_path",
        "manifest_path",
        "provider_raw_output_path",
        "provider_events_path",
    ):
        assert Path(manifest[field]).exists()
    assert manifest["telemetry"]["raw_streams_are_provider_specific"] is True
    if backend in {"hermes", "claude"}:
        assert manifest["model_session"]["provider"] == backend
        assert manifest["model_session"]["state"] == "reserved"
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


def test_provider_and_control_changes_are_part_of_launch_idempotency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subagent.subprocess, "Popen", lambda *args, **kwargs: _DetachedProcess()
    )

    hermes = asyncio.run(
        subagent.launch_subagent_task(
            ResidentConfig(),
            task="same bounded task",
            project_dir=str(tmp_path),
            model="hermes:glm-5.2",
        )
    )
    claude = asyncio.run(
        subagent.launch_subagent_task(
            ResidentConfig(),
            task="same bounded task",
            project_dir=str(tmp_path),
            model="claude:opus",
        )
    )

    assert hermes.run_id != claude.run_id
    assert hermes.manifest_path != claude.manifest_path


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
    raw_output_path = run_dir / "provider.raw"
    raw_output_path.touch()
    metadata_path = run_dir / "provider-metadata.json"
    events_path = run_dir / "events.jsonl"
    events_path.touch()
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
                "provider_raw_output_path": str(raw_output_path),
                "provider_metadata_path": str(metadata_path),
                "provider_events_path": str(events_path),
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
        captured["env"] = kwargs.get("env")
        output = kwargs.get("stdout")
        assert output is not None
        if backend == "claude":
            session_id = argv[argv.index("--session-id") + 1]
            output.write(
                (
                    json.dumps(
                        {
                            "type": "system",
                            "subtype": "init",
                            "session_id": session_id,
                            "model": model,
                            "tools": ["Read"],
                        }
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "type": "result",
                            "subtype": "success",
                            "session_id": session_id,
                            "is_error": False,
                            "result": "READY",
                            "usage": {"output_tokens": 1},
                        }
                    )
                    + "\n"
                ).encode()
            )
        else:
            output.write(b"READY\n")
            session_id = argv[argv.index("--session-id") + 1]
            Path(argv[argv.index("--metadata-file") + 1]).write_text(
                json.dumps(
                    {
                        "session_id": session_id,
                        "resolved_model": model,
                        "toolsets": ["file"],
                        "usage": {"output_tokens": 1},
                        "events": [],
                    }
                ),
                encoding="utf-8",
            )
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
    assert manifest["model_session"]["provider"] == backend
    assert manifest["model_session"]["state"] == "persisted"
    assert Path(manifest["provider_events_path"]).read_text(encoding="utf-8").strip()
    assert manifest["telemetry"]["status"] == "captured"
    if backend == "claude":
        assert "--no-session-persistence" not in argv
        assert argv[argv.index("--tools") + 1] == "Read,Edit,Write,Glob,Grep"
        assert captured["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "128"


@pytest.mark.parametrize(
    ("backend", "model"),
    [
        ("codex", "gpt-5.6-terra"),
        ("hermes", "zhipu:glm-5.2"),
        ("claude", "opus"),
    ],
)
@pytest.mark.parametrize("explicit_timeout_s", [None, 17.0])
def test_managed_worker_timeout_is_opt_in_for_every_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
    model: str,
    explicit_timeout_s: float | None,
) -> None:
    manifest_path = _worker_manifest(tmp_path, backend=backend, model=model)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if explicit_timeout_s is not None:
        manifest["timeout_policy"] = {
            "mode": "explicit",
            "source": "trusted_cli",
            "timeout_s": explicit_timeout_s,
        }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    captured: dict[str, object] = {"waits": []}

    class _Worker:
        pid = 225

        def wait(self, timeout=None):
            captured["waits"].append(timeout)
            return 0

        def poll(self):
            return 0

    def fake_popen(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["env"] = kwargs.get("env")
        output = kwargs["stdout"]
        if backend == "codex":
            Path(argv[argv.index("--output-last-message") + 1]).write_text(
                "READY\n", encoding="utf-8"
            )
            output.write(
                (
                    json.dumps({"type": "thread.started", "thread_id": "019f5d2e-d5da-75f3-a617-4712a1c57cc4"})
                    + "\n"
                    + json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "READY"}})
                    + "\n"
                ).encode()
            )
        elif backend == "hermes":
            session_id = argv[argv.index("--session-id") + 1]
            Path(argv[argv.index("--metadata-file") + 1]).write_text(
                json.dumps({"session_id": session_id, "resolved_model": model, "events": []}),
                encoding="utf-8",
            )
            output.write(b"READY\n")
        else:
            session_id = argv[argv.index("--session-id") + 1]
            output.write(
                (
                    json.dumps({"type": "system", "subtype": "init", "session_id": session_id, "model": model})
                    + "\n"
                    + json.dumps({"type": "result", "subtype": "success", "session_id": session_id, "is_error": False, "result": "READY"})
                    + "\n"
                ).encode()
            )
        output.flush()
        return _Worker()

    monkeypatch.setattr(subagent.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(subagent.os, "geteuid", lambda: 0)

    assert subagent._run_managed_manifest(manifest_path) == 0
    expected_wait = explicit_timeout_s if explicit_timeout_s is not None else None
    assert captured["waits"] == [expected_wait]
    argv = captured["argv"]
    if backend == "claude":
        if explicit_timeout_s is None:
            assert "--timeout" not in argv
        else:
            assert argv[argv.index("--timeout") + 1] == str(explicit_timeout_s)
    if backend == "hermes" and explicit_timeout_s is None:
        assert captured["env"]["HERMES_API_TIMEOUT"] == "inf"
        assert captured["env"]["HERMES_DEEPSEEK_API_TIMEOUT"] == "inf"
        assert captured["env"]["ARNOLD_RESIDENT_UNBOUNDED_REQUEST"] == "1"


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
    assert manifest["failure"]["category"] == "empty_result"
    assert "without a final response" in manifest["failure"]["message"]


def test_provider_timeout_is_enforced_and_captured_durably(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _worker_manifest(tmp_path, backend="hermes", model="zhipu:glm-5.2")

    class _TimedOutWorker:
        pid = 223
        terminated = False

        def wait(self, timeout=None):
            if not self.terminated:
                raise subagent.subprocess.TimeoutExpired(cmd="hermes", timeout=timeout)
            return -15

        def poll(self):
            return None if not self.terminated else -15

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.terminated = True

    monkeypatch.setattr(
        subagent.subprocess, "Popen", lambda *args, **kwargs: _TimedOutWorker()
    )

    assert subagent._run_managed_manifest(manifest_path) == 124
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "failed"
    assert manifest["returncode"] == 124
    assert manifest["failure"]["category"] == "timeout"
    assert manifest["lifecycle"]["work"]["status"] == "worker_failed"
    assert Path(manifest["provider_events_path"]).is_file()


def test_claude_auth_failure_remains_terminal_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _worker_manifest(tmp_path, backend="claude", model="opus")
    manifest = json.loads(manifest_path.read_text())
    Path(manifest["log_path"]).write_text("Not logged in · Please run /login\n")

    class _Unauthenticated:
        pid = 224

        def wait(self, timeout=None):
            return 1

        def poll(self):
            return 1

    monkeypatch.setattr(
        subagent.subprocess, "Popen", lambda *args, **kwargs: _Unauthenticated()
    )

    assert subagent._run_managed_manifest(manifest_path) == 1
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "failed"
    assert manifest["failure"]["category"] == "authentication_failed"
    assert Path(manifest["failure"]["log_path"]).read_text().startswith("Not logged in")
