from __future__ import annotations

import inspect

from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def _workflow() -> VibeWorkflow:
    return VibeWorkflow("test/shims", WorkflowSource("test/shims", path="ready_templates/test.py"))


def test_generated_core_wrappers_are_importable_and_delegate() -> None:
    from vibecomfy.nodes.core import CLIPLoader, KSampler, UNETLoader

    wf = _workflow()
    unet = UNETLoader(wf, unet_name="model.safetensors", weight_dtype="default")
    sampler = KSampler(
        wf,
        model=unet,
        sampler_name="euler",
        scheduler="simple",
        positive="p",
        negative="n",
        latent_image="latent",
    )

    assert wf.nodes[unet.node.id].class_type == "UNETLoader"
    assert wf.nodes[sampler.node.id].class_type == "KSampler"
    assert any(edge.from_node == unet.node.id and edge.to_node == sampler.node.id and edge.to_input == "model" for edge in wf.edges)
    assert "Pack:" in (UNETLoader.__doc__ or "")
    assert "Returns:" in (UNETLoader.__doc__ or "")
    assert "type_" in inspect.signature(CLIPLoader).parameters


def test_generated_pack_modules_import_and_exclude_helper_nodes() -> None:
    import vibecomfy.nodes.controlnet_aux as controlnet_aux
    import vibecomfy.nodes.depthanythingv2 as depthanythingv2
    import vibecomfy.nodes.gguf as gguf
    import vibecomfy.nodes.kjnodes as kjnodes
    import vibecomfy.nodes.ltxvideo as ltxvideo
    import vibecomfy.nodes.qwen3tts as qwen3tts
    import vibecomfy.nodes.qwentts as qwentts
    import vibecomfy.nodes.rgthree as rgthree
    import vibecomfy.nodes.sam2 as sam2
    import vibecomfy.nodes.videohelpersuite as videohelpersuite
    import vibecomfy.nodes.wananimatepreprocess as wananimatepreprocess
    import vibecomfy.nodes.wanvideowrapper as wanvideowrapper
    from vibecomfy.nodes import UNETLoader

    assert UNETLoader.__name__ == "UNETLoader"
    for module in (
        controlnet_aux,
        depthanythingv2,
        gguf,
        kjnodes,
        ltxvideo,
        qwen3tts,
        qwentts,
        rgthree,
        sam2,
        videohelpersuite,
        wananimatepreprocess,
        wanvideowrapper,
    ):
        assert isinstance(module.__all__, list)
    assert "SetNode" not in kjnodes.__all__
    assert "GetNode" not in kjnodes.__all__
    assert "Note" not in kjnodes.__all__
    assert "MarkdownNote" not in kjnodes.__all__
    assert "Reroute" not in kjnodes.__all__
    assert "PrimitiveNode" not in kjnodes.__all__
