"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def GemmaAPITextEncode(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    api_key: Any = _UNSET,
    prompt: Any = _UNSET,
    enhance_prompt: Any = _UNSET,
    ckpt_name: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Gemma API Text Encode
    
    Pack: ComfyUI-LTXVideo
    Returns: conditioning
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    modality: Any = _UNSET,
    cfg: Any = _UNSET,
    stg: Any = _UNSET,
    perturb_attn: Any = _UNSET,
    rescale: Any = _UNSET,
    modality_scale: Any = _UNSET,
    skip_step: Any = _UNSET,
    cross_attn: Any = _UNSET,
    parameters: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Guider Parameters
    
    Pack: ComfyUI-LTXVideo
    Returns: GUIDER_PARAMETERS
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    positive: Any = _UNSET,
    negative: Any = _UNSET,
    vae: Any = _UNSET,
    latent: Any = _UNSET,
    image: Any = _UNSET,
    frame_idx: Any = _UNSET,
    strength: Any = _UNSET,
    latent_downscale_factor: Any = _UNSET,
    crop: Any = _UNSET,
    use_tiled_encode: Any = _UNSET,
    tile_size: Any = _UNSET,
    tile_overlap: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds one or more conditioning frames starting at the specified frame index. Supports both single images and multi-frame videos. The latent_downscale_factor resizes input to a fraction of the target size (1 = original, 2 = half, 3 = third, etc.) for IC-LoRA on small grids.
    
    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    a: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Float To Int
    
    Pack: ComfyUI-LTXVideo
    Returns: INT
    """
    _kwargs: dict[str, Any] = {}
    if a is not _UNSET:
        _kwargs['a'] = a
    _kwargs.update(_extras)
    return node(wf, 'LTXFloatToInt', _id, pass_raw=pass_raw, **_kwargs)

def LTXICLoRALoaderModelOnly(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    lora_name: Any = _UNSET,
    strength_model: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads a LoRA model and extracts the latent_downscale_factor from the safetensors metadata.
    
    Pack: ComfyUI-LTXVideo
    Returns: model, latent_downscale_factor
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    vae: Any = _UNSET,
    positive: Any = _UNSET,
    negative: Any = _UNSET,
    latent: Any = _UNSET,
    guiding_latent: Any = _UNSET,
    latent_idx: Any = _UNSET,
    strength: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds a keyframe or a video segment at a specific frame index.
    
    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    gemma_path: Any = _UNSET,
    ltxv_path: Any = _UNSET,
    max_length: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Gemma 3 Model Loader
    
    Pack: ComfyUI-LTXVideo
    Returns: clip
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    image: Any = _UNSET,
    exposure: Any = _UNSET,
    save_exr: Any = _UNSET,
    output_dir: Any = _UNSET,
    filename_prefix: Any = _UNSET,
    half_precision: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Decompresses VAE-decoded output from HDR IC-LoRA (LogC3) and applies Reinhard tonemapping. Place after VAE Decode. 'tonemapped' is the SDR preview; 'hdr_linear' is raw linear HDR for downstream use. Enable 'save_exr' to write an EXR image sequence.if save_exr is enabled, make sure to set OPENCV_IO_ENABLE_OPENEXR=1 environment in the command line
    
    Pack: ComfyUI-LTXVideo
    Returns: tonemapped, hdr_linear
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    vae: Any = _UNSET,
    image: Any = _UNSET,
    latent: Any = _UNSET,
    strength: Any = _UNSET,
    bypass: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Applies image conditioning to the first frames of an existing latent. Creates a noise mask to control conditioning strength.
    
    Pack: ComfyUI-LTXVideo
    Returns: latent
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    masks: Any = _UNSET,
    vae: Any = _UNSET,
    invert_input_masks: Any = _UNSET,
    ignore_first_mask: Any = _UNSET,
    pooling_method: Any = _UNSET,
    grow_mask: Any = _UNSET,
    tapered_corners: Any = _UNSET,
    clamp_min: Any = _UNSET,
    clamp_max: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preprocess masks to be used for masking latents in the LTXVideo model.
    
    Pack: ComfyUI-LTXVideo
    Returns: MASK
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    samples: Any = _UNSET,
    masks: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Applies multiple masks to a video latent. masks can be 2D, 3D, or 4D tensors. If there are fewer masks than frames, the last mask will be reused.
    
    Pack: ComfyUI-LTXVideo
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    _kwargs.update(_extras)
    return node(wf, 'LTXVSetVideoLatentNoiseMasks', _id, pass_raw=pass_raw, **_kwargs)

def LTXVTiledVAEDecode(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    vae: Any = _UNSET,
    latents: Any = _UNSET,
    horizontal_tiles: Any = _UNSET,
    vertical_tiles: Any = _UNSET,
    overlap: Any = _UNSET,
    last_frame_fix: Any = _UNSET,
    working_device: Any = _UNSET,
    working_dtype: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Tiled VAE Decode
    
    Pack: ComfyUI-LTXVideo
    Returns: image
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    ckpt_name: Any = _UNSET,
    dependencies: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads an LTXV Audio VAE checkpoint with dependency support. Connect 'dependencies' to a previous loader's output to ensure sequential loading and reduce peak VRAM usage.
    
    Pack: ComfyUI-LTXVideo
    Returns: audio_vae
    """
    _kwargs: dict[str, Any] = {}
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    if dependencies is not _UNSET:
        _kwargs['dependencies'] = dependencies
    _kwargs.update(_extras)
    return node(wf, 'LowVRAMAudioVAELoader', _id, pass_raw=pass_raw, **_kwargs)

def LowVRAMCheckpointLoader(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    ckpt_name: Any = _UNSET,
    dependencies: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads a diffusion model checkpoint with dependency support. Connect 'dependencies' to a previous loader's output to ensure sequential loading and reduce peak VRAM usage.
    
    Pack: ComfyUI-LTXVideo
    Returns: MODEL, CLIP, VAE
    """
    _kwargs: dict[str, Any] = {}
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    if dependencies is not _UNSET:
        _kwargs['dependencies'] = dependencies
    _kwargs.update(_extras)
    return node(wf, 'LowVRAMCheckpointLoader', _id, pass_raw=pass_raw, **_kwargs)

def MultimodalGuider(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    positive: Any = _UNSET,
    negative: Any = _UNSET,
    parameters: Any = _UNSET,
    skip_blocks: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Multimodal Guider
    
    Pack: ComfyUI-LTXVideo
    Returns: GUIDER
    """
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
