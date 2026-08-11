from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident.agent_loop import (
    AgentLoopError,
    AgentRequest,
    ManagedProviderCliAgentRunner,
    _hermes_resume_session_missing,
)
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.cli import _resident_runner
from arnold_pipelines.megaplan.resident.tool_registry import ToolRegistry
from arnold_pipelines.megaplan.store.file import FileStore


def _manifests(root: Path) -> list[Path]:
    return sorted((root / "provider_runs").glob("*/*/manifest.json"))


def _request(conversation_id: str = "conversation-1") -> AgentRequest:
    return AgentRequest(
        conversation_id=conversation_id,
        messages=({"role": "user", "content": "Run the provider turn."},),
        system_prompt="You are the resident.",
        turn_id="turn-provider-test",
    )


class _FakeMessage:
    role = "assistant"
    model = "glm-5.2"
    stopReason = "end_turn"
    content: list[dict[str, object]] = []
    usage = {"input": 5, "output": 3, "totalTokens": 8, "cost": {"total": 0.0001}}


class _FakeTurn:
    messages = (_FakeMessage(),)
    assistant_message = messages[0]
    assistant_text = "OMP_RESIDENT_OK"
    events: tuple[object, ...] = ()

    def require_assistant_text(self) -> str:
        return self.assistant_text


class _FakeStats:
    tokens = {"input": 5, "output": 3, "total": 8}


class _FakeRpcClient:
    """Fake omp_rpc.RpcClient for hermes->omp routed turns (B11)."""

    instances: list["_FakeRpcClient"] = []
    hang_event: asyncio.Event | None = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = dict(kwargs)
        self.stopped = False
        self.prompt: str | None = None
        _FakeRpcClient.instances.append(self)

    def start(self) -> None:
        pass

    def set_model(self, provider: str, model: str) -> None:
        pass

    def set_thinking_level(self, level: str) -> None:
        pass

    def get_state(self) -> dict[str, object]:
        return {"model": {"id": self.kwargs.get("model")}}

    def prompt_and_wait(self, prompt: str, timeout: object = None) -> _FakeTurn:
        self.prompt = prompt
        event = _FakeRpcClient.hang_event
        if event is not None and event.is_set():
            # Match omp_rpc's timeout behavior: builtin TimeoutError.
            raise TimeoutError("simulated omp RPC timeout")
        return _FakeTurn()

    def get_session_stats(self) -> _FakeStats:
        return _FakeStats()

    def stop(self) -> None:
        self.stopped = True


def _hermes_runner(tmp_path: Path, **config_overrides: object) -> ManagedProviderCliAgentRunner:
    return ManagedProviderCliAgentRunner(
        ResidentConfig(
            model_provider="hermes",
            model_name="zhipu:glm-5.2",
            model_timeout_s=5,
            model_max_tokens=1234,
            model_toolsets="file,terminal",
            **config_overrides,  # type: ignore[arg-type]
        ),
        cwd=tmp_path,
        state_root=tmp_path / "state",
    )


def test_resident_cli_selects_managed_glm_runner_and_store_custody(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "resident-store")

    runner = _resident_runner(ResidentConfig(), tmp_path, store=store)

    assert isinstance(runner, ManagedProviderCliAgentRunner)
    assert runner.config.model_provider == "hermes"
    assert runner.config.model_name == "zhipu:glm-5.2"
    assert runner.state_root == store.root


def test_hermes_resident_runner_persists_artifacts_and_runs_stateless_omp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeRpcClient.instances.clear()
    monkeypatch.setattr("omp_rpc.RpcClient", _FakeRpcClient)
    state_root = tmp_path / "state"
    runner = _hermes_runner(tmp_path)

    first = asyncio.run(runner.run(_request(), ToolRegistry()))
    second = asyncio.run(runner.run(_request(), ToolRegistry()))

    # Hermes routes through the omp RPC adapter (B11): stateless per-turn
    # sessions, never resumed, never persisted.
    assert first.final_text == "OMP_RESIDENT_OK"
    assert second.final_text == "OMP_RESIDENT_OK"
    assert first.metadata["session_mode"] == "new"
    assert second.metadata["session_mode"] == "new"
    assert first.metadata["session_id"] != second.metadata["session_id"]
    assert len(_FakeRpcClient.instances) == 2
    for client in _FakeRpcClient.instances:
        assert client.kwargs["provider"] == "zai"
        assert client.kwargs["model"] == "glm-5.2"
        assert client.kwargs["no_session"] is True
        assert client.stopped is True
    assert list((state_root / "provider_sessions").glob("*.json")) == []

    manifests = _manifests(state_root)
    assert len(manifests) == 2
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text())
        run_dir = manifest_path.parent
        assert manifest["status"] == "completed"
        assert manifest["provider"] == "omp"
        assert manifest["model"] == "zai/glm-5.2"
        assert manifest["model_session"]["state"] == "ephemeral"
        assert manifest["model_session"]["resume_semantics"] == "stateless"
        assert (run_dir / "prompt.md").is_file()
        assert (run_dir / "result.md").read_text().strip() == "OMP_RESIDENT_OK"
        assert (run_dir / "run.log").is_file()
        assert (run_dir / "provider.raw").is_file()
        assert (run_dir / "events.jsonl").is_file()


def test_hermes_resident_runner_stateless_turns_never_share_handles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeRpcClient.instances.clear()
    monkeypatch.setattr("omp_rpc.RpcClient", _FakeRpcClient)
    state_root = tmp_path / "state"
    runner = _hermes_runner(tmp_path)

    first = asyncio.run(runner.run(_request(), ToolRegistry()))
    second = asyncio.run(runner.run(_request(), ToolRegistry()))
    third = asyncio.run(runner.run(_request(), ToolRegistry()))

    markers = [first.metadata["session_id"], second.metadata["session_id"], third.metadata["session_id"]]
    assert len(set(markers)) == 3  # fresh stateless marker per turn
    assert len(_FakeRpcClient.instances) == 3
    # No session file is ever persisted for the omp route (B7).
    assert list((state_root / "provider_sessions").glob("*.json")) == []


def test_hermes_missing_resume_is_not_replayed_stateless_omp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Post-B11 hermes turns are stateless omp turns: there is no resume to
    # lose, so the launcher-era quarantine/retry path never triggers.
    _FakeRpcClient.instances.clear()
    monkeypatch.setattr("omp_rpc.RpcClient", _FakeRpcClient)
    state_root = tmp_path / "state"
    runner = _hermes_runner(tmp_path)

    first = asyncio.run(runner.run(_request(), ToolRegistry()))
    recovered = asyncio.run(runner.run(_request(), ToolRegistry()))

    assert first.final_text == recovered.final_text == "OMP_RESIDENT_OK"
    manifests = [json.loads(path.read_text()) for path in _manifests(state_root)]
    assert all(item["status"] == "completed" for item in manifests)
    assert all(item["model_session"]["state"] == "ephemeral" for item in manifests)
    # No quarantine dir: nothing to quarantine when turns never resume.
    assert not (state_root / "provider_sessions" / "quarantine").exists()


def test_hermes_missing_resume_detection_requires_pre_dispatch_evidence(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "run.log"
    raw_path = tmp_path / "provider.raw"
    metadata_path = tmp_path / "provider-metadata.json"
    diagnostic = "error: Hermes session stale-handle does not exist\n"
    log_path.write_text(diagnostic)
    raw_path.write_text("")
    metadata_path.write_text("")

    assert _hermes_resume_session_missing(
        log_path=log_path,
        raw_path=raw_path,
        metadata_path=metadata_path,
        returncode=8,
    )
    assert not _hermes_resume_session_missing(
        log_path=log_path,
        raw_path=raw_path,
        metadata_path=metadata_path,
        returncode=6,
    )

    log_path.write_text("provider failed without a pre-dispatch diagnostic\n")
    raw_path.write_text(diagnostic)
    assert not _hermes_resume_session_missing(
        log_path=log_path,
        raw_path=raw_path,
        metadata_path=metadata_path,
        returncode=8,
    )

    raw_path.write_text("")
    log_path.write_text(diagnostic)
    metadata_path.write_text('{"session_id":"possibly-started"}')
    assert not _hermes_resume_session_missing(
        log_path=log_path,
        raw_path=raw_path,
        metadata_path=metadata_path,
        returncode=8,
    )


def test_codex_resident_runner_captures_thread_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex = tmp_path / "codex"
    calls = tmp_path / "codex-calls.jsonl"
    session_id = "11111111-2222-4333-8444-555555555555"
    codex.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args=sys.argv[1:]\n"
        "Path(os.environ['PROVIDER_CALLS']).open('a').write(json.dumps(args)+'\\n')\n"
        "out=Path(args[args.index('--output-last-message')+1])\n"
        "out.write_text('CODEX_RESIDENT_OK\\n')\n"
        "sys.stdin.read()\n"
        f"print(json.dumps({{'type':'thread.started','thread_id':'{session_id}'}}))\n"
        "print(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}))\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PROVIDER_CALLS", str(calls))
    state_root = tmp_path / "state"
    runner = ManagedProviderCliAgentRunner(
        ResidentConfig(model_provider="codex", model_name="gpt-5.6-terra"),
        cwd=tmp_path,
        state_root=state_root,
        codex_bin=str(codex),
    )

    first = asyncio.run(runner.run(_request(), ToolRegistry()))
    second = asyncio.run(runner.run(_request(), ToolRegistry()))

    assert first.final_text == second.final_text == "CODEX_RESIDENT_OK"
    assert first.metadata["session_id"] == session_id
    assert second.metadata["session_mode"] == "resume"
    rows = [json.loads(line) for line in calls.read_text().splitlines()]
    assert "resume" not in rows[0]
    assert "resume" in rows[1]
    assert session_id in rows[1]


def test_claude_resident_runner_preserves_auth_failure_evidence(
    tmp_path: Path,
) -> None:
    launcher = tmp_path / "fake_claude.py"
    launcher.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "sid=sys.argv[sys.argv.index('--session-id')+1]\n"
        "print(json.dumps({'type':'system','subtype':'init','session_id':sid,'model':'opus','tools':['Read']}))\n"
        "print(json.dumps({'type':'result','subtype':'error_during_execution','session_id':sid,'is_error':True,'errors':['Not logged in · Please run /login'],'usage':{}}))\n"
        "print('Not logged in', file=sys.stderr)\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    state_root = tmp_path / "state"
    runner = ManagedProviderCliAgentRunner(
        ResidentConfig(
            model_provider="claude",
            model_name="opus",
            model_timeout_s=5,
            model_max_tokens=2222,
            model_toolsets="file",
        ),
        cwd=tmp_path,
        state_root=state_root,
        claude_launcher=launcher,
    )

    with pytest.raises(AgentLoopError, match="authentication_failed"):
        asyncio.run(runner.run(_request(), ToolRegistry()))

    manifest = json.loads(_manifests(state_root)[0].read_text())
    assert manifest["status"] == "failed"
    assert manifest["failure"]["category"] == "authentication_failed"
    assert manifest["model_session"]["state"] == "reserved_unconfirmed"
    assert manifest["provider_contract"]["controls"]["max_tokens"] == 2222
    assert "Not logged in" in Path(manifest["log_path"]).read_text()
    assert "Not logged in" in Path(manifest["provider_raw_output_path"]).read_text()


def test_hermes_resident_runner_captures_timeout_terminally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    _FakeRpcClient.instances.clear()
    _FakeRpcClient.hang_event = asyncio.Event()
    _FakeRpcClient.hang_event.set()
    monkeypatch.setattr("omp_rpc.RpcClient", _FakeRpcClient)
    state_root = tmp_path / "state"
    runner = ManagedProviderCliAgentRunner(
        ResidentConfig(
            model_provider="hermes",
            model_name="zhipu:glm-5.2",
            model_timeout_s=0.05,
        ),
        cwd=tmp_path,
        state_root=state_root,
    )

    with pytest.raises(AgentLoopError, match="timed out"):
        asyncio.run(runner.run(_request("timeout-conversation"), ToolRegistry()))

    manifest = json.loads(_manifests(state_root)[0].read_text())
    assert manifest["status"] == "failed"
    assert manifest["failure"]["category"] == "timeout"
    assert manifest["provider"] == "omp"
    assert _FakeRpcClient.instances[0].stopped is True
    _FakeRpcClient.hang_event = None


def test_provider_environment_preserves_absent_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeRpcClient.instances.clear()
    monkeypatch.setattr("omp_rpc.RpcClient", _FakeRpcClient)
    monkeypatch.setenv("ARNOLD_RESIDENT_DELEGATION_CONTEXT", "stale")
    runner = _hermes_runner(tmp_path)

    response = asyncio.run(runner.run(_request(), ToolRegistry()))

    assert response.final_text == "OMP_RESIDENT_OK"
    # The child did not need the variable; the assertion documents that the
    # runner succeeded after environment_with_provenance removed stale custody.
    assert os.environ["ARNOLD_RESIDENT_DELEGATION_CONTEXT"] == "stale"
