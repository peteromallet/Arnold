"""Contract tests for megaplan._pipeline._forward_m2_m3.

Three contract units:
1. RoutingKey construction and attribute integrity
2. _bridge_recommendation_to_routing_key round-trip for all four legacy labels
3. restore_and_diverge sentinel identity and RoutingKey projection
"""

from __future__ import annotations

import pytest

from megaplan._pipeline._forward_m2_m3 import (
    Graph,
    Port,
    PortKind,
    RoutingKey,
    RoutingKeyKind,
    _bridge_recommendation_to_routing_key,
    restore_and_diverge,
)


class TestRoutingKeyContract:
    """T1.1: RoutingKey is constructible and carries name + kind."""

    def test_construct_default_kind(self):
        """Default kind is 'advance'."""
        rk = RoutingKey(name="advance")
        assert rk.name == "advance"
        assert rk.kind == "advance"

    def test_construct_explicit_kind(self):
        """All six RoutingKey kind values are accepted."""
        for kind in ("advance", "revise", "restore", "escalate", "select", "custom"):
            rk = RoutingKey(name=kind, kind=kind)
            assert rk.name == kind
            assert rk.kind == kind

    def test_immutable(self):
        """RoutingKey is frozen — mutation is rejected."""
        rk = RoutingKey(name="test", kind="advance")
        with pytest.raises(Exception):
            rk.name = "mutated"  # type: ignore[misc]


class TestBridgeRoundTrip:
    """T1.2: _bridge_recommendation_to_routing_key covers all four
    legacy GateRecommendation labels with correct name/kind pairs."""

    def test_proceed(self):
        rk = _bridge_recommendation_to_routing_key("proceed")
        assert rk.name == "proceed"
        assert rk.kind == "advance"

    def test_iterate(self):
        rk = _bridge_recommendation_to_routing_key("iterate")
        assert rk.name == "iterate"
        assert rk.kind == "revise"

    def test_tiebreaker(self):
        rk = _bridge_recommendation_to_routing_key("tiebreaker")
        assert rk.name == "tiebreaker"
        assert rk.kind == "advance"

    def test_escalate(self):
        rk = _bridge_recommendation_to_routing_key("escalate")
        assert rk.name == "escalate"
        assert rk.kind == "escalate"

    def test_unknown_recommendation_raises(self):
        """Unknown gate-verdict labels raise ValueError."""
        with pytest.raises(ValueError, match="Unknown gate-verdict label"):
            _bridge_recommendation_to_routing_key("invalid")  # type: ignore[arg-type]

    def test_proceed_and_tiebreaker_collide_on_kind(self):
        """SD2: proceed and tiebreaker both map to kind='advance'.
        Disambiguation is via .name."""
        proceed_rk = _bridge_recommendation_to_routing_key("proceed")
        tiebreaker_rk = _bridge_recommendation_to_routing_key("tiebreaker")
        assert proceed_rk.kind == tiebreaker_rk.kind == "advance"
        assert proceed_rk.name != tiebreaker_rk.name


class TestRestoreAndDivergeSentinel:
    """T1.3: restore_and_diverge is a singleton with correct identity
    and projects to the canonical M2 RoutingKey."""

    def test_singleton(self):
        """Multiple instantiations return the same object."""
        r1 = type(restore_and_diverge)()
        r2 = type(restore_and_diverge)()
        assert r1 is r2  # Singleton via __new__

    def test_repr(self):
        """String representation is the canonical name."""
        assert repr(restore_and_diverge) == "restore_and_diverge"

    def test_to_routing_key(self):
        """Projects to a RoutingKey with kind='restore'."""
        rk = restore_and_diverge.to_routing_key()
        assert isinstance(rk, RoutingKey)
        assert rk.name == "restore_and_diverge"
        assert rk.kind == "restore"
