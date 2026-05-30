"""Tests for vibecomfy.security.provenance — S4 capability fence."""

from __future__ import annotations

import pytest

from vibecomfy.security import provenance
from vibecomfy.security.provenance import PROVENANCE_KEY
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _node(**meta) -> VibeNode:
    return VibeNode(id="n1", class_type="CLIPTextEncode", metadata=dict(meta))


def _wf(node: VibeNode) -> VibeWorkflow:
    wf = VibeWorkflow(id="t", source=WorkflowSource(id="t"))
    wf.nodes[node.id] = node
    return wf


# --- read() fail-closed ----------------------------------------------------


def test_read_missing_key_returns_untrusted_source():
    node = _node()
    assert provenance.read(node) == "untrusted_source"


def test_read_none_value_returns_untrusted_source():
    node = _node(provenance=None)
    assert provenance.read(node) == "untrusted_source"


def test_read_unknown_value_returns_untrusted_source():
    node = _node(provenance="bogus")
    assert provenance.read(node) == "untrusted_source"


def test_read_no_metadata_attr_returns_untrusted_source():
    class Bare:
        pass

    assert provenance.read(Bare()) == "untrusted_source"


# --- round-trip set/read ---------------------------------------------------


@pytest.mark.parametrize(
    "value", ["untrusted_source", "agent_authored", "user_confirmed"]
)
def test_tag_then_read_roundtrip(value):
    node = _node()
    provenance.tag(node, value)
    assert node.metadata[PROVENANCE_KEY] == value
    assert provenance.read(node) == value


def test_tag_rejects_invalid_value():
    node = _node()
    with pytest.raises(ValueError):
        provenance.tag(node, "fully_trusted")  # type: ignore[arg-type]


# --- confirm() promotion + idempotency ------------------------------------


def test_confirm_promotes_untrusted_to_user_confirmed():
    node = _node(provenance="untrusted_source")
    provenance.confirm(node)
    assert provenance.read(node) == "user_confirmed"


def test_confirm_idempotent_on_user_confirmed():
    node = _node(provenance="user_confirmed")
    provenance.confirm(node)
    assert provenance.read(node) == "user_confirmed"


def test_confirm_idempotent_on_agent_authored():
    node = _node(provenance="agent_authored")
    provenance.confirm(node)
    assert provenance.read(node) == "agent_authored"


def test_confirm_promotes_missing_key():
    """Fresh node with no provenance reads as untrusted_source — confirm promotes it."""
    node = _node()
    provenance.confirm(node)
    assert provenance.read(node) == "user_confirmed"


def test_confirm_never_raises_on_missing_metadata():
    class Bare:
        pass

    provenance.confirm(Bare())  # must not raise


# --- fresh-node read default -----------------------------------------------


def test_fresh_vibenode_reads_untrusted_source():
    """A freshly constructed VibeNode has no provenance metadata — fail-closed."""
    node = VibeNode(id="x", class_type="CLIPTextEncode")
    assert provenance.read(node) == "untrusted_source"
    assert node.provenance == "untrusted_source"


# --- VibeWorkflow.confirm_node + VibeNode.provenance property -------------


def test_vibenode_provenance_property_reads_through():
    node = _node(provenance="agent_authored")
    assert node.provenance == "agent_authored"


def test_vibeworkflow_confirm_node_promotes():
    node = _node(provenance="untrusted_source")
    wf = _wf(node)
    result = wf.confirm_node("n1")
    assert result is wf
    assert wf.nodes["n1"].provenance == "user_confirmed"


def test_vibeworkflow_confirm_node_idempotent_on_trusted():
    node = _node(provenance="user_confirmed")
    wf = _wf(node)
    wf.confirm_node("n1")
    assert wf.nodes["n1"].provenance == "user_confirmed"


def test_vibeworkflow_confirm_node_unknown_raises_keyerror():
    wf = _wf(_node(provenance="untrusted_source"))
    with pytest.raises(KeyError):
        wf.confirm_node("missing")
