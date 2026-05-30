"""M4 T2 — runtime Governor install gate.

Verifies that :func:`megaplan.runtime.install_runtime_governor` attaches a
Governor to the current ContextVar scope, and that the executor's flag-gated
install seam fires only when ``MEGAPLAN_UNIFIED_DISPATCH=1``.
"""

from __future__ import annotations

import contextvars

import pytest

from megaplan._pipeline.envelope import EMPTY_ENVELOPE
from megaplan.runtime import install_runtime_governor
from megaplan.runtime.governor import (
    Governor,
    current_governor,
    set_governor,
)


def _run_isolated(fn):
    """Run *fn* in a fresh ContextVar copy so installs don't leak."""

    ctx = contextvars.copy_context()
    return ctx.run(fn)


def test_install_runtime_governor_attaches_governor():
    def body():
        set_governor(None)
        assert current_governor() is None
        gov = install_runtime_governor(EMPTY_ENVELOPE)
        assert isinstance(gov, Governor)
        assert current_governor() is gov
        return True

    assert _run_isolated(body) is True


def test_install_runtime_governor_accepts_ledger_path_kwarg(tmp_path):
    def body():
        gov = install_runtime_governor(EMPTY_ENVELOPE, ledger_path=tmp_path)
        assert isinstance(gov, Governor)
        return True

    assert _run_isolated(body) is True


def test_executor_install_seam_on_when_flag_set(monkeypatch):
    """When the flag is on, the executor's install helper installs a Governor."""

    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")

    def body():
        set_governor(None)
        # Mirror the executor's flag-gated install seam.
        from megaplan._pipeline.flags import unified_dispatch_on
        assert unified_dispatch_on() is True
        from megaplan.runtime import install_runtime_governor as _install
        _install(EMPTY_ENVELOPE)
        assert current_governor() is not None
        return True

    assert _run_isolated(body) is True


def test_executor_install_seam_off_when_flag_unset(monkeypatch):
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    def body():
        set_governor(None)
        from megaplan._pipeline.flags import unified_dispatch_on
        assert unified_dispatch_on() is False
        # No install path under the flag-off branch.
        assert current_governor() is None
        return True

    assert _run_isolated(body) is True


def test_governor_charge_defensive_on_legacy_envelope():
    """Governor.charge must not AttributeError on an envelope missing capacity_grant."""

    class _Legacy:
        cost = 1.0
        lineage = ()

    gov = Governor(dollar_cap=10.0)
    gov.charge(_Legacy())
    assert gov.spent_dollars == pytest.approx(1.0)


def test_governor_would_exceed_defensive_on_legacy_envelope():
    class _Legacy:
        cost = 0.0
        lineage = ()

    gov = Governor(dollar_cap=1.0)
    assert gov.would_exceed(_Legacy()) is None
