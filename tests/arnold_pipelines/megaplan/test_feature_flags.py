"""Unit tests for arnold_pipelines.megaplan.feature_flags.

Covers:
- Default-off behaviour for every flag
- Explicit-on behaviour (env='1')
- Companion inheritance from MEGAPLAN_UNIFIED_DISPATCH
- Independent flags: calibration, control_interface, supervisor_tier, m7_sinks
- unified_evaluand_on R5_UNIFIED alias fallback
- Private helpers (_master_on, _companion_on) exercised through public API
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from arnold_pipelines.megaplan.feature_flags import (
    activation_emit_on,
    calibration_query_route_on,
    control_interface_routing_on,
    conveyance_strict_on,
    effect_ledger_on,
    m7_sinks_on,
    megaplan_unified_dispatch_on,
    r1_authority_on,
    supervisor_tier_routing_on,
    typed_ports_on,
    unified_budget_on,
    unified_config_on,
    unified_dispatch_enabled,
    unified_dispatch_on,
    unified_emit_on,
    unified_evaluand_on,
    unified_evidence_on,
    unified_recovery_on,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _clear_env() -> dict:
    """Return a context manager that clears all env vars."""
    return patch.dict(os.environ, {}, clear=True)


def _set_env(**kwargs: str) -> dict:
    """Return a context manager that sets only the given env vars."""
    return patch.dict(os.environ, kwargs, clear=True)


# ── typed_ports_on ─────────────────────────────────────────────────────────


class TestTypedPortsOn:
    """Default-off; only MEGAPLAN_TYPED_PORTS='1' activates it."""

    def test_default_off(self) -> None:
        with _clear_env():
            assert typed_ports_on() is False

    def test_on_when_1(self) -> None:
        with _set_env(MEGAPLAN_TYPED_PORTS="1"):
            assert typed_ports_on() is True

    def test_off_when_0(self) -> None:
        with _set_env(MEGAPLAN_TYPED_PORTS="0"):
            assert typed_ports_on() is False

    def test_off_when_garbage(self) -> None:
        with _set_env(MEGAPLAN_TYPED_PORTS="true"):
            assert typed_ports_on() is False

    def test_off_when_empty(self) -> None:
        with _set_env(MEGAPLAN_TYPED_PORTS=""):
            assert typed_ports_on() is False

    def test_independent_of_unified_dispatch(self) -> None:
        """typed_ports_on does NOT inherit from the master gate."""
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert typed_ports_on() is False


# ── unified_dispatch_on / megaplan_unified_dispatch_on ─────────────────────


class TestUnifiedDispatchOn:
    """Master gate — default-off, only MEGAPLAN_UNIFIED_DISPATCH='1' flips it."""

    def test_default_off(self) -> None:
        with _clear_env():
            assert unified_dispatch_on() is False

    def test_on_when_1(self) -> None:
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert unified_dispatch_on() is True

    def test_off_when_0(self) -> None:
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="0"):
            assert unified_dispatch_on() is False

    def test_alias_unified_dispatch_enabled(self) -> None:
        """unified_dispatch_enabled() is an alias for unified_dispatch_on()."""
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert unified_dispatch_enabled() is True
        with _clear_env():
            assert unified_dispatch_enabled() is False

    def test_megaplan_unified_dispatch_on_default_off(self) -> None:
        with _clear_env():
            assert megaplan_unified_dispatch_on() is False

    def test_megaplan_unified_dispatch_on_when_1(self) -> None:
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert megaplan_unified_dispatch_on() is True


# ── Companion flags — inheritance from master ──────────────────────────────


class TestCompanionInheritance:
    """Every companion flag inherits from MEGAPLAN_UNIFIED_DISPATCH when
    its own env var is unset, and can be independently overridden."""

    COMPANIONS = [
        ("conveyance_strict_on", "CONVEYANCE_STRICT"),
        ("r1_authority_on", "R1_AUTHORITY"),
        ("activation_emit_on", "ACTIVATION_EMIT"),
        ("unified_emit_on", "UNIFIED_EMIT"),
        ("unified_evidence_on", "UNIFIED_EVIDENCE"),
        ("unified_config_on", "UNIFIED_CONFIG"),
        ("effect_ledger_on", "EFFECT_LEDGER"),
        ("unified_recovery_on", "UNIFIED_RECOVERY"),
        ("unified_budget_on", "UNIFIED_BUDGET"),
    ]

    @pytest.mark.parametrize("func_name,env_var", COMPANIONS)
    def test_default_off_when_master_off(self, func_name: str, env_var: str) -> None:
        """Companion is off by default (master off, companion unset)."""
        func = globals()[func_name]
        with _clear_env():
            assert func() is False

    @pytest.mark.parametrize("func_name,env_var", COMPANIONS)
    def test_inherits_from_master(self, func_name: str, env_var: str) -> None:
        """Companion inherits True when master=1 and companion unset."""
        func = globals()[func_name]
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert func() is True

    @pytest.mark.parametrize("func_name,env_var", COMPANIONS)
    def test_independent_on_when_master_off(self, func_name: str, env_var: str) -> None:
        """Companion can be explicitly on even when master is off."""
        func = globals()[func_name]
        with _set_env(**{env_var: "1"}):
            assert func() is True

    @pytest.mark.parametrize("func_name,env_var", COMPANIONS)
    def test_independent_off_when_master_on(self, func_name: str, env_var: str) -> None:
        """Companion explicitly set to '0' overrides master=1."""
        func = globals()[func_name]
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1", **{env_var: "0"}):
            assert func() is False

    @pytest.mark.parametrize("func_name,env_var", COMPANIONS)
    def test_garbage_value_is_off(self, func_name: str, env_var: str) -> None:
        """Non-'1' values (e.g. 'true', 'yes') are treated as off."""
        func = globals()[func_name]
        with _set_env(**{env_var: "true"}):
            assert func() is False

    @pytest.mark.parametrize("func_name,env_var", COMPANIONS)
    def test_empty_string_is_off(self, func_name: str, env_var: str) -> None:
        """Empty string is treated as off."""
        func = globals()[func_name]
        with _set_env(**{env_var: ""}):
            assert func() is False


# ── unified_evaluand_on — dual-env fallback ────────────────────────────────


class TestUnifiedEvaluandOn:
    """UNIFIED_EVALUAND with R5_UNIFIED fallback, plus master inheritance."""

    def test_default_off(self) -> None:
        with _clear_env():
            assert unified_evaluand_on() is False

    def test_on_via_unified_evaluand(self) -> None:
        with _set_env(UNIFIED_EVALUAND="1"):
            assert unified_evaluand_on() is True

    def test_on_via_r5_unified_fallback(self) -> None:
        with _set_env(R5_UNIFIED="1"):
            assert unified_evaluand_on() is True

    def test_unified_evaluand_takes_precedence(self) -> None:
        """UNIFIED_EVALUAND=0 overrides R5_UNIFIED=1."""
        with _set_env(UNIFIED_EVALUAND="0", R5_UNIFIED="1"):
            assert unified_evaluand_on() is False

    def test_inherits_from_master(self) -> None:
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert unified_evaluand_on() is True

    def test_explicit_on_overrides_master_off(self) -> None:
        with _set_env(UNIFIED_EVALUAND="1", MEGAPLAN_UNIFIED_DISPATCH="0"):
            assert unified_evaluand_on() is True


# ── Independent flags ──────────────────────────────────────────────────────


class TestCalibrationQueryRouteOn:
    """Independent flag — no inheritance from master."""

    def test_default_off(self) -> None:
        with _clear_env():
            assert calibration_query_route_on() is False

    def test_on_when_1(self) -> None:
        with _set_env(MEGAPLAN_CALIBRATION_QUERY_ROUTE="1"):
            assert calibration_query_route_on() is True

    def test_off_when_0(self) -> None:
        with _set_env(MEGAPLAN_CALIBRATION_QUERY_ROUTE="0"):
            assert calibration_query_route_on() is False

    def test_independent_of_master(self) -> None:
        """Must remain off even when MEGAPLAN_UNIFIED_DISPATCH=1."""
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert calibration_query_route_on() is False


class TestM7SinksOn:
    """Independent flag — no inheritance from master."""

    def test_default_off(self) -> None:
        with _clear_env():
            assert m7_sinks_on() is False

    def test_on_when_1(self) -> None:
        with _set_env(MEGAPLAN_M7_SINKS="1"):
            assert m7_sinks_on() is True

    def test_off_when_0(self) -> None:
        with _set_env(MEGAPLAN_M7_SINKS="0"):
            assert m7_sinks_on() is False

    def test_independent_of_master(self) -> None:
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert m7_sinks_on() is False


class TestControlInterfaceRoutingOn:
    """Independent flag — no inheritance from master."""

    def test_default_off(self) -> None:
        with _clear_env():
            assert control_interface_routing_on() is False

    def test_on_when_1(self) -> None:
        with _set_env(MEGAPLAN_CONTROL_INTERFACE_ROUTING="1"):
            assert control_interface_routing_on() is True

    def test_off_when_0(self) -> None:
        with _set_env(MEGAPLAN_CONTROL_INTERFACE_ROUTING="0"):
            assert control_interface_routing_on() is False

    def test_independent_of_master(self) -> None:
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert control_interface_routing_on() is False


class TestSupervisorTierRoutingOn:
    """Independent flag — no inheritance from master; prove isolation from
    sibling independent flags."""

    def test_default_off(self) -> None:
        with _clear_env():
            assert supervisor_tier_routing_on() is False

    def test_on_when_1(self) -> None:
        with _set_env(MEGAPLAN_SUPERVISOR_TIER="1"):
            assert supervisor_tier_routing_on() is True

    def test_off_when_0(self) -> None:
        with _set_env(MEGAPLAN_SUPERVISOR_TIER="0"):
            assert supervisor_tier_routing_on() is False

    def test_off_when_true_string(self) -> None:
        with _set_env(MEGAPLAN_SUPERVISOR_TIER="true"):
            assert supervisor_tier_routing_on() is False

    def test_off_when_empty(self) -> None:
        with _set_env(MEGAPLAN_SUPERVISOR_TIER=""):
            assert supervisor_tier_routing_on() is False

    def test_independent_of_master(self) -> None:
        """Must remain off when MEGAPLAN_UNIFIED_DISPATCH=1 but
        MEGAPLAN_SUPERVISOR_TIER is unset."""
        with _set_env(MEGAPLAN_UNIFIED_DISPATCH="1"):
            assert supervisor_tier_routing_on() is False

    def test_independent_of_control_interface(self) -> None:
        """Must remain off when MEGAPLAN_CONTROL_INTERFACE_ROUTING=1 but
        MEGAPLAN_SUPERVISOR_TIER is unset."""
        with _set_env(MEGAPLAN_CONTROL_INTERFACE_ROUTING="1"):
            assert supervisor_tier_routing_on() is False

    def test_off_despite_both_sibling_flags_on(self) -> None:
        """Both UNIFIED_DISPATCH and CONTROL_INTERFACE_ROUTING on but
        SUPERVISOR_TIER unset — must still be off."""
        with _set_env(
            MEGAPLAN_UNIFIED_DISPATCH="1",
            MEGAPLAN_CONTROL_INTERFACE_ROUTING="1",
        ):
            assert supervisor_tier_routing_on() is False

    def test_on_with_supervisor_only_siblings_off(self) -> None:
        """Only SUPERVISOR_TIER=1, siblings explicitly '0' — must be on."""
        with _set_env(
            MEGAPLAN_SUPERVISOR_TIER="1",
            MEGAPLAN_UNIFIED_DISPATCH="0",
            MEGAPLAN_CONTROL_INTERFACE_ROUTING="0",
        ):
            assert supervisor_tier_routing_on() is True

    def test_on_when_control_interface_also_on(self) -> None:
        """Both independent flags on — supervisor must still activate."""
        with _set_env(
            MEGAPLAN_SUPERVISOR_TIER="1",
            MEGAPLAN_CONTROL_INTERFACE_ROUTING="1",
        ):
            assert supervisor_tier_routing_on() is True

    def test_off_when_control_interface_on_but_supervisor_0(self) -> None:
        """SUPERVISOR_TIER=0, CONTROL_INTERFACE_ROUTING=1 — must be off."""
        with _set_env(
            MEGAPLAN_SUPERVISOR_TIER="0",
            MEGAPLAN_CONTROL_INTERFACE_ROUTING="1",
        ):
            assert supervisor_tier_routing_on() is False
