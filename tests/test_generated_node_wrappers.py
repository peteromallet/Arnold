from __future__ import annotations

import pytest

from vibecomfy.nodes.core import EmptyImage, SaveImage
from vibecomfy.templates import new_workflow


def test_generated_wrapper_uses_context_workflow_and_preserves_source_id() -> None:
    wf = new_workflow({"ready_template": "image/example"}, source_path="ready_templates/image/example.py")

    with wf:
        image = EmptyImage(_id="7", width=64, height=64)

    assert image.node.id == "7"
    assert wf.nodes["7"].class_type == "EmptyImage"
    assert wf.nodes["7"].inputs["width"] == 64
    assert wf.metadata["id_map"]["7"] == "7"


def test_generated_wrapper_accepts_explicit_workflow_outside_context() -> None:
    wf = new_workflow({"ready_template": "image/example"}, source_path="ready_templates/image/example.py")

    image = EmptyImage(wf, _id="8", width=32, height=32)

    assert image.node.id == "8"
    assert wf.nodes["8"].class_type == "EmptyImage"
    assert wf.nodes["8"].inputs["height"] == 32


def test_generated_wrapper_rejects_multiple_positional_workflows() -> None:
    first = new_workflow({"ready_template": "image/first"}, source_path="ready_templates/image/first.py")
    second = new_workflow({"ready_template": "image/second"}, source_path="ready_templates/image/second.py")

    with pytest.raises(TypeError, match="EmptyImage\\(\\) takes at most 1 positional argument, got 2"):
        EmptyImage(first, second, width=16, height=16)


def test_generated_wrapper_requires_context_when_workflow_omitted() -> None:
    with pytest.raises(RuntimeError, match="No active workflow"):
        EmptyImage(width=16, height=16)


def test_generated_wrapper_preserves_extras_and_pass_raw() -> None:
    wf = new_workflow({"ready_template": "image/example"}, source_path="ready_templates/image/example.py")

    image = EmptyImage(wf, _id="9", width=16, height=16)
    saved = SaveImage(wf, _id="10", images=image, filename_prefix="out", custom_extra="kept", pass_raw=True)

    assert saved.node.id == "10"
    assert wf.nodes["10"].inputs["custom_extra"] == "kept"
    assert wf.nodes["10"].inputs["images"] is image
