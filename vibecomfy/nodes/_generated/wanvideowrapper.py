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
    steps: Any = 30,
    cfg_scale_start: Any = 5.0,
    cfg_scale_end: Any = 5.0,
    interpolation: Any = 'linear',
    start_percent: Any = 0.0,
    end_percent: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Helper node to generate a list of floats that can be used to schedule cfg scale for the steps, outside the set range cfg is set to 1.0
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: float_list
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['steps'] = steps
    _kwargs['cfg_scale_start'] = cfg_scale_start
    _kwargs['cfg_scale_end'] = cfg_scale_end
    _kwargs['interpolation'] = interpolation
    _kwargs['start_percent'] = start_percent
    _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'CreateCFGScheduleFloatList', pass_raw=pass_raw, **_kwargs)

def DownloadAndLoadWav2VecModel(
    wf: VibeWorkflow,
    *,
    model: Any,
    base_precision: Any = 'fp16',
    load_device: Any = 'main_device',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    (Down)load Wav2Vec Model
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wav2vec_model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['base_precision'] = base_precision
    _kwargs['load_device'] = load_device
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadWav2VecModel', pass_raw=pass_raw, **_kwargs)

def LoadWanVideoClipTextEncoder(
    wf: VibeWorkflow,
    *,
    model_name: Any,
    precision: Any = 'fp16',
    load_device: Any = 'offload_device',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads Wan clip_vision model from 'ComfyUI/models/clip_vision'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wan_clip_vision
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model_name'] = model_name
    _kwargs['precision'] = precision
    _kwargs['load_device'] = load_device
    _kwargs.update(_extras)
    return node(wf, 'LoadWanVideoClipTextEncoder', pass_raw=pass_raw, **_kwargs)

def LoadWanVideoT5TextEncoder(
    wf: VibeWorkflow,
    *,
    model_name: Any,
    precision: Any = 'bf16',
    load_device: Any = 'offload_device',
    quantization: Any = 'disabled',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads Wan text_encoder model from 'ComfyUI/models/LLM'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wan_t5_model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model_name'] = model_name
    _kwargs['precision'] = precision
    _kwargs['load_device'] = load_device
    _kwargs['quantization'] = quantization
    _kwargs.update(_extras)
    return node(wf, 'LoadWanVideoT5TextEncoder', pass_raw=pass_raw, **_kwargs)

def MultiTalkModelLoader(
    wf: VibeWorkflow,
    *,
    model: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Multi/InfiniteTalk Model Loader
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'MultiTalkModelLoader', pass_raw=pass_raw, **_kwargs)

def MultiTalkWav2VecEmbeds(
    wf: VibeWorkflow,
    *,
    wav2vec_model: Any,
    audio_1: Any,
    normalize_loudness: Any = True,
    num_frames: Any = 81,
    fps: Any = 25.0,
    audio_scale: Any = 1.0,
    audio_cfg_scale: Any = 1.0,
    multi_audio_type: Any = 'para',
    audio_2: Any = _UNSET,
    audio_3: Any = _UNSET,
    audio_4: Any = _UNSET,
    ref_target_masks: Any = _UNSET,
    add_noise_floor: Any = False,
    smooth_transients: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Multi/InfiniteTalk Wav2vec2 Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: multitalk_embeds, audio, num_frames
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['wav2vec_model'] = wav2vec_model
    _kwargs['audio_1'] = audio_1
    _kwargs['normalize_loudness'] = normalize_loudness
    _kwargs['num_frames'] = num_frames
    _kwargs['fps'] = fps
    _kwargs['audio_scale'] = audio_scale
    _kwargs['audio_cfg_scale'] = audio_cfg_scale
    _kwargs['multi_audio_type'] = multi_audio_type
    if audio_2 is not _UNSET:
        _kwargs['audio_2'] = audio_2
    if audio_3 is not _UNSET:
        _kwargs['audio_3'] = audio_3
    if audio_4 is not _UNSET:
        _kwargs['audio_4'] = audio_4
    if ref_target_masks is not _UNSET:
        _kwargs['ref_target_masks'] = ref_target_masks
    _kwargs['add_noise_floor'] = add_noise_floor
    _kwargs['smooth_transients'] = smooth_transients
    _kwargs.update(_extras)
    return node(wf, 'MultiTalkWav2VecEmbeds', pass_raw=pass_raw, **_kwargs)

def NormalizeAudioLoudness(
    wf: VibeWorkflow,
    *,
    audio: Any,
    lufs: Any = -23.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Normalize Audio Loudness
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio'] = audio
    _kwargs['lufs'] = lufs
    _kwargs.update(_extras)
    return node(wf, 'NormalizeAudioLoudness', pass_raw=pass_raw, **_kwargs)

def OviMMAudioVAELoader(
    wf: VibeWorkflow,
    *,
    vae: Any,
    vocoder: Any,
    precision: Any = 'bf16',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads MMAudio VAE for Ovi audio generation
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: mmaudio_vae
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae'] = vae
    _kwargs['vocoder'] = vocoder
    _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'OviMMAudioVAELoader', pass_raw=pass_raw, **_kwargs)

def ReCamMasterPoseVisualizer(
    wf: VibeWorkflow,
    *,
    camera_poses: Any,
    base_xval: Any = 0.2,
    zval: Any = 0.3,
    scale: Any = 1.0,
    arrow_length: Any = 1,
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
    _kwargs['camera_poses'] = camera_poses
    _kwargs['base_xval'] = base_xval
    _kwargs['zval'] = zval
    _kwargs['scale'] = scale
    _kwargs['arrow_length'] = arrow_length
    _kwargs.update(_extras)
    return node(wf, 'ReCamMasterPoseVisualizer', pass_raw=pass_raw, **_kwargs)

def WanVideoAddS2VEmbeds(
    wf: VibeWorkflow,
    *,
    embeds: Any,
    frame_window_size: Any = 80,
    audio_scale: Any = 1.0,
    pose_start_percent: Any = 0.0,
    pose_end_percent: Any = 1.0,
    audio_encoder_output: Any = _UNSET,
    ref_latent: Any = _UNSET,
    pose_latent: Any = _UNSET,
    vae: Any = _UNSET,
    enable_framepack: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Add S2V Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds, audio_frame_count
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['embeds'] = embeds
    _kwargs['frame_window_size'] = frame_window_size
    _kwargs['audio_scale'] = audio_scale
    _kwargs['pose_start_percent'] = pose_start_percent
    _kwargs['pose_end_percent'] = pose_end_percent
    if audio_encoder_output is not _UNSET:
        _kwargs['audio_encoder_output'] = audio_encoder_output
    if ref_latent is not _UNSET:
        _kwargs['ref_latent'] = ref_latent
    if pose_latent is not _UNSET:
        _kwargs['pose_latent'] = pose_latent
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs['enable_framepack'] = enable_framepack
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddS2VEmbeds', pass_raw=pass_raw, **_kwargs)

def WanVideoAddWanMoveTracks(
    wf: VibeWorkflow,
    *,
    image_embeds: Any,
    strength: Any = 1.0,
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
    _kwargs['image_embeds'] = image_embeds
    _kwargs['strength'] = strength
    if track_mask is not _UNSET:
        _kwargs['track_mask'] = track_mask
    if track_coords is not _UNSET:
        _kwargs['track_coords'] = track_coords
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddWanMoveTracks', pass_raw=pass_raw, **_kwargs)

def WanVideoBlockSwap(
    wf: VibeWorkflow,
    *,
    blocks_to_swap: Any = 20,
    offload_img_emb: Any = False,
    offload_txt_emb: Any = False,
    use_non_blocking: Any = False,
    vace_blocks_to_swap: Any = 0,
    prefetch_blocks: Any = 0,
    block_swap_debug: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Settings for block swapping, reduces VRAM use by swapping blocks to CPU memory
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: block_swap_args
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['blocks_to_swap'] = blocks_to_swap
    _kwargs['offload_img_emb'] = offload_img_emb
    _kwargs['offload_txt_emb'] = offload_txt_emb
    _kwargs['use_non_blocking'] = use_non_blocking
    _kwargs['vace_blocks_to_swap'] = vace_blocks_to_swap
    _kwargs['prefetch_blocks'] = prefetch_blocks
    _kwargs['block_swap_debug'] = block_swap_debug
    _kwargs.update(_extras)
    return node(wf, 'WanVideoBlockSwap', pass_raw=pass_raw, **_kwargs)

def WanVideoClipVisionEncode(
    wf: VibeWorkflow,
    *,
    clip_vision: Any,
    image_1: Any,
    strength_1: Any = 1.0,
    strength_2: Any = 1.0,
    crop: Any = 'center',
    combine_embeds: Any = 'average',
    force_offload: Any = True,
    image_2: Any = _UNSET,
    negative_image: Any = _UNSET,
    tiles: Any = 0,
    ratio: Any = 0.5,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo ClipVision Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['clip_vision'] = clip_vision
    _kwargs['image_1'] = image_1
    _kwargs['strength_1'] = strength_1
    _kwargs['strength_2'] = strength_2
    _kwargs['crop'] = crop
    _kwargs['combine_embeds'] = combine_embeds
    _kwargs['force_offload'] = force_offload
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    if negative_image is not _UNSET:
        _kwargs['negative_image'] = negative_image
    _kwargs['tiles'] = tiles
    _kwargs['ratio'] = ratio
    _kwargs.update(_extras)
    return node(wf, 'WanVideoClipVisionEncode', pass_raw=pass_raw, **_kwargs)

def WanVideoContextOptions(
    wf: VibeWorkflow,
    *,
    context_schedule: Any,
    context_frames: Any = 81,
    context_stride: Any = 4,
    context_overlap: Any = 16,
    freenoise: Any = True,
    verbose: Any = False,
    fuse_method: Any = 'linear',
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
    _kwargs['context_schedule'] = context_schedule
    _kwargs['context_frames'] = context_frames
    _kwargs['context_stride'] = context_stride
    _kwargs['context_overlap'] = context_overlap
    _kwargs['freenoise'] = freenoise
    _kwargs['verbose'] = verbose
    _kwargs['fuse_method'] = fuse_method
    if reference_latent is not _UNSET:
        _kwargs['reference_latent'] = reference_latent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoContextOptions', pass_raw=pass_raw, **_kwargs)

def WanVideoControlEmbeds(
    wf: VibeWorkflow,
    *,
    latents: Any,
    start_percent: Any = 0.0,
    end_percent: Any = 1.0,
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
    _kwargs['latents'] = latents
    _kwargs['start_percent'] = start_percent
    _kwargs['end_percent'] = end_percent
    if fun_ref_image is not _UNSET:
        _kwargs['fun_ref_image'] = fun_ref_image
    _kwargs.update(_extras)
    return node(wf, 'WanVideoControlEmbeds', pass_raw=pass_raw, **_kwargs)

def WanVideoControlnet(
    wf: VibeWorkflow,
    *,
    model: Any,
    controlnet: Any,
    control_images: Any,
    strength: Any = 1.0,
    control_stride: Any = 3,
    control_start_percent: Any = 0.0,
    control_end_percent: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Controlnet Apply
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['controlnet'] = controlnet
    _kwargs['control_images'] = control_images
    _kwargs['strength'] = strength
    _kwargs['control_stride'] = control_stride
    _kwargs['control_start_percent'] = control_start_percent
    _kwargs['control_end_percent'] = control_end_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoControlnet', pass_raw=pass_raw, **_kwargs)

def WanVideoControlnetLoader(
    wf: VibeWorkflow,
    *,
    model: Any,
    base_precision: Any = 'bf16',
    quantization: Any = 'disabled',
    load_device: Any = 'main_device',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads ControlNet model from 'https://huggingface.co/collections/TheDenk/wan21-controlnets-68302b430411dafc0d74d2fc'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: controlnet
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['base_precision'] = base_precision
    _kwargs['quantization'] = quantization
    _kwargs['load_device'] = load_device
    _kwargs.update(_extras)
    return node(wf, 'WanVideoControlnetLoader', pass_raw=pass_raw, **_kwargs)

def WanVideoDecode(
    wf: VibeWorkflow,
    *,
    vae: Any,
    samples: Any,
    enable_vae_tiling: Any = False,
    tile_x: Any = 272,
    tile_y: Any = 272,
    tile_stride_x: Any = 144,
    tile_stride_y: Any = 128,
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
    _kwargs['vae'] = vae
    _kwargs['samples'] = samples
    _kwargs['enable_vae_tiling'] = enable_vae_tiling
    _kwargs['tile_x'] = tile_x
    _kwargs['tile_y'] = tile_y
    _kwargs['tile_stride_x'] = tile_stride_x
    _kwargs['tile_stride_y'] = tile_stride_y
    if normalization is not _UNSET:
        _kwargs['normalization'] = normalization
    _kwargs.update(_extras)
    return node(wf, 'WanVideoDecode', pass_raw=pass_raw, **_kwargs)

def WanVideoDecodeOviAudio(
    wf: VibeWorkflow,
    *,
    mmaudio_vae: Any,
    samples: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Decode Ovi Audio
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['mmaudio_vae'] = mmaudio_vae
    _kwargs['samples'] = samples
    _kwargs.update(_extras)
    return node(wf, 'WanVideoDecodeOviAudio', pass_raw=pass_raw, **_kwargs)

def WanVideoEasyCache(
    wf: VibeWorkflow,
    *,
    easycache_thresh: Any = 0.015,
    start_step: Any = 10,
    end_step: Any = -1,
    cache_device: Any = 'offload_device',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EasyCache for WanVideoWrapper, source https://github.com/H-EmbodVis/EasyCache
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: cache_args
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['easycache_thresh'] = easycache_thresh
    _kwargs['start_step'] = start_step
    _kwargs['end_step'] = end_step
    _kwargs['cache_device'] = cache_device
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEasyCache', pass_raw=pass_raw, **_kwargs)

def WanVideoEmptyEmbeds(
    wf: VibeWorkflow,
    *,
    width: Any = 832,
    height: Any = 480,
    num_frames: Any = 81,
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
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['num_frames'] = num_frames
    if control_embeds is not _UNSET:
        _kwargs['control_embeds'] = control_embeds
    if extra_latents is not _UNSET:
        _kwargs['extra_latents'] = extra_latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEmptyEmbeds', pass_raw=pass_raw, **_kwargs)

def WanVideoEmptyMMAudioLatents(
    wf: VibeWorkflow,
    *,
    length: Any = 157,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Empty MMAudio Latents
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: samples
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['length'] = length
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEmptyMMAudioLatents', pass_raw=pass_raw, **_kwargs)

def WanVideoEncode(
    wf: VibeWorkflow,
    *,
    vae: Any,
    image: Any,
    enable_vae_tiling: Any = False,
    tile_x: Any = 272,
    tile_y: Any = 272,
    tile_stride_x: Any = 144,
    tile_stride_y: Any = 128,
    noise_aug_strength: Any = 0.0,
    latent_strength: Any = 1.0,
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
    _kwargs['vae'] = vae
    _kwargs['image'] = image
    _kwargs['enable_vae_tiling'] = enable_vae_tiling
    _kwargs['tile_x'] = tile_x
    _kwargs['tile_y'] = tile_y
    _kwargs['tile_stride_x'] = tile_stride_x
    _kwargs['tile_stride_y'] = tile_stride_y
    _kwargs['noise_aug_strength'] = noise_aug_strength
    _kwargs['latent_strength'] = latent_strength
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEncode', pass_raw=pass_raw, **_kwargs)

def WanVideoEnhanceAVideo(
    wf: VibeWorkflow,
    *,
    weight: Any = 2.0,
    start_percent: Any = 0.0,
    end_percent: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: feta_args
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['weight'] = weight
    _kwargs['start_percent'] = start_percent
    _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEnhanceAVideo', pass_raw=pass_raw, **_kwargs)

def WanVideoExperimentalArgs(
    wf: VibeWorkflow,
    *,
    video_attention_split_steps: Any = '',
    cfg_zero_star: Any = False,
    use_zero_init: Any = False,
    zero_star_steps: Any = 0,
    use_fresca: Any = False,
    fresca_scale_low: Any = 1.0,
    fresca_scale_high: Any = 1.25,
    fresca_freq_cutoff: Any = 20,
    use_tcfg: Any = False,
    raag_alpha: Any = 0.0,
    bidirectional_sampling: Any = False,
    temporal_score_rescaling: Any = False,
    tsr_k: Any = 0.95,
    tsr_sigma: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Experimental stuff
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: exp_args
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['video_attention_split_steps'] = video_attention_split_steps
    _kwargs['cfg_zero_star'] = cfg_zero_star
    _kwargs['use_zero_init'] = use_zero_init
    _kwargs['zero_star_steps'] = zero_star_steps
    _kwargs['use_fresca'] = use_fresca
    _kwargs['fresca_scale_low'] = fresca_scale_low
    _kwargs['fresca_scale_high'] = fresca_scale_high
    _kwargs['fresca_freq_cutoff'] = fresca_freq_cutoff
    _kwargs['use_tcfg'] = use_tcfg
    _kwargs['raag_alpha'] = raag_alpha
    _kwargs['bidirectional_sampling'] = bidirectional_sampling
    _kwargs['temporal_score_rescaling'] = temporal_score_rescaling
    _kwargs['tsr_k'] = tsr_k
    _kwargs['tsr_sigma'] = tsr_sigma
    _kwargs.update(_extras)
    return node(wf, 'WanVideoExperimentalArgs', pass_raw=pass_raw, **_kwargs)

def WanVideoExtraModelSelect(
    wf: VibeWorkflow,
    *,
    extra_model: Any,
    prev_model: Any = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Extra model to load and add to the main model, ie. VACE or MTV Crafter 'ComfyUI/models/diffusion_models'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: extra_model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['extra_model'] = extra_model
    _kwargs['prev_model'] = prev_model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoExtraModelSelect', pass_raw=pass_raw, **_kwargs)

def WanVideoFunCameraEmbeds(
    wf: VibeWorkflow,
    *,
    poses: Any,
    width: Any = 832,
    height: Any = 480,
    strength: Any = 1.0,
    start_percent: Any = 0.0,
    end_percent: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo FunCamera Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['poses'] = poses
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['strength'] = strength
    _kwargs['start_percent'] = start_percent
    _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoFunCameraEmbeds', pass_raw=pass_raw, **_kwargs)

def WanVideoImageToVideoEncode(
    wf: VibeWorkflow,
    *,
    width: Any = 832,
    height: Any = 480,
    num_frames: Any = 81,
    noise_aug_strength: Any = 0.0,
    start_latent_strength: Any = 1.0,
    end_latent_strength: Any = 1.0,
    force_offload: Any = True,
    vae: Any = _UNSET,
    clip_embeds: Any = _UNSET,
    start_image: Any = _UNSET,
    end_image: Any = _UNSET,
    control_embeds: Any = _UNSET,
    fun_or_fl2v_model: Any = True,
    temporal_mask: Any = _UNSET,
    extra_latents: Any = _UNSET,
    tiled_vae: Any = False,
    add_cond_latents: Any = _UNSET,
    augment_empty_frames: Any = 0.0,
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
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['num_frames'] = num_frames
    _kwargs['noise_aug_strength'] = noise_aug_strength
    _kwargs['start_latent_strength'] = start_latent_strength
    _kwargs['end_latent_strength'] = end_latent_strength
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
    _kwargs['fun_or_fl2v_model'] = fun_or_fl2v_model
    if temporal_mask is not _UNSET:
        _kwargs['temporal_mask'] = temporal_mask
    if extra_latents is not _UNSET:
        _kwargs['extra_latents'] = extra_latents
    _kwargs['tiled_vae'] = tiled_vae
    if add_cond_latents is not _UNSET:
        _kwargs['add_cond_latents'] = add_cond_latents
    _kwargs['augment_empty_frames'] = augment_empty_frames
    if empty_frame_pad_image is not _UNSET:
        _kwargs['empty_frame_pad_image'] = empty_frame_pad_image
    _kwargs.update(_extras)
    return node(wf, 'WanVideoImageToVideoEncode', pass_raw=pass_raw, **_kwargs)

def WanVideoImageToVideoMultiTalk(
    wf: VibeWorkflow,
    *,
    vae: Any,
    width: Any = 832,
    height: Any = 480,
    frame_window_size: Any = 81,
    motion_frame: Any = 25,
    force_offload: Any = False,
    colormatch: Any = 'disabled',
    start_image: Any = _UNSET,
    tiled_vae: Any = False,
    clip_embeds: Any = _UNSET,
    mode: Any = 'auto',
    output_path: Any = '',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Enables Multi/InfiniteTalk long video generation sampling method, the video is created in windows with overlapping frames. Not compatible or necessary to be used with context windows and many other features besides Multi/InfiniteTalk.
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds, output_path
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae'] = vae
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['frame_window_size'] = frame_window_size
    _kwargs['motion_frame'] = motion_frame
    _kwargs['force_offload'] = force_offload
    _kwargs['colormatch'] = colormatch
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    _kwargs['tiled_vae'] = tiled_vae
    if clip_embeds is not _UNSET:
        _kwargs['clip_embeds'] = clip_embeds
    _kwargs['mode'] = mode
    _kwargs['output_path'] = output_path
    _kwargs.update(_extras)
    return node(wf, 'WanVideoImageToVideoMultiTalk', pass_raw=pass_raw, **_kwargs)

def WanVideoLoraSelect(
    wf: VibeWorkflow,
    *,
    lora: Any,
    strength: Any = 1.0,
    prev_lora: Any = None,
    blocks: Any = _UNSET,
    low_mem_load: Any = False,
    merge_loras: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select a LoRA model from ComfyUI/models/loras
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: lora
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['lora'] = lora
    _kwargs['strength'] = strength
    _kwargs['prev_lora'] = prev_lora
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    _kwargs['low_mem_load'] = low_mem_load
    _kwargs['merge_loras'] = merge_loras
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLoraSelect', pass_raw=pass_raw, **_kwargs)

def WanVideoLoraSelectMulti(
    wf: VibeWorkflow,
    *,
    lora_0: Any = 'none',
    strength_0: Any = 1.0,
    lora_1: Any = 'none',
    strength_1: Any = 1.0,
    lora_2: Any = 'none',
    strength_2: Any = 1.0,
    lora_3: Any = 'none',
    strength_3: Any = 1.0,
    lora_4: Any = 'none',
    strength_4: Any = 1.0,
    prev_lora: Any = None,
    blocks: Any = _UNSET,
    low_mem_load: Any = False,
    merge_loras: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select a LoRA model from ComfyUI/models/loras
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: lora
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['lora_0'] = lora_0
    _kwargs['strength_0'] = strength_0
    _kwargs['lora_1'] = lora_1
    _kwargs['strength_1'] = strength_1
    _kwargs['lora_2'] = lora_2
    _kwargs['strength_2'] = strength_2
    _kwargs['lora_3'] = lora_3
    _kwargs['strength_3'] = strength_3
    _kwargs['lora_4'] = lora_4
    _kwargs['strength_4'] = strength_4
    _kwargs['prev_lora'] = prev_lora
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    _kwargs['low_mem_load'] = low_mem_load
    _kwargs['merge_loras'] = merge_loras
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLoraSelectMulti', pass_raw=pass_raw, **_kwargs)

def WanVideoModelLoader(
    wf: VibeWorkflow,
    *,
    model: Any,
    base_precision: Any = 'bf16',
    quantization: Any = 'disabled',
    load_device: Any = 'offload_device',
    attention_mode: Any = 'sdpa',
    compile_args: Any = _UNSET,
    block_swap_args: Any = _UNSET,
    lora: Any = None,
    vram_management_args: Any = None,
    extra_model: Any = None,
    fantasytalking_model: Any = None,
    multitalk_model: Any = None,
    fantasyportrait_model: Any = None,
    rms_norm_function: Any = 'default',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Model Loader
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['base_precision'] = base_precision
    _kwargs['quantization'] = quantization
    _kwargs['load_device'] = load_device
    _kwargs['attention_mode'] = attention_mode
    if compile_args is not _UNSET:
        _kwargs['compile_args'] = compile_args
    if block_swap_args is not _UNSET:
        _kwargs['block_swap_args'] = block_swap_args
    _kwargs['lora'] = lora
    _kwargs['vram_management_args'] = vram_management_args
    _kwargs['extra_model'] = extra_model
    _kwargs['fantasytalking_model'] = fantasytalking_model
    _kwargs['multitalk_model'] = multitalk_model
    _kwargs['fantasyportrait_model'] = fantasyportrait_model
    _kwargs['rms_norm_function'] = rms_norm_function
    _kwargs.update(_extras)
    return node(wf, 'WanVideoModelLoader', pass_raw=pass_raw, **_kwargs)

def WanVideoOviCFG(
    wf: VibeWorkflow,
    *,
    original_text_embeds: Any,
    ovi_audio_cfg: Any = 3.0,
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
    _kwargs['original_text_embeds'] = original_text_embeds
    _kwargs['ovi_audio_cfg'] = ovi_audio_cfg
    if ovi_negative_text_embeds is not _UNSET:
        _kwargs['ovi_negative_text_embeds'] = ovi_negative_text_embeds
    _kwargs.update(_extras)
    return node(wf, 'WanVideoOviCFG', pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterCameraEmbed(
    wf: VibeWorkflow,
    *,
    camera_poses: Any,
    latents: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/KwaiVGI/ReCamMaster
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: camera_embeds, camera_poses
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['camera_poses'] = camera_poses
    _kwargs['latents'] = latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterCameraEmbed', pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterDefaultCamera(
    wf: VibeWorkflow,
    *,
    latents: Any,
    camera_type: Any = 'pan_right',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/KwaiVGI/ReCamMaster
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: camera_poses
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['latents'] = latents
    _kwargs['camera_type'] = camera_type
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterDefaultCamera', pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterGenerateOrbitCamera(
    wf: VibeWorkflow,
    *,
    num_frames: Any = 81,
    degrees: Any = 90,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/KwaiVGI/ReCamMaster
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: camera_poses
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['num_frames'] = num_frames
    _kwargs['degrees'] = degrees
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterGenerateOrbitCamera', pass_raw=pass_raw, **_kwargs)

def WanVideoSLG(
    wf: VibeWorkflow,
    *,
    blocks: Any = '10',
    start_percent: Any = 0.1,
    end_percent: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Skips uncond on the selected blocks
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: slg_args
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['blocks'] = blocks
    _kwargs['start_percent'] = start_percent
    _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSLG', pass_raw=pass_raw, **_kwargs)

def WanVideoSampler(
    wf: VibeWorkflow,
    *,
    model: Any,
    image_embeds: Any,
    steps: Any = 30,
    cfg: Any = 6.0,
    shift: Any = 5.0,
    seed: Any = 0,
    force_offload: Any = True,
    scheduler: Any = 'unipc',
    riflex_freq_index: Any = 0,
    text_embeds: Any = _UNSET,
    samples: Any = _UNSET,
    denoise_strength: Any = 1.0,
    feta_args: Any = _UNSET,
    context_options: Any = _UNSET,
    cache_args: Any = _UNSET,
    flowedit_args: Any = _UNSET,
    batched_cfg: Any = False,
    slg_args: Any = _UNSET,
    rope_function: Any = 'comfy',
    loop_args: Any = _UNSET,
    experimental_args: Any = _UNSET,
    sigmas: Any = _UNSET,
    unianimate_poses: Any = _UNSET,
    fantasytalking_embeds: Any = _UNSET,
    uni3c_embeds: Any = _UNSET,
    multitalk_embeds: Any = _UNSET,
    freeinit_args: Any = _UNSET,
    start_step: Any = 0,
    end_step: Any = -1,
    add_noise_to_samples: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Sampler
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: samples, denoised_samples
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['image_embeds'] = image_embeds
    _kwargs['steps'] = steps
    _kwargs['cfg'] = cfg
    _kwargs['shift'] = shift
    _kwargs['seed'] = seed
    _kwargs['force_offload'] = force_offload
    _kwargs['scheduler'] = scheduler
    _kwargs['riflex_freq_index'] = riflex_freq_index
    if text_embeds is not _UNSET:
        _kwargs['text_embeds'] = text_embeds
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    _kwargs['denoise_strength'] = denoise_strength
    if feta_args is not _UNSET:
        _kwargs['feta_args'] = feta_args
    if context_options is not _UNSET:
        _kwargs['context_options'] = context_options
    if cache_args is not _UNSET:
        _kwargs['cache_args'] = cache_args
    if flowedit_args is not _UNSET:
        _kwargs['flowedit_args'] = flowedit_args
    _kwargs['batched_cfg'] = batched_cfg
    if slg_args is not _UNSET:
        _kwargs['slg_args'] = slg_args
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
    _kwargs['start_step'] = start_step
    _kwargs['end_step'] = end_step
    _kwargs['add_noise_to_samples'] = add_noise_to_samples
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSampler', pass_raw=pass_raw, **_kwargs)

def WanVideoSetBlockSwap(
    wf: VibeWorkflow,
    *,
    model: Any,
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
    _kwargs['model'] = model
    if block_swap_args is not _UNSET:
        _kwargs['block_swap_args'] = block_swap_args
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetBlockSwap', pass_raw=pass_raw, **_kwargs)

def WanVideoSetLoRAs(
    wf: VibeWorkflow,
    *,
    model: Any,
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
    _kwargs['model'] = model
    if lora is not _UNSET:
        _kwargs['lora'] = lora
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetLoRAs', pass_raw=pass_raw, **_kwargs)

def WanVideoTeaCache(
    wf: VibeWorkflow,
    *,
    rel_l1_thresh: Any = 0.3,
    start_step: Any = 1,
    end_step: Any = -1,
    cache_device: Any = 'offload_device',
    use_coefficients: Any = True,
    mode: Any = 'e',
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
    _kwargs['rel_l1_thresh'] = rel_l1_thresh
    _kwargs['start_step'] = start_step
    _kwargs['end_step'] = end_step
    _kwargs['cache_device'] = cache_device
    _kwargs['use_coefficients'] = use_coefficients
    _kwargs['mode'] = mode
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTeaCache', pass_raw=pass_raw, **_kwargs)

def WanVideoTextEmbedBridge(
    wf: VibeWorkflow,
    *,
    positive: Any,
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
    _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEmbedBridge', pass_raw=pass_raw, **_kwargs)

def WanVideoTextEncode(
    wf: VibeWorkflow,
    *,
    positive_prompt: Any = '',
    negative_prompt: Any = '',
    t5: Any = _UNSET,
    force_offload: Any = True,
    model_to_offload: Any = _UNSET,
    use_disk_cache: Any = False,
    device: Any = 'gpu',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Encodes text prompts into text embeddings. For rudimentary prompt travel you can input multiple prompts separated by '|', they will be equally spread over the video length
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: text_embeds
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['positive_prompt'] = positive_prompt
    _kwargs['negative_prompt'] = negative_prompt
    if t5 is not _UNSET:
        _kwargs['t5'] = t5
    _kwargs['force_offload'] = force_offload
    if model_to_offload is not _UNSET:
        _kwargs['model_to_offload'] = model_to_offload
    _kwargs['use_disk_cache'] = use_disk_cache
    _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEncode', pass_raw=pass_raw, **_kwargs)

def WanVideoTextEncodeCached(
    wf: VibeWorkflow,
    *,
    model_name: Any,
    precision: Any = 'bf16',
    positive_prompt: Any = '',
    negative_prompt: Any = '',
    quantization: Any = 'disabled',
    use_disk_cache: Any = True,
    device: Any = 'gpu',
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
    _kwargs['model_name'] = model_name
    _kwargs['precision'] = precision
    _kwargs['positive_prompt'] = positive_prompt
    _kwargs['negative_prompt'] = negative_prompt
    _kwargs['quantization'] = quantization
    _kwargs['use_disk_cache'] = use_disk_cache
    _kwargs['device'] = device
    if extender_args is not _UNSET:
        _kwargs['extender_args'] = extender_args
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEncodeCached', pass_raw=pass_raw, **_kwargs)

def WanVideoTorchCompileSettings(
    wf: VibeWorkflow,
    *,
    backend: Any = 'inductor',
    fullgraph: Any = False,
    mode: Any = 'default',
    dynamic: Any = False,
    dynamo_cache_size_limit: Any = 64,
    compile_transformer_blocks_only: Any = True,
    dynamo_recompile_limit: Any = 128,
    force_parameter_static_shapes: Any = False,
    allow_unmerged_lora_compile: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    torch.compile settings, when connected to the model loader, torch.compile of the selected layers is attempted. Requires Triton and torch > 2.7.0 is recommended
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: torch_compile_args
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['backend'] = backend
    _kwargs['fullgraph'] = fullgraph
    _kwargs['mode'] = mode
    _kwargs['dynamic'] = dynamic
    _kwargs['dynamo_cache_size_limit'] = dynamo_cache_size_limit
    _kwargs['compile_transformer_blocks_only'] = compile_transformer_blocks_only
    _kwargs['dynamo_recompile_limit'] = dynamo_recompile_limit
    _kwargs['force_parameter_static_shapes'] = force_parameter_static_shapes
    _kwargs['allow_unmerged_lora_compile'] = allow_unmerged_lora_compile
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTorchCompileSettings', pass_raw=pass_raw, **_kwargs)

def WanVideoVACEEncode(
    wf: VibeWorkflow,
    *,
    vae: Any,
    width: Any = 832,
    height: Any = 480,
    num_frames: Any = 81,
    strength: Any = 1.0,
    vace_start_percent: Any = 0.0,
    vace_end_percent: Any = 1.0,
    input_frames: Any = _UNSET,
    ref_images: Any = _UNSET,
    input_masks: Any = _UNSET,
    prev_vace_embeds: Any = _UNSET,
    tiled_vae: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo VACE Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: vace_embeds
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae'] = vae
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['num_frames'] = num_frames
    _kwargs['strength'] = strength
    _kwargs['vace_start_percent'] = vace_start_percent
    _kwargs['vace_end_percent'] = vace_end_percent
    if input_frames is not _UNSET:
        _kwargs['input_frames'] = input_frames
    if ref_images is not _UNSET:
        _kwargs['ref_images'] = ref_images
    if input_masks is not _UNSET:
        _kwargs['input_masks'] = input_masks
    if prev_vace_embeds is not _UNSET:
        _kwargs['prev_vace_embeds'] = prev_vace_embeds
    _kwargs['tiled_vae'] = tiled_vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEEncode', pass_raw=pass_raw, **_kwargs)

def WanVideoVACEModelSelect(
    wf: VibeWorkflow,
    *,
    vace_model: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VACE model to use when not using model that has it included, loaded from 'ComfyUI/models/diffusion_models'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: extra_model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vace_model'] = vace_model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEModelSelect', pass_raw=pass_raw, **_kwargs)

def WanVideoVACEStartToEndFrame(
    wf: VibeWorkflow,
    *,
    num_frames: Any = 81,
    empty_frame_level: Any = 0.5,
    start_image: Any = _UNSET,
    end_image: Any = _UNSET,
    control_images: Any = _UNSET,
    inpaint_mask: Any = _UNSET,
    start_index: Any = 0,
    end_index: Any = -1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Helper node to create start/end frame batch and masks for VACE
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: images, masks
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['num_frames'] = num_frames
    _kwargs['empty_frame_level'] = empty_frame_level
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    if end_image is not _UNSET:
        _kwargs['end_image'] = end_image
    if control_images is not _UNSET:
        _kwargs['control_images'] = control_images
    if inpaint_mask is not _UNSET:
        _kwargs['inpaint_mask'] = inpaint_mask
    _kwargs['start_index'] = start_index
    _kwargs['end_index'] = end_index
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEStartToEndFrame', pass_raw=pass_raw, **_kwargs)

def WanVideoVAELoader(
    wf: VibeWorkflow,
    *,
    model_name: Any,
    precision: Any = 'bf16',
    compile_args: Any = _UNSET,
    use_cpu_cache: Any = False,
    verbose: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads Wan VAE model from 'ComfyUI/models/vae'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: vae
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model_name'] = model_name
    _kwargs['precision'] = precision
    if compile_args is not _UNSET:
        _kwargs['compile_args'] = compile_args
    _kwargs['use_cpu_cache'] = use_cpu_cache
    _kwargs['verbose'] = verbose
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVAELoader', pass_raw=pass_raw, **_kwargs)

def WanVideoVRAMManagement(
    wf: VibeWorkflow,
    *,
    offload_percent: Any = 1.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Alternative offloading method from DiffSynth-Studio, more aggressive in reducing memory use than block swapping, but can be slower
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: vram_management_args
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['offload_percent'] = offload_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVRAMManagement', pass_raw=pass_raw, **_kwargs)

def WanVideoWanDrawWanMoveTracks(
    wf: VibeWorkflow,
    *,
    images: Any,
    tracks: Any,
    line_resolution: Any = 24,
    circle_size: Any = 10,
    opacity: Any = 0.5,
    line_width: Any = 14,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Draw WanMove Tracks
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['images'] = images
    _kwargs['tracks'] = tracks
    _kwargs['line_resolution'] = line_resolution
    _kwargs['circle_size'] = circle_size
    _kwargs['opacity'] = opacity
    _kwargs['line_width'] = line_width
    _kwargs.update(_extras)
    return node(wf, 'WanVideoWanDrawWanMoveTracks', pass_raw=pass_raw, **_kwargs)

def Wav2VecModelLoader(
    wf: VibeWorkflow,
    *,
    model: Any,
    base_precision: Any = 'fp16',
    load_device: Any = 'main_device',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Wav2vec2 Model Loader
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wav2vec_model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['base_precision'] = base_precision
    _kwargs['load_device'] = load_device
    _kwargs.update(_extras)
    return node(wf, 'Wav2VecModelLoader', pass_raw=pass_raw, **_kwargs)

__all__ = ['CreateCFGScheduleFloatList', 'DownloadAndLoadWav2VecModel', 'LoadWanVideoClipTextEncoder', 'LoadWanVideoT5TextEncoder', 'MultiTalkModelLoader', 'MultiTalkWav2VecEmbeds', 'NormalizeAudioLoudness', 'OviMMAudioVAELoader', 'ReCamMasterPoseVisualizer', 'WanVideoAddS2VEmbeds', 'WanVideoAddWanMoveTracks', 'WanVideoBlockSwap', 'WanVideoClipVisionEncode', 'WanVideoContextOptions', 'WanVideoControlEmbeds', 'WanVideoControlnet', 'WanVideoControlnetLoader', 'WanVideoDecode', 'WanVideoDecodeOviAudio', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEmptyMMAudioLatents', 'WanVideoEncode', 'WanVideoEnhanceAVideo', 'WanVideoExperimentalArgs', 'WanVideoExtraModelSelect', 'WanVideoFunCameraEmbeds', 'WanVideoImageToVideoEncode', 'WanVideoImageToVideoMultiTalk', 'WanVideoLoraSelect', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoOviCFG', 'WanVideoReCamMasterCameraEmbed', 'WanVideoReCamMasterDefaultCamera', 'WanVideoReCamMasterGenerateOrbitCamera', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTeaCache', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVACEEncode', 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader', 'WanVideoVRAMManagement', 'WanVideoWanDrawWanMoveTracks', 'Wav2VecModelLoader']
