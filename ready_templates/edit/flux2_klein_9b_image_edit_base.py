# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import LoadImage, SaveImage


MODELS = {
    'flux_2_klein_base_9b_fp8': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors', sha256='gated', hf_revision='gated', subdir='diffusion_models'),
    'qwen_3_8b_fp8mixed': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors', sha256='abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6', hf_revision='23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83', size_bytes=8664848742, subdir='text_encoders'),
    'full_encoder_small_decoder': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors', sha256='ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62', hf_revision='a3efc24f613ef42d9428af62fdbd6f5fd8856c4a', size_bytes=249519092, subdir='vae'),
}

PUBLIC_INPUTS = {
    'image': InputSpec(node=ref('loadimage'), field='image', default='car_interior_white.jpeg'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='car_interior_white.jpeg'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_edit',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    approach='official Flux.2 Klein 9B base image-edit workflow',
    provenance={'source_workflow': 'workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadimage = LoadImage(
            _id='76',
            image='car_interior_white.jpeg',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        loadimage_2 = LoadImage(
            _id='81',
            image='comfy_logo_blue.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_2'] = loadimage_2.node.id

        n_7b34ab90_36f9_45ba_a665_71d418f0df18 = raw_call(wf, '7b34ab90-36f9-45ba-a665-71d418f0df18', '75',
            image=loadimage.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['n_7b34ab90_36f9_45ba_a665_71d418f0df18'] = n_7b34ab90_36f9_45ba_a665_71d418f0df18.node.id

        n_65c22b29_59aa_496b_89c6_55a603658670 = raw_call(wf, '65c22b29-59aa-496b-89c6-55a603658670', '92',
            image=loadimage.out('IMAGE'),
            image_1=loadimage_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['n_65c22b29_59aa_496b_89c6_55a603658670'] = n_65c22b29_59aa_496b_89c6_55a603658670.node.id

        saveimage = SaveImage(
            _id='9',
            filename_prefix='Flux2-Klein-4b-base',
            images=n_7b34ab90_36f9_45ba_a665_71d418f0df18.out(0),
        )
        wf.metadata.setdefault('id_map', {})['saveimage'] = saveimage.node.id

        saveimage_2 = SaveImage(
            _id='94',
            filename_prefix='Flux2-Klein-4b-base',
            images=n_65c22b29_59aa_496b_89c6_55a603658670.out(0),
        )
        wf.metadata.setdefault('id_map', {})['saveimage_2'] = saveimage_2.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein-4b-base')

