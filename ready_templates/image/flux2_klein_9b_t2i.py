# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, EmptyFlux2LatentImage, Flux2Scheduler, KSamplerSelect, RandomNoise, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAELoader


DEFAULT_SEED = 653844576367526
GUIDE_STRENGTH = 5
MODEL_NAME = 'flux-2-klein-base-9b-fp8.safetensors'
MODEL_NAME_2 = 'qwen_3_8b_fp8mixed.safetensors'
MODEL_NAME_3 = 'full_encoder_small_decoder.safetensors'
TEXT = ''
WIDGET_1 = 'fixed'


MODELS = {
    'flux_2_klein_base_9b_fp8': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors', sha256='gated', hf_revision='gated', subdir='diffusion_models'),
    'qwen_3_8b_fp8mixed': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors', sha256='abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6', hf_revision='23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83', size_bytes=8664848742, subdir='text_encoders'),
    'full_encoder_small_decoder': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors', sha256='ea4273f02d1fafbf8e1d1c2cf6018ed8748652eb0bf34f2dd91171f16f15ab62', hf_revision='a3efc24f613ef42d9428af62fdbd6f5fd8856c4a', size_bytes=249519092, subdir='vae'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('negative'), field='text', default=TEXT),
}

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
    primitiveint = raw_call('PrimitiveInt', '68', widget_1=WIDGET_1, value=value)
    primitiveint_2 = raw_call('PrimitiveInt', '69', widget_1=WIDGET_1, value=value_1)
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=DEFAULT_SEED,
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

        # Sampling
        ksamplerselect = KSamplerSelect(sampler_name='euler')

        # Inputs
        primitiveint = raw_call('PrimitiveInt', '68', value=1024, widget_1=WIDGET_1)
        primitiveint_2 = raw_call('PrimitiveInt', '69', value=1024, widget_1=WIDGET_1)

        # Loaders
        unetloader = UNETLoader(unet_name=MODEL_NAME)
        cliploader = CLIPLoader(clip_name=MODEL_NAME_2, type_='flux2')
        vaeloader = VAELoader(vae_name=MODEL_NAME_3)

        randomnoise = RandomNoise(
            noise_seed=DEFAULT_SEED,
            control_after_generate='randomize',
        )

        # Sampling
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

        # Conditioning
        negative = CLIPTextEncode(text=TEXT, clip=cliploader)
        positive = CLIPTextEncode(text=TEXT, clip=cliploader)

        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH,
            model=unetloader,
            negative=negative,
            positive=positive,
        )

        # Sampling
        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=emptyflux2latentimage,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=flux2scheduler,
        )

        # Decode
        vaedecode = VAEDecode(samples=output, vae=vaeloader)

        # Outputs
        saveimage = SaveImage(filename_prefix='Flux2-Klein', images=vaedecode)

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

