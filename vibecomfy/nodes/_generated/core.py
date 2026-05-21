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

def AudioConcat(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio1: Any | _Omitted = _UNSET,
    audio2: Any | _Omitted = _UNSET,
    direction: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Concatenates the audio1 to audio2 in the specified direction.
    
    Pack: comfy_core
    Returns: AUDIO
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"AudioConcat() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio1 is not _UNSET:
        _kwargs['audio1'] = audio1
    if audio2 is not _UNSET:
        _kwargs['audio2'] = audio2
    if direction is not _UNSET:
        _kwargs['direction'] = direction
    _kwargs.update(_extras)
    return node(wf, 'AudioConcat', _id, pass_raw=pass_raw, **_kwargs)

def AudioEncoderEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio_encoder: Any | _Omitted = _UNSET,
    audio: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: AUDIO_ENCODER_OUTPUT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"AudioEncoderEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio_encoder is not _UNSET:
        _kwargs['audio_encoder'] = audio_encoder
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'AudioEncoderEncode', _id, pass_raw=pass_raw, **_kwargs)

def AudioEncoderLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio_encoder_name: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: AUDIO_ENCODER
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"AudioEncoderLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio_encoder_name is not _UNSET:
        _kwargs['audio_encoder_name'] = audio_encoder_name
    _kwargs.update(_extras)
    return node(wf, 'AudioEncoderLoader', _id, pass_raw=pass_raw, **_kwargs)

def BasicScheduler(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    scheduler: Any | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    denoise: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SIGMAS
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BasicScheduler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if denoise is not _UNSET:
        _kwargs['denoise'] = denoise
    _kwargs.update(_extras)
    return node(wf, 'BasicScheduler', _id, pass_raw=pass_raw, **_kwargs)

def CFGGuider(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: GUIDER
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CFGGuider() takes at most 1 positional argument, got {len(args)}")
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
    _kwargs.update(_extras)
    return node(wf, 'CFGGuider', _id, pass_raw=pass_raw, **_kwargs)

def CFGNorm(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: patched_model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CFGNorm() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'CFGNorm', _id, pass_raw=pass_raw, **_kwargs)

def CLIPLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_name: Literal['ViT-L-14-BEST-smooth-GmP-TE-only-HF-format.safetensors', 'ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors', 'byt5_small_glyphxl_fp16.safetensors', 'clip_g.safetensors', 'clip_g_hidream.safetensors', 'clip_l.safetensors', 'clip_l_hidream.safetensors', 'ernie-image-prompt-enhancer.safetensors', 'full_encoder_small_decoder.safetensors', 'gemma_2_2b_fp16.safetensors', 'gemma_3_12B_it.safetensors', 'gemma_3_12B_it_fp4_mixed.safetensors', 'gemma_3_12B_it_fp8_scaled.safetensors', 'gemma_3_4b_it_bf16.safetensors', 'jina_clip_v2_bf16.safetensors', 'llama_3.1_8b_instruct_fp8_scaled.safetensors', 'llava_llama3_fp16.safetensors', 'llava_llama3_fp8_scaled.safetensors', 'ltx-2-19b-embeddings_connector_distill_bf16.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'ministral-3-3b.safetensors', 'mistral_3_small_flux2_bf16.safetensors', 'mistral_3_small_flux2_fp8.safetensors', 'oldt5_xxl_fp16.safetensors', 'oldt5_xxl_fp8_e4m3fn_scaled.safetensors', 'ovis_2.5.safetensors', 'qwen3.5_4b_bf16.safetensors', 'qwen_0.6b_ace15.safetensors', 'qwen_1.7b_ace15.safetensors', 'qwen_2.5_vl_7b.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_fp16.safetensors', 'qwen_3_06b_base.safetensors', 'qwen_3_4b.safetensors', 'qwen_3_8b.safetensors', 'qwen_3_8b_fp8mixed.safetensors', 'qwen_4b_ace15.safetensors', 't5-base.safetensors', 't5_base.safetensors', 't5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'] | _Omitted = _UNSET,
    type_: Literal['stable_diffusion', 'stable_cascade', 'sd3', 'stable_audio', 'mochi', 'ltxv', 'pixart', 'cosmos', 'lumina2', 'wan', 'hidream', 'chroma', 'ace', 'omnigen2', 'qwen_image', 'hunyuan_image', 'flux2', 'ovis', 'longcat_image'] | _Omitted = _UNSET,
    device: Literal['default', 'cpu'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    [Recipes]
    
    stable_diffusion: clip-l
    stable_cascade: clip-g
    sd3: t5 xxl/ clip-g / clip-l
    stable_audio: t5 base
    mochi: t5 xxl
    cosmos: old t5 xxl
    lumina2: gemma 2 2B
    wan: umt5 xxl
     hidream: llama-3.1 (Recommend) or t5
    omnigen2: qwen vl 2.5 3B
    
    Pack: comfy
    Returns: CLIP
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CLIPLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip_name is not _UNSET:
        _kwargs['clip_name'] = clip_name
    if type_ is not _UNSET:
        _kwargs['type'] = type_
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'CLIPLoader', _id, pass_raw=pass_raw, **_kwargs)

def CLIPTextEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    text: str | _Omitted = _UNSET,
    clip: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Encodes a text prompt using a CLIP model into an embedding that can be used to guide the diffusion model towards generating specific images.
    
    Pack: comfy
    Returns: CONDITIONING
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CLIPTextEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if text is not _UNSET:
        _kwargs['text'] = text
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    _kwargs.update(_extras)
    return node(wf, 'CLIPTextEncode', _id, pass_raw=pass_raw, **_kwargs)

def CLIPVisionEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_vision: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    crop: Literal['center', 'none'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    CLIP Vision Encode
    
    Pack: comfy
    Returns: CLIP_VISION_OUTPUT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CLIPVisionEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip_vision is not _UNSET:
        _kwargs['clip_vision'] = clip_vision
    if image is not _UNSET:
        _kwargs['image'] = image
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    _kwargs.update(_extras)
    return node(wf, 'CLIPVisionEncode', _id, pass_raw=pass_raw, **_kwargs)

def CLIPVisionLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_name: Literal['CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors', 'clip_vision_g.safetensors', 'clip_vision_h.safetensors', 'llava_llama3_vision.safetensors', 'sigclip_vision_patch14_384.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load CLIP Vision
    
    Pack: comfy
    Returns: CLIP_VISION
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CLIPVisionLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip_name is not _UNSET:
        _kwargs['clip_name'] = clip_name
    _kwargs.update(_extras)
    return node(wf, 'CLIPVisionLoader', _id, pass_raw=pass_raw, **_kwargs)

def CheckpointLoaderSimple(
    *args: VibeWorkflow,
    _id: str | None = None,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads a diffusion model checkpoint, diffusion models are used to denoise latents.
    
    Pack: comfy
    Returns: MODEL, CLIP, VAE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CheckpointLoaderSimple() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    _kwargs.update(_extras)
    return node(wf, 'CheckpointLoaderSimple', _id, pass_raw=pass_raw, **_kwargs)

def ComfyMathExpression(
    *args: VibeWorkflow,
    _id: str | None = None,
    expression: str | _Omitted = _UNSET,
    values: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Math Expression
    
    Pack: comfy_core
    Returns: FLOAT, INT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ComfyMathExpression() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if expression is not _UNSET:
        _kwargs['expression'] = expression
    if values is not _UNSET:
        _kwargs['values'] = values
    _kwargs.update(_extras)
    return node(wf, 'ComfyMathExpression', _id, pass_raw=pass_raw, **_kwargs)

def ComfySwitchNode(
    *args: VibeWorkflow,
    _id: str | None = None,
    switch: bool | _Omitted = _UNSET,
    on_false: Any | _Omitted = _UNSET,
    on_true: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Switch
    
    Pack: comfy_core
    Returns: output
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ComfySwitchNode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if switch is not _UNSET:
        _kwargs['switch'] = switch
    if on_false is not _UNSET:
        _kwargs['on_false'] = on_false
    if on_true is not _UNSET:
        _kwargs['on_true'] = on_true
    _kwargs.update(_extras)
    return node(wf, 'ComfySwitchNode', _id, pass_raw=pass_raw, **_kwargs)

def ConditioningZeroOut(
    *args: VibeWorkflow,
    _id: str | None = None,
    conditioning: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    ConditioningZeroOut
    
    Pack: comfy
    Returns: CONDITIONING
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ConditioningZeroOut() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if conditioning is not _UNSET:
        _kwargs['conditioning'] = conditioning
    _kwargs.update(_extras)
    return node(wf, 'ConditioningZeroOut', _id, pass_raw=pass_raw, **_kwargs)

def CreateVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    fps: float | _Omitted = _UNSET,
    audio: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create a video from images.
    
    Pack: comfy_core
    Returns: VIDEO
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'CreateVideo', _id, pass_raw=pass_raw, **_kwargs)

def DualCLIPLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_name1: Literal['ViT-L-14-BEST-smooth-GmP-TE-only-HF-format.safetensors', 'ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors', 'byt5_small_glyphxl_fp16.safetensors', 'clip_g.safetensors', 'clip_g_hidream.safetensors', 'clip_l.safetensors', 'clip_l_hidream.safetensors', 'ernie-image-prompt-enhancer.safetensors', 'flux1-dev-Q4_K_S.gguf', 'flux1-dev-Q8_0.gguf', 'flux1-schnell-Q4_K_S.gguf', 'flux1-schnell-Q8_0.gguf', 'full_encoder_small_decoder.safetensors', 'gemma_2_2b_fp16.safetensors', 'gemma_3_12B_it.safetensors', 'gemma_3_12B_it_fp4_mixed.safetensors', 'gemma_3_12B_it_fp8_scaled.safetensors', 'gemma_3_4b_it_bf16.safetensors', 'jina_clip_v2_bf16.safetensors', 'llama_3.1_8b_instruct_fp8_scaled.safetensors', 'llava_llama3_fp16.safetensors', 'llava_llama3_fp8_scaled.safetensors', 'ltx-2-19b-embeddings_connector_distill_bf16.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'ministral-3-3b.safetensors', 'mistral_3_small_flux2_bf16.safetensors', 'mistral_3_small_flux2_fp8.safetensors', 'oldt5_xxl_fp16.safetensors', 'oldt5_xxl_fp8_e4m3fn_scaled.safetensors', 'ovis_2.5.safetensors', 'qwen3.5_4b_bf16.safetensors', 'qwen_0.6b_ace15.safetensors', 'qwen_1.7b_ace15.safetensors', 'qwen_2.5_vl_7b.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_fp16.safetensors', 'qwen_3_06b_base.safetensors', 'qwen_3_4b.safetensors', 'qwen_3_8b.safetensors', 'qwen_3_8b_fp8mixed.safetensors', 'qwen_4b_ace15.safetensors', 't5-base.safetensors', 't5-v1_1-xxl-encoder-Q4_K_M.gguf', 't5-v1_1-xxl-encoder-Q8_0.gguf', 't5_base.safetensors', 't5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'] | _Omitted = _UNSET,
    clip_name2: Literal['ViT-L-14-BEST-smooth-GmP-TE-only-HF-format.safetensors', 'ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors', 'byt5_small_glyphxl_fp16.safetensors', 'clip_g.safetensors', 'clip_g_hidream.safetensors', 'clip_l.safetensors', 'clip_l_hidream.safetensors', 'ernie-image-prompt-enhancer.safetensors', 'flux1-dev-Q4_K_S.gguf', 'flux1-dev-Q8_0.gguf', 'flux1-schnell-Q4_K_S.gguf', 'flux1-schnell-Q8_0.gguf', 'full_encoder_small_decoder.safetensors', 'gemma_2_2b_fp16.safetensors', 'gemma_3_12B_it.safetensors', 'gemma_3_12B_it_fp4_mixed.safetensors', 'gemma_3_12B_it_fp8_scaled.safetensors', 'gemma_3_4b_it_bf16.safetensors', 'jina_clip_v2_bf16.safetensors', 'llama_3.1_8b_instruct_fp8_scaled.safetensors', 'llava_llama3_fp16.safetensors', 'llava_llama3_fp8_scaled.safetensors', 'ltx-2-19b-embeddings_connector_distill_bf16.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'ministral-3-3b.safetensors', 'mistral_3_small_flux2_bf16.safetensors', 'mistral_3_small_flux2_fp8.safetensors', 'oldt5_xxl_fp16.safetensors', 'oldt5_xxl_fp8_e4m3fn_scaled.safetensors', 'ovis_2.5.safetensors', 'qwen3.5_4b_bf16.safetensors', 'qwen_0.6b_ace15.safetensors', 'qwen_1.7b_ace15.safetensors', 'qwen_2.5_vl_7b.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_fp16.safetensors', 'qwen_3_06b_base.safetensors', 'qwen_3_4b.safetensors', 'qwen_3_8b.safetensors', 'qwen_3_8b_fp8mixed.safetensors', 'qwen_4b_ace15.safetensors', 't5-base.safetensors', 't5-v1_1-xxl-encoder-Q4_K_M.gguf', 't5-v1_1-xxl-encoder-Q8_0.gguf', 't5_base.safetensors', 't5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'] | _Omitted = _UNSET,
    type_: Literal['sdxl', 'sd3', 'flux', 'hunyuan_video', 'hidream', 'hunyuan_image', 'hunyuan_video_15', 'kandinsky5', 'kandinsky5_image', 'ltxv', 'newbie', 'ace'] | _Omitted = _UNSET,
    device: Literal['default', 'cpu'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    [Recipes]
    
    sdxl: clip-l, clip-g
    sd3: clip-l, clip-g / clip-l, t5 / clip-g, t5
    flux: clip-l, t5
    hidream: at least one of t5 or llama, recommended t5 and llama
    hunyuan_image: qwen2.5vl 7b and byt5 small
    newbie: gemma-3-4b-it, jina clip v2
    
    Pack: comfy
    Returns: CLIP
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DualCLIPLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip_name1 is not _UNSET:
        _kwargs['clip_name1'] = clip_name1
    if clip_name2 is not _UNSET:
        _kwargs['clip_name2'] = clip_name2
    if type_ is not _UNSET:
        _kwargs['type'] = type_
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'DualCLIPLoader', _id, pass_raw=pass_raw, **_kwargs)

def EmptyAceStep1_5LatentAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    seconds: float | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Empty Ace Step 1.5 Latent Audio
    
    Pack: comfy_core
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EmptyAceStep1_5LatentAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if seconds is not _UNSET:
        _kwargs['seconds'] = seconds
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyAceStep1.5LatentAudio', _id, pass_raw=pass_raw, **_kwargs)

def EmptyAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    duration: float | _Omitted = _UNSET,
    sample_rate: int | _Omitted = _UNSET,
    channels: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Empty Audio
    
    Pack: comfy_core
    Returns: AUDIO
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EmptyAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if duration is not _UNSET:
        _kwargs['duration'] = duration
    if sample_rate is not _UNSET:
        _kwargs['sample_rate'] = sample_rate
    if channels is not _UNSET:
        _kwargs['channels'] = channels
    _kwargs.update(_extras)
    return node(wf, 'EmptyAudio', _id, pass_raw=pass_raw, **_kwargs)

def EmptyFlux2LatentImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Empty Flux 2 Latent
    
    Pack: comfy_core
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EmptyFlux2LatentImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyFlux2LatentImage', _id, pass_raw=pass_raw, **_kwargs)

def EmptyHunyuanLatentVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    length: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Empty HunyuanVideo 1.0 Latent
    
    Pack: comfy_core
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EmptyHunyuanLatentVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if length is not _UNSET:
        _kwargs['length'] = length
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyHunyuanLatentVideo', _id, pass_raw=pass_raw, **_kwargs)

def EmptyImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    color: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EmptyImage
    
    Pack: comfy
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EmptyImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if color is not _UNSET:
        _kwargs['color'] = color
    _kwargs.update(_extras)
    return node(wf, 'EmptyImage', _id, pass_raw=pass_raw, **_kwargs)

def EmptyLTXVLatentVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    length: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EmptyLTXVLatentVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if length is not _UNSET:
        _kwargs['length'] = length
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyLTXVLatentVideo', _id, pass_raw=pass_raw, **_kwargs)

def EmptySD3LatentImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EmptySD3LatentImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptySD3LatentImage', _id, pass_raw=pass_raw, **_kwargs)

def Flux2Scheduler(
    *args: VibeWorkflow,
    _id: str | None = None,
    steps: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SIGMAS
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Flux2Scheduler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    _kwargs.update(_extras)
    return node(wf, 'Flux2Scheduler', _id, pass_raw=pass_raw, **_kwargs)

def GetImageRangeFromBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    start_index: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    masks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Get Image or Mask Range From Batch
    
    Pack: comfy_extras
    Returns: IMAGE, MASK
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetImageRangeFromBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if images is not _UNSET:
        _kwargs['images'] = images
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    _kwargs.update(_extras)
    return node(wf, 'GetImageRangeFromBatch', _id, pass_raw=pass_raw, **_kwargs)

def GetImageSize(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns width and height of the image, and passes it through unchanged.
    
    Pack: comfy_core
    Returns: width, height, batch_size
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetImageSize() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'GetImageSize', _id, pass_raw=pass_raw, **_kwargs)

def GetVideoComponents(
    *args: VibeWorkflow,
    _id: str | None = None,
    video: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Extracts all components from a video: frames, audio, and framerate.
    
    Pack: comfy_core
    Returns: images, audio, fps
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetVideoComponents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video is not _UNSET:
        _kwargs['video'] = video
    _kwargs.update(_extras)
    return node(wf, 'GetVideoComponents', _id, pass_raw=pass_raw, **_kwargs)

def GrowMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    expand: int | _Omitted = _UNSET,
    tapered_corners: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Grow Mask
    
    Pack: comfy_core
    Returns: MASK
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GrowMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if expand is not _UNSET:
        _kwargs['expand'] = expand
    if tapered_corners is not _UNSET:
        _kwargs['tapered_corners'] = tapered_corners
    _kwargs.update(_extras)
    return node(wf, 'GrowMask', _id, pass_raw=pass_raw, **_kwargs)

def ImageBlend(
    *args: VibeWorkflow,
    _id: str | None = None,
    image1: Any | _Omitted = _UNSET,
    image2: Any | _Omitted = _UNSET,
    blend_factor: float | _Omitted = _UNSET,
    blend_mode: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Blend
    
    Pack: comfy_core
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageBlend() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image1 is not _UNSET:
        _kwargs['image1'] = image1
    if image2 is not _UNSET:
        _kwargs['image2'] = image2
    if blend_factor is not _UNSET:
        _kwargs['blend_factor'] = blend_factor
    if blend_mode is not _UNSET:
        _kwargs['blend_mode'] = blend_mode
    _kwargs.update(_extras)
    return node(wf, 'ImageBlend', _id, pass_raw=pass_raw, **_kwargs)

def ImageBlur(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    blur_radius: int | _Omitted = _UNSET,
    sigma: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Blur
    
    Pack: comfy_core
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageBlur() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if blur_radius is not _UNSET:
        _kwargs['blur_radius'] = blur_radius
    if sigma is not _UNSET:
        _kwargs['sigma'] = sigma
    _kwargs.update(_extras)
    return node(wf, 'ImageBlur', _id, pass_raw=pass_raw, **_kwargs)

def ImageFromBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    batch_index: int | _Omitted = _UNSET,
    length: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageFromBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if batch_index is not _UNSET:
        _kwargs['batch_index'] = batch_index
    if length is not _UNSET:
        _kwargs['length'] = length
    _kwargs.update(_extras)
    return node(wf, 'ImageFromBatch', _id, pass_raw=pass_raw, **_kwargs)

def ImageScale(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    crop: Literal['disabled', 'center'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Upscale Image
    
    Pack: comfy
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageScale() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if upscale_method is not _UNSET:
        _kwargs['upscale_method'] = upscale_method
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    _kwargs.update(_extras)
    return node(wf, 'ImageScale', _id, pass_raw=pass_raw, **_kwargs)

def ImageScaleBy(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = _UNSET,
    scale_by: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Upscale Image By
    
    Pack: comfy
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageScaleBy() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if upscale_method is not _UNSET:
        _kwargs['upscale_method'] = upscale_method
    if scale_by is not _UNSET:
        _kwargs['scale_by'] = scale_by
    _kwargs.update(_extras)
    return node(wf, 'ImageScaleBy', _id, pass_raw=pass_raw, **_kwargs)

def ImageScaleToTotalPixels(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    upscale_method: Any | _Omitted = _UNSET,
    megapixels: float | _Omitted = _UNSET,
    resolution_steps: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageScaleToTotalPixels() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if upscale_method is not _UNSET:
        _kwargs['upscale_method'] = upscale_method
    if megapixels is not _UNSET:
        _kwargs['megapixels'] = megapixels
    if resolution_steps is not _UNSET:
        _kwargs['resolution_steps'] = resolution_steps
    _kwargs.update(_extras)
    return node(wf, 'ImageScaleToTotalPixels', _id, pass_raw=pass_raw, **_kwargs)

def KSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    sampler_name: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = _UNSET,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    latent_image: Any | _Omitted = _UNSET,
    denoise: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Uses the provided model, positive and negative conditioning to denoise the latent image.
    
    Pack: comfy
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"KSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if sampler_name is not _UNSET:
        _kwargs['sampler_name'] = sampler_name
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if latent_image is not _UNSET:
        _kwargs['latent_image'] = latent_image
    if denoise is not _UNSET:
        _kwargs['denoise'] = denoise
    _kwargs.update(_extras)
    return node(wf, 'KSampler', _id, pass_raw=pass_raw, **_kwargs)

def KSamplerSelect(
    *args: VibeWorkflow,
    _id: str | None = None,
    sampler_name: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SAMPLER
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"KSamplerSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if sampler_name is not _UNSET:
        _kwargs['sampler_name'] = sampler_name
    _kwargs.update(_extras)
    return node(wf, 'KSamplerSelect', _id, pass_raw=pass_raw, **_kwargs)

def LTXAVTextEncoderLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    text_encoder: Any | _Omitted = _UNSET,
    ckpt_name: Any | _Omitted = _UNSET,
    device: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    [Recipes]
    
    ltxav: gemma 3 12B
    
    Pack: comfy_core
    Returns: CLIP
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXAVTextEncoderLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if text_encoder is not _UNSET:
        _kwargs['text_encoder'] = text_encoder
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'LTXAVTextEncoderLoader', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAddGuide(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    frame_idx: int | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: positive, negative, latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAddGuide() takes at most 1 positional argument, got {len(args)}")
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
    _kwargs.update(_extras)
    return node(wf, 'LTXVAddGuide', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAddGuideMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    num_guides: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Add multiple guide images at specified frame indices with strengths, uses DynamicCombo which requires ComfyUI 0.8.1 and frontend 1.33.4 or later.
    
    Pack: comfy_core
    Returns: positive, negative, latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAddGuideMulti() takes at most 1 positional argument, got {len(args)}")
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
    if num_guides is not _UNSET:
        _kwargs['num_guides'] = num_guides
    _kwargs.update(_extras)
    return node(wf, 'LTXVAddGuideMulti', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAudioVAEDecode(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    audio_vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Audio VAE Decode
    
    Pack: comfy_core
    Returns: Audio
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAudioVAEDecode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if audio_vae is not _UNSET:
        _kwargs['audio_vae'] = audio_vae
    _kwargs.update(_extras)
    return node(wf, 'LTXVAudioVAEDecode', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAudioVAEEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    audio_vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Audio VAE Encode
    
    Pack: comfy_core
    Returns: Audio Latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAudioVAEEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if audio_vae is not _UNSET:
        _kwargs['audio_vae'] = audio_vae
    _kwargs.update(_extras)
    return node(wf, 'LTXVAudioVAEEncode', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAudioVAELoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    ckpt_name: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Audio VAE Loader
    
    Pack: comfy_core
    Returns: Audio VAE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAudioVAELoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    _kwargs.update(_extras)
    return node(wf, 'LTXVAudioVAELoader', _id, pass_raw=pass_raw, **_kwargs)

def LTXVConcatAVLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    video_latent: Any | _Omitted = _UNSET,
    audio_latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVConcatAVLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video_latent is not _UNSET:
        _kwargs['video_latent'] = video_latent
    if audio_latent is not _UNSET:
        _kwargs['audio_latent'] = audio_latent
    _kwargs.update(_extras)
    return node(wf, 'LTXVConcatAVLatent', _id, pass_raw=pass_raw, **_kwargs)

def LTXVConditioning(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    frame_rate: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: positive, negative
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVConditioning() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if frame_rate is not _UNSET:
        _kwargs['frame_rate'] = frame_rate
    _kwargs.update(_extras)
    return node(wf, 'LTXVConditioning', _id, pass_raw=pass_raw, **_kwargs)

def LTXVCropGuides(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: positive, negative, latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVCropGuides() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    _kwargs.update(_extras)
    return node(wf, 'LTXVCropGuides', _id, pass_raw=pass_raw, **_kwargs)

def LTXVEmptyLatentAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    frames_number: int | _Omitted = _UNSET,
    frame_rate: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    audio_vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Empty Latent Audio
    
    Pack: comfy_core
    Returns: Latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVEmptyLatentAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if frames_number is not _UNSET:
        _kwargs['frames_number'] = frames_number
    if frame_rate is not _UNSET:
        _kwargs['frame_rate'] = frame_rate
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if audio_vae is not _UNSET:
        _kwargs['audio_vae'] = audio_vae
    _kwargs.update(_extras)
    return node(wf, 'LTXVEmptyLatentAudio', _id, pass_raw=pass_raw, **_kwargs)

def LTXVImgToVideoInplace(
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
    Pack: comfy_core
    Returns: latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVImgToVideoInplace() takes at most 1 positional argument, got {len(args)}")
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
    return node(wf, 'LTXVImgToVideoInplace', _id, pass_raw=pass_raw, **_kwargs)

def LTXVLatentUpsampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    upscale_model: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXVLatentUpsampler
    
    Pack: comfy_extras
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVLatentUpsampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if upscale_model is not _UNSET:
        _kwargs['upscale_model'] = upscale_model
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'LTXVLatentUpsampler', _id, pass_raw=pass_raw, **_kwargs)

def LTXVPreprocess(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    img_compression: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: output_image
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVPreprocess() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if img_compression is not _UNSET:
        _kwargs['img_compression'] = img_compression
    _kwargs.update(_extras)
    return node(wf, 'LTXVPreprocess', _id, pass_raw=pass_raw, **_kwargs)

def LTXVScheduler(
    *args: VibeWorkflow,
    _id: str | None = None,
    steps: int | _Omitted = _UNSET,
    max_shift: float | _Omitted = _UNSET,
    base_shift: float | _Omitted = _UNSET,
    stretch: bool | _Omitted = _UNSET,
    terminal: float | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SIGMAS
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVScheduler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if max_shift is not _UNSET:
        _kwargs['max_shift'] = max_shift
    if base_shift is not _UNSET:
        _kwargs['base_shift'] = base_shift
    if stretch is not _UNSET:
        _kwargs['stretch'] = stretch
    if terminal is not _UNSET:
        _kwargs['terminal'] = terminal
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    _kwargs.update(_extras)
    return node(wf, 'LTXVScheduler', _id, pass_raw=pass_raw, **_kwargs)

def LTXVSeparateAVLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    av_latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Separate AV Latent
    
    Pack: comfy_core
    Returns: video_latent, audio_latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVSeparateAVLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if av_latent is not _UNSET:
        _kwargs['av_latent'] = av_latent
    _kwargs.update(_extras)
    return node(wf, 'LTXVSeparateAVLatent', _id, pass_raw=pass_raw, **_kwargs)

def LatentUpscaleModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['hunyuanvideo15_latent_upsampler_1080p.safetensors', 'ltx-2-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x1.5-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'ltx-2.3-temporal-upscaler-x2-1.0.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LatentUpscaleModelLoader
    
    Pack: comfy_extras
    Returns: LATENT_UPSCALE_MODEL
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LatentUpscaleModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    _kwargs.update(_extras)
    return node(wf, 'LatentUpscaleModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def LoadAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Audio
    
    Pack: comfy_core
    Returns: AUDIO
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'LoadAudio', _id, pass_raw=pass_raw, **_kwargs)

def LoadImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Image
    
    Pack: comfy
    Returns: IMAGE, MASK
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'LoadImage', _id, pass_raw=pass_raw, **_kwargs)

def LoadVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    file: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Video
    
    Pack: comfy_core
    Returns: VIDEO
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if file is not _UNSET:
        _kwargs['file'] = file
    _kwargs.update(_extras)
    return node(wf, 'LoadVideo', _id, pass_raw=pass_raw, **_kwargs)

def LoraLoaderModelOnly(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    lora_name: Literal['Flux2TurboComfyv2.safetensors', 'Flux_2-Turbo-LoRA_comfyui.safetensors', 'GoodHands-beta2.safetensors', 'Hyper-SD15-12steps-CFG-lora.safetensors', 'Hyper-SDXL-12steps-CFG-lora.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'PixelArtRedmond15V-PixelArt-PIXARFK.safetensors', 'Qwen-Edit-2509-Multiple-angles.safetensors', 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', 'Qwen-Image-Edit-2509-Anything2RealAlpha.safetensors', 'Qwen-Image-Edit-2509-Fusion.safetensors', 'Qwen-Image-Edit-2509-Light-Migration.safetensors', 'Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Relight.safetensors', 'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors', 'Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors', 'Qwen-Image-Lightning-4steps-V2.0.safetensors', 'Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors', 'Qwen-Image-Lightning-8steps-V2.0.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'Wuli-Qwen-Image-2512-Turbo-LoRA-2steps-V1.0-bf16.safetensors', 'blur_control_xl_v1.safetensors', 'chronoedit_distill_lora.safetensors', 'flux1-canny-dev-lora.safetensors', 'flux1-depth-dev-lora.safetensors', 'gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors', 'gummycandy_qwen.safetensors', 'illustration-1.0-qwen-image.safetensors', 'ip-adapter-faceid-plus_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sdxl_lora.safetensors', 'ip-adapter-faceid_sd15_lora.safetensors', 'ip-adapter-faceid_sdxl_lora.safetensors', 'lcm_lora_sdxl.safetensors', 'lightx2v_14B_T2V_cfg_step_distill_lora_adaptive_rank_quantile_0.15_bf16.safetensors', 'ltx-2-19b-distilled-lora-384.safetensors', 'ltx-2-19b-ic-lora-canny-control.safetensors', 'ltx-2-19b-ic-lora-depth-control.safetensors', 'ltx-2-19b-ic-lora-pose-control.safetensors', 'ltx-2-19b-lora-camera-control-dolly-left.safetensors', 'ltx-2.3-22b-distilled-lora-384.safetensors', 'ltx-2.3-id-lora-talkvid-3k.safetensors', 'ltx2-squish.safetensors', 'ltx2.3-transition.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'openxl_handsfix.safetensors', 'qwen-image-edit-2511-multiple-angles-lora.safetensors', 'qwen_image_union_diffsynth_lora.safetensors', 'uso-flux1-dit-lora-v1.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors', 'wan_alpha_2.1_rgba_lora.safetensors'] | _Omitted = _UNSET,
    strength_model: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LoRAs are used to modify diffusion and CLIP models, altering the way in which latents are denoised such as applying styles. Multiple LoRA nodes can be linked together.
    
    Pack: comfy
    Returns: MODEL
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoraLoaderModelOnly() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if lora_name is not _UNSET:
        _kwargs['lora_name'] = lora_name
    if strength_model is not _UNSET:
        _kwargs['strength_model'] = strength_model
    _kwargs.update(_extras)
    return node(wf, 'LoraLoaderModelOnly', _id, pass_raw=pass_raw, **_kwargs)

def ManualSigmas(
    *args: VibeWorkflow,
    _id: str | None = None,
    sigmas: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SIGMAS
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ManualSigmas() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    _kwargs.update(_extras)
    return node(wf, 'ManualSigmas', _id, pass_raw=pass_raw, **_kwargs)

def MaskPreview(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input images to your ComfyUI output directory.
    
    Pack: comfy_core
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MaskPreview() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'MaskPreview', _id, pass_raw=pass_raw, **_kwargs)

def MaskToImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Convert Mask to Image
    
    Pack: comfy_core
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MaskToImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'MaskToImage', _id, pass_raw=pass_raw, **_kwargs)

def ModelSamplingAuraFlow(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    shift: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    ModelSamplingAuraFlow
    
    Pack: comfy_extras
    Returns: MODEL
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ModelSamplingAuraFlow() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if shift is not _UNSET:
        _kwargs['shift'] = shift
    _kwargs.update(_extras)
    return node(wf, 'ModelSamplingAuraFlow', _id, pass_raw=pass_raw, **_kwargs)

def ModelSamplingSD3(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    shift: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    ModelSamplingSD3
    
    Pack: comfy_extras
    Returns: MODEL
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ModelSamplingSD3() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if shift is not _UNSET:
        _kwargs['shift'] = shift
    _kwargs.update(_extras)
    return node(wf, 'ModelSamplingSD3', _id, pass_raw=pass_raw, **_kwargs)

def PixelPerfectResolution(
    *args: VibeWorkflow,
    _id: str | None = None,
    original_image: Any | _Omitted = _UNSET,
    image_gen_width: int | _Omitted = _UNSET,
    image_gen_height: int | _Omitted = _UNSET,
    resize_mode: Literal['Just Resize', 'Crop and Resize', 'Resize and Fill'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pixel Perfect Resolution
    
    Pack: comfy_extras
    Returns: RESOLUTION (INT)
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PixelPerfectResolution() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if original_image is not _UNSET:
        _kwargs['original_image'] = original_image
    if image_gen_width is not _UNSET:
        _kwargs['image_gen_width'] = image_gen_width
    if image_gen_height is not _UNSET:
        _kwargs['image_gen_height'] = image_gen_height
    if resize_mode is not _UNSET:
        _kwargs['resize_mode'] = resize_mode
    _kwargs.update(_extras)
    return node(wf, 'PixelPerfectResolution', _id, pass_raw=pass_raw, **_kwargs)

def PreviewAny(
    *args: VibeWorkflow,
    _id: str | None = None,
    source: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preview as Text
    
    Pack: comfy_extras
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PreviewAny() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if source is not _UNSET:
        _kwargs['source'] = source
    _kwargs.update(_extras)
    return node(wf, 'PreviewAny', _id, pass_raw=pass_raw, **_kwargs)

def PreviewAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preview Audio
    
    Pack: comfy_core
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PreviewAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'PreviewAudio', _id, pass_raw=pass_raw, **_kwargs)

def PreviewImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input images to your ComfyUI output directory.
    
    Pack: comfy
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PreviewImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'PreviewImage', _id, pass_raw=pass_raw, **_kwargs)

def PrimitiveStringMultiline(
    *args: VibeWorkflow,
    _id: str | None = None,
    value: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    String (Multiline)
    
    Pack: comfy_core
    Returns: STRING
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PrimitiveStringMultiline() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if value is not _UNSET:
        _kwargs['value'] = value
    _kwargs.update(_extras)
    return node(wf, 'PrimitiveStringMultiline', _id, pass_raw=pass_raw, **_kwargs)

def RandomNoise(
    *args: VibeWorkflow,
    _id: str | None = None,
    noise_seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: NOISE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"RandomNoise() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if noise_seed is not _UNSET:
        _kwargs['noise_seed'] = noise_seed
    _kwargs.update(_extras)
    return node(wf, 'RandomNoise', _id, pass_raw=pass_raw, **_kwargs)

def ReferenceLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    conditioning: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node sets the guiding latent for an edit model. If the model supports it you can chain multiple to set multiple reference images.
    
    Pack: comfy_core
    Returns: CONDITIONING
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ReferenceLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if conditioning is not _UNSET:
        _kwargs['conditioning'] = conditioning
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    _kwargs.update(_extras)
    return node(wf, 'ReferenceLatent', _id, pass_raw=pass_raw, **_kwargs)

def RepeatImageBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    amount: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"RepeatImageBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if amount is not _UNSET:
        _kwargs['amount'] = amount
    _kwargs.update(_extras)
    return node(wf, 'RepeatImageBatch', _id, pass_raw=pass_raw, **_kwargs)

def ResizeImageMaskNode(
    *args: VibeWorkflow,
    _id: str | None = None,
    input: Any | _Omitted = _UNSET,
    resize_type: Any | _Omitted = _UNSET,
    scale_method: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Resize an image or mask using various scaling methods.
    
    Pack: comfy_core
    Returns: resized
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ResizeImageMaskNode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input is not _UNSET:
        _kwargs['input'] = input
    if resize_type is not _UNSET:
        _kwargs['resize_type'] = resize_type
    if scale_method is not _UNSET:
        _kwargs['scale_method'] = scale_method
    _kwargs.update(_extras)
    return node(wf, 'ResizeImageMaskNode', _id, pass_raw=pass_raw, **_kwargs)

def ResizeImagesByLongerEdge(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    longer_edge: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Resize Images by Longer Edge
    
    Pack: comfy_core
    Returns: images
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ResizeImagesByLongerEdge() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if longer_edge is not _UNSET:
        _kwargs['longer_edge'] = longer_edge
    _kwargs.update(_extras)
    return node(wf, 'ResizeImagesByLongerEdge', _id, pass_raw=pass_raw, **_kwargs)

def SamplerCustomAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    noise: Any | _Omitted = _UNSET,
    guider: Any | _Omitted = _UNSET,
    sampler: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    latent_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: output, denoised_output
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SamplerCustomAdvanced() takes at most 1 positional argument, got {len(args)}")
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
    _kwargs.update(_extras)
    return node(wf, 'SamplerCustomAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def SamplerEulerAncestral(
    *args: VibeWorkflow,
    _id: str | None = None,
    eta: float | _Omitted = _UNSET,
    s_noise: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SAMPLER
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SamplerEulerAncestral() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if eta is not _UNSET:
        _kwargs['eta'] = eta
    if s_noise is not _UNSET:
        _kwargs['s_noise'] = s_noise
    _kwargs.update(_extras)
    return node(wf, 'SamplerEulerAncestral', _id, pass_raw=pass_raw, **_kwargs)

def SaveAudioMP3(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    quality: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Save Audio (MP3)
    
    Pack: comfy_core
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SaveAudioMP3() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    if quality is not _UNSET:
        _kwargs['quality'] = quality
    _kwargs.update(_extras)
    return node(wf, 'SaveAudioMP3', _id, pass_raw=pass_raw, **_kwargs)

def SaveImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input images to your ComfyUI output directory.
    
    Pack: comfy
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SaveImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    _kwargs.update(_extras)
    return node(wf, 'SaveImage', _id, pass_raw=pass_raw, **_kwargs)

def SaveVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    video: Any | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    format: Any | _Omitted = _UNSET,
    codec: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input images to your ComfyUI output directory.
    
    Pack: comfy_core
    Returns: None
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SaveVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video is not _UNSET:
        _kwargs['video'] = video
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    if format is not _UNSET:
        _kwargs['format'] = format
    if codec is not _UNSET:
        _kwargs['codec'] = codec
    _kwargs.update(_extras)
    return node(wf, 'SaveVideo', _id, pass_raw=pass_raw, **_kwargs)

def SetLatentNoiseMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Set Latent Noise Mask
    
    Pack: comfy
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SetLatentNoiseMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'SetLatentNoiseMask', _id, pass_raw=pass_raw, **_kwargs)

def SimpleMath(
    *args: VibeWorkflow,
    _id: str | None = None,
    value: str | _Omitted = _UNSET,
    a: Any | _Omitted = _UNSET,
    b: Any | _Omitted = _UNSET,
    c: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Simple Math
    
    Pack: comfy_extras
    Returns: INT, FLOAT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SimpleMath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if value is not _UNSET:
        _kwargs['value'] = value
    if a is not _UNSET:
        _kwargs['a'] = a
    if b is not _UNSET:
        _kwargs['b'] = b
    if c is not _UNSET:
        _kwargs['c'] = c
    _kwargs.update(_extras)
    return node(wf, 'SimpleMath+', _id, pass_raw=pass_raw, **_kwargs)

def SolidMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    value: float | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: MASK
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SolidMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if value is not _UNSET:
        _kwargs['value'] = value
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    _kwargs.update(_extras)
    return node(wf, 'SolidMask', _id, pass_raw=pass_raw, **_kwargs)

def StringConcatenate(
    *args: VibeWorkflow,
    _id: str | None = None,
    string_a: str | _Omitted = _UNSET,
    string_b: str | _Omitted = _UNSET,
    delimiter: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Text Concatenate
    
    Pack: comfy_core
    Returns: STRING
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"StringConcatenate() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if string_a is not _UNSET:
        _kwargs['string_a'] = string_a
    if string_b is not _UNSET:
        _kwargs['string_b'] = string_b
    if delimiter is not _UNSET:
        _kwargs['delimiter'] = delimiter
    _kwargs.update(_extras)
    return node(wf, 'StringConcatenate', _id, pass_raw=pass_raw, **_kwargs)

def TextEncodeAceStepAudio1_5(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip: Any | _Omitted = _UNSET,
    tags: str | _Omitted = _UNSET,
    lyrics: str | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    bpm: int | _Omitted = _UNSET,
    duration: float | _Omitted = _UNSET,
    timesignature: Any | _Omitted = _UNSET,
    language: Any | _Omitted = _UNSET,
    keyscale: Any | _Omitted = _UNSET,
    generate_audio_codes: bool | _Omitted = _UNSET,
    cfg_scale: float | _Omitted = _UNSET,
    temperature: float | _Omitted = _UNSET,
    top_p: float | _Omitted = _UNSET,
    top_k: int | _Omitted = _UNSET,
    min_p: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: CONDITIONING
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TextEncodeAceStepAudio1_5() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if tags is not _UNSET:
        _kwargs['tags'] = tags
    if lyrics is not _UNSET:
        _kwargs['lyrics'] = lyrics
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if bpm is not _UNSET:
        _kwargs['bpm'] = bpm
    if duration is not _UNSET:
        _kwargs['duration'] = duration
    if timesignature is not _UNSET:
        _kwargs['timesignature'] = timesignature
    if language is not _UNSET:
        _kwargs['language'] = language
    if keyscale is not _UNSET:
        _kwargs['keyscale'] = keyscale
    if generate_audio_codes is not _UNSET:
        _kwargs['generate_audio_codes'] = generate_audio_codes
    if cfg_scale is not _UNSET:
        _kwargs['cfg_scale'] = cfg_scale
    if temperature is not _UNSET:
        _kwargs['temperature'] = temperature
    if top_p is not _UNSET:
        _kwargs['top_p'] = top_p
    if top_k is not _UNSET:
        _kwargs['top_k'] = top_k
    if min_p is not _UNSET:
        _kwargs['min_p'] = min_p
    _kwargs.update(_extras)
    return node(wf, 'TextEncodeAceStepAudio1.5', _id, pass_raw=pass_raw, **_kwargs)

def TextEncodeQwenImageEdit(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip: Any | _Omitted = _UNSET,
    prompt: str | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: CONDITIONING
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TextEncodeQwenImageEdit() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'TextEncodeQwenImageEdit', _id, pass_raw=pass_raw, **_kwargs)

def TextGenerateLTX2Prompt(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip: Any | _Omitted = _UNSET,
    prompt: str | _Omitted = _UNSET,
    max_length: int | _Omitted = _UNSET,
    sampling_mode: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    thinking: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: generated_text
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TextGenerateLTX2Prompt() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if max_length is not _UNSET:
        _kwargs['max_length'] = max_length
    if sampling_mode is not _UNSET:
        _kwargs['sampling_mode'] = sampling_mode
    if image is not _UNSET:
        _kwargs['image'] = image
    if thinking is not _UNSET:
        _kwargs['thinking'] = thinking
    _kwargs.update(_extras)
    return node(wf, 'TextGenerateLTX2Prompt', _id, pass_raw=pass_raw, **_kwargs)

def TrimAudioDuration(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    start_index: float | _Omitted = _UNSET,
    duration: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Trim audio tensor into chosen time range.
    
    Pack: comfy_core
    Returns: AUDIO
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TrimAudioDuration() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    if duration is not _UNSET:
        _kwargs['duration'] = duration
    _kwargs.update(_extras)
    return node(wf, 'TrimAudioDuration', _id, pass_raw=pass_raw, **_kwargs)

def TrimVideoLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    trim_amount: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TrimVideoLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if trim_amount is not _UNSET:
        _kwargs['trim_amount'] = trim_amount
    _kwargs.update(_extras)
    return node(wf, 'TrimVideoLatent', _id, pass_raw=pass_raw, **_kwargs)

def UNETLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    unet_name: Any | _Omitted = _UNSET,
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e5m2', 'fp8_e4m3fn_fast'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Diffusion Model
    
    Pack: comfy
    Returns: MODEL
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"UNETLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if unet_name is not _UNSET:
        _kwargs['unet_name'] = unet_name
    if weight_dtype is not _UNSET:
        _kwargs['weight_dtype'] = weight_dtype
    _kwargs.update(_extras)
    return node(wf, 'UNETLoader', _id, pass_raw=pass_raw, **_kwargs)

def VAEDecode(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Decodes latent images back into pixel space images.
    
    Pack: comfy
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VAEDecode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VAEDecode', _id, pass_raw=pass_raw, **_kwargs)

def VAEDecodeAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VAE Decode Audio
    
    Pack: comfy_core
    Returns: AUDIO
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VAEDecodeAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VAEDecodeAudio', _id, pass_raw=pass_raw, **_kwargs)

def VAEDecodeTiled(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    tile_size: int | _Omitted = _UNSET,
    overlap: int | _Omitted = _UNSET,
    temporal_size: int | _Omitted = _UNSET,
    temporal_overlap: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VAE Decode (Tiled)
    
    Pack: comfy
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VAEDecodeTiled() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if tile_size is not _UNSET:
        _kwargs['tile_size'] = tile_size
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if temporal_size is not _UNSET:
        _kwargs['temporal_size'] = temporal_size
    if temporal_overlap is not _UNSET:
        _kwargs['temporal_overlap'] = temporal_overlap
    _kwargs.update(_extras)
    return node(wf, 'VAEDecodeTiled', _id, pass_raw=pass_raw, **_kwargs)

def VAEEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    pixels: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VAE Encode
    
    Pack: comfy
    Returns: LATENT
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VAEEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pixels is not _UNSET:
        _kwargs['pixels'] = pixels
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VAEEncode', _id, pass_raw=pass_raw, **_kwargs)

def VAELoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae_name: Literal['LTX23_video_vae_bf16.safetensors', 'Wan2_1_VAE_bf16.safetensors', 'Wan2_2_VAE_bf16.safetensors', 'ace_1.5_vae.safetensors', 'ae.safetensors', 'cosmos_cv8x8x8_1.0.safetensors', 'flux2-vae.safetensors', 'hunyuan_image_2.1_vae_fp16.safetensors', 'hunyuan_image_refiner_vae_fp16.safetensors', 'hunyuan_video_vae_bf16.safetensors', 'hunyuanvideo15_vae_fp16.safetensors', 'lumina_image_2.0-ae.safetensors', 'mochi_vae.safetensors', 'qwen_image_layered_vae.safetensors', 'qwen_image_vae.safetensors', 'sdxl_vae.safetensors', 'taeltx2_3.safetensors', 'vae-ft-mse-840000-ema-pruned.safetensors', 'wan2.2_vae.safetensors', 'wan_2.1_vae.safetensors', 'wan_alpha_2.1_vae_alpha_channel.safetensors', 'wan_alpha_2.1_vae_rgb_channel.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors', 'z_image_turbo_vae.safetensors', 'pixel_space'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load VAE
    
    Pack: comfy
    Returns: VAE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VAELoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae_name is not _UNSET:
        _kwargs['vae_name'] = vae_name
    _kwargs.update(_extras)
    return node(wf, 'VAELoader', _id, pass_raw=pass_raw, **_kwargs)

def WanAnimateToVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    length: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    continue_motion_max_frames: int | _Omitted = _UNSET,
    video_frame_offset: int | _Omitted = _UNSET,
    clip_vision_output: Any | _Omitted = _UNSET,
    reference_image: Any | _Omitted = _UNSET,
    face_video: Any | _Omitted = _UNSET,
    pose_video: Any | _Omitted = _UNSET,
    background_video: Any | _Omitted = _UNSET,
    character_mask: Any | _Omitted = _UNSET,
    continue_motion: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: positive, negative, latent, trim_latent, trim_image, video_frame_offset
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanAnimateToVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if length is not _UNSET:
        _kwargs['length'] = length
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if continue_motion_max_frames is not _UNSET:
        _kwargs['continue_motion_max_frames'] = continue_motion_max_frames
    if video_frame_offset is not _UNSET:
        _kwargs['video_frame_offset'] = video_frame_offset
    if clip_vision_output is not _UNSET:
        _kwargs['clip_vision_output'] = clip_vision_output
    if reference_image is not _UNSET:
        _kwargs['reference_image'] = reference_image
    if face_video is not _UNSET:
        _kwargs['face_video'] = face_video
    if pose_video is not _UNSET:
        _kwargs['pose_video'] = pose_video
    if background_video is not _UNSET:
        _kwargs['background_video'] = background_video
    if character_mask is not _UNSET:
        _kwargs['character_mask'] = character_mask
    if continue_motion is not _UNSET:
        _kwargs['continue_motion'] = continue_motion
    _kwargs.update(_extras)
    return node(wf, 'WanAnimateToVideo', _id, pass_raw=pass_raw, **_kwargs)

def WanImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    length: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    clip_vision_output: Any | _Omitted = _UNSET,
    start_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: positive, negative, latent
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanImageToVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if length is not _UNSET:
        _kwargs['length'] = length
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if clip_vision_output is not _UNSET:
        _kwargs['clip_vision_output'] = clip_vision_output
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    _kwargs.update(_extras)
    return node(wf, 'WanImageToVideo', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['AudioConcat', 'AudioEncoderEncode', 'AudioEncoderLoader', 'BasicScheduler', 'CFGGuider', 'CFGNorm', 'CLIPLoader', 'CLIPTextEncode', 'CLIPVisionEncode', 'CLIPVisionLoader', 'CheckpointLoaderSimple', 'ComfyMathExpression', 'ComfySwitchNode', 'ConditioningZeroOut', 'CreateVideo', 'DualCLIPLoader', 'EmptyAceStep1_5LatentAudio', 'EmptyAudio', 'EmptyFlux2LatentImage', 'EmptyHunyuanLatentVideo', 'EmptyImage', 'EmptyLTXVLatentVideo', 'EmptySD3LatentImage', 'Flux2Scheduler', 'GetImageRangeFromBatch', 'GetImageSize', 'GetVideoComponents', 'GrowMask', 'ImageBlend', 'ImageBlur', 'ImageFromBatch', 'ImageScale', 'ImageScaleBy', 'ImageScaleToTotalPixels', 'KSampler', 'KSamplerSelect', 'LTXAVTextEncoderLoader', 'LTXVAddGuide', 'LTXVAddGuideMulti', 'LTXVAudioVAEDecode', 'LTXVAudioVAEEncode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideoInplace', 'LTXVLatentUpsampler', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader', 'LoadAudio', 'LoadImage', 'LoadVideo', 'LoraLoaderModelOnly', 'ManualSigmas', 'MaskPreview', 'MaskToImage', 'ModelSamplingAuraFlow', 'ModelSamplingSD3', 'PixelPerfectResolution', 'PreviewAny', 'PreviewAudio', 'PreviewImage', 'PrimitiveStringMultiline', 'RandomNoise', 'ReferenceLatent', 'RepeatImageBatch', 'ResizeImageMaskNode', 'ResizeImagesByLongerEdge', 'SamplerCustomAdvanced', 'SamplerEulerAncestral', 'SaveAudioMP3', 'SaveImage', 'SaveVideo', 'SetLatentNoiseMask', 'SimpleMath', 'SolidMask', 'StringConcatenate', 'TextEncodeAceStepAudio1_5', 'TextEncodeQwenImageEdit', 'TextGenerateLTX2Prompt', 'TrimAudioDuration', 'TrimVideoLatent', 'UNETLoader', 'VAEDecode', 'VAEDecodeAudio', 'VAEDecodeTiled', 'VAEEncode', 'VAELoader', 'WanAnimateToVideo', 'WanImageToVideo']
