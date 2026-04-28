from __future__ import annotations

import pytest

from vibecomfy import Image, Video, image, video


def test_image_t2i_returns_lazy_image_artifact_with_prompt_input() -> None:
    artifact = image.t2i("hello")

    assert isinstance(artifact, Image)
    workflow = artifact.preview_workflow()
    api = workflow.compile("api")

    assert any(node["class_type"] == "SaveImage" for node in api.values())
    assert workflow.inputs["prompt"].value == "hello"


def test_video_t2v_returns_lazy_video_artifact_with_save_video_output() -> None:
    artifact = video.t2v("hello")

    assert isinstance(artifact, Video)
    workflow = artifact.preview_workflow()

    assert workflow.outputs[0].output_type == "SaveVideo"


def test_flux_gguf_t2i_route_is_deferred() -> None:
    with pytest.raises(KeyError):
        image.t2i("hello", model="flux2_klein_9b_gguf")
