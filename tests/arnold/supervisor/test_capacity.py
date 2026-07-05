from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from arnold.runtime.envelope import make_envelope
from arnold.agent.run_agent import AIAgent
from arnold.agent.tools.code_execution_tool import execute_code
from arnold.agent.tools.image_generation_tool import image_generate_tool
from arnold.agent.tools import rl_training_tool
from arnold.supervisor.capacity import (
    CapacityGate,
    CapacityPoolConfig,
    CapacityStatus,
)
from arnold.supervisor.capacity_context import (
    CapacityContext,
    CapacityGateRejected,
    gate_capacity,
    set_capacity_context,
)
from arnold.execution.operations import (
    NullOperationRegistry,
    OperationKind,
    OperationRequest,
)


def test_capacity_gate_acquires_releases_and_suppresses_duplicate_grants() -> None:
    gate = CapacityGate(
        {
            "workers": CapacityPoolConfig(
                name="workers",
                limit=2,
                wait=True,
                retry_after_seconds=3.0,
            )
        }
    )

    first = gate.acquire("workers", lease_id="lease-a", fencing_token=1, units=2)
    duplicate = gate.acquire("workers", lease_id="lease-a", fencing_token=1, units=2)
    delayed = gate.acquire("workers", lease_id="lease-b", fencing_token=1, units=1)
    released = gate.release("workers", lease_id="lease-a", fencing_token=1)
    second = gate.acquire("workers", lease_id="lease-b", fencing_token=1, units=1)

    assert first.status is CapacityStatus.GRANTED
    assert first.used_units == 2
    assert duplicate.status is CapacityStatus.DUPLICATE
    assert duplicate.used_units == 2
    assert duplicate.reason == "duplicate_grant_suppressed"
    assert delayed.status is CapacityStatus.WAIT
    assert delayed.retry_after_seconds == 3.0
    assert released.status is CapacityStatus.RELEASED
    assert second.status is CapacityStatus.GRANTED
    assert second.used_units == 1


def test_capacity_gate_can_reject_instead_of_waiting() -> None:
    gate = CapacityGate(
        {"gpu": CapacityPoolConfig(name="gpu", limit=1, wait=False)}
    )

    assert gate.acquire("gpu", lease_id="lease-a", fencing_token=1).granted
    rejected = gate.acquire("gpu", lease_id="lease-b", fencing_token=1)

    assert rejected.status is CapacityStatus.REJECT
    assert rejected.rejected is True
    assert rejected.reason == "capacity_exhausted"


def test_capacity_context_records_structured_rejection_metadata() -> None:
    gate = CapacityGate({"provider": CapacityPoolConfig(name="provider", limit=1, wait=False)})
    assert gate.acquire("provider", lease_id="lease-a", fencing_token=1).granted
    last_result: dict[str, object] = {}
    context = CapacityContext(
        gate=gate,
        pool="provider",
        lease_id="lease-b",
        fencing_token=1,
        last_result=last_result,
    )

    try:
        with gate_capacity("provider_call", context):
            raise AssertionError("rejected capacity should not enter operation")
    except CapacityGateRejected as exc:
        metadata = exc.metadata

    assert last_result == {"capacity": metadata}
    assert metadata["operation"] == "provider_call"
    assert metadata["reason"] == "capacity_exhausted"
    assert metadata["grant_required"] == 1
    assert metadata["grant_available"] == 0
    assert metadata["used_units"] == 1
    assert metadata["limit"] == 1


def test_operation_registry_execute_dispatch_returns_capacity_rejection() -> None:
    gate = CapacityGate({"execute": CapacityPoolConfig(name="execute", limit=1, wait=False)})
    assert gate.acquire("execute", lease_id="lease-a", fencing_token=1).granted
    last_result: dict[str, object] = {}
    request = OperationRequest(
        kind=OperationKind.EXECUTE,
        payload={
            "capacity_context": {
                "gate": gate,
                "pool": "execute",
                "lease_id": "lease-b",
                "fencing_token": 1,
                "last_result": last_result,
            }
        },
    )

    result = NullOperationRegistry().dispatch(request)

    assert result.ok is False
    assert result.errors == ("capacity_exhausted", "run_phase")
    assert result.payload["last_result"] == last_result
    assert last_result["capacity"]["operation"] == "operation_registry_execute"


# ---------------------------------------------------------------------------
# T17 — Wait metadata, release accounting, rejection metadata, oracle tests
# ---------------------------------------------------------------------------


def test_wait_decision_carries_reason_retry_used_and_limit() -> None:
    """A WAIT decision must expose reason, retry_after_seconds, used_units, and limit."""
    gate = CapacityGate(
        {"pool": CapacityPoolConfig(name="pool", limit=1, wait=True, retry_after_seconds=5.0)}
    )
    gate.acquire("pool", lease_id="L1", fencing_token=1)
    wait = gate.acquire("pool", lease_id="L2", fencing_token=1)

    assert wait.status is CapacityStatus.WAIT
    assert wait.should_wait is True
    assert wait.reason == "capacity_exhausted"
    assert wait.retry_after_seconds == 5.0
    assert wait.used_units == 1  # L1 still holds the slot
    assert wait.limit == 1
    assert wait.lease_id == "L2"
    assert wait.fencing_token == 1
    assert wait.granted_units == 0  # nothing granted while waiting


def test_release_frees_capacity_for_new_grants() -> None:
    """Releasing a grant must return capacity to the pool so new acquisitions succeed."""
    gate = CapacityGate(
        {"pool": CapacityPoolConfig(name="pool", limit=2, wait=True)}
    )
    a = gate.acquire("pool", lease_id="A", fencing_token=1)
    b = gate.acquire("pool", lease_id="B", fencing_token=1)
    assert a.status is CapacityStatus.GRANTED
    assert b.status is CapacityStatus.GRANTED
    assert gate.usage("pool").used_units == 2

    rel = gate.release("pool", lease_id="A", fencing_token=1)
    assert rel.status is CapacityStatus.RELEASED
    assert gate.usage("pool").used_units == 1

    c = gate.acquire("pool", lease_id="C", fencing_token=1)
    assert c.status is CapacityStatus.GRANTED
    assert gate.usage("pool").used_units == 2


def test_reject_decision_carries_reason_and_no_retry() -> None:
    """A REJECT decision must carry the exhaustion reason and no retry hint."""
    gate = CapacityGate(
        {"pool": CapacityPoolConfig(name="pool", limit=1, wait=False)}
    )
    gate.acquire("pool", lease_id="L1", fencing_token=1)
    rejected = gate.acquire("pool", lease_id="L2", fencing_token=1)

    assert rejected.status is CapacityStatus.REJECT
    assert rejected.rejected is True
    assert rejected.should_wait is False
    assert rejected.granted is False
    assert rejected.reason == "capacity_exhausted"
    assert rejected.retry_after_seconds is None  # reject pools don't retry
    assert rejected.used_units == 1
    assert rejected.limit == 1
    assert rejected.lease_id == "L2"


def test_capacity_oracle_usage_consistency_across_acquire_release_cycle() -> None:
    """Oracle: pool usage must stay consistent through multiple acquire/release cycles."""
    gate = CapacityGate(
        {"p": CapacityPoolConfig(name="p", limit=3, wait=True)}
    )
    # Fill the pool
    for i in range(3):
        d = gate.acquire("p", lease_id=f"L{i}", fencing_token=1)
        assert d.status is CapacityStatus.GRANTED
        assert d.used_units == i + 1
        assert d.limit == 3

    assert gate.usage("p").used_units == 3

    # Release middle grant; usage must drop
    gate.release("p", lease_id="L1", fencing_token=1)
    assert gate.usage("p").used_units == 2

    # Re-acquire in the freed slot
    d = gate.acquire("p", lease_id="L3", fencing_token=1)
    assert d.status is CapacityStatus.GRANTED
    assert gate.usage("p").used_units == 3

    # Release all and verify zero
    for lid in ("L0", "L2", "L3"):
        gate.release("p", lease_id=lid, fencing_token=1)
    assert gate.usage("p").used_units == 0


def test_capacity_oracle_duplicate_across_different_fencing_tokens_are_distinct() -> None:
    """Oracle: same lease_id with different fencing tokens are distinct grants."""
    gate = CapacityGate(
        {"pool": CapacityPoolConfig(name="pool", limit=2, wait=False)}
    )
    a = gate.acquire("pool", lease_id="L", fencing_token=1)
    b = gate.acquire("pool", lease_id="L", fencing_token=2)

    assert a.status is CapacityStatus.GRANTED
    assert b.status is CapacityStatus.GRANTED
    assert gate.usage("pool").used_units == 2

    # Releasing by (L, 1) should only free that grant
    gate.release("pool", lease_id="L", fencing_token=1)
    assert gate.usage("pool").used_units == 1

    # (L, 2) is still held
    gate.release("pool", lease_id="L", fencing_token=2)
    assert gate.usage("pool").used_units == 0


def test_capacity_oracle_duplicate_identity_uses_original_units() -> None:
    """Oracle: a duplicate grant keeps the original unit count, not the new request."""
    gate = CapacityGate(
        {"pool": CapacityPoolConfig(name="pool", limit=5, wait=True)}
    )
    first = gate.acquire("pool", lease_id="X", fencing_token=1, units=3)
    dup = gate.acquire("pool", lease_id="X", fencing_token=1, units=99)

    assert first.status is CapacityStatus.GRANTED
    assert first.granted_units == 3
    assert first.used_units == 3
    assert dup.status is CapacityStatus.DUPLICATE
    assert dup.granted_units == 3  # original, not 99
    assert dup.used_units == 3  # unchanged
    assert gate.usage("pool").used_units == 3  # single grant counted once


def test_envelope_join_duplicate_capacity_grant_suppression() -> None:
    """Envelope join must suppress duplicate concrete (lease_id, fencing_token) grants."""
    a = make_envelope(lease_id="L1", fencing_token=1, capacity_grant=2)
    b = make_envelope(lease_id="L1", fencing_token=1, capacity_grant=5)
    joined = a.join(b)
    assert joined.capacity_grant == 5  # larger wins for duplicate identity
    assert joined.lease_id == "L1"
    assert joined.fencing_token == 1

    # Reverse join is commutative for duplicate suppression
    assert b.join(a).capacity_grant == 5


def test_envelope_join_distinct_capacity_grants_are_additive() -> None:
    """Envelope join must add capacity_grants for distinct (lease_id, fencing_token)."""
    a = make_envelope(lease_id="L1", fencing_token=1, capacity_grant=2)
    b = make_envelope(lease_id="L1", fencing_token=2, capacity_grant=3)
    joined = a.join(b)
    assert joined.capacity_grant == 5  # additive for distinct tokens

    # Grants with None lease_id are always additive (legacy / unkeyed)
    c = make_envelope(lease_id=None, fencing_token=None, capacity_grant=4)
    joined2 = joined.join(c)
    assert joined2.capacity_grant == 9  # 5 + 4 additive for None lease_id


def test_envelope_join_mixed_duplicate_and_distinct_grants() -> None:
    """Envelope join with mixed duplicate and distinct grants handles both correctly."""
    a = make_envelope(lease_id="L1", fencing_token=1, capacity_grant=2)
    b = make_envelope(lease_id="L1", fencing_token=1, capacity_grant=3)  # duplicate of a
    c = make_envelope(lease_id="L2", fencing_token=1, capacity_grant=1)  # distinct

    step1 = a.join(b)
    assert step1.capacity_grant == 3  # duplicate suppression: max(2,3)

    # a.join(b) has lease_id=L1, joining with c (L2) should raise LeaseIdConflict
    from arnold.runtime.envelope import LeaseIdConflict
    import pytest as _pytest
    with _pytest.raises(LeaseIdConflict):
        step1.join(c)


def test_capacity_gate_unknown_pool_raises() -> None:
    """Acquiring from an unknown pool name must raise."""
    gate = CapacityGate()
    import pytest as _pytest
    with _pytest.raises(ValueError, match="unknown capacity pool"):
        gate.acquire("nonexistent", lease_id="L", fencing_token=1)


def test_capacity_release_absent_grant_is_idempotent() -> None:
    """Releasing a grant that was never acquired returns RELEASED with grant_absent reason."""
    gate = CapacityGate(
        {"pool": CapacityPoolConfig(name="pool", limit=2, wait=True)}
    )
    result = gate.release("pool", lease_id="ghost", fencing_token=1)
    assert result.status is CapacityStatus.RELEASED
    assert result.reason == "grant_absent"
    assert result.used_units == 0


def _make_provider_agent(response: object) -> AIAgent:
    agent = object.__new__(AIAgent)
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    agent._run_codex_stream = lambda *args, **kwargs: response
    agent._anthropic_messages_create = lambda *args, **kwargs: response
    agent._api_timeout_seconds = lambda: 1.0
    agent._abort_request_client = lambda *args, **kwargs: None
    agent._close_request_openai_client = lambda *args, **kwargs: None

    def _create_request_openai_client(*, reason: str):
        del reason
        return SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kwargs: response)
            )
        )

    agent._create_request_openai_client = _create_request_openai_client
    return agent


def test_provider_call_releases_capacity_on_success() -> None:
    gate = CapacityGate({"provider": CapacityPoolConfig(name="provider", limit=1, wait=False)})
    last_result: dict[str, object] = {}
    context = CapacityContext(
        gate=gate,
        pool="provider",
        lease_id="lease-provider",
        fencing_token=7,
        last_result=last_result,
    )

    with set_capacity_context(context):
        response = _make_provider_agent({"ok": True})._interruptible_api_call({"prompt": "hi"})

    assert response == {"ok": True}
    assert gate.usage("provider").used_units == 0
    assert last_result == {}


def test_provider_call_wait_metadata_is_recorded_on_delay() -> None:
    gate = CapacityGate(
        {"provider": CapacityPoolConfig(name="provider", limit=1, wait=True, retry_after_seconds=2.5)}
    )
    assert gate.acquire("provider", lease_id="holder", fencing_token=1).granted
    last_result: dict[str, object] = {}
    context = CapacityContext(
        gate=gate,
        pool="provider",
        lease_id="lease-provider",
        fencing_token=7,
        last_result=last_result,
    )

    with set_capacity_context(context):
        try:
            _make_provider_agent({"ok": True})._interruptible_api_call({"prompt": "hi"})
        except CapacityGateRejected as exc:
            metadata = exc.metadata
        else:  # pragma: no cover - defensive
            raise AssertionError("provider call should have been delayed")

    assert metadata["operation"] == "provider_call"
    assert metadata["status"] == "wait"
    assert metadata["retry_after_seconds"] == 2.5
    assert last_result["capacity"] == metadata


def test_code_execution_subprocess_releases_capacity_on_success() -> None:
    gate = CapacityGate({"code": CapacityPoolConfig(name="code", limit=1, wait=False)})
    last_result: dict[str, object] = {}
    context = CapacityContext(
        gate=gate,
        pool="code",
        lease_id="lease-code",
        fencing_token=11,
        last_result=last_result,
    )

    with set_capacity_context(context):
        result = json.loads(execute_code("print('sandbox-ok')"))

    assert result["status"] == "success"
    assert "sandbox-ok" in result["output"]
    assert gate.usage("code").used_units == 0
    assert last_result == {}


def test_code_execution_subprocess_wait_metadata_is_recorded_on_delay() -> None:
    gate = CapacityGate({"code": CapacityPoolConfig(name="code", limit=1, wait=True, retry_after_seconds=4.0)})
    assert gate.acquire("code", lease_id="holder", fencing_token=1).granted
    last_result: dict[str, object] = {}
    context = CapacityContext(
        gate=gate,
        pool="code",
        lease_id="lease-code",
        fencing_token=11,
        last_result=last_result,
    )

    with set_capacity_context(context):
        result = json.loads(execute_code("print('sandbox-blocked')"))

    assert result["status"] == "error"
    assert "capacity_exhausted" in result["error"]
    assert last_result["capacity"]["operation"] == "code_execution_subprocess"
    assert last_result["capacity"]["status"] == "wait"


def test_image_generation_submission_releases_capacity_on_success(monkeypatch) -> None:
    class _Handler:
        def get(self):
            return {"images": [{"url": "https://example.test/image.png", "width": 64, "height": 64}]}

    monkeypatch.setenv("FAL_KEY", "test-key")
    monkeypatch.setattr("arnold.agent.tools.image_generation_tool.fal_client.submit", lambda *args, **kwargs: _Handler())
    monkeypatch.setattr("arnold.agent.tools.image_generation_tool._upscale_image", lambda *args, **kwargs: None)

    gate = CapacityGate({"image": CapacityPoolConfig(name="image", limit=1, wait=False)})
    last_result: dict[str, object] = {}
    context = CapacityContext(
        gate=gate,
        pool="image",
        lease_id="lease-image",
        fencing_token=13,
        last_result=last_result,
    )

    with set_capacity_context(context):
        result = json.loads(image_generate_tool("draw a square"))

    assert result["success"] is True
    assert gate.usage("image").used_units == 0
    assert last_result == {}


def test_image_generation_submission_wait_metadata_is_recorded_on_delay(monkeypatch) -> None:
    monkeypatch.setenv("FAL_KEY", "test-key")
    gate = CapacityGate({"image": CapacityPoolConfig(name="image", limit=1, wait=True, retry_after_seconds=6.0)})
    assert gate.acquire("image", lease_id="holder", fencing_token=1).granted
    last_result: dict[str, object] = {}
    context = CapacityContext(
        gate=gate,
        pool="image",
        lease_id="lease-image",
        fencing_token=13,
        last_result=last_result,
    )

    with set_capacity_context(context):
        result = json.loads(image_generate_tool("draw a square"))

    assert result["success"] is False
    assert last_result["capacity"]["operation"] == "image_generation_submission"
    assert last_result["capacity"]["status"] == "wait"


def test_rl_training_subprocess_releases_capacity_on_success(monkeypatch, tmp_path: Path) -> None:
    class _Proc:
        returncode = None

        def poll(self):
            return None

    async def _sleep_immediately(seconds: float) -> None:
        del seconds
        return None

    scheduled: list[object] = []
    monkeypatch.setattr(rl_training_tool, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(rl_training_tool, "_ensure_logs_dir", lambda: rl_training_tool.LOGS_DIR.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(rl_training_tool, "spawn", lambda *args, **kwargs: _Proc())
    monkeypatch.setattr(rl_training_tool.asyncio, "sleep", _sleep_immediately)
    monkeypatch.setattr(rl_training_tool.asyncio, "create_task", lambda task: scheduled.append(task))
    monkeypatch.setattr(rl_training_tool, "_monitor_training_run", lambda run_state: SimpleNamespace(run_id=run_state.run_id))
    monkeypatch.setattr(
        rl_training_tool,
        "_environments",
        [rl_training_tool.EnvironmentInfo(name="demo", class_name="Env", file_path=str(tmp_path / "env.py"))],
    )

    gate = CapacityGate({"rl": CapacityPoolConfig(name="rl", limit=1, wait=False)})
    last_result: dict[str, object] = {}
    context = CapacityContext(
        gate=gate,
        pool="rl",
        lease_id="lease-rl",
        fencing_token=17,
        last_result=last_result,
    )
    run_state = rl_training_tool.RunState(run_id="run-1", environment="demo", config={})

    with set_capacity_context(context):
        asyncio.run(rl_training_tool._spawn_training_run(run_state, tmp_path / "config.yaml"))

    assert run_state.status == "running"
    assert gate.usage("rl").used_units == 0
    assert last_result == {}
    assert len(scheduled) == 1


def test_rl_training_subprocess_wait_metadata_is_recorded_on_delay(monkeypatch, tmp_path: Path) -> None:
    async def _sleep_immediately(seconds: float) -> None:
        del seconds
        return None

    monkeypatch.setattr(rl_training_tool, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(rl_training_tool, "_ensure_logs_dir", lambda: rl_training_tool.LOGS_DIR.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(rl_training_tool.asyncio, "sleep", _sleep_immediately)
    monkeypatch.setattr(rl_training_tool, "_stop_training_run", lambda run_state: None)

    gate = CapacityGate({"rl": CapacityPoolConfig(name="rl", limit=1, wait=True, retry_after_seconds=8.0)})
    assert gate.acquire("rl", lease_id="holder", fencing_token=1).granted
    last_result: dict[str, object] = {}
    context = CapacityContext(
        gate=gate,
        pool="rl",
        lease_id="lease-rl",
        fencing_token=17,
        last_result=last_result,
    )
    run_state = rl_training_tool.RunState(run_id="run-2", environment="demo", config={})

    with set_capacity_context(context):
        asyncio.run(rl_training_tool._spawn_training_run(run_state, tmp_path / "config.yaml"))

    assert run_state.status == "failed"
    assert last_result["capacity"]["operation"] == "rl_training_subprocess"
    assert last_result["capacity"]["status"] == "wait"
