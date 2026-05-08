# vibecomfy: manual
"""Native ComfyUI Wan 2.2 Animate workflow bundled as a VibeComfy ready template."""
from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


NEGATIVE_PROMPT = (
    "overexposed, static, blurry details, captions, text, watermark, low quality, jpeg artifacts, ugly, "
    "deformed, disfigured, bad hands, bad face, malformed limbs, fused fingers, still frame, cluttered background"
)


API_WORKFLOW = {
    "1": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": NEGATIVE_PROMPT}},
    "2": {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "device": "default",
            "type": "wan",
        },
    },
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
    "4": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "clip_vision_h.safetensors"}},
    "9": {
        "class_type": "CLIPVisionEncode",
        "inputs": {"clip_vision": ["4", 0], "crop": "none", "image": ["10", 0]},
    },
    "10": {"class_type": "LoadImage", "inputs": {"image": "reference_image.png"}},
    "18": {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {
            "lora_name": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
            "model": ["20", 0],
            "strength_model": 1,
        },
    },
    "19": {
        "class_type": "SaveVideo",
        "inputs": {"codec": "auto", "filename_prefix": "video/ComfyUI", "format": "auto", "video": ["232:15", 0]},
    },
    "20": {
        "class_type": "UNETLoader",
        "inputs": {"unet_name": "Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors", "weight_dtype": "default"},
    },
    "21": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "The character is dancing in the room"}},
    "23": {"class_type": "GetVideoComponents", "inputs": {"video": ["145", 0]}},
    "60": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["99", 0], "shift": 8}},
    "99": {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"lora_name": "WanAnimate_relight_lora_fp16.safetensors", "model": ["18", 0], "strength_model": 1},
    },
    "100": {
        "class_type": "DWPreprocessor",
        "inputs": {
            "bbox_detector": "yolox_l.onnx",
            "detect_body": "disable",
            "detect_face": "enable",
            "detect_hand": "disable",
            "image": ["212", 0],
            "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt",
            "resolution": ["158", 0],
            "scale_stick_for_xinsr_cn": "disable",
        },
    },
    "101": {
        "class_type": "DWPreprocessor",
        "inputs": {
            "bbox_detector": "yolox_l.onnx",
            "detect_body": "enable",
            "detect_face": "disable",
            "detect_hand": "enable",
            "image": ["212", 0],
            "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt",
            "resolution": ["158", 0],
            "scale_stick_for_xinsr_cn": "disable",
        },
    },
    "107": {
        "class_type": "Sam2Segmentation",
        "inputs": {
            "coordinates_positive": ["229", 0],
            "image": ["212", 0],
            "individual_objects": False,
            "keep_model_loaded": True,
            "sam2_model": ["108", 0],
        },
    },
    "108": {
        "class_type": "DownloadAndLoadSAM2Model",
        "inputs": {"device": "cuda", "model": "sam2_hiera_base_plus.safetensors", "precision": "fp16", "segmentor": "video"},
    },
    "145": {"class_type": "LoadVideo", "inputs": {"file": "motion_video.mp4"}},
    "158": {
        "class_type": "PixelPerfectResolution",
        "inputs": {
            "image_gen_height": ["160", 0],
            "image_gen_width": ["159", 0],
            "original_image": ["23", 0],
            "resize_mode": "Just Resize",
        },
    },
    "159": {"class_type": "PrimitiveInt", "inputs": {"value": 640}},
    "160": {"class_type": "PrimitiveInt", "inputs": {"value": 640}},
    "212": {
        "class_type": "ImageScale",
        "inputs": {"crop": "center", "height": ["160", 0], "image": ["23", 0], "upscale_method": "lanczos", "width": ["159", 0]},
    },
    "229": {
        "class_type": "PointsEditor",
        "inputs": {
            "bbox_format": "xyxy",
            "bg_image": ["212", 0],
            "bbox_store": "[{}]",
            "bboxes": '[{"startX":160,"startY":96,"endX":480,"endY":544}]',
            "coordinates": '[{"x":320,"y":320}]',
            "height": 640,
            "neg_coordinates": "[]",
            "normalize": False,
            "points_store": "[{}]",
            "width": 640,
        },
    },
    "232:15": {"class_type": "CreateVideo", "inputs": {"audio": ["23", 1], "fps": 16, "images": ["232:230", 0]}},
    "232:57": {"class_type": "TrimVideoLatent", "inputs": {"samples": ["232:63", 0], "trim_amount": ["232:62", 3]}},
    "232:58": {"class_type": "VAEDecode", "inputs": {"samples": ["232:57", 0], "vae": ["3", 0]}},
    "232:62": {
        "class_type": "WanAnimateToVideo",
        "inputs": {
            "background_video": ["275", 0],
            "batch_size": 1,
            "character_mask": ["276", 0],
            "clip_vision_output": ["9", 0],
            "continue_motion_max_frames": 5,
            "face_video": ["100", 0],
            "height": ["160", 0],
            "length": 77,
            "negative": ["1", 0],
            "pose_video": ["101", 0],
            "positive": ["21", 0],
            "reference_image": ["10", 0],
            "vae": ["3", 0],
            "video_frame_offset": 0,
            "width": ["159", 0],
        },
    },
    "232:63": {
        "class_type": "KSampler",
        "inputs": {
            "cfg": 1,
            "denoise": 1,
            "latent_image": ["232:62", 2],
            "model": ["60", 0],
            "negative": ["232:62", 1],
            "positive": ["232:62", 0],
            "sampler_name": "euler",
            "scheduler": "simple",
            "seed": 1106558644923357,
            "steps": 6,
        },
    },
    "232:230": {"class_type": "ImageFromBatch", "inputs": {"batch_index": ["232:62", 4], "image": ["232:58", 0], "length": 4096}},
    "274": {"class_type": "GrowMask", "inputs": {"expand": 10, "mask": ["107", 0], "tapered_corners": True}},
    "275": {"class_type": "DrawMaskOnImage", "inputs": {"color": "0, 0, 0", "image": ["212", 0], "mask": ["276", 0]}},
    "276": {"class_type": "BlockifyMask", "inputs": {"block_size": 32, "masks": ["274", 0]}},
}


READY_METADATA = {
    "approach": "Native ComfyUI Wan 2.2 Animate first-stage replacement workflow using DWPose, SAM2 masking, and native WanAnimateToVideo.",
    "capability": "animate_character",
    "coverage_tier": "production_parity_candidate",
    "ready_template": "video/wan22_animate_native_first_stage",
    "runtime_note": "Worker scratchpads patch reference image, motion video, prompt, negative prompt, seed, steps, width, height, and output options.",
    "source_role": "materialized_native_comfy_workflow",
    "source_url": "https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_14B_animate.json",
    "unbound_inputs": {
        "height": "160.value",
        "motion_video": "145.file",
        "negative_prompt": "1.text",
        "prompt": "21.text",
        "reference_image": "10.image",
        "seed": "232:63.seed",
        "steps": "232:63.steps",
        "width": "159.value",
    },
    "workflow_template": "wan22_animate_native_first_stage",
}


READY_REQUIREMENTS = {
    "custom_nodes": ["ComfyUI-KJNodes", "ComfyUI-segment-anything-2", "comfyui_controlnet_aux"],
    "models": [
        {
            "directory": "diffusion_models",
            "name": "Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
        },
        {
            "directory": "loras",
            "name": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
        },
        {
            "directory": "loras",
            "name": "WanAnimate_relight_lora_fp16.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors",
        },
        {
            "directory": "clip_vision",
            "name": "clip_vision_h.safetensors",
            "url": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors",
        },
        {
            "directory": "sams",
            "name": "sam2_hiera_base_plus.safetensors",
            "url": "https://huggingface.co/Kijai/sam2-safetensors/resolve/main/sam2_hiera_base_plus.safetensors",
        },
        {
            "directory": "text_encoders",
            "name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "url": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        },
        {
            "directory": "vae",
            "name": "wan_2.1_vae.safetensors",
            "url": "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors",
        },
        {
            "directory": "onnx/yolo",
            "name": "yolox_l.onnx",
            "url": "https://huggingface.co/hr16/yolox-onnx/resolve/main/yolox_l.onnx",
        },
        {
            "directory": "onnx/dwpose",
            "name": "dw-ll_ucoco_384_bs5.torchscript.pt",
            "url": "https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt",
        },
    ],
}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        READY_METADATA,
        source_path=__file__,
        workflow_id="video/wan22_animate_native_first_stage",
        requirements=READY_REQUIREMENTS,
    )
