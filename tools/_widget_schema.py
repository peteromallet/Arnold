"""Positional-widget schema for generated ready-template modules.

Each entry maps a class type to its ordered POSITIONAL WIDGET names — the
sequence ComfyUI's UI uses to populate `widgets_values`. Link-only inputs
(IMAGE, MODEL, LATENT, etc.) are NOT included; only widget-type inputs
(STRING, INT, FLOAT, BOOL, dropdown) count for positional indexing.

Cross-checked against `vendor/ComfyUI/comfy/nodes/base_nodes.py` and
`vendor/ComfyUI/comfy_extras/` `INPUT_TYPES` declarations.
"""

from __future__ import annotations

WIDGET_SCHEMA: dict[str, list[str]] = {
    # Stock samplers / guiders — only widget inputs (links omitted).
    "BasicScheduler": ["scheduler", "steps", "denoise"],
    "CFGGuider": ["cfg"],
    "CheckpointLoaderSimple": ["ckpt_name"],
    "CLIPLoader": ["clip_name", "type", "device"],
    "CLIPTextEncode": ["text"],
    "CLIPTextEncodeFlux": ["clip_l", "t5xxl", "guidance"],
    "CLIPTextEncodeSD3": ["clip_l", "clip_g", "t5xxl", "empty_padding"],
    "ConditioningSetTimestepRange": ["start", "end"],
    "CreateVideo": ["fps"],
    "DualCLIPLoader": ["clip_name1", "clip_name2", "type", "device"],
    "EmptyFlux2LatentImage": ["width", "height", "batch_size"],
    "EmptyHunyuanLatentVideo": ["width", "height", "length", "batch_size"],
    "EmptyLTXVLatentVideo": ["width", "height", "length", "batch_size"],
    "EmptySD3LatentImage": ["width", "height", "batch_size"],
    "FluxGuidance": ["guidance"],
    "Flux2Scheduler": ["steps"],
    "GetImageSize": [],
    "ImageResize": ["resize_mode", "resolutions", "interpolation", "aspect_ratio_tolerance"],
    "ImageScale": ["upscale_method", "width", "height", "crop"],
    "ImageScaleToTotalPixels": ["upscale_method", "megapixels", "resolution_steps"],
    "KSampler": [
        "seed",
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "denoise",
    ],
    "KSamplerAdvanced": [
        "add_noise",
        "noise_seed",
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "start_at_step",
        "end_at_step",
        "return_with_leftover_noise",
    ],
    "KSamplerSelect": ["sampler_name"],
    "LoadAudio": ["audio"],
    "LoadImage": ["image"],
    "LoraLoaderModelOnly": ["lora_name", "strength_model"],
    "ModelSamplingAuraFlow": ["shift"],
    "ModelSamplingFlux": ["max_shift", "base_shift", "width", "height"],
    "ModelSamplingSD3": ["shift"],
    "PrimitiveBoolean": ["value"],
    "PrimitiveFloat": ["value"],
    "PrimitiveInt": ["value"],
    "PrimitiveString": ["value"],
    "PrimitiveStringMultiline": ["value"],
    "RandomNoise": ["noise_seed", "control_after_generate"],
    "SamplerCustomAdvanced": [],
    "SaveAudio": ["filename_prefix"],
    "SaveAudioMP3": ["filename_prefix", "quality"],
    "SaveImage": ["filename_prefix"],
    "SaveVideo": ["filename_prefix", "format", "codec"],
    "TextEncodeQwenImageEdit": ["prompt"],
    "TripleCLIPLoader": ["clip_name1", "clip_name2", "clip_name3"],
    "UNETLoader": ["unet_name", "weight_dtype"],
    "VAEDecode": [],
    "VAEDecodeTiled": ["tile_size", "overlap", "temporal_size", "temporal_overlap"],
    "VAEEncode": [],
    "VAELoader": ["vae_name"],
}


def resolve_widget_name(class_type: str, idx: int) -> str:
    """Return the real input name for a positional widget, when known."""
    names = WIDGET_SCHEMA.get(class_type)
    if names is not None and 0 <= idx < len(names):
        return names[idx]
    return f"widget_{idx}"
