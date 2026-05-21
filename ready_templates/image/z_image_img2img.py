# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, ImageScale, KSampler, LoadImage, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAEEncode, VAELoader


DEFAULT_PROMPT = 'A compact red cube on a clean white tabletop, product-photo lighting.'
DEFAULT_SEED = 770044821593082
GUIDE_STRENGTH = 0.0
MODEL_NAME = 'z_image_bf16.safetensors'
MODEL_NAME_2 = 'qwen_3_4b.safetensors'
MODEL_NAME_3 = 'ae.safetensors'


MODELS = {
    'z_image_bf16': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/diffusion_models/z_image_bf16.safetensors', subdir='diffusion_models'),
    'qwen_3_4b': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', subdir='text_encoders'),
    'ae': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors', subdir='vae'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('positive'), field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('ksampler'), field='seed', default=DEFAULT_SEED),
    'steps': InputSpec(node=ref('ksampler'), field='steps', default=12),
    'image': InputSpec(node=ref('image'), field='image', default='image_z_image_img2img_input.png'),
    'input_image': InputSpec(node=ref('image'), field='image', default='image_z_image_img2img_input.png'),
    'width': InputSpec(node=ref('imagescale'), field='width', default=1024),
    'height': InputSpec(node=ref('imagescale'), field='height', default=1024),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_to_image',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    approach='Z-Image Turbo img2img via VAEEncode init latent and KSampler denoise strength',
    runtime_note='Intended to match Reigh z_image_turbo_i2i production semantics.',
    smoke_resolution='1024x1024',
    provenance={'source_workflow': 'ready_templates/image/z_image_img2img.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        image, mask = LoadImage(image='image_z_image_img2img_input.png')

        # Loaders
        unetloader = UNETLoader(unet_name=MODEL_NAME)
        cliploader = CLIPLoader(clip_name=MODEL_NAME_2, type_='lumina2')
        vaeloader = VAELoader(vae_name=MODEL_NAME_3)
        modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=unetloader)

        # Conditioning
        positive = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)
        negative = CLIPTextEncode(text='', clip=cliploader)

        imagescale = ImageScale(
            upscale_method='lanczos',
            width=1024,
            height=1024,
            crop='center',
            image=image,
        )

        vaeencode = VAEEncode(pixels=imagescale, vae=vaeloader)

        # Sampling
        ksampler = KSampler(
            seed=DEFAULT_SEED,
            steps=12,
            cfg=GUIDE_STRENGTH,
            sampler_name='res_multistep',
            denoise=0.7,
            latent_image=vaeencode,
            model=modelsamplingauraflow,
            negative=negative,
            positive=positive,
        )

        # Decode
        vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

        # Outputs
        saveimage = SaveImage(filename_prefix='z-image-img2img', images=vaedecode)

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='z-image-img2img')

