"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def AudioConcat(
    wf: VibeWorkflow,
    *,
    audio1: Any,
    audio2: Any,
    direction: Any = 'after',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Concatenates the audio1 to audio2 in the specified direction.
    
    Pack: comfy_core
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio1'] = audio1
    _kwargs['audio2'] = audio2
    _kwargs['direction'] = direction
    _kwargs.update(_extras)
    return node(wf, 'AudioConcat', pass_raw=pass_raw, **_kwargs)

def AudioEncoderEncode(
    wf: VibeWorkflow,
    *,
    audio_encoder: Any,
    audio: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: AUDIO_ENCODER_OUTPUT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio_encoder'] = audio_encoder
    _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'AudioEncoderEncode', pass_raw=pass_raw, **_kwargs)

def AudioEncoderLoader(
    wf: VibeWorkflow,
    *,
    audio_encoder_name: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: AUDIO_ENCODER
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio_encoder_name'] = audio_encoder_name
    _kwargs.update(_extras)
    return node(wf, 'AudioEncoderLoader', pass_raw=pass_raw, **_kwargs)

def BasicScheduler(
    wf: VibeWorkflow,
    *,
    model: Any,
    scheduler: Any,
    steps: Any = 20,
    denoise: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SIGMAS
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['scheduler'] = scheduler
    _kwargs['steps'] = steps
    _kwargs['denoise'] = denoise
    _kwargs.update(_extras)
    return node(wf, 'BasicScheduler', pass_raw=pass_raw, **_kwargs)

def CFGGuider(
    wf: VibeWorkflow,
    *,
    model: Any,
    positive: Any,
    negative: Any,
    cfg: Any = 8.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: GUIDER
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['cfg'] = cfg
    _kwargs.update(_extras)
    return node(wf, 'CFGGuider', pass_raw=pass_raw, **_kwargs)

def CFGNorm(
    wf: VibeWorkflow,
    *,
    model: Any,
    strength: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: patched_model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'CFGNorm', pass_raw=pass_raw, **_kwargs)

def CLIPLoader(
    wf: VibeWorkflow,
    *,
    clip_name: Any,
    type_: Any,
    device: Any = 'default',
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['clip_name'] = clip_name
    _kwargs['type'] = type_
    _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'CLIPLoader', pass_raw=pass_raw, **_kwargs)

def CLIPTextEncode(
    wf: VibeWorkflow,
    *,
    text: Any,
    clip: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Encodes a text prompt using a CLIP model into an embedding that can be used to guide the diffusion model towards generating specific images.
    
    Pack: comfy
    Returns: CONDITIONING
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['text'] = text
    _kwargs['clip'] = clip
    _kwargs.update(_extras)
    return node(wf, 'CLIPTextEncode', pass_raw=pass_raw, **_kwargs)

def CLIPVisionEncode(
    wf: VibeWorkflow,
    *,
    clip_vision: Any,
    image: Any,
    crop: Any = 'center',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    CLIP Vision Encode
    
    Pack: comfy
    Returns: CLIP_VISION_OUTPUT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['clip_vision'] = clip_vision
    _kwargs['image'] = image
    _kwargs['crop'] = crop
    _kwargs.update(_extras)
    return node(wf, 'CLIPVisionEncode', pass_raw=pass_raw, **_kwargs)

def CLIPVisionLoader(
    wf: VibeWorkflow,
    *,
    clip_name: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load CLIP Vision
    
    Pack: comfy
    Returns: CLIP_VISION
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['clip_name'] = clip_name
    _kwargs.update(_extras)
    return node(wf, 'CLIPVisionLoader', pass_raw=pass_raw, **_kwargs)

def CheckpointLoaderSimple(
    wf: VibeWorkflow,
    *,
    ckpt_name: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads a diffusion model checkpoint, diffusion models are used to denoise latents.
    
    Pack: comfy
    Returns: MODEL, CLIP, VAE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['ckpt_name'] = ckpt_name
    _kwargs.update(_extras)
    return node(wf, 'CheckpointLoaderSimple', pass_raw=pass_raw, **_kwargs)

def ComfyMathExpression(
    wf: VibeWorkflow,
    *,
    values: Any,
    expression: Any = 'a + b',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Math Expression
    
    Pack: comfy_core
    Returns: FLOAT, INT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['values'] = values
    _kwargs['expression'] = expression
    _kwargs.update(_extras)
    return node(wf, 'ComfyMathExpression', pass_raw=pass_raw, **_kwargs)

def ComfySwitchNode(
    wf: VibeWorkflow,
    *,
    switch: Any,
    on_false: Any,
    on_true: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Switch
    
    Pack: comfy_core
    Returns: output
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['switch'] = switch
    _kwargs['on_false'] = on_false
    _kwargs['on_true'] = on_true
    _kwargs.update(_extras)
    return node(wf, 'ComfySwitchNode', pass_raw=pass_raw, **_kwargs)

def ConditioningZeroOut(
    wf: VibeWorkflow,
    *,
    conditioning: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    ConditioningZeroOut
    
    Pack: comfy
    Returns: CONDITIONING
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['conditioning'] = conditioning
    _kwargs.update(_extras)
    return node(wf, 'ConditioningZeroOut', pass_raw=pass_raw, **_kwargs)

def CreateVideo(
    wf: VibeWorkflow,
    *,
    images: Any,
    fps: Any = 30.0,
    audio: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create a video from images.
    
    Pack: comfy_core
    Returns: VIDEO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['images'] = images
    _kwargs['fps'] = fps
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'CreateVideo', pass_raw=pass_raw, **_kwargs)

def DualCLIPLoader(
    wf: VibeWorkflow,
    *,
    clip_name1: Any,
    clip_name2: Any,
    type_: Any,
    device: Any = _UNSET,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['clip_name1'] = clip_name1
    _kwargs['clip_name2'] = clip_name2
    _kwargs['type'] = type_
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'DualCLIPLoader', pass_raw=pass_raw, **_kwargs)

def EmptyAceStep1_5LatentAudio(
    wf: VibeWorkflow,
    *,
    seconds: Any = 120.0,
    batch_size: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Empty Ace Step 1.5 Latent Audio
    
    Pack: comfy_core
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['seconds'] = seconds
    _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyAceStep1.5LatentAudio', pass_raw=pass_raw, **_kwargs)

def EmptyAudio(
    wf: VibeWorkflow,
    *,
    duration: Any = 60.0,
    sample_rate: Any = 44100,
    channels: Any = 2,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Empty Audio
    
    Pack: comfy_core
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['duration'] = duration
    _kwargs['sample_rate'] = sample_rate
    _kwargs['channels'] = channels
    _kwargs.update(_extras)
    return node(wf, 'EmptyAudio', pass_raw=pass_raw, **_kwargs)

def EmptyFlux2LatentImage(
    wf: VibeWorkflow,
    *,
    width: Any = 1024,
    height: Any = 1024,
    batch_size: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Empty Flux 2 Latent
    
    Pack: comfy_core
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyFlux2LatentImage', pass_raw=pass_raw, **_kwargs)

def EmptyHunyuanLatentVideo(
    wf: VibeWorkflow,
    *,
    width: Any = 848,
    height: Any = 480,
    length: Any = 25,
    batch_size: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Empty HunyuanVideo 1.0 Latent
    
    Pack: comfy_core
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['length'] = length
    _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyHunyuanLatentVideo', pass_raw=pass_raw, **_kwargs)

def EmptyImage(
    wf: VibeWorkflow,
    *,
    width: Any = 512,
    height: Any = 512,
    batch_size: Any = 1,
    color: Any = 0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EmptyImage
    
    Pack: comfy
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['batch_size'] = batch_size
    _kwargs['color'] = color
    _kwargs.update(_extras)
    return node(wf, 'EmptyImage', pass_raw=pass_raw, **_kwargs)

def EmptyLTXVLatentVideo(
    wf: VibeWorkflow,
    *,
    width: Any = 768,
    height: Any = 512,
    length: Any = 97,
    batch_size: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['length'] = length
    _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyLTXVLatentVideo', pass_raw=pass_raw, **_kwargs)

def EmptySD3LatentImage(
    wf: VibeWorkflow,
    *,
    width: Any = 1024,
    height: Any = 1024,
    batch_size: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptySD3LatentImage', pass_raw=pass_raw, **_kwargs)

def Flux2Scheduler(
    wf: VibeWorkflow,
    *,
    steps: Any = 20,
    width: Any = 1024,
    height: Any = 1024,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SIGMAS
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['steps'] = steps
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs.update(_extras)
    return node(wf, 'Flux2Scheduler', pass_raw=pass_raw, **_kwargs)

def GetImageRangeFromBatch(
    wf: VibeWorkflow,
    *,
    start_index: Any = 0,
    num_frames: Any = 1,
    images: Any = _UNSET,
    masks: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Get Image or Mask Range From Batch
    
    Pack: comfy_extras
    Returns: IMAGE, MASK
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['start_index'] = start_index
    _kwargs['num_frames'] = num_frames
    if images is not _UNSET:
        _kwargs['images'] = images
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    _kwargs.update(_extras)
    return node(wf, 'GetImageRangeFromBatch', pass_raw=pass_raw, **_kwargs)

def GetImageSize(
    wf: VibeWorkflow,
    *,
    image: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns width and height of the image, and passes it through unchanged.
    
    Pack: comfy_core
    Returns: width, height, batch_size
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'GetImageSize', pass_raw=pass_raw, **_kwargs)

def GetVideoComponents(
    wf: VibeWorkflow,
    *,
    video: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Extracts all components from a video: frames, audio, and framerate.
    
    Pack: comfy_core
    Returns: images, audio, fps
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['video'] = video
    _kwargs.update(_extras)
    return node(wf, 'GetVideoComponents', pass_raw=pass_raw, **_kwargs)

def GrowMask(
    wf: VibeWorkflow,
    *,
    mask: Any,
    expand: Any = 0,
    tapered_corners: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Grow Mask
    
    Pack: comfy_core
    Returns: MASK
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['mask'] = mask
    _kwargs['expand'] = expand
    _kwargs['tapered_corners'] = tapered_corners
    _kwargs.update(_extras)
    return node(wf, 'GrowMask', pass_raw=pass_raw, **_kwargs)

def ImageBlend(
    wf: VibeWorkflow,
    *,
    image1: Any,
    image2: Any,
    blend_mode: Any,
    blend_factor: Any = 0.5,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Blend
    
    Pack: comfy_core
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image1'] = image1
    _kwargs['image2'] = image2
    _kwargs['blend_mode'] = blend_mode
    _kwargs['blend_factor'] = blend_factor
    _kwargs.update(_extras)
    return node(wf, 'ImageBlend', pass_raw=pass_raw, **_kwargs)

def ImageBlur(
    wf: VibeWorkflow,
    *,
    image: Any,
    blur_radius: Any = 1,
    sigma: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Blur
    
    Pack: comfy_core
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['blur_radius'] = blur_radius
    _kwargs['sigma'] = sigma
    _kwargs.update(_extras)
    return node(wf, 'ImageBlur', pass_raw=pass_raw, **_kwargs)

def ImageFromBatch(
    wf: VibeWorkflow,
    *,
    image: Any,
    batch_index: Any = 0,
    length: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['batch_index'] = batch_index
    _kwargs['length'] = length
    _kwargs.update(_extras)
    return node(wf, 'ImageFromBatch', pass_raw=pass_raw, **_kwargs)

def ImageScale(
    wf: VibeWorkflow,
    *,
    image: Any,
    upscale_method: Any,
    width: Any = 512,
    height: Any = 512,
    crop: Any = 'none',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Upscale Image
    
    Pack: comfy
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['upscale_method'] = upscale_method
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['crop'] = crop
    _kwargs.update(_extras)
    return node(wf, 'ImageScale', pass_raw=pass_raw, **_kwargs)

def ImageScaleBy(
    wf: VibeWorkflow,
    *,
    image: Any,
    upscale_method: Any,
    scale_by: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Upscale Image By
    
    Pack: comfy
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['upscale_method'] = upscale_method
    _kwargs['scale_by'] = scale_by
    _kwargs.update(_extras)
    return node(wf, 'ImageScaleBy', pass_raw=pass_raw, **_kwargs)

def ImageScaleToTotalPixels(
    wf: VibeWorkflow,
    *,
    image: Any,
    upscale_method: Any,
    megapixels: Any = 1.0,
    resolution_steps: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['upscale_method'] = upscale_method
    _kwargs['megapixels'] = megapixels
    _kwargs['resolution_steps'] = resolution_steps
    _kwargs.update(_extras)
    return node(wf, 'ImageScaleToTotalPixels', pass_raw=pass_raw, **_kwargs)

def KSampler(
    wf: VibeWorkflow,
    *,
    model: Any,
    sampler_name: Any,
    positive: Any,
    negative: Any,
    latent_image: Any,
    seed: Any = 0,
    steps: Any = 20,
    cfg: Any = 8.0,
    scheduler: Any = 'simple',
    denoise: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Uses the provided model, positive and negative conditioning to denoise the latent image.
    
    Pack: comfy
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['sampler_name'] = sampler_name
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['latent_image'] = latent_image
    _kwargs['seed'] = seed
    _kwargs['steps'] = steps
    _kwargs['cfg'] = cfg
    _kwargs['scheduler'] = scheduler
    _kwargs['denoise'] = denoise
    _kwargs.update(_extras)
    return node(wf, 'KSampler', pass_raw=pass_raw, **_kwargs)

def KSamplerSelect(
    wf: VibeWorkflow,
    *,
    sampler_name: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SAMPLER
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['sampler_name'] = sampler_name
    _kwargs.update(_extras)
    return node(wf, 'KSamplerSelect', pass_raw=pass_raw, **_kwargs)

def LTXAVTextEncoderLoader(
    wf: VibeWorkflow,
    *,
    text_encoder: Any,
    ckpt_name: Any,
    device: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    [Recipes]
    
    ltxav: gemma 3 12B
    
    Pack: comfy_core
    Returns: CLIP
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['text_encoder'] = text_encoder
    _kwargs['ckpt_name'] = ckpt_name
    _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'LTXAVTextEncoderLoader', pass_raw=pass_raw, **_kwargs)

def LTXVAddGuide(
    wf: VibeWorkflow,
    *,
    positive: Any,
    negative: Any,
    vae: Any,
    latent: Any,
    image: Any,
    frame_idx: Any = 0,
    strength: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
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
    _kwargs.update(_extras)
    return node(wf, 'LTXVAddGuide', pass_raw=pass_raw, **_kwargs)

def LTXVAddGuideMulti(
    wf: VibeWorkflow,
    *,
    positive: Any,
    negative: Any,
    vae: Any,
    latent: Any,
    num_guides: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Add multiple guide images at specified frame indices with strengths, uses DynamicCombo which requires ComfyUI 0.8.1 and frontend 1.33.4 or later.
    
    Pack: comfy_core
    Returns: positive, negative, latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['vae'] = vae
    _kwargs['latent'] = latent
    _kwargs['num_guides'] = num_guides
    _kwargs.update(_extras)
    return node(wf, 'LTXVAddGuideMulti', pass_raw=pass_raw, **_kwargs)

def LTXVAudioVAEDecode(
    wf: VibeWorkflow,
    *,
    samples: Any,
    audio_vae: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Audio VAE Decode
    
    Pack: comfy_core
    Returns: Audio
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['samples'] = samples
    _kwargs['audio_vae'] = audio_vae
    _kwargs.update(_extras)
    return node(wf, 'LTXVAudioVAEDecode', pass_raw=pass_raw, **_kwargs)

def LTXVAudioVAEEncode(
    wf: VibeWorkflow,
    *,
    audio: Any,
    audio_vae: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Audio VAE Encode
    
    Pack: comfy_core
    Returns: Audio Latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio'] = audio
    _kwargs['audio_vae'] = audio_vae
    _kwargs.update(_extras)
    return node(wf, 'LTXVAudioVAEEncode', pass_raw=pass_raw, **_kwargs)

def LTXVAudioVAELoader(
    wf: VibeWorkflow,
    *,
    ckpt_name: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Audio VAE Loader
    
    Pack: comfy_core
    Returns: Audio VAE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['ckpt_name'] = ckpt_name
    _kwargs.update(_extras)
    return node(wf, 'LTXVAudioVAELoader', pass_raw=pass_raw, **_kwargs)

def LTXVConcatAVLatent(
    wf: VibeWorkflow,
    *,
    video_latent: Any,
    audio_latent: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['video_latent'] = video_latent
    _kwargs['audio_latent'] = audio_latent
    _kwargs.update(_extras)
    return node(wf, 'LTXVConcatAVLatent', pass_raw=pass_raw, **_kwargs)

def LTXVConditioning(
    wf: VibeWorkflow,
    *,
    positive: Any,
    negative: Any,
    frame_rate: Any = 25.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: positive, negative
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['frame_rate'] = frame_rate
    _kwargs.update(_extras)
    return node(wf, 'LTXVConditioning', pass_raw=pass_raw, **_kwargs)

def LTXVCropGuides(
    wf: VibeWorkflow,
    *,
    positive: Any,
    negative: Any,
    latent: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: positive, negative, latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['latent'] = latent
    _kwargs.update(_extras)
    return node(wf, 'LTXVCropGuides', pass_raw=pass_raw, **_kwargs)

def LTXVEmptyLatentAudio(
    wf: VibeWorkflow,
    *,
    audio_vae: Any,
    frames_number: Any = 97,
    frame_rate: Any = 25,
    batch_size: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Empty Latent Audio
    
    Pack: comfy_core
    Returns: Latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio_vae'] = audio_vae
    _kwargs['frames_number'] = frames_number
    _kwargs['frame_rate'] = frame_rate
    _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'LTXVEmptyLatentAudio', pass_raw=pass_raw, **_kwargs)

def LTXVImgToVideoInplace(
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
    Pack: comfy_core
    Returns: latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae'] = vae
    _kwargs['image'] = image
    _kwargs['latent'] = latent
    _kwargs['strength'] = strength
    _kwargs['bypass'] = bypass
    _kwargs.update(_extras)
    return node(wf, 'LTXVImgToVideoInplace', pass_raw=pass_raw, **_kwargs)

def LTXVLatentUpsampler(
    wf: VibeWorkflow,
    *,
    samples: Any,
    upscale_model: Any,
    vae: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXVLatentUpsampler
    
    Pack: comfy_extras
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['samples'] = samples
    _kwargs['upscale_model'] = upscale_model
    _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'LTXVLatentUpsampler', pass_raw=pass_raw, **_kwargs)

def LTXVPreprocess(
    wf: VibeWorkflow,
    *,
    image: Any,
    img_compression: Any = 35,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: output_image
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['img_compression'] = img_compression
    _kwargs.update(_extras)
    return node(wf, 'LTXVPreprocess', pass_raw=pass_raw, **_kwargs)

def LTXVScheduler(
    wf: VibeWorkflow,
    *,
    steps: Any = 20,
    max_shift: Any = 2.05,
    base_shift: Any = 0.95,
    stretch: Any = True,
    terminal: Any = 0.1,
    latent: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SIGMAS
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['steps'] = steps
    _kwargs['max_shift'] = max_shift
    _kwargs['base_shift'] = base_shift
    _kwargs['stretch'] = stretch
    _kwargs['terminal'] = terminal
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    _kwargs.update(_extras)
    return node(wf, 'LTXVScheduler', pass_raw=pass_raw, **_kwargs)

def LTXVSeparateAVLatent(
    wf: VibeWorkflow,
    *,
    av_latent: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LTXV Separate AV Latent
    
    Pack: comfy_core
    Returns: video_latent, audio_latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['av_latent'] = av_latent
    _kwargs.update(_extras)
    return node(wf, 'LTXVSeparateAVLatent', pass_raw=pass_raw, **_kwargs)

def LatentUpscaleModelLoader(
    wf: VibeWorkflow,
    *,
    model_name: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LatentUpscaleModelLoader
    
    Pack: comfy_extras
    Returns: LATENT_UPSCALE_MODEL
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model_name'] = model_name
    _kwargs.update(_extras)
    return node(wf, 'LatentUpscaleModelLoader', pass_raw=pass_raw, **_kwargs)

def LoadAudio(
    wf: VibeWorkflow,
    *,
    audio: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Audio
    
    Pack: comfy_core
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'LoadAudio', pass_raw=pass_raw, **_kwargs)

def LoadImage(
    wf: VibeWorkflow,
    *,
    image: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Image
    
    Pack: comfy
    Returns: IMAGE, MASK
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'LoadImage', pass_raw=pass_raw, **_kwargs)

def LoadVideo(
    wf: VibeWorkflow,
    *,
    file: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Video
    
    Pack: comfy_core
    Returns: VIDEO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['file'] = file
    _kwargs.update(_extras)
    return node(wf, 'LoadVideo', pass_raw=pass_raw, **_kwargs)

def LoraLoaderModelOnly(
    wf: VibeWorkflow,
    *,
    model: Any,
    lora_name: Any,
    strength_model: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LoRAs are used to modify diffusion and CLIP models, altering the way in which latents are denoised such as applying styles. Multiple LoRA nodes can be linked together.
    
    Pack: comfy
    Returns: MODEL
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['lora_name'] = lora_name
    _kwargs['strength_model'] = strength_model
    _kwargs.update(_extras)
    return node(wf, 'LoraLoaderModelOnly', pass_raw=pass_raw, **_kwargs)

def ManualSigmas(
    wf: VibeWorkflow,
    *,
    sigmas: Any = '1, 0.5',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SIGMAS
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['sigmas'] = sigmas
    _kwargs.update(_extras)
    return node(wf, 'ManualSigmas', pass_raw=pass_raw, **_kwargs)

def MaskPreview(
    wf: VibeWorkflow,
    *,
    mask: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input images to your ComfyUI output directory.
    
    Pack: comfy_core
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'MaskPreview', pass_raw=pass_raw, **_kwargs)

def MaskToImage(
    wf: VibeWorkflow,
    *,
    mask: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Convert Mask to Image
    
    Pack: comfy_core
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'MaskToImage', pass_raw=pass_raw, **_kwargs)

def ModelSamplingAuraFlow(
    wf: VibeWorkflow,
    *,
    model: Any,
    shift: Any = 1.73,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    ModelSamplingAuraFlow
    
    Pack: comfy_extras
    Returns: MODEL
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['shift'] = shift
    _kwargs.update(_extras)
    return node(wf, 'ModelSamplingAuraFlow', pass_raw=pass_raw, **_kwargs)

def ModelSamplingSD3(
    wf: VibeWorkflow,
    *,
    model: Any,
    shift: Any = 3.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    ModelSamplingSD3
    
    Pack: comfy_extras
    Returns: MODEL
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['shift'] = shift
    _kwargs.update(_extras)
    return node(wf, 'ModelSamplingSD3', pass_raw=pass_raw, **_kwargs)

def PixelPerfectResolution(
    wf: VibeWorkflow,
    *,
    original_image: Any,
    image_gen_width: Any = 512,
    image_gen_height: Any = 512,
    resize_mode: Any = 'Just Resize',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pixel Perfect Resolution
    
    Pack: comfy_extras
    Returns: RESOLUTION (INT)
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['original_image'] = original_image
    _kwargs['image_gen_width'] = image_gen_width
    _kwargs['image_gen_height'] = image_gen_height
    _kwargs['resize_mode'] = resize_mode
    _kwargs.update(_extras)
    return node(wf, 'PixelPerfectResolution', pass_raw=pass_raw, **_kwargs)

def PreviewAny(
    wf: VibeWorkflow,
    *,
    source: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preview as Text
    
    Pack: comfy_extras
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['source'] = source
    _kwargs.update(_extras)
    return node(wf, 'PreviewAny', pass_raw=pass_raw, **_kwargs)

def PreviewAudio(
    wf: VibeWorkflow,
    *,
    audio: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preview Audio
    
    Pack: comfy_core
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'PreviewAudio', pass_raw=pass_raw, **_kwargs)

def PreviewImage(
    wf: VibeWorkflow,
    *,
    images: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input images to your ComfyUI output directory.
    
    Pack: comfy
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'PreviewImage', pass_raw=pass_raw, **_kwargs)

def PrimitiveStringMultiline(
    wf: VibeWorkflow,
    *,
    value: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    String (Multiline)
    
    Pack: comfy_core
    Returns: STRING
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['value'] = value
    _kwargs.update(_extras)
    return node(wf, 'PrimitiveStringMultiline', pass_raw=pass_raw, **_kwargs)

def RandomNoise(
    wf: VibeWorkflow,
    *,
    noise_seed: Any = 0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: NOISE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['noise_seed'] = noise_seed
    _kwargs.update(_extras)
    return node(wf, 'RandomNoise', pass_raw=pass_raw, **_kwargs)

def ReferenceLatent(
    wf: VibeWorkflow,
    *,
    conditioning: Any,
    latent: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node sets the guiding latent for an edit model. If the model supports it you can chain multiple to set multiple reference images.
    
    Pack: comfy_core
    Returns: CONDITIONING
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['conditioning'] = conditioning
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    _kwargs.update(_extras)
    return node(wf, 'ReferenceLatent', pass_raw=pass_raw, **_kwargs)

def RepeatImageBatch(
    wf: VibeWorkflow,
    *,
    image: Any,
    amount: Any = 1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['amount'] = amount
    _kwargs.update(_extras)
    return node(wf, 'RepeatImageBatch', pass_raw=pass_raw, **_kwargs)

def ResizeImageMaskNode(
    wf: VibeWorkflow,
    *,
    input: Any,
    resize_type: Any,
    scale_method: Any = 'area',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Resize an image or mask using various scaling methods.
    
    Pack: comfy_core
    Returns: resized
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['input'] = input
    _kwargs['resize_type'] = resize_type
    _kwargs['scale_method'] = scale_method
    _kwargs.update(_extras)
    return node(wf, 'ResizeImageMaskNode', pass_raw=pass_raw, **_kwargs)

def ResizeImagesByLongerEdge(
    wf: VibeWorkflow,
    *,
    images: Any,
    longer_edge: Any = 1024,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Resize Images by Longer Edge
    
    Pack: comfy_core
    Returns: images
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['images'] = images
    _kwargs['longer_edge'] = longer_edge
    _kwargs.update(_extras)
    return node(wf, 'ResizeImagesByLongerEdge', pass_raw=pass_raw, **_kwargs)

def SamplerCustomAdvanced(
    wf: VibeWorkflow,
    *,
    noise: Any,
    guider: Any,
    sampler: Any,
    sigmas: Any,
    latent_image: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: output, denoised_output
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['noise'] = noise
    _kwargs['guider'] = guider
    _kwargs['sampler'] = sampler
    _kwargs['sigmas'] = sigmas
    _kwargs['latent_image'] = latent_image
    _kwargs.update(_extras)
    return node(wf, 'SamplerCustomAdvanced', pass_raw=pass_raw, **_kwargs)

def SamplerEulerAncestral(
    wf: VibeWorkflow,
    *,
    eta: Any = 1.0,
    s_noise: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: SAMPLER
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['eta'] = eta
    _kwargs['s_noise'] = s_noise
    _kwargs.update(_extras)
    return node(wf, 'SamplerEulerAncestral', pass_raw=pass_raw, **_kwargs)

def SaveAudioMP3(
    wf: VibeWorkflow,
    *,
    audio: Any,
    filename_prefix: Any = 'audio/ComfyUI',
    quality: Any = 'V0',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Save Audio (MP3)
    
    Pack: comfy_core
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio'] = audio
    _kwargs['filename_prefix'] = filename_prefix
    _kwargs['quality'] = quality
    _kwargs.update(_extras)
    return node(wf, 'SaveAudioMP3', pass_raw=pass_raw, **_kwargs)

def SaveImage(
    wf: VibeWorkflow,
    *,
    images: Any,
    filename_prefix: Any = 'ComfyUI',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input images to your ComfyUI output directory.
    
    Pack: comfy
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['images'] = images
    _kwargs['filename_prefix'] = filename_prefix
    _kwargs.update(_extras)
    return node(wf, 'SaveImage', pass_raw=pass_raw, **_kwargs)

def SaveVideo(
    wf: VibeWorkflow,
    *,
    video: Any,
    filename_prefix: Any = 'video/ComfyUI',
    format: Any = 'auto',
    codec: Any = 'auto',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input images to your ComfyUI output directory.
    
    Pack: comfy_core
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['video'] = video
    _kwargs['filename_prefix'] = filename_prefix
    _kwargs['format'] = format
    _kwargs['codec'] = codec
    _kwargs.update(_extras)
    return node(wf, 'SaveVideo', pass_raw=pass_raw, **_kwargs)

def SetLatentNoiseMask(
    wf: VibeWorkflow,
    *,
    samples: Any,
    mask: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Set Latent Noise Mask
    
    Pack: comfy
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['samples'] = samples
    _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'SetLatentNoiseMask', pass_raw=pass_raw, **_kwargs)

def SimpleMath(
    wf: VibeWorkflow,
    *,
    value: Any = '',
    a: Any = 0.0,
    b: Any = 0.0,
    c: Any = 0.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Simple Math
    
    Pack: comfy_extras
    Returns: INT, FLOAT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['value'] = value
    _kwargs['a'] = a
    _kwargs['b'] = b
    _kwargs['c'] = c
    _kwargs.update(_extras)
    return node(wf, 'SimpleMath+', pass_raw=pass_raw, **_kwargs)

def SolidMask(
    wf: VibeWorkflow,
    *,
    value: Any = 1.0,
    width: Any = 512,
    height: Any = 512,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: MASK
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['value'] = value
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs.update(_extras)
    return node(wf, 'SolidMask', pass_raw=pass_raw, **_kwargs)

def StringConcatenate(
    wf: VibeWorkflow,
    *,
    string_a: Any,
    string_b: Any,
    delimiter: Any = '',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Text Concatenate
    
    Pack: comfy_core
    Returns: STRING
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['string_a'] = string_a
    _kwargs['string_b'] = string_b
    _kwargs['delimiter'] = delimiter
    _kwargs.update(_extras)
    return node(wf, 'StringConcatenate', pass_raw=pass_raw, **_kwargs)

def TextEncodeAceStepAudio1_5(
    wf: VibeWorkflow,
    *,
    clip: Any,
    tags: Any,
    lyrics: Any,
    timesignature: Any,
    language: Any,
    keyscale: Any,
    seed: Any = 0,
    bpm: Any = 120,
    duration: Any = 120.0,
    generate_audio_codes: Any = True,
    cfg_scale: Any = 2.0,
    temperature: Any = 0.85,
    top_p: Any = 0.9,
    top_k: Any = 0,
    min_p: Any = 0.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: CONDITIONING
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['clip'] = clip
    _kwargs['tags'] = tags
    _kwargs['lyrics'] = lyrics
    _kwargs['timesignature'] = timesignature
    _kwargs['language'] = language
    _kwargs['keyscale'] = keyscale
    _kwargs['seed'] = seed
    _kwargs['bpm'] = bpm
    _kwargs['duration'] = duration
    _kwargs['generate_audio_codes'] = generate_audio_codes
    _kwargs['cfg_scale'] = cfg_scale
    _kwargs['temperature'] = temperature
    _kwargs['top_p'] = top_p
    _kwargs['top_k'] = top_k
    _kwargs['min_p'] = min_p
    _kwargs.update(_extras)
    return node(wf, 'TextEncodeAceStepAudio1.5', pass_raw=pass_raw, **_kwargs)

def TextEncodeQwenImageEdit(
    wf: VibeWorkflow,
    *,
    clip: Any,
    prompt: Any,
    vae: Any = _UNSET,
    image: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: CONDITIONING
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['clip'] = clip
    _kwargs['prompt'] = prompt
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'TextEncodeQwenImageEdit', pass_raw=pass_raw, **_kwargs)

def TextGenerateLTX2Prompt(
    wf: VibeWorkflow,
    *,
    clip: Any,
    sampling_mode: Any,
    prompt: Any = '',
    max_length: Any = 256,
    image: Any = _UNSET,
    thinking: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: generated_text
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['clip'] = clip
    _kwargs['sampling_mode'] = sampling_mode
    _kwargs['prompt'] = prompt
    _kwargs['max_length'] = max_length
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs['thinking'] = thinking
    _kwargs.update(_extras)
    return node(wf, 'TextGenerateLTX2Prompt', pass_raw=pass_raw, **_kwargs)

def TrimAudioDuration(
    wf: VibeWorkflow,
    *,
    audio: Any,
    start_index: Any = 0.0,
    duration: Any = 60.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Trim audio tensor into chosen time range.
    
    Pack: comfy_core
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio'] = audio
    _kwargs['start_index'] = start_index
    _kwargs['duration'] = duration
    _kwargs.update(_extras)
    return node(wf, 'TrimAudioDuration', pass_raw=pass_raw, **_kwargs)

def TrimVideoLatent(
    wf: VibeWorkflow,
    *,
    samples: Any,
    trim_amount: Any = 0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['samples'] = samples
    _kwargs['trim_amount'] = trim_amount
    _kwargs.update(_extras)
    return node(wf, 'TrimVideoLatent', pass_raw=pass_raw, **_kwargs)

def UNETLoader(
    wf: VibeWorkflow,
    *,
    unet_name: Any,
    weight_dtype: Any = 'default',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Diffusion Model
    
    Pack: comfy
    Returns: MODEL
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['unet_name'] = unet_name
    _kwargs['weight_dtype'] = weight_dtype
    _kwargs.update(_extras)
    return node(wf, 'UNETLoader', pass_raw=pass_raw, **_kwargs)

def VAEDecode(
    wf: VibeWorkflow,
    *,
    samples: Any,
    vae: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Decodes latent images back into pixel space images.
    
    Pack: comfy
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['samples'] = samples
    _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VAEDecode', pass_raw=pass_raw, **_kwargs)

def VAEDecodeAudio(
    wf: VibeWorkflow,
    *,
    samples: Any,
    vae: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VAE Decode Audio
    
    Pack: comfy_core
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['samples'] = samples
    _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VAEDecodeAudio', pass_raw=pass_raw, **_kwargs)

def VAEDecodeTiled(
    wf: VibeWorkflow,
    *,
    samples: Any,
    vae: Any,
    tile_size: Any = 512,
    overlap: Any = 64,
    temporal_size: Any = 64,
    temporal_overlap: Any = 8,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VAE Decode (Tiled)
    
    Pack: comfy
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['samples'] = samples
    _kwargs['vae'] = vae
    _kwargs['tile_size'] = tile_size
    _kwargs['overlap'] = overlap
    _kwargs['temporal_size'] = temporal_size
    _kwargs['temporal_overlap'] = temporal_overlap
    _kwargs.update(_extras)
    return node(wf, 'VAEDecodeTiled', pass_raw=pass_raw, **_kwargs)

def VAEEncode(
    wf: VibeWorkflow,
    *,
    pixels: Any,
    vae: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VAE Encode
    
    Pack: comfy
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['pixels'] = pixels
    _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'VAEEncode', pass_raw=pass_raw, **_kwargs)

def VAELoader(
    wf: VibeWorkflow,
    *,
    vae_name: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load VAE
    
    Pack: comfy
    Returns: VAE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae_name'] = vae_name
    _kwargs.update(_extras)
    return node(wf, 'VAELoader', pass_raw=pass_raw, **_kwargs)

def WanAnimateToVideo(
    wf: VibeWorkflow,
    *,
    positive: Any,
    negative: Any,
    vae: Any,
    width: Any = 832,
    height: Any = 480,
    length: Any = 77,
    batch_size: Any = 1,
    continue_motion_max_frames: Any = 5,
    video_frame_offset: Any = 0,
    clip_vision_output: Any = _UNSET,
    reference_image: Any = _UNSET,
    face_video: Any = _UNSET,
    pose_video: Any = _UNSET,
    background_video: Any = _UNSET,
    character_mask: Any = _UNSET,
    continue_motion: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: positive, negative, latent, trim_latent, trim_image, video_frame_offset
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['vae'] = vae
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['length'] = length
    _kwargs['batch_size'] = batch_size
    _kwargs['continue_motion_max_frames'] = continue_motion_max_frames
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
    return node(wf, 'WanAnimateToVideo', pass_raw=pass_raw, **_kwargs)

def WanImageToVideo(
    wf: VibeWorkflow,
    *,
    positive: Any,
    negative: Any,
    vae: Any,
    width: Any = 832,
    height: Any = 480,
    length: Any = 81,
    batch_size: Any = 1,
    clip_vision_output: Any = _UNSET,
    start_image: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: comfy_core
    Returns: positive, negative, latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['positive'] = positive
    _kwargs['negative'] = negative
    _kwargs['vae'] = vae
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['length'] = length
    _kwargs['batch_size'] = batch_size
    if clip_vision_output is not _UNSET:
        _kwargs['clip_vision_output'] = clip_vision_output
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    _kwargs.update(_extras)
    return node(wf, 'WanImageToVideo', pass_raw=pass_raw, **_kwargs)

__all__ = ['AudioConcat', 'AudioEncoderEncode', 'AudioEncoderLoader', 'BasicScheduler', 'CFGGuider', 'CFGNorm', 'CLIPLoader', 'CLIPTextEncode', 'CLIPVisionEncode', 'CLIPVisionLoader', 'CheckpointLoaderSimple', 'ComfyMathExpression', 'ComfySwitchNode', 'ConditioningZeroOut', 'CreateVideo', 'DualCLIPLoader', 'EmptyAceStep1_5LatentAudio', 'EmptyAudio', 'EmptyFlux2LatentImage', 'EmptyHunyuanLatentVideo', 'EmptyImage', 'EmptyLTXVLatentVideo', 'EmptySD3LatentImage', 'Flux2Scheduler', 'GetImageRangeFromBatch', 'GetImageSize', 'GetVideoComponents', 'GrowMask', 'ImageBlend', 'ImageBlur', 'ImageFromBatch', 'ImageScale', 'ImageScaleBy', 'ImageScaleToTotalPixels', 'KSampler', 'KSamplerSelect', 'LTXAVTextEncoderLoader', 'LTXVAddGuide', 'LTXVAddGuideMulti', 'LTXVAudioVAEDecode', 'LTXVAudioVAEEncode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideoInplace', 'LTXVLatentUpsampler', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader', 'LoadAudio', 'LoadImage', 'LoadVideo', 'LoraLoaderModelOnly', 'ManualSigmas', 'MaskPreview', 'MaskToImage', 'ModelSamplingAuraFlow', 'ModelSamplingSD3', 'PixelPerfectResolution', 'PreviewAny', 'PreviewAudio', 'PreviewImage', 'PrimitiveStringMultiline', 'RandomNoise', 'ReferenceLatent', 'RepeatImageBatch', 'ResizeImageMaskNode', 'ResizeImagesByLongerEdge', 'SamplerCustomAdvanced', 'SamplerEulerAncestral', 'SaveAudioMP3', 'SaveImage', 'SaveVideo', 'SetLatentNoiseMask', 'SimpleMath', 'SolidMask', 'StringConcatenate', 'TextEncodeAceStepAudio1_5', 'TextEncodeQwenImageEdit', 'TextGenerateLTX2Prompt', 'TrimAudioDuration', 'TrimVideoLatent', 'UNETLoader', 'VAEDecode', 'VAEDecodeAudio', 'VAEDecodeTiled', 'VAEEncode', 'VAELoader', 'WanAnimateToVideo', 'WanImageToVideo']
