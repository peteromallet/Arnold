# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [{'name': 'wan2.1_i2v_480p_14B_fp16.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'wan_2.1_vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'clip_vision_h.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors',
                   'subdir': 'clip_vision'}],
 'unbound_inputs': {'seed': 1694},
 'ready_template': 'video/wan_i2v',
 'workflow_template': 'wan_i2v',
 'capability': 'image_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/video/wan_i2v.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'wan2.1_i2v_480p_14B_fp16.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'wan_2.1_vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
             'subdir': 'vae'},
            {'name': 'clip_vision_h.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors',
             'subdir': 'clip_vision'}],
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

    unetloader = _node(wf, 'UNETLoader', '37',
        unet_name='wan2.1_i2v_480p_14B_fp16.safetensors',
        weight_dtype='default',
    )
    cliploader = _node(wf, 'CLIPLoader', '38',
        clip_name='umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        type='wan',
        device='default',
    )
    vaeloader = _node(wf, 'VAELoader', '39',
        vae_name='wan_2.1_vae.safetensors',
    )
    clipvisionloader = _node(wf, 'CLIPVisionLoader', '49',
        clip_name='clip_vision_h.safetensors',
    )
    loadimage = _node(wf, 'LoadImage', '52',
        image='image_to_video_wan_start_image.png',
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '6',
        text='a cute anime girl with massive fennec ears and a big fluffy tail wearing a maid outfit turning around',
        clip=cliploader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '7',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader.out(0),
    )
    clipvisionencode = _node(wf, 'CLIPVisionEncode', '51',
        crop='none',
        clip_vision=clipvisionloader.out(0),
        image=loadimage.out(0),
    )
    modelsamplingsd3 = _node(wf, 'ModelSamplingSD3', '54',
        shift=8,
        model=unetloader.out(0),
    )
    wanimagetovideo = _node(wf, 'WanImageToVideo', '50',
        batch_size=1,
        height=512,
        length=33,
        width=512,
        clip_vision_output=clipvisionencode.out(0),
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
        start_image=loadimage.out(0),
        vae=vaeloader.out(0),
    )
    ksampler = _node(wf, 'KSampler', '3',
        seed=987948718394761,
        steps=20,
        cfg=6,
        sampler_name='uni_pc',
        scheduler='simple',
        denoise=1,
        latent_image=wanimagetovideo.out(2),
        model=modelsamplingsd3.out(0),
        negative=wanimagetovideo.out(1),
        positive=wanimagetovideo.out(0),
    )
    vaedecode = _node(wf, 'VAEDecode', '8',
        samples=ksampler.out(0),
        vae=vaeloader.out(0),
    )
    createvideo = _node(wf, 'CreateVideo', '55',
        fps=16,
        images=vaedecode.out(0),
    )
    savevideo = _node(wf, 'SaveVideo', '56',
        filename_prefix='video/ComfyUI',
        format='auto',
        codec='auto',
        video=createvideo.out(0),
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

