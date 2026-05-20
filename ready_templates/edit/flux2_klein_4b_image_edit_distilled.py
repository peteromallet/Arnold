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
    'image': InputSpec(node=ref('loadimage'), field='image', default='handbag_white.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='handbag_white.png'),
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

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Sampling
        ksamplerselect = KSamplerSelect(_id='75:61', sampler_name='euler')
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id
        # Loaders
        unetloader = UNETLoader(_id='75:70', unet_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        cliploader = CLIPLoader(_id='75:71', clip_name=MODEL_NAME_2, type_='flux2')
        wf.metadata.setdefault('id_map', {})['cliploader'] = cliploader.node.id
        vaeloader = VAELoader(_id='75:72', vae_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        randomnoise = RandomNoise(_id='75:73', noise_seed=DEFAULT_SEED)
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id
        # Inputs
        loadimage = LoadImage(
            _id='76',
            image='handbag_white.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        loadimage_2 = LoadImage(
            _id='81',
            image='comfy_logo_blue.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_2'] = loadimage_2.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='75:74',
            text='Change the bag color to blue.',
            clip=cliploader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        imagescaletototalpixels = ImageScaleToTotalPixels(
            _id='75:80',
            upscale_method='nearest-exact',
            image=loadimage.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['imagescaletototalpixels'] = imagescaletototalpixels.node.id

        conditioningzeroout = ConditioningZeroOut(
            _id='75:82',
            conditioning=cliptextencode,
        )
        wf.metadata.setdefault('id_map', {})['conditioningzeroout'] = conditioningzeroout.node.id

        getimagesize = GetImageSize(
            _id='75:99',
            image=imagescaletototalpixels,
            _outputs=('WIDTH', 'HEIGHT', 'BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize'] = getimagesize.node.id

        vaeencode = VAEEncode(
            _id='75:122',
            pixels=imagescaletototalpixels,
            vae=vaeloader,
        )
        wf.metadata.setdefault('id_map', {})['vaeencode'] = vaeencode.node.id

        # Sampling
        flux2scheduler = Flux2Scheduler(
            _id='75:62',
            steps=4,
            height=getimagesize.out('HEIGHT'),
            width=getimagesize.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['flux2scheduler'] = flux2scheduler.node.id

        emptyflux2latentimage = EmptyFlux2LatentImage(
            _id='75:66',
            width=getimagesize.out('WIDTH'),
            height=getimagesize.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['emptyflux2latentimage'] = emptyflux2latentimage.node.id

        referencelatent = ReferenceLatent(
            _id='75:121',
            conditioning=conditioningzeroout,
            latent=vaeencode,
        )
        wf.metadata.setdefault('id_map', {})['referencelatent'] = referencelatent.node.id

        referencelatent_2 = ReferenceLatent(
            _id='75:123',
            conditioning=cliptextencode,
            latent=vaeencode,
        )
        wf.metadata.setdefault('id_map', {})['referencelatent_2'] = referencelatent_2.node.id

        # Conditioning
        cfgguider = CFGGuider(
            _id='75:63',
            cfg=GUIDE_STRENGTH,
            model=unetloader,
            negative=referencelatent,
            positive=referencelatent_2,
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='75:64',
            guider=cfgguider,
            latent_image=emptyflux2latentimage,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=flux2scheduler,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        # Decode
        vaedecode = VAEDecode(
            _id='75:65',
            samples=samplercustomadvanced.out('OUTPUT'),
            vae=vaeloader,
        )
        wf.metadata.setdefault('id_map', {})['vaedecode'] = vaedecode.node.id

        # Outputs
        saveimage = SaveImage(_id='9', filename_prefix='Flux2-Klein', images=vaedecode)
        wf.metadata.setdefault('id_map', {})['saveimage'] = saveimage.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

