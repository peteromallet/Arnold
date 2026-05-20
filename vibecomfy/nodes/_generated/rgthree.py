"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import _current_workflow_or_raise, node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def Any_Switch_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Any Switch (rgthree)
    
    Pack: rgthree-comfy
    Returns: *
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Any_Switch_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Any Switch (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
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
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Context_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    return node(wf, 'Context (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
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
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Context_Big_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    return node(wf, 'Context Big (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Merge_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context Merge (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Context_Merge_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Merge (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Merge_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context Merge Big (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED, STEPS, STEP_REFINER, CFG, CKPT_NAME, SAMPLER, SCHEDULER, CLIP_WIDTH, CLIP_HEIGHT, TEXT_POS_G, TEXT_POS_L, TEXT_NEG_G, TEXT_NEG_L, MASK, CONTROL_NET
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Context_Merge_Big_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Merge Big (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Switch_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context Switch (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Context_Switch_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Switch (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Context_Switch_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context Switch Big (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONTEXT, MODEL, CLIP, VAE, POSITIVE, NEGATIVE, LATENT, IMAGE, SEED, STEPS, STEP_REFINER, CFG, CKPT_NAME, SAMPLER, SCHEDULER, CLIP_WIDTH, CLIP_HEIGHT, TEXT_POS_G, TEXT_POS_L, TEXT_NEG_G, TEXT_NEG_L, MASK, CONTROL_NET
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Context_Switch_Big_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Context Switch Big (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Display_Any_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    source: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Display Any (rgthree)
    
    Pack: rgthree-comfy
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Display_Any_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if source is not _UNSET:
        _kwargs['source'] = source
    _kwargs.update(_extras)
    return node(wf, 'Display Any (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Display_Int_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    input: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Display Int (rgthree)
    
    Pack: rgthree-comfy
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Display_Int_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input is not _UNSET:
        _kwargs['input'] = input
    _kwargs.update(_extras)
    return node(wf, 'Display Int (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Image_Comparer_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    image_a: Any = _UNSET,
    image_b: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Compares two images with a hover slider, or click from properties.
    
    Pack: rgthree-comfy
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Image_Comparer_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image_a is not _UNSET:
        _kwargs['image_a'] = image_a
    if image_b is not _UNSET:
        _kwargs['image_b'] = image_b
    _kwargs.update(_extras)
    return node(wf, 'Image Comparer (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Image_Inset_Crop_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any = _UNSET,
    measurement: Any = _UNSET,
    left: Any = _UNSET,
    right: Any = _UNSET,
    top: Any = _UNSET,
    bottom: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Inset Crop (rgthree)
    
    Pack: rgthree-comfy
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Image_Inset_Crop_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if measurement is not _UNSET:
        _kwargs['measurement'] = measurement
    if left is not _UNSET:
        _kwargs['left'] = left
    if right is not _UNSET:
        _kwargs['right'] = right
    if top is not _UNSET:
        _kwargs['top'] = top
    if bottom is not _UNSET:
        _kwargs['bottom'] = bottom
    _kwargs.update(_extras)
    return node(wf, 'Image Inset Crop (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Image_Resize_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any = _UNSET,
    measurement: Any = _UNSET,
    width: Any = _UNSET,
    height: Any = _UNSET,
    fit: Any = _UNSET,
    method: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Resize the image.
    
    Pack: rgthree-comfy
    Returns: IMAGE, WIDTH, HEIGHT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Image_Resize_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if measurement is not _UNSET:
        _kwargs['measurement'] = measurement
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if fit is not _UNSET:
        _kwargs['fit'] = fit
    if method is not _UNSET:
        _kwargs['method'] = method
    _kwargs.update(_extras)
    return node(wf, 'Image Resize (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Image_or_Latent_Size_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image or Latent Size (rgthree)
    
    Pack: rgthree-comfy
    Returns: WIDTH, HEIGHT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Image_or_Latent_Size_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Image or Latent Size (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def KSampler_Config_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    steps_total: Any = _UNSET,
    refiner_step: Any = _UNSET,
    cfg: Any = _UNSET,
    sampler_name: Any = _UNSET,
    scheduler: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    KSampler Config (rgthree)
    
    Pack: rgthree-comfy
    Returns: STEPS, REFINER_STEP, CFG, SAMPLER, SCHEDULER
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"KSampler_Config_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if steps_total is not _UNSET:
        _kwargs['steps_total'] = steps_total
    if refiner_step is not _UNSET:
        _kwargs['refiner_step'] = refiner_step
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if sampler_name is not _UNSET:
        _kwargs['sampler_name'] = sampler_name
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    _kwargs.update(_extras)
    return node(wf, 'KSampler Config (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Lora_Loader_Stack_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any = _UNSET,
    clip: Any = _UNSET,
    lora_01: Any = _UNSET,
    strength_01: Any = _UNSET,
    lora_02: Any = _UNSET,
    strength_02: Any = _UNSET,
    lora_03: Any = _UNSET,
    strength_03: Any = _UNSET,
    lora_04: Any = _UNSET,
    strength_04: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Lora Loader Stack (rgthree)
    
    Pack: rgthree-comfy
    Returns: MODEL, CLIP
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Lora_Loader_Stack_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if lora_01 is not _UNSET:
        _kwargs['lora_01'] = lora_01
    if strength_01 is not _UNSET:
        _kwargs['strength_01'] = strength_01
    if lora_02 is not _UNSET:
        _kwargs['lora_02'] = lora_02
    if strength_02 is not _UNSET:
        _kwargs['strength_02'] = strength_02
    if lora_03 is not _UNSET:
        _kwargs['lora_03'] = lora_03
    if strength_03 is not _UNSET:
        _kwargs['strength_03'] = strength_03
    if lora_04 is not _UNSET:
        _kwargs['lora_04'] = lora_04
    if strength_04 is not _UNSET:
        _kwargs['strength_04'] = strength_04
    _kwargs.update(_extras)
    return node(wf, 'Lora Loader Stack (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Lora_Loader_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any = _UNSET,
    clip: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Power Lora Loader (rgthree)
    
    Pack: rgthree-comfy
    Returns: MODEL, CLIP
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Power_Lora_Loader_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    _kwargs.update(_extras)
    return node(wf, 'Power Lora Loader (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Primitive_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Power Primitive (rgthree)
    
    Pack: rgthree-comfy
    Returns: *
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Power_Primitive_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Power Primitive (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Prompt_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt: Any = _UNSET,
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
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Power_Prompt_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt is not _UNSET:
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
    return node(wf, 'Power Prompt (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Prompt_Simple_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt: Any = _UNSET,
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
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Power_Prompt_Simple_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    _kwargs.update(_extras)
    return node(wf, 'Power Prompt - Simple (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Power_Puter_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Power Puter (rgthree)
    
    Pack: rgthree-comfy
    Returns: *
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Power_Puter_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    _kwargs.update(_extras)
    return node(wf, 'Power Puter (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def SDXL_Empty_Latent_Image_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    dimensions: Any = _UNSET,
    clip_scale: Any = _UNSET,
    batch_size: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    SDXL Empty Latent Image (rgthree)
    
    Pack: rgthree-comfy
    Returns: LATENT, CLIP_WIDTH, CLIP_HEIGHT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SDXL_Empty_Latent_Image_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if dimensions is not _UNSET:
        _kwargs['dimensions'] = dimensions
    if clip_scale is not _UNSET:
        _kwargs['clip_scale'] = clip_scale
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'SDXL Empty Latent Image (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def SDXL_Power_Prompt_Positive_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt_g: Any = _UNSET,
    prompt_l: Any = _UNSET,
    opt_model: Any = _UNSET,
    opt_clip: Any = _UNSET,
    opt_clip_width: Any = _UNSET,
    opt_clip_height: Any = _UNSET,
    insert_lora: Any = _UNSET,
    insert_embedding: Any = _UNSET,
    insert_saved: Any = _UNSET,
    target_width: Any = _UNSET,
    target_height: Any = _UNSET,
    crop_width: Any = _UNSET,
    crop_height: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    SDXL Power Prompt - Positive (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONDITIONING, MODEL, CLIP, TEXT_G, TEXT_L
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SDXL_Power_Prompt_Positive_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt_g is not _UNSET:
        _kwargs['prompt_g'] = prompt_g
    if prompt_l is not _UNSET:
        _kwargs['prompt_l'] = prompt_l
    if opt_model is not _UNSET:
        _kwargs['opt_model'] = opt_model
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    if opt_clip_width is not _UNSET:
        _kwargs['opt_clip_width'] = opt_clip_width
    if opt_clip_height is not _UNSET:
        _kwargs['opt_clip_height'] = opt_clip_height
    if insert_lora is not _UNSET:
        _kwargs['insert_lora'] = insert_lora
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    if target_width is not _UNSET:
        _kwargs['target_width'] = target_width
    if target_height is not _UNSET:
        _kwargs['target_height'] = target_height
    if crop_width is not _UNSET:
        _kwargs['crop_width'] = crop_width
    if crop_height is not _UNSET:
        _kwargs['crop_height'] = crop_height
    _kwargs.update(_extras)
    return node(wf, 'SDXL Power Prompt - Positive (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def SDXL_Power_Prompt_Simple_Negative_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt_g: Any = _UNSET,
    prompt_l: Any = _UNSET,
    opt_clip: Any = _UNSET,
    opt_clip_width: Any = _UNSET,
    opt_clip_height: Any = _UNSET,
    insert_embedding: Any = _UNSET,
    insert_saved: Any = _UNSET,
    target_width: Any = _UNSET,
    target_height: Any = _UNSET,
    crop_width: Any = _UNSET,
    crop_height: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    SDXL Power Prompt - Simple / Negative (rgthree)
    
    Pack: rgthree-comfy
    Returns: CONDITIONING, TEXT_G, TEXT_L
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SDXL_Power_Prompt_Simple_Negative_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt_g is not _UNSET:
        _kwargs['prompt_g'] = prompt_g
    if prompt_l is not _UNSET:
        _kwargs['prompt_l'] = prompt_l
    if opt_clip is not _UNSET:
        _kwargs['opt_clip'] = opt_clip
    if opt_clip_width is not _UNSET:
        _kwargs['opt_clip_width'] = opt_clip_width
    if opt_clip_height is not _UNSET:
        _kwargs['opt_clip_height'] = opt_clip_height
    if insert_embedding is not _UNSET:
        _kwargs['insert_embedding'] = insert_embedding
    if insert_saved is not _UNSET:
        _kwargs['insert_saved'] = insert_saved
    if target_width is not _UNSET:
        _kwargs['target_width'] = target_width
    if target_height is not _UNSET:
        _kwargs['target_height'] = target_height
    if crop_width is not _UNSET:
        _kwargs['crop_width'] = crop_width
    if crop_height is not _UNSET:
        _kwargs['crop_height'] = crop_height
    _kwargs.update(_extras)
    return node(wf, 'SDXL Power Prompt - Simple / Negative (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

def Seed_rgthree(
    *args: VibeWorkflow,
    _id: str | None = None,
    seed: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Seed (rgthree)
    
    Pack: rgthree-comfy
    Returns: SEED
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Seed_rgthree() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'Seed (rgthree)', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['Any_Switch_rgthree', 'Context_rgthree', 'Context_Big_rgthree', 'Context_Merge_rgthree', 'Context_Merge_Big_rgthree', 'Context_Switch_rgthree', 'Context_Switch_Big_rgthree', 'Display_Any_rgthree', 'Display_Int_rgthree', 'Image_Comparer_rgthree', 'Image_Inset_Crop_rgthree', 'Image_Resize_rgthree', 'Image_or_Latent_Size_rgthree', 'KSampler_Config_rgthree', 'Lora_Loader_Stack_rgthree', 'Power_Lora_Loader_rgthree', 'Power_Primitive_rgthree', 'Power_Prompt_rgthree', 'Power_Prompt_Simple_rgthree', 'Power_Puter_rgthree', 'SDXL_Empty_Latent_Image_rgthree', 'SDXL_Power_Prompt_Positive_rgthree', 'SDXL_Power_Prompt_Simple_Negative_rgthree', 'Seed_rgthree']
