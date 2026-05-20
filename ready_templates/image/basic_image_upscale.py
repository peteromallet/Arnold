# vibecomfy: manual
"""Core ComfyUI image upscale template for Reigh image-upscale parity.

Output: unknown.

Source:  ComfyUI core LoadImage -> ImageScaleBy -> SaveImage
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='basic_image_upscale',
    capability='image_upscale',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    provenance={'source_workflow': 'ComfyUI core LoadImage -> ImageScaleBy -> SaveImage', 'source_role': 'reigh_parity_manual_template', 'approach': 'Core ComfyUI lanczos ImageScaleBy; maps Reigh image-upscale parameters without external API calls.'},
    coverage_tier='production_parity_candidate',
    runtime_note='This preserves the task contract but is not FlashVSR/RealESRGAN model super-resolution.',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    wf = new_workflow(READY_METADATA, source_path=__file__)
    # ════ SAMPLING ════
    image = node(wf, "LoadImage", "1", image="image_upscale_input.png")
    # ════ IMAGE PREP ════
    upscaled = node(
        wf,
        "ImageScaleBy",
        "2",
        image=image.out('IMAGE'),
        upscale_method="lanczos",
        scale_by=2.0,
    )
    node(wf, "SaveImage", "3", filename_prefix="image-upscale", images=upscaled.out(0))

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='3',
        source_path=__file__,
    )
