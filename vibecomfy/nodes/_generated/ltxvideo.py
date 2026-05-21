"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.templates import _current_workflow_or_raise, node
from vibecomfy.workflow import VibeWorkflow

class _Omitted:
    pass

_UNSET = _Omitted()

def GemmaAPITextEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    api_key: str | _Omitted = _UNSET,
    prompt: str | _Omitted = _UNSET,
    enhance_prompt: bool | _Omitted = _UNSET,
    ckpt_name: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Gemma API Text Encode
    
    Pack: ComfyUI-LTXVideo
    Returns: conditioning
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GemmaAPITextEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if api_key is not _UNSET:
        _kwargs['api_key'] = api_key
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if enhance_prompt is not _UNSET:
        _kwargs['enhance_prompt'] = enhance_prompt
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    _kwargs.update(_extras)
    return node(wf, 'GemmaAPITextEncode', _id, pass_raw=pass_raw, **_kwargs)

def GuiderParameters(
    *args: VibeWorkflow,
    _id: str | None = None,
    modality: Literal['VIDEO', 'AUDIO'] | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    stg: float | _Omitted = _UNSET,
    perturb_attn: bool | _Omitted = _UNSET,
    rescale: float | _Omitted = _UNSET,
    modality_scale: float | _Omitted = _UNSET,
    skip_step: int | _Omitted = _UNSET,
    cross_attn: bool | _Omitted = _UNSET,
    parameters: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Guider Parameters
    
    Pack: ComfyUI-LTXVideo
    Returns: GUIDER_PARAMETERS
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GuiderParameters() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if modality is not _UNSET:
        _kwargs['modality'] = modality
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if stg is not _UNSET:
        _kwargs['stg'] = stg
    if perturb_attn is not _UNSET:
        _kwargs['perturb_attn'] = perturb_attn
    if rescale is not _UNSET:
        _kwargs['rescale'] = rescale
    if modality_scale is not _UNSET:
        _kwargs['modality_scale'] = modality_scale
    if skip_step is not _UNSET:
        _kwargs['skip_step'] = skip_step
    if cross_attn is not _UNSET:
        _kwargs['cross_attn'] = cross_attn
    if parameters is not _UNSET:
        _kwargs['parameters'] = parameters
    _kwargs.update(_extras)
    return node(wf, 'GuiderParameters', _id, pass_raw=pass_raw, **_kwargs)

def LTXAddVideoICLoRAGuide(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    frame_idx: int | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    latent_downscale_factor: float | _Omitted = _UNSET,
    crop: Any | _Omitted = _UNSET,
    use_tiled_encode: bool | _Omitted = _UNSET,
    tile_size: int | _Omitted = _UNSET,
    tile_overlap: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds one or more conditioning frames starting at the specified frame index. Supports both single images and multi-frame videos. The latent_downscale_factor resizes input to a fraction of the target size (1 = original, 2 = half, 3 = third, etc.) for IC-LoRA on small grids.
    
    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXAddVideoICLoRAGuide() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if image is not _UNSET:
        _kwargs['image'] = image
    if frame_idx is not _UNSET:
        _kwargs['frame_idx'] = frame_idx
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if latent_downscale_factor is not _UNSET:
        _kwargs['latent_downscale_factor'] = latent_downscale_factor
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if use_tiled_encode is not _UNSET:
        _kwargs['use_tiled_encode'] = use_tiled_encode
    if tile_size is not _UNSET:
        _kwargs['tile_size'] = tile_size
    if tile_overlap is not _UNSET:
        _kwargs['tile_overlap'] = tile_overlap
    _kwargs.update(_extras)
    return node(wf, 'LTXAddVideoICLoRAGuide', _id, pass_raw=pass_raw, **_kwargs)

def LTXFloatToInt(
    *args: VibeWorkflow,
    _id: str | None = None,
    a: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Float To Int
    
    Pack: ComfyUI-LTXVideo
    Returns: INT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXFloatToInt() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if a is not _UNSET:
        _kwargs['a'] = a
    _kwargs.update(_extras)
    return node(wf, 'LTXFloatToInt', _id, pass_raw=pass_raw, **_kwargs)

def LTXICLoRALoaderModelOnly(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    lora_name: Any | _Omitted = _UNSET,
    strength_model: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads a LoRA model and extracts the latent_downscale_factor from the safetensors metadata.
    
    Pack: ComfyUI-LTXVideo
    Returns: model, latent_downscale_factor
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXICLoRALoaderModelOnly() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if lora_name is not _UNSET:
        _kwargs['lora_name'] = lora_name
    if strength_model is not _UNSET:
        _kwargs['strength_model'] = strength_model
    _kwargs.update(_extras)
    return node(wf, 'LTXICLoRALoaderModelOnly', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAddLatentGuide(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    guiding_latent: Any | _Omitted = _UNSET,
    latent_idx: int | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds a keyframe or a video segment at a specific frame index.
    
    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAddLatentGuide() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if guiding_latent is not _UNSET:
        _kwargs['guiding_latent'] = guiding_latent
    if latent_idx is not _UNSET:
        _kwargs['latent_idx'] = latent_idx
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'LTXVAddLatentGuide', _id, pass_raw=pass_raw, **_kwargs)

def LTXVGemmaCLIPModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    gemma_path: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = _UNSET,
    ltxv_path: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = _UNSET,
    max_length: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Gemma 3 Model Loader
    
    Pack: ComfyUI-LTXVideo
    Returns: clip
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVGemmaCLIPModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if gemma_path is not _UNSET:
        _kwargs['gemma_path'] = gemma_path
    if ltxv_path is not _UNSET:
        _kwargs['ltxv_path'] = ltxv_path
    if max_length is not _UNSET:
        _kwargs['max_length'] = max_length
    _kwargs.update(_extras)
    return node(wf, 'LTXVGemmaCLIPModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def LTXVHDRDecodePostprocess(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    exposure: float | _Omitted = _UNSET,
    save_exr: bool | _Omitted = _UNSET,
    output_dir: str | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    half_precision: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Decompresses VAE-decoded output from HDR IC-LoRA (LogC3) and applies Reinhard tonemapping. Place after VAE Decode. 'tonemapped' is the SDR preview; 'hdr_linear' is raw linear HDR for downstream use. Enable 'save_exr' to write an EXR image sequence.if save_exr is enabled, make sure to set OPENCV_IO_ENABLE_OPENEXR=1 environment in the command line
    
    Pack: ComfyUI-LTXVideo
    Returns: tonemapped, hdr_linear
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVHDRDecodePostprocess() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if exposure is not _UNSET:
        _kwargs['exposure'] = exposure
    if save_exr is not _UNSET:
        _kwargs['save_exr'] = save_exr
    if output_dir is not _UNSET:
        _kwargs['output_dir'] = output_dir
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    if half_precision is not _UNSET:
        _kwargs['half_precision'] = half_precision
    _kwargs.update(_extras)
    return node(wf, 'LTXVHDRDecodePostprocess', _id, pass_raw=pass_raw, **_kwargs)

def LTXVImgToVideoConditionOnly(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    bypass: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Applies image conditioning to the first frames of an existing latent. Creates a noise mask to control conditioning strength.
    
    Pack: ComfyUI-LTXVideo
    Returns: latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVImgToVideoConditionOnly() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if image is not _UNSET:
        _kwargs['image'] = image
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if bypass is not _UNSET:
        _kwargs['bypass'] = bypass
    _kwargs.update(_extras)
    return node(wf, 'LTXVImgToVideoConditionOnly', _id, pass_raw=pass_raw, **_kwargs)

def LTXVPreprocessMasks(
    *args: VibeWorkflow,
    _id: str | None = None,
    masks: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    invert_input_masks: bool | _Omitted = _UNSET,
    ignore_first_mask: bool | _Omitted = _UNSET,
    pooling_method: Literal['max', 'mean', 'min'] | _Omitted = _UNSET,
    grow_mask: int | _Omitted = _UNSET,
    tapered_corners: bool | _Omitted = _UNSET,
    clamp_min: float | _Omitted = _UNSET,
    clamp_max: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preprocess masks to be used for masking latents in the LTXVideo model.
    
    Pack: ComfyUI-LTXVideo
    Returns: MASK
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVPreprocessMasks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if invert_input_masks is not _UNSET:
        _kwargs['invert_input_masks'] = invert_input_masks
    if ignore_first_mask is not _UNSET:
        _kwargs['ignore_first_mask'] = ignore_first_mask
    if pooling_method is not _UNSET:
        _kwargs['pooling_method'] = pooling_method
    if grow_mask is not _UNSET:
        _kwargs['grow_mask'] = grow_mask
    if tapered_corners is not _UNSET:
        _kwargs['tapered_corners'] = tapered_corners
    if clamp_min is not _UNSET:
        _kwargs['clamp_min'] = clamp_min
    if clamp_max is not _UNSET:
        _kwargs['clamp_max'] = clamp_max
    _kwargs.update(_extras)
    return node(wf, 'LTXVPreprocessMasks', _id, pass_raw=pass_raw, **_kwargs)

def LTXVSetVideoLatentNoiseMasks(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    masks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Applies multiple masks to a video latent. masks can be 2D, 3D, or 4D tensors. If there are fewer masks than frames, the last mask will be reused.
    
    Pack: ComfyUI-LTXVideo
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVSetVideoLatentNoiseMasks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    _kwargs.update(_extras)
    return node(wf, 'LTXVSetVideoLatentNoiseMasks', _id, pass_raw=pass_raw, **_kwargs)

def LTXVTiledVAEDecode(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    horizontal_tiles: int | _Omitted = _UNSET,
    vertical_tiles: int | _Omitted = _UNSET,
    overlap: int | _Omitted = _UNSET,
    last_frame_fix: bool | _Omitted = _UNSET,
    working_device: Literal['cpu', 'auto'] | _Omitted = _UNSET,
    working_dtype: Literal['float16', 'float32', 'auto'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Tiled VAE Decode
    
    Pack: ComfyUI-LTXVideo
    Returns: image
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVTiledVAEDecode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if horizontal_tiles is not _UNSET:
        _kwargs['horizontal_tiles'] = horizontal_tiles
    if vertical_tiles is not _UNSET:
        _kwargs['vertical_tiles'] = vertical_tiles
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if last_frame_fix is not _UNSET:
        _kwargs['last_frame_fix'] = last_frame_fix
    if working_device is not _UNSET:
        _kwargs['working_device'] = working_device
    if working_dtype is not _UNSET:
        _kwargs['working_dtype'] = working_dtype
    _kwargs.update(_extras)
    return node(wf, 'LTXVTiledVAEDecode', _id, pass_raw=pass_raw, **_kwargs)

def LowVRAMAudioVAELoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    ckpt_name: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = _UNSET,
    dependencies: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads an LTXV Audio VAE checkpoint with dependency support. Connect 'dependencies' to a previous loader's output to ensure sequential loading and reduce peak VRAM usage.
    
    Pack: ComfyUI-LTXVideo
    Returns: audio_vae
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LowVRAMAudioVAELoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    if dependencies is not _UNSET:
        _kwargs['dependencies'] = dependencies
    _kwargs.update(_extras)
    return node(wf, 'LowVRAMAudioVAELoader', _id, pass_raw=pass_raw, **_kwargs)

def LowVRAMCheckpointLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors'] | _Omitted = _UNSET,
    dependencies: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads a diffusion model checkpoint with dependency support. Connect 'dependencies' to a previous loader's output to ensure sequential loading and reduce peak VRAM usage.
    
    Pack: ComfyUI-LTXVideo
    Returns: MODEL, CLIP, VAE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LowVRAMCheckpointLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    if dependencies is not _UNSET:
        _kwargs['dependencies'] = dependencies
    _kwargs.update(_extras)
    return node(wf, 'LowVRAMCheckpointLoader', _id, pass_raw=pass_raw, **_kwargs)

def MultimodalGuider(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    parameters: Any | _Omitted = _UNSET,
    skip_blocks: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Multimodal Guider
    
    Pack: ComfyUI-LTXVideo
    Returns: GUIDER
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MultimodalGuider() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if parameters is not _UNSET:
        _kwargs['parameters'] = parameters
    if skip_blocks is not _UNSET:
        _kwargs['skip_blocks'] = skip_blocks
    _kwargs.update(_extras)
    return node(wf, 'MultimodalGuider', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['GemmaAPITextEncode', 'GuiderParameters', 'LTXAddVideoICLoRAGuide', 'LTXFloatToInt', 'LTXICLoRALoaderModelOnly', 'LTXVAddLatentGuide', 'LTXVGemmaCLIPModelLoader', 'LTXVHDRDecodePostprocess', 'LTXVImgToVideoConditionOnly', 'LTXVPreprocessMasks', 'LTXVSetVideoLatentNoiseMasks', 'LTXVTiledVAEDecode', 'LowVRAMAudioVAELoader', 'LowVRAMCheckpointLoader', 'MultimodalGuider']
