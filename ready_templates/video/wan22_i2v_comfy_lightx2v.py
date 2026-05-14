# vibecomfy: manual
# Converted from ComfyUI's expanded component-cache graph, then hand-edited to
# restore official model URLs from the source subgraphed workflow.
"""Comfy native Wan 2.2 I2V Lightx2v ready template candidate."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'ready_template': 'video/wan22_i2v_comfy_lightx2v',
 'workflow_template': 'wan22_i2v_comfy_lightx2v',
 'capability': 'image_to_video',
 'coverage_tier': 'production_parity_candidate',
 'approach': 'Native ComfyUI WanImageToVideo Wan 2.2 A14B I2V with fp8_scaled high/low diffusion models and official Lightx2v 4-step LoRAs.',
 'runtime_note': 'Candidate for comparing against the Kijai WanVideoWrapper Wan 2.2 I2V path; uses only Comfy core/runtime node classes after component expansion.',
 'smoke_resolution': '720x720x81_frames',
 'model_assets': [{'name': 'wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors',
                   'subdir': 'loras'},
                  {'name': 'wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors',
                   'subdir': 'loras'},
                  {'name': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'wan_2.1_vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
                   'subdir': 'vae'}],
 'unbound_inputs': {'image': '97.image',
                    'prompt': '130:107.text',
                    'negative_prompt': '130:125.text',
                    'seed': '130:110.noise_seed',
                    'width': '130:128.width',
                    'height': '130:128.height',
                    'num_frames': '130:128.length',
                    'steps': '130:110.steps'},
 'source_workflow': 'vendor/ComfyUI/tests/unit/playwright_cache/1.43.1+t0.9.45/03_video_wan2_2_14B_i2v_subgraphed.json',
 'source_component_workflow': 'vendor/direct_templates/03_video_wan2_2_14B_i2v_subgraphed.json',
 'provenance': {'source_path': 'vendor/ComfyUI/tests/unit/playwright_cache/1.43.1+t0.9.45/03_video_wan2_2_14B_i2v_subgraphed.json',
                'source_id': '03_video_wan2_2_14B_i2v_subgraphed',
                'source_type': 'api',
                'source_workflow_path': 'vendor/ComfyUI/tests/unit/playwright_cache/1.43.1+t0.9.45/03_video_wan2_2_14B_i2v_subgraphed.json',
                'source_ref': 'vendor/ComfyUI/tests/unit/playwright_cache/1.43.1+t0.9.45/03_video_wan2_2_14B_i2v_subgraphed.json',
                'source_kind': 'raw_json',
                'indexed_id': None,
                'workflow_source_id': '03_video_wan2_2_14B_i2v_subgraphed',
                'workflow_source_type': 'api',
                'raw_workflow_shape': 'api',
                'source_hash': 'sha256:6d8f09096c1e0817c00184b6b53c0676f155985f4063f59c38100388b43fbd4e',
                'workflow_shape': {'nodes': 17,
                                   'runtime_nodes': 17,
                                   'helper_nodes': 0,
                                   'edges': 1,
                                   'inputs': 4,
                                   'outputs': 1},
                'output_mode': 'ready_template',
                'ready_id': 'video/wan22_i2v_comfy_lightx2v'}}

READY_REQUIREMENTS = {'models': READY_METADATA["model_assets"], 'custom_nodes': []}


def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type='ready_template',
            provenance={'source_path': 'vendor/ComfyUI/tests/unit/playwright_cache/1.43.1+t0.9.45/03_video_wan2_2_14B_i2v_subgraphed.json', 'source_id': '03_video_wan2_2_14B_i2v_subgraphed', 'source_type': 'api', 'source_workflow_path': 'vendor/ComfyUI/tests/unit/playwright_cache/1.43.1+t0.9.45/03_video_wan2_2_14B_i2v_subgraphed.json', 'source_ref': 'vendor/ComfyUI/tests/unit/playwright_cache/1.43.1+t0.9.45/03_video_wan2_2_14B_i2v_subgraphed.json', 'source_kind': 'raw_json', 'indexed_id': None, 'workflow_source_id': '03_video_wan2_2_14B_i2v_subgraphed', 'workflow_source_type': 'api', 'raw_workflow_shape': 'api', 'source_hash': 'sha256:6d8f09096c1e0817c00184b6b53c0676f155985f4063f59c38100388b43fbd4e', 'workflow_shape': {'nodes': 17, 'runtime_nodes': 17, 'helper_nodes': 0, 'edges': 1, 'inputs': 4, 'outputs': 1}, 'output_mode': 'ready_template', 'ready_id': 'video/wan22_i2v_comfy_lightx2v'},
        ),
    )

    loadimage = _node(wf, 'LoadImage', '97',
        image='03_video_wan2_2_14B_i2v_subgraphed_input_image.png',
    )
    cliploader = _node(wf, 'CLIPLoader', '130:105',
        clip_name='umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        type='wan',
        device='default',
    )
    vaeloader = _node(wf, 'VAELoader', '130:106',
        vae_name='wan_2.1_vae.safetensors',
    )
    unetloader = _node(wf, 'UNETLoader', '130:122',
        unet_name='wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors',
        weight_dtype='default',
    )
    unetloader_2 = _node(wf, 'UNETLoader', '130:123',
        unet_name='wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors',
        weight_dtype='default',
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '130:107',
        text='A felt-style little eagle cashier greeting, waving, and smiling at the camera.',
        clip=cliploader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '130:125',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '130:126',
        lora_name='wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors',
        strength_model=1.0000000000000002,
        model=unetloader.out(0),
    )
    loraloadermodelonly_2 = _node(wf, 'LoraLoaderModelOnly', '130:127',
        lora_name='wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors',
        strength_model=1.0000000000000002,
        model=unetloader_2.out(0),
    )
    modelsamplingsd3 = _node(wf, 'ModelSamplingSD3', '130:109',
        shift=5.000000000000001,
        model=loraloadermodelonly.out(0),
    )
    modelsamplingsd3_2 = _node(wf, 'ModelSamplingSD3', '130:124',
        shift=5.000000000000001,
        model=loraloadermodelonly_2.out(0),
    )
    wanimagetovideo = _node(wf, 'WanImageToVideo', '130:128',
        batch_size=1,
        height=720,
        length=81,
        width=720,
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
        start_image=loadimage.out(0),
        vae=vaeloader.out(0),
    )
    ksampleradvanced = _node(wf, 'KSamplerAdvanced', '130:110',
        add_noise='enable',
        noise_seed=0,
        steps=4,
        cfg=1,
        sampler_name='euler',
        scheduler='simple',
        start_at_step=0,
        end_at_step=2,
        return_with_leftover_noise='enable',
        latent_image=wanimagetovideo.out(2),
        model=modelsamplingsd3.out(0),
        negative=wanimagetovideo.out(1),
        positive=wanimagetovideo.out(0),
    )
    ksampleradvanced_2 = _node(wf, 'KSamplerAdvanced', '130:111',
        add_noise='disable',
        noise_seed=0,
        steps=4,
        cfg=1,
        sampler_name='euler',
        scheduler='simple',
        start_at_step=2,
        end_at_step=4,
        return_with_leftover_noise='disable',
        latent_image=ksampleradvanced.out(0),
        model=modelsamplingsd3_2.out(0),
        negative=wanimagetovideo.out(1),
        positive=wanimagetovideo.out(0),
    )
    vaedecode = _node(wf, 'VAEDecode', '130:129',
        samples=ksampleradvanced_2.out(0),
        vae=vaeloader.out(0),
    )
    createvideo = _node(wf, 'CreateVideo', '130:117',
        fps=16,
        images=vaedecode.out(0),
    )
    savevideo = _node(wf, 'SaveVideo', '108',
        filename_prefix='video/Wan2.2_image_to_video',
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
