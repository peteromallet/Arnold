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
    ckpt_name: Any,
    api_key: Any = '',
    prompt: Any = '',
    enhance_prompt: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Gemma API Text Encode
    
    Pack: ComfyUI-LTXVideo
    Returns: conditioning
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['ckpt_name'] = ckpt_name
    _kwargs['api_key'] = api_key
    _kwargs['prompt'] = prompt
    _kwargs['enhance_prompt'] = enhance_prompt
    _kwargs.update(_extras)
    return node(wf, 'GemmaAPITextEncode', pass_raw=pass_raw, **_kwargs)

def GuiderParameters(
    wf: VibeWorkflow,
    *,
    modality: Any = 'VIDEO',
    cfg: Any = 1.0,
    stg: Any = 1.0,
    perturb_attn: Any = True,
    rescale: Any = 0.7,
    modality_scale: Any = 0.0,
    skip_step: Any = 0,
    cross_attn: Any = True,
    parameters: Any = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Guider Parameters
    
    Pack: ComfyUI-LTXVideo
    Returns: GUIDER_PARAMETERS
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['modality'] = modality
    _kwargs['cfg'] = cfg
    _kwargs['stg'] = stg
    _kwargs['perturb_attn'] = perturb_attn
    _kwargs['rescale'] = rescale
    _kwargs['modality_scale'] = modality_scale
    _kwargs['skip_step'] = skip_step
    _kwargs['cross_attn'] = cross_attn
    _kwargs['parameters'] = parameters
    _kwargs.update(_extras)
    return node(wf, 'GuiderParameters', pass_raw=pass_raw, **_kwargs)

def LTXAddVideoICLoRAGuide(
    wf: VibeWorkflow,
    *,
    positive: Any,
    negative: Any,
    vae: Any,
    latent: Any,
    image: Any,
    frame_idx: Any = 0,
    strength: Any = 1.0,
    latent_downscale_factor: Any = 1.0,
    crop: Any = 'disabled',
    use_tiled_encode: Any = False,
    tile_size: Any = 256,
    tile_overlap: Any = 64,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds one or more conditioning frames starting at the specified frame index. Supports both single images and multi-frame videos. The latent_downscale_factor resizes input to a fraction of the target size (1 = original, 2 = half, 3 = third, etc.) for IC-LoRA on small grids.
    
    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['vae'] = vae
    _kwargs['latent'] = latent
    _kwargs['image'] = image
    _kwargs['frame_idx'] = frame_idx
    _kwargs['strength'] = strength
    _kwargs['latent_downscale_factor'] = latent_downscale_factor
    _kwargs['crop'] = crop
    _kwargs['use_tiled_encode'] = use_tiled_encode
    _kwargs['tile_size'] = tile_size
    _kwargs['tile_overlap'] = tile_overlap
    _kwargs.update(_extras)
    return node(wf, 'LTXAddVideoICLoRAGuide', pass_raw=pass_raw, **_kwargs)

def LTXFloatToInt(
    wf: VibeWorkflow,
    *,
    a: Any = 0.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Float To Int
    
    Pack: ComfyUI-LTXVideo
    Returns: INT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['a'] = a
    _kwargs.update(_extras)
    return node(wf, 'LTXFloatToInt', pass_raw=pass_raw, **_kwargs)

def LTXICLoRALoaderModelOnly(
    wf: VibeWorkflow,
    *,
    model: Any,
    lora_name: Any,
    strength_model: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads a LoRA model and extracts the latent_downscale_factor from the safetensors metadata.
    
    Pack: ComfyUI-LTXVideo
    Returns: model, latent_downscale_factor
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['lora_name'] = lora_name
    _kwargs['strength_model'] = strength_model
    _kwargs.update(_extras)
    return node(wf, 'LTXICLoRALoaderModelOnly', pass_raw=pass_raw, **_kwargs)

def LTXVAddLatentGuide(
    wf: VibeWorkflow,
    *,
    vae: Any,
    positive: Any,
    negative: Any,
    latent: Any,
    guiding_latent: Any,
    latent_idx: Any = 0,
    strength: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds a keyframe or a video segment at a specific frame index.
    
    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae'] = vae
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['latent'] = latent
    _kwargs['guiding_latent'] = guiding_latent
    _kwargs['latent_idx'] = latent_idx
    _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'LTXVAddLatentGuide', pass_raw=pass_raw, **_kwargs)

def LTXVGemmaCLIPModelLoader(
    wf: VibeWorkflow,
    *,
    gemma_path: Any,
    ltxv_path: Any,
    max_length: Any = 1024,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Gemma 3 Model Loader
    
    Pack: ComfyUI-LTXVideo
    Returns: clip
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['gemma_path'] = gemma_path
    _kwargs['ltxv_path'] = ltxv_path
    _kwargs['max_length'] = max_length
    _kwargs.update(_extras)
    return node(wf, 'LTXVGemmaCLIPModelLoader', pass_raw=pass_raw, **_kwargs)

def LTXVHDRDecodePostprocess(
    wf: VibeWorkflow,
    *,
    image: Any,
    exposure: Any = 0.0,
    save_exr: Any = False,
    output_dir: Any = 'output/hdr_exr',
    filename_prefix: Any = 'frame',
    half_precision: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Decompresses VAE-decoded output from HDR IC-LoRA (LogC3) and applies Reinhard tonemapping. Place after VAE Decode. 'tonemapped' is the SDR preview; 'hdr_linear' is raw linear HDR for downstream use. Enable 'save_exr' to write an EXR image sequence.if save_exr is enabled, make sure to set OPENCV_IO_ENABLE_OPENEXR=1 environment in the command line
    
    Pack: ComfyUI-LTXVideo
    Returns: tonemapped, hdr_linear
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['exposure'] = exposure
    _kwargs['save_exr'] = save_exr
    _kwargs['output_dir'] = output_dir
    _kwargs['filename_prefix'] = filename_prefix
    _kwargs['half_precision'] = half_precision
    _kwargs.update(_extras)
    return node(wf, 'LTXVHDRDecodePostprocess', pass_raw=pass_raw, **_kwargs)

def LTXVImgToVideoConditionOnly(
    wf: VibeWorkflow,
    *,
    vae: Any,
    image: Any,
    latent: Any,
    strength: Any = 1.0,
    bypass: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Applies image conditioning to the first frames of an existing latent. Creates a noise mask to control conditioning strength.
    
    Pack: ComfyUI-LTXVideo
    Returns: latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae'] = vae
    _kwargs['image'] = image
    _kwargs['latent'] = latent
    _kwargs['strength'] = strength
    _kwargs['bypass'] = bypass
    _kwargs.update(_extras)
    return node(wf, 'LTXVImgToVideoConditionOnly', pass_raw=pass_raw, **_kwargs)

def LTXVPreprocessMasks(
    wf: VibeWorkflow,
    *,
    masks: Any,
    vae: Any,
    invert_input_masks: Any = False,
    ignore_first_mask: Any = True,
    pooling_method: Any = 'max',
    grow_mask: Any = 0,
    tapered_corners: Any = True,
    clamp_min: Any = 0.5,
    clamp_max: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preprocess masks to be used for masking latents in the LTXVideo model.
    
    Pack: ComfyUI-LTXVideo
    Returns: MASK
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['masks'] = masks
    _kwargs['vae'] = vae
    _kwargs['invert_input_masks'] = invert_input_masks
    _kwargs['ignore_first_mask'] = ignore_first_mask
    _kwargs['pooling_method'] = pooling_method
    _kwargs['grow_mask'] = grow_mask
    _kwargs['tapered_corners'] = tapered_corners
    _kwargs['clamp_min'] = clamp_min
    _kwargs['clamp_max'] = clamp_max
    _kwargs.update(_extras)
    return node(wf, 'LTXVPreprocessMasks', pass_raw=pass_raw, **_kwargs)

def LTXVSetVideoLatentNoiseMasks(
    wf: VibeWorkflow,
    *,
    samples: Any,
    masks: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Applies multiple masks to a video latent. masks can be 2D, 3D, or 4D tensors. If there are fewer masks than frames, the last mask will be reused.
    
    Pack: ComfyUI-LTXVideo
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['samples'] = samples
    _kwargs['masks'] = masks
    _kwargs.update(_extras)
    return node(wf, 'LTXVSetVideoLatentNoiseMasks', pass_raw=pass_raw, **_kwargs)

def LTXVTiledVAEDecode(
    wf: VibeWorkflow,
    *,
    vae: Any,
    latents: Any,
    horizontal_tiles: Any = 1,
    vertical_tiles: Any = 1,
    overlap: Any = 1,
    last_frame_fix: Any = False,
    working_device: Any = 'auto',
    working_dtype: Any = 'auto',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Tiled VAE Decode
    
    Pack: ComfyUI-LTXVideo
    Returns: image
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae'] = vae
    _kwargs['latents'] = latents
    _kwargs['horizontal_tiles'] = horizontal_tiles
    _kwargs['vertical_tiles'] = vertical_tiles
    _kwargs['overlap'] = overlap
    _kwargs['last_frame_fix'] = last_frame_fix
    _kwargs['working_device'] = working_device
    _kwargs['working_dtype'] = working_dtype
    _kwargs.update(_extras)
    return node(wf, 'LTXVTiledVAEDecode', pass_raw=pass_raw, **_kwargs)

def LowVRAMAudioVAELoader(
    wf: VibeWorkflow,
    *,
    ckpt_name: Any,
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
    _kwargs['ckpt_name'] = ckpt_name
    if dependencies is not _UNSET:
        _kwargs['dependencies'] = dependencies
    _kwargs.update(_extras)
    return node(wf, 'LowVRAMAudioVAELoader', pass_raw=pass_raw, **_kwargs)

def LowVRAMCheckpointLoader(
    wf: VibeWorkflow,
    *,
    ckpt_name: Any,
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
    _kwargs['ckpt_name'] = ckpt_name
    if dependencies is not _UNSET:
        _kwargs['dependencies'] = dependencies
    _kwargs.update(_extras)
    return node(wf, 'LowVRAMCheckpointLoader', pass_raw=pass_raw, **_kwargs)

def MultimodalGuider(
    wf: VibeWorkflow,
    *,
    model: Any,
    positive: Any,
    negative: Any,
    parameters: Any,
    skip_blocks: Any = '',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Multimodal Guider
    
    Pack: ComfyUI-LTXVideo
    Returns: GUIDER
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['parameters'] = parameters
    _kwargs['skip_blocks'] = skip_blocks
    _kwargs.update(_extras)
    return node(wf, 'MultimodalGuider', pass_raw=pass_raw, **_kwargs)

__all__ = ['GemmaAPITextEncode', 'GuiderParameters', 'LTXAddVideoICLoRAGuide', 'LTXFloatToInt', 'LTXICLoRALoaderModelOnly', 'LTXVAddLatentGuide', 'LTXVGemmaCLIPModelLoader', 'LTXVHDRDecodePostprocess', 'LTXVImgToVideoConditionOnly', 'LTXVPreprocessMasks', 'LTXVSetVideoLatentNoiseMasks', 'LTXVTiledVAEDecode', 'LowVRAMAudioVAELoader', 'LowVRAMCheckpointLoader', 'MultimodalGuider']
