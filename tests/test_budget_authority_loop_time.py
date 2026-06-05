"""M4 T21 — loop time budget + dispatch attribution route through the
budget authority only when UNIFIED_BUDGET=1; flag-OFF is byte-identical.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.loop import engine as loop_engine
from arnold.pipelines.megaplan.runtime import budget_authority as ba


@pytest.fixture(autouse=True)
def _reset_authority():
    ba.uninstall()
    yield
    ba.uninstall()


def _ns(**kwargs):
    return argparse.Namespace(**kwargs)


def test_loop_time_budget_flag_off_is_byte_identical(monkeypatch, tmp_path):
    monkeypatch.delenv("UNIFIED_BUDGET", raising=False)
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    ba.install("t1", base_dir=tmp_path, state_total=0.0)
    state = {"time_budget_seconds": 333}
    args = _ns(time_budget=None, time_budget_seconds=None)
    assert loop_engine._time_budget_seconds(state, args) == 333


def test_loop_time_budget_flag_on_authority_can_override(monkeypatch, tmp_path):
    monkeypatch.setenv("UNIFIED_BUDGET", "1")
    auth = ba.install("t1", base_dir=tmp_path, state_total=0.0)

    def fake_override(*, default: int):
        return 9999

    auth.loop_time_budget_seconds = fake_override
    state = {"time_budget_seconds": 333}
    args = _ns(time_budget=None, time_budget_seconds=None)
    assert loop_engine._time_budget_seconds(state, args) == 9999


def test_loop_time_budget_flag_on_no_authority_falls_through(monkeypatch):
    monkeypatch.setenv("UNIFIED_BUDGET", "1")
    state = {"time_budget_seconds": 600}
    args = _ns(time_budget=None, time_budget_seconds=None)
    assert loop_engine._time_budget_seconds(state, args) == 600


def test_dispatch_attribution_flag_off_no_charge(monkeypatch, tmp_path):
    monkeypatch.delenv("UNIFIED_BUDGET", raising=False)
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    auth = ba.install("t1", base_dir=tmp_path, state_total=0.0)
    loop_engine._record_dispatch_attribution(
        lease_id="L1", fencing_token=1, amount_usd=0.5
    )
    assert auth.current_total() == 0.0


def test_dispatch_attribution_flag_on_charges_authority(monkeypatch, tmp_path):
    monkeypatch.setenv("UNIFIED_BUDGET", "1")
    auth = ba.install("t1", base_dir=tmp_path, state_total=0.0)
    loop_engine._record_dispatch_attribution(
        lease_id="L1", fencing_token=1, amount_usd=0.5
    )
    loop_engine._record_dispatch_attribution(
        lease_id="L1", fencing_token=1, amount_usd=0.5  # idempotent
    )
    assert auth.current_total() == pytest.approx(0.5)


def test_dispatch_attribution_zero_amount_noop(monkeypatch, tmp_path):
    monkeypatch.setenv("UNIFIED_BUDGET", "1")
    auth = ba.install("t1", base_dir=tmp_path, state_total=0.0)
    loop_engine._record_dispatch_attribution(
        lease_id="L1", fencing_token=1, amount_usd=0.0
    )
    assert auth.current_total() == 0.0
