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


MODELS = {
    'qwen_3_8b_fp8mixed': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors', sha256='abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6', hf_revision='23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83', size_bytes=8664848742, subdir='text_encoders'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('positive'), field='text', default=TEXT),
    'negative_prompt': InputSpec(node=ref('negative'), field='text', default=TEXT),
    'negative': InputSpec(node=ref('negative'), field='text', default=TEXT),
    'width': InputSpec(node=ref('primitiveint'), field='value', default=1024),
    'height': InputSpec(node=ref('primitiveint_2'), field='value', default=1024),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='Flux2-Klein',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Sampling
        ksamplerselect = KSamplerSelect(sampler_name='euler')

        # Loaders
        unetloader = UNETLoader(unet_name=MODEL_NAME)
        cliploader = CLIPLoader(clip_name=MODEL_NAME_2, type_='flux2')
        vaeloader = VAELoader(vae_name=MODEL_NAME_3)
        randomnoise = RandomNoise(noise_seed=DEFAULT_SEED)

        # Inputs
        primitiveint = raw_call('PrimitiveInt', '75:68', value=1024)
        primitiveint_2 = raw_call('PrimitiveInt', '75:69', value=1024)

        # Sampling
        flux2scheduler = Flux2Scheduler(height=primitiveint_2, width=primitiveint)

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

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

