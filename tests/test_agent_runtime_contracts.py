from __future__ import annotations

import sys

import megaplan.types as types
from megaplan.workers import WorkerResult


EXPECTED_RUNTIME_ALL = {
    "AgentRequest",
    "AgentResult",
    "TokenUsage",
    "CostUsage",
    "ResultProvenance",
    "FanoutUnit",
    "FanoutResult",
    "scatter_agent_units",
    "AgentSpec",
    "AgentMode",
    "parse_agent_spec",
    "format_agent_spec",
    "AgentDispatcher",
    "PromptProvider",
    "SessionStore",
    "EventEmitter",
    "LivenessTouch",
    "KeySource",
}

LOWER_LEVEL_ADAPTER_NAMES = {
    "CommandRunner",
    "CommandResult",
}

BANNED_IMPORT_PREFIXES = (
    "megaplan.handlers",
    "megaplan.prompts",
    "megaplan.schemas",
    "megaplan.store",
    "megaplan.observability",
    "megaplan.cli",
    "megaplan._pipeline",
    "megaplan.workers",
    "megaplan._core",
)


def test_runtime_public_surface_is_exact_and_identity_preserving() -> None:
    import megaplan.agent_runtime as runtime

    assert set(runtime.__all__) == EXPECTED_RUNTIME_ALL
    assert LOWER_LEVEL_ADAPTER_NAMES.isdisjoint(runtime.__all__)
    assert runtime.AgentSpec is types.AgentSpec
    assert runtime.AgentMode is types.AgentMode
    assert runtime.parse_agent_spec is types.parse_agent_spec
    assert runtime.format_agent_spec is types.format_agent_spec
    assert not hasattr(runtime, "resolved_default_model_for_agent")


def test_runtime_import_keeps_banned_layers_out(monkeypatch) -> None:
    for name in list(sys.modules):
        if name == "megaplan.agent_runtime" or name.startswith("megaplan.agent_runtime."):
            monkeypatch.delitem(sys.modules, name, raising=False)
        elif name.startswith(BANNED_IMPORT_PREFIXES):
            monkeypatch.delitem(sys.modules, name, raising=False)

    import megaplan.agent_runtime  # noqa: F401

    imported_banned = [
        name for name in sys.modules if name.startswith(BANNED_IMPORT_PREFIXES)
    ]
    assert imported_banned == []


def test_agent_result_has_no_worker_conversion_methods() -> None:
    from megaplan.agent_runtime import AgentResult

    assert not hasattr(AgentResult, "from_worker_result")
    assert not hasattr(AgentResult, "to_worker_result")


def test_worker_result_round_trips_agent_result_losslessly() -> None:
    from megaplan.agent_runtime import AgentResult

    worker = WorkerResult(
        payload={"ok": True, "nested": {"value": 1}},
        raw_output='{"ok": true}',
        duration_ms=1234,
        cost_usd=0.42,
        session_id="sess-123",
        trace_output="trace",
        rendered_prompt="prompt",
        model_actual="actual-model",
        prompt_tokens=11,
        completion_tokens=13,
        total_tokens=24,
        shannon_plan={"kind": "resume", "session_id": "shannon-1"},
        rate_limit={"window": "1h", "remaining": 42},
    )

    result = worker.to_agent_result()
    assert result.payload == worker.payload
    assert result.raw_output == worker.raw_output
    assert result.duration_ms == worker.duration_ms
    assert result.cost_usd == worker.cost_usd
    assert result.session_id == worker.session_id
    assert result.trace_output == worker.trace_output
    assert result.rendered_prompt == worker.rendered_prompt
    assert result.model_actual == worker.model_actual
    assert result.prompt_tokens == worker.prompt_tokens
    assert result.completion_tokens == worker.completion_tokens
    assert result.total_tokens == worker.total_tokens
    assert result.shannon_plan == worker.shannon_plan
    assert result.rate_limit == worker.rate_limit

    round_tripped = WorkerResult.from_agent_result(result)
    assert round_tripped == worker


def test_agent_request_preserves_resolved_mode_and_metadata() -> None:
    from megaplan.agent_runtime import AgentRequest, AgentSpec, ResultProvenance

    spec = AgentSpec("codex", model="gpt-5.5", effort="high")
    provenance = ResultProvenance(
        agent="codex",
        mode="real",
        model="gpt-5.5",
        resolved_model="gpt-5.5",
        effort="high",
        session_id="sess",
        metadata={"source": "test"},
    )

    request = AgentRequest(
        agent="codex",
        mode="real",
        model="gpt-5.5",
        resolved_model="gpt-5.5",
        effort="high",
        spec=spec,
        read_only=True,
        prompt="do work",
        system_prompt="system",
        metadata={"step": "execute"},
        timeout_seconds=30,
        provenance=provenance,
        attestation={"readonly": True},
    )

    assert request.agent == "codex"
    assert request.mode == "real"
    assert request.model == "gpt-5.5"
    assert request.resolved_model == "gpt-5.5"
    assert request.effort == "high"
    assert request.spec is spec
    assert request.read_only is True
    assert request.provenance is provenance
    assert request.metadata == {"step": "execute"}
    assert request.attestation == {"readonly": True}


def test_adapter_protocols_are_structural_and_split_by_export_level() -> None:
    import megaplan.agent_runtime as runtime
    from megaplan.agent_runtime import adapters
    from megaplan.agent_runtime.contracts import AgentResult

    class FakeDispatcher:
        def dispatch(self, request: runtime.AgentRequest) -> runtime.AgentResult:
            return AgentResult(
                payload={"agent": request.agent, "read_only": request.read_only},
                raw_output='{"agent": "codex"}',
                duration_ms=7,
                cost_usd=0.01,
                prompt_tokens=2,
                completion_tokens=3,
                total_tokens=5,
            )

    class FakeCommandRunner:
        def run(
            self,
            command: list[str],
            *,
            cwd: str | None = None,
            env: dict[str, str] | None = None,
            timeout_seconds: float | None = None,
        ) -> adapters.CommandResult:
            return adapters.CommandResult(
                returncode=0,
                stdout=" ".join(command),
                metadata={"cwd": cwd, "env": env, "timeout_seconds": timeout_seconds},
            )

    dispatcher = FakeDispatcher()
    request = runtime.AgentRequest(agent="codex", mode="read", read_only=True)

    assert isinstance(dispatcher, runtime.AgentDispatcher)
    assert isinstance(dispatcher, adapters.AgentDispatcher)
    result = dispatcher.dispatch(request)
    assert result.payload == {"agent": "codex", "read_only": True}
    assert result.total_tokens == 5

    runner = FakeCommandRunner()
    assert isinstance(runner, adapters.CommandRunner)
    assert not hasattr(runtime, "CommandRunner")
    assert runner.run(["agent", "status"]).stdout == "agent status"
