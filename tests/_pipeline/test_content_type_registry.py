"""Unit tests for megaplan._pipeline.types content-type registry (M2/T1)."""

from __future__ import annotations

import pytest

from megaplan._pipeline.types import (
    CONTENT_TYPES,
    ContentTypeRegistry,
    Port,
    PortRef,
    RoutingKey,
    register_schema,
)


# ── Builtins present ─────────────────────────────────────────────────────


class TestBuiltinsPresent:
    """The seven builtin content types must be registered at import time."""

    BUILTIN_NAMES = frozenset(
        {
            "text/markdown",
            "image/png",
            "application/x-git-diff",
            "application/x-verdict+json",
            "application/x-routing-key+json",
            "application/x-fanout-results+json",
            "application/x-evaluand-record+json",
        }
    )

    def test_all_seven_builtins_registered(self) -> None:
        registered = set(CONTENT_TYPES.names())
        assert registered == self.BUILTIN_NAMES

    def test_each_builtin_is_queryable(self) -> None:
        for name in self.BUILTIN_NAMES:
            assert name in CONTENT_TYPES
            digest = CONTENT_TYPES.get(name)
            assert isinstance(digest, str)
            assert len(digest) == 64  # SHA-256 hex digest


# ── Duplicate registration raises ────────────────────────────────────────


class TestDuplicateRegisterRaises:
    def test_raises_value_error_on_duplicate(self) -> None:
        ct = ContentTypeRegistry()
        ct.register("text/plain", {"content_type": "text/plain"})
        with pytest.raises(ValueError, match="already registered"):
            ct.register("text/plain", {"content_type": "text/plain", "extra": True})

    def test_duplicate_on_builtin_registry_raises(self) -> None:
        with pytest.raises(ValueError, match="already registered"):
            CONTENT_TYPES.register("text/markdown", {"content_type": "text/markdown"})


# ── New name queryable ───────────────────────────────────────────────────


class TestNewNameQueryable:
    def test_register_then_query(self) -> None:
        ct = ContentTypeRegistry()
        digest = ct.register("application/pdf", {"content_type": "application/pdf"})
        assert "application/pdf" in ct
        assert ct.get("application/pdf") == digest
        assert "application/pdf" in ct.names()

    def test_names_includes_just_registered(self) -> None:
        ct = ContentTypeRegistry()
        assert ct.names() == ()
        ct.register("text/html", {"content_type": "text/html"})
        assert ct.names() == ("text/html",)


# ── Frozen dataclass smoke ───────────────────────────────────────────────


class TestFrozenDataclasses:
    def test_port_is_frozen(self) -> None:
        p = Port(name="result", content_type="text/markdown")
        with pytest.raises(Exception):
            p.name = "other"  # type: ignore[misc]

    def test_portref_is_frozen(self) -> None:
        pr = PortRef(port_name="result", content_type="text/markdown")
        with pytest.raises(Exception):
            pr.port_name = "other"  # type: ignore[misc]

    def test_routing_key_is_frozen(self) -> None:
        rk = RoutingKey(key="text/markdown")
        with pytest.raises(Exception):
            rk.key = "image/png"  # type: ignore[misc]


# ── register_schema determinism ──────────────────────────────────────────


class TestRegisterSchemaDeterminism:
    def test_deterministic_same_input(self) -> None:
        a = register_schema({"a": 1, "b": 2})
        b = register_schema({"b": 2, "a": 1})
        assert a == b

    def test_different_inputs_different_digest(self) -> None:
        a = register_schema({"a": 1})
        b = register_schema({"b": 1})
        assert a != b

    def test_hex_length(self) -> None:
        digest = register_schema({"k": "v"})
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)


# ── KeyError for unknown ─────────────────────────────────────────────────


class TestGetUnknownRaises:
    def test_get_unknown_raises_keyerror(self) -> None:
        ct = ContentTypeRegistry()
        with pytest.raises(KeyError, match="no content type named"):
            ct.get("nonexistent")
