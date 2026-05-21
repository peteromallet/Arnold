"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def GemmaAPITextEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    api_key: str | _Omitted = ...,
    prompt: str | _Omitted = ...,
    enhance_prompt: bool | _Omitted = ...,
    ckpt_name: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GuiderParameters(
    *args: VibeWorkflow,
    _id: str | None = ...,
    modality: Literal['VIDEO', 'AUDIO'] | _Omitted = ...,
    cfg: float | _Omitted = ...,
    stg: float | _Omitted = ...,
    perturb_attn: bool | _Omitted = ...,
    rescale: float | _Omitted = ...,
    modality_scale: float | _Omitted = ...,
    skip_step: int | _Omitted = ...,
    cross_attn: bool | _Omitted = ...,
    parameters: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXAddVideoICLoRAGuide(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    frame_idx: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    latent_downscale_factor: float | _Omitted = ...,
    crop: Any | _Omitted = ...,
    use_tiled_encode: bool | _Omitted = ...,
    tile_size: int | _Omitted = ...,
    tile_overlap: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXFloatToInt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    a: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXICLoRALoaderModelOnly(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    lora_name: Any | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddLatentGuide(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    guiding_latent: Any | _Omitted = ...,
    latent_idx: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVGemmaCLIPModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    gemma_path: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = ...,
    ltxv_path: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = ...,
    max_length: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVHDRDecodePostprocess(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    exposure: float | _Omitted = ...,
    save_exr: bool | _Omitted = ...,
    output_dir: str | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    half_precision: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVImgToVideoConditionOnly(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    bypass: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVPreprocessMasks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    invert_input_masks: bool | _Omitted = ...,
    ignore_first_mask: bool | _Omitted = ...,
    pooling_method: Literal['max', 'mean', 'min'] | _Omitted = ...,
    grow_mask: int | _Omitted = ...,
    tapered_corners: bool | _Omitted = ...,
    clamp_min: float | _Omitted = ...,
    clamp_max: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSetVideoLatentNoiseMasks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    masks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVTiledVAEDecode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    latents: Any | _Omitted = ...,
    horizontal_tiles: int | _Omitted = ...,
    vertical_tiles: int | _Omitted = ...,
    overlap: int | _Omitted = ...,
    last_frame_fix: bool | _Omitted = ...,
    working_device: Literal['cpu', 'auto'] | _Omitted = ...,
    working_dtype: Literal['float16', 'float32', 'auto'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LowVRAMAudioVAELoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = ...,
    dependencies: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LowVRAMCheckpointLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors'] | _Omitted = ...,
    dependencies: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MultimodalGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    parameters: Any | _Omitted = ...,
    skip_blocks: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
