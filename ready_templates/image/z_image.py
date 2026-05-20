# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, EmptySD3LatentImage, KSampler, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAELoader


DEFAULT_PROMPT = 'A fashion photography work full of surreal romanticism, using a low-angle upward shooting composition, with a clear light blue sky as the background, and the visual focus concentrated on the fantasy blue vegetation and the model walking through it.\n\nThe vegetation in the picture is processed into varying shades of blue, from light ice blue to deep cobalt blue. The textures of the leaves and branches are delicate and realistic. The warm brown tree trunks form a sharp contrast with the cool blue leaves, resembling a dreamy forest from another world. An African-American model wearing a yellow and white vertical striped long dress walks slowly on the sand. The warm tones of the dress echo with the surrounding cool blue vegetation. The noon sun casts clear shadows on the sand, enhancing the sense of space and reality in the picture.\n\nThe entire scene, with its clean and transparent colors and fantasy settings, not only exudes the vastness of the natural wilderness but also presents a quiet and poetic high-fashion sense due to the surreal vegetation.'
DEFAULT_SEED = 770044821593082
GUIDE_STRENGTH = 4.0
MODEL_NAME = 'z_image_bf16.safetensors'
MODEL_NAME_2 = 'qwen_3_4b.safetensors'
MODEL_NAME_3 = 'ae.safetensors'


MODELS = {
    'qwen_3_4b': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', subdir='text_encoders'),
    'ae': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors', subdir='vae'),
    'z_image_bf16': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/diffusion_models/z_image_bf16.safetensors', subdir='diffusion_models'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('positive'), field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('ksampler'), field='seed', default=DEFAULT_SEED),
    'steps': InputSpec(node=ref('ksampler'), field='steps', default=25),
    'negative_prompt': InputSpec(node=ref('negative'), field='text', default=''),
    'width': InputSpec(node=ref('emptysd3latentimage'), field='width', default=1024),
    'height': InputSpec(node=ref('emptysd3latentimage'), field='height', default=1024),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    provenance={'source_workflow': 'workflow_corpus/official/image/z_image.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Loaders
        unetloader = UNETLoader(_id='1', unet_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        cliploader = CLIPLoader(_id='2', clip_name=MODEL_NAME_2, type_='lumina2')
        wf.metadata.setdefault('id_map', {})['cliploader'] = cliploader.node.id
        vaeloader = VAELoader(_id='3', vae_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        # Sampling
        emptysd3latentimage = EmptySD3LatentImage(_id='7', width=1024, height=1024)
        wf.metadata.setdefault('id_map', {})['emptysd3latentimage'] = emptysd3latentimage.node.id
        modelsamplingauraflow = ModelSamplingAuraFlow(
            _id='4',
            shift=3,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingauraflow'] = modelsamplingauraflow.node.id

        # Conditioning
        positive = CLIPTextEncode(_id='5', text=DEFAULT_PROMPT, clip=cliploader)
        wf.metadata.setdefault('id_map', {})['positive'] = positive.node.id
        negative = CLIPTextEncode(_id='6', text='', clip=cliploader)
        wf.metadata.setdefault('id_map', {})['negative'] = negative.node.id
        # Sampling
        ksampler = KSampler(
            _id='8',
            seed=DEFAULT_SEED,
            steps=25,
            cfg=GUIDE_STRENGTH,
            sampler_name='res_multistep',
            latent_image=emptysd3latentimage,
            model=modelsamplingauraflow,
            negative=negative,
            positive=positive,
        )
        wf.metadata.setdefault('id_map', {})['ksampler'] = ksampler.node.id

        # Decode
        vaedecode = VAEDecode(_id='9', samples=ksampler, vae=vaeloader)
        wf.metadata.setdefault('id_map', {})['vaedecode'] = vaedecode.node.id
        # Outputs
        saveimage = SaveImage(_id='10', filename_prefix='z-image', images=vaedecode)
        wf.metadata.setdefault('id_map', {})['saveimage'] = saveimage.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='z-image')

