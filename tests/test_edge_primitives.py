from __future__ import annotations

from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


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
