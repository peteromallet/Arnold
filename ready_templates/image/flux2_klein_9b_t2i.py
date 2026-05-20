# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import SaveImage


MODELS = {
    'flux_2_klein_base_9b_fp8': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors', sha256='gated', hf_revision='gated', subdir='diffusion_models'),
    'qwen_3_8b_fp8mixed': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors', sha256='abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6', hf_revision='23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83', size_bytes=8664848742, subdir='text_encoders'),
    'full_encoder_small_decoder': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors', sha256='ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62', hf_revision='a3efc24f613ef42d9428af62fdbd6f5fd8856c4a', size_bytes=249519092, subdir='vae'),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    approach='official Flux.2 Klein 9B text-to-image safetensors workflow',
    provenance={'source_workflow': 'workflow_corpus/official/image/flux2_klein_9b_t2i.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        n_7b34ab90_36f9_45ba_a665_71d418f0df18 = raw_call(wf, '7b34ab90-36f9-45ba-a665-71d418f0df18', '75',
        )
        wf.metadata.setdefault('id_map', {})['n_7b34ab90_36f9_45ba_a665_71d418f0df18'] = n_7b34ab90_36f9_45ba_a665_71d418f0df18.node.id

        saveimage = SaveImage(
            _id='9',
            filename_prefix='Flux2-Klein',
            images=n_7b34ab90_36f9_45ba_a665_71d418f0df18.out(0),
        )
        wf.metadata.setdefault('id_map', {})['saveimage'] = saveimage.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

