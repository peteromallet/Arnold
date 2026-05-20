# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Animate Character with Wan 2.2 Animate 14B Fp 8 E4m3fn Scaled Kj.

Public inputs:
    cfg: Classifier-free guidance scale
    sampler_name: Sampler algorithm

Output: unknown.

Packs:   ComfyUI-KJNodes, ComfyUI-segment-anything-2, comfyui_controlnet_aux
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {
    'wan2_2_animate_14b_fp8_e4m3fn_scaled_kj': ModelAsset(
        filename='Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        subdir='diffusion_models',
        sha256='2936b31473a967e7a429a6646bba60e7862d0938e178b58b2a140f391dd5b8e6',
        hf_revision='5571ff9d81a631ee97946a703e94911d63214c44',
        size_bytes=18401760586,
    ),
    'lightx2v_i2v_14b_480p_cfg_step_distill_ran': ModelAsset(
        filename='lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        subdir='',
    ),
    'wananimate_relight_lora_fp16': ModelAsset(
        filename='WanAnimate_relight_lora_fp16.safetensors',
        url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors',
        subdir='loras',
        sha256='fc646c74c73f4b251f5fd9bc440ef21b03b27305f499966c68b2b3aa31498561',
        hf_revision='87badb1f794c15daf51db60838a433ca08bb218f',
        size_bytes=1436672440,
    ),
    'clip_vision_h': ModelAsset(
        filename='clip_vision_h.safetensors',
        url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors',
        subdir='',
        hf_revision='main',
    ),
    'sam2_hiera_base_plus': ModelAsset(
        filename='sam2_hiera_base_plus.safetensors',
        url='https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2_hiera_base_plus.safetensors',
        subdir='',
    ),
    'umt5_xxl_fp8_e4m3fn_scaled': ModelAsset(
        filename='umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        subdir='',
        hf_revision='main',
    ),
    'wan_2_1_vae': ModelAsset(
        filename='wan_2.1_vae.safetensors',
        url='https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
        subdir='',
    ),
    'yolox_l': ModelAsset(
        filename='yolox_l.onnx',
        url='https://huggingface.co/hr16/yolox-onnx/resolve/main/yolox_l.onnx',
        subdir='',
    ),
    'dw_ll_ucoco_384_bs5_torchscript': ModelAsset(
        filename='dw-ll_ucoco_384_bs5.torchscript.pt',
        url='https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt',
        subdir='',
        hf_revision='main',
    ),
}

PUBLIC_INPUTS = {
    'cfg': InputSpec(node='232:63', field='cfg', default=1, type='INT', description='Classifier-free guidance scale.'),
    'sampler_name': InputSpec(node='232:63', field='sampler_name', default='euler', type='STRING', description='Sampler algorithm.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='wan22_animate_native_first_stage',
    capability='animate_character',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-segment-anything-2', 'comfyui_controlnet_aux'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-segment-anything-2', 'source': 'git',
                       'commit': '0c35fff5f382803e2310103357b5e985f5437f32', 'url': 'https://github.com/kijai/ComfyUI-segment-anything-2.git'}, {'slug': 'comfyui_controlnet_aux', 'source': 'git',
                       'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git'}]},
    provenance={'approach': 'Native ComfyUI Wan 2.2 Animate first-stage replacement workflow using DWPose, SAM2 masking, and native WanAnimateToVideo.', 'source_role': 'materialized_native_comfy_workflow'},
    coverage_tier='production_parity_candidate',
    runtime_note='Worker scratchpads patch reference image, motion video, prompt, negative prompt, seed, steps, width, height, frame count, and output options.',
    source_url='https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_14B_animate.json',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

READY_METADATA["unbound_inputs"].update({'num_frames': '232:62.length'})

PRIVATE_KNOBS = {
    'prompt': 'a person moving naturally, cinematic motion',
    'negative_prompt': 'low quality, blurry, distorted',
    'seed': 42,
    'steps': 20,
    'width': 832,
    'height': 480,
    'num_frames': 81,
}

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ LOADERS ════
    text_encoder = node(wf, 'CLIPLoader', '2',
        clip_name=MODELS['umt5_xxl_fp8_e4m3fn_scaled'].filename,
        type='wan',
        device='default',
    )
    vae = node(wf, 'VAELoader', '3',
        vae_name=MODELS['wan_2_1_vae'].filename,
    )
    clip_vision = node(wf, 'CLIPVisionLoader', '4',
        clip_name=MODELS['clip_vision_h'].filename,
    )
    # ════ SAMPLING ════
    input_image = node(wf, 'LoadImage', '10',
        image='reference_image.png',
    )
    base_diffusion_model = node(wf, 'UNETLoader', '20',
        unet_name=MODELS['wan2_2_animate_14b_fp8_e4m3fn_scaled_kj'].filename,
        weight_dtype='default',
    )
    download_and_load_s_a_m2_model_108 = node(wf, 'DownloadAndLoadSAM2Model', '108',
        model=MODELS['sam2_hiera_base_plus'].filename,
        segmentor='video',
        device='cuda',
        precision='fp16',
    )
    input_video = node(wf, 'LoadVideo', '145',
        file='motion_video.mp4',
    )
    param_int_159 = node(wf, 'PrimitiveInt', '159', value=PRIVATE_KNOBS['width'])
    param_int_2 = node(wf, 'PrimitiveInt', '160', value=PRIVATE_KNOBS['height'])
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '1',
        text=PRIVATE_KNOBS['negative_prompt'],
        clip=text_encoder.out('CLIP'),
    )
    clip_vision_features = node(wf, 'CLIPVisionEncode', '9',
        crop='none',
        clip_vision=clip_vision.out('CLIP_VISION'),
        image=input_image.out('IMAGE'),
    )
    # ════ MODEL PATCH STACK ════
    lora_18 = node(wf, 'LoraLoaderModelOnly', '18',
        lora_name=MODELS['lightx2v_i2v_14b_480p_cfg_step_distill_ran'].filename,
        strength_model=1,
        model=base_diffusion_model.out('MODEL'),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '21',
        text=PRIVATE_KNOBS['prompt'],
        clip=text_encoder.out('CLIP'),
    )
    # ════ IMAGE PREP ════
    video_components = node(wf, 'GetVideoComponents', '23',
        video=input_video.out('VIDEO'),
    )
    lora_2 = node(wf, 'LoraLoaderModelOnly', '99',
        lora_name=MODELS['wananimate_relight_lora_fp16'].filename,
        strength_model=1,
        model=lora_18.out('MODEL'),
    )
    pixel_perfect_resolution_158 = node(wf, 'PixelPerfectResolution', '158',
        resize_mode='Just Resize',
        image_gen_height=param_int_2.out('INT'),
        image_gen_width=param_int_159.out('INT'),
        original_image=video_components.out('IMAGES'),
    )
    image_scale_212 = node(wf, 'ImageScale', '212',
        upscale_method='lanczos',
        crop='center',
        width=param_int_159.out('INT'),
        height=param_int_2.out('INT'),
        image=video_components.out('IMAGES'),
    )
    model_sampling = node(wf, 'ModelSamplingSD3', '60',
        shift=8,
        model=lora_2.out('MODEL'),
    )
    # ════ CONTROL ════
    pose_estimated_100 = node(wf, 'DWPreprocessor', '100',
        detect_hand='disable',
        detect_body='disable',
        detect_face='enable',
        bbox_detector=MODELS['yolox_l'].filename,
        pose_estimator=MODELS['dw_ll_ucoco_384_bs5_torchscript'].filename,
        scale_stick_for_xinsr_cn='disable',
        resolution=pixel_perfect_resolution_158.out(0),
        image=image_scale_212.out(0),
    )
    pose_estimated_2 = node(wf, 'DWPreprocessor', '101',
        detect_hand='enable',
        detect_body='enable',
        detect_face='disable',
        bbox_detector=MODELS['yolox_l'].filename,
        pose_estimator=MODELS['dw_ll_ucoco_384_bs5_torchscript'].filename,
        scale_stick_for_xinsr_cn='disable',
        resolution=pixel_perfect_resolution_158.out(0),
        image=image_scale_212.out(0),
    )
    points_editor_229 = node(wf, 'PointsEditor', '229',
        points_store='[{}]',
        coordinates='[{"x":320,"y":320}]',
        neg_coordinates='[]',
        bbox_store='[{}]',
        bboxes='[{"startX":160,"startY":96,"endX":480,"endY":544}]',
        bbox_format='xyxy',
        width=640,
        height=640,
        normalize=False,
        bg_image=image_scale_212.out(0),
    )
    sam2_segmentation_107 = node(wf, 'Sam2Segmentation', '107',
        keep_model_loaded=True,
        individual_objects=False,
        coordinates_positive=points_editor_229.out(0),
        image=image_scale_212.out(0),
        sam2_model=download_and_load_s_a_m2_model_108.out(0),
    )
    grow_mask_274 = node(wf, 'GrowMask', '274',
        expand=10,
        tapered_corners=True,
        mask=sam2_segmentation_107.out(0),
    )
    blockify_mask_276 = node(wf, 'BlockifyMask', '276',
        block_size=32,
        masks=grow_mask_274.out(0),
    )
    draw_mask_on_image_275 = node(wf, 'DrawMaskOnImage', '275',
        color='0, 0, 0',
        image=image_scale_212.out(0),
        mask=blockify_mask_276.out(0),
    )
    wan_animate_to_video = node(wf, 'WanAnimateToVideo', '232:62',
        batch_size=1,
        continue_motion_max_frames=5,
        length=PRIVATE_KNOBS['num_frames'],
        video_frame_offset=0,
        background_video=draw_mask_on_image_275.out(0),
        character_mask=blockify_mask_276.out(0),
        clip_vision_output=clip_vision_features.out('CLIP_VISION_OUTPUT'),
        face_video=pose_estimated_100.out('IMAGE'),
        height=param_int_2.out('INT'),
        negative=negative_prompt.out('CONDITIONING'),
        pose_video=pose_estimated_2.out('IMAGE'),
        positive=positive_prompt.out('CONDITIONING'),
        reference_image=input_image.out('IMAGE'),
        vae=vae.out('VAE'),
        width=param_int_159.out('INT'),
    )
    sampler = node(wf, 'KSampler', '232:63',
        seed=PRIVATE_KNOBS['seed'],
        steps=PRIVATE_KNOBS['steps'],
        cfg=PUBLIC_INPUTS['cfg'].default,
        sampler_name=PUBLIC_INPUTS['sampler_name'].default,
        scheduler='simple',
        denoise=1,
        latent_image=wan_animate_to_video.out(2),
        model=model_sampling.out('MODEL'),
        negative=wan_animate_to_video.out(1),
        positive=wan_animate_to_video.out(0),
    )
    # ════ LATENT ════
    trim_video_latent = node(wf, 'TrimVideoLatent', '232:57',
        samples=sampler.out('LATENT'),
        trim_amount=wan_animate_to_video.out(3),
    )
    # ════ DECODE ════
    decoded_image = node(wf, 'VAEDecode', '232:58',
        samples=trim_video_latent.out(0),
        vae=vae.out('VAE'),
    )
    image_from_batch = node(wf, 'ImageFromBatch', '232:230',
        length=4096,
        batch_index=wan_animate_to_video.out(4),
        image=decoded_image.out('IMAGE'),
    )
    # ════ OUTPUT ════
    video = node(wf, 'CreateVideo', '232:15',
        fps=16,
        audio=video_components.out(1),
        images=image_from_batch.out(0),
    )
    saved_video = node(wf, 'SaveVideo', '19',
        filename_prefix='video/ComfyUI',
        format='auto',
        codec='auto',
        video=video.out('VIDEO'),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )
