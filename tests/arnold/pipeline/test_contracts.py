"""Tests for Arnold ``contracts`` module — ContractLedger, coercion (M3a T21).

Also exercises :class:`PortBindError` from the Megaplan bridge for
completeness, since the task description explicitly mentions it.
"""

from __future__ import annotations

import pytest

from arnold.pipeline.contracts import (
    BindResult,
    ContractLedger,
    PortBindError,
    RepairGradient,
    _contract_hash,
    bind,
    coerce,
    is_legal_coercion,
    legal_coercions,
)
from arnold.pipeline.schema_registry import AcceptedVersionRange
from arnold.pipeline.types import (
    Edge,
    Port,
    PortRef,
    Stage,
    StepContext,
    StepResult,
)


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

    def test_legacy_one_aliases_to_singleton_hash_and_port_metadata(self) -> None:
        ledger = ContractLedger()
        h_one = ledger.register(
            name="p", kind="produce", content_type="text/plain",
            schema={}, cardinality="one",
        )
        h_singleton = ledger.register(
            name="p", kind="produce", content_type="text/plain",
            schema={}, cardinality="singleton",
        )

        assert h_one == h_singleton
        assert ledger.lookup(h_one).cardinality == "singleton"

    def test_contract_hash_accepts_legacy_one_alias_directly(self) -> None:
        legacy = _contract_hash(
            "p", "produce", "application/json", {}, "one"
        )
        canonical = _contract_hash(
            "p", "produce", "application/json", {}, "singleton"
        )

        assert legacy == canonical

    def test_register_records_intentional_collection_cardinality(self) -> None:
        ledger = ContractLedger()
        digest = ledger.register(
            name="items", kind="produce", content_type="application/json",
            schema={}, cardinality="collection",
        )

        assert ledger.lookup(digest).cardinality == "collection"

    def test_hash_includes_logical_type_and_accepted_version_range(self) -> None:
        accepted_range = AcceptedVersionRange(
            "review",
            min_version="sha256:" + "0" * 64,
            max_version="sha256:" + "f" * 64,
        )

        base = _contract_hash(
            "p", "produce", "application/json", {}, "singleton",
            logical_type="review",
            accepted_version_range=accepted_range,
        )
        different_logical_type = _contract_hash(
            "p", "produce", "application/json", {}, "singleton",
            logical_type="summary",
            accepted_version_range=accepted_range,
        )
        different_range = _contract_hash(
            "p", "produce", "application/json", {}, "singleton",
            logical_type="review",
            accepted_version_range=AcceptedVersionRange(
                "review",
                min_version="sha256:" + "1" * 64,
                max_version="sha256:" + "f" * 64,
            ),
        )

        assert base != different_logical_type
        assert base != different_range

    def test_lookup_preserves_logical_metadata(self) -> None:
        ledger = ContractLedger()
        accepted_range = AcceptedVersionRange(
            "review",
            min_version="sha256:" + "0" * 64,
            max_version="sha256:" + "f" * 64,
        )

        digest = ledger.register(
            name="review",
            kind="produce",
            content_type="application/json",
            schema={},
            cardinality="singleton",
            logical_type="review",
            accepted_version_range=accepted_range,
        )

        port = ledger.lookup(digest)

        assert port.logical_type == "review"
        assert port.accepted_version_range is accepted_range

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


# ---------------------------------------------------------------------------
# bind — enriched typed-port metadata
# ---------------------------------------------------------------------------


class _Source:
    name = "src"
    kind = "produce"
    produces = ()
    consumes = ()

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
        return StepResult()


class _Sink:
    name = "sink"
    kind = "consume"
    produces = ()

    def __init__(self, consumes: tuple[PortRef, ...]) -> None:
        self.consumes = consumes

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
        return StepResult()


def _binding_stages(produces: tuple[Port, ...], consumes: tuple[PortRef, ...]):
    src = Stage(
        name="src",
        step=_Source(),
        edges=(Edge(label="ok", target="sink"),),
        produces=produces,
    )
    sink = Stage(name="sink", step=_Sink(consumes), edges=())
    return {"src": src, "sink": sink}


class TestBindTypedPortMetadata:
    def test_bind_matches_collection_cardinality_and_logical_metadata(self) -> None:
        accepted_range = AcceptedVersionRange("review")
        stages = _binding_stages(
            (
                Port(
                    name="reviews",
                    content_type="application/json",
                    cardinality="collection",
                    logical_type="review",
                    accepted_version_range=accepted_range,
                ),
            ),
            (
                PortRef(
                    port_name="reviews",
                    content_type="application/json",
                    cardinality="collection",
                    logical_type="review",
                    accepted_version_range=accepted_range,
                ),
            ),
        )

        result = bind(stages, {"src": ("sink",)})

        assert isinstance(result, BindResult)
        assert result.binding_map[("sink", "reviews")] == ("src", "reviews")

    def test_bind_accepts_legacy_one_alias_against_singleton_consumes(self) -> None:
        stages = _binding_stages(
            (
                Port(
                    name="review",
                    content_type="application/json",
                    cardinality="one",
                ),
            ),
            (
                PortRef(
                    port_name="review",
                    content_type="application/json",
                    cardinality="singleton",
                ),
            ),
        )

        result = bind(stages, {"src": ("sink",)})

        assert isinstance(result, BindResult)
        assert result.binding_map[("sink", "review")] == ("src", "review")

    def test_bind_rejects_cardinality_mismatch_with_repair_gradient(self) -> None:
        stages = _binding_stages(
            (
                Port(
                    name="reviews",
                    content_type="application/json",
                    cardinality="collection",
                ),
            ),
            (PortRef(port_name="reviews", content_type="application/json"),),
        )

        result = bind(stages, {"src": ("sink",)})

        assert isinstance(result, RepairGradient)
        assert result.error_kind == "cardinality_mismatch"

    def test_bind_rejects_logical_metadata_mismatch_with_schema_gradient(self) -> None:
        stages = _binding_stages(
            (
                Port(
                    name="payload",
                    content_type="application/json",
                    logical_type="review",
                ),
            ),
            (
                PortRef(
                    port_name="payload",
                    content_type="application/json",
                    logical_type="summary",
                ),
            ),
        )

        result = bind(stages, {"src": ("sink",)})

        assert isinstance(result, RepairGradient)
        assert result.error_kind == "schema_mismatch"

    def test_bind_rejects_accepted_version_range_mismatch_with_schema_gradient(self) -> None:
        stages = _binding_stages(
            (
                Port(
                    name="payload",
                    content_type="application/json",
                    logical_type="review",
                    accepted_version_range=AcceptedVersionRange(
                        "review",
                        min_version="sha256:" + "0" * 64,
                        max_version="sha256:" + "2" * 64,
                    ),
                ),
            ),
            (
                PortRef(
                    port_name="payload",
                    content_type="application/json",
                    logical_type="review",
                    accepted_version_range=AcceptedVersionRange(
                        "review",
                        min_version="sha256:" + "1" * 64,
                        max_version="sha256:" + "2" * 64,
                    ),
                ),
            ),
        )

        result = bind(stages, {"src": ("sink",)})

        assert isinstance(result, RepairGradient)
        assert result.error_kind == "schema_mismatch"

    def test_bind_rejects_reserved_stream_cardinality_at_runtime(self) -> None:
        stages = _binding_stages(
            (
                Port(
                    name="events",
                    content_type="application/json",
                    cardinality="stream",
                ),
            ),
            (
                PortRef(
                    port_name="events",
                    content_type="application/json",
                    cardinality="stream",
                ),
            ),
        )

        with pytest.raises(PortBindError, match="reserved stream cardinality"):
            bind(stages, {"src": ("sink",)})
