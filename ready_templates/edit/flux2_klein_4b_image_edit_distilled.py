# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, ConditioningZeroOut, EmptyFlux2LatentImage, Flux2Scheduler, GetImageSize, ImageScaleToTotalPixels, KSamplerSelect, LoadImage, RandomNoise, ReferenceLatent, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


DEFAULT_SEED = 43301611940728
GUIDE_STRENGTH = 1
MODEL_NAME = 'flux-2-klein-4b-fp8.safetensors'
MODEL_NAME_2 = 'qwen_3_4b.safetensors'
MODEL_NAME_3 = 'flux2-vae.safetensors'


MODELS = {
    'flux_2_klein_4b_fp8': ModelAsset(url='https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors', sha256='97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6', hf_revision='5b4408e59397a4a37ccb46afe426d8ed86379441', size_bytes=4070624520, subdir='diffusion_models'),
    'qwen_3_4b': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', sha256='6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a', hf_revision='2f862278568d3f0a83167a16e5f11094da6dee72', size_bytes=8044982048, subdir='text_encoders'),
    'flux2_vae': ModelAsset(url='https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors', sha256='d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5', hf_revision='03d6521e6f6a47396b3f951cbea50f7e6c2f482e', size_bytes=336213556, subdir='vae'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default='Change the bag color to blue.'),
    'image': InputSpec(node=ref('image'), field='image', default='handbag_white.png'),
    'input_image': InputSpec(node=ref('image'), field='image', default='handbag_white.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_edit',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='Flux2-Klein',
    requirements={'custom_nodes': ['ComfyUI-KJNodes']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}},
    provenance={'source_workflow': 'workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json'},
)

# === Subgraph functions ===

def image_edit_flux2_klein_4b_distilled(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    text: str,
    image,
):
    """Image Edit (Flux.2 Klein 4B Distilled) - single-image variant.

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json.
    Inner nodes: KSamplerSelect, UNETLoader, CLIPLoader, VAELoader, EmptyFlux2LatentImage, ImageScaleToTotalPixels, Flux2Scheduler, CLIPTextEncode, ConditioningZeroOut, ReferenceLatentx2, GetImageSize, VAEEncode, SamplerCustomAdvanced, VAEDecode, RandomNoise, CFGGuider.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=43301611940728,
        control_after_generate='randomize',
    )

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
        image=image,
    )

    cliptextencode = CLIPTextEncode(text=text, clip=cliploader)
    width, height, batch_size = GetImageSize(image=imagescaletototalpixels)
    vaeencode = VAEEncode(pixels=imagescaletototalpixels, vae=vaeloader)

    flux2scheduler = Flux2Scheduler(
        steps=4,
        widget_1=1024,
        widget_2=1024,
        height=height,
        width=width,
    )

    emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)
    conditioningzeroout = ConditioningZeroOut(conditioning=cliptextencode)
    referencelatent_2 = ReferenceLatent(conditioning=cliptextencode, latent=vaeencode)

    referencelatent = ReferenceLatent(
        conditioning=conditioningzeroout,
        latent=vaeencode,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=unetloader,
        negative=referencelatent,
        positive=referencelatent_2,
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


def reference_conditioning(
    *,
    conditioning,
    conditioning_1,
    pixels,
    vae,
):
    """Reference Conditioning - single-image variant.

    Materialized from subgraph 27eacb9f-0da2-421d-a0bf-b4b4e5fe5709 in workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json.
    Inner nodes: ReferenceLatentx2, VAEEncode.
    """

    vaeencode = VAEEncode(pixels=pixels, vae=vae)
    referencelatent = ReferenceLatent(conditioning=conditioning_1, latent=vaeencode)
    referencelatent_2 = ReferenceLatent(conditioning=conditioning, latent=vaeencode)

    return referencelatent_2, referencelatent


def reference_conditioning_93041a64(
    *,
    conditioning,
    conditioning_1,
    pixels,
    vae,
):
    """Reference Conditioning - single-image variant.

    Materialized from subgraph 93041a64-452a-477a-9447-40330b7c1136 in workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json.
    Inner nodes: ReferenceLatentx2, VAEEncode.
    """

    vaeencode = VAEEncode(pixels=pixels, vae=vae)
    referencelatent = ReferenceLatent(conditioning=conditioning_1, latent=vaeencode)
    referencelatent_2 = ReferenceLatent(conditioning=conditioning, latent=vaeencode)

    return referencelatent_2, referencelatent


def image_edit_flux2_klein_4b_distilled_dual(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    text: str,
    image,
    image_1,
):
    """Image Edit (Flux.2 Klein 4B Distilled) - two-image variant.

    Materialized from subgraph 65c22b29-59aa-496b-89c6-55a603658670 in workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json.
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, CLIPLoader, CLIPTextEncode, VAELoader, ImageScaleToTotalPixelsx2, 27eacb9f-0da2-421d-a0bf-b4b4e5fe5709, 93041a64-452a-477a-9447-40330b7c1136, ConditioningZeroOut, EmptyFlux2LatentImage, GetImageSize.
    """

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
        image=image_1,
    )

    ksamplerselect = KSamplerSelect(sampler_name='euler')

    randomnoise = RandomNoise(
        noise_seed=786795143695419,
        control_after_generate='randomize',
    )

    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    imagescaletototalpixels_2 = ImageScaleToTotalPixels(
        upscale_method='nearest-exact',
        image=image,
    )

    cliptextencode = CLIPTextEncode(text=text, clip=cliploader)
    width, height, batch_size = GetImageSize(image=imagescaletototalpixels_2)
    conditioningzeroout = ConditioningZeroOut(conditioning=cliptextencode)

    flux2scheduler = Flux2Scheduler(
        steps=4,
        widget_1=1024,
        widget_2=1024,
        height=height,
        width=width,
    )

    emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)
    conditioning, conditioning_1 = reference_conditioning(
        conditioning=cliptextencode,
        conditioning_1=conditioningzeroout,
        pixels=imagescaletototalpixels_2,
        vae=vaeloader,
    )
    conditioning_2, conditioning_1_2 = reference_conditioning_93041a64(
        conditioning=conditioning,
        conditioning_1=conditioning_1,
        pixels=imagescaletototalpixels,
        vae=vaeloader,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=unetloader,
        negative=conditioning_1_2,
        positive=conditioning_2,
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

        # Loaders
        unetloader = UNETLoader(unet_name=MODEL_NAME)
        cliploader = CLIPLoader(clip_name=MODEL_NAME_2, type_='flux2')
        vaeloader = VAELoader(vae_name=MODEL_NAME_3)
        randomnoise = RandomNoise(noise_seed=DEFAULT_SEED)

        # Inputs
        image, mask = LoadImage(image='handbag_white.png')
        image_load, mask_load = LoadImage(image='comfy_logo_blue.png')

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text='Change the bag color to blue.',
            clip=cliploader,
        )

        imagescaletototalpixels = ImageScaleToTotalPixels(
            upscale_method='nearest-exact',
            image=image,
        )

        conditioningzeroout = ConditioningZeroOut(conditioning=cliptextencode)
        width, height, batch_size = GetImageSize(image=imagescaletototalpixels)
        vaeencode = VAEEncode(pixels=imagescaletototalpixels, vae=vaeloader)

        # Sampling
        flux2scheduler = Flux2Scheduler(steps=4, height=height, width=width)
        emptyflux2latentimage = EmptyFlux2LatentImage(width=width, height=height)

        referencelatent = ReferenceLatent(
            conditioning=conditioningzeroout,
            latent=vaeencode,
        )

        referencelatent_2 = ReferenceLatent(
            conditioning=cliptextencode,
            latent=vaeencode,
        )

        # Conditioning
        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH,
            model=unetloader,
            negative=referencelatent,
            positive=referencelatent_2,
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

