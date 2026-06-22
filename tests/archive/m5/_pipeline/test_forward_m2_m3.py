"""Focused metadata-alignment tests for the forward M2/M3 module.

Verifies that the competing forward ``Port`` declaration has been retired
and the public ``Port`` surface now delegates to the canonical
``arnold.pipeline.types.Port``, with no remaining conflicting public
protocol fields such as integer cardinality/version.
"""

from __future__ import annotations

import dataclasses

import pytest

from arnold.pipeline import CONTRACT_RESULT_SCHEMA_VERSION, ContractResult, types as canonical_types
from arnold.pipelines.megaplan._pipeline import _forward_m2_m3
from arnold.pipelines.megaplan._pipeline.types import StepResult


# ── Port identity (canonical delegation) ────────────────────────────────


class TestPortDelegation:
    """The forward module's Port must be the canonical arnold.pipeline.types.Port."""

    def test_port_is_canonical(self) -> None:
        assert _forward_m2_m3.Port is canonical_types.Port

    def test_port_in_all(self) -> None:
        assert "Port" in _forward_m2_m3.__all__

    def test_port_is_frozen_dataclass(self) -> None:
        assert dataclasses.is_dataclass(canonical_types.Port)
        # Confirm forward export is the same concrete type.
        port = _forward_m2_m3.Port(name="test", content_type="text/markdown")
        assert isinstance(port, canonical_types.Port)
        assert port.name == "test"
        assert port.content_type == "text/markdown"
        assert port.taint == frozenset()
        assert port.cardinality == "singleton"
        assert port.logical_type is None
        assert port.accepted_version_range is None

    def test_port_preserves_legacy_taint_constructor_and_new_metadata(self) -> None:
        port = _forward_m2_m3.Port(
            "reviews",
            "application/json",
            frozenset({"sensitive"}),
            cardinality="collection",
            logical_type="review",
        )

        assert port.taint == frozenset({"sensitive"})
        assert port.cardinality == "collection"
        assert port.logical_type == "review"


# ── No competing protocol fields ────────────────────────────────────────


class TestNoCompetingProtocolFields:
    """The canonical Port must not carry the retired integer
    cardinality/version or schema/kind Protocol fields."""

    CANONICAL_FIELDS = frozenset(
        {
            "name",
            "content_type",
            "taint",
            "cardinality",
            "logical_type",
            "accepted_version_range",
        }
    )
    RETIRED_FIELDS = frozenset({"kind", "schema", "version"})

    def test_canonical_fields_only(self) -> None:
        field_names = {f.name for f in dataclasses.fields(canonical_types.Port)}
        assert field_names == self.CANONICAL_FIELDS

    def test_no_retired_fields(self) -> None:
        field_names = {f.name for f in dataclasses.fields(canonical_types.Port)}
        assert field_names.isdisjoint(self.RETIRED_FIELDS)

    def test_port_instantiation_rejects_retired_fields(self) -> None:
        """Constructing a Port with retired fields must raise TypeError."""
        with pytest.raises(TypeError):
            _forward_m2_m3.Port(
                name="bad",
                content_type="text/markdown",
                version=1,  # retired — must not be accepted
            )


# ── PortKind retirement ─────────────────────────────────────────────────


class TestPortKindRetired:
    """PortKind must not be exported from the forward module."""

    def test_portkind_not_in_all(self) -> None:
        assert "PortKind" not in _forward_m2_m3.__all__

    def test_portkind_not_accessible(self) -> None:
        assert not hasattr(_forward_m2_m3, "PortKind")


# ── Preserved forward declarations ──────────────────────────────────────


class TestPreservedForwardDeclarations:
    """RoutingKey, Graph, restore_and_diverge, and the bridge must
    remain intact."""

    def test_routing_key_preserved(self) -> None:
        assert hasattr(_forward_m2_m3, "RoutingKey")
        assert "RoutingKey" in _forward_m2_m3.__all__
        rk = _forward_m2_m3.RoutingKey(name="proceed", kind="advance")
        assert rk.name == "proceed"
        assert rk.kind == "advance"

    def test_routing_key_kind_preserved(self) -> None:
        assert hasattr(_forward_m2_m3, "RoutingKeyKind")
        assert "RoutingKeyKind" in _forward_m2_m3.__all__

    def test_graph_preserved(self) -> None:
        assert hasattr(_forward_m2_m3, "Graph")
        assert "Graph" in _forward_m2_m3.__all__

    def test_restore_and_diverge_preserved(self) -> None:
        assert hasattr(_forward_m2_m3, "restore_and_diverge")
        assert "restore_and_diverge" in _forward_m2_m3.__all__
        sentinel = _forward_m2_m3.restore_and_diverge
        assert repr(sentinel) == "restore_and_diverge"
        rk = sentinel.to_routing_key()
        assert rk.name == "restore_and_diverge"
        assert rk.kind == "restore"

    def test_bridge_preserved(self) -> None:
        assert hasattr(_forward_m2_m3, "_bridge_recommendation_to_routing_key")
        assert "_bridge_recommendation_to_routing_key" in _forward_m2_m3.__all__
        bridge = _forward_m2_m3._bridge_recommendation_to_routing_key
        rk = bridge("proceed")
        assert rk.name == "proceed"
        assert rk.kind == "advance"

    def test_bridge_unknown_raises(self) -> None:
        bridge = _forward_m2_m3._bridge_recommendation_to_routing_key
        with pytest.raises(ValueError, match="Unknown recommendation"):
            bridge("nonexistent")


class TestStepResultContractResult:
    """Megaplan StepResult should carry the Arnold-neutral ContractResult additively."""

    def test_contract_result_defaults_none(self) -> None:
        result = StepResult()
        assert result.contract_result is None

    def test_contract_result_preserves_structural_vs_payload_schema_versions(self) -> None:
        contract = ContractResult(payload={"schema_version": "sha256:typed-port-payload-v1"})
        result = StepResult(contract_result=contract)

        assert result.contract_result is contract
        assert result.contract_result.schema_version == CONTRACT_RESULT_SCHEMA_VERSION
        assert result.contract_result.payload["schema_version"] == "sha256:typed-port-payload-v1"
