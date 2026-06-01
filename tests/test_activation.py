"""Tests for megaplan._core.activation (T18).

Covers:
- cross-process determinism of compute_activation_id
- tuple↔list stability for input_ports
- 7-char drift vs the canonical_sha256 prefixed helper
- Activation dataclass construction and is_ready semantics
- ACTIVATION_TRANSITIONED event constant exists in EventKind
"""

from __future__ import annotations

import hashlib
import subprocess
import sys

import pytest

from megaplan._core.activation import (
    Activation,
    LifecycleState,
    ReadinessRule,
    compute_activation_id,
)
from megaplan.observability.events import EventKind
from megaplan.store.snapshot import canonical_json_dumps, canonical_sha256


# ---------------------------------------------------------------------------
# compute_activation_id determinism
# ---------------------------------------------------------------------------

def test_compute_activation_id_is_deterministic():
    id1 = compute_activation_id("node_a", ["p1", "p2"], "pro")
    id2 = compute_activation_id("node_a", ["p1", "p2"], "pro")
    assert id1 == id2


def test_compute_activation_id_length():
    aid = compute_activation_id("node_a", ["p1"], "pro")
    assert len(aid) == 16


def test_compute_activation_id_is_hex():
    aid = compute_activation_id("node_a", ["p1"], "pro")
    int(aid, 16)  # raises ValueError if not valid hex


def test_compute_activation_id_cross_process():
    """id produced in a child process matches the id produced here."""
    script = (
        "from megaplan._core.activation import compute_activation_id;"
        "print(compute_activation_id('n', ['a', 'b'], 'default'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    child_id = result.stdout.strip()
    parent_id = compute_activation_id("n", ["a", "b"], "default")
    assert child_id == parent_id


# ---------------------------------------------------------------------------
# tuple ↔ list stability
# ---------------------------------------------------------------------------

def test_compute_activation_id_tuple_equals_list():
    id_list = compute_activation_id("node_x", ["port1", "port2"], "p")
    id_tuple = compute_activation_id("node_x", ("port1", "port2"), "p")
    assert id_list == id_tuple


def test_compute_activation_id_empty_ports_stable():
    id1 = compute_activation_id("node_x", [], "p")
    id2 = compute_activation_id("node_x", (), "p")
    assert id1 == id2


# ---------------------------------------------------------------------------
# 7-char drift from prefixed canonical_sha256
# ---------------------------------------------------------------------------

def test_activation_id_differs_from_prefixed_sha256_by_7_chars():
    """If someone mistakenly used canonical_sha256(...)[:16] they'd get the
    first 16 chars of "sha256:<hex>", which is "sha256:" (7 chars) + 9 hex
    chars.  The correct id is the first 16 hex chars of the raw digest.
    """
    payload = {"node": "n", "input_ports": ["a"], "profile": "p"}
    correct_id = compute_activation_id("n", ["a"], "p")
    wrong_id = canonical_sha256(payload)[:16]  # "sha256:" prefix shifts by 7

    # They must differ
    assert correct_id != wrong_id

    # The wrong id starts with the 7-char prefix "sha256:"
    assert wrong_id == "sha256:" + wrong_id[7:]
    assert len("sha256:") == 7

    # The correct id is pure hex (no prefix)
    int(correct_id, 16)  # does not raise

    # Confirm: raw hex[:16] == correct_id
    raw_hex = hashlib.sha256(
        canonical_json_dumps(payload).encode("utf-8")
    ).hexdigest()
    assert correct_id == raw_hex[:16]


# ---------------------------------------------------------------------------
# Activation dataclass
# ---------------------------------------------------------------------------

def test_activation_construction():
    aid = compute_activation_id("node_a", ["p1"], "default")
    act = Activation(
        id=aid,
        node="node_a",
        input_ports=frozenset(["p1"]),
        profile="default",
        readiness_rule=ReadinessRule.UPSTREAM_DONE,
    )
    assert act.id == aid
    assert act.node == "node_a"
    assert act.lifecycle is LifecycleState.PENDING


def test_activation_is_frozen():
    act = Activation(
        id="abc",
        node="n",
        input_ports=frozenset(),
        profile="p",
        readiness_rule=ReadinessRule.UPSTREAM_DONE,
    )
    with pytest.raises((AttributeError, TypeError)):
        act.node = "other"  # type: ignore[misc]


def test_is_ready_upstream_done_pending_returns_false():
    act = Activation(
        id="x",
        node="n",
        input_ports=frozenset(),
        profile="p",
        readiness_rule=ReadinessRule.UPSTREAM_DONE,
        lifecycle=LifecycleState.PENDING,
    )
    assert act.is_ready() is False


def test_is_ready_upstream_done_ready_returns_true():
    act = Activation(
        id="x",
        node="n",
        input_ports=frozenset(),
        profile="p",
        readiness_rule=ReadinessRule.UPSTREAM_DONE,
        lifecycle=LifecycleState.READY,
    )
    assert act.is_ready() is True


@pytest.mark.parametrize("rule", [
    ReadinessRule.MANUAL,
    ReadinessRule.SCHEDULED,
    ReadinessRule.EXTERNAL_EVENT,
])
def test_is_ready_raises_not_implemented_for_other_rules(rule):
    act = Activation(
        id="x",
        node="n",
        input_ports=frozenset(),
        profile="p",
        readiness_rule=rule,
        lifecycle=LifecycleState.READY,
    )
    with pytest.raises(NotImplementedError):
        act.is_ready()


# ---------------------------------------------------------------------------
# ACTIVATION_TRANSITIONED event
# ---------------------------------------------------------------------------

def test_activation_transitioned_event_exists():
    assert hasattr(EventKind, "ACTIVATION_TRANSITIONED")
    assert EventKind.ACTIVATION_TRANSITIONED == "activation_transitioned"


def test_activation_transitioned_in_all_event_kinds():
    from megaplan.observability.events import _ALL_EVENT_KINDS
    assert "activation_transitioned" in _ALL_EVENT_KINDS
