# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, EmptyFlux2LatentImage, Flux2Scheduler, GetImageSize, ImageScaleToTotalPixels, KSamplerSelect, LoadImage, RandomNoise, ReferenceLatent, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='76', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image',
    inputs=PUBLIC_INPUT_METADATA,
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json', 'source_id': 'flux2_klein_4b_image_edit_base', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json', 'output_mode': 'ready_template', 'ready_id': 'edit/flux2_klein_4b_image_edit_base'},
)

# === Subgraph functions ===

def image_edit_flux2_klein_4b(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    image,
):
    """Image Edit (Flux.2 Klein 4B) - single-image variant.

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json.
    # vibecomfy source hash: sha256:93485ad599c8953cdc6bfb19a765b319305d8f31faef9dea11b21cf8d0d61953
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, CLIPLoader, CLIPTextEncodex2, VAELoader, EmptyFlux2LatentImage, ImageScaleToTotalPixels, GetImageSize, ReferenceLatentx2, VAEEncode.
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
        noise_seed=1111443136920027,
        control_after_generate='randomize',
    )

    imagescaletototalpixels = ImageScaleToTotalPixels(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:80',
        upscale_method='nearest-exact',
        image=image,
    )

    negative = CLIPTextEncode(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:67',
        text='',
        clip=cliploader,
    )

    cliptextencode = CLIPTextEncode(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:74',
        text=prompt,
        clip=cliploader,
    )

    width, height, _ = GetImageSize(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:100',
        image=imagescaletototalpixels,
    )

    vaeencode = VAEEncode(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:123',
        pixels=imagescaletototalpixels,
        vae=vaeloader,
    )

    flux2scheduler = Flux2Scheduler(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:62',
        width=width,
        height=height,
    )

    emptyflux2latentimage = EmptyFlux2LatentImage(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:66',
        width=width,
        height=height,
    )

    referencelatent = ReferenceLatent(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:122',
        conditioning=negative,
        latent=vaeencode,
    )

    referencelatent_2 = ReferenceLatent(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:124',
        conditioning=cliptextencode,
        latent=vaeencode,
    )

    cfgguider = CFGGuider(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:63',
        cfg=5,
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


def image_edit_flux2_klein_9b(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    reference_image1,
    reference_image2,
):
    """Image Edit (Flux.2 Klein 9B) - two-image variant.

    Materialized from subgraph 65c22b29-59aa-496b-89c6-55a603658670 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json.
    # vibecomfy source hash: sha256:9865b964bc214fb9bbe16fb67ea685334baa13e88d122a7abc41e3eee75af6a3
    Inner nodes: KSamplerSelect, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, VAELoader, GetImageSize, EmptyFlux2LatentImage, ImageScaleToTotalPixelsx2, CLIPLoader, CLIPTextEncodex2, CFGGuider, Flux2Scheduler, ReferenceLatentx4, VAEEncodex2.
    """

    imagescaletototalpixels = ImageScaleToTotalPixels(
        _id='65c22b29-59aa-496b-89c6-55a603658670:85',
        upscale_method='nearest-exact',
        image=reference_image2,
    )

    ksamplerselect = KSamplerSelect(
        _id='65c22b29-59aa-496b-89c6-55a603658670:102',
        sampler_name='euler',
    )

    randomnoise = RandomNoise(
        _id='65c22b29-59aa-496b-89c6-55a603658670:105',
        noise_seed=133932424540642,
        control_after_generate='randomize',
    )

    unetloader = UNETLoader(
        _id='65c22b29-59aa-496b-89c6-55a603658670:106',
        unet_name=unet_name,
    )

    vaeloader = VAELoader(
        _id='65c22b29-59aa-496b-89c6-55a603658670:107',
        vae_name=vae_name,
    )

    imagescaletototalpixels_2 = ImageScaleToTotalPixels(
        _id='65c22b29-59aa-496b-89c6-55a603658670:110',
        upscale_method='nearest-exact',
        image=reference_image1,
    )

    cliploader = CLIPLoader(
        _id='65c22b29-59aa-496b-89c6-55a603658670:111',
        type_='flux2',
        clip_name=clip_name,
    )

    negative = CLIPTextEncode(
        _id='65c22b29-59aa-496b-89c6-55a603658670:87',
        text='',
        clip=cliploader,
    )

    width, height, _ = GetImageSize(
        _id='65c22b29-59aa-496b-89c6-55a603658670:108',
        image=imagescaletototalpixels_2,
    )

    cliptextencode = CLIPTextEncode(
        _id='65c22b29-59aa-496b-89c6-55a603658670:113',
        text=prompt,
        clip=cliploader,
    )

    vaeencode = VAEEncode(
        _id='65c22b29-59aa-496b-89c6-55a603658670:126',
        pixels=imagescaletototalpixels_2,
        vae=vaeloader,
    )

    vaeencode_2 = VAEEncode(
        _id='65c22b29-59aa-496b-89c6-55a603658670:129',
        pixels=imagescaletototalpixels,
        vae=vaeloader,
    )

    emptyflux2latentimage = EmptyFlux2LatentImage(
        _id='65c22b29-59aa-496b-89c6-55a603658670:109',
        width=width,
        height=height,
    )

    flux2scheduler = Flux2Scheduler(
        _id='65c22b29-59aa-496b-89c6-55a603658670:115',
        width=width,
        height=height,
    )

    referencelatent = ReferenceLatent(
        _id='65c22b29-59aa-496b-89c6-55a603658670:125',
        conditioning=negative,
        latent=vaeencode,
    )

    referencelatent_2 = ReferenceLatent(
        _id='65c22b29-59aa-496b-89c6-55a603658670:127',
        conditioning=cliptextencode,
        latent=vaeencode,
    )

    referencelatent_3 = ReferenceLatent(
        _id='65c22b29-59aa-496b-89c6-55a603658670:128',
        conditioning=referencelatent,
        latent=vaeencode_2,
    )

    referencelatent_4 = ReferenceLatent(
        _id='65c22b29-59aa-496b-89c6-55a603658670:130',
        conditioning=referencelatent_2,
        latent=vaeencode_2,
    )

    cfgguider = CFGGuider(
        _id='65c22b29-59aa-496b-89c6-55a603658670:114',
        cfg=5,
        model=unetloader,
        negative=referencelatent_3,
        positive=referencelatent_4,
    )

    output, _ = SamplerCustomAdvanced(
        _id='65c22b29-59aa-496b-89c6-55a603658670:103',
        guider=cfgguider,
        latent_image=emptyflux2latentimage,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=flux2scheduler,
    )

    vaedecode = VAEDecode(
        _id='65c22b29-59aa-496b-89c6-55a603658670:104',
        samples=output,
        vae=vaeloader,
    )

    return vaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    image, _ = LoadImage(image='robed_women.png')
    image_load, _ = LoadImage(image='pink_tone_chair.png')
    edited = image_edit_flux2_klein_4b(
        unet_name='flux-2-klein-base-4b-fp8.safetensors',
        clip_name=image,
        vae_name='full_encoder_small_decoder.safetensors',
        prompt="Change the background to a cozy, softly lit interior space with warm beige tones, soft natural window light filtering through, and a relaxed, intimate atmosphere similar to the original image's mood. Keep the person in the exact same position, scale, and pose. Maintain identical camera angle, framing, and perspective. The lighting should be soft, even, and warm - not harsh or bright. Only replace the room environment, preserving all facial features, hairstyle, expression, clothing, and pose exactly as they are.",
        image=image,
    )
    edited_2 = image_edit_flux2_klein_9b(
        unet_name='flux-2-klein-base-4b-fp8.safetensors',
        clip_name=image,
        vae_name=image_load,
        prompt="A stylish young woman with dark skin wearing a plush deep emerald green bathrobe, light pink towel turban, and red heart-shaped sunglasses, seated on a light-colored rattan chair with soft pink cushions, positioned in front of a textured dusty rose pink wall with an arched alcove, large tropical plants with broad dark green leaves framing both sides, woven straw baskets on the floor, remove any existing shoes from the background, only the woman's beige woven sandals visible in the foreground, soft natural lighting casting gentle shadows, warm bohemian chic aesthetic, professional fashion photography",
        reference_image1=image,
        reference_image2=image_load,
    )
    saveimage = SaveImage(filename_prefix='Flux2-Klein-4b-base', images=edited)
    saveimage_2 = SaveImage(filename_prefix='Flux2-Klein-4b-base', images=edited_2)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein-4b-base')

