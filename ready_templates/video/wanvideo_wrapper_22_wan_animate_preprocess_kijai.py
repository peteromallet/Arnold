# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'approach': 'Kijai WanAnimate preprocessing workflow using reference image, pose video, SAM2/DWPose '
             'masking, relight LoRA, and Lightx2v LoRA',
 'capability': 'animate_character',
 'coverage_tier': 'production_parity_candidate',
 'model_assets': [{'directory': 'diffusion_models/WanVideo/2_2',
                   'name': 'Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors'},
                  {'directory': 'loras/WanVideo',
                   'name': 'WanAnimate_relight_lora_fp16.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors'},
                  {'directory': 'clip_vision',
                   'name': 'clip_vision_h.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors'},
                  {'directory': 'sams',
                   'name': 'sam2_hiera_base_plus.safetensors',
                   'url': 'https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2_hiera_base_plus.safetensors'},
                  {'directory': 'detection',
                   'name': 'yolov10m.onnx',
                   'url': 'https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx'},
                  {'directory': 'detection',
                   'name': 'vitpose-l-wholebody.onnx',
                   'url': 'https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/wholebody/vitpose-l-wholebody.onnx'},
                  {'directory': 'onnx/yolo',
                   'name': 'yolox_l.torchscript.pt',
                   'url': 'https://huggingface.co/hr16/yolox-onnx/resolve/main/yolox_l.torchscript.pt'},
                  {'directory': 'onnx/dwpose',
                   'name': 'dw-ll_ucoco_384_bs5.torchscript.pt',
                   'url': 'https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt'},
                  {'directory': 'vae/wanvideo',
                   'name': 'Wan2_1_VAE_bf16.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors'},
                  {'directory': 'text_encoders',
                   'name': 'umt5-xxl-enc-bf16.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors'},
                  {'directory': 'loras/WanVideo/Lightx2v',
                   'name': 'lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
                   'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'}],
 'ready_template': 'video/wanvideo_wrapper_22_wan_animate_preprocess_kijai',
 'runtime_note': 'Worker scratchpads patch reference image, motion video, prompt, seed, and output options.',
 'smoke_resolution': '832x480_motion_source',
 'source_role': 'materialized_kijai_reference_workflow',
 'source_url': 'https://raw.githubusercontent.com/kijai/ComfyUI-WanVideoWrapper/main/example_workflows/wanvideo_WanAnimate_preprocess_example_02.json',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wanvideo_WanAnimate_preprocess_example_02.json',
 'unbound_inputs': {'height': '151.widget_0',
                    'motion_video': '63.video',
                    'negative_prompt': '65.widget_3',
                    'prompt': '65.widget_2',
                    'reference_image': '57.widget_0',
                    'seed': '27.widget_3',
                    'steps': '27.widget_0',
                    'width': '150.widget_0'},
 'workflow_template': 'wanvideo_wrapper_22_wan_animate_preprocess_kijai'}

READY_REQUIREMENTS = {'custom_nodes': ['ComfyUI-KJNodes',
                  'ComfyUI-VideoHelperSuite',
                  'ComfyUI-WanAnimatePreprocess',
                  'ComfyUI-WanVideoWrapper',
                  'ComfyUI-segment-anything-2',
                  'comfyui_controlnet_aux',
                  'rgthree-comfy'],
 'models': [{'directory': 'diffusion_models/WanVideo/2_2',
             'name': 'Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors'},
            {'directory': 'loras/WanVideo',
             'name': 'WanAnimate_relight_lora_fp16.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors'},
            {'directory': 'clip_vision',
             'name': 'clip_vision_h.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors'},
            {'directory': 'sams',
             'name': 'sam2_hiera_base_plus.safetensors',
             'url': 'https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2_hiera_base_plus.safetensors'},
            {'directory': 'detection',
             'name': 'yolov10m.onnx',
             'url': 'https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx'},
            {'directory': 'detection',
             'name': 'vitpose-l-wholebody.onnx',
             'url': 'https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/wholebody/vitpose-l-wholebody.onnx'},
            {'directory': 'onnx/yolo',
             'name': 'yolox_l.torchscript.pt',
             'url': 'https://huggingface.co/hr16/yolox-onnx/resolve/main/yolox_l.torchscript.pt'},
            {'directory': 'onnx/dwpose',
             'name': 'dw-ll_ucoco_384_bs5.torchscript.pt',
             'url': 'https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt'},
            {'directory': 'vae/wanvideo',
             'name': 'Wan2_1_VAE_bf16.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors'},
            {'directory': 'text_encoders',
             'name': 'umt5-xxl-enc-bf16.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors'},
            {'directory': 'loras/WanVideo/Lightx2v',
             'name': 'lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'}],
 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes',
                       'source': 'git',
                       'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df',
                       'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'},
                      {'slug': 'ComfyUI-VideoHelperSuite',
                       'source': 'git',
                       'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'},
                      {'slug': 'ComfyUI-WanAnimatePreprocess',
                       'source': 'git',
                       'url': 'https://github.com/kijai/ComfyUI-WanAnimatePreprocess.git'},
                      {'slug': 'ComfyUI-WanVideoWrapper',
                       'source': 'git',
                       'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c',
                       'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'},
                      {'slug': 'ComfyUI-segment-anything-2',
                       'source': 'git',
                       'url': 'https://github.com/kijai/ComfyUI-segment-anything-2.git'},
                      {'slug': 'comfyui_controlnet_aux',
                       'source': 'git',
                       'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git'},
                      {'slug': 'rgthree-comfy',
                       'source': 'git',
                       'url': 'https://github.com/rgthree/rgthree-comfy.git'}]}


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
    wanvideoblockswap = _node(wf, 'WanVideoBlockSwap', '51',
        blocks_to_swap=25,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=0,
        prefetch_blocks=1,
        block_swap_debug=False,
    )
    loadimage = _node(wf, 'LoadImage', '57',
        image='refer.jpeg',
    )
    wanvideotextencodecached = _node(wf, 'WanVideoTextEncodeCached', '65',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        positive_prompt='man is walking, style is soft 3D render style, night time, moonlight',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        quantization='disabled',
        use_disk_cache=False,
        device='gpu',
    )
    clipvisionloader = _node(wf, 'CLIPVisionLoader', '71',
        clip_name='clip_vision_h.safetensors',
    )
    downloadandloadsam2model = _node(wf, 'DownloadAndLoadSAM2Model', '102',
        model='sam2.1_hiera_base_plus.safetensors',
        segmentor='video',
        device='cuda',
        precision='fp16',
    )
    wanvideocontextoptions = _node(wf, 'WanVideoContextOptions', '110',
        context_schedule='static_standard',
        context_frames=81,
        context_stride=4,
        context_overlap=32,
        freenoise=True,
        verbose=False,
        fuse_method='linear',
    )
    getnode = _node(wf, 'GetNode', '131',
        widget_0='background_image',
    )
    getnode_2 = _node(wf, 'GetNode', '133',
        widget_0='reference_image',
    )
    getnode_3 = _node(wf, 'GetNode', '134',
        widget_0='reference_image',
    )
    getnode_4 = _node(wf, 'GetNode', '137',
        widget_0='face_images',
    )
    getnode_5 = _node(wf, 'GetNode', '138',
        widget_0='face_images',
    )
    getnode_6 = _node(wf, 'GetNode', '140',
        widget_0='pose_images',
    )
    getnode_7 = _node(wf, 'GetNode', '141',
        widget_0='pose_images',
    )
    getnode_8 = _node(wf, 'GetNode', '143',
        widget_0='mask',
    )
    getnode_9 = _node(wf, 'GetNode', '145',
        widget_0='input_video',
    )
    getnode_10 = _node(wf, 'GetNode', '146',
        widget_0='input_video',
    )
    getnode_11 = _node(wf, 'GetNode', '149',
        widget_0='input_audio',
    )
    intconstant = _node(wf, 'INTConstant', '150',
        value=832,
    )
    intconstant_2 = _node(wf, 'INTConstant', '151',
        value=480,
    )
    getnode_12 = _node(wf, 'GetNode', '155',
        widget_0='width',
    )
    getnode_13 = _node(wf, 'GetNode', '156',
        widget_0='height',
    )
    getnode_14 = _node(wf, 'GetNode', '158',
        widget_0='frame_count',
    )
    getnode_15 = _node(wf, 'GetNode', '162',
        widget_0='VAE',
    )
    getnode_16 = _node(wf, 'GetNode', '163',
        widget_0='VAE',
    )
    wanvideoloraselectmulti = _node(wf, 'WanVideoLoraSelectMulti', '171',
        lora_0='WanVideo\\WanAnimate_relight_lora_fp16.safetensors',
        strength_0=1,
        lora_1='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        strength_1=1.2,
        lora_2='none',
        strength_2=1,
        lora_3='none',
        strength_3=1,
        lora_4='none',
        strength_4=1,
        low_mem_load=False,
        merge_loras=False,
    )
    onnxdetectionmodelloader = _node(wf, 'OnnxDetectionModelLoader', '178',
        vitpose_model='vitpose-l-wholebody.onnx',
        yolo_model='onnx\\yolov10m.onnx',
        onnx_device='CUDAExecutionProvider',
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\2_2\\Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        quantization='disabled',
        load_device='offload_device',
        attention_mode='sdpa',
        rms_norm_function='default',
        compile_args=wanvideotorchcompilesettings.out(0),
    )
    vhs_loadvideo = _node(wf, 'VHS_LoadVideo', '63',
        force_rate=16,
        format='AnimateDiff',
        frame_load_cap=0,
        select_every_nth=1,
        skip_first_frames=0,
        video='raw.mp4',
        videopreview={'hidden': False, 'params': {'custom_height': 544, 'custom_width': 960, 'filename': 'raw.mp4', 'force_rate': 16, 'format': 'video/mp4', 'frame_load_cap': 0, 'select_every_nth': 1, 'skip_first_frames': 0, 'type': 'input'}, 'paused': False},
        custom_height=intconstant_2.out(0),
        custom_width=intconstant.out(0),
        _extras={'choose video to upload': 'image'},
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '64',
        upscale_method='lanczos',
        keep_proportion='pad_edge_pixel',
        pad_color='0, 0, 0',
        crop_position='top',
        divisible_by=16,
        device='cpu',
        widget_0=832,
        widget_1=480,
        width=intconstant.out(0),
        height=intconstant_2.out(0),
        image=loadimage.out(0),
    )
    wanvideoclipvisionencode = _node(wf, 'WanVideoClipVisionEncode', '70',
        strength_1=1,
        strength_2=1,
        crop='center',
        combine_embeds='average',
        force_offload=True,
        tiles=0,
        ratio=0.5,
        clip_vision=clipvisionloader.out(0),
        image_1=getnode_2.out(0),
    )
    imageconcatmulti_2 = _node(wf, 'ImageConcatMulti', '77',
        inputcount=4,
        direction='down',
        match_image_size=True,
        unused_3=None,
        image_1=getnode_3.out(0),
        image_2=getnode_4.out(0),
        image_3=getnode_6.out(0),
        image_4=getnode_9.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '153',
        widget_0='width',
        INT=intconstant.out(0),
    )
    setnode_7 = _node(wf, 'SetNode', '154',
        widget_0='height',
        INT=intconstant_2.out(0),
    )
    setnode_9 = _node(wf, 'SetNode', '161',
        widget_0='VAE',
        WANVAE=wanvideovaeloader.out(0),
    )
    wanvideosetloras = _node(wf, 'WanVideoSetLoRAs', '48',
        lora=wanvideoloraselectmulti.out(0),
        model=wanvideomodelloader.out(0),
    )
    wanvideoanimateembeds = _node(wf, 'WanVideoAnimateEmbeds', '62',
        force_offload=False,
        frame_window_size=77,
        colormatch='disabled',
        face_strength=1,
        pose_strength=1,
        unused_8=False,
        widget_0=832,
        widget_1=480,
        widget_2=501,
        width=getnode_12.out(0),
        height=getnode_13.out(0),
        num_frames=getnode_14.out(0),
        bg_images=getnode.out(0),
        clip_embeds=wanvideoclipvisionencode.out(0),
        face_images=getnode_5.out(0),
        mask=getnode_8.out(0),
        pose_images=getnode_7.out(0),
        ref_images=getnode_2.out(0),
        vae=getnode_16.out(0),
    )
    setnode = _node(wf, 'SetNode', '128',
        widget_0='reference_image',
        IMAGE=imageresizekjv2.out(0),
    )
    setnode_4 = _node(wf, 'SetNode', '144',
        widget_0='input_video',
        IMAGE=vhs_loadvideo.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '148',
        widget_0='input_audio',
        AUDIO=vhs_loadvideo.out(2),
    )
    setnode_8 = _node(wf, 'SetNode', '157',
        widget_0='frame_count',
        INT=vhs_loadvideo.out(1),
    )
    wanvideosetblockswap = _node(wf, 'WanVideoSetBlockSwap', '50',
        block_swap_args=wanvideoblockswap.out(0),
        model=wanvideosetloras.out(0),
    )
    getimagesizeandcount_2 = _node(wf, 'GetImageSizeAndCount', '180',
        image=setnode_4.out(0),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '27',
        steps=4,
        cfg=1,
        shift=5,
        seed=42,
        force_offload=True,
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg='',
        rope_function='comfy',
        start_step=0,
        end_step=-1,
        add_noise_to_samples=False,
        image_embeds=wanvideoanimateembeds.out(0),
        model=wanvideosetblockswap.out(0),
        text_embeds=wanvideotextencodecached.out(0),
    )
    poseandfacedetection = _node(wf, 'PoseAndFaceDetection', '172',
        widget_0=832,
        widget_1=480,
        width=getimagesizeandcount_2.out(1),
        height=getimagesizeandcount_2.out(2),
        images=getimagesizeandcount_2.out(0),
        model=onnxdetectionmodelloader.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '28',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        normalization='default',
        samples=wanvideosampler.out(0),
        vae=getnode_15.out(0),
    )
    sam2segmentation = _node(wf, 'Sam2Segmentation', '104',
        keep_model_loaded=False,
        individual_objects=False,
        bboxes=poseandfacedetection.out(3),
        image=getimagesizeandcount_2.out(0),
        sam2_model=downloadandloadsam2model.out(0),
    )
    drawvitpose = _node(wf, 'DrawViTPose', '173',
        retarget_padding=16,
        body_stick_width=-1,
        hand_stick_width=-1,
        draw_head='True',
        widget_0=832,
        widget_1=480,
        width=getimagesizeandcount_2.out(1),
        height=getimagesizeandcount_2.out(2),
        pose_data=poseandfacedetection.out(0),
    )
    setnode_10 = _node(wf, 'SetNode', '183',
        widget_0='face_images',
        IMAGE=poseandfacedetection.out(1),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '42',
        image=wanvideodecode.out(0),
    )
    vhs_videocombine_3 = _node(wf, 'VHS_VideoCombine', '174',
        crf=19,
        filename_prefix='vitpose',
        format='video/h264-mp4',
        frame_rate=16,
        loop_count=0,
        pingpong=False,
        pix_fmt='yuv420p',
        save_metadata=True,
        save_output=False,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'vitpose_00004.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\vitpose_00004.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'vitpose_00004.png'}, 'paused': False},
        images=setnode_10.out(0),
    )
    growmaskwithblur = _node(wf, 'GrowMaskWithBlur', '182',
        expand=10,
        incremental_expandrate=0,
        tapered_corners=True,
        flip_input=False,
        blur_radius=0,
        lerp_alpha=1,
        decay_factor=1,
        unused_7=False,
        mask=sam2segmentation.out(0),
    )
    setnode_11 = _node(wf, 'SetNode', '184',
        widget_0='pose_images',
        IMAGE=drawvitpose.out(0),
    )
    imageconcatmulti = _node(wf, 'ImageConcatMulti', '66',
        inputcount=2,
        direction='left',
        match_image_size=True,
        unused_3=None,
        image_1=getimagesizeandcount.out(0),
        image_2=imageconcatmulti_2.out(0),
    )
    blockifymask = _node(wf, 'BlockifyMask', '108',
        block_size=32,
        masks=growmaskwithblur.out(0),
    )
    vhs_videocombine_4 = _node(wf, 'VHS_VideoCombine', '181',
        crf=19,
        filename_prefix='WanVideo2_1_T2V',
        format='video/h264-mp4',
        frame_rate=16,
        loop_count=0,
        pingpong=False,
        pix_fmt='yuv420p',
        save_metadata=True,
        save_output=False,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_1_T2V_00002.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_T2V_00002.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_1_T2V_00002.png'}, 'paused': False},
        images=setnode_11.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '30',
        crf=19,
        filename_prefix='Wanimate',
        format='video/h264-mp4',
        frame_rate=16,
        loop_count=0,
        pingpong=False,
        pix_fmt='yuv420p',
        save_metadata=True,
        save_output=True,
        trim_to_audio=True,
        videopreview={'hidden': False, 'params': {'filename': 'Wanimate_00002-audio.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\Wanimate_00002-audio.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'Wanimate_00002.png'}, 'paused': False},
        audio=getnode_11.out(0),
        images=imageconcatmulti.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '142',
        widget_0='mask',
        MASK=blockifymask.out(0),
    )
    drawmaskonimage = _node(wf, 'DrawMaskOnImage', '99',
        color='0, 0, 0',
        image=getnode_10.out(0),
        mask=setnode_3.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '130',
        widget_0='background_image',
        IMAGE=drawmaskonimage.out(0),
    )
    vhs_videocombine_2 = _node(wf, 'VHS_VideoCombine', '75',
        crf=19,
        filename_prefix='WanVideo2_1_T2V',
        format='video/h264-mp4',
        frame_rate=16,
        loop_count=0,
        pingpong=False,
        pix_fmt='yuv420p',
        save_metadata=True,
        save_output=False,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_1_T2V_00004.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_T2V_00004.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_1_T2V_00004.png'}, 'paused': False},
        images=setnode_2.out(0),
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
