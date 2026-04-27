# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [{'name': 'qwen_image_edit_fp8_e4m3fn.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'qwen_image_vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
                   'url': 'https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
                   'subdir': 'loras'}],
 'unbound_inputs': {'seed': 2570},
 'ready_template': 'edit/qwen_image_edit',
 'workflow_template': 'qwen_image_edit',
 'capability': 'image_edit',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/edit/qwen_image_edit.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'qwen_image_edit_fp8_e4m3fn.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'qwen_image_vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
             'subdir': 'vae'},
            {'name': 'Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
             'url': 'https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
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

    loadimage = _node(wf, 'LoadImage', '78',
        image='image_qwen_image_edit_input_image.png',
    )
    unetloader = _node(wf, 'UNETLoader', '102:37',
        unet_name='qwen_image_edit_fp8_e4m3fn.safetensors',
        weight_dtype='default',
    )
    cliploader = _node(wf, 'CLIPLoader', '102:38',
        clip_name='qwen_2.5_vl_7b_fp8_scaled.safetensors',
        type='qwen_image',
        device='default',
    )
    vaeloader = _node(wf, 'VAELoader', '102:39',
        vae_name='qwen_image_vae.safetensors',
    )
    primitiveint = _node(wf, 'PrimitiveInt', '102:103',
        value=4,
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '102:105',
        value=1,
    )
    primitiveint_2 = _node(wf, 'PrimitiveInt', '102:106',
        value=20,
    )
    primitivefloat_2 = _node(wf, 'PrimitiveFloat', '102:107',
        value=2.5,
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '102:111',
        value=False,
    )
    imagescaletototalpixels = _node(wf, 'ImageScaleToTotalPixels', '93',
        upscale_method='lanczos',
        megapixels=1.5,
        resolution_steps=1,
        image=loadimage.out(0),
    )
    textencodeqwenimageedit = _node(wf, 'TextEncodeQwenImageEdit', '102:76',
        prompt='Remove all UI text elements from the image. Keep the feeling that the characters and scene are in water. Also, remove the green UI elements at the bottom.',
        clip=cliploader.out(0),
        image=loadimage.out(0),
        vae=vaeloader.out(0),
    )
    textencodeqwenimageedit_2 = _node(wf, 'TextEncodeQwenImageEdit', '102:77',
        prompt='',
        clip=cliploader.out(0),
        image=loadimage.out(0),
        vae=vaeloader.out(0),
    )
    vaeencode = _node(wf, 'VAEEncode', '102:88',
        pixels=loadimage.out(0),
        vae=vaeloader.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '102:89',
        lora_name='Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
        strength_model=1,
        model=unetloader.out(0),
    )
    comfyswitchnode_2 = _node(wf, 'ComfySwitchNode', '102:109',
        on_false=primitivefloat_2.out(0),
        on_true=primitivefloat.out(0),
        switch=primitiveboolean.out(0),
    )
    comfyswitchnode_3 = _node(wf, 'ComfySwitchNode', '102:110',
        on_false=primitiveint_2.out(0),
        on_true=primitiveint.out(0),
        switch=primitiveboolean.out(0),
    )
    comfyswitchnode = _node(wf, 'ComfySwitchNode', '102:108',
        on_false=unetloader.out(0),
        on_true=loraloadermodelonly.out(0),
        switch=primitiveboolean.out(0),
    )
    modelsamplingauraflow = _node(wf, 'ModelSamplingAuraFlow', '102:66',
        shift=3,
        model=comfyswitchnode.out(0),
    )
    cfgnorm = _node(wf, 'CFGNorm', '102:75',
        strength=1,
        model=modelsamplingauraflow.out(0),
    )
    ksampler = _node(wf, 'KSampler', '102:3',
        seed=344147753686358,
        sampler_name='euler',
        scheduler='simple',
        denoise=1,
        steps=comfyswitchnode_3.out(0),
        cfg=comfyswitchnode_2.out(0),
        latent_image=vaeencode.out(0),
        model=cfgnorm.out(0),
        negative=textencodeqwenimageedit_2.out(0),
        positive=textencodeqwenimageedit.out(0),
    )
    vaedecode = _node(wf, 'VAEDecode', '102:8',
        samples=ksampler.out(0),
        vae=vaeloader.out(0),
    )
    saveimage = _node(wf, 'SaveImage', '60',
        filename_prefix='ComfyUI',
        images=vaedecode.out(0),
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
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

