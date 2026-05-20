# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Text-to-image generation with Flux 2 Klein Base 9B.

Output: unknown.

Source:  workflow_corpus/official/image/flux2_klein_9b_t2i.json
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {
    'flux_2_klein_base_9b_fp8': ModelAsset(
        filename='flux-2-klein-base-9b-fp8.safetensors',
        url='https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors',
        subdir='diffusion_models',
    ),
    'qwen_3_8b_fp8mixed': ModelAsset(
        filename='qwen_3_8b_fp8mixed.safetensors',
        url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors',
        subdir='text_encoders',
    ),
    'full_encoder_small_decoder': ModelAsset(
        filename='full_encoder_small_decoder.safetensors',
        url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors',
        subdir='vae',
    ),
}

PUBLIC_INPUTS = {}

# ported from workflow_corpus/official/image/flux2_klein_9b_t2i.json (sha256: ac7513756f3bf72b49292a334c48315aa40e6c0e4ff8dd152773bb55dac17fff)
READY_METADATA = ReadyMetadata.build(
    template_id='flux2_klein_9b_t2i',
    capability='text_to_image',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    provenance={'source_workflow': 'workflow_corpus/official/image/flux2_klein_9b_t2i.json', 'approach': 'official Flux.2 Klein 9B text-to-image safetensors workflow', 'source_role': 'materialized_ready_python_template'},
    coverage_tier='supplemental',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    n_7b34ab90_36f9_45ba_a665_71d418f0df18 = node(wf, '7b34ab90-36f9-45ba-a665-71d418f0df18', '75')
    # ════ OUTPUT ════
    image_output = node(wf, 'SaveImage', '9',
        filename_prefix='Flux2-Klein',
        images=n_7b34ab90_36f9_45ba_a665_71d418f0df18.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

