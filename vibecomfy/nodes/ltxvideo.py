# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
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

def APGGuider(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    cfg_scale: float | _Omitted = _UNSET,
    eta: float | _Omitted = _UNSET,
    norm_threshold: float | _Omitted = _UNSET,
    momentum_coefficient: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    The APG Guider implements Adaptive Projected Guidance (APG).
        Reference: https://arxiv.org/abs/2410.02416.

    Pack: ComfyUI-LTXVideo
    Returns: GUIDER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"APGGuider() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if cfg_scale is not _UNSET:
        _kwargs['cfg_scale'] = cfg_scale
    if eta is not _UNSET:
        _kwargs['eta'] = eta
    if norm_threshold is not _UNSET:
        _kwargs['norm_threshold'] = norm_threshold
    if momentum_coefficient is not _UNSET:
        _kwargs['momentum_coefficient'] = momentum_coefficient
    _kwargs.update(_extras)
    return node(wf, 'APGGuider', _id, pass_raw=pass_raw, **_kwargs)

def DynamicConditioning(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    power: float | _Omitted = _UNSET,
    only_first_frame: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Dynamic Conditioning

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DynamicConditioning() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if power is not _UNSET:
        _kwargs['power'] = power
    if only_first_frame is not _UNSET:
        _kwargs['only_first_frame'] = only_first_frame
    _kwargs.update(_extras)
    return node(wf, 'DynamicConditioning', _id, pass_raw=pass_raw, **_kwargs)

def GemmaAPITextEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    api_key: str | _Omitted = _UNSET,
    prompt: str | _Omitted = _UNSET,
    enhance_prompt: bool | _Omitted = _UNSET,
    ckpt_name: Literal['ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = _UNSET,
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

def ImageToCPU(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Image to CPU

    Pack: ComfyUI-LTXVideo
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageToCPU() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'ImageToCPU', _id, pass_raw=pass_raw, **_kwargs)

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

def LTXAddVideoICLoRAGuideAdvanced(
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
    attention_strength: float | _Omitted = _UNSET,
    attention_mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds IC-LoRA guide conditioning with per-guide attention strength control. Same as LTXAddVideoICLoRAGuide, but allows controlling how strongly this guide influences generation via self-attention, optionally with a spatial mask.

    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXAddVideoICLoRAGuideAdvanced() takes at most 1 positional argument, got {len(args)}")
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
    if attention_strength is not _UNSET:
        _kwargs['attention_strength'] = attention_strength
    if attention_mask is not _UNSET:
        _kwargs['attention_mask'] = attention_mask
    _kwargs.update(_extras)
    return node(wf, 'LTXAddVideoICLoRAGuideAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def LTXAttentioOverride(
    *args: VibeWorkflow,
    _id: str | None = None,
    blocks: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Attn Block Override

    Pack: ComfyUI-LTXVideo
    Returns: LTX_BLOCKS

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXAttentioOverride() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    _kwargs.update(_extras)
    return node(wf, 'LTXAttentioOverride', _id, pass_raw=pass_raw, **_kwargs)

def LTXAttentionBank(
    *args: VibeWorkflow,
    _id: str | None = None,
    save_steps: int | _Omitted = _UNSET,
    blocks: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Attention Bank

    Pack: ComfyUI-LTXVideo
    Returns: ATTN_BANK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXAttentionBank() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if save_steps is not _UNSET:
        _kwargs['save_steps'] = save_steps
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    _kwargs.update(_extras)
    return node(wf, 'LTXAttentionBank', _id, pass_raw=pass_raw, **_kwargs)

def LTXAttnOverride(
    *args: VibeWorkflow,
    _id: str | None = None,
    layers: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Attention Override

    Pack: ComfyUI-LTXVideo
    Returns: ATTN_OVERRIDE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXAttnOverride() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if layers is not _UNSET:
        _kwargs['layers'] = layers
    _kwargs.update(_extras)
    return node(wf, 'LTXAttnOverride', _id, pass_raw=pass_raw, **_kwargs)

def LTXFetaEnhance(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    feta_weight: float | _Omitted = _UNSET,
    attn_override: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Feta Enhance

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXFetaEnhance() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if feta_weight is not _UNSET:
        _kwargs['feta_weight'] = feta_weight
    if attn_override is not _UNSET:
        _kwargs['attn_override'] = attn_override
    _kwargs.update(_extras)
    return node(wf, 'LTXFetaEnhance', _id, pass_raw=pass_raw, **_kwargs)

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

def LTXFlowEditCFGGuider(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    source_pos: Any | _Omitted = _UNSET,
    source_neg: Any | _Omitted = _UNSET,
    target_pos: Any | _Omitted = _UNSET,
    target_neg: Any | _Omitted = _UNSET,
    source_cfg: float | _Omitted = _UNSET,
    target_cfg: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Flow Edit CFG Guider

    Pack: ComfyUI-LTXVideo
    Returns: GUIDER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXFlowEditCFGGuider() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if source_pos is not _UNSET:
        _kwargs['source_pos'] = source_pos
    if source_neg is not _UNSET:
        _kwargs['source_neg'] = source_neg
    if target_pos is not _UNSET:
        _kwargs['target_pos'] = target_pos
    if target_neg is not _UNSET:
        _kwargs['target_neg'] = target_neg
    if source_cfg is not _UNSET:
        _kwargs['source_cfg'] = source_cfg
    if target_cfg is not _UNSET:
        _kwargs['target_cfg'] = target_cfg
    _kwargs.update(_extras)
    return node(wf, 'LTXFlowEditCFGGuider', _id, pass_raw=pass_raw, **_kwargs)

def LTXFlowEditSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    skip_steps: int | _Omitted = _UNSET,
    refine_steps: int | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Flow Edit Sampler

    Pack: ComfyUI-LTXVideo
    Returns: SAMPLER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXFlowEditSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if skip_steps is not _UNSET:
        _kwargs['skip_steps'] = skip_steps
    if refine_steps is not _UNSET:
        _kwargs['refine_steps'] = refine_steps
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'LTXFlowEditSampler', _id, pass_raw=pass_raw, **_kwargs)

def LTXForwardModelSamplingPred(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Forward Model Pred

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXForwardModelSamplingPred() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'LTXForwardModelSamplingPred', _id, pass_raw=pass_raw, **_kwargs)

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

def LTXPerturbedAttention(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    scale: float | _Omitted = _UNSET,
    rescale: float | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    attn_override: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Apply Perturbed Attention

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXPerturbedAttention() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if scale is not _UNSET:
        _kwargs['scale'] = scale
    if rescale is not _UNSET:
        _kwargs['rescale'] = rescale
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if attn_override is not _UNSET:
        _kwargs['attn_override'] = attn_override
    _kwargs.update(_extras)
    return node(wf, 'LTXPerturbedAttention', _id, pass_raw=pass_raw, **_kwargs)

def LTXPrepareAttnInjections(
    *args: VibeWorkflow,
    _id: str | None = None,
    latent: Any | _Omitted = _UNSET,
    attn_bank: Any | _Omitted = _UNSET,
    query: bool | _Omitted = _UNSET,
    key: bool | _Omitted = _UNSET,
    value: bool | _Omitted = _UNSET,
    inject_steps: int | _Omitted = _UNSET,
    blocks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Prepare Attn Injection

    Pack: ComfyUI-LTXVideo
    Returns: LATENT, ATTN_INJ

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXPrepareAttnInjections() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if attn_bank is not _UNSET:
        _kwargs['attn_bank'] = attn_bank
    if query is not _UNSET:
        _kwargs['query'] = query
    if key is not _UNSET:
        _kwargs['key'] = key
    if value is not _UNSET:
        _kwargs['value'] = value
    if inject_steps is not _UNSET:
        _kwargs['inject_steps'] = inject_steps
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    _kwargs.update(_extras)
    return node(wf, 'LTXPrepareAttnInjections', _id, pass_raw=pass_raw, **_kwargs)

def LTXQ8Patch(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    use_fp8_attention: bool | _Omitted = _UNSET,
    quantization_preset: Literal['0.9.8', 'ltxv2', 'full_bf16', 'custom'] | _Omitted = _UNSET,
    quantize_self_attn: bool | _Omitted = _UNSET,
    quantize_cross_attn: bool | _Omitted = _UNSET,
    quantize_ffn: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXQ8Patch

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXQ8Patch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if use_fp8_attention is not _UNSET:
        _kwargs['use_fp8_attention'] = use_fp8_attention
    if quantization_preset is not _UNSET:
        _kwargs['quantization_preset'] = quantization_preset
    if quantize_self_attn is not _UNSET:
        _kwargs['quantize_self_attn'] = quantize_self_attn
    if quantize_cross_attn is not _UNSET:
        _kwargs['quantize_cross_attn'] = quantize_cross_attn
    if quantize_ffn is not _UNSET:
        _kwargs['quantize_ffn'] = quantize_ffn
    _kwargs.update(_extras)
    return node(wf, 'LTXQ8Patch', _id, pass_raw=pass_raw, **_kwargs)

def LTXRFForwardODESampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    gamma: float | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    gamma_trend: Literal['linear_decrease', 'linear_increase', 'constant'] | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    attn_bank: Any | _Omitted = _UNSET,
    order: Literal['first', 'second'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Rf-Inv Forward Sampler

    Pack: ComfyUI-LTXVideo
    Returns: SAMPLER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXRFForwardODESampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if gamma is not _UNSET:
        _kwargs['gamma'] = gamma
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if gamma_trend is not _UNSET:
        _kwargs['gamma_trend'] = gamma_trend
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if attn_bank is not _UNSET:
        _kwargs['attn_bank'] = attn_bank
    if order is not _UNSET:
        _kwargs['order'] = order
    _kwargs.update(_extras)
    return node(wf, 'LTXRFForwardODESampler', _id, pass_raw=pass_raw, **_kwargs)

def LTXRFReverseODESampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    latent_image: Any | _Omitted = _UNSET,
    eta: float | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    eta_trend: Literal['linear_decrease', 'linear_increase', 'constant'] | _Omitted = _UNSET,
    attn_inj: Any | _Omitted = _UNSET,
    order: Literal['first', 'second'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Rf-Inv Reverse Sampler

    Pack: ComfyUI-LTXVideo
    Returns: SAMPLER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXRFReverseODESampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if latent_image is not _UNSET:
        _kwargs['latent_image'] = latent_image
    if eta is not _UNSET:
        _kwargs['eta'] = eta
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if eta_trend is not _UNSET:
        _kwargs['eta_trend'] = eta_trend
    if attn_inj is not _UNSET:
        _kwargs['attn_inj'] = attn_inj
    if order is not _UNSET:
        _kwargs['order'] = order
    _kwargs.update(_extras)
    return node(wf, 'LTXRFReverseODESampler', _id, pass_raw=pass_raw, **_kwargs)

def LTXReverseModelSamplingPred(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTX Reverse Model Pred

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXReverseModelSamplingPred() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'LTXReverseModelSamplingPred', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAdainLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    reference: Any | _Omitted = _UNSET,
    factor: float | _Omitted = _UNSET,
    per_frame: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Adain Latent

    Pack: ComfyUI-LTXVideo
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAdainLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if reference is not _UNSET:
        _kwargs['reference'] = reference
    if factor is not _UNSET:
        _kwargs['factor'] = factor
    if per_frame is not _UNSET:
        _kwargs['per_frame'] = per_frame
    _kwargs.update(_extras)
    return node(wf, 'LTXVAdainLatent', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAddGuideAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    frame_idx: int | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    crf: int | _Omitted = _UNSET,
    blur_radius: int | _Omitted = _UNSET,
    interpolation: Literal['lanczos', 'bislerp', 'nearest', 'bilinear', 'bicubic', 'area', 'nearest-exact'] | _Omitted = _UNSET,
    crop: Literal['center', 'disabled'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds a conditioning frame or a video at a specific frame index. This node is used to add a keyframe or a video segment which should appear in the generated video at a specified index. It resizes the image to the correct size and applies preprocessing to it.

    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAddGuideAdvanced() takes at most 1 positional argument, got {len(args)}")
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
    if crf is not _UNSET:
        _kwargs['crf'] = crf
    if blur_radius is not _UNSET:
        _kwargs['blur_radius'] = blur_radius
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    _kwargs.update(_extras)
    return node(wf, 'LTXVAddGuideAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAddGuideAdvancedAttention(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    frame_idx: int | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    crf: int | _Omitted = _UNSET,
    blur_radius: int | _Omitted = _UNSET,
    interpolation: Literal['lanczos', 'bislerp', 'nearest', 'bilinear', 'bicubic', 'area', 'nearest-exact'] | _Omitted = _UNSET,
    crop: Literal['center', 'disabled'] | _Omitted = _UNSET,
    attention_strength: float | _Omitted = _UNSET,
    attention_mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds a conditioning frame/video at a specific frame index with per-guide attention strength control. Same preprocessing as LTXVAddGuideAdvanced, plus attention_strength and optional spatial attention_mask.

    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAddGuideAdvancedAttention() takes at most 1 positional argument, got {len(args)}")
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
    if crf is not _UNSET:
        _kwargs['crf'] = crf
    if blur_radius is not _UNSET:
        _kwargs['blur_radius'] = blur_radius
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if attention_strength is not _UNSET:
        _kwargs['attention_strength'] = attention_strength
    if attention_mask is not _UNSET:
        _kwargs['attention_mask'] = attention_mask
    _kwargs.update(_extras)
    return node(wf, 'LTXVAddGuideAdvancedAttention', _id, pass_raw=pass_raw, **_kwargs)

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

def LTXVAddLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents1: Any | _Omitted = _UNSET,
    latents2: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Concatenates two video latents along the frames dimension. latents1 and latents2 must have the same dimensions except for the frames dimension.

    Pack: ComfyUI-LTXVideo
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAddLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents1 is not _UNSET:
        _kwargs['latents1'] = latents1
    if latents2 is not _UNSET:
        _kwargs['latents2'] = latents2
    _kwargs.update(_extras)
    return node(wf, 'LTXVAddLatents', _id, pass_raw=pass_raw, **_kwargs)

def LTXVApplySTG(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    block_indices: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Defines the blocks to apply the STG to.

    Pack: ComfyUI-LTXVideo
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVApplySTG() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if block_indices is not _UNSET:
        _kwargs['block_indices'] = block_indices
    _kwargs.update(_extras)
    return node(wf, 'LTXVApplySTG', _id, pass_raw=pass_raw, **_kwargs)

def LTXVBaseSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    guider: Any | _Omitted = _UNSET,
    sampler: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    noise: Any | _Omitted = _UNSET,
    optional_cond_images: Any | _Omitted = _UNSET,
    optional_cond_indices: str | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    crop: Literal['center', 'disabled'] | _Omitted = _UNSET,
    crf: int | _Omitted = _UNSET,
    blur: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Base Sampler

    Pack: ComfyUI-LTXVideo
    Returns: denoised, positive, negative

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVBaseSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if guider is not _UNSET:
        _kwargs['guider'] = guider
    if sampler is not _UNSET:
        _kwargs['sampler'] = sampler
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if noise is not _UNSET:
        _kwargs['noise'] = noise
    if optional_cond_images is not _UNSET:
        _kwargs['optional_cond_images'] = optional_cond_images
    if optional_cond_indices is not _UNSET:
        _kwargs['optional_cond_indices'] = optional_cond_indices
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if crf is not _UNSET:
        _kwargs['crf'] = crf
    if blur is not _UNSET:
        _kwargs['blur'] = blur
    _kwargs.update(_extras)
    return node(wf, 'LTXVBaseSampler', _id, pass_raw=pass_raw, **_kwargs)

def LTXVDilateLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    latent: Any | _Omitted = _UNSET,
    horizontal_scale: int | _Omitted = _UNSET,
    vertical_scale: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Dilates a latent by a grid size.

    Pack: ComfyUI-LTXVideo
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVDilateLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if horizontal_scale is not _UNSET:
        _kwargs['horizontal_scale'] = horizontal_scale
    if vertical_scale is not _UNSET:
        _kwargs['vertical_scale'] = vertical_scale
    _kwargs.update(_extras)
    return node(wf, 'LTXVDilateLatent', _id, pass_raw=pass_raw, **_kwargs)

def LTXVDilateVideoMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    spatial_radius: int | _Omitted = _UNSET,
    temporal_radius: int | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    image_as_mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Dilates a video mask spatially and/or temporally using separable max-pooling and thresholds the result.

    Pack: ComfyUI-LTXVideo
    Returns: mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVDilateVideoMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if spatial_radius is not _UNSET:
        _kwargs['spatial_radius'] = spatial_radius
    if temporal_radius is not _UNSET:
        _kwargs['temporal_radius'] = temporal_radius
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if image_as_mask is not _UNSET:
        _kwargs['image_as_mask'] = image_as_mask
    _kwargs.update(_extras)
    return node(wf, 'LTXVDilateVideoMask', _id, pass_raw=pass_raw, **_kwargs)

def LTXVDrawTracks(
    *args: VibeWorkflow,
    _id: str | None = None,
    tracks: str | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    GPU-accelerated sparse track renderer. Rasterises circles at high resolution and downscales with bilinear interpolation.

    Pack: ComfyUI-LTXVideo
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVDrawTracks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    _kwargs.update(_extras)
    return node(wf, 'LTXVDrawTracks', _id, pass_raw=pass_raw, **_kwargs)

def LTXVExtendSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    num_new_frames: int | _Omitted = _UNSET,
    frame_overlap: int | _Omitted = _UNSET,
    guider: Any | _Omitted = _UNSET,
    sampler: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    noise: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    optional_guiding_latents: Any | _Omitted = _UNSET,
    optional_cond_images: Any | _Omitted = _UNSET,
    optional_cond_indices: str | _Omitted = _UNSET,
    cond_image_strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Extend Sampler

    Pack: ComfyUI-LTXVideo
    Returns: denoised_video, positive, negative

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVExtendSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if num_new_frames is not _UNSET:
        _kwargs['num_new_frames'] = num_new_frames
    if frame_overlap is not _UNSET:
        _kwargs['frame_overlap'] = frame_overlap
    if guider is not _UNSET:
        _kwargs['guider'] = guider
    if sampler is not _UNSET:
        _kwargs['sampler'] = sampler
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if noise is not _UNSET:
        _kwargs['noise'] = noise
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if optional_guiding_latents is not _UNSET:
        _kwargs['optional_guiding_latents'] = optional_guiding_latents
    if optional_cond_images is not _UNSET:
        _kwargs['optional_cond_images'] = optional_cond_images
    if optional_cond_indices is not _UNSET:
        _kwargs['optional_cond_indices'] = optional_cond_indices
    if cond_image_strength is not _UNSET:
        _kwargs['cond_image_strength'] = cond_image_strength
    _kwargs.update(_extras)
    return node(wf, 'LTXVExtendSampler', _id, pass_raw=pass_raw, **_kwargs)

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

def LTXVGemmaEnhancePrompt(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip: Any | _Omitted = _UNSET,
    prompt: str | _Omitted = _UNSET,
    system_prompt: str | _Omitted = _UNSET,
    max_tokens: int | _Omitted = _UNSET,
    bypass_i2v: bool | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Enhance text prompts using Gemma 3 VLLM for improved video generation.

    Pack: ComfyUI-LTXVideo
    Returns: enhanced_prompt

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVGemmaEnhancePrompt() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if system_prompt is not _UNSET:
        _kwargs['system_prompt'] = system_prompt
    if max_tokens is not _UNSET:
        _kwargs['max_tokens'] = max_tokens
    if bypass_i2v is not _UNSET:
        _kwargs['bypass_i2v'] = bypass_i2v
    if image is not _UNSET:
        _kwargs['image'] = image
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'LTXVGemmaEnhancePrompt', _id, pass_raw=pass_raw, **_kwargs)

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

def LTXVImgToVideoAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    length: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    crf: int | _Omitted = _UNSET,
    blur_radius: int | _Omitted = _UNSET,
    interpolation: Literal['lanczos', 'bislerp', 'nearest', 'bilinear', 'bicubic', 'area', 'nearest-exact'] | _Omitted = _UNSET,
    crop: Literal['center', 'disabled'] | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds a conditioning frame or a video at index 0. This node is used to add a keyframe or a video segment which should appear in the generated video at index 0. It resizes the image to the correct size and applies preprocessing to it.

    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVImgToVideoAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if image is not _UNSET:
        _kwargs['image'] = image
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if length is not _UNSET:
        _kwargs['length'] = length
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if crf is not _UNSET:
        _kwargs['crf'] = crf
    if blur_radius is not _UNSET:
        _kwargs['blur_radius'] = blur_radius
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'LTXVImgToVideoAdvanced', _id, pass_raw=pass_raw, **_kwargs)

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

def LTXVInContextSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    guider: Any | _Omitted = _UNSET,
    sampler: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    noise: Any | _Omitted = _UNSET,
    guiding_latents: Any | _Omitted = _UNSET,
    optional_cond_images: Any | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV In Context Sampler

    Pack: ComfyUI-LTXVideo
    Returns: denoised_video, positive, negative

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVInContextSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if guider is not _UNSET:
        _kwargs['guider'] = guider
    if sampler is not _UNSET:
        _kwargs['sampler'] = sampler
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if noise is not _UNSET:
        _kwargs['noise'] = noise
    if guiding_latents is not _UNSET:
        _kwargs['guiding_latents'] = guiding_latents
    if optional_cond_images is not _UNSET:
        _kwargs['optional_cond_images'] = optional_cond_images
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    _kwargs.update(_extras)
    return node(wf, 'LTXVInContextSampler', _id, pass_raw=pass_raw, **_kwargs)

def LTXVInpaintPreprocess(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Composites images with a green background where mask is active, for inpainting conditioning.

    Pack: ComfyUI-LTXVideo
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVInpaintPreprocess() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'LTXVInpaintPreprocess', _id, pass_raw=pass_raw, **_kwargs)

def LTXVLaplacianPyramidBlend(
    *args: VibeWorkflow,
    _id: str | None = None,
    image_a: Any | _Omitted = _UNSET,
    image_b: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    trim_to_shortest: bool | _Omitted = _UNSET,
    mask_low_res_dilation: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Blend two images seamlessly using Laplacian pyramid blending.

    Pack: ComfyUI-LTXVideo
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVLaplacianPyramidBlend() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image_a is not _UNSET:
        _kwargs['image_a'] = image_a
    if image_b is not _UNSET:
        _kwargs['image_b'] = image_b
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if trim_to_shortest is not _UNSET:
        _kwargs['trim_to_shortest'] = trim_to_shortest
    if mask_low_res_dilation is not _UNSET:
        _kwargs['mask_low_res_dilation'] = mask_low_res_dilation
    _kwargs.update(_extras)
    return node(wf, 'LTXVLaplacianPyramidBlend', _id, pass_raw=pass_raw, **_kwargs)

def LTXVLinearOverlapLatentTransition(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples1: Any | _Omitted = _UNSET,
    samples2: Any | _Omitted = _UNSET,
    overlap: int | _Omitted = _UNSET,
    axis: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Linear Overlap Latent Transition

    Pack: ComfyUI-LTXVideo
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVLinearOverlapLatentTransition() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples1 is not _UNSET:
        _kwargs['samples1'] = samples1
    if samples2 is not _UNSET:
        _kwargs['samples2'] = samples2
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if axis is not _UNSET:
        _kwargs['axis'] = axis
    _kwargs.update(_extras)
    return node(wf, 'LTXVLinearOverlapLatentTransition', _id, pass_raw=pass_raw, **_kwargs)

def LTXVLoadConditioning(
    *args: VibeWorkflow,
    _id: str | None = None,
    file_name: Any | _Omitted = _UNSET,
    device: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Load Conditioning

    Pack: ComfyUI-LTXVideo
    Returns: CONDITIONING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVLoadConditioning() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if file_name is not _UNSET:
        _kwargs['file_name'] = file_name
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'LTXVLoadConditioning', _id, pass_raw=pass_raw, **_kwargs)

def LTXVLoopingSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    noise: Any | _Omitted = _UNSET,
    sampler: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    guider: Any | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    temporal_tile_size: int | _Omitted = _UNSET,
    temporal_overlap: int | _Omitted = _UNSET,
    guiding_strength: float | _Omitted = _UNSET,
    temporal_overlap_cond_strength: float | _Omitted = _UNSET,
    cond_image_strength: float | _Omitted = _UNSET,
    horizontal_tiles: int | _Omitted = _UNSET,
    vertical_tiles: int | _Omitted = _UNSET,
    spatial_overlap: int | _Omitted = _UNSET,
    optional_cond_images: Any | _Omitted = _UNSET,
    optional_guiding_latents: Any | _Omitted = _UNSET,
    adain_factor: float | _Omitted = _UNSET,
    optional_positive_conditionings: Any | _Omitted = _UNSET,
    optional_negative_index_latents: Any | _Omitted = _UNSET,
    guiding_start_step: int | _Omitted = _UNSET,
    guiding_end_step: int | _Omitted = _UNSET,
    optional_cond_image_indices: str | _Omitted = _UNSET,
    optional_normalizing_latents: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Looping Sampler

    Pack: ComfyUI-LTXVideo
    Returns: denoised_output

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVLoopingSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if noise is not _UNSET:
        _kwargs['noise'] = noise
    if sampler is not _UNSET:
        _kwargs['sampler'] = sampler
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if guider is not _UNSET:
        _kwargs['guider'] = guider
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if temporal_tile_size is not _UNSET:
        _kwargs['temporal_tile_size'] = temporal_tile_size
    if temporal_overlap is not _UNSET:
        _kwargs['temporal_overlap'] = temporal_overlap
    if guiding_strength is not _UNSET:
        _kwargs['guiding_strength'] = guiding_strength
    if temporal_overlap_cond_strength is not _UNSET:
        _kwargs['temporal_overlap_cond_strength'] = temporal_overlap_cond_strength
    if cond_image_strength is not _UNSET:
        _kwargs['cond_image_strength'] = cond_image_strength
    if horizontal_tiles is not _UNSET:
        _kwargs['horizontal_tiles'] = horizontal_tiles
    if vertical_tiles is not _UNSET:
        _kwargs['vertical_tiles'] = vertical_tiles
    if spatial_overlap is not _UNSET:
        _kwargs['spatial_overlap'] = spatial_overlap
    if optional_cond_images is not _UNSET:
        _kwargs['optional_cond_images'] = optional_cond_images
    if optional_guiding_latents is not _UNSET:
        _kwargs['optional_guiding_latents'] = optional_guiding_latents
    if adain_factor is not _UNSET:
        _kwargs['adain_factor'] = adain_factor
    if optional_positive_conditionings is not _UNSET:
        _kwargs['optional_positive_conditionings'] = optional_positive_conditionings
    if optional_negative_index_latents is not _UNSET:
        _kwargs['optional_negative_index_latents'] = optional_negative_index_latents
    if guiding_start_step is not _UNSET:
        _kwargs['guiding_start_step'] = guiding_start_step
    if guiding_end_step is not _UNSET:
        _kwargs['guiding_end_step'] = guiding_end_step
    if optional_cond_image_indices is not _UNSET:
        _kwargs['optional_cond_image_indices'] = optional_cond_image_indices
    if optional_normalizing_latents is not _UNSET:
        _kwargs['optional_normalizing_latents'] = optional_normalizing_latents
    _kwargs.update(_extras)
    return node(wf, 'LTXVLoopingSampler', _id, pass_raw=pass_raw, **_kwargs)

def LTXVMultiPromptProvider(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompts: str | _Omitted = _UNSET,
    clip: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Multi Prompt Provider

    Pack: ComfyUI-LTXVideo
    Returns: conditionings

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVMultiPromptProvider() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompts is not _UNSET:
        _kwargs['prompts'] = prompts
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    _kwargs.update(_extras)
    return node(wf, 'LTXVMultiPromptProvider', _id, pass_raw=pass_raw, **_kwargs)

def LTXVNormalizingSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    noise: Any | _Omitted = _UNSET,
    guider: Any | _Omitted = _UNSET,
    sampler: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    latent_image: Any | _Omitted = _UNSET,
    video_normalization_factors: str | _Omitted = _UNSET,
    audio_normalization_factors: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Normalizing Sampler

    Pack: ComfyUI-LTXVideo
    Returns: denoised_output

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVNormalizingSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if noise is not _UNSET:
        _kwargs['noise'] = noise
    if guider is not _UNSET:
        _kwargs['guider'] = guider
    if sampler is not _UNSET:
        _kwargs['sampler'] = sampler
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if latent_image is not _UNSET:
        _kwargs['latent_image'] = latent_image
    if video_normalization_factors is not _UNSET:
        _kwargs['video_normalization_factors'] = video_normalization_factors
    if audio_normalization_factors is not _UNSET:
        _kwargs['audio_normalization_factors'] = audio_normalization_factors
    _kwargs.update(_extras)
    return node(wf, 'LTXVNormalizingSampler', _id, pass_raw=pass_raw, **_kwargs)

def LTXVPatcherVAE(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Patcher VAE

    Pack: ComfyUI-LTXVideo
    Returns: VAE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVPatcherVAE() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'LTXVPatcherVAE', _id, pass_raw=pass_raw, **_kwargs)

def LTXVPerStepAdainPatcher(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    factors: str | _Omitted = _UNSET,
    reference: Any | _Omitted = _UNSET,
    per_frame: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Per Step Adain Patcher

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVPerStepAdainPatcher() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if factors is not _UNSET:
        _kwargs['factors'] = factors
    if reference is not _UNSET:
        _kwargs['reference'] = reference
    if per_frame is not _UNSET:
        _kwargs['per_frame'] = per_frame
    _kwargs.update(_extras)
    return node(wf, 'LTXVPerStepAdainPatcher', _id, pass_raw=pass_raw, **_kwargs)

def LTXVPerStepStatNormPatcher(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    factors: str | _Omitted = _UNSET,
    target_mean: float | _Omitted = _UNSET,
    target_std: float | _Omitted = _UNSET,
    percentile: float | _Omitted = _UNSET,
    clip_outliers: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Per Step Stat Norm Patcher

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVPerStepStatNormPatcher() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if factors is not _UNSET:
        _kwargs['factors'] = factors
    if target_mean is not _UNSET:
        _kwargs['target_mean'] = target_mean
    if target_std is not _UNSET:
        _kwargs['target_std'] = target_std
    if percentile is not _UNSET:
        _kwargs['percentile'] = percentile
    if clip_outliers is not _UNSET:
        _kwargs['clip_outliers'] = clip_outliers
    _kwargs.update(_extras)
    return node(wf, 'LTXVPerStepStatNormPatcher', _id, pass_raw=pass_raw, **_kwargs)

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

def LTXVPromptEnhancer(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt: str | _Omitted = _UNSET,
    prompt_enhancer: Any | _Omitted = _UNSET,
    max_resulting_tokens: int | _Omitted = _UNSET,
    image_prompt: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Enhances text prompts for image generation using LLMs. Optionally incorporates reference images to create more contextually relevant descriptions.

    Pack: ComfyUI-LTXVideo
    Returns: str

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVPromptEnhancer() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if prompt_enhancer is not _UNSET:
        _kwargs['prompt_enhancer'] = prompt_enhancer
    if max_resulting_tokens is not _UNSET:
        _kwargs['max_resulting_tokens'] = max_resulting_tokens
    if image_prompt is not _UNSET:
        _kwargs['image_prompt'] = image_prompt
    _kwargs.update(_extras)
    return node(wf, 'LTXVPromptEnhancer', _id, pass_raw=pass_raw, **_kwargs)

def LTXVPromptEnhancerLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    llm_name: str | _Omitted = _UNSET,
    image_captioner_name: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Downloads and initializes LLM and image captioning models from Hugging Face to enhance text prompts for image generation.

    Pack: ComfyUI-LTXVideo
    Returns: prompt_enhancer

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVPromptEnhancerLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if llm_name is not _UNSET:
        _kwargs['llm_name'] = llm_name
    if image_captioner_name is not _UNSET:
        _kwargs['image_captioner_name'] = image_captioner_name
    _kwargs.update(_extras)
    return node(wf, 'LTXVPromptEnhancerLoader', _id, pass_raw=pass_raw, **_kwargs)

def LTXVQ8LoraModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    lora_name: Literal['ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength_model: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXVQ8Lora Model Loader

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVQ8LoraModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if lora_name is not _UNSET:
        _kwargs['lora_name'] = lora_name
    if strength_model is not _UNSET:
        _kwargs['strength_model'] = strength_model
    _kwargs.update(_extras)
    return node(wf, 'LTXVQ8LoraModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def LTXVSaveConditioning(
    *args: VibeWorkflow,
    _id: str | None = None,
    conditioning: Any | _Omitted = _UNSET,
    filename: str | _Omitted = _UNSET,
    dtype: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Save Conditioning

    Pack: ComfyUI-LTXVideo
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVSaveConditioning() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if conditioning is not _UNSET:
        _kwargs['conditioning'] = conditioning
    if filename is not _UNSET:
        _kwargs['filename'] = filename
    if dtype is not _UNSET:
        _kwargs['dtype'] = dtype
    _kwargs.update(_extras)
    return node(wf, 'LTXVSaveConditioning', _id, pass_raw=pass_raw, **_kwargs)

def LTXVSelectLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    start_index: int | _Omitted = _UNSET,
    end_index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Selects a range of frames from the video latent. start_index and end_index define a closed interval (inclusive of both endpoints).

    Pack: ComfyUI-LTXVideo
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVSelectLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    if end_index is not _UNSET:
        _kwargs['end_index'] = end_index
    _kwargs.update(_extras)
    return node(wf, 'LTXVSelectLatents', _id, pass_raw=pass_raw, **_kwargs)

def LTXVSetAudioRefTokens(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    audio_latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Provides speaker identity context for audio generation by attaching reference audio tokens to the conditioning. The tokens are prepended with negative temporal positions so the model treats them as context rather than generation targets.

    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, frozen_audio

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVSetAudioRefTokens() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if audio_latent is not _UNSET:
        _kwargs['audio_latent'] = audio_latent
    _kwargs.update(_extras)
    return node(wf, 'LTXVSetAudioRefTokens', _id, pass_raw=pass_raw, **_kwargs)

def LTXVSetAudioVideoMaskByTime(
    *args: VibeWorkflow,
    _id: str | None = None,
    av_latent: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    audio_vae: Any | _Omitted = _UNSET,
    start_time: float | _Omitted = _UNSET,
    end_time: float | _Omitted = _UNSET,
    video_fps: float | _Omitted = _UNSET,
    mask_video: bool | _Omitted = _UNSET,
    mask_audio: bool | _Omitted = _UNSET,
    mask_init_value_video: float | _Omitted = _UNSET,
    mask_init_value_audio: float | _Omitted = _UNSET,
    slope_len: int | _Omitted = _UNSET,
    spatial_mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sets the audio and video mask by time.

    Pack: ComfyUI-LTXVideo
    Returns: positive, negative, av_latent, video_latent_blend_coefficients, video_pixel_blend_coefficients

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVSetAudioVideoMaskByTime() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if av_latent is not _UNSET:
        _kwargs['av_latent'] = av_latent
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if model is not _UNSET:
        _kwargs['model'] = model
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if audio_vae is not _UNSET:
        _kwargs['audio_vae'] = audio_vae
    if start_time is not _UNSET:
        _kwargs['start_time'] = start_time
    if end_time is not _UNSET:
        _kwargs['end_time'] = end_time
    if video_fps is not _UNSET:
        _kwargs['video_fps'] = video_fps
    if mask_video is not _UNSET:
        _kwargs['mask_video'] = mask_video
    if mask_audio is not _UNSET:
        _kwargs['mask_audio'] = mask_audio
    if mask_init_value_video is not _UNSET:
        _kwargs['mask_init_value_video'] = mask_init_value_video
    if mask_init_value_audio is not _UNSET:
        _kwargs['mask_init_value_audio'] = mask_init_value_audio
    if slope_len is not _UNSET:
        _kwargs['slope_len'] = slope_len
    if spatial_mask is not _UNSET:
        _kwargs['spatial_mask'] = spatial_mask
    _kwargs.update(_extras)
    return node(wf, 'LTXVSetAudioVideoMaskByTime', _id, pass_raw=pass_raw, **_kwargs)

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

def LTXVSparseTrackEditor(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    points_store: str | _Omitted = _UNSET,
    coordinates: str | _Omitted = _UNSET,
    points_to_sample: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Interactive spline editor for drawing sparse motion tracks on a reference image.

    Pack: ComfyUI-LTXVideo
    Returns: tracks

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVSparseTrackEditor() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if points_store is not _UNSET:
        _kwargs['points_store'] = points_store
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if points_to_sample is not _UNSET:
        _kwargs['points_to_sample'] = points_to_sample
    _kwargs.update(_extras)
    return node(wf, 'LTXVSparseTrackEditor', _id, pass_raw=pass_raw, **_kwargs)

def LTXVSpatioTemporalTiledVAEDecode(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    spatial_tiles: int | _Omitted = _UNSET,
    spatial_overlap: int | _Omitted = _UNSET,
    temporal_tile_length: int | _Omitted = _UNSET,
    temporal_overlap: int | _Omitted = _UNSET,
    last_frame_fix: bool | _Omitted = _UNSET,
    working_device: Literal['cpu', 'auto'] | _Omitted = _UNSET,
    working_dtype: Literal['float16', 'float32', 'auto'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Spatio Temporal Tiled VAE Decode

    Pack: ComfyUI-LTXVideo
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVSpatioTemporalTiledVAEDecode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if spatial_tiles is not _UNSET:
        _kwargs['spatial_tiles'] = spatial_tiles
    if spatial_overlap is not _UNSET:
        _kwargs['spatial_overlap'] = spatial_overlap
    if temporal_tile_length is not _UNSET:
        _kwargs['temporal_tile_length'] = temporal_tile_length
    if temporal_overlap is not _UNSET:
        _kwargs['temporal_overlap'] = temporal_overlap
    if last_frame_fix is not _UNSET:
        _kwargs['last_frame_fix'] = last_frame_fix
    if working_device is not _UNSET:
        _kwargs['working_device'] = working_device
    if working_dtype is not _UNSET:
        _kwargs['working_dtype'] = working_dtype
    _kwargs.update(_extras)
    return node(wf, 'LTXVSpatioTemporalTiledVAEDecode', _id, pass_raw=pass_raw, **_kwargs)

def LTXVStatNormLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    target_mean: float | _Omitted = _UNSET,
    target_std: float | _Omitted = _UNSET,
    percentile: float | _Omitted = _UNSET,
    factor: float | _Omitted = _UNSET,
    clip_outliers: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Stat Norm Latent

    Pack: ComfyUI-LTXVideo
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVStatNormLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if target_mean is not _UNSET:
        _kwargs['target_mean'] = target_mean
    if target_std is not _UNSET:
        _kwargs['target_std'] = target_std
    if percentile is not _UNSET:
        _kwargs['percentile'] = percentile
    if factor is not _UNSET:
        _kwargs['factor'] = factor
    if clip_outliers is not _UNSET:
        _kwargs['clip_outliers'] = clip_outliers
    _kwargs.update(_extras)
    return node(wf, 'LTXVStatNormLatent', _id, pass_raw=pass_raw, **_kwargs)

def LTXVTiledSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    noise: Any | _Omitted = _UNSET,
    sampler: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    guider: Any | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    horizontal_tiles: int | _Omitted = _UNSET,
    vertical_tiles: int | _Omitted = _UNSET,
    overlap: int | _Omitted = _UNSET,
    latents_cond_strength: float | _Omitted = _UNSET,
    boost_latent_similarity: bool | _Omitted = _UNSET,
    crop: Literal['center', 'disabled'] | _Omitted = _UNSET,
    optional_cond_images: Any | _Omitted = _UNSET,
    optional_cond_indices: str | _Omitted = _UNSET,
    images_cond_strengths: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 LTXV Tiled Sampler

    Pack: ComfyUI-LTXVideo
    Returns: output, denoised_output

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVTiledSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if noise is not _UNSET:
        _kwargs['noise'] = noise
    if sampler is not _UNSET:
        _kwargs['sampler'] = sampler
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if guider is not _UNSET:
        _kwargs['guider'] = guider
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if horizontal_tiles is not _UNSET:
        _kwargs['horizontal_tiles'] = horizontal_tiles
    if vertical_tiles is not _UNSET:
        _kwargs['vertical_tiles'] = vertical_tiles
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if latents_cond_strength is not _UNSET:
        _kwargs['latents_cond_strength'] = latents_cond_strength
    if boost_latent_similarity is not _UNSET:
        _kwargs['boost_latent_similarity'] = boost_latent_similarity
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if optional_cond_images is not _UNSET:
        _kwargs['optional_cond_images'] = optional_cond_images
    if optional_cond_indices is not _UNSET:
        _kwargs['optional_cond_indices'] = optional_cond_indices
    if images_cond_strengths is not _UNSET:
        _kwargs['images_cond_strengths'] = images_cond_strengths
    _kwargs.update(_extras)
    return node(wf, 'LTXVTiledSampler', _id, pass_raw=pass_raw, **_kwargs)

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

def LinearOverlapLatentTransition(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples1: Any | _Omitted = _UNSET,
    samples2: Any | _Omitted = _UNSET,
    overlap: int | _Omitted = _UNSET,
    axis: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Linear transition with overlap

    Pack: ComfyUI-LTXVideo
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LinearOverlapLatentTransition() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples1 is not _UNSET:
        _kwargs['samples1'] = samples1
    if samples2 is not _UNSET:
        _kwargs['samples2'] = samples2
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if axis is not _UNSET:
        _kwargs['axis'] = axis
    _kwargs.update(_extras)
    return node(wf, 'LinearOverlapLatentTransition', _id, pass_raw=pass_raw, **_kwargs)

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

def LowVRAMLatentUpscaleModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['hunyuanvideo15_latent_upsampler_1080p.safetensors', 'ltx-2-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x1.5-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'ltx-2.3-temporal-upscaler-x2-1.0.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Low VRAM Latent Upscale Model Loader

    Pack: ComfyUI-LTXVideo
    Returns: LATENT_UPSCALE_MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LowVRAMLatentUpscaleModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    _kwargs.update(_extras)
    return node(wf, 'LowVRAMLatentUpscaleModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def ModifyLTXModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Modify LTX Model

    Pack: ComfyUI-LTXVideo
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ModifyLTXModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'ModifyLTXModel', _id, pass_raw=pass_raw, **_kwargs)

def MultiPromptProvider(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompts: str | _Omitted = _UNSET,
    clip: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Multi Prompt Provider

    Pack: ComfyUI-LTXVideo
    Returns: conditionings

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MultiPromptProvider() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompts is not _UNSET:
        _kwargs['prompts'] = prompts
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    _kwargs.update(_extras)
    return node(wf, 'MultiPromptProvider', _id, pass_raw=pass_raw, **_kwargs)

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

def STGAdvancedPresets(
    *args: VibeWorkflow,
    _id: str | None = None,
    preset: Literal['Custom', '13b Dynamic', '13b Balanced', '13b Upscale', '13b Distilled', '2b'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 STG Advanced Presets

    Pack: ComfyUI-LTXVideo
    Returns: STG_ADVANCED_PRESET

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"STGAdvancedPresets() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if preset is not _UNSET:
        _kwargs['preset'] = preset
    _kwargs.update(_extras)
    return node(wf, 'STGAdvancedPresets', _id, pass_raw=pass_raw, **_kwargs)

def STGGuider(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    stg: float | _Omitted = _UNSET,
    rescale: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Implements Spatiotemporal Skip Guidance (STG), a training-free method enhancing transformer-based video diffusion models by selectively skipping layers during sampling. This approach improves video quality without sacrificing diversity or motion fidelity.Reference: https://arxiv.org/abs/2411.18664.

    Pack: ComfyUI-LTXVideo
    Returns: GUIDER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"STGGuider() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if stg is not _UNSET:
        _kwargs['stg'] = stg
    if rescale is not _UNSET:
        _kwargs['rescale'] = rescale
    _kwargs.update(_extras)
    return node(wf, 'STGGuider', _id, pass_raw=pass_raw, **_kwargs)

def STGGuiderAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    skip_steps_sigma_threshold: float | _Omitted = _UNSET,
    cfg_star_rescale: bool | _Omitted = _UNSET,
    sigmas: str | _Omitted = _UNSET,
    cfg_values: str | _Omitted = _UNSET,
    stg_scale_values: str | _Omitted = _UNSET,
    stg_rescale_values: str | _Omitted = _UNSET,
    stg_layers_indices: str | _Omitted = _UNSET,
    preset: Any | _Omitted = _UNSET,
    apply_apg: bool | _Omitted = _UNSET,
    apg_cfg_scale: float | _Omitted = _UNSET,
    eta: float | _Omitted = _UNSET,
    norm_threshold: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    The Advanced STG Guider implements sophisticated techniques for controlling the denoising process:

        It creates a dynamic mapping from scheduler-defined sigma values to CFG and STG (Spatio-Temporal Skip Guidance [1]) parameters.
        This approach establishes distinct sigma value ranges that operate independently of step numbers, allowing precise control over:
        • CFG scale
        • STG scale and rescale factors
        • STG attention layer skipping patterns

        The guider also supports:
        • CFG-Zero* [2] rescaling, which dynamically adjusts negative predictions based on the dot product between positive and negative signals
        • Threshold-based noise prediction zeroing for steps with sigma values exceeding a specified threshold

        For example if the sigma ranges are defined as [1.0, 0.9, 0.85, 0.6] and the CFG values are defined as [4, 3, 2, 1] and STG scale values
        are defined as [2, 2, 2, 1] and STG rescale values are defined as [1, 1, 1, 1] and STG layers indices are defined as [[14, 17], [14, 16], [14], [14]], then the guider will:
        - use CFG=4, STG scale=2, STG rescale=1 and STG layers indices = [14, 17] for sigma in the range (0.9, 1.0]
        - use CFG=3, STG scale=2, STG rescale=1 and STG layers indices = [14, 16] for sigma in the range (0.85, 0.9]
        - use CFG=2, STG scale=2, STG rescale=1 and STG layers indices = [14] for sigma in the range (0.8, 0.85]
        - use CFG=1, STG scale=1, STG rescale=1 and STG layers indices = [14] for sigma in the range (0.6, 0.8]

        The guider will use the same parameters for the same sigma values, regardless of the step number.

        References:
        [1] https://arxiv.org/abs/2411.18664
        [2] https://arxiv.org/abs/2503.18886

    Pack: ComfyUI-LTXVideo
    Returns: GUIDER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"STGGuiderAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if skip_steps_sigma_threshold is not _UNSET:
        _kwargs['skip_steps_sigma_threshold'] = skip_steps_sigma_threshold
    if cfg_star_rescale is not _UNSET:
        _kwargs['cfg_star_rescale'] = cfg_star_rescale
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if cfg_values is not _UNSET:
        _kwargs['cfg_values'] = cfg_values
    if stg_scale_values is not _UNSET:
        _kwargs['stg_scale_values'] = stg_scale_values
    if stg_rescale_values is not _UNSET:
        _kwargs['stg_rescale_values'] = stg_rescale_values
    if stg_layers_indices is not _UNSET:
        _kwargs['stg_layers_indices'] = stg_layers_indices
    if preset is not _UNSET:
        _kwargs['preset'] = preset
    if apply_apg is not _UNSET:
        _kwargs['apply_apg'] = apply_apg
    if apg_cfg_scale is not _UNSET:
        _kwargs['apg_cfg_scale'] = apg_cfg_scale
    if eta is not _UNSET:
        _kwargs['eta'] = eta
    if norm_threshold is not _UNSET:
        _kwargs['norm_threshold'] = norm_threshold
    _kwargs.update(_extras)
    return node(wf, 'STGGuiderAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def STGGuiderNode(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    stg: float | _Omitted = _UNSET,
    rescale: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Implements Spatiotemporal Skip Guidance (STG), a training-free method enhancing transformer-based video diffusion models by selectively skipping layers during sampling. This approach improves video quality without sacrificing diversity or motion fidelity.Reference: https://arxiv.org/abs/2411.18664.

    Pack: ComfyUI-LTXVideo
    Returns: GUIDER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"STGGuiderNode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if stg is not _UNSET:
        _kwargs['stg'] = stg
    if rescale is not _UNSET:
        _kwargs['rescale'] = rescale
    _kwargs.update(_extras)
    return node(wf, 'STGGuiderNode', _id, pass_raw=pass_raw, **_kwargs)

def Set_VAE_Decoder_Noise(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    timestep: float | _Omitted = _UNSET,
    scale: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    🅛🅣🅧 Set VAE Decoder Noise

    Pack: ComfyUI-LTXVideo
    Returns: VAE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Set_VAE_Decoder_Noise() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if timestep is not _UNSET:
        _kwargs['timestep'] = timestep
    if scale is not _UNSET:
        _kwargs['scale'] = scale
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'Set VAE Decoder Noise', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['APGGuider', 'DynamicConditioning', 'GemmaAPITextEncode', 'GuiderParameters', 'ImageToCPU', 'LTXAddVideoICLoRAGuide', 'LTXAddVideoICLoRAGuideAdvanced', 'LTXAttentioOverride', 'LTXAttentionBank', 'LTXAttnOverride', 'LTXFetaEnhance', 'LTXFloatToInt', 'LTXFlowEditCFGGuider', 'LTXFlowEditSampler', 'LTXForwardModelSamplingPred', 'LTXICLoRALoaderModelOnly', 'LTXPerturbedAttention', 'LTXPrepareAttnInjections', 'LTXQ8Patch', 'LTXRFForwardODESampler', 'LTXRFReverseODESampler', 'LTXReverseModelSamplingPred', 'LTXVAdainLatent', 'LTXVAddGuideAdvanced', 'LTXVAddGuideAdvancedAttention', 'LTXVAddLatentGuide', 'LTXVAddLatents', 'LTXVApplySTG', 'LTXVBaseSampler', 'LTXVDilateLatent', 'LTXVDilateVideoMask', 'LTXVDrawTracks', 'LTXVExtendSampler', 'LTXVGemmaCLIPModelLoader', 'LTXVGemmaEnhancePrompt', 'LTXVHDRDecodePostprocess', 'LTXVImgToVideoAdvanced', 'LTXVImgToVideoConditionOnly', 'LTXVInContextSampler', 'LTXVInpaintPreprocess', 'LTXVLaplacianPyramidBlend', 'LTXVLinearOverlapLatentTransition', 'LTXVLoadConditioning', 'LTXVLoopingSampler', 'LTXVMultiPromptProvider', 'LTXVNormalizingSampler', 'LTXVPatcherVAE', 'LTXVPerStepAdainPatcher', 'LTXVPerStepStatNormPatcher', 'LTXVPreprocessMasks', 'LTXVPromptEnhancer', 'LTXVPromptEnhancerLoader', 'LTXVQ8LoraModelLoader', 'LTXVSaveConditioning', 'LTXVSelectLatents', 'LTXVSetAudioRefTokens', 'LTXVSetAudioVideoMaskByTime', 'LTXVSetVideoLatentNoiseMasks', 'LTXVSparseTrackEditor', 'LTXVSpatioTemporalTiledVAEDecode', 'LTXVStatNormLatent', 'LTXVTiledSampler', 'LTXVTiledVAEDecode', 'LinearOverlapLatentTransition', 'LowVRAMAudioVAELoader', 'LowVRAMCheckpointLoader', 'LowVRAMLatentUpscaleModelLoader', 'ModifyLTXModel', 'MultiPromptProvider', 'MultimodalGuider', 'STGAdvancedPresets', 'STGGuider', 'STGGuiderAdvanced', 'STGGuiderNode', 'Set_VAE_Decoder_Noise']
__vibecomfy_class_types__ = {'APGGuider': 'APGGuider', 'DynamicConditioning': 'DynamicConditioning', 'GemmaAPITextEncode': 'GemmaAPITextEncode', 'GuiderParameters': 'GuiderParameters', 'ImageToCPU': 'ImageToCPU', 'LTXAddVideoICLoRAGuide': 'LTXAddVideoICLoRAGuide', 'LTXAddVideoICLoRAGuideAdvanced': 'LTXAddVideoICLoRAGuideAdvanced', 'LTXAttentioOverride': 'LTXAttentioOverride', 'LTXAttentionBank': 'LTXAttentionBank', 'LTXAttnOverride': 'LTXAttnOverride', 'LTXFetaEnhance': 'LTXFetaEnhance', 'LTXFloatToInt': 'LTXFloatToInt', 'LTXFlowEditCFGGuider': 'LTXFlowEditCFGGuider', 'LTXFlowEditSampler': 'LTXFlowEditSampler', 'LTXForwardModelSamplingPred': 'LTXForwardModelSamplingPred', 'LTXICLoRALoaderModelOnly': 'LTXICLoRALoaderModelOnly', 'LTXPerturbedAttention': 'LTXPerturbedAttention', 'LTXPrepareAttnInjections': 'LTXPrepareAttnInjections', 'LTXQ8Patch': 'LTXQ8Patch', 'LTXRFForwardODESampler': 'LTXRFForwardODESampler', 'LTXRFReverseODESampler': 'LTXRFReverseODESampler', 'LTXReverseModelSamplingPred': 'LTXReverseModelSamplingPred', 'LTXVAdainLatent': 'LTXVAdainLatent', 'LTXVAddGuideAdvanced': 'LTXVAddGuideAdvanced', 'LTXVAddGuideAdvancedAttention': 'LTXVAddGuideAdvancedAttention', 'LTXVAddLatentGuide': 'LTXVAddLatentGuide', 'LTXVAddLatents': 'LTXVAddLatents', 'LTXVApplySTG': 'LTXVApplySTG', 'LTXVBaseSampler': 'LTXVBaseSampler', 'LTXVDilateLatent': 'LTXVDilateLatent', 'LTXVDilateVideoMask': 'LTXVDilateVideoMask', 'LTXVDrawTracks': 'LTXVDrawTracks', 'LTXVExtendSampler': 'LTXVExtendSampler', 'LTXVGemmaCLIPModelLoader': 'LTXVGemmaCLIPModelLoader', 'LTXVGemmaEnhancePrompt': 'LTXVGemmaEnhancePrompt', 'LTXVHDRDecodePostprocess': 'LTXVHDRDecodePostprocess', 'LTXVImgToVideoAdvanced': 'LTXVImgToVideoAdvanced', 'LTXVImgToVideoConditionOnly': 'LTXVImgToVideoConditionOnly', 'LTXVInContextSampler': 'LTXVInContextSampler', 'LTXVInpaintPreprocess': 'LTXVInpaintPreprocess', 'LTXVLaplacianPyramidBlend': 'LTXVLaplacianPyramidBlend', 'LTXVLinearOverlapLatentTransition': 'LTXVLinearOverlapLatentTransition', 'LTXVLoadConditioning': 'LTXVLoadConditioning', 'LTXVLoopingSampler': 'LTXVLoopingSampler', 'LTXVMultiPromptProvider': 'LTXVMultiPromptProvider', 'LTXVNormalizingSampler': 'LTXVNormalizingSampler', 'LTXVPatcherVAE': 'LTXVPatcherVAE', 'LTXVPerStepAdainPatcher': 'LTXVPerStepAdainPatcher', 'LTXVPerStepStatNormPatcher': 'LTXVPerStepStatNormPatcher', 'LTXVPreprocessMasks': 'LTXVPreprocessMasks', 'LTXVPromptEnhancer': 'LTXVPromptEnhancer', 'LTXVPromptEnhancerLoader': 'LTXVPromptEnhancerLoader', 'LTXVQ8LoraModelLoader': 'LTXVQ8LoraModelLoader', 'LTXVSaveConditioning': 'LTXVSaveConditioning', 'LTXVSelectLatents': 'LTXVSelectLatents', 'LTXVSetAudioRefTokens': 'LTXVSetAudioRefTokens', 'LTXVSetAudioVideoMaskByTime': 'LTXVSetAudioVideoMaskByTime', 'LTXVSetVideoLatentNoiseMasks': 'LTXVSetVideoLatentNoiseMasks', 'LTXVSparseTrackEditor': 'LTXVSparseTrackEditor', 'LTXVSpatioTemporalTiledVAEDecode': 'LTXVSpatioTemporalTiledVAEDecode', 'LTXVStatNormLatent': 'LTXVStatNormLatent', 'LTXVTiledSampler': 'LTXVTiledSampler', 'LTXVTiledVAEDecode': 'LTXVTiledVAEDecode', 'LinearOverlapLatentTransition': 'LinearOverlapLatentTransition', 'LowVRAMAudioVAELoader': 'LowVRAMAudioVAELoader', 'LowVRAMCheckpointLoader': 'LowVRAMCheckpointLoader', 'LowVRAMLatentUpscaleModelLoader': 'LowVRAMLatentUpscaleModelLoader', 'ModifyLTXModel': 'ModifyLTXModel', 'MultiPromptProvider': 'MultiPromptProvider', 'MultimodalGuider': 'MultimodalGuider', 'STGAdvancedPresets': 'STGAdvancedPresets', 'STGGuider': 'STGGuider', 'STGGuiderAdvanced': 'STGGuiderAdvanced', 'STGGuiderNode': 'STGGuiderNode', 'Set_VAE_Decoder_Noise': 'Set VAE Decoder Noise'}
