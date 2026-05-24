# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'approach': 'Native ComfyUI Wan 2.2 Animate first-stage replacement workflow using DWPose, SAM2 masking, '
             'and native WanAnimateToVideo.',
 'capability': 'animate_character',
 'coverage_tier': 'production_parity_candidate',
 'ready_template': 'video/wan22_animate_native_first_stage',
 'runtime_note': 'Worker scratchpads patch reference image, motion video, prompt, negative prompt, seed, '
                 'steps, width, height, frame count, and output options.',
 'source_role': 'materialized_native_comfy_workflow',
 'source_url': 'https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_14B_animate.json',
 'unbound_inputs': {'height': '160.value',
                    'motion_video': '145.file',
                    'negative_prompt': '1.text',
                    'num_frames': '232:62.length',
                    'prompt': '21.text',
                    'reference_image': '10.image',
                    'seed': '232:63.seed',
                    'steps': '232:63.steps',
                    'width': '159.value'},
 'workflow_template': 'wan22_animate_native_first_stage'}

READY_REQUIREMENTS = {'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-segment-anything-2', 'comfyui_controlnet_aux'],
 'models': [{'directory': 'diffusion_models',
             'name': 'Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors'},
            {'directory': 'loras',
             'name': 'lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'},
            {'directory': 'loras',
             'name': 'WanAnimate_relight_lora_fp16.safetensors',
             'url': 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors'},
            {'directory': 'clip_vision',
             'name': 'clip_vision_h.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors'},
            {'directory': 'sam2',
             'name': 'sam2_hiera_base_plus.safetensors',
             'url': 'https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2_hiera_base_plus.safetensors'},
            {'directory': 'text_encoders',
             'name': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors'},
            {'directory': 'vae',
             'name': 'wan_2.1_vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors'},
            {'directory': 'onnx/yolo',
             'name': 'yolox_l.onnx',
             'url': 'https://huggingface.co/hr16/yolox-onnx/resolve/main/yolox_l.onnx'},
            {'directory': 'onnx/dwpose',
             'name': 'dw-ll_ucoco_384_bs5.torchscript.pt',
             'url': 'https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt'}]}


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

    cliploader = _node(wf, 'CLIPLoader', '2',
        clip_name='umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        type='wan',
        device='default',
    )
    vaeloader = _node(wf, 'VAELoader', '3',
        vae_name='wan_2.1_vae.safetensors',
    )
    clipvisionloader = _node(wf, 'CLIPVisionLoader', '4',
        clip_name='clip_vision_h.safetensors',
    )
    loadimage = _node(wf, 'LoadImage', '10',
        image='reference_image.png',
    )
    unetloader = _node(wf, 'UNETLoader', '20',
        unet_name='Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        weight_dtype='default',
    )
    downloadandloadsam2model = _node(wf, 'DownloadAndLoadSAM2Model', '108',
        model='sam2_hiera_base_plus.safetensors',
        segmentor='video',
        device='cuda',
        precision='fp16',
    )
    loadvideo = _node(wf, 'LoadVideo', '145',
        file='motion_video.mp4',
    )
    primitiveint = _node(wf, 'PrimitiveInt', '159',
        value=640,
    )
    primitiveint_2 = _node(wf, 'PrimitiveInt', '160',
        value=640,
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '1',
        text='overexposed, static, blurry details, captions, text, watermark, low quality, jpeg artifacts, ugly, deformed, disfigured, bad hands, bad face, malformed limbs, fused fingers, still frame, cluttered background',
        clip=cliploader.out(0),
    )
    clipvisionencode = _node(wf, 'CLIPVisionEncode', '9',
        crop='none',
        clip_vision=clipvisionloader.out(0),
        image=loadimage.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '18',
        lora_name='lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        strength_model=1,
        model=unetloader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '21',
        text='The character is dancing in the room',
        clip=cliploader.out(0),
    )
    getvideocomponents = _node(wf, 'GetVideoComponents', '23',
        video=loadvideo.out(0),
    )
    loraloadermodelonly_2 = _node(wf, 'LoraLoaderModelOnly', '99',
        lora_name='WanAnimate_relight_lora_fp16.safetensors',
        strength_model=1,
        model=loraloadermodelonly.out(0),
    )
    pixelperfectresolution = _node(wf, 'PixelPerfectResolution', '158',
        resize_mode='Just Resize',
        image_gen_height=primitiveint_2.out(0),
        image_gen_width=primitiveint.out(0),
        original_image=getvideocomponents.out(0),
    )
    imagescale = _node(wf, 'ImageScale', '212',
        upscale_method='lanczos',
        crop='center',
        width=primitiveint.out(0),
        height=primitiveint_2.out(0),
        image=getvideocomponents.out(0),
    )
    modelsamplingsd3 = _node(wf, 'ModelSamplingSD3', '60',
        shift=8,
        model=loraloadermodelonly_2.out(0),
    )
    dwpreprocessor = _node(wf, 'DWPreprocessor', '100',
        detect_hand='disable',
        detect_body='disable',
        detect_face='enable',
        bbox_detector='yolox_l.onnx',
        pose_estimator='dw-ll_ucoco_384_bs5.torchscript.pt',
        scale_stick_for_xinsr_cn='disable',
        resolution=pixelperfectresolution.out(0),
        image=imagescale.out(0),
    )
    dwpreprocessor_2 = _node(wf, 'DWPreprocessor', '101',
        detect_hand='enable',
        detect_body='enable',
        detect_face='disable',
        bbox_detector='yolox_l.onnx',
        pose_estimator='dw-ll_ucoco_384_bs5.torchscript.pt',
        scale_stick_for_xinsr_cn='disable',
        resolution=pixelperfectresolution.out(0),
        image=imagescale.out(0),
    )
    pointseditor = _node(wf, 'PointsEditor', '229',
        points_store='[{}]',
        coordinates='[{"x":320,"y":320}]',
        neg_coordinates='[]',
        bbox_store='[{}]',
        bboxes='[{"startX":160,"startY":96,"endX":480,"endY":544}]',
        bbox_format='xyxy',
        width=640,
        height=640,
        normalize=False,
        bg_image=imagescale.out(0),
    )
    sam2segmentation = _node(wf, 'Sam2Segmentation', '107',
        keep_model_loaded=True,
        individual_objects=False,
        coordinates_positive=pointseditor.out(0),
        image=imagescale.out(0),
        sam2_model=downloadandloadsam2model.out(0),
    )
    growmask = _node(wf, 'GrowMask', '274',
        expand=10,
        tapered_corners=True,
        mask=sam2segmentation.out(0),
    )
    blockifymask = _node(wf, 'BlockifyMask', '276',
        block_size=32,
        masks=growmask.out(0),
    )
    drawmaskonimage = _node(wf, 'DrawMaskOnImage', '275',
        color='0, 0, 0',
        image=imagescale.out(0),
        mask=blockifymask.out(0),
    )
    wananimatetovideo = _node(wf, 'WanAnimateToVideo', '232:62',
        batch_size=1,
        continue_motion_max_frames=5,
        length=77,
        video_frame_offset=0,
        background_video=drawmaskonimage.out(0),
        character_mask=blockifymask.out(0),
        clip_vision_output=clipvisionencode.out(0),
        face_video=dwpreprocessor.out(0),
        height=primitiveint_2.out(0),
        negative=cliptextencode.out(0),
        pose_video=dwpreprocessor_2.out(0),
        positive=cliptextencode_2.out(0),
        reference_image=loadimage.out(0),
        vae=vaeloader.out(0),
        width=primitiveint.out(0),
    )
    ksampler = _node(wf, 'KSampler', '232:63',
        seed=1106558644923357,
        steps=6,
        cfg=1,
        sampler_name='euler',
        scheduler='simple',
        denoise=1,
        latent_image=wananimatetovideo.out(2),
        model=modelsamplingsd3.out(0),
        negative=wananimatetovideo.out(1),
        positive=wananimatetovideo.out(0),
    )
    trimvideolatent = _node(wf, 'TrimVideoLatent', '232:57',
        samples=ksampler.out(0),
        trim_amount=wananimatetovideo.out(3),
    )
    vaedecode = _node(wf, 'VAEDecode', '232:58',
        samples=trimvideolatent.out(0),
        vae=vaeloader.out(0),
    )
    imagefrombatch = _node(wf, 'ImageFromBatch', '232:230',
        length=4096,
        batch_index=wananimatetovideo.out(4),
        image=vaedecode.out(0),
    )
    createvideo = _node(wf, 'CreateVideo', '232:15',
        fps=16,
        audio=getvideocomponents.out(1),
        images=imagefrombatch.out(0),
    )
    savevideo = _node(wf, 'SaveVideo', '19',
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
