"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def Any_Switch_rgthree(
    wf: VibeWorkflow,
    *,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Any Switch (rgthree)
    
    Pack: rgthree-comfy
    Returns: *
    """
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Any Switch (rgthree)', pass_raw=pass_raw, **_kwargs)

def Context_rgthree(
    wf: VibeWorkflow,
    *,
    base_ctx: Any = _UNSET,
    model: Any = _UNSET,
    clip: Any = _UNSET,
    vae: Any = _UNSET,
    positive: Any = _UNSET,
    negative: Any = _UNSET,
    latent: Any = _UNSET,
    images: Any = _UNSET,
    seed: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED
    """
    _kwargs: dict[str, Any] = {}
    if base_ctx is not _UNSET:
        _kwargs['base_ctx'] = base_ctx
    if model is not _UNSET:
        _kwargs['model'] = model
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if images is not _UNSET:
        _kwargs['images'] = images
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'Context (rgthree)', pass_raw=pass_raw, **_kwargs)

def Context_Big_rgthree(
    wf: VibeWorkflow,
    *,
    base_ctx: Any = _UNSET,
    model: Any = _UNSET,
    clip: Any = _UNSET,
    vae: Any = _UNSET,
    positive: Any = _UNSET,
    negative: Any = _UNSET,
    latent: Any = _UNSET,
    images: Any = _UNSET,
    seed: Any = _UNSET,
    steps: Any = _UNSET,
    step_refiner: Any = _UNSET,
    cfg: Any = _UNSET,
    ckpt_name: Any = _UNSET,
    sampler: Any = _UNSET,
    scheduler: Any = _UNSET,
    clip_width: Any = _UNSET,
    clip_height: Any = _UNSET,
    text_pos_g: Any = _UNSET,
    text_pos_l: Any = _UNSET,
    text_neg_g: Any = _UNSET,
    text_neg_l: Any = _UNSET,
    mask: Any = _UNSET,
    control_net: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context Big (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED, STEPS, STEP_REFINER, CFG, CKPT_NAME, SAMPLER, SCHEDULER, CLIP_WIDTH, CLIP_HEIGHT, TEXT_POS_G, TEXT_POS_L, TEXT_NEG_G, TEXT_NEG_L, MASK, CONTROL_NET
    """
    _kwargs: dict[str, Any] = {}
    if base_ctx is not _UNSET:
        _kwargs['base_ctx'] = base_ctx
    if model is not _UNSET:
        _kwargs['model'] = model
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if images is not _UNSET:
        _kwargs['images'] = images
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if step_refiner is not _UNSET:
        _kwargs['step_refiner'] = step_refiner
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    if sampler is not _UNSET:
        _kwargs['sampler'] = sampler
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if clip_width is not _UNSET:
        _kwargs['clip_width'] = clip_width
    if clip_height is not _UNSET:
        _kwargs['clip_height'] = clip_height
    if text_pos_g is not _UNSET:
        _kwargs['text_pos_g'] = text_pos_g
    if text_pos_l is not _UNSET:
        _kwargs['text_pos_l'] = text_pos_l
    if text_neg_g is not _UNSET:
        _kwargs['text_neg_g'] = text_neg_g
    if text_neg_l is not _UNSET:
        _kwargs['text_neg_l'] = text_neg_l
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if control_net is not _UNSET:
        _kwargs['control_net'] = control_net
    _kwargs.update(_extras)
    return node(wf, 'Context Big (rgthree)', pass_raw=pass_raw, **_kwargs)

def Context_Merge_rgthree(
    wf: VibeWorkflow,
    *,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context Merge (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED
    """
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Merge (rgthree)', pass_raw=pass_raw, **_kwargs)

def Context_Merge_Big_rgthree(
    wf: VibeWorkflow,
    *,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context Merge Big (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED, STEPS, STEP_REFINER, CFG, CKPT_NAME, SAMPLER, SCHEDULER, CLIP_WIDTH, CLIP_HEIGHT, TEXT_POS_G, TEXT_POS_L, TEXT_NEG_G, TEXT_NEG_L, MASK, CONTROL_NET
    """
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Merge Big (rgthree)', pass_raw=pass_raw, **_kwargs)

def Context_Switch_rgthree(
    wf: VibeWorkflow,
    *,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context Switch (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED
    """
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Switch (rgthree)', pass_raw=pass_raw, **_kwargs)

def Context_Switch_Big_rgthree(
    wf: VibeWorkflow,
    *,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context Switch Big (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED, STEPS, STEP_REFINER, CFG, CKPT_NAME, SAMPLER, SCHEDULER, CLIP_WIDTH, CLIP_HEIGHT, TEXT_POS_G, TEXT_POS_L, TEXT_NEG_G, TEXT_NEG_L, MASK, CONTROL_NET
    """
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Switch Big (rgthree)', pass_raw=pass_raw, **_kwargs)

def Display_Any_rgthree(
    wf: VibeWorkflow,
    *,
    source: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Display Any (rgthree)
    
    Pack: rgthree-comfy
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['source'] = source
    _kwargs.update(_extras)
    return node(wf, 'Display Any (rgthree)', pass_raw=pass_raw, **_kwargs)

def Display_Int_rgthree(
    wf: VibeWorkflow,
    *,
    input: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Display Int (rgthree)
    
    Pack: rgthree-comfy
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['input'] = input
    _kwargs.update(_extras)
    return node(wf, 'Display Int (rgthree)', pass_raw=pass_raw, **_kwargs)

def Image_Comparer_rgthree(
    wf: VibeWorkflow,
    *,
    image_a: Any = _UNSET,
    image_b: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Compares two images with a hover slider, or click from properties.
    
    Pack: rgthree-comfy
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    if image_a is not _UNSET:
        _kwargs['image_a'] = image_a
    if image_b is not _UNSET:
        _kwargs['image_b'] = image_b
    _kwargs.update(_extras)
    return node(wf, 'Image Comparer (rgthree)', pass_raw=pass_raw, **_kwargs)

def Image_Inset_Crop_rgthree(
    wf: VibeWorkflow,
    *,
    image: Any,
    measurement: Any,
    left: Any = 0,
    right: Any = 0,
    top: Any = 0,
    bottom: Any = 0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Inset Crop (rgthree)
    
    Pack: rgthree-comfy
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['measurement'] = measurement
    _kwargs['left'] = left
    _kwargs['right'] = right
    _kwargs['top'] = top
    _kwargs['bottom'] = bottom
    _kwargs.update(_extras)
    return node(wf, 'Image Inset Crop (rgthree)', pass_raw=pass_raw, **_kwargs)

def Image_Resize_rgthree(
    wf: VibeWorkflow,
    *,
    image: Any,
    measurement: Any,
    fit: Any,
    method: Any,
    width: Any = 0,
    height: Any = 0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Resize the image.
    
    Pack: rgthree-comfy
    Returns: IMAGE, WIDTH, HEIGHT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['measurement'] = measurement
    _kwargs['fit'] = fit
    _kwargs['method'] = method
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs.update(_extras)
    return node(wf, 'Image Resize (rgthree)', pass_raw=pass_raw, **_kwargs)

def Image_or_Latent_Size_rgthree(
    wf: VibeWorkflow,
    *,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image or Latent Size (rgthree)
    
    Pack: rgthree-comfy
    Returns: WIDTH, HEIGHT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Image or Latent Size (rgthree)', pass_raw=pass_raw, **_kwargs)

def KSampler_Config_rgthree(
    wf: VibeWorkflow,
    *,
    sampler_name: Any,
    scheduler: Any,
    steps_total: Any = 30,
    refiner_step: Any = 24,
    cfg: Any = 8.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    KSampler Config (rgthree)
    
    Pack: rgthree-comfy
    Returns: STEPS, REFINER_STEP, CFG, SAMPLER, SCHEDULER
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['sampler_name'] = sampler_name
    _kwargs['scheduler'] = scheduler
    _kwargs['steps_total'] = steps_total
    _kwargs['refiner_step'] = refiner_step
    _kwargs['cfg'] = cfg
    _kwargs.update(_extras)
    return node(wf, 'KSampler Config (rgthree)', pass_raw=pass_raw, **_kwargs)

def Lora_Loader_Stack_rgthree(
    wf: VibeWorkflow,
    *,
    model: Any,
    clip: Any,
    lora_01: Any,
    lora_02: Any,
    lora_03: Any,
    lora_04: Any,
    strength_01: Any = 1.0,
    strength_02: Any = 1.0,
    strength_03: Any = 1.0,
    strength_04: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Lora Loader Stack (rgthree)
    
    Pack: rgthree-comfy
    Returns: MODEL, CLIP
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['clip'] = clip
    _kwargs['lora_01'] = lora_01
    _kwargs['lora_02'] = lora_02
    _kwargs['lora_03'] = lora_03
    _kwargs['lora_04'] = lora_04
    _kwargs['strength_01'] = strength_01
    _kwargs['strength_02'] = strength_02
    _kwargs['strength_03'] = strength_03
    _kwargs['strength_04'] = strength_04
    _kwargs.update(_extras)
    return node(wf, 'Lora Loader Stack (rgthree)', pass_raw=pass_raw, **_kwargs)

def Power_Lora_Loader_rgthree(
    wf: VibeWorkflow,
    *,
    model: Any = _UNSET,
    clip: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Power Lora Loader (rgthree)
    
    Pack: rgthree-comfy
    Returns: MODEL, CLIP
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    _kwargs.update(_extras)
    return node(wf, 'Power Lora Loader (rgthree)', pass_raw=pass_raw, **_kwargs)

def Power_Primitive_rgthree(
    wf: VibeWorkflow,
    *,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Power Primitive (rgthree)
    
    Pack: rgthree-comfy
    Returns: *
    """
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Power Primitive (rgthree)', pass_raw=pass_raw, **_kwargs)

def Power_Prompt_rgthree(
    wf: VibeWorkflow,
    *,
    prompt: Any,
    opt_model: Any = _UNSET,
    opt_clip: Any = _UNSET,
    insert_lora: Any = _UNSET,
    insert_embedding: Any = _UNSET,
    insert_saved: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Power Prompt (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONDITIONING, MODEL, CLIP, TEXT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['prompt'] = prompt
    if opt_model is not _UNSET:
        _kwargs['opt_model'] = opt_model
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    if insert_lora is not _UNSET:
        _kwargs['insert_lora'] = insert_lora
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    _kwargs.update(_extras)
    return node(wf, 'Power Prompt (rgthree)', pass_raw=pass_raw, **_kwargs)

def Power_Prompt_Simple_rgthree(
    wf: VibeWorkflow,
    *,
    prompt: Any,
    opt_clip: Any = _UNSET,
    insert_embedding: Any = _UNSET,
    insert_saved: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Power Prompt - Simple (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONDITIONING, TEXT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['prompt'] = prompt
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    _kwargs.update(_extras)
    return node(wf, 'Power Prompt - Simple (rgthree)', pass_raw=pass_raw, **_kwargs)

def Power_Puter_rgthree(
    wf: VibeWorkflow,
    *,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Power Puter (rgthree)
    
    Pack: rgthree-comfy
    Returns: *
    """
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Power Puter (rgthree)', pass_raw=pass_raw, **_kwargs)

def SDXL_Empty_Latent_Image_rgthree(
    wf: VibeWorkflow,
    *,
    dimensions: Any = '1024 x 1024  (square)',
    clip_scale: Any = 2.0,
    batch_size: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    SDXL Empty Latent Image (rgthree)
    
    Pack: rgthree-comfy
    Returns: LATENT, CLIP_WIDTH, CLIP_HEIGHT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['dimensions'] = dimensions
    _kwargs['clip_scale'] = clip_scale
    _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'SDXL Empty Latent Image (rgthree)', pass_raw=pass_raw, **_kwargs)

def SDXL_Power_Prompt_Positive_rgthree(
    wf: VibeWorkflow,
    *,
    prompt_g: Any,
    prompt_l: Any,
    opt_model: Any = _UNSET,
    opt_clip: Any = _UNSET,
    opt_clip_width: Any = 1024.0,
    opt_clip_height: Any = 1024.0,
    insert_lora: Any = _UNSET,
    insert_embedding: Any = _UNSET,
    insert_saved: Any = _UNSET,
    target_width: Any = -1,
    target_height: Any = -1,
    crop_width: Any = -1,
    crop_height: Any = -1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    SDXL Power Prompt - Positive (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONDITIONING, MODEL, CLIP, TEXT_G, TEXT_L
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['prompt_g'] = prompt_g
    _kwargs['prompt_l'] = prompt_l
    if opt_model is not _UNSET:
        _kwargs['opt_model'] = opt_model
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    _kwargs['opt_clip_width'] = opt_clip_width
    _kwargs['opt_clip_height'] = opt_clip_height
    if insert_lora is not _UNSET:
        _kwargs['insert_lora'] = insert_lora
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    _kwargs['target_width'] = target_width
    _kwargs['target_height'] = target_height
    _kwargs['crop_width'] = crop_width
    _kwargs['crop_height'] = crop_height
    _kwargs.update(_extras)
    return node(wf, 'SDXL Power Prompt - Positive (rgthree)', pass_raw=pass_raw, **_kwargs)

def SDXL_Power_Prompt_Simple_Negative_rgthree(
    wf: VibeWorkflow,
    *,
    prompt_g: Any,
    prompt_l: Any,
    opt_clip: Any = _UNSET,
    opt_clip_width: Any = 1024.0,
    opt_clip_height: Any = 1024.0,
    insert_embedding: Any = _UNSET,
    insert_saved: Any = _UNSET,
    target_width: Any = -1,
    target_height: Any = -1,
    crop_width: Any = -1,
    crop_height: Any = -1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    SDXL Power Prompt - Simple / Negative (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONDITIONING, TEXT_G, TEXT_L
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['prompt_g'] = prompt_g
    _kwargs['prompt_l'] = prompt_l
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    _kwargs['opt_clip_width'] = opt_clip_width
    _kwargs['opt_clip_height'] = opt_clip_height
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    _kwargs['target_width'] = target_width
    _kwargs['target_height'] = target_height
    _kwargs['crop_width'] = crop_width
    _kwargs['crop_height'] = crop_height
    _kwargs.update(_extras)
    return node(wf, 'SDXL Power Prompt - Simple / Negative (rgthree)', pass_raw=pass_raw, **_kwargs)

def Seed_rgthree(
    wf: VibeWorkflow,
    *,
    seed: Any = 0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Seed (rgthree)
    
    Pack: rgthree-comfy
    Returns: SEED
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'Seed (rgthree)', pass_raw=pass_raw, **_kwargs)

__all__ = ['Any_Switch_rgthree', 'Context_rgthree', 'Context_Big_rgthree', 'Context_Merge_rgthree', 'Context_Merge_Big_rgthree', 'Context_Switch_rgthree', 'Context_Switch_Big_rgthree', 'Display_Any_rgthree', 'Display_Int_rgthree', 'Image_Comparer_rgthree', 'Image_Inset_Crop_rgthree', 'Image_Resize_rgthree', 'Image_or_Latent_Size_rgthree', 'KSampler_Config_rgthree', 'Lora_Loader_Stack_rgthree', 'Power_Lora_Loader_rgthree', 'Power_Primitive_rgthree', 'Power_Prompt_rgthree', 'Power_Prompt_Simple_rgthree', 'Power_Puter_rgthree', 'SDXL_Empty_Latent_Image_rgthree', 'SDXL_Power_Prompt_Positive_rgthree', 'SDXL_Power_Prompt_Simple_Negative_rgthree', 'Seed_rgthree']
