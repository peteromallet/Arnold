# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'approach': 'Kijai WanVideoWrapper Wan 2.2 A14B I2V high/low two-phase workflow with Lightx2v LoRA',
 'capability': 'image_to_video',
 'coverage_tier': 'production_parity_candidate',
 'model_assets': [{'directory': 'diffusion_models/WanVideo/2_2',
                   'name': 'Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'},
                  {'directory': 'diffusion_models/WanVideo/2_2',
                   'name': 'Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'},
                  {'directory': 'vae/wanvideo',
                   'name': 'Wan2_1_VAE_bf16.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors'},
                  {'directory': 'text_encoders',
                   'name': 'umt5-xxl-enc-bf16.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors'},
                  {'directory': 'text_encoders',
                   'name': 'umt5_xxl_fp16.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors'},
                  {'directory': 'loras/WanVideo/Lightx2v',
                   'name': 'lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'}],
 'ready_template': 'video/wanvideo_wrapper_22_14b_i2v_kijai',
 'runtime_note': 'Worker scratchpads patch image, prompt, seed, resolution, frame count, and force VHS '
                 'output saving.',
 'smoke_resolution': '832x480x81_frames',
 'source_role': 'materialized_kijai_reference_workflow',
 'source_url': 'https://raw.githubusercontent.com/kijai/ComfyUI-WanVideoWrapper/main/example_workflows/wanvideo_2_2_I2V_A14B_example_WIP.json',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wanvideo_2_2_I2V_A14B_example_WIP.json',
 'unbound_inputs': {'end_step': '91.widget_0',
                    'height': '68.widget_1',
                    'image': '67.widget_0',
                    'negative_prompt': '16.widget_1',
                    'num_frames': '89.widget_2',
                    'prompt': '16.widget_0',
                    'seed': '27.widget_3',
                    'steps': '94.widget_0',
                    'width': '68.widget_0'},
 'workflow_template': 'wanvideo_wrapper_22_14b_i2v_kijai'}

READY_REQUIREMENTS = {'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'],
 'models': [{'directory': 'diffusion_models/WanVideo/2_2',
             'name': 'Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'},
            {'directory': 'diffusion_models/WanVideo/2_2',
             'name': 'Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'},
            {'directory': 'vae/wanvideo',
             'name': 'Wan2_1_VAE_bf16.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors'},
            {'directory': 'text_encoders',
             'name': 'umt5-xxl-enc-bf16.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors'},
            {'directory': 'text_encoders',
             'name': 'umt5_xxl_fp16.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors'},
            {'directory': 'loras/WanVideo/Lightx2v',
             'name': 'lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'}]}


def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type='ready_template',
        ),
    )

    loadwanvideot5textencoder = _node(wf, 'LoadWanVideoT5TextEncoder', '11',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        load_device='offload_device',
        quantization='disabled',
    )
    wanvideotorchcompilesettings = _node(wf, 'WanVideoTorchCompileSettings', '35',
        backend='inductor',
        fullgraph=False,
        mode='default',
        dynamic=False,
        dynamo_cache_size_limit=64,
        compile_transformer_blocks_only=True,
        dynamo_recompile_limit=128,
    )
    wanvideovaeloader = _node(wf, 'WanVideoVAELoader', '38',
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
    )
    wanvideoblockswap = _node(wf, 'WanVideoBlockSwap', '39',
        blocks_to_swap=20,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=False,
        vace_blocks_to_swap=1,
    )
    cliploader = _node(wf, 'CLIPLoader', '48',
        clip_name='umt5_xxl_fp16.safetensors',
        type='wan',
        device='default',
    )
    wanvideoloraselect = _node(wf, 'WanVideoLoraSelect', '56',
        lora='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        strength=3,
        low_mem_load=False,
        merge_loras=False,
    )
    loadimage = _node(wf, 'LoadImage', '67',
        image='oldman_upscaled.png',
    )
    intconstant = _node(wf, 'INTConstant', '91',
        value=3,
    )
    intconstant_2 = _node(wf, 'INTConstant', '94',
        value=6,
    )
    wanvideoloraselect_2 = _node(wf, 'WanVideoLoraSelect', '97',
        lora='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        strength=1,
        low_mem_load=False,
        merge_loras=False,
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        positive_prompt='old man gets up and jumps into the lake',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        force_offload=True,
        use_disk_cache=False,
        device='gpu',
        t5=loadwanvideot5textencoder.out(0),
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\2_2\\Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn_scaled',
        load_device='offload_device',
        attention_mode='sdpa',
        compile_args=wanvideotorchcompilesettings.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '49',
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=cliploader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '68',
        width=720,
        height=720,
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=32,
        device='cpu',
        image=loadimage.out(0),
    )
    wanvideomodelloader_2 = _node(wf, 'WanVideoModelLoader', '71',
        model='WanVideo\\2_2\\Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn_scaled',
        load_device='offload_device',
        attention_mode='sdpa',
        compile_args=wanvideotorchcompilesettings.out(0),
    )
    createcfgschedulefloatlist = _node(wf, 'CreateCFGScheduleFloatList', '95',
        cfg_scale_start=2,
        cfg_scale_end=2,
        interpolation='linear',
        start_percent=0,
        end_percent=0.01,
        widget_0=30,
        steps=intconstant_2.out(0),
    )
    wanvideotextembedbridge = _node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    wanvideoimagetovideoencode = _node(wf, 'WanVideoImageToVideoEncode', '89',
        num_frames=81,
        noise_aug_strength=0,
        start_latent_strength=1,
        end_latent_strength=1,
        force_offload=True,
        tiled_vae=False,
        fun_or_fl2v_model=False,
        widget_0=832,
        widget_1=480,
        width=imageresizekjv2.out(1),
        height=imageresizekjv2.out(2),
        start_image=imageresizekjv2.out(0),
        vae=wanvideovaeloader.out(0),
    )
    wanvideosetblockswap = _node(wf, 'WanVideoSetBlockSwap', '92',
        block_swap_args=wanvideoblockswap.out(0),
        model=wanvideomodelloader.out(0),
    )
    wanvideosetblockswap_2 = _node(wf, 'WanVideoSetBlockSwap', '93',
        block_swap_args=wanvideoblockswap.out(0),
        model=wanvideomodelloader_2.out(0),
    )
    wanvideosetloras = _node(wf, 'WanVideoSetLoRAs', '79',
        lora=wanvideoloraselect_2.out(0),
        model=wanvideosetblockswap_2.out(0),
    )
    wanvideosetloras_2 = _node(wf, 'WanVideoSetLoRAs', '80',
        lora=wanvideoloraselect.out(0),
        model=wanvideosetblockswap.out(0),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '27',
        shift=8,
        seed=43,
        force_offload=True,
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        rope_function='comfy',
        start_step=0,
        add_noise_to_samples='',
        widget_0=6,
        widget_1=1,
        widget_12=10,
        steps=intconstant_2.out(0),
        cfg=createcfgschedulefloatlist.out(0),
        end_step=intconstant.out(0),
        image_embeds=wanvideoimagetovideoencode.out(0),
        model=wanvideosetloras_2.out(0),
        text_embeds=wanvideotextencode.out(0),
    )
    wanvideosampler_2 = _node(wf, 'WanVideoSampler', '90',
        cfg=1,
        shift=8,
        seed=43,
        force_offload=True,
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        rope_function='comfy',
        end_step=-1,
        add_noise_to_samples='',
        widget_0=6,
        widget_11=10,
        steps=intconstant_2.out(0),
        start_step=intconstant.out(0),
        image_embeds=wanvideoimagetovideoencode.out(0),
        model=wanvideosetloras.out(0),
        samples=wanvideosampler.out(0),
        text_embeds=wanvideotextencode.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '28',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        normalization='default',
        samples=wanvideosampler_2.out(0),
        vae=wanvideovaeloader.out(0),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '69',
        image=wanvideodecode.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '60',
        crf=19,
        filename_prefix='WanVideo2_2_I2V',
        format='video/h264-mp4',
        frame_rate=16,
        loop_count=0,
        pingpong=False,
        pix_fmt='yuv420p',
        save_metadata=True,
        save_output=False,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_2_I2V_00006.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_2_I2V_00006.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_2_I2V_00006.png'}, 'paused': False},
        images=getimagesizeandcount.out(0),
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
