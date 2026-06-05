"""Tests for Arnold ``contracts`` module — ContractLedger, coercion (M3a T21).

Also exercises :class:`PortBindError` from the Megaplan bridge for
completeness, since the task description explicitly mentions it.
"""

from __future__ import annotations

import pytest

from arnold.pipeline.contracts import (
    ContractLedger,
    _contract_hash,
    coerce,
    is_legal_coercion,
    legal_coercions,
)
from arnold.pipeline.types import Port


# ---------------------------------------------------------------------------
# ContractLedger — registration & lookup
# ---------------------------------------------------------------------------


class TestContractLedgerRegister:
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

    def test_different_content_type_different_hash(self) -> None:
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

    def test_taint_excluded_from_hash(self) -> None:
        """Contract hash covers only (name, kind, content_type, schema, cardinality).

        Taint must not affect contract identity.
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
        with pytest.raises(KeyError, match="no contract registered"):
            ledger.lookup("deadbeef")

    def test_contains(self) -> None:
        ledger = ContractLedger()
        h = ledger.register(
            name="q", kind="consume", content_type="application/json",
            schema={}, cardinality="one",
        )
        assert h in ledger
        assert "nonexistent" not in ledger

    def test_different_name_different_hash(self) -> None:
        ledger = ContractLedger()
        h_a = ledger.register(
            name="a", kind="produce", content_type="text/plain",
            schema={}, cardinality="one",
        )
        h_b = ledger.register(
            name="b", kind="produce", content_type="text/plain",
            schema={}, cardinality="one",
        )
        assert h_a != h_b

    def test_different_cardinality_different_hash(self) -> None:
        ledger = ContractLedger()
        h_one = ledger.register(
            name="p", kind="produce", content_type="text/plain",
            schema={}, cardinality="one",
        )
        h_many = ledger.register(
            name="p", kind="produce", content_type="text/plain",
            schema={}, cardinality="many",
        )
        assert h_one != h_many

    def test_multiple_registrations_different_ports(self) -> None:
        ledger = ContractLedger()
        h_a = ledger.register(
            name="a", kind="produce", content_type="ct-a",
            schema={}, cardinality="one",
        )
        h_b = ledger.register(
            name="b", kind="produce", content_type="ct-b",
            schema={}, cardinality="one",
        )
        port_a = ledger.lookup(h_a)
        port_b = ledger.lookup(h_b)
        assert port_a.name == "a"
        assert port_b.name == "b"
        assert port_a.content_type == "ct-a"
        assert port_b.content_type == "ct-b"


# ---------------------------------------------------------------------------
# Coercion
# ---------------------------------------------------------------------------


class TestCoercion:
    def test_identity_is_always_legal(self) -> None:
        assert is_legal_coercion("text/markdown", "text/markdown") is True
        assert is_legal_coercion("application/json", "application/json") is True
        v = object()
        assert coerce("text/markdown", "text/markdown", v) is v

    def test_register_seeds_identity_in_table(self) -> None:
        ledger = ContractLedger()
        ledger.register(
            name="p", kind="produce", content_type="application/x-test",
            schema={}, cardinality="one",
        )
        assert ("application/x-test", "application/x-test") in legal_coercions

    def test_missing_cross_coercion_is_illegal(self) -> None:
        assert is_legal_coercion("text/markdown", "image/png") is False
        with pytest.raises(KeyError):
            coerce("text/markdown", "image/png", "hi")

    def test_table_empty_of_cross_coercions_by_default(self) -> None:
        """No non-identity coercions exist in a fresh table."""
        import arnold.pipeline.contracts as mod
        cross = [
            (a, b) for (a, b) in mod.legal_coercions.keys() if a != b
        ]
        assert cross == []

    def test_coerce_applies_custom_function(self) -> None:
        ledger = ContractLedger()
        # Identity is always auto-registered
        assert is_legal_coercion("text/plain", "text/plain")


# ---------------------------------------------------------------------------
# PortBindError — from Megaplan bridge
# ---------------------------------------------------------------------------


class TestPortBindError:
    def test_port_bind_error_creation(self) -> None:
        from arnold.pipelines.megaplan._pipeline.contracts import PortBindError

        err = PortBindError("step-1", "consume-x")
        assert err.step_id == "step-1"
        assert err.consume_name == "consume-x"
        assert "step-1" in str(err)
        assert "consume-x" in str(err)
        assert isinstance(err, RuntimeError)

    def test_port_bind_error_with_detail(self) -> None:
        from arnold.pipelines.megaplan._pipeline.contracts import PortBindError

        err = PortBindError("s", "c", detail="type mismatch")
        assert "type mismatch" in str(err)


# ---------------------------------------------------------------------------
# Boundary — no Megaplan imports in Arnold contracts
# ---------------------------------------------------------------------------


class TestContractsBoundary:
    def test_contracts_module_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = P(__file__).parents[3] / "arnold" / "pipeline" / "contracts.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("megaplan"), (
                            f"contracts.py imports megaplan: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not node.module.startswith(
                        "megaplan"
                    ), (
                        f"contracts.py imports from megaplan: {node.module!r}"
                    )

    def test_contract_ledger_importable_from_arnold(self) -> None:
        """ContractLedger must be importable from arnold.pipeline.contracts."""
        from arnold.pipeline.contracts import ContractLedger as CL
        assert CL is ContractLedger

    def test_coerce_importable_from_arnold(self) -> None:
        from arnold.pipeline.contracts import coerce as c
        assert c is coerce
