"""Step 10: driver-selection contract tests.

Locks:
    - Default OFF (no MEGAPLAN_UNIFIED_DISPATCH) preserves behavior: select_driver
      returns None and does NOT pin current_substrate.
    - ON selects the new driver: select_driver returns an instance of the right
      driver class and current_substrate() reflects the pinned literal.
    - Anti-silent-no-op: current_substrate() reports the substrate IMMEDIATELY
      after select_driver returns (static, populated at select time).
"""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan import drivers
from arnold.pipelines.megaplan.drivers import (
    SUBSTRATES,
    TOPOLOGIES,
    InProcessDriver,
    SubprocessIsolatedDriver,
    current_substrate,
    reset_substrate,
    select_driver,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_substrate()
    yield
    reset_substrate()


# ---------------------------------------------------------------------------
# Default OFF preserves behavior
# ---------------------------------------------------------------------------


def test_default_off_select_driver_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    assert select_driver("in_process", "linear") is None


def test_default_off_does_not_pin_current_substrate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    select_driver("in_process", "linear")
    assert current_substrate() is None


def test_default_off_subprocess_substrate_also_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    assert select_driver("subprocess_isolated", "fanout") is None
    assert current_substrate() is None


def test_off_non_truthy_values_preserve_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    for val in ("0", "on", "true", "yes", "True", ""):
        monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", val)
        reset_substrate()
        assert select_driver("in_process", "linear") is None, val
        assert current_substrate() is None, val


# ---------------------------------------------------------------------------
# ON selects the new driver + current_substrate is populated at select time
# ---------------------------------------------------------------------------


def test_on_selects_in_process_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    drv = select_driver("in_process", "linear")
    assert isinstance(drv, InProcessDriver)


def test_on_selects_subprocess_isolated_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    drv = select_driver("subprocess_isolated", "fanout")
    assert isinstance(drv, SubprocessIsolatedDriver)


def test_on_current_substrate_returns_selected_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-silent-no-op: substrate is observable the instant select_driver returns."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    assert current_substrate() is None
    select_driver("subprocess_isolated", "dag")
    assert current_substrate() == "subprocess_isolated"
    select_driver("in_process", "linear")
    assert current_substrate() == "in_process"


def test_on_invalid_substrate_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    with pytest.raises(ValueError):
        select_driver("nope", "linear")


def test_on_invalid_topology_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    with pytest.raises(ValueError):
        select_driver("in_process", "nope")


# ---------------------------------------------------------------------------
# Literal-set surface
# ---------------------------------------------------------------------------


def test_substrate_literal_set() -> None:
    assert SUBSTRATES == frozenset({"in_process", "subprocess_isolated"})


def test_topology_literal_set() -> None:
    assert TOPOLOGIES == frozenset({"linear", "fanout", "dag"})


# ---------------------------------------------------------------------------
# Public surface exported from megaplan.drivers
# ---------------------------------------------------------------------------


def test_public_surface() -> None:
    assert hasattr(drivers, "Substrate")
    assert hasattr(drivers, "Topology")
    assert callable(drivers.select_driver)
    assert callable(drivers.current_substrate)
