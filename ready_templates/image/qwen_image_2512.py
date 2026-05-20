# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, ComfySwitchNode, EmptySD3LatentImage, KSampler, LoraLoaderModelOnly, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAELoader


DEFAULT_PROMPT = 'Urban alleyway at dusk. Tall, statuesque high-fashion model striding elegantly, mid distant full body shot from an angular perspective, cinematic/editorial with bold contrasts and tactile materials. They wear a rose-gold metallic trench coat with deconstructed elements over a black long-sleeved turtleneck with subtle texture; paired with forest-green pleated pants with raw hems and a soft texture. Long braided dark hair, medium complexion. They carry a vibrant yellow designer handbag with geometric details and a structured silhouette. White architectural sneakers with bold geometric cutouts. Bold, high-contrast, tactile, urban-grit meets high-fashion impact, extreme clarity, extreme layering, post-processing with transparent light-transmitting ultra-smooth high-definition film effect, removing all noise and grain, removing all blur, removing all vintage feel, removing all roughness, drawn with 32K pixel precision, unparalleled fine line drawing of every single detail, the entire image like a brand new photograph, photorealistic\n'
DEFAULT_PROMPT_2 = '低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲'
DEFAULT_SEED = 1232512
MODEL_NAME = 'qwen_2.5_vl_7b_fp8_scaled.safetensors'
MODEL_NAME_2 = 'qwen_image_vae.safetensors'
MODEL_NAME_3 = 'qwen_image_2512_fp8_e4m3fn.safetensors'
MODEL_NAME_4 = 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors'


MODELS = {
    'qwen_image_2512_fp8_e4m3fn': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors', sha256='5dc80554d5d83390046a2f4a94ece06afb7700bf7b0aaf8bde9769793875876b', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=20430679144, subdir='diffusion_models'),
    'qwen_2_5_vl_7b_fp8_scaled': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors', sha256='cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=9384670680, subdir='text_encoders'),
    'qwen_image_vae': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors', sha256='a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=253806246, subdir='vae'),
    'qwen_image_2512_lightning_4steps_v1_0_fp32': ModelAsset(url='https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', sha256='ad12117461cb41e2ea637fec8df6392ce8e8550c47fbe2b829ed3deb98262066', hf_revision='a52649c9d0f6e1a248bff13f0df33bb8a2abdb52', size_bytes=1698951104, subdir='loras'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME_3),
    'prompt': InputSpec(node=ref('positive'), field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('ksampler'), field='seed', default=DEFAULT_SEED),
    'negative_prompt': InputSpec(node=ref('negative'), field='text', default=DEFAULT_PROMPT_2),
    'negative': InputSpec(node=ref('negative'), field='text', default=DEFAULT_PROMPT_2),
    'width': InputSpec(node=ref('emptysd3latentimage'), field='width', default=768),
    'height': InputSpec(node=ref('emptysd3latentimage'), field='height', default=768),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=True),
    'sampler_name': InputSpec(node=ref('ksampler'), field='sampler_name', default='euler'),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='Qwen-Image-2512',
    smoke_resolution='768x768',
    runtime_variant='qwen-image-2512-lightning-4step-768px',
    approach='official Qwen-Image-2512 text-to-image workflow using the 4-step Lightning LoRA path for smoke/runtime validation',
    provenance={'source_workflow': 'workflow_corpus/official/image/qwen_image_2512.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Loaders
        cliploader = CLIPLoader(clip_name=MODEL_NAME, type_='qwen_image')
        vaeloader = VAELoader(vae_name=MODEL_NAME_2)
        unetloader = UNETLoader(unet_name=MODEL_NAME_3)

        # Sampling
        emptysd3latentimage = EmptySD3LatentImage(width=768, height=768)

        # Inputs
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '238:218', value=1.0)
        primitivefloat_2 = raw_call(wf, 'PrimitiveFloat', '238:223', value=1)
        primitiveint = raw_call(wf, 'PrimitiveInt', '238:224', value=4)
        primitiveint_2 = raw_call(wf, 'PrimitiveInt', '238:225', value=4)
        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '238:229', value=True)
        loraloadermodelonly = LoraLoaderModelOnly(
            lora_name=MODEL_NAME_4,
            model=unetloader,
        )

        # Conditioning
        positive = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)
        negative = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader)
        comfyswitchnode = ComfySwitchNode(
            on_false=primitiveint,
            on_true=primitiveint_2,
            switch=primitiveboolean,
        )

        comfyswitchnode_2 = ComfySwitchNode(
            on_false=primitivefloat_2,
            on_true=primitivefloat,
            switch=primitiveboolean,
        )

        comfyswitchnode_3 = ComfySwitchNode(
            on_false=unetloader,
            on_true=loraloadermodelonly,
            switch=primitiveboolean,
        )

        modelsamplingauraflow = ModelSamplingAuraFlow(
            shift=3.1,
            model=comfyswitchnode_3,
        )

        # Sampling
        ksampler = KSampler(
            seed=DEFAULT_SEED,
            sampler_name='euler',
            steps=comfyswitchnode,
            cfg=comfyswitchnode_2,
            latent_image=emptysd3latentimage,
            model=modelsamplingauraflow,
            negative=negative,
            positive=positive,
        )

        # Decode
        vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

        # Outputs
        saveimage = SaveImage(filename_prefix='Qwen-Image-2512', images=vaedecode)

        wf._set_id_map({name: node.node.id for name, node in (('cliploader', cliploader), ('vaeloader', vaeloader), ('unetloader', unetloader), ('emptysd3latentimage', emptysd3latentimage), ('loraloadermodelonly', loraloadermodelonly), ('positive', positive), ('negative', negative), ('comfyswitchnode', comfyswitchnode), ('comfyswitchnode_2', comfyswitchnode_2), ('comfyswitchnode_3', comfyswitchnode_3), ('modelsamplingauraflow', modelsamplingauraflow), ('ksampler', ksampler), ('vaedecode', vaedecode), ('saveimage', saveimage), ('primitivefloat', primitivefloat), ('primitivefloat_2', primitivefloat_2), ('primitiveint', primitiveint), ('primitiveint_2', primitiveint_2), ('primitiveboolean', primitiveboolean))})

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

