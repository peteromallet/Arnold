# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGNorm, CLIPLoader, ComfySwitchNode, ImageScaleToTotalPixels, KSampler, LoadImage, LoraLoaderModelOnly, ModelSamplingAuraFlow, SaveImage, TextEncodeQwenImageEdit, UNETLoader, VAEDecode, VAEEncode, VAELoader


DEFAULT_PROMPT = 'Remove all UI text elements from the image. Keep the feeling that the characters and scene are in water. Also, remove the green UI elements at the bottom.'
DEFAULT_SEED = 344147753686358
MODEL_NAME = 'qwen_image_edit_fp8_e4m3fn.safetensors'
MODEL_NAME_2 = 'qwen_2.5_vl_7b_fp8_scaled.safetensors'
MODEL_NAME_3 = 'qwen_image_vae.safetensors'
MODEL_NAME_4 = 'Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors'


MODELS = {
    'qwen_image_edit_fp8_e4m3fn': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors', sha256='393c6743d1de2e9031b5197027b36116f2096958ccc0223526d34e1860266021', hf_revision='83ae44f23af827155718b906c7dcc195a37c60b4', size_bytes=20430635136, subdir='diffusion_models'),
    'qwen_2_5_vl_7b_fp8_scaled': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors', sha256='cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=9384670680, subdir='text_encoders'),
    'qwen_image_vae': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors', sha256='a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=253806246, subdir='vae'),
    'qwen_image_edit_lightning_4steps_v1_0_bf16': ModelAsset(url='https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors', sha256='d8132c32e7df906603dd6b072ff2fb0af88ab15ef0f3ac697a2011c8b47bbeb1', hf_revision='e74da8d4e71a54b341de86aa9f8d2509165aa513', size_bytes=849608296, subdir='loras'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('textencodeqwenimageedit'), field='prompt', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('ksampler'), field='seed', default=DEFAULT_SEED),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=False),
    'sampler_name': InputSpec(node=ref('ksampler'), field='sampler_name', default='euler'),
    'source_image': InputSpec(node=ref('loadimage'), field='image', default='image_qwen_image_edit_input_image.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='image_qwen_image_edit_input_image.png'),
    'image': InputSpec(node=ref('loadimage'), field='image', default='image_qwen_image_edit_input_image.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_edit',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    provenance={'source_workflow': 'workflow_corpus/official/edit/qwen_image_edit.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        loadimage = LoadImage(
            _id='78',
            image='image_qwen_image_edit_input_image.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        # Loaders
        unetloader = UNETLoader(_id='102:37', unet_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        cliploader = CLIPLoader(
            _id='102:38',
            clip_name=MODEL_NAME_2,
            type_='qwen_image',
        )
        wf.metadata.setdefault('id_map', {})['cliploader'] = cliploader.node.id

        vaeloader = VAELoader(_id='102:39', vae_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        # Inputs
        primitiveint = raw_call(wf, 'PrimitiveInt', '102:103', value=4)
        wf.metadata.setdefault('id_map', {})['primitiveint'] = primitiveint.node.id
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '102:105', value=1)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        primitiveint_2 = raw_call(wf, 'PrimitiveInt', '102:106', value=20)
        wf.metadata.setdefault('id_map', {})['primitiveint_2'] = primitiveint_2.node.id
        primitivefloat_2 = raw_call(wf, 'PrimitiveFloat', '102:107', value=2.5)
        wf.metadata.setdefault('id_map', {})['primitivefloat_2'] = primitivefloat_2.node.id
        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '102:111', value=False)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        imagescaletototalpixels = ImageScaleToTotalPixels(
            _id='93',
            upscale_method='lanczos',
            megapixels=1.5,
            image=loadimage.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['imagescaletototalpixels'] = imagescaletototalpixels.node.id

        textencodeqwenimageedit = TextEncodeQwenImageEdit(
            _id='102:76',
            prompt=DEFAULT_PROMPT,
            clip=cliploader,
            image=loadimage.out('IMAGE'),
            vae=vaeloader,
        )
        wf.metadata.setdefault('id_map', {})['textencodeqwenimageedit'] = textencodeqwenimageedit.node.id

        textencodeqwenimageedit_2 = TextEncodeQwenImageEdit(
            _id='102:77',
            prompt='',
            clip=cliploader,
            image=loadimage.out('IMAGE'),
            vae=vaeloader,
        )
        wf.metadata.setdefault('id_map', {})['textencodeqwenimageedit_2'] = textencodeqwenimageedit_2.node.id

        vaeencode = VAEEncode(
            _id='102:88',
            pixels=loadimage.out('IMAGE'),
            vae=vaeloader,
        )
        wf.metadata.setdefault('id_map', {})['vaeencode'] = vaeencode.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='102:89',
            lora_name=MODEL_NAME_4,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        comfyswitchnode_2 = ComfySwitchNode(
            _id='102:109',
            on_false=primitivefloat_2,
            on_true=primitivefloat,
            switch=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode_2'] = comfyswitchnode_2.node.id

        comfyswitchnode_3 = ComfySwitchNode(
            _id='102:110',
            on_false=primitiveint_2,
            on_true=primitiveint,
            switch=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode_3'] = comfyswitchnode_3.node.id

        comfyswitchnode = ComfySwitchNode(
            _id='102:108',
            on_false=unetloader,
            on_true=loraloadermodelonly,
            switch=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode'] = comfyswitchnode.node.id

        modelsamplingauraflow = ModelSamplingAuraFlow(
            _id='102:66',
            shift=3,
            model=comfyswitchnode,
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingauraflow'] = modelsamplingauraflow.node.id

        cfgnorm = CFGNorm(_id='102:75', model=modelsamplingauraflow)
        wf.metadata.setdefault('id_map', {})['cfgnorm'] = cfgnorm.node.id
        # Sampling
        ksampler = KSampler(
            _id='102:3',
            seed=DEFAULT_SEED,
            sampler_name='euler',
            steps=comfyswitchnode_3,
            cfg=comfyswitchnode_2,
            latent_image=vaeencode,
            model=cfgnorm,
            negative=textencodeqwenimageedit_2,
            positive=textencodeqwenimageedit,
        )
        wf.metadata.setdefault('id_map', {})['ksampler'] = ksampler.node.id

        # Decode
        vaedecode = VAEDecode(_id='102:8', samples=ksampler, vae=vaeloader)
        wf.metadata.setdefault('id_map', {})['vaedecode'] = vaedecode.node.id
        # Outputs
        saveimage = SaveImage(_id='60', images=vaedecode)
        wf.metadata.setdefault('id_map', {})['saveimage'] = saveimage.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

