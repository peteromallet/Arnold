# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import LoadImage, SaveImage


MODELS = {
    'flux_2_klein_9b_fp8': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/main/flux-2-klein-9b-fp8.safetensors', sha256='gated', hf_revision='gated', subdir='diffusion_models'),
    'qwen_3_8b_fp8mixed': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors', sha256='abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6', hf_revision='23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83', size_bytes=8664848742, subdir='text_encoders'),
    'full_encoder_small_decoder': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors', sha256='ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62', hf_revision='a3efc24f613ef42d9428af62fdbd6f5fd8856c4a', size_bytes=249519092, subdir='vae'),
}

PUBLIC_INPUTS = {
    'image': InputSpec(node=ref('image'), field='image', default='bold_outfit_woman.jpeg'),
    'input_image': InputSpec(node=ref('image'), field='image', default='bold_outfit_woman.jpeg'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_edit',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    approach='official Flux.2 Klein 9B distilled image-edit workflow',
    provenance={'source_workflow': 'workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        image, mask = LoadImage(image='bold_outfit_woman.jpeg')
        image_load, mask_load = LoadImage(image='handbag_white.png')

        subgraph_7b34ab90 = raw_call('7b34ab90-36f9-45ba-a665-71d418f0df18', '75',
            image=image,
        )

        subgraph_65c22b29 = raw_call('65c22b29-59aa-496b-89c6-55a603658670', '92',
            image=image,
            image_1=image_load,
        )

        saveimage = SaveImage(
            filename_prefix='Flux2-Klein',
            images=subgraph_7b34ab90.out(0),
        )
        saveimage_2 = SaveImage(images=subgraph_65c22b29.out(0))

        return wf.finalize(PUBLIC_INPUTS, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

