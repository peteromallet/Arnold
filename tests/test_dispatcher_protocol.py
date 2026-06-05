"""M4 T5 — Dispatcher Protocol shape + companion-flag inheritance.

These tests pin the request/result shape (liveness IN, god-fields OUT) and
verify that the seven UNIFIED_* companion flags inherit from the master
``MEGAPLAN_UNIFIED_DISPATCH`` gate when their own env var is unset.
"""

from __future__ import annotations

from dataclasses import fields

from arnold.pipelines.megaplan._pipeline.dispatch import (
    Dispatcher,
    DispatchRequest,
    DispatchResult,
)
from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE
from arnold.pipelines.megaplan._pipeline import flags as F


def test_dispatch_request_carries_liveness_sink():
    field_names = {f.name for f in fields(DispatchRequest)}
    assert "envelope" in field_names
    assert "prompt_override" in field_names
    assert "shim_state" in field_names
    assert "liveness_sink" in field_names


def test_dispatch_request_excludes_god_fields():
    """Cost / rate / recovery / budget belong on other seams, NOT on the
    Dispatcher request."""
    field_names = {f.name for f in fields(DispatchRequest)}
    forbidden = {"cost", "rate_limit", "rate", "recovery", "budget"}
    assert field_names.isdisjoint(forbidden), (
        f"DispatchRequest must not bundle god-fields: {field_names & forbidden}"
    )


def test_dispatch_result_shape():
    field_names = {f.name for f in fields(DispatchResult)}
    assert field_names == {"result", "cost", "session_ref"}


def test_dispatcher_protocol_is_runnable():
    class _Fake:
        def run(self, request: DispatchRequest) -> DispatchResult:
            sink = request.liveness_sink
            if sink is not None:
                sink({"alive": True})
            return DispatchResult(result="ok", cost=request.envelope.cost, session_ref="sref")

    fake: Dispatcher = _Fake()
    heartbeats: list[dict] = []
    req = DispatchRequest(
        envelope=EMPTY_ENVELOPE,
        prompt_override="hi",
        shim_state={"k": 1},
        liveness_sink=heartbeats.append,
    )
    res = fake.run(req)
    assert res.result == "ok"
    assert res.session_ref == "sref"
    assert heartbeats == [{"alive": True}]


COMPANIONS = [
    ("UNIFIED_EMIT", F.unified_emit_on),
    ("UNIFIED_EVIDENCE", F.unified_evidence_on),
    ("UNIFIED_CONFIG", F.unified_config_on),
    ("EFFECT_LEDGER", F.effect_ledger_on),
    ("UNIFIED_RECOVERY", F.unified_recovery_on),
    ("UNIFIED_BUDGET", F.unified_budget_on),
    ("UNIFIED_EVALUAND", F.unified_evaluand_on),
]


def test_all_seven_companion_flags_exist():
    assert len(COMPANIONS) == 7


def test_companion_flags_inherit_from_master(monkeypatch):
    for env_name, _ in COMPANIONS:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.delenv("R5_UNIFIED", raising=False)
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    for env_name, fn in COMPANIONS:
        assert fn() is True, f"{env_name} should inherit master ON"
    assert F.unified_dispatch_enabled() is True


def test_companion_flags_off_when_master_off(monkeypatch):
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    for env_name, _ in COMPANIONS:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.delenv("R5_UNIFIED", raising=False)
    for env_name, fn in COMPANIONS:
        assert fn() is False, f"{env_name} should inherit master OFF"
    assert F.unified_dispatch_enabled() is False


def test_companion_flag_override_wins(monkeypatch):
    """A per-organ env override beats the master setting."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    monkeypatch.setenv("UNIFIED_EMIT", "0")
    assert F.unified_emit_on() is False

    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "")
    monkeypatch.setenv("UNIFIED_RECOVERY", "1")
    assert F.unified_recovery_on() is True


def test_r5_unified_alias_routes_to_unified_evaluand(monkeypatch):
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    monkeypatch.delenv("UNIFIED_EVALUAND", raising=False)
    monkeypatch.setenv("R5_UNIFIED", "1")
    assert F.unified_evaluand_on() is True
