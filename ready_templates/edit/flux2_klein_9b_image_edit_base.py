# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, EmptyFlux2LatentImage, Flux2Scheduler, GetImageSize, ImageScaleToTotalPixels, KSamplerSelect, LoadImage, RandomNoise, ReferenceLatent, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='76', field='image', default='car_interior_white.jpeg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json', 'source_id': 'flux2_klein_9b_image_edit_base', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json', 'output_mode': 'ready_template', 'ready_id': 'edit/flux2_klein_9b_image_edit_base'},
)

# === Subgraph functions ===

def image_edit_flux2_klein_9b(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    image,
):
    """Image Edit (Flux.2 Klein 9B) - single-image variant.

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json.
    # vibecomfy source hash: sha256:b2d3d67eb296d6e0e41bc55934c4f7c02695f20c73be184bf6fe5349ebefd8af
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
        noise_seed=192774551144773,
        control_after_generate='randomize',
    )

    imagescaletototalpixels = ImageScaleToTotalPixels(
        _id='7b34ab90-36f9-45ba-a665-71d418f0df18:80',
        upscale_method='lanczos',
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


def image_edit_flux2_klein_9b_dual(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    reference_image1,
    reference_image2,
):
    """Image Edit (Flux.2 Klein 9B) - two-image variant.

    Materialized from subgraph 65c22b29-59aa-496b-89c6-55a603658670 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json.
    # vibecomfy source hash: sha256:99bcee3dbb6e2838d7c3275e03f30c27d09b5f53173f2f049a42eff86bbb883c
    Inner nodes: KSamplerSelect, SamplerCustomAdvanced, VAEDecode, RandomNoise, UNETLoader, VAELoader, GetImageSize, EmptyFlux2LatentImage, ImageScaleToTotalPixelsx2, CLIPLoader, CLIPTextEncodex2, CFGGuider, Flux2Scheduler, ReferenceLatentx4, VAEEncodex2.
    """

    imagescaletototalpixels = ImageScaleToTotalPixels(
        _id='65c22b29-59aa-496b-89c6-55a603658670:85',
        upscale_method='lanczos',
        image=reference_image2,
    )

    ksamplerselect = KSamplerSelect(
        _id='65c22b29-59aa-496b-89c6-55a603658670:102',
        sampler_name='euler',
    )

    randomnoise = RandomNoise(
        _id='65c22b29-59aa-496b-89c6-55a603658670:105',
        noise_seed=86928255107192,
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
        upscale_method='lanczos',
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

    image, _ = LoadImage(image='car_interior_white.jpeg')
    image_load, _ = LoadImage(image='comfy_logo_blue.png')
    edited = image_edit_flux2_klein_9b(
        unet_name='flux-2-klein-base-9b-fp8.safetensors',
        clip_name=image,
        vae_name='full_encoder_small_decoder.safetensors',
        prompt="Change the camera angle to a first-person driver's perspective looking through the steering wheel at the dashboard and windshield, maintaining the same white minimalist interior style and lighting\n",
        image=image,
    )
    edited_dual = image_edit_flux2_klein_9b_dual(
        unet_name='flux-2-klein-base-9b-fp8.safetensors',
        clip_name=image,
        vae_name=image_load,
        prompt='Apply the yellow "C" logo to the center hub of the steering wheel, and change the steering wheel color to royal blue matching the logo background, while maintaining the same interior style, lighting, camera angle, and all other elements unchanged',
        reference_image1=image,
        reference_image2=image_load,
    )
    saveimage = SaveImage(filename_prefix='Flux2-Klein-4b-base', images=edited)
    saveimage_2 = SaveImage(filename_prefix='Flux2-Klein-4b-base', images=edited_dual)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein-4b-base')

