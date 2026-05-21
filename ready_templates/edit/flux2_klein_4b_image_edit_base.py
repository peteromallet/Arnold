# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import LoadImage, SaveImage


MODELS = {
    'flux_2_klein_base_4b_fp8': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4b-fp8/resolve/main/flux-2-klein-base-4b-fp8.safetensors', sha256='44bab3a86fe98b85d21dd2a4729ebdc3ae51fb8a39f76e457e18c724219e6840', hf_revision='103db268c10d4d3921101b46057671f9ac460da6', size_bytes=4089498488, subdir='diffusion_models'),
    'qwen_3_4b': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', sha256='6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a', hf_revision='2f862278568d3f0a83167a16e5f11094da6dee72', size_bytes=8044982048, subdir='text_encoders'),
    'full_encoder_small_decoder': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors', sha256='ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62', hf_revision='a3efc24f613ef42d9428af62fdbd6f5fd8856c4a', size_bytes=249519092, subdir='vae'),
}

PUBLIC_INPUTS = {
    'image': InputSpec(node=ref('image'), field='image', default='robed_women.png'),
    'input_image': InputSpec(node=ref('image'), field='image', default='robed_women.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_edit',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    approach='official Flux.2 Klein 4B base image-edit workflow',
    provenance={'source_workflow': 'workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        image, mask = LoadImage(image='robed_women.png')
        image_load, mask_load = LoadImage(image='pink_tone_chair.png')

        subgraph_7b34ab90 = raw_call('7b34ab90-36f9-45ba-a665-71d418f0df18', '75',
            image=image,
        )

        subgraph_65c22b29 = raw_call('65c22b29-59aa-496b-89c6-55a603658670', '92',
            image=image,
            image_1=image_load,
        )

        saveimage = SaveImage(
            filename_prefix='Flux2-Klein-4b-base',
            images=subgraph_7b34ab90.out(0),
        )

        saveimage_2 = SaveImage(
            filename_prefix='Flux2-Klein-4b-base',
            images=subgraph_65c22b29.out(0),
        )

        return wf.finalize(PUBLIC_INPUTS, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein-4b-base')

