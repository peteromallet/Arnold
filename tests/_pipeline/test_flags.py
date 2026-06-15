"""Unit tests for megaplan._pipeline.flags."""

from __future__ import annotations

import os
from unittest.mock import patch

from arnold.pipelines.megaplan._pipeline.flags import typed_ports_on, supervisor_tier_routing_on


class TestTypedPortsOn:
    """Three canonical cases: on (env='1'), off (env='0'), missing."""

    def test_on_when_env_is_1(self) -> None:
        with patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "1"}):
            assert typed_ports_on() is True

    def test_off_when_env_is_0(self) -> None:
        with patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "0"}):
            assert typed_ports_on() is False

    def test_off_when_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert typed_ports_on() is False


class TestSupervisorTierRoutingOn:
    """Prove supervisor_tier_routing_on() is default-off, enabled only by
    MEGAPLAN_SUPERVISOR_TIER=1, and independent of MEGAPLAN_UNIFIED_DISPATCH
    and MEGAPLAN_CONTROL_INTERFACE_ROUTING."""

    # -- Default-off / canonical on/off cases ---------------------------------

    def test_default_off_when_env_unset(self) -> None:
        """Must return False when MEGAPLAN_SUPERVISOR_TIER is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert supervisor_tier_routing_on() is False

    def test_on_when_env_is_1(self) -> None:
        """Must return True only when MEGAPLAN_SUPERVISOR_TIER is exactly '1'."""
        with patch.dict(os.environ, {"MEGAPLAN_SUPERVISOR_TIER": "1"}, clear=True):
            assert supervisor_tier_routing_on() is True

    def test_off_when_env_is_0(self) -> None:
        """Must return False for any value other than '1'."""
        with patch.dict(os.environ, {"MEGAPLAN_SUPERVISOR_TIER": "0"}, clear=True):
            assert supervisor_tier_routing_on() is False

    def test_off_when_env_is_true(self) -> None:
        """Must return False for the string 'true' (not the canonical '1')."""
        with patch.dict(os.environ, {"MEGAPLAN_SUPERVISOR_TIER": "true"}, clear=True):
            assert supervisor_tier_routing_on() is False

    def test_off_when_env_is_empty(self) -> None:
        """Must return False for empty string."""
        with patch.dict(os.environ, {"MEGAPLAN_SUPERVISOR_TIER": ""}, clear=True):
            assert supervisor_tier_routing_on() is False

    # -- Independence from MEGAPLAN_UNIFIED_DISPATCH --------------------------

    def test_off_despite_unified_dispatch_on(self) -> None:
        """Must remain False when MEGAPLAN_UNIFIED_DISPATCH=1 but
        MEGAPLAN_SUPERVISOR_TIER is unset — no inheritance from master gate."""
        with patch.dict(os.environ, {"MEGAPLAN_UNIFIED_DISPATCH": "1"}, clear=True):
            assert supervisor_tier_routing_on() is False

    def test_off_despite_unified_dispatch_and_other_flags(self) -> None:
        """Must remain False when MEGAPLAN_UNIFIED_DISPATCH=1 and
        CONTROL_INTERFACE_ROUTING=1 are both set but SUPERVISOR_TIER is
        unset — proves complete independence from sibling flags."""
        with patch.dict(
            os.environ,
            {
                "MEGAPLAN_UNIFIED_DISPATCH": "1",
                "MEGAPLAN_CONTROL_INTERFACE_ROUTING": "1",
            },
            clear=True,
        ):
            assert supervisor_tier_routing_on() is False

    def test_on_with_supervisor_tier_only_all_flags_off(self) -> None:
        """Must return True when only MEGAPLAN_SUPERVISOR_TIER=1 is set
        while all other flags (UNIFIED_DISPATCH, CONTROL_INTERFACE_ROUTING)
        are explicitly '0' — proves no false-positive activation."""
        with patch.dict(
            os.environ,
            {
                "MEGAPLAN_SUPERVISOR_TIER": "1",
                "MEGAPLAN_UNIFIED_DISPATCH": "0",
                "MEGAPLAN_CONTROL_INTERFACE_ROUTING": "0",
            },
            clear=True,
        ):
            assert supervisor_tier_routing_on() is True

    # -- Independence from MEGAPLAN_CONTROL_INTERFACE_ROUTING -----------------

    def test_off_despite_control_interface_routing_on(self) -> None:
        """Must remain False when MEGAPLAN_CONTROL_INTERFACE_ROUTING=1 but
        MEGAPLAN_SUPERVISOR_TIER is unset."""
        with patch.dict(
            os.environ, {"MEGAPLAN_CONTROL_INTERFACE_ROUTING": "1"}, clear=True
        ):
            assert supervisor_tier_routing_on() is False

    def test_on_when_control_interface_also_on(self) -> None:
        """Must return True when both MEGAPLAN_SUPERVISOR_TIER=1 and
        MEGAPLAN_CONTROL_INTERFACE_ROUTING=1 are set — the flags are
        independent, so supervisor should activate regardless of the
        control-interface routing flag state."""
        with patch.dict(
            os.environ,
            {
                "MEGAPLAN_SUPERVISOR_TIER": "1",
                "MEGAPLAN_CONTROL_INTERFACE_ROUTING": "1",
            },
            clear=True,
        ):
            assert supervisor_tier_routing_on() is True

    def test_off_when_control_interface_on_but_supervisor_0(self) -> None:
        """Must return False when MEGAPLAN_SUPERVISOR_TIER=0 but
        MEGAPLAN_CONTROL_INTERFACE_ROUTING=1."""
        with patch.dict(
            os.environ,
            {
                "MEGAPLAN_SUPERVISOR_TIER": "0",
                "MEGAPLAN_CONTROL_INTERFACE_ROUTING": "1",
            },
            clear=True,
        ):
            assert supervisor_tier_routing_on() is False
