from __future__ import annotations

import pytest

from vibecomfy import Image, Video, audio, edit, image, video


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


def test_deferred_edit_and_audio_ops_raise_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="load_workflow_any"):
        image.edit("dummy.png", "hi")
    with pytest.raises(NotImplementedError, match="load_workflow_any"):
        edit.qwen("dummy.png", "hi")
    with pytest.raises(NotImplementedError, match="no audio template registered"):
        audio.t2a("hi")


def test_flux_gguf_t2i_route_is_deferred() -> None:
    with pytest.raises(KeyError):
        image.t2i("hello", model="flux2_klein_9b_gguf")
