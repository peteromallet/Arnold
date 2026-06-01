"""Unit tests for megaplan._pipeline.taint."""

from __future__ import annotations

from megaplan._pipeline.taint import port_value_hash, propagate_taint
from megaplan._pipeline.types import Port, PortRef


def test_identical_value_different_taint_produces_different_hash():
    p_clean = Port(name="out", content_type="text/markdown", taint=frozenset())
    p_secret = Port(
        name="out", content_type="text/markdown", taint=frozenset({"secret"})
    )
    value = {"a": 1, "b": [1, 2, 3]}
    assert port_value_hash(p_clean, value) != port_value_hash(p_secret, value)


def test_same_taint_same_value_is_stable():
    p = Port(name="out", content_type="text/markdown", taint=frozenset({"pii"}))
    assert port_value_hash(p, {"x": 1}) == port_value_hash(p, {"x": 1})


def test_taint_set_order_irrelevant():
    p1 = Port(name="o", content_type="text/markdown", taint=frozenset({"a", "b"}))
    p2 = Port(name="o", content_type="text/markdown", taint=frozenset({"b", "a"}))
    assert port_value_hash(p1, "v") == port_value_hash(p2, "v")


def test_propagate_taint_unions_consumed_taints():
    produced = (
        Port(name="o1", content_type="text/markdown", taint=frozenset({"a"})),
        Port(name="o2", content_type="image/png", taint=frozenset()),
    )
    consumed = (
        PortRef(port_name="in1", content_type="text/markdown"),
        PortRef(port_name="in2", content_type="text/markdown"),
    )
    # PortRef carries no taint of its own; emulate consumed-port taints via Port objects:
    consumed_ports = (
        Port(name="in1", content_type="text/markdown", taint=frozenset({"secret"})),
        Port(name="in2", content_type="text/markdown", taint=frozenset({"pii"})),
    )
    out = propagate_taint(produced, consumed_ports)
    assert out[0].taint == frozenset({"a", "secret", "pii"})
    assert out[1].taint == frozenset({"secret", "pii"})


def test_propagate_taint_returns_new_port_instances():
    produced = (Port(name="o", content_type="text/markdown", taint=frozenset({"a"})),)
    consumed = (Port(name="i", content_type="text/markdown", taint=frozenset({"b"})),)
    out = propagate_taint(produced, consumed)
    assert out[0] is not produced[0]
    # Original untouched
    assert produced[0].taint == frozenset({"a"})
    assert out[0].taint == frozenset({"a", "b"})


def test_propagate_taint_empty_consumed_yields_equal_taint_but_new_instance():
    produced = (Port(name="o", content_type="text/markdown", taint=frozenset({"x"})),)
    out = propagate_taint(produced, ())
    assert out[0].taint == frozenset({"x"})
    assert out[0] is not produced[0]
