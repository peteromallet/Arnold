# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, EmptyFlux2LatentImage, Flux2Scheduler, KSamplerSelect, RandomNoise, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAELoader


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

# === Subgraph functions ===

def text_to_image_flux2_klein_9b(
    *,
    value: int,
    value_1: int,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    text: str,
):
    """Text to Image (Flux.2 Klein 9B).

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in workflow_corpus/official/image/flux2_klein_9b_t2i.json.
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, EmptyFlux2LatentImage, CLIPTextEncodex2, PrimitiveIntx2, RandomNoise, UNETLoader, CLIPLoader, VAELoader.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    primitiveint = raw_call('PrimitiveInt', '68', widget_1='fixed', value=value)
    primitiveint_2 = raw_call('PrimitiveInt', '69', widget_1='fixed', value=value_1)
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=653844576367526,
        control_after_generate='randomize',
    )

    flux2scheduler = Flux2Scheduler(
        widget_1=1024,
        widget_2=1024,
        height=primitiveint_2,
        width=primitiveint,
    )

    emptyflux2latentimage = EmptyFlux2LatentImage(
        width=primitiveint,
        height=primitiveint_2,
    )
    negative = CLIPTextEncode(text='', clip=cliploader)
    positive = CLIPTextEncode(text=text, clip=cliploader)

    cfgguider = CFGGuider(
        cfg=5,
        model=unetloader,
        negative=negative,
        positive=positive,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=emptyflux2latentimage,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=flux2scheduler,
    )
    vaedecode = VAEDecode(samples=output, vae=vaeloader)

    return vaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        edited = text_to_image_flux2_klein_9b(
            value=1024,
            value_1=1024,
            unet_name='flux-2-klein-base-9b-fp8.safetensors',
            clip_name='qwen_3_8b_fp8mixed.safetensors',
            vae_name='full_encoder_small_decoder.safetensors',
            text='',
        )
        saveimage = SaveImage(filename_prefix='Flux2-Klein', images=edited)

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

