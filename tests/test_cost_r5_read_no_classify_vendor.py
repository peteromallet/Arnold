"""M4 T27 — R5 cost branch reads vendor off RunEnvelope.provenance
instead of calling _classify_vendor when UNIFIED_EMIT=1.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from megaplan.observability import cost
from megaplan.observability.events import EventKind


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for key in (
        "UNIFIED_EMIT",
        "UNIFIED_EVALUAND",
        "R5_UNIFIED",
        "MEGAPLAN_UNIFIED_DISPATCH",
    ):
        monkeypatch.delenv(key, raising=False)


def _cost_event(model, *, provenance=None):
    payload = {"model": model, "cost_usd": 1.0}
    if provenance is not None:
        payload["provenance"] = provenance
    return {"kind": EventKind.COST_RECORDED, "payload": payload, "phase": "execute"}


def test_flag_off_calls_classify_vendor():
    ev = _cost_event("claude-opus-4-7", provenance={"vendor": "WRONG"})
    with patch.object(cost, "_classify_vendor", wraps=cost._classify_vendor) as spy:
        cost._aggregate([ev], meta_cost=0.0)
        assert spy.called


def test_flag_on_with_provenance_skips_classify_vendor(monkeypatch):
    monkeypatch.setenv("UNIFIED_EMIT", "1")
    ev = _cost_event("claude-opus-4-7", provenance={"vendor": "claude"})
    with patch.object(cost, "_classify_vendor") as spy:
        agg = cost._aggregate([ev], meta_cost=0.0)
        # COST_RECORDED path must NOT have hit _classify_vendor.
        # Only LLM_CALL_END paths still call it; there are none here.
        assert not spy.called
    assert "claude" in agg["cost_by_vendor"]


def test_flag_on_no_provenance_falls_through(monkeypatch):
    monkeypatch.setenv("UNIFIED_EMIT", "1")
    ev = _cost_event("claude-opus-4-7")
    with patch.object(cost, "_classify_vendor", wraps=cost._classify_vendor) as spy:
        cost._aggregate([ev], meta_cost=0.0)
        assert spy.called


def test_classify_vendor_still_live_and_authoritative():
    # Symbol survives and still classifies the legacy way.
    assert cost._classify_vendor("claude-opus-4-7") == "claude"
    assert cost._classify_vendor("gpt-5") == "codex"
    assert cost._classify_vendor("deepseek-v3") == "deepseek"
