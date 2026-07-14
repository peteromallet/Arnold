"""Unit tests for ContractLedger and legal_coercions (M2 / T4a)."""

from __future__ import annotations

import pytest

pytest.skip("archived legacy pipeline contract surface", allow_module_level=True)

from arnold.pipelines.megaplan._pipeline import contracts as contracts_mod
from arnold.pipelines.megaplan._pipeline.contracts import (
    ContractLedger,
    coerce,
    is_legal_coercion,
    legal_coercions,
)
from arnold.pipelines.megaplan._pipeline.types import Port


class TestRegisterAndLookupByHash:
    def test_register_returns_deterministic_hash(self) -> None:
        ledger = ContractLedger()
        h1 = ledger.register(
            name="p",
            kind="produce",
            content_type="text/markdown",
            schema={"type": "string"},
            cardinality="one",
        )
        h2 = ledger.register(
            name="p",
            kind="produce",
            content_type="text/markdown",
            schema={"type": "string"},
            cardinality="one",
        )
        assert h1 == h2
        port = ledger.lookup(h1)
        assert isinstance(port, Port)
        assert port.content_type == "text/markdown"

    def test_different_content_type_yields_different_hash(self) -> None:
        ledger = ContractLedger()
        h_md = ledger.register(
            name="p", kind="produce", content_type="text/markdown",
            schema={}, cardinality="one",
        )
        h_png = ledger.register(
            name="p", kind="produce", content_type="image/png",
            schema={}, cardinality="one",
        )
        assert h_md != h_png

    def test_taint_not_in_contract_hash(self) -> None:
        """Hash is over (name, kind, content_type, schema, cardinality) only.

        Caller-side ``taint`` metadata must not alter the contract identity.
        We assert by registering with the same five-tuple twice — the
        contract hash MUST be identical irrespective of any ambient taint.
        """
        ledger = ContractLedger()
        h1 = ledger.register(
            name="p", kind="produce", content_type="text/markdown",
            schema={"x": 1}, cardinality="many",
        )
        h2 = ledger.register(
            name="p", kind="produce", content_type="text/markdown",
            schema={"x": 1}, cardinality="many",
        )
        assert h1 == h2

    def test_lookup_missing_raises(self) -> None:
        ledger = ContractLedger()
        with pytest.raises(KeyError):
            ledger.lookup("deadbeef")


class TestIdentityCoercion:
    def test_identity_is_always_legal_zero_cost(self) -> None:
        assert is_legal_coercion("text/markdown", "text/markdown") is True
        v = object()
        assert coerce("text/markdown", "text/markdown", v) is v

    def test_register_seeds_identity_in_table(self) -> None:
        # Snapshot then mutate via register.
        ledger = ContractLedger()
        ledger.register(
            name="p", kind="produce", content_type="application/x-novel-ct",
            schema={}, cardinality="one",
        )
        assert ("application/x-novel-ct", "application/x-novel-ct") in legal_coercions


class TestMissingCoercionIllegal:
    def test_missing_coercion_is_illegal(self) -> None:
        assert is_legal_coercion("text/markdown", "image/png") is False
        with pytest.raises(KeyError):
            coerce("text/markdown", "image/png", "hi")

    def test_table_seeded_empty_of_cross_coercions(self) -> None:
        """The seeded table has no non-identity coercions by default."""
        cross = [
            (a, b)
            for (a, b) in contracts_mod.legal_coercions.keys()
            if a != b
        ]
        assert cross == []
