"""Lock the truthy convention for unified-dispatch flags.

Gate (SC1): ``"on"``, ``"true"``, ``"yes"``, ``"0"`` all read OFF for
both master and companion env vars, and companions inherit master when
their own var is unset.
"""

from __future__ import annotations

import os
import pytest

import arnold.pipelines.megaplan._pipeline.flags as _flags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pop_master() -> str | None:
    return os.environ.pop("MEGAPLAN_UNIFIED_DISPATCH", None)


def _set_master(val: str) -> None:
    os.environ["MEGAPLAN_UNIFIED_DISPATCH"] = val


def _clear_master() -> None:
    os.environ.pop("MEGAPLAN_UNIFIED_DISPATCH", None)


def _assert_all_off() -> None:
    assert _flags.unified_dispatch_on() is False
    assert _flags.conveyance_strict_on() is False
    assert _flags.r1_authority_on() is False
    assert _flags.activation_emit_on() is False


# ---------------------------------------------------------------------------
# Master flag
# ---------------------------------------------------------------------------

class TestMasterFlag:
    """``unified_dispatch_on()`` reads ``MEGAPLAN_UNIFIED_DISPATCH``."""

    def test_master_unset_is_off(self):
        _clear_master()
        assert _flags.unified_dispatch_on() is False

    def test_master_1_is_on(self):
        _set_master("1")
        assert _flags.unified_dispatch_on() is True

    @pytest.mark.parametrize(
        "bad",
        ["on", "true", "yes", "0", "ON", "TRUE", "YES", "True", "Yes", "", " ", "2"],
    )
    def test_master_non_1_is_off(self, bad):
        _set_master(bad)
        assert _flags.unified_dispatch_on() is False, f"{bad!r} must read OFF"


# ---------------------------------------------------------------------------
# Companion inheritance
# ---------------------------------------------------------------------------

class TestCompanionInheritance:
    """Companions inherit master when their own env var is unset."""

    def test_inherit_master_on_when_own_unset(self):
        _set_master("1")
        for env_name in ("CONVEYANCE_STRICT", "R1_AUTHORITY", "ACTIVATION_EMIT"):
            os.environ.pop(env_name, None)
        assert _flags.conveyance_strict_on() is True
        assert _flags.r1_authority_on() is True
        assert _flags.activation_emit_on() is True

    def test_inherit_master_off_when_own_unset(self):
        _clear_master()
        for env_name in ("CONVEYANCE_STRICT", "R1_AUTHORITY", "ACTIVATION_EMIT"):
            os.environ.pop(env_name, None)
        _assert_all_off()

    def test_companion_own_1_overrides_master_off(self):
        _clear_master()
        os.environ["CONVEYANCE_STRICT"] = "1"
        os.environ["R1_AUTHORITY"] = "1"
        os.environ["ACTIVATION_EMIT"] = "1"
        assert _flags.conveyance_strict_on() is True
        assert _flags.r1_authority_on() is True
        assert _flags.activation_emit_on() is True
        # master is still off
        assert _flags.unified_dispatch_on() is False

    def test_companion_own_off_overrides_master_on(self):
        _set_master("1")
        # Set companions to explicit OFF — truthy values that are not "1"
        os.environ["CONVEYANCE_STRICT"] = "0"
        os.environ["R1_AUTHORITY"] = "off"
        os.environ["ACTIVATION_EMIT"] = "no"
        assert _flags.conveyance_strict_on() is False
        assert _flags.r1_authority_on() is False
        assert _flags.activation_emit_on() is False
        # master is still on
        assert _flags.unified_dispatch_on() is True

    def test_mixed_companions_some_inherit_some_override(self):
        _set_master("1")
        os.environ["CONVEYANCE_STRICT"] = "0"  # explicitly OFF
        os.environ.pop("R1_AUTHORITY", None)  # inherit ON
        os.environ["ACTIVATION_EMIT"] = "1"  # explicitly ON
        assert _flags.conveyance_strict_on() is False
        assert _flags.r1_authority_on() is True
        assert _flags.activation_emit_on() is True


# ---------------------------------------------------------------------------
# Companion-specific OFF values
# ---------------------------------------------------------------------------

class TestCompanionOffValues:
    """``"on"``, ``"true"``, ``"yes"``, ``"0"`` all read OFF for companions too."""

    OFF_VALUES = ["on", "true", "yes", "0", "ON", "TRUE", "YES"]

    @pytest.mark.parametrize("bad", OFF_VALUES)
    def test_conveyance_strict_non_1_off(self, bad):
        os.environ["CONVEYANCE_STRICT"] = bad
        assert _flags.conveyance_strict_on() is False, f"{bad!r} must read OFF"

    @pytest.mark.parametrize("bad", OFF_VALUES)
    def test_r1_authority_non_1_off(self, bad):
        os.environ["R1_AUTHORITY"] = bad
        assert _flags.r1_authority_on() is False, f"{bad!r} must read OFF"

    @pytest.mark.parametrize("bad", OFF_VALUES)
    def test_activation_emit_non_1_off(self, bad):
        os.environ["ACTIVATION_EMIT"] = bad
        assert _flags.activation_emit_on() is False, f"{bad!r} must read OFF"


# ---------------------------------------------------------------------------
# Autouse fixture — leave env clean
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env():
    """Ensure no flag env vars leak between tests."""
    saved = {}
    for key in (
        "MEGAPLAN_UNIFIED_DISPATCH",
        "CONVEYANCE_STRICT",
        "R1_AUTHORITY",
        "ACTIVATION_EMIT",
    ):
        saved[key] = os.environ.pop(key, None)
    yield
    for key, val in saved.items():
        if val is not None:
            os.environ[key] = val
        else:
            os.environ.pop(key, None)
