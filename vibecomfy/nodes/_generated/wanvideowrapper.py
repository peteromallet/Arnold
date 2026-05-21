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

def CreateCFGScheduleFloatList(
    *args: VibeWorkflow,
    _id: str | None = None,
    steps: int | _Omitted = _UNSET,
    cfg_scale_start: float | _Omitted = _UNSET,
    cfg_scale_end: float | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out'] | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Helper node to generate a list of floats that can be used to schedule cfg scale for the steps, outside the set range cfg is set to 1.0
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: float_list
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateCFGScheduleFloatList() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['TencentGameMate/chinese-wav2vec2-base', 'facebook/wav2vec2-base-960h'] | _Omitted = _UNSET,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    (Down)load Wav2Vec Model
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wav2vec_model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadWav2VecModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads Wan clip_vision model from 'ComfyUI/models/clip_vision'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wan_clip_vision
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadWanVideoClipTextEncoder() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp32', 'bf16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    quantization: Literal['disabled', 'fp8_e4m3fn'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads Wan text_encoder model from 'ComfyUI/models/LLM'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wan_t5_model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadWanVideoT5TextEncoder() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Multi/InfiniteTalk Model Loader
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MultiTalkModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'MultiTalkModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def MultiTalkWav2VecEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    wav2vec_model: Any | _Omitted = _UNSET,
    audio_1: Any | _Omitted = _UNSET,
    normalize_loudness: bool | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    fps: float | _Omitted = _UNSET,
    audio_scale: float | _Omitted = _UNSET,
    audio_cfg_scale: float | _Omitted = _UNSET,
    multi_audio_type: Literal['para', 'add'] | _Omitted = _UNSET,
    audio_2: Any | _Omitted = _UNSET,
    audio_3: Any | _Omitted = _UNSET,
    audio_4: Any | _Omitted = _UNSET,
    ref_target_masks: Any | _Omitted = _UNSET,
    add_noise_floor: bool | _Omitted = _UNSET,
    smooth_transients: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Multi/InfiniteTalk Wav2vec2 Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: multitalk_embeds, audio, num_frames
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MultiTalkWav2VecEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    lufs: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Normalize Audio Loudness
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: audio
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"NormalizeAudioLoudness() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if lufs is not _UNSET:
        _kwargs['lufs'] = lufs
    _kwargs.update(_extras)
    return node(wf, 'NormalizeAudioLoudness', _id, pass_raw=pass_raw, **_kwargs)

def OviMMAudioVAELoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = _UNSET,
    vocoder: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = _UNSET,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads MMAudio VAE for Ovi audio generation
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: mmaudio_vae
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"OviMMAudioVAELoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    camera_poses: Any | _Omitted = _UNSET,
    base_xval: float | _Omitted = _UNSET,
    zval: float | _Omitted = _UNSET,
    scale: float | _Omitted = _UNSET,
    arrow_length: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Visualizes the camera poses, from Animatediff-Evolved CameraCtrl Pose  
    or a .txt file with RealEstate camera intrinsics and coordinates, in a 3D plot.
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: IMAGE
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ReCamMasterPoseVisualizer() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    embeds: Any | _Omitted = _UNSET,
    frame_window_size: int | _Omitted = _UNSET,
    audio_scale: float | _Omitted = _UNSET,
    pose_start_percent: float | _Omitted = _UNSET,
    pose_end_percent: float | _Omitted = _UNSET,
    audio_encoder_output: Any | _Omitted = _UNSET,
    ref_latent: Any | _Omitted = _UNSET,
    pose_latent: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    enable_framepack: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Add S2V Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds, audio_frame_count
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddS2VEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    image_embeds: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    track_mask: Any | _Omitted = _UNSET,
    track_coords: str | _Omitted = _UNSET,
    tracks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Add WanMove Tracks
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds, tracks
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddWanMoveTracks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    blocks_to_swap: int | _Omitted = _UNSET,
    offload_img_emb: bool | _Omitted = _UNSET,
    offload_txt_emb: bool | _Omitted = _UNSET,
    use_non_blocking: bool | _Omitted = _UNSET,
    vace_blocks_to_swap: int | _Omitted = _UNSET,
    prefetch_blocks: int | _Omitted = _UNSET,
    block_swap_debug: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Settings for block swapping, reduces VRAM use by swapping blocks to CPU memory
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: block_swap_args
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoBlockSwap() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_vision: Any | _Omitted = _UNSET,
    image_1: Any | _Omitted = _UNSET,
    strength_1: float | _Omitted = _UNSET,
    strength_2: float | _Omitted = _UNSET,
    crop: Literal['center', 'disabled'] | _Omitted = _UNSET,
    combine_embeds: Literal['average', 'sum', 'concat', 'batch'] | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    image_2: Any | _Omitted = _UNSET,
    negative_image: Any | _Omitted = _UNSET,
    tiles: int | _Omitted = _UNSET,
    ratio: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo ClipVision Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoClipVisionEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    context_schedule: Literal['uniform_standard', 'uniform_looped', 'static_standard'] | _Omitted = _UNSET,
    context_frames: int | _Omitted = _UNSET,
    context_stride: int | _Omitted = _UNSET,
    context_overlap: int | _Omitted = _UNSET,
    freenoise: bool | _Omitted = _UNSET,
    verbose: bool | _Omitted = _UNSET,
    fuse_method: Literal['linear', 'pyramid'] | _Omitted = _UNSET,
    reference_latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Context options for WanVideo, allows splitting the video into context windows and attemps blending them for longer generations than the model and memory otherwise would allow.
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: context_options
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoContextOptions() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    start_percent: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    fun_ref_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Control Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoControlEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    controlnet: Any | _Omitted = _UNSET,
    control_images: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    control_stride: int | _Omitted = _UNSET,
    control_start_percent: float | _Omitted = _UNSET,
    control_end_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Controlnet Apply
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoControlnet() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    quantization: Literal['disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp8_e4m3fn_fast_no_ffn'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads ControlNet model from 'https://huggingface.co/collections/TheDenk/wan21-controlnets-68302b430411dafc0d74d2fc'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: controlnet
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoControlnetLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    samples: Any | _Omitted = _UNSET,
    enable_vae_tiling: bool | _Omitted = _UNSET,
    tile_x: int | _Omitted = _UNSET,
    tile_y: int | _Omitted = _UNSET,
    tile_stride_x: int | _Omitted = _UNSET,
    tile_stride_y: int | _Omitted = _UNSET,
    normalization: Literal['default', 'minmax', 'none'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Decode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: images
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoDecode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    mmaudio_vae: Any | _Omitted = _UNSET,
    samples: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Decode Ovi Audio
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: audio
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoDecodeOviAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mmaudio_vae is not _UNSET:
        _kwargs['mmaudio_vae'] = mmaudio_vae
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    _kwargs.update(_extras)
    return node(wf, 'WanVideoDecodeOviAudio', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEasyCache(
    *args: VibeWorkflow,
    _id: str | None = None,
    easycache_thresh: float | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EasyCache for WanVideoWrapper, source https://github.com/H-EmbodVis/EasyCache
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: cache_args
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEasyCache() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    control_embeds: Any | _Omitted = _UNSET,
    extra_latents: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Empty Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEmptyEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    length: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Empty MMAudio Latents
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: samples
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEmptyMMAudioLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if length is not _UNSET:
        _kwargs['length'] = length
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEmptyMMAudioLatents', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    enable_vae_tiling: bool | _Omitted = _UNSET,
    tile_x: int | _Omitted = _UNSET,
    tile_y: int | _Omitted = _UNSET,
    tile_stride_x: int | _Omitted = _UNSET,
    tile_stride_y: int | _Omitted = _UNSET,
    noise_aug_strength: float | _Omitted = _UNSET,
    latent_strength: float | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: samples
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    weight: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: feta_args
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEnhanceAVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    video_attention_split_steps: str | _Omitted = _UNSET,
    cfg_zero_star: bool | _Omitted = _UNSET,
    use_zero_init: bool | _Omitted = _UNSET,
    zero_star_steps: int | _Omitted = _UNSET,
    use_fresca: bool | _Omitted = _UNSET,
    fresca_scale_low: float | _Omitted = _UNSET,
    fresca_scale_high: float | _Omitted = _UNSET,
    fresca_freq_cutoff: int | _Omitted = _UNSET,
    use_tcfg: bool | _Omitted = _UNSET,
    raag_alpha: float | _Omitted = _UNSET,
    bidirectional_sampling: bool | _Omitted = _UNSET,
    temporal_score_rescaling: bool | _Omitted = _UNSET,
    tsr_k: float | _Omitted = _UNSET,
    tsr_sigma: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Experimental stuff
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: exp_args
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoExperimentalArgs() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    extra_model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    prev_model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Extra model to load and add to the main model, ie. VACE or MTV Crafter 'ComfyUI/models/diffusion_models'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: extra_model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoExtraModelSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if extra_model is not _UNSET:
        _kwargs['extra_model'] = extra_model
    if prev_model is not _UNSET:
        _kwargs['prev_model'] = prev_model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoExtraModelSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoFunCameraEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    poses: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo FunCamera Embeds
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoFunCameraEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    noise_aug_strength: float | _Omitted = _UNSET,
    start_latent_strength: float | _Omitted = _UNSET,
    end_latent_strength: float | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    clip_embeds: Any | _Omitted = _UNSET,
    start_image: Any | _Omitted = _UNSET,
    end_image: Any | _Omitted = _UNSET,
    control_embeds: Any | _Omitted = _UNSET,
    fun_or_fl2v_model: bool | _Omitted = _UNSET,
    temporal_mask: Any | _Omitted = _UNSET,
    extra_latents: Any | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    add_cond_latents: Any | _Omitted = _UNSET,
    augment_empty_frames: float | _Omitted = _UNSET,
    empty_frame_pad_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo ImageToVideo Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoImageToVideoEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    frame_window_size: int | _Omitted = _UNSET,
    motion_frame: int | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    colormatch: Literal['disabled', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = _UNSET,
    start_image: Any | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    clip_embeds: Any | _Omitted = _UNSET,
    mode: Literal['auto', 'multitalk', 'infinitetalk'] | _Omitted = _UNSET,
    output_path: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Enables Multi/InfiniteTalk long video generation sampling method, the video is created in windows with overlapping frames. Not compatible or necessary to be used with context windows and many other features besides Multi/InfiniteTalk.
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image_embeds, output_path
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoImageToVideoMultiTalk() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    lora: Literal['ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    prev_lora: Any | _Omitted = _UNSET,
    blocks: Any | _Omitted = _UNSET,
    low_mem_load: bool | _Omitted = _UNSET,
    merge_loras: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select a LoRA model from ComfyUI/models/loras
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: lora
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoLoraSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    lora_0: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength_0: float | _Omitted = _UNSET,
    lora_1: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength_1: float | _Omitted = _UNSET,
    lora_2: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength_2: float | _Omitted = _UNSET,
    lora_3: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength_3: float | _Omitted = _UNSET,
    lora_4: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength_4: float | _Omitted = _UNSET,
    prev_lora: Any | _Omitted = _UNSET,
    blocks: Any | _Omitted = _UNSET,
    low_mem_load: bool | _Omitted = _UNSET,
    merge_loras: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select a LoRA model from ComfyUI/models/loras
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: lora
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoLoraSelectMulti() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    base_precision: Literal['fp32', 'bf16', 'fp16', 'fp16_fast'] | _Omitted = _UNSET,
    quantization: Literal['disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e4m3fn_scaled', 'fp8_e4m3fn_scaled_fast', 'fp8_e5m2', 'fp8_e5m2_fast', 'fp8_e5m2_scaled', 'fp8_e5m2_scaled_fast'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    attention_mode: Literal['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn', 'sageattn_3', 'radial_sage_attention', 'sageattn_compiled', 'sageattn_ultravico', 'comfy'] | _Omitted = _UNSET,
    compile_args: Any | _Omitted = _UNSET,
    block_swap_args: Any | _Omitted = _UNSET,
    lora: Any | _Omitted = _UNSET,
    vram_management_args: Any | _Omitted = _UNSET,
    extra_model: Any | _Omitted = _UNSET,
    fantasytalking_model: Any | _Omitted = _UNSET,
    multitalk_model: Any | _Omitted = _UNSET,
    fantasyportrait_model: Any | _Omitted = _UNSET,
    rms_norm_function: Literal['default', 'pytorch'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Model Loader
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    original_text_embeds: Any | _Omitted = _UNSET,
    ovi_audio_cfg: float | _Omitted = _UNSET,
    ovi_negative_text_embeds: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds Ovi negative text embeddings and audio CFG scale to the text embeddings dictionary
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: text_embeds
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoOviCFG() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    camera_poses: Any | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/KwaiVGI/ReCamMaster
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: camera_embeds, camera_poses
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoReCamMasterCameraEmbed() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if camera_poses is not _UNSET:
        _kwargs['camera_poses'] = camera_poses
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterCameraEmbed', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterDefaultCamera(
    *args: VibeWorkflow,
    _id: str | None = None,
    camera_type: Literal['pan_right', 'pan_left', 'tilt_up', 'tilt_down', 'zoom_in', 'zoom_out', 'translate_up', 'translate_down', 'arc_left', 'arc_right'] | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/KwaiVGI/ReCamMaster
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: camera_poses
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoReCamMasterDefaultCamera() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if camera_type is not _UNSET:
        _kwargs['camera_type'] = camera_type
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterDefaultCamera', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterGenerateOrbitCamera(
    *args: VibeWorkflow,
    _id: str | None = None,
    num_frames: int | _Omitted = _UNSET,
    degrees: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/KwaiVGI/ReCamMaster
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: camera_poses
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoReCamMasterGenerateOrbitCamera() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if degrees is not _UNSET:
        _kwargs['degrees'] = degrees
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterGenerateOrbitCamera', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSLG(
    *args: VibeWorkflow,
    _id: str | None = None,
    blocks: str | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Skips uncond on the selected blocks
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: slg_args
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSLG() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    image_embeds: Any | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    shift: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    scheduler: Literal['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'] | _Omitted = _UNSET,
    riflex_freq_index: int | _Omitted = _UNSET,
    text_embeds: Any | _Omitted = _UNSET,
    samples: Any | _Omitted = _UNSET,
    denoise_strength: float | _Omitted = _UNSET,
    feta_args: Any | _Omitted = _UNSET,
    context_options: Any | _Omitted = _UNSET,
    cache_args: Any | _Omitted = _UNSET,
    flowedit_args: Any | _Omitted = _UNSET,
    batched_cfg: bool | _Omitted = _UNSET,
    slg_args: Any | _Omitted = _UNSET,
    rope_function: Literal['default', 'comfy', 'comfy_chunked'] | _Omitted = _UNSET,
    loop_args: Any | _Omitted = _UNSET,
    experimental_args: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    unianimate_poses: Any | _Omitted = _UNSET,
    fantasytalking_embeds: Any | _Omitted = _UNSET,
    uni3c_embeds: Any | _Omitted = _UNSET,
    multitalk_embeds: Any | _Omitted = _UNSET,
    freeinit_args: Any | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    add_noise_to_samples: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Sampler
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: samples, denoised_samples
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    block_swap_args: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Set BlockSwap
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSetBlockSwap() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if block_swap_args is not _UNSET:
        _kwargs['block_swap_args'] = block_swap_args
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetBlockSwap', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSetLoRAs(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    lora: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sets the LoRA weights to be used directly in linear layers of the model, this does NOT merge LoRAs
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSetLoRAs() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if lora is not _UNSET:
        _kwargs['lora'] = lora
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetLoRAs', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTeaCache(
    *args: VibeWorkflow,
    _id: str | None = None,
    rel_l1_thresh: float | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    use_coefficients: bool | _Omitted = _UNSET,
    mode: Literal['e', 'e0'] | _Omitted = _UNSET,
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
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTeaCache() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Bridge between ComfyUI native text embedding and WanVideoWrapper text embedding
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: text_embeds
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTextEmbedBridge() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEmbedBridge', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTextEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive_prompt: str | _Omitted = _UNSET,
    negative_prompt: str | _Omitted = _UNSET,
    t5: Any | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    model_to_offload: Any | _Omitted = _UNSET,
    use_disk_cache: bool | _Omitted = _UNSET,
    device: Literal['gpu', 'cpu'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Encodes text prompts into text embeddings. For rudimentary prompt travel you can input multiple prompts separated by '|', they will be equally spread over the video length
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: text_embeds
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTextEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp32', 'bf16'] | _Omitted = _UNSET,
    positive_prompt: str | _Omitted = _UNSET,
    negative_prompt: str | _Omitted = _UNSET,
    quantization: Literal['disabled', 'fp8_e4m3fn'] | _Omitted = _UNSET,
    use_disk_cache: bool | _Omitted = _UNSET,
    device: Literal['gpu', 'cpu'] | _Omitted = _UNSET,
    extender_args: Any | _Omitted = _UNSET,
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
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTextEncodeCached() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = _UNSET,
    fullgraph: bool | _Omitted = _UNSET,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = _UNSET,
    dynamic: bool | _Omitted = _UNSET,
    dynamo_cache_size_limit: int | _Omitted = _UNSET,
    compile_transformer_blocks_only: bool | _Omitted = _UNSET,
    dynamo_recompile_limit: int | _Omitted = _UNSET,
    force_parameter_static_shapes: bool | _Omitted = _UNSET,
    allow_unmerged_lora_compile: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    torch.compile settings, when connected to the model loader, torch.compile of the selected layers is attempted. Requires Triton and torch > 2.7.0 is recommended
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: torch_compile_args
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTorchCompileSettings() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    vace_start_percent: float | _Omitted = _UNSET,
    vace_end_percent: float | _Omitted = _UNSET,
    input_frames: Any | _Omitted = _UNSET,
    ref_images: Any | _Omitted = _UNSET,
    input_masks: Any | _Omitted = _UNSET,
    prev_vace_embeds: Any | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo VACE Encode
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: vace_embeds
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVACEEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    vace_model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VACE model to use when not using model that has it included, loaded from 'ComfyUI/models/diffusion_models'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: extra_model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVACEModelSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vace_model is not _UNSET:
        _kwargs['vace_model'] = vace_model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEModelSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVACEStartToEndFrame(
    *args: VibeWorkflow,
    _id: str | None = None,
    num_frames: int | _Omitted = _UNSET,
    empty_frame_level: float | _Omitted = _UNSET,
    start_image: Any | _Omitted = _UNSET,
    end_image: Any | _Omitted = _UNSET,
    control_images: Any | _Omitted = _UNSET,
    inpaint_mask: Any | _Omitted = _UNSET,
    start_index: int | _Omitted = _UNSET,
    end_index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Helper node to create start/end frame batch and masks for VACE
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: images, masks
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVACEStartToEndFrame() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = _UNSET,
    compile_args: Any | _Omitted = _UNSET,
    use_cpu_cache: bool | _Omitted = _UNSET,
    verbose: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads Wan VAE model from 'ComfyUI/models/vae'
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: vae
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVAELoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    offload_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Alternative offloading method from DiffSynth-Studio, more aggressive in reducing memory use than block swapping, but can be slower
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: vram_management_args
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVRAMManagement() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if offload_percent is not _UNSET:
        _kwargs['offload_percent'] = offload_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVRAMManagement', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoWanDrawWanMoveTracks(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    tracks: Any | _Omitted = _UNSET,
    line_resolution: int | _Omitted = _UNSET,
    circle_size: int | _Omitted = _UNSET,
    opacity: float | _Omitted = _UNSET,
    line_width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    WanVideo Draw WanMove Tracks
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: image
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoWanDrawWanMoveTracks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Wav2vec2 Model Loader
    
    Pack: ComfyUI-WanVideoWrapper
    Returns: wav2vec_model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Wav2VecModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
