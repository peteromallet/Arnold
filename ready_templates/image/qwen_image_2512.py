# vibecomfy: manual
# Promoted during sprint 7 to preserve snapshot parity while curating public output contracts.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_input, bind_output


READY_METADATA = {'model_assets': [{'name': 'qwen_image_2512_fp8_e4m3fn.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'qwen_image_vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
                   'url': 'https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
                   'subdir': 'loras'}],
 'ready_template': 'image/qwen_image_2512',
 'workflow_template': 'qwen_image_2512',
 'capability': 'text_to_image',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/image/qwen_image_2512.json',
 'coverage_tier': 'required',
 'approach': 'official Qwen-Image-2512 text-to-image workflow using the 4-step Lightning LoRA path for '
             'smoke/runtime validation',
 'runtime_note': None,
 'discord_signal': None,
 'runtime_variant': 'qwen-image-2512-lightning-4step-768px',
 'smoke_resolution': '768x768'}

READY_REQUIREMENTS = {'models': [{'name': 'qwen_image_2512_fp8_e4m3fn.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'qwen_image_vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
             'subdir': 'vae'},
            {'name': 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
             'url': 'https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
             'subdir': 'loras'}],
 'custom_nodes': []}


def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    primitivefloat = _node(wf, 'PrimitiveFloat', '238:218',
        value=1.0,
    )
    cliploader = _node(wf, 'CLIPLoader', '238:219',
        clip_name='qwen_2.5_vl_7b_fp8_scaled.safetensors',
        type='qwen_image',
        device='default',
    )
    vaeloader = _node(wf, 'VAELoader', '238:220',
        vae_name='qwen_image_vae.safetensors',
    )
    primitivefloat_2 = _node(wf, 'PrimitiveFloat', '238:223',
        value=1,
    )
    primitiveint = _node(wf, 'PrimitiveInt', '238:224',
        value=4,
    )
    primitiveint_2 = _node(wf, 'PrimitiveInt', '238:225',
        value=4,
    )
    unetloader = _node(wf, 'UNETLoader', '238:226',
        unet_name='qwen_image_2512_fp8_e4m3fn.safetensors',
        weight_dtype='default',
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '238:229',
        value=True,
    )
    emptysd3latentimage = _node(wf, 'EmptySD3LatentImage', '238:232',
        width=768,
        height=768,
        batch_size=1,
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '238:221',
        lora_name='Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
        strength_model=1,
        model=unetloader.out(0),
    )
    positive = _node(wf, 'CLIPTextEncode', '238:227',
        text='Urban alleyway at dusk. Tall, statuesque high-fashion model striding elegantly, mid distant full body shot from an angular perspective, cinematic/editorial with bold contrasts and tactile materials. They wear a rose-gold metallic trench coat with deconstructed elements over a black long-sleeved turtleneck with subtle texture; paired with forest-green pleated pants with raw hems and a soft texture. Long braided dark hair, medium complexion. They carry a vibrant yellow designer handbag with geometric details and a structured silhouette. White architectural sneakers with bold geometric cutouts. Bold, high-contrast, tactile, urban-grit meets high-fashion impact, extreme clarity, extreme layering, post-processing with transparent light-transmitting ultra-smooth high-definition film effect, removing all noise and grain, removing all blur, removing all vintage feel, removing all roughness, drawn with 32K pixel precision, unparalleled fine line drawing of every single detail, the entire image like a brand new photograph, photorealistic\n',
        clip=cliploader.out(0),
    )
    negative = _node(wf, 'CLIPTextEncode', '238:228',
        text='低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲',
        clip=cliploader.out(0),
    )
    comfyswitchnode_2 = _node(wf, 'ComfySwitchNode', '238:240',
        on_false=primitiveint.out(0),
        on_true=primitiveint_2.out(0),
        switch=primitiveboolean.out(0),
    )
    comfyswitchnode_3 = _node(wf, 'ComfySwitchNode', '238:243',
        on_false=primitivefloat_2.out(0),
        on_true=primitivefloat.out(0),
        switch=primitiveboolean.out(0),
    )
    comfyswitchnode = _node(wf, 'ComfySwitchNode', '238:233',
        on_false=unetloader.out(0),
        on_true=loraloadermodelonly.out(0),
        switch=primitiveboolean.out(0),
    )
    modelsamplingauraflow = _node(wf, 'ModelSamplingAuraFlow', '238:222',
        shift=3.1000000000000005,
        model=comfyswitchnode.out(0),
    )
    ksampler = _node(wf, 'KSampler', '238:230',
        seed=1232512,
        sampler_name='euler',
        scheduler='simple',
        denoise=1,
        steps=comfyswitchnode_2.out(0),
        cfg=comfyswitchnode_3.out(0),
        latent_image=emptysd3latentimage.out(0),
        model=modelsamplingauraflow.out(0),
        negative=negative.out(0),
        positive=positive.out(0),
    )
    vaedecode = _node(wf, 'VAEDecode', '238:231',
        samples=ksampler.out(0),
        vae=vaeloader.out(0),
    )
    saveimage = _node(wf, 'SaveImage', '60',
        filename_prefix='Qwen-Image-2512',
        images=vaedecode.out(0),
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    bind_input(wf, 'prompt', '238:227', 'text', type='STRING', required=True, media_semantics='text')
    bind_input(wf, 'negative_prompt', '238:228', 'text', type='STRING', aliases=['negative'], media_semantics='text')
    bind_input(wf, 'seed', '238:230', 'seed', type='INT')
    bind_input(wf, 'width', '238:232', 'width', type='INT')
    bind_input(wf, 'height', '238:232', 'height', type='INT')
    bind_output(wf, '60', output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', filename_prefix='Qwen-Image-2512', expected_cardinality='one')
    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
