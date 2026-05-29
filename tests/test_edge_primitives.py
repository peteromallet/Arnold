from __future__ import annotations

import pytest

from vibecomfy.handles import Handle
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _make_workflow() -> VibeWorkflow:
    return VibeWorkflow("edge-test", WorkflowSource("edge-test"))


def test_disconnect_removes_matching_edge_and_returns_bool() -> None:
    workflow = _make_workflow()
    workflow.nodes["A"] = VibeNode("A", "SourceNode")
    workflow.nodes["B"] = VibeNode("B", "SinkNode")
    workflow.connect("A.0", "B.in")

    assert workflow.disconnect("B.in") is True
    assert workflow.edges == []
    assert workflow.disconnect("B.in") is False


def test_connect_bare_string_source_defaults_to_slot_zero() -> None:
    workflow = _make_workflow()
    workflow.nodes["A"] = VibeNode("A", "SourceNode")
    workflow.nodes["B"] = VibeNode("B", "SinkNode")

    workflow.connect("A", "B.in")

    assert workflow.edges == [VibeEdge("A", "0", "B", "in")]
    assert workflow.compile()["B"]["inputs"]["in"] == ["A", 0]


def test_connect_handle_source_keeps_explicit_slot() -> None:
    workflow = _make_workflow()
    workflow.nodes["A"] = VibeNode("A", "SourceNode")
    workflow.nodes["B"] = VibeNode("B", "SinkNode")

    workflow.connect(Handle(node_id="A", output_slot=3), "B.in")

    assert workflow.edges == [VibeEdge("A", "3", "B", "in")]
    assert workflow.compile()["B"]["inputs"]["in"] == ["A", 3]


def test_connect_requires_explicit_destination_field() -> None:
    workflow = _make_workflow()
    workflow.nodes["A"] = VibeNode("A", "SourceNode")
    workflow.nodes["B"] = VibeNode("B", "SinkNode")

    with pytest.raises(ValueError, match="connect: malformed target ref 'B'"):
        workflow.connect("A", "B")


def test_replace_edge_redirects_target_input() -> None:
    workflow = _make_workflow()
    workflow.nodes["A"] = VibeNode("A", "SourceNode")
    workflow.nodes["B"] = VibeNode("B", "MiddleNode")
    workflow.nodes["C"] = VibeNode("C", "SinkNode")

    workflow.connect("A.0", "B.in")
    workflow.connect("B.out", "C.in")

    workflow.replace_edge("C.in", "A.0")

    api = workflow.compile()
    assert api["C"]["inputs"]["in"] == ["A", 0]
    # The original A -> B edge should remain untouched.
    assert api["B"]["inputs"]["in"] == ["A", 0]


def test_replace_edge_bare_string_source_defaults_to_slot_zero() -> None:
    workflow = _make_workflow()
    workflow.nodes["A"] = VibeNode("A", "SourceNode")
    workflow.nodes["B"] = VibeNode("B", "SinkNode")
    workflow.nodes["C"] = VibeNode("C", "AltSourceNode")

    workflow.connect("A.1", "B.in")
    workflow.replace_edge("B.in", "C")

    assert workflow.compile()["B"]["inputs"]["in"] == ["C", 0]


def test_replace_edge_handle_source_keeps_explicit_slot() -> None:
    workflow = _make_workflow()
    workflow.nodes["A"] = VibeNode("A", "SourceNode")
    workflow.nodes["B"] = VibeNode("B", "SinkNode")
    workflow.nodes["C"] = VibeNode("C", "AltSourceNode")

    workflow.connect("A.1", "B.in")
    workflow.replace_edge("B.in", Handle(node_id="C", output_slot=4))

    assert workflow.compile()["B"]["inputs"]["in"] == ["C", 4]


@pytest.mark.parametrize(
    ("operation", "args", "message"),
    [
        ("connect", ("", "B.in"), "connect: source ref must not be empty"),
        ("connect", (123, "B.in"), "connect: source ref must be a Handle or string, got int"),
        ("connect", ("A.", "B.in"), "connect: malformed source ref 'A.'"),
        ("connect", (".0", "B.in"), "connect: malformed source ref '.0'"),
        ("connect", ("A.0", "B"), "connect: malformed target ref 'B'"),
        ("connect", ("A.0", ""), "connect: target ref must not be empty"),
        ("connect", ("A.0", ".in"), "connect: malformed target ref '.in'"),
        ("disconnect", ("",), "disconnect: target ref must not be empty"),
        ("disconnect", ("B",), "disconnect: malformed target ref 'B'"),
        ("replace_edge", ("B", "A.0"), "replace_edge: malformed target ref 'B'"),
        ("replace_edge", ("", "A.0"), "replace_edge: target ref must not be empty"),
        ("replace_edge", ("B.in", ""), "replace_edge: source ref must not be empty"),
        ("replace_edge", ("B.in", "A."), "replace_edge: malformed source ref 'A.'"),
        ("replace_edge", ("B.in", ".0"), "replace_edge: malformed source ref '.0'"),
    ],
)
def test_edge_ref_parsing_is_loud_for_malformed_refs(
    operation: str,
    args: tuple[str, ...],
    message: str,
) -> None:
    workflow = _make_workflow()
    workflow.nodes["A"] = VibeNode("A", "SourceNode")
    workflow.nodes["B"] = VibeNode("B", "SinkNode")

    method = getattr(workflow, operation)
    with pytest.raises(ValueError, match=message):
        method(*args)


def test_connect_allows_non_numeric_source_node_ids() -> None:
    workflow = _make_workflow()
    workflow.nodes["source-node"] = VibeNode("source-node", "SourceNode")
    workflow.nodes["sink-node"] = VibeNode("sink-node", "SinkNode")

    workflow.connect("source-node", "sink-node.in")

    assert workflow.edges == [VibeEdge("source-node", "0", "sink-node", "in")]
    assert workflow.compile()["sink-node"]["inputs"]["in"] == ["source-node", 0]


def test_next_node_id_uses_lowest_unused_positive_numeric_id() -> None:
    workflow = _make_workflow()
    workflow.nodes["2"] = VibeNode("2", "NodeTwo")
    workflow.nodes["4"] = VibeNode("4", "NodeFour")
    workflow.nodes["-1"] = VibeNode("-1", "NegativeNode")
    workflow.nodes["abc"] = VibeNode("abc", "TextNode")
    workflow.nodes["0"] = VibeNode("0", "ZeroNode")

    assert workflow._next_node_id() == "1"

    workflow.nodes["1"] = VibeNode("1", "NodeOne")
    assert workflow._next_node_id() == "3"


def test_add_node_defaults_to_one_when_workflow_has_no_positive_numeric_ids() -> None:
    workflow = _make_workflow()
    workflow.nodes["alpha"] = VibeNode("alpha", "ExistingNode")
    workflow.nodes["0"] = VibeNode("0", "ZeroNode")
    workflow.nodes["-7"] = VibeNode("-7", "NegativeNode")

    created = workflow.add_node("AutoNode")

    assert created.id == "1"
    assert workflow._next_node_id() == "2"


def test_add_node_reuses_lowest_deleted_positive_numeric_id() -> None:
    workflow = _make_workflow()
    workflow.nodes["1"] = VibeNode("1", "NodeOne")
    workflow.nodes["2"] = VibeNode("2", "NodeTwo")
    workflow.nodes["4"] = VibeNode("4", "NodeFour")

    workflow.remove_node("2")
    created = workflow.add_node("GapFillNode")

    assert created.id == "2"
    assert workflow._next_node_id() == "3"


def test_add_node_ignores_non_numeric_ids_when_allocating_default_id() -> None:
    workflow = _make_workflow()
    workflow.nodes["1"] = VibeNode("1", "NodeOne")
    workflow.nodes["beta"] = VibeNode("beta", "NamedNode")

    created = workflow.add_node("AutoNode")

    assert created.id == "2"


def test_add_node_preserves_explicit_non_numeric_id() -> None:
    workflow = _make_workflow()

    created = workflow.add_node("NamedNode", _id="custom-node")

    assert created.id == "custom-node"
    assert workflow.nodes["custom-node"].class_type == "NamedNode"


def test_add_node_preserves_explicit_numeric_id() -> None:
    workflow = _make_workflow()
    workflow.nodes["1"] = VibeNode("1", "NodeOne")

    created = workflow.add_node("ManualNode", _id="7")

    assert created.id == "7"
    assert workflow._next_node_id() == "2"


def test_round_trip_splice_simulates_controlnet() -> None:
    workflow = _make_workflow()
    workflow.nodes["text"] = VibeNode("text", "CLIPTextEncode")
    workflow.nodes["sampler"] = VibeNode("sampler", "KSampler")
    workflow.connect("text.0", "sampler.positive")

    # Splice cn_apply between text and sampler.positive.
    workflow.nodes["cn_apply"] = VibeNode("cn_apply", "ControlNetApplyAdvanced")
    workflow.connect("text.0", "cn_apply.positive")
    workflow.replace_edge("sampler.positive", "cn_apply.0")

    api = workflow.compile()
    assert api["cn_apply"]["inputs"]["positive"] == ["text", 0]
    assert api["sampler"]["inputs"]["positive"] == ["cn_apply", 0]
