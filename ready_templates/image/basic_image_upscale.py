# vibecomfy: manual
"""Core ComfyUI image upscale template for Reigh image-upscale parity."""
from __future__ import annotations

from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


READY_METADATA = {
    "model_assets": [],
    "unbound_inputs": {
        "image": "1.image",
        "scale_factor": "2.scale_by",
    },
    "ready_template": "image/basic_image_upscale",
    "workflow_template": "basic_image_upscale",
    "capability": "image_upscale",
    "source_role": "reigh_parity_manual_template",
    "source_workflow": "ComfyUI core LoadImage -> ImageScaleBy -> SaveImage",
    "coverage_tier": "production_parity_candidate",
    "approach": "Core ComfyUI lanczos ImageScaleBy; maps Reigh image-upscale parameters without external API calls.",
    "runtime_note": "This preserves the task contract but is not FlashVSR/RealESRGAN model super-resolution.",
}

READY_REQUIREMENTS = {"models": [], "custom_nodes": []}


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(id=READY_METADATA["ready_template"], path=__file__, source_type="ready_template"),
    )
    image = _node(wf, "LoadImage", "1", image="image_upscale_input.png")
    upscaled = _node(
        wf,
        "ImageScaleBy",
        "2",
        image=image.out(0),
        upscale_method="lanczos",
        scale_by=2.0,
    )
    _node(wf, "SaveImage", "3", filename_prefix="image-upscale", images=upscaled.out(0))

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, **kwargs):
    builder = wf.node(class_type, **kwargs)
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
