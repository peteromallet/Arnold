from __future__ import annotations

import time
from dataclasses import fields

import arnold.pipelines.megaplan.agent_runtime as runtime


class RecordingDispatcher:
    def __init__(self) -> None:
        self.requests: list[runtime.AgentRequest] = []

    def dispatch(self, request: runtime.AgentRequest) -> runtime.AgentResult:
        self.requests.append(request)
        if request.metadata.get("fail"):
            raise ValueError(f"boom-{request.agent}")
        time.sleep(float(request.metadata.get("delay", 0.0)))
        return runtime.AgentResult(
            payload={
                "agent": request.agent,
                "mode": request.mode,
                "model": request.model,
                "resolved_model": request.resolved_model,
                "effort": request.effort,
                "spec": request.spec,
                "read_only": request.read_only,
                "prompt": request.prompt,
                "system_prompt": request.system_prompt,
                "metadata": request.metadata,
                "timeout_seconds": request.timeout_seconds,
                "provenance": request.provenance,
                "attestation": request.attestation,
            },
            raw_output=request.agent,
            duration_ms=int(request.metadata.get("duration_ms", 1)),
            cost_usd=float(request.metadata.get("cost_usd", 0.0)),
            prompt_tokens=int(request.metadata.get("prompt_tokens", 0)),
            completion_tokens=int(request.metadata.get("completion_tokens", 0)),
            total_tokens=int(request.metadata.get("total_tokens", 0)),
            provenance=request.provenance,
        )


def _request(agent: str, **overrides: object) -> runtime.AgentRequest:
    spec = runtime.AgentSpec(agent, model=f"{agent}-model", effort="high")
    values = {
        "agent": agent,
        "mode": "read",
        "model": spec.model,
        "resolved_model": f"{agent}-actual",
        "effort": spec.effort,
        "spec": spec,
        "read_only": True,
        "prompt": f"prompt-{agent}",
        "system_prompt": f"system-{agent}",
        "metadata": {"agent": agent},
        "timeout_seconds": 30.0,
        "provenance": runtime.ResultProvenance(
            agent=agent,
            mode="read",
            model=spec.model,
            resolved_model=f"{agent}-actual",
            effort=spec.effort,
            session_id=f"sess-{agent}",
        ),
        "attestation": {"readonly": True, "agent": agent},
    }
    values.update(overrides)
    return runtime.AgentRequest(**values)


def test_scatter_agent_units_preserves_input_order_and_request_fields() -> None:
    dispatcher = RecordingDispatcher()
    slow = _request(
        "codex",
        metadata={
            "agent": "codex",
            "delay": 0.02,
            "cost_usd": 0.2,
            "prompt_tokens": 2,
            "completion_tokens": 3,
            "total_tokens": 5,
        },
    )
    fast = _request(
        "shannon",
        metadata={
            "agent": "shannon",
            "delay": 0.0,
            "cost_usd": 0.3,
            "prompt_tokens": 7,
            "completion_tokens": 11,
            "total_tokens": 18,
        },
    )
    units = [runtime.FanoutUnit(request=slow), runtime.FanoutUnit(request=fast)]

    fanout = runtime.scatter_agent_units(
        units=units,
        dispatcher=dispatcher,
        max_concurrent=2,
    )

    assert [result.payload["agent"] for result in fanout.results] == ["codex", "shannon"]
    assert sorted(request.agent for request in dispatcher.requests) == ["codex", "shannon"]
    assert all(request is unit.request for request, unit in zip(dispatcher.requests, units)) or {
        request.agent: request for request in dispatcher.requests
    } == {unit.request.agent: unit.request for unit in units}
    assert fanout.cost_usd == 0.5
    assert fanout.prompt_tokens == 9
    assert fanout.completion_tokens == 14
    assert fanout.total_tokens == 23

    for unit, result in zip(units, fanout.results):
        for field in fields(runtime.AgentRequest):
            assert result.payload[field.name] == getattr(unit.request, field.name)
        assert result.provenance is unit.request.provenance


def test_scatter_agent_units_uses_ordered_tolerant_error_sentinels() -> None:
    dispatcher = RecordingDispatcher()
    units = [
        runtime.FanoutUnit(request=_request("codex")),
        runtime.FanoutUnit(request=_request("claude", metadata={"fail": True})),
        runtime.FanoutUnit(request=_request("shannon")),
    ]

    def sentinel(
        index: int,
        unit: runtime.FanoutUnit,
        exc: Exception,
    ) -> runtime.AgentResult:
        return runtime.AgentResult(
            payload={"index": index, "agent": unit.request.agent, "error": str(exc)},
            raw_output="",
            duration_ms=0,
            cost_usd=0.0,
            provenance=unit.request.provenance,
        )

    fanout = runtime.scatter_agent_units(
        units=units,
        dispatcher=dispatcher,
        max_concurrent=3,
        on_unit_error=sentinel,
    )

    assert [result.payload["agent"] for result in fanout.results] == [
        "codex",
        "claude",
        "shannon",
    ]
    assert fanout.results[1].payload == {
        "index": 1,
        "agent": "claude",
        "error": "boom-claude",
    }
    assert fanout.results[1].provenance is units[1].request.provenance
    assert fanout.total_tokens == 0


def test_scatter_agent_units_rejects_non_positive_concurrency() -> None:
    dispatcher = RecordingDispatcher()
    unit = runtime.FanoutUnit(request=_request("codex"))

    try:
        runtime.scatter_agent_units(units=[unit], dispatcher=dispatcher, max_concurrent=0)
    except ValueError as exc:
        assert str(exc) == "max_concurrent must be positive"
    else:
        raise AssertionError("expected max_concurrent validation")
