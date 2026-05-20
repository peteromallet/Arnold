"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def CreateCFGScheduleFloatList(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    steps: Any = _UNSET,
    cfg_scale_start: Any = _UNSET,
    cfg_scale_end: Any = _UNSET,
    interpolation: Any = _UNSET,
    start_percent: Any = _UNSET,
    end_percent: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Helper node to generate a list of floats that can be used to schedule cfg scale for the steps, outside the set range cfg is set to 1.0
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: float_list
    """
    _kwargs: dict[str, Any] = {}
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if cfg_scale_start is not _UNSET:
        _kwargs['cfg_scale_start'] = cfg_scale_start
    if cfg_scale_end is not _UNSET:
        _kwargs['cfg_scale_end'] = cfg_scale_end
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'CreateCFGScheduleFloatList', _id, pass_raw=pass_raw, **_kwargs)

def DownloadAndLoadWav2VecModel(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    base_precision: Any = _UNSET,
    load_device: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    (Down)load Wav2Vec Model
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wav2vec_model
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadWav2VecModel', _id, pass_raw=pass_raw, **_kwargs)

def LoadWanVideoClipTextEncoder(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model_name: Any = _UNSET,
    precision: Any = _UNSET,
    load_device: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads Wan clip_vision model from 'ComfyUI/models/clip_vision'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wan_clip_vision
    """
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    _kwargs.update(_extras)
    return node(wf, 'LoadWanVideoClipTextEncoder', _id, pass_raw=pass_raw, **_kwargs)

def LoadWanVideoT5TextEncoder(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model_name: Any = _UNSET,
    precision: Any = _UNSET,
    load_device: Any = _UNSET,
    quantization: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads Wan text_encoder model from 'ComfyUI/models/LLM'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wan_t5_model
    """
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if quantization is not _UNSET:
        _kwargs['quantization'] = quantization
    _kwargs.update(_extras)
    return node(wf, 'LoadWanVideoT5TextEncoder', _id, pass_raw=pass_raw, **_kwargs)

def MultiTalkModelLoader(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Multi/InfiniteTalk Model Loader
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'MultiTalkModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def MultiTalkWav2VecEmbeds(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    wav2vec_model: Any = _UNSET,
    audio_1: Any = _UNSET,
    normalize_loudness: Any = _UNSET,
    num_frames: Any = _UNSET,
    fps: Any = _UNSET,
    audio_scale: Any = _UNSET,
    audio_cfg_scale: Any = _UNSET,
    multi_audio_type: Any = _UNSET,
    audio_2: Any = _UNSET,
    audio_3: Any = _UNSET,
    audio_4: Any = _UNSET,
    ref_target_masks: Any = _UNSET,
    add_noise_floor: Any = _UNSET,
    smooth_transients: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Multi/InfiniteTalk Wav2vec2 Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: multitalk_embeds, audio, num_frames
    """
    _kwargs: dict[str, Any] = {}
    if wav2vec_model is not _UNSET:
        _kwargs['wav2vec_model'] = wav2vec_model
    if audio_1 is not _UNSET:
        _kwargs['audio_1'] = audio_1
    if normalize_loudness is not _UNSET:
        _kwargs['normalize_loudness'] = normalize_loudness
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    if audio_scale is not _UNSET:
        _kwargs['audio_scale'] = audio_scale
    if audio_cfg_scale is not _UNSET:
        _kwargs['audio_cfg_scale'] = audio_cfg_scale
    if multi_audio_type is not _UNSET:
        _kwargs['multi_audio_type'] = multi_audio_type
    if audio_2 is not _UNSET:
        _kwargs['audio_2'] = audio_2
    if audio_3 is not _UNSET:
        _kwargs['audio_3'] = audio_3
    if audio_4 is not _UNSET:
        _kwargs['audio_4'] = audio_4
    if ref_target_masks is not _UNSET:
        _kwargs['ref_target_masks'] = ref_target_masks
    if add_noise_floor is not _UNSET:
        _kwargs['add_noise_floor'] = add_noise_floor
    if smooth_transients is not _UNSET:
        _kwargs['smooth_transients'] = smooth_transients
    _kwargs.update(_extras)
    return node(wf, 'MultiTalkWav2VecEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def NormalizeAudioLoudness(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    audio: Any = _UNSET,
    lufs: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Normalize Audio Loudness
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if lufs is not _UNSET:
        _kwargs['lufs'] = lufs
    _kwargs.update(_extras)
    return node(wf, 'NormalizeAudioLoudness', _id, pass_raw=pass_raw, **_kwargs)

def OviMMAudioVAELoader(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    vae: Any = _UNSET,
    vocoder: Any = _UNSET,
    precision: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads MMAudio VAE for Ovi audio generation
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: mmaudio_vae
    """
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if vocoder is not _UNSET:
        _kwargs['vocoder'] = vocoder
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'OviMMAudioVAELoader', _id, pass_raw=pass_raw, **_kwargs)

def ReCamMasterPoseVisualizer(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    camera_poses: Any = _UNSET,
    base_xval: Any = _UNSET,
    zval: Any = _UNSET,
    scale: Any = _UNSET,
    arrow_length: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Visualizes the camera poses, from Animatediff-Evolved CameraCtrl Pose  
    or a .txt file with RealEstate camera intrinsics and coordinates, in a 3D plot.
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    if camera_poses is not _UNSET:
        _kwargs['camera_poses'] = camera_poses
    if base_xval is not _UNSET:
        _kwargs['base_xval'] = base_xval
    if zval is not _UNSET:
        _kwargs['zval'] = zval
    if scale is not _UNSET:
        _kwargs['scale'] = scale
    if arrow_length is not _UNSET:
        _kwargs['arrow_length'] = arrow_length
    _kwargs.update(_extras)
    return node(wf, 'ReCamMasterPoseVisualizer', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddS2VEmbeds(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    embeds: Any = _UNSET,
    frame_window_size: Any = _UNSET,
    audio_scale: Any = _UNSET,
    pose_start_percent: Any = _UNSET,
    pose_end_percent: Any = _UNSET,
    audio_encoder_output: Any = _UNSET,
    ref_latent: Any = _UNSET,
    pose_latent: Any = _UNSET,
    vae: Any = _UNSET,
    enable_framepack: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Add S2V Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds, audio_frame_count
    """
    _kwargs: dict[str, Any] = {}
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if frame_window_size is not _UNSET:
        _kwargs['frame_window_size'] = frame_window_size
    if audio_scale is not _UNSET:
        _kwargs['audio_scale'] = audio_scale
    if pose_start_percent is not _UNSET:
        _kwargs['pose_start_percent'] = pose_start_percent
    if pose_end_percent is not _UNSET:
        _kwargs['pose_end_percent'] = pose_end_percent
    if audio_encoder_output is not _UNSET:
        _kwargs['audio_encoder_output'] = audio_encoder_output
    if ref_latent is not _UNSET:
        _kwargs['ref_latent'] = ref_latent
    if pose_latent is not _UNSET:
        _kwargs['pose_latent'] = pose_latent
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if enable_framepack is not _UNSET:
        _kwargs['enable_framepack'] = enable_framepack
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddS2VEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddWanMoveTracks(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    image_embeds: Any = _UNSET,
    strength: Any = _UNSET,
    track_mask: Any = _UNSET,
    track_coords: Any = _UNSET,
    tracks: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Add WanMove Tracks
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds, tracks
    """
    _kwargs: dict[str, Any] = {}
    if image_embeds is not _UNSET:
        _kwargs['image_embeds'] = image_embeds
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if track_mask is not _UNSET:
        _kwargs['track_mask'] = track_mask
    if track_coords is not _UNSET:
        _kwargs['track_coords'] = track_coords
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddWanMoveTracks', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoBlockSwap(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    blocks_to_swap: Any = _UNSET,
    offload_img_emb: Any = _UNSET,
    offload_txt_emb: Any = _UNSET,
    use_non_blocking: Any = _UNSET,
    vace_blocks_to_swap: Any = _UNSET,
    prefetch_blocks: Any = _UNSET,
    block_swap_debug: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Settings for block swapping, reduces VRAM use by swapping blocks to CPU memory
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: block_swap_args
    """
    _kwargs: dict[str, Any] = {}
    if blocks_to_swap is not _UNSET:
        _kwargs['blocks_to_swap'] = blocks_to_swap
    if offload_img_emb is not _UNSET:
        _kwargs['offload_img_emb'] = offload_img_emb
    if offload_txt_emb is not _UNSET:
        _kwargs['offload_txt_emb'] = offload_txt_emb
    if use_non_blocking is not _UNSET:
        _kwargs['use_non_blocking'] = use_non_blocking
    if vace_blocks_to_swap is not _UNSET:
        _kwargs['vace_blocks_to_swap'] = vace_blocks_to_swap
    if prefetch_blocks is not _UNSET:
        _kwargs['prefetch_blocks'] = prefetch_blocks
    if block_swap_debug is not _UNSET:
        _kwargs['block_swap_debug'] = block_swap_debug
    _kwargs.update(_extras)
    return node(wf, 'WanVideoBlockSwap', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoClipVisionEncode(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    clip_vision: Any = _UNSET,
    image_1: Any = _UNSET,
    strength_1: Any = _UNSET,
    strength_2: Any = _UNSET,
    crop: Any = _UNSET,
    combine_embeds: Any = _UNSET,
    force_offload: Any = _UNSET,
    image_2: Any = _UNSET,
    negative_image: Any = _UNSET,
    tiles: Any = _UNSET,
    ratio: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo ClipVision Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    """
    _kwargs: dict[str, Any] = {}
    if clip_vision is not _UNSET:
        _kwargs['clip_vision'] = clip_vision
    if image_1 is not _UNSET:
        _kwargs['image_1'] = image_1
    if strength_1 is not _UNSET:
        _kwargs['strength_1'] = strength_1
    if strength_2 is not _UNSET:
        _kwargs['strength_2'] = strength_2
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if combine_embeds is not _UNSET:
        _kwargs['combine_embeds'] = combine_embeds
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    if negative_image is not _UNSET:
        _kwargs['negative_image'] = negative_image
    if tiles is not _UNSET:
        _kwargs['tiles'] = tiles
    if ratio is not _UNSET:
        _kwargs['ratio'] = ratio
    _kwargs.update(_extras)
    return node(wf, 'WanVideoClipVisionEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoContextOptions(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    context_schedule: Any = _UNSET,
    context_frames: Any = _UNSET,
    context_stride: Any = _UNSET,
    context_overlap: Any = _UNSET,
    freenoise: Any = _UNSET,
    verbose: Any = _UNSET,
    fuse_method: Any = _UNSET,
    reference_latent: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context options for WanVideo, allows splitting the video into context windows and attemps blending them for longer generations than the model and memory otherwise would allow.
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: context_options
    """
    _kwargs: dict[str, Any] = {}
    if context_schedule is not _UNSET:
        _kwargs['context_schedule'] = context_schedule
    if context_frames is not _UNSET:
        _kwargs['context_frames'] = context_frames
    if context_stride is not _UNSET:
        _kwargs['context_stride'] = context_stride
    if context_overlap is not _UNSET:
        _kwargs['context_overlap'] = context_overlap
    if freenoise is not _UNSET:
        _kwargs['freenoise'] = freenoise
    if verbose is not _UNSET:
        _kwargs['verbose'] = verbose
    if fuse_method is not _UNSET:
        _kwargs['fuse_method'] = fuse_method
    if reference_latent is not _UNSET:
        _kwargs['reference_latent'] = reference_latent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoContextOptions', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoControlEmbeds(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    start_percent: Any = _UNSET,
    end_percent: Any = _UNSET,
    latents: Any = _UNSET,
    fun_ref_image: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Control Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    """
    _kwargs: dict[str, Any] = {}
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if fun_ref_image is not _UNSET:
        _kwargs['fun_ref_image'] = fun_ref_image
    _kwargs.update(_extras)
    return node(wf, 'WanVideoControlEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoControlnet(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    controlnet: Any = _UNSET,
    control_images: Any = _UNSET,
    strength: Any = _UNSET,
    control_stride: Any = _UNSET,
    control_start_percent: Any = _UNSET,
    control_end_percent: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Controlnet Apply
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if controlnet is not _UNSET:
        _kwargs['controlnet'] = controlnet
    if control_images is not _UNSET:
        _kwargs['control_images'] = control_images
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if control_stride is not _UNSET:
        _kwargs['control_stride'] = control_stride
    if control_start_percent is not _UNSET:
        _kwargs['control_start_percent'] = control_start_percent
    if control_end_percent is not _UNSET:
        _kwargs['control_end_percent'] = control_end_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoControlnet', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoControlnetLoader(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    base_precision: Any = _UNSET,
    quantization: Any = _UNSET,
    load_device: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads ControlNet model from 'https://huggingface.co/collections/TheDenk/wan21-controlnets-68302b430411dafc0d74d2fc'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: controlnet
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if quantization is not _UNSET:
        _kwargs['quantization'] = quantization
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    _kwargs.update(_extras)
    return node(wf, 'WanVideoControlnetLoader', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoDecode(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    vae: Any = _UNSET,
    samples: Any = _UNSET,
    enable_vae_tiling: Any = _UNSET,
    tile_x: Any = _UNSET,
    tile_y: Any = _UNSET,
    tile_stride_x: Any = _UNSET,
    tile_stride_y: Any = _UNSET,
    normalization: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Decode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: images
    """
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if enable_vae_tiling is not _UNSET:
        _kwargs['enable_vae_tiling'] = enable_vae_tiling
    if tile_x is not _UNSET:
        _kwargs['tile_x'] = tile_x
    if tile_y is not _UNSET:
        _kwargs['tile_y'] = tile_y
    if tile_stride_x is not _UNSET:
        _kwargs['tile_stride_x'] = tile_stride_x
    if tile_stride_y is not _UNSET:
        _kwargs['tile_stride_y'] = tile_stride_y
    if normalization is not _UNSET:
        _kwargs['normalization'] = normalization
    _kwargs.update(_extras)
    return node(wf, 'WanVideoDecode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoDecodeOviAudio(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    mmaudio_vae: Any = _UNSET,
    samples: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Decode Ovi Audio
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    if mmaudio_vae is not _UNSET:
        _kwargs['mmaudio_vae'] = mmaudio_vae
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    _kwargs.update(_extras)
    return node(wf, 'WanVideoDecodeOviAudio', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEasyCache(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    easycache_thresh: Any = _UNSET,
    start_step: Any = _UNSET,
    end_step: Any = _UNSET,
    cache_device: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EasyCache for WanVideoWrapper, source https://github.com/H-EmbodVis/EasyCache
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: cache_args
    """
    _kwargs: dict[str, Any] = {}
    if easycache_thresh is not _UNSET:
        _kwargs['easycache_thresh'] = easycache_thresh
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if cache_device is not _UNSET:
        _kwargs['cache_device'] = cache_device
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEasyCache', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEmptyEmbeds(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    width: Any = _UNSET,
    height: Any = _UNSET,
    num_frames: Any = _UNSET,
    control_embeds: Any = _UNSET,
    extra_latents: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Empty Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    """
    _kwargs: dict[str, Any] = {}
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if control_embeds is not _UNSET:
        _kwargs['control_embeds'] = control_embeds
    if extra_latents is not _UNSET:
        _kwargs['extra_latents'] = extra_latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEmptyEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEmptyMMAudioLatents(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    length: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Empty MMAudio Latents
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: samples
    """
    _kwargs: dict[str, Any] = {}
    if length is not _UNSET:
        _kwargs['length'] = length
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEmptyMMAudioLatents', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEncode(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    vae: Any = _UNSET,
    image: Any = _UNSET,
    enable_vae_tiling: Any = _UNSET,
    tile_x: Any = _UNSET,
    tile_y: Any = _UNSET,
    tile_stride_x: Any = _UNSET,
    tile_stride_y: Any = _UNSET,
    noise_aug_strength: Any = _UNSET,
    latent_strength: Any = _UNSET,
    mask: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: samples
    """
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if image is not _UNSET:
        _kwargs['image'] = image
    if enable_vae_tiling is not _UNSET:
        _kwargs['enable_vae_tiling'] = enable_vae_tiling
    if tile_x is not _UNSET:
        _kwargs['tile_x'] = tile_x
    if tile_y is not _UNSET:
        _kwargs['tile_y'] = tile_y
    if tile_stride_x is not _UNSET:
        _kwargs['tile_stride_x'] = tile_stride_x
    if tile_stride_y is not _UNSET:
        _kwargs['tile_stride_y'] = tile_stride_y
    if noise_aug_strength is not _UNSET:
        _kwargs['noise_aug_strength'] = noise_aug_strength
    if latent_strength is not _UNSET:
        _kwargs['latent_strength'] = latent_strength
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEnhanceAVideo(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    weight: Any = _UNSET,
    start_percent: Any = _UNSET,
    end_percent: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: feta_args
    """
    _kwargs: dict[str, Any] = {}
    if weight is not _UNSET:
        _kwargs['weight'] = weight
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEnhanceAVideo', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoExperimentalArgs(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    video_attention_split_steps: Any = _UNSET,
    cfg_zero_star: Any = _UNSET,
    use_zero_init: Any = _UNSET,
    zero_star_steps: Any = _UNSET,
    use_fresca: Any = _UNSET,
    fresca_scale_low: Any = _UNSET,
    fresca_scale_high: Any = _UNSET,
    fresca_freq_cutoff: Any = _UNSET,
    use_tcfg: Any = _UNSET,
    raag_alpha: Any = _UNSET,
    bidirectional_sampling: Any = _UNSET,
    temporal_score_rescaling: Any = _UNSET,
    tsr_k: Any = _UNSET,
    tsr_sigma: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Experimental stuff
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: exp_args
    """
    _kwargs: dict[str, Any] = {}
    if video_attention_split_steps is not _UNSET:
        _kwargs['video_attention_split_steps'] = video_attention_split_steps
    if cfg_zero_star is not _UNSET:
        _kwargs['cfg_zero_star'] = cfg_zero_star
    if use_zero_init is not _UNSET:
        _kwargs['use_zero_init'] = use_zero_init
    if zero_star_steps is not _UNSET:
        _kwargs['zero_star_steps'] = zero_star_steps
    if use_fresca is not _UNSET:
        _kwargs['use_fresca'] = use_fresca
    if fresca_scale_low is not _UNSET:
        _kwargs['fresca_scale_low'] = fresca_scale_low
    if fresca_scale_high is not _UNSET:
        _kwargs['fresca_scale_high'] = fresca_scale_high
    if fresca_freq_cutoff is not _UNSET:
        _kwargs['fresca_freq_cutoff'] = fresca_freq_cutoff
    if use_tcfg is not _UNSET:
        _kwargs['use_tcfg'] = use_tcfg
    if raag_alpha is not _UNSET:
        _kwargs['raag_alpha'] = raag_alpha
    if bidirectional_sampling is not _UNSET:
        _kwargs['bidirectional_sampling'] = bidirectional_sampling
    if temporal_score_rescaling is not _UNSET:
        _kwargs['temporal_score_rescaling'] = temporal_score_rescaling
    if tsr_k is not _UNSET:
        _kwargs['tsr_k'] = tsr_k
    if tsr_sigma is not _UNSET:
        _kwargs['tsr_sigma'] = tsr_sigma
    _kwargs.update(_extras)
    return node(wf, 'WanVideoExperimentalArgs', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoExtraModelSelect(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    extra_model: Any = _UNSET,
    prev_model: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Extra model to load and add to the main model, ie. VACE or MTV Crafter 'ComfyUI/models/diffusion_models'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: extra_model
    """
    _kwargs: dict[str, Any] = {}
    if extra_model is not _UNSET:
        _kwargs['extra_model'] = extra_model
    if prev_model is not _UNSET:
        _kwargs['prev_model'] = prev_model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoExtraModelSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoFunCameraEmbeds(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    poses: Any = _UNSET,
    width: Any = _UNSET,
    height: Any = _UNSET,
    strength: Any = _UNSET,
    start_percent: Any = _UNSET,
    end_percent: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo FunCamera Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    """
    _kwargs: dict[str, Any] = {}
    if poses is not _UNSET:
        _kwargs['poses'] = poses
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoFunCameraEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoImageToVideoEncode(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    width: Any = _UNSET,
    height: Any = _UNSET,
    num_frames: Any = _UNSET,
    noise_aug_strength: Any = _UNSET,
    start_latent_strength: Any = _UNSET,
    end_latent_strength: Any = _UNSET,
    force_offload: Any = _UNSET,
    vae: Any = _UNSET,
    clip_embeds: Any = _UNSET,
    start_image: Any = _UNSET,
    end_image: Any = _UNSET,
    control_embeds: Any = _UNSET,
    fun_or_fl2v_model: Any = _UNSET,
    temporal_mask: Any = _UNSET,
    extra_latents: Any = _UNSET,
    tiled_vae: Any = _UNSET,
    add_cond_latents: Any = _UNSET,
    augment_empty_frames: Any = _UNSET,
    empty_frame_pad_image: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo ImageToVideo Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    """
    _kwargs: dict[str, Any] = {}
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if noise_aug_strength is not _UNSET:
        _kwargs['noise_aug_strength'] = noise_aug_strength
    if start_latent_strength is not _UNSET:
        _kwargs['start_latent_strength'] = start_latent_strength
    if end_latent_strength is not _UNSET:
        _kwargs['end_latent_strength'] = end_latent_strength
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if clip_embeds is not _UNSET:
        _kwargs['clip_embeds'] = clip_embeds
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    if end_image is not _UNSET:
        _kwargs['end_image'] = end_image
    if control_embeds is not _UNSET:
        _kwargs['control_embeds'] = control_embeds
    if fun_or_fl2v_model is not _UNSET:
        _kwargs['fun_or_fl2v_model'] = fun_or_fl2v_model
    if temporal_mask is not _UNSET:
        _kwargs['temporal_mask'] = temporal_mask
    if extra_latents is not _UNSET:
        _kwargs['extra_latents'] = extra_latents
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    if add_cond_latents is not _UNSET:
        _kwargs['add_cond_latents'] = add_cond_latents
    if augment_empty_frames is not _UNSET:
        _kwargs['augment_empty_frames'] = augment_empty_frames
    if empty_frame_pad_image is not _UNSET:
        _kwargs['empty_frame_pad_image'] = empty_frame_pad_image
    _kwargs.update(_extras)
    return node(wf, 'WanVideoImageToVideoEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoImageToVideoMultiTalk(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    vae: Any = _UNSET,
    width: Any = _UNSET,
    height: Any = _UNSET,
    frame_window_size: Any = _UNSET,
    motion_frame: Any = _UNSET,
    force_offload: Any = _UNSET,
    colormatch: Any = _UNSET,
    start_image: Any = _UNSET,
    tiled_vae: Any = _UNSET,
    clip_embeds: Any = _UNSET,
    mode: Any = _UNSET,
    output_path: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Enables Multi/InfiniteTalk long video generation sampling method, the video is created in windows with overlapping frames. Not compatible or necessary to be used with context windows and many other features besides Multi/InfiniteTalk.
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds, output_path
    """
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if frame_window_size is not _UNSET:
        _kwargs['frame_window_size'] = frame_window_size
    if motion_frame is not _UNSET:
        _kwargs['motion_frame'] = motion_frame
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if colormatch is not _UNSET:
        _kwargs['colormatch'] = colormatch
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    if clip_embeds is not _UNSET:
        _kwargs['clip_embeds'] = clip_embeds
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if output_path is not _UNSET:
        _kwargs['output_path'] = output_path
    _kwargs.update(_extras)
    return node(wf, 'WanVideoImageToVideoMultiTalk', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoLoraSelect(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    lora: Any = _UNSET,
    strength: Any = _UNSET,
    prev_lora: Any = _UNSET,
    blocks: Any = _UNSET,
    low_mem_load: Any = _UNSET,
    merge_loras: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select a LoRA model from ComfyUI/models/loras
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: lora
    """
    _kwargs: dict[str, Any] = {}
    if lora is not _UNSET:
        _kwargs['lora'] = lora
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if prev_lora is not _UNSET:
        _kwargs['prev_lora'] = prev_lora
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    if low_mem_load is not _UNSET:
        _kwargs['low_mem_load'] = low_mem_load
    if merge_loras is not _UNSET:
        _kwargs['merge_loras'] = merge_loras
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLoraSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoLoraSelectMulti(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    lora_0: Any = _UNSET,
    strength_0: Any = _UNSET,
    lora_1: Any = _UNSET,
    strength_1: Any = _UNSET,
    lora_2: Any = _UNSET,
    strength_2: Any = _UNSET,
    lora_3: Any = _UNSET,
    strength_3: Any = _UNSET,
    lora_4: Any = _UNSET,
    strength_4: Any = _UNSET,
    prev_lora: Any = _UNSET,
    blocks: Any = _UNSET,
    low_mem_load: Any = _UNSET,
    merge_loras: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select a LoRA model from ComfyUI/models/loras
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: lora
    """
    _kwargs: dict[str, Any] = {}
    if lora_0 is not _UNSET:
        _kwargs['lora_0'] = lora_0
    if strength_0 is not _UNSET:
        _kwargs['strength_0'] = strength_0
    if lora_1 is not _UNSET:
        _kwargs['lora_1'] = lora_1
    if strength_1 is not _UNSET:
        _kwargs['strength_1'] = strength_1
    if lora_2 is not _UNSET:
        _kwargs['lora_2'] = lora_2
    if strength_2 is not _UNSET:
        _kwargs['strength_2'] = strength_2
    if lora_3 is not _UNSET:
        _kwargs['lora_3'] = lora_3
    if strength_3 is not _UNSET:
        _kwargs['strength_3'] = strength_3
    if lora_4 is not _UNSET:
        _kwargs['lora_4'] = lora_4
    if strength_4 is not _UNSET:
        _kwargs['strength_4'] = strength_4
    if prev_lora is not _UNSET:
        _kwargs['prev_lora'] = prev_lora
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    if low_mem_load is not _UNSET:
        _kwargs['low_mem_load'] = low_mem_load
    if merge_loras is not _UNSET:
        _kwargs['merge_loras'] = merge_loras
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLoraSelectMulti', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoModelLoader(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    base_precision: Any = _UNSET,
    quantization: Any = _UNSET,
    load_device: Any = _UNSET,
    attention_mode: Any = _UNSET,
    compile_args: Any = _UNSET,
    block_swap_args: Any = _UNSET,
    lora: Any = _UNSET,
    vram_management_args: Any = _UNSET,
    extra_model: Any = _UNSET,
    fantasytalking_model: Any = _UNSET,
    multitalk_model: Any = _UNSET,
    fantasyportrait_model: Any = _UNSET,
    rms_norm_function: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Model Loader
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if quantization is not _UNSET:
        _kwargs['quantization'] = quantization
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if attention_mode is not _UNSET:
        _kwargs['attention_mode'] = attention_mode
    if compile_args is not _UNSET:
        _kwargs['compile_args'] = compile_args
    if block_swap_args is not _UNSET:
        _kwargs['block_swap_args'] = block_swap_args
    if lora is not _UNSET:
        _kwargs['lora'] = lora
    if vram_management_args is not _UNSET:
        _kwargs['vram_management_args'] = vram_management_args
    if extra_model is not _UNSET:
        _kwargs['extra_model'] = extra_model
    if fantasytalking_model is not _UNSET:
        _kwargs['fantasytalking_model'] = fantasytalking_model
    if multitalk_model is not _UNSET:
        _kwargs['multitalk_model'] = multitalk_model
    if fantasyportrait_model is not _UNSET:
        _kwargs['fantasyportrait_model'] = fantasyportrait_model
    if rms_norm_function is not _UNSET:
        _kwargs['rms_norm_function'] = rms_norm_function
    _kwargs.update(_extras)
    return node(wf, 'WanVideoModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoOviCFG(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    original_text_embeds: Any = _UNSET,
    ovi_audio_cfg: Any = _UNSET,
    ovi_negative_text_embeds: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds Ovi negative text embeddings and audio CFG scale to the text embeddings dictionary
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: text_embeds
    """
    _kwargs: dict[str, Any] = {}
    if original_text_embeds is not _UNSET:
        _kwargs['original_text_embeds'] = original_text_embeds
    if ovi_audio_cfg is not _UNSET:
        _kwargs['ovi_audio_cfg'] = ovi_audio_cfg
    if ovi_negative_text_embeds is not _UNSET:
        _kwargs['ovi_negative_text_embeds'] = ovi_negative_text_embeds
    _kwargs.update(_extras)
    return node(wf, 'WanVideoOviCFG', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterCameraEmbed(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    camera_poses: Any = _UNSET,
    latents: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/KwaiVGI/ReCamMaster
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: camera_embeds, camera_poses
    """
    _kwargs: dict[str, Any] = {}
    if camera_poses is not _UNSET:
        _kwargs['camera_poses'] = camera_poses
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterCameraEmbed', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterDefaultCamera(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    camera_type: Any = _UNSET,
    latents: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/KwaiVGI/ReCamMaster
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: camera_poses
    """
    _kwargs: dict[str, Any] = {}
    if camera_type is not _UNSET:
        _kwargs['camera_type'] = camera_type
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterDefaultCamera', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterGenerateOrbitCamera(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    num_frames: Any = _UNSET,
    degrees: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/KwaiVGI/ReCamMaster
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: camera_poses
    """
    _kwargs: dict[str, Any] = {}
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if degrees is not _UNSET:
        _kwargs['degrees'] = degrees
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterGenerateOrbitCamera', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSLG(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    blocks: Any = _UNSET,
    start_percent: Any = _UNSET,
    end_percent: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Skips uncond on the selected blocks
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: slg_args
    """
    _kwargs: dict[str, Any] = {}
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSLG', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSampler(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    image_embeds: Any = _UNSET,
    steps: Any = _UNSET,
    cfg: Any = _UNSET,
    shift: Any = _UNSET,
    seed: Any = _UNSET,
    force_offload: Any = _UNSET,
    scheduler: Any = _UNSET,
    riflex_freq_index: Any = _UNSET,
    text_embeds: Any = _UNSET,
    samples: Any = _UNSET,
    denoise_strength: Any = _UNSET,
    feta_args: Any = _UNSET,
    context_options: Any = _UNSET,
    cache_args: Any = _UNSET,
    flowedit_args: Any = _UNSET,
    batched_cfg: Any = _UNSET,
    slg_args: Any = _UNSET,
    rope_function: Any = _UNSET,
    loop_args: Any = _UNSET,
    experimental_args: Any = _UNSET,
    sigmas: Any = _UNSET,
    unianimate_poses: Any = _UNSET,
    fantasytalking_embeds: Any = _UNSET,
    uni3c_embeds: Any = _UNSET,
    multitalk_embeds: Any = _UNSET,
    freeinit_args: Any = _UNSET,
    start_step: Any = _UNSET,
    end_step: Any = _UNSET,
    add_noise_to_samples: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Sampler
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: samples, denoised_samples
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if image_embeds is not _UNSET:
        _kwargs['image_embeds'] = image_embeds
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if shift is not _UNSET:
        _kwargs['shift'] = shift
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if riflex_freq_index is not _UNSET:
        _kwargs['riflex_freq_index'] = riflex_freq_index
    if text_embeds is not _UNSET:
        _kwargs['text_embeds'] = text_embeds
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if denoise_strength is not _UNSET:
        _kwargs['denoise_strength'] = denoise_strength
    if feta_args is not _UNSET:
        _kwargs['feta_args'] = feta_args
    if context_options is not _UNSET:
        _kwargs['context_options'] = context_options
    if cache_args is not _UNSET:
        _kwargs['cache_args'] = cache_args
    if flowedit_args is not _UNSET:
        _kwargs['flowedit_args'] = flowedit_args
    if batched_cfg is not _UNSET:
        _kwargs['batched_cfg'] = batched_cfg
    if slg_args is not _UNSET:
        _kwargs['slg_args'] = slg_args
    if rope_function is not _UNSET:
        _kwargs['rope_function'] = rope_function
    if loop_args is not _UNSET:
        _kwargs['loop_args'] = loop_args
    if experimental_args is not _UNSET:
        _kwargs['experimental_args'] = experimental_args
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if unianimate_poses is not _UNSET:
        _kwargs['unianimate_poses'] = unianimate_poses
    if fantasytalking_embeds is not _UNSET:
        _kwargs['fantasytalking_embeds'] = fantasytalking_embeds
    if uni3c_embeds is not _UNSET:
        _kwargs['uni3c_embeds'] = uni3c_embeds
    if multitalk_embeds is not _UNSET:
        _kwargs['multitalk_embeds'] = multitalk_embeds
    if freeinit_args is not _UNSET:
        _kwargs['freeinit_args'] = freeinit_args
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if add_noise_to_samples is not _UNSET:
        _kwargs['add_noise_to_samples'] = add_noise_to_samples
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSampler', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSetBlockSwap(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    block_swap_args: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Set BlockSwap
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if block_swap_args is not _UNSET:
        _kwargs['block_swap_args'] = block_swap_args
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetBlockSwap', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSetLoRAs(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    lora: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sets the LoRA weights to be used directly in linear layers of the model, this does NOT merge LoRAs
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if lora is not _UNSET:
        _kwargs['lora'] = lora
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetLoRAs', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTeaCache(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    rel_l1_thresh: Any = _UNSET,
    start_step: Any = _UNSET,
    end_step: Any = _UNSET,
    cache_device: Any = _UNSET,
    use_coefficients: Any = _UNSET,
    mode: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Patch WanVideo model to use TeaCache. Speeds up inference by caching the output and  
    applying it instead of doing the step.  Best results are achieved by choosing the  
    appropriate coefficients for the model. Early steps should never be skipped, with too  
    aggressive values this can happen and the motion suffers. Starting later can help with that too.   
    When NOT using coefficients, the threshold value should be  
    about 10 times smaller than the value used with coefficients.  
    
    Official recommended values https://github.com/ali-vilab/TeaCache/tree/main/TeaCache4Wan2.1
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: cache_args
    """
    _kwargs: dict[str, Any] = {}
    if rel_l1_thresh is not _UNSET:
        _kwargs['rel_l1_thresh'] = rel_l1_thresh
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if cache_device is not _UNSET:
        _kwargs['cache_device'] = cache_device
    if use_coefficients is not _UNSET:
        _kwargs['use_coefficients'] = use_coefficients
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTeaCache', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTextEmbedBridge(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    positive: Any = _UNSET,
    negative: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Bridge between ComfyUI native text embedding and WanVideoWrapper text embedding
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: text_embeds
    """
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEmbedBridge', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTextEncode(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    positive_prompt: Any = _UNSET,
    negative_prompt: Any = _UNSET,
    t5: Any = _UNSET,
    force_offload: Any = _UNSET,
    model_to_offload: Any = _UNSET,
    use_disk_cache: Any = _UNSET,
    device: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Encodes text prompts into text embeddings. For rudimentary prompt travel you can input multiple prompts separated by '|', they will be equally spread over the video length
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: text_embeds
    """
    _kwargs: dict[str, Any] = {}
    if positive_prompt is not _UNSET:
        _kwargs['positive_prompt'] = positive_prompt
    if negative_prompt is not _UNSET:
        _kwargs['negative_prompt'] = negative_prompt
    if t5 is not _UNSET:
        _kwargs['t5'] = t5
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if model_to_offload is not _UNSET:
        _kwargs['model_to_offload'] = model_to_offload
    if use_disk_cache is not _UNSET:
        _kwargs['use_disk_cache'] = use_disk_cache
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTextEncodeCached(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model_name: Any = _UNSET,
    precision: Any = _UNSET,
    positive_prompt: Any = _UNSET,
    negative_prompt: Any = _UNSET,
    quantization: Any = _UNSET,
    use_disk_cache: Any = _UNSET,
    device: Any = _UNSET,
    extender_args: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Encodes text prompts into text embeddings. This node loads and completely unloads the T5 after done,  
    leaving no VRAM or RAM imprint. If prompts have been cached before T5 is not loaded at all.  
    negative output is meant to be used with NAG, it contains only negative prompt embeddings.  
    
    Additionally you can provide a Qwen LLM model to extend the positive prompt with either one  
    of the original Wan templates or a custom system prompt.
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: text_embeds, negative_text_embeds, positive_prompt
    """
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if positive_prompt is not _UNSET:
        _kwargs['positive_prompt'] = positive_prompt
    if negative_prompt is not _UNSET:
        _kwargs['negative_prompt'] = negative_prompt
    if quantization is not _UNSET:
        _kwargs['quantization'] = quantization
    if use_disk_cache is not _UNSET:
        _kwargs['use_disk_cache'] = use_disk_cache
    if device is not _UNSET:
        _kwargs['device'] = device
    if extender_args is not _UNSET:
        _kwargs['extender_args'] = extender_args
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEncodeCached', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTorchCompileSettings(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    backend: Any = _UNSET,
    fullgraph: Any = _UNSET,
    mode: Any = _UNSET,
    dynamic: Any = _UNSET,
    dynamo_cache_size_limit: Any = _UNSET,
    compile_transformer_blocks_only: Any = _UNSET,
    dynamo_recompile_limit: Any = _UNSET,
    force_parameter_static_shapes: Any = _UNSET,
    allow_unmerged_lora_compile: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    torch.compile settings, when connected to the model loader, torch.compile of the selected layers is attempted. Requires Triton and torch > 2.7.0 is recommended
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: torch_compile_args
    """
    _kwargs: dict[str, Any] = {}
    if backend is not _UNSET:
        _kwargs['backend'] = backend
    if fullgraph is not _UNSET:
        _kwargs['fullgraph'] = fullgraph
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if dynamic is not _UNSET:
        _kwargs['dynamic'] = dynamic
    if dynamo_cache_size_limit is not _UNSET:
        _kwargs['dynamo_cache_size_limit'] = dynamo_cache_size_limit
    if compile_transformer_blocks_only is not _UNSET:
        _kwargs['compile_transformer_blocks_only'] = compile_transformer_blocks_only
    if dynamo_recompile_limit is not _UNSET:
        _kwargs['dynamo_recompile_limit'] = dynamo_recompile_limit
    if force_parameter_static_shapes is not _UNSET:
        _kwargs['force_parameter_static_shapes'] = force_parameter_static_shapes
    if allow_unmerged_lora_compile is not _UNSET:
        _kwargs['allow_unmerged_lora_compile'] = allow_unmerged_lora_compile
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTorchCompileSettings', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVACEEncode(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    vae: Any = _UNSET,
    width: Any = _UNSET,
    height: Any = _UNSET,
    num_frames: Any = _UNSET,
    strength: Any = _UNSET,
    vace_start_percent: Any = _UNSET,
    vace_end_percent: Any = _UNSET,
    input_frames: Any = _UNSET,
    ref_images: Any = _UNSET,
    input_masks: Any = _UNSET,
    prev_vace_embeds: Any = _UNSET,
    tiled_vae: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo VACE Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: vace_embeds
    """
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if vace_start_percent is not _UNSET:
        _kwargs['vace_start_percent'] = vace_start_percent
    if vace_end_percent is not _UNSET:
        _kwargs['vace_end_percent'] = vace_end_percent
    if input_frames is not _UNSET:
        _kwargs['input_frames'] = input_frames
    if ref_images is not _UNSET:
        _kwargs['ref_images'] = ref_images
    if input_masks is not _UNSET:
        _kwargs['input_masks'] = input_masks
    if prev_vace_embeds is not _UNSET:
        _kwargs['prev_vace_embeds'] = prev_vace_embeds
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVACEModelSelect(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    vace_model: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VACE model to use when not using model that has it included, loaded from 'ComfyUI/models/diffusion_models'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: extra_model
    """
    _kwargs: dict[str, Any] = {}
    if vace_model is not _UNSET:
        _kwargs['vace_model'] = vace_model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEModelSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVACEStartToEndFrame(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    num_frames: Any = _UNSET,
    empty_frame_level: Any = _UNSET,
    start_image: Any = _UNSET,
    end_image: Any = _UNSET,
    control_images: Any = _UNSET,
    inpaint_mask: Any = _UNSET,
    start_index: Any = _UNSET,
    end_index: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Helper node to create start/end frame batch and masks for VACE
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: images, masks
    """
    _kwargs: dict[str, Any] = {}
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if empty_frame_level is not _UNSET:
        _kwargs['empty_frame_level'] = empty_frame_level
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    if end_image is not _UNSET:
        _kwargs['end_image'] = end_image
    if control_images is not _UNSET:
        _kwargs['control_images'] = control_images
    if inpaint_mask is not _UNSET:
        _kwargs['inpaint_mask'] = inpaint_mask
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    if end_index is not _UNSET:
        _kwargs['end_index'] = end_index
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEStartToEndFrame', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVAELoader(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model_name: Any = _UNSET,
    precision: Any = _UNSET,
    compile_args: Any = _UNSET,
    use_cpu_cache: Any = _UNSET,
    verbose: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads Wan VAE model from 'ComfyUI/models/vae'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: vae
    """
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if compile_args is not _UNSET:
        _kwargs['compile_args'] = compile_args
    if use_cpu_cache is not _UNSET:
        _kwargs['use_cpu_cache'] = use_cpu_cache
    if verbose is not _UNSET:
        _kwargs['verbose'] = verbose
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVAELoader', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVRAMManagement(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    offload_percent: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Alternative offloading method from DiffSynth-Studio, more aggressive in reducing memory use than block swapping, but can be slower
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: vram_management_args
    """
    _kwargs: dict[str, Any] = {}
    if offload_percent is not _UNSET:
        _kwargs['offload_percent'] = offload_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVRAMManagement', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoWanDrawWanMoveTracks(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    images: Any = _UNSET,
    tracks: Any = _UNSET,
    line_resolution: Any = _UNSET,
    circle_size: Any = _UNSET,
    opacity: Any = _UNSET,
    line_width: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Draw WanMove Tracks
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image
    """
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    if line_resolution is not _UNSET:
        _kwargs['line_resolution'] = line_resolution
    if circle_size is not _UNSET:
        _kwargs['circle_size'] = circle_size
    if opacity is not _UNSET:
        _kwargs['opacity'] = opacity
    if line_width is not _UNSET:
        _kwargs['line_width'] = line_width
    _kwargs.update(_extras)
    return node(wf, 'WanVideoWanDrawWanMoveTracks', _id, pass_raw=pass_raw, **_kwargs)

def Wav2VecModelLoader(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    base_precision: Any = _UNSET,
    load_device: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Wav2vec2 Model Loader
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wav2vec_model
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    _kwargs.update(_extras)
    return node(wf, 'Wav2VecModelLoader', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['CreateCFGScheduleFloatList', 'DownloadAndLoadWav2VecModel', 'LoadWanVideoClipTextEncoder', 'LoadWanVideoT5TextEncoder', 'MultiTalkModelLoader', 'MultiTalkWav2VecEmbeds', 'NormalizeAudioLoudness', 'OviMMAudioVAELoader', 'ReCamMasterPoseVisualizer', 'WanVideoAddS2VEmbeds', 'WanVideoAddWanMoveTracks', 'WanVideoBlockSwap', 'WanVideoClipVisionEncode', 'WanVideoContextOptions', 'WanVideoControlEmbeds', 'WanVideoControlnet', 'WanVideoControlnetLoader', 'WanVideoDecode', 'WanVideoDecodeOviAudio', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEmptyMMAudioLatents', 'WanVideoEncode', 'WanVideoEnhanceAVideo', 'WanVideoExperimentalArgs', 'WanVideoExtraModelSelect', 'WanVideoFunCameraEmbeds', 'WanVideoImageToVideoEncode', 'WanVideoImageToVideoMultiTalk', 'WanVideoLoraSelect', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoOviCFG', 'WanVideoReCamMasterCameraEmbed', 'WanVideoReCamMasterDefaultCamera', 'WanVideoReCamMasterGenerateOrbitCamera', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTeaCache', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVACEEncode', 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader', 'WanVideoVRAMManagement', 'WanVideoWanDrawWanMoveTracks', 'Wav2VecModelLoader']
