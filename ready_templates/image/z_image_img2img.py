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
    'image': InputSpec(node=ref('loadimage'), field='image', default='image_z_image_img2img_input.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='image_z_image_img2img_input.png'),
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
        loadimage = LoadImage(
            _id='1',
            image='image_z_image_img2img_input.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        # Loaders
        unetloader = UNETLoader(_id='2', unet_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        cliploader = CLIPLoader(_id='3', clip_name=MODEL_NAME_2, type_='lumina2')
        wf.metadata.setdefault('id_map', {})['cliploader'] = cliploader.node.id
        vaeloader = VAELoader(_id='4', vae_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        modelsamplingauraflow = ModelSamplingAuraFlow(
            _id='5',
            shift=3,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingauraflow'] = modelsamplingauraflow.node.id

        # Conditioning
        positive = CLIPTextEncode(_id='6', text=DEFAULT_PROMPT, clip=cliploader)
        wf.metadata.setdefault('id_map', {})['positive'] = positive.node.id
        negative = CLIPTextEncode(_id='7', text='', clip=cliploader)
        wf.metadata.setdefault('id_map', {})['negative'] = negative.node.id
        imagescale = ImageScale(
            _id='8',
            upscale_method='lanczos',
            width=1024,
            height=1024,
            crop='center',
            image=loadimage.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['imagescale'] = imagescale.node.id

        vaeencode = VAEEncode(_id='9', pixels=imagescale, vae=vaeloader)
        wf.metadata.setdefault('id_map', {})['vaeencode'] = vaeencode.node.id
        # Sampling
        ksampler = KSampler(
            _id='10',
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
        wf.metadata.setdefault('id_map', {})['ksampler'] = ksampler.node.id

        # Decode
        vaedecode = VAEDecode(_id='11', samples=ksampler, vae=vaeloader)
        wf.metadata.setdefault('id_map', {})['vaedecode'] = vaedecode.node.id
        # Outputs
        saveimage = SaveImage(
            _id='12',
            filename_prefix='z-image-img2img',
            images=vaedecode,
        )
        wf.metadata.setdefault('id_map', {})['saveimage'] = saveimage.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='z-image-img2img')

