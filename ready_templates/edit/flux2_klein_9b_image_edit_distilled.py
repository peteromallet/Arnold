# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, ConditioningZeroOut, EmptyFlux2LatentImage, Flux2Scheduler, GetImageSize, ImageScaleToTotalPixels, KSamplerSelect, LoadImage, RandomNoise, ReferenceLatent, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='76', field='image', default='bold_outfit_woman.jpeg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json', 'source_id': 'flux2_klein_9b_image_edit_distilled', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json', 'output_mode': 'ready_template', 'ready_id': 'edit/flux2_klein_9b_image_edit_distilled'},
)

# === Subgraph functions ===

def image_edit_flux2_klein_9b_distilled(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    image,
):
    """Image Edit (Flux.2 Klein 9B Distilled) - single-image variant.

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json.
    # vibecomfy source hash: sha256:0b7a93c4ebae73fabb58354865af446dc745929583f3fafe5b72376fa5da1df4
    Inner nodes: KSamplerSelect, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, CLIPLoader, EmptyFlux2LatentImage, CFGGuider, Flux2Scheduler, GetImageSize, ReferenceLatentx2, ImageScaleToTotalPixels, VAELoader, CLIPTextEncode, ConditioningZeroOut, VAEEncode.
    """

    ksamplerselect = KSamplerSelect(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:61',
        sampler_name='euler',
    )

    unetloader = UNETLoader(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:70',
        unet_name=unet_name,
    )

    cliploader = CLIPLoader(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:71',
        type_='flux2',
        clip_name=clip_name,
    )

    vaeloader = VAELoader(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:72',
        vae_name=vae_name,
    )

    randomnoise = RandomNoise(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:73',
        noise_seed=26416064315367,
        control_after_generate='randomize',
    )

    imagescaletototalpixels = ImageScaleToTotalPixels(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:80',
        upscale_method='nearest-exact',
        image=image,
    )

    cliptextencode = CLIPTextEncode(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:74',
        text=prompt,
        clip=cliploader,
    )

    width, height, _ = GetImageSize(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:99',
        image=imagescaletototalpixels,
    )

    vaeencode = VAEEncode(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:124',
        pixels=imagescaletototalpixels,
        vae=vaeloader,
    )

    flux2scheduler = Flux2Scheduler(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:62',
        steps=4,
        width=width,
        height=height,
    )

    emptyflux2latentimage = EmptyFlux2LatentImage(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:66',
        width=width,
        height=height,
    )

    conditioningzeroout = ConditioningZeroOut(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:82',
        conditioning=cliptextencode,
    )

    referencelatent_2 = ReferenceLatent(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:125',
        conditioning=cliptextencode,
        latent=vaeencode,
    )

    referencelatent = ReferenceLatent(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:123',
        conditioning=conditioningzeroout,
        latent=vaeencode,
    )

    cfgguider = CFGGuider(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:63',
        cfg=1,
        model=unetloader,
        negative=referencelatent,
        positive=referencelatent_2,
    )

    output, _ = SamplerCustomAdvanced(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:64',
        guider=cfgguider,
        latent_image=emptyflux2latentimage,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=flux2scheduler,
    )

    vaedecode = VAEDecode(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:65',
        samples=output,
        vae=vaeloader,
    )

    return vaedecode


def image_edit_flux2_klein_9b_distilled_dual(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    reference_image1,
    reference_image2,
):
    """Image Edit (Flux.2 Klein 9B Distilled) - two-image variant.

    Materialized from subgraph 65c22b29-59aa-496b-89c6-55a603658670 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json.
    # vibecomfy source hash: sha256:e3e88715b6dc65b2dda2734513ba272914a1375e81ddf783dc057743d63912c3
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, CLIPLoader, CLIPTextEncode, ConditioningZeroOut, EmptyFlux2LatentImage, GetImageSize, VAEEncodex2, ReferenceLatentx4, VAELoader, ImageScaleToTotalPixelsx2.
    """

    imagescaletototalpixels = ImageScaleToTotalPixels(
        _id='65c22b29-59aa-496b-89c6-55a603658670:85',
        upscale_method='lanczos',
        image=reference_image2,
    )

    ksamplerselect = KSamplerSelect(
        _id='65c22b29-59aa-496b-89c6-55a603658670:101',
        sampler_name='euler',
    )

    randomnoise = RandomNoise(
        _id='65c22b29-59aa-496b-89c6-55a603658670:106',
        noise_seed=583453753589969,
        control_after_generate='randomize',
    )

    unetloader = UNETLoader(
        _id='65c22b29-59aa-496b-89c6-55a603658670:107',
        unet_name=unet_name,
    )

    cliploader = CLIPLoader(
        _id='65c22b29-59aa-496b-89c6-55a603658670:108',
        type_='flux2',
        clip_name=clip_name,
    )

    vaeloader = VAELoader(
        _id='65c22b29-59aa-496b-89c6-55a603658670:110',
        vae_name=vae_name,
    )

    imagescaletototalpixels_2 = ImageScaleToTotalPixels(
        _id='65c22b29-59aa-496b-89c6-55a603658670:111',
        upscale_method='lanczos',
        image=reference_image1,
    )

    cliptextencode = CLIPTextEncode(
        _id='65c22b29-59aa-496b-89c6-55a603658670:109',
        text=prompt,
        clip=cliploader,
    )

    width, height, _ = GetImageSize(
        _id='65c22b29-59aa-496b-89c6-55a603658670:114',
        image=imagescaletototalpixels_2,
    )

    vaeencode = VAEEncode(
        _id='65c22b29-59aa-496b-89c6-55a603658670:127',
        pixels=imagescaletototalpixels_2,
        vae=vaeloader,
    )

    vaeencode_2 = VAEEncode(
        _id='65c22b29-59aa-496b-89c6-55a603658670:130',
        pixels=imagescaletototalpixels,
        vae=vaeloader,
    )

    conditioningzeroout = ConditioningZeroOut(
        _id='65c22b29-59aa-496b-89c6-55a603658670:86',
        conditioning=cliptextencode,
    )

    flux2scheduler = Flux2Scheduler(
        _id='65c22b29-59aa-496b-89c6-55a603658670:102',
        steps=4,
        width=width,
        height=height,
    )

    emptyflux2latentimage = EmptyFlux2LatentImage(
        _id='65c22b29-59aa-496b-89c6-55a603658670:113',
        width=width,
        height=height,
    )

    referencelatent_2 = ReferenceLatent(
        _id='65c22b29-59aa-496b-89c6-55a603658670:128',
        conditioning=cliptextencode,
        latent=vaeencode,
    )

    referencelatent = ReferenceLatent(
        _id='65c22b29-59aa-496b-89c6-55a603658670:126',
        conditioning=conditioningzeroout,
        latent=vaeencode,
    )

    referencelatent_4 = ReferenceLatent(
        _id='65c22b29-59aa-496b-89c6-55a603658670:131',
        conditioning=referencelatent_2,
        latent=vaeencode_2,
    )

    referencelatent_3 = ReferenceLatent(
        _id='65c22b29-59aa-496b-89c6-55a603658670:129',
        conditioning=referencelatent,
        latent=vaeencode_2,
    )

    cfgguider = CFGGuider(
        _id='65c22b29-59aa-496b-89c6-55a603658670:103',
        cfg=1,
        model=unetloader,
        negative=referencelatent_3,
        positive=referencelatent_4,
    )

    output, _ = SamplerCustomAdvanced(
        _id='65c22b29-59aa-496b-89c6-55a603658670:104',
        guider=cfgguider,
        latent_image=emptyflux2latentimage,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=flux2scheduler,
    )

    vaedecode = VAEDecode(
        _id='65c22b29-59aa-496b-89c6-55a603658670:105',
        samples=output,
        vae=vaeloader,
    )

    return vaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    image, _ = LoadImage(image='bold_outfit_woman.jpeg')
    image_load, _ = LoadImage(image='handbag_white.png')
    edited = image_edit_flux2_klein_9b_distilled(
        unet_name='flux-2-klein-9b-fp8.safetensors',
        clip_name=image,
        vae_name='full_encoder_small_decoder.safetensors',
        prompt='Replace the background with a quiet coastal cliff at overcast sunset. Remove all buildings and streets. Add wind-shaped grass and a distant ocean horizon. Keep the subject’s pose and framing unchanged.',
        image=image,
    )
    edited_dual = image_edit_flux2_klein_9b_distilled_dual(
        unet_name='flux-2-klein-9b-fp8.safetensors',
        clip_name=image,
        vae_name=image_load,
        prompt='Let this character hold the bag with both hands',
        reference_image1=image,
        reference_image2=image_load,
    )
    saveimage = SaveImage(filename_prefix='Flux2-Klein', images=edited)
    saveimage_2 = SaveImage(images=edited_dual)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

