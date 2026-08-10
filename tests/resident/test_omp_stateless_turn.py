"""B7 — omp resident turns are fresh, stateless RPC sessions.

Every omp turn gets a synthetic ``omp-stateless:<turn>`` identity that is a
handshake marker only: no omp session file is persisted, resume semantics
never apply, and each turn starts a brand-new RPC session.  This test proves
one complete turn end to end through ``ManagedProviderCliAgentRunner`` with a
fake ``omp_rpc.RpcClient``: final text, evidence, usage/ledger shape, the
synthetic identity, and the absence of any persisted omp session file.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident.agent_loop import (
    AgentRequest,
    ManagedProviderCliAgentRunner,
)
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.tool_registry import ToolRegistry

_OMP_STATELESS_RE = re.compile(r"^omp-stateless:[0-9a-f]{32}$")


class _FakeMessage:
    role = "assistant"
    model = "deepseek-v4-flash"
    stopReason = "end_turn"
    content: list[dict[str, object]] = []
    usage = {
        "input": 12,
        "output": 7,
        "cacheRead": 1,
        "cacheWrite": 0,
        "totalTokens": 20,
        "cost": {"total": 0.0004},
    }


class _FakeTurn:
    messages = (_FakeMessage(),)
    assistant_message = messages[0]
    assistant_text = "OMP_RESIDENT_OK"
    events: tuple[object, ...] = ()

    def require_assistant_text(self) -> str:
        return self.assistant_text


class _FakeStats:
    tokens = {"input": 12, "output": 7, "cache_read": 1, "cache_write": 0, "total": 20}


class _FakeRpcClient:
    instances: list["_FakeRpcClient"] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = dict(kwargs)
        self.stopped = False
        self.prompt: str | None = None
        self.timeout: object = None
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
        self.timeout = timeout
        return _FakeTurn()

    def get_session_stats(self) -> _FakeStats:
        return _FakeStats()

    def stop(self) -> None:
        self.stopped = True


def _request(conversation_id: str = "conversation-omp") -> AgentRequest:
    return AgentRequest(
        conversation_id=conversation_id,
        messages=({"role": "user", "content": "Reply with the smoke token."},),
        system_prompt="You are the resident.",
        turn_id="turn-omp-stateless",
    )


def _make_runner(tmp_path: Path) -> ManagedProviderCliAgentRunner:
    return ManagedProviderCliAgentRunner(
        ResidentConfig(
            model_provider="omp",
            model_name="deepseek/deepseek-v4-flash",
            model_timeout_s=5,
            model_max_tokens=1234,
            model_toolsets="file,terminal",
        ),
        cwd=tmp_path,
        state_root=tmp_path / "state",
    )


def test_omp_stateless_turn_completes_with_synthetic_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeRpcClient.instances.clear()
    monkeypatch.setattr("omp_rpc.RpcClient", _FakeRpcClient)

    runner = _make_runner(tmp_path)
    first = asyncio.run(runner.run(_request(), ToolRegistry()))
    second = asyncio.run(runner.run(_request(), ToolRegistry()))

    # ── final text + one-turn success ──────────────────────────────────────
    assert first.final_text == "OMP_RESIDENT_OK"
    assert second.final_text == "OMP_RESIDENT_OK"

    # ── synthetic identity: per-turn marker, never resumed ─────────────────
    assert _OMP_STATELESS_RE.fullmatch(first.metadata["session_id"])
    assert _OMP_STATELESS_RE.fullmatch(second.metadata["session_id"])
    assert first.metadata["session_mode"] == "new"
    assert second.metadata["session_mode"] == "new"
    assert first.metadata["resume_semantics"] == "stateless"
    # Fresh stateless session per turn: distinct markers.
    assert first.metadata["session_id"] != second.metadata["session_id"]

    # ── fresh stateless RPC session per attempt ────────────────────────────
    assert len(_FakeRpcClient.instances) == 2
    for client in _FakeRpcClient.instances:
        assert client.kwargs["provider"] == "deepseek"
        assert client.kwargs["model"] == "deepseek-v4-flash"
        assert client.kwargs["no_session"] is True
        assert client.kwargs["cwd"] == tmp_path
        assert client.kwargs["tools"] == [
            "read", "edit", "write", "glob", "grep", "bash",
        ]
        assert client.stopped is True

    # ── NO persisted omp session file (stateless) ──────────────────────────
    session_dir = tmp_path / "state" / "provider_sessions"
    assert session_dir.is_dir()
    assert list(session_dir.glob("*.json")) == []

    # ── manifest: completed, ephemeral/stateless model session ─────────────
    manifests = sorted((tmp_path / "state" / "provider_runs").glob("*/*/manifest.json"))
    assert len(manifests) == 2
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["status"] == "completed"
        assert manifest["provider"] == "omp"
        assert manifest["model_session"] == {
            "provider": "omp",
            "session_id": manifest["session_dispatch"]["session_id"],
            "state": "ephemeral",
            "persistence": "ephemeral",
            "resume_semantics": "stateless",
        }
        assert manifest["session_dispatch"]["mode"] == "new"
        assert manifest["session_dispatch"]["resume_semantics"] == "stateless"
        assert _OMP_STATELESS_RE.fullmatch(manifest["model_session"]["session_id"])

    # ── usage / ledger shape: exactly-once per-turn aggregate ──────────────
    first_manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    usage = first_manifest["telemetry"]["usage"]
    assert usage["input"] == 12
    assert usage["output"] == 7
    assert usage["cache_read"] == 1
    assert usage["cache_write"] == 0
    assert usage["total"] == 20
    assert usage["cost_usd"] == 0.0004
    assert usage["cost_pricing"] == "omp_usage_cost"
    assert usage["messages_counted"] == 1
    assert usage["provider"] == "deepseek"
    assert usage["model"] == "deepseek-v4-flash"

    # ── evidence artifacts ─────────────────────────────────────────────────
    run_dir = manifests[0].parent
    assert (run_dir / "prompt.md").is_file()
    assert (run_dir / "result.md").read_text().strip() == "OMP_RESIDENT_OK"
    assert (run_dir / "provider.raw").is_file()
    assert (run_dir / "run.log").is_file()
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    event_kinds = [event.get("kind") for event in events]
    assert "session.started" in event_kinds
    assert "turn.completed" in event_kinds
    raw_lines = [
        json.loads(line)
        for line in (run_dir / "provider.raw").read_text(encoding="utf-8").splitlines()
    ]
    assert raw_lines[0]["type"] == "session.started"
    assert raw_lines[0]["session_id"] == first_manifest["model_session"]["session_id"]
    assert raw_lines[-1]["type"] == "turn.completed"
    assert raw_lines[-1]["assistant_text"] == "OMP_RESIDENT_OK"


def test_omp_reserve_and_valid_session_id_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.resident.provider_runtime import (
        reserve_session_id,
        valid_session_id,
    )

    marker = reserve_session_id("omp")
    assert marker is not None
    assert _OMP_STATELESS_RE.fullmatch(marker)
    assert valid_session_id("omp", marker) is True
    assert valid_session_id("omp", "resident_abcdef") is False
    assert valid_session_id("omp", "omp-stateless:short") is False
    # A stateless marker is not a strict-uuid resumable handle (codex/claude
    # require the exact UUID shape); omp itself never resumes it.
    assert valid_session_id("codex", marker) is False
    assert valid_session_id("claude", marker) is False
