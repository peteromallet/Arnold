from __future__ import annotations

import pytest

from vibecomfy.blocks import Handles, block, block_spec, registered_blocks
from vibecomfy.blocks.decode import vae as decode_vae
from vibecomfy.blocks.encoding import clip_vision as encode_clip_vision, text_pair
from vibecomfy.blocks.latent import HunyuanVideoShape, empty_hunyuan_video
from vibecomfy.blocks.loaders import LoaderNames, clip_vision as load_clip_vision, load_image, unet_clip_vae
from vibecomfy.blocks.save import VideoSaveSettings, image as save_image, video as save_video
from vibecomfy.blocks.sampling import KSamplerSettings, ksampler, model_sampling_sd3
from vibecomfy.blocks.subgraph import opaque, ref
from vibecomfy.blocks.video import VideoCreateSettings, create as create_video
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def test_block_decorator_registers_metadata() -> None:
    spec = block_spec(load_image)

    assert spec is not None
    assert spec.name == "vibecomfy.blocks.loaders.load_image"
    assert spec.module == "vibecomfy.blocks.loaders"
    assert "workflow" in spec.signature
    assert registered_blocks()[spec.name] is load_image


def test_block_decorator_requires_workflow_first_parameter() -> None:
    with pytest.raises(TypeError, match="workflow as its first parameter"):

        @block
        def missing_workflow(*, value: str) -> Handles:
            return Handles(value=value)


def test_registered_block_remains_callable() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    handles = registered_blocks()["vibecomfy.blocks.loaders.load_image"](
        workflow,
        image="example.png",
    )

    assert handles.image == "1"
    assert workflow.nodes["1"].metadata["block"] == "vibecomfy.blocks.loaders.load_image"


def test_loader_block_uses_grouped_names() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    handles = unet_clip_vae(
        workflow,
        names=LoaderNames(
            unet_name="unet.safetensors",
            clip_name="clip.safetensors",
            vae_name="vae.safetensors",
            clip_type="flux",
        ),
    )

    assert handles.model == "1"
    assert workflow.nodes["1"].widgets["widget_0"] == "unet.safetensors"
    assert workflow.nodes["2"].widgets["widget_1"] == "flux"
    assert workflow.nodes["3"].widgets["widget_0"] == "vae.safetensors"


def test_authoring_dsl_builds_compileable_text_to_image_chain() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    loaded = unet_clip_vae(
        workflow,
        names=LoaderNames(unet_name="unet.safetensors", clip_name="clip.safetensors", vae_name="vae.safetensors"),
    )
    encoded = text_pair(workflow, clip=loaded.clip, positive="a red cube", negative="blurry")
    sampled = ksampler(
        workflow,
        model=loaded.model,
        positive=encoded.positive,
        negative=encoded.negative,
        latent="99",
        settings=KSamplerSettings(seed=42, steps=5),
    )
    saved = save_image(workflow, images=sampled.samples, filename_prefix="blocks/out")

    api = workflow.compile()

    assert saved.image == "7"
    assert workflow.nodes["4"].metadata["block"] == "vibecomfy.blocks.encoding.text_pair"
    assert workflow.nodes["7"].metadata["block"] == "vibecomfy.blocks.save.image"
    # CLIPTextEncode is a committed widget alias class; widget_0 -> text at compile.
    assert api["4"]["inputs"] == {"text": "a red cube", "clip": ["2", 0]}
    assert api["5"]["inputs"] == {"text": "blurry", "clip": ["2", 0]}
    assert api["6"]["inputs"]["model"] == ["1", 0]
    assert api["6"]["inputs"]["positive"] == ["4", 0]
    assert api["6"]["inputs"]["negative"] == ["5", 0]
    assert api["6"]["inputs"]["latent_image"] == ["99", 0]
    assert api["6"]["inputs"]["widget_0"] == 42
    assert api["6"]["inputs"]["widget_2"] == 5
    assert api["7"]["class_type"] == "SaveImage"
    assert api["7"]["inputs"] == {"widget_0": "blocks/out", "images": ["6", 0]}


def test_ksampler_uses_grouped_settings() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    handles = ksampler(
        workflow,
        model="1",
        positive="2",
        negative="3",
        latent="4",
        settings=KSamplerSettings(seed=123, steps=12, cfg=4.5),
    )

    assert handles.samples == "1"
    assert workflow.nodes["1"].widgets["widget_0"] == 123
    assert workflow.nodes["1"].widgets["widget_2"] == 12
    assert workflow.nodes["1"].widgets["widget_3"] == 4.5


def test_latent_block_uses_grouped_shape() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    empty_hunyuan_video(workflow, shape=HunyuanVideoShape(width=320, height=192, length=9))

    assert workflow.nodes["1"].widgets == {
        "widget_0": 320,
        "widget_1": 192,
        "widget_2": 9,
        "widget_3": 1,
    }


def test_opaque_uses_explicit_widgets_inputs_and_links() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    source = workflow.add_node("Source")
    handles = opaque(
        workflow,
        class_type="CustomNode",
        widgets_by_name={"widget_0": "literal"},
        inputs={"text": "1.0"},
        links={"image": ref(source, slot=1)},
        outputs=("out", "preview"),
    )

    assert handles.out == "2.0"
    assert handles.preview == "2.1"
    assert workflow.nodes["2"].inputs["text"] == "1.0"
    assert workflow.nodes["2"].widgets["widget_0"] == "literal"
    assert workflow.compile()["2"]["inputs"]["image"] == ["1", 1]


def test_opaque_rejects_ambiguous_widget_sources() -> None:
    workflow = VibeWorkflow("blocks-test", WorkflowSource("blocks-test"))

    with pytest.raises(ValueError, match="either widgets_by_name or widget_values"):
        opaque(
            workflow,
            class_type="CustomNode",
            widgets_by_name={"widget_0": "literal"},
            widget_values=["literal"],
        )


def test_block_compile_smoke_widget_keys() -> None:
    workflow = VibeWorkflow("block-smoke", WorkflowSource("block-smoke"))

    loaded = unet_clip_vae(
        workflow,
        names=LoaderNames(
            unet_name="unet.safetensors",
            clip_name="clip.safetensors",
            vae_name="vae.safetensors",
            clip_type="wan",
        ),
    )
    vision = load_clip_vision(workflow, clip_name="clip_vision.safetensors")
    image = load_image(workflow, image="example.png")
    encoded = text_pair(workflow, clip=loaded.clip, positive="prompt", negative="negative")
    vision_encoded = encode_clip_vision(workflow, clip_vision=vision.clip_vision, image=image.image)
    latent = empty_hunyuan_video(workflow, shape=HunyuanVideoShape(width=320, height=192, length=9))
    sampled_model = model_sampling_sd3(workflow, model=loaded.model)
    sampled = ksampler(workflow, model=sampled_model.model, positive=encoded.positive, negative=encoded.negative, latent=latent.latent)
    decoded = decode_vae(workflow, samples=sampled.samples, vae=loaded.vae)
    video = create_video(workflow, images=decoded.images, settings=VideoCreateSettings(fps=12))
    save_image(workflow, images=decoded.images, filename_prefix="smoke/image")
    save_video(workflow, video=video.video, settings=VideoSaveSettings(filename_prefix="smoke/video"))

    api = workflow.compile("api")

    assert len(api) == 15
    assert api["1"]["inputs"].keys() == {"widget_0", "widget_1"}
    assert api["2"]["inputs"].keys() == {"widget_0", "widget_1", "widget_2"}
    assert api["4"]["class_type"] == "CLIPVisionLoader"
    # CLIPTextEncode is a committed widget alias class; widget_0 -> text at compile.
    assert api["6"]["inputs"]["text"] == "prompt"
    assert api["8"]["class_type"] == "CLIPVisionEncode"
    assert api["9"]["inputs"].keys() == {"widget_0", "widget_1", "widget_2", "widget_3"}
    assert api["14"]["class_type"] == "SaveImage"
    assert api["15"]["class_type"] == "SaveVideo"
