from __future__ import annotations

import warnings

import pytest

from vibecomfy import Handle, VibeWorkflow, WorkflowSource
from vibecomfy.blocks import Handles


def test_handle_string_equality_and_hash() -> None:
    handle = Handle("12", 0)

    assert str(handle) == "12.0"
    assert handle == "12.0"
    assert handle == "12"
    assert handle == Handle("12", "0")
    assert hash(handle) == hash(Handle("12", "0"))


def test_handles_coerces_raw_string_once_per_source_location() -> None:
    from vibecomfy.blocks import _RAW_HANDLE_WARNING_SITES

    _RAW_HANDLE_WARNING_SITES.clear()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        first = Handles({"x": "12.0"}); second = Handles({"x": "12.0"})

    assert isinstance(first["x"], Handle)
    assert isinstance(second["x"], Handle)
    assert str(first["x"]) == "12.0"
    assert [item.category for item in caught].count(DeprecationWarning) == 1


def test_public_handle_import_path() -> None:
    from vibecomfy import Handle as PublicHandle

    assert PublicHandle is Handle


def test_workflow_node_out_compile_and_connect_with_handle() -> None:
    workflow = VibeWorkflow("handle-test", WorkflowSource("handle-test"))

    clip = workflow.node("CLIPTextEncode", text="hello")
    conditioning = clip.out(0)
    consumer = workflow.node("PreviewImage")
    workflow.connect(conditioning, f"{consumer.id}.images")

    assert isinstance(conditioning, Handle)
    api = workflow.compile("api")
    assert api[clip.id]["inputs"]["text"] == "hello"
    assert api[consumer.id]["inputs"]["images"] == [clip.id, 0]


def test_named_output_requires_mp6_schema_integration() -> None:
    workflow = VibeWorkflow("handle-test", WorkflowSource("handle-test"))

    with pytest.raises(NotImplementedError, match="MP-6"):
        workflow.node("CLIPTextEncode", text="hello").out("CONDITIONING")


def test_run_until_requires_mp6_output_type() -> None:
    workflow = VibeWorkflow("handle-test", WorkflowSource("handle-test"))
    handle = workflow.node("CLIPTextEncode", text="hello").out(0)

    with pytest.raises(NotImplementedError, match="MP-6 schema integration"):
        workflow.run_until(handle)
