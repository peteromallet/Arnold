# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Image editing with Flux 2 Klein 9B.

Output: unknown.

Source:  workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {
    'flux_2_klein_9b_fp8': ModelAsset(
        filename='flux-2-klein-9b-fp8.safetensors',
        url='https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/main/flux-2-klein-9b-fp8.safetensors',
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

# ported from workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json (sha256: e6e03c7158fd6e0799fe6b1d26e50e85ce748ac5664a807911daa55935844d1c)
READY_METADATA = ReadyMetadata.build(
    template_id='flux2_klein_9b_image_edit_distilled',
    capability='image_edit',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    provenance={'approach': 'official Flux.2 Klein 9B distilled image-edit workflow', 'source_workflow': 'workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json', 'source_role': 'materialized_ready_python_template'},
    coverage_tier='supplemental',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    input_image_76 = node(wf, 'LoadImage', '76',
        image='bold_outfit_woman.jpeg',
)
    input_image_2 = node(wf, 'LoadImage', '121',
        image='handbag_white.png',
)
    n_7b34ab90_36f9_45ba_a665_71d418f0df18 = node(wf, '7b34ab90-36f9-45ba-a665-71d418f0df18', '75',
        image=input_image_76.out('IMAGE'),
    )
    n_65c22b29_59aa_496b_89c6_55a603658670 = node(wf, '65c22b29-59aa-496b-89c6-55a603658670', '92',
        image=input_image_76.out('IMAGE'),
        image_1=input_image_2.out('IMAGE'),
    )
    # ════ OUTPUT ════
    image_output_9 = node(wf, 'SaveImage', '9',
        filename_prefix='Flux2-Klein',
        images=n_7b34ab90_36f9_45ba_a665_71d418f0df18.out(0),
    )
    image_output_2 = node(wf, 'SaveImage', '122',
        filename_prefix='ComfyUI',
        images=n_65c22b29_59aa_496b_89c6_55a603658670.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

