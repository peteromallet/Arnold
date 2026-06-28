# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def CreateCFGScheduleFloatList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    steps: int | _Omitted = ...,
    cfg_scale_start: float | _Omitted = ...,
    cfg_scale_end: float | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out'] | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateScheduleFloatList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    steps: int | _Omitted = ...,
    start_value: float | _Omitted = ...,
    end_value: float | _Omitted = ...,
    default_value: float | _Omitted = ...,
    interpolation: Literal['linear', 'ease_in', 'ease_out'] | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DownloadAndLoadNLFModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    url: Literal['https://github.com/isarandi/nlf/releases/download/v0.3.2/nlf_l_multi_0.3.2.torchscript', 'https://github.com/isarandi/nlf/releases/download/v0.2.2/nlf_l_multi_0.2.2.torchscript'] | _Omitted = ...,
    warmup: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DownloadAndLoadWav2VecModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['TencentGameMate/chinese-wav2vec2-base', 'facebook/wav2vec2-base-960h'] | _Omitted = ...,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = ...,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DrawArcFaceLandmarks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lynx_face_embeds: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    image_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DrawGaussianNoiseOnImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    device: Literal['cpu', 'gpu'] | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DrawNLFPoses(
    *args: VibeWorkflow,
    _id: str | None = ...,
    poses: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    stick_width: float | _Omitted = ...,
    point_radius: int | _Omitted = ...,
    style: Literal['original', 'scail'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DummyComfyWanModelObject(
    *args: VibeWorkflow,
    _id: str | None = ...,
    shift: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ExtractStartFramesForContinuations(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input_video_frames: Any | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FaceMaskFromPoseKeypoints(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pose_kps: Any | _Omitted = ...,
    person_index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FantasyPortraitFaceDetector(
    *args: VibeWorkflow,
    _id: str | None = ...,
    portrait_model: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    adapter_scale: float | _Omitted = ...,
    mouth_scale: float | _Omitted = ...,
    emo_scale: float | _Omitted = ...,
    device: Literal['cuda', 'cpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FantasyPortraitModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = ...,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FantasyTalkingModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = ...,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def FantasyTalkingWav2VecEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    wav2vec_model: Any | _Omitted = ...,
    fantasytalking_model: Any | _Omitted = ...,
    audio: Any | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    fps: float | _Omitted = ...,
    audio_scale: float | _Omitted = ...,
    audio_cfg_scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def HuMoEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    num_frames: int | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    audio_scale: float | _Omitted = ...,
    audio_cfg_scale: float | _Omitted = ...,
    audio_start_percent: float | _Omitted = ...,
    audio_end_percent: float | _Omitted = ...,
    whisper_model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    reference_images: Any | _Omitted = ...,
    audio: Any | _Omitted = ...,
    tiled_vae: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LandmarksToImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    landmarks: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadLynxResampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = ...,
    precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadNLFModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    nlf_model: Any | _Omitted = ...,
    warmup: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadVQVAE(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadWanVideoClipTextEncoder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = ...,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = ...,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadWanVideoT5TextEncoder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = ...,
    precision: Literal['fp32', 'bf16'] | _Omitted = ...,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    quantization: Literal['disabled', 'fp8_e4m3fn'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LynxEncodeFaceIP(
    *args: VibeWorkflow,
    _id: str | None = ...,
    resampler: Any | _Omitted = ...,
    ip_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LynxInsightFaceCrop(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MTVCrafterEncodePoses(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vqvae: Any | _Omitted = ...,
    poses: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MochaEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    input_video: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    ref1: Any | _Omitted = ...,
    ref2: Any | _Omitted = ...,
    tiled_vae: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MultiTalkModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MultiTalkSilentEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    num_frames: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MultiTalkWav2VecEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    wav2vec_model: Any | _Omitted = ...,
    audio_1: Any | _Omitted = ...,
    normalize_loudness: bool | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    fps: float | _Omitted = ...,
    audio_scale: float | _Omitted = ...,
    audio_cfg_scale: float | _Omitted = ...,
    multi_audio_type: Literal['para', 'add'] | _Omitted = ...,
    audio_2: Any | _Omitted = ...,
    audio_3: Any | _Omitted = ...,
    audio_4: Any | _Omitted = ...,
    ref_target_masks: Any | _Omitted = ...,
    add_noise_floor: bool | _Omitted = ...,
    smooth_transients: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def NLFPredict(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    per_batch: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def NormalizeAudioLoudness(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    lufs: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OviMMAudioVAELoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = ...,
    vocoder: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = ...,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def QwenLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = ...,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReCamMasterPoseVisualizer(
    *args: VibeWorkflow,
    _id: str | None = ...,
    camera_poses: Any | _Omitted = ...,
    base_xval: float | _Omitted = ...,
    zval: float | _Omitted = ...,
    scale: float | _Omitted = ...,
    arrow_length: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextImageEncodeQwenVL(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanMove_native(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    track_coords: str | _Omitted = ...,
    track_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoATITracks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    tracks: str | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    temperature: float | _Omitted = ...,
    topk: int | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoATITracksVisualize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    tracks: str | _Omitted = ...,
    min_radius: int | _Omitted = ...,
    max_radius: int | _Omitted = ...,
    max_retain: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoATI_comfy(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    tracks: str | _Omitted = ...,
    temperature: float | _Omitted = ...,
    topk: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddBindweaveEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    reference_latents: Any | _Omitted = ...,
    ref_masks: Any | _Omitted = ...,
    qwenvl_embeds_pos: Any | _Omitted = ...,
    qwenvl_embeds_neg: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddControlEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    latents: Any | _Omitted = ...,
    fun_ref_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddDualControlEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    first_frame_noise_level: float | _Omitted = ...,
    dense: Any | _Omitted = ...,
    sparse: Any | _Omitted = ...,
    prev_images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddExtraLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    extra_latents: Any | _Omitted = ...,
    latent_index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddFantasyPortrait(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    portrait_embeds: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    portrait_cfg: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddFlashVSRInput(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddLucyEditLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    extra_latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddLynxEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    ip_scale: float | _Omitted = ...,
    ref_scale: float | _Omitted = ...,
    lynx_cfg_scale: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    vae: Any | _Omitted = ...,
    lynx_ip_embeds: Any | _Omitted = ...,
    ref_image: Any | _Omitted = ...,
    ref_text_embed: Any | _Omitted = ...,
    ref_blocks_to_use: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddMTVMotion(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    mtv_crafter_motion: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddOneToAllExtendEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    prev_latents: Any | _Omitted = ...,
    window_size: int | _Omitted = ...,
    overlap: int | _Omitted = ...,
    frames_processed: int | _Omitted = ...,
    if_not_enough_frames: Literal['pad_with_last', 'error'] | _Omitted = ...,
    pose_images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddOneToAllPoseEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    pose_images: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pose_prefix_image: Any | _Omitted = ...,
    pose_cfg_scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddOneToAllReferenceEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    ref_image: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    ref_mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddOviAudioToLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    original_samples: Any | _Omitted = ...,
    audio_samples: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddPusaNoise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    noise_multipliers: float | _Omitted = ...,
    noisy_steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddS2VEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    frame_window_size: int | _Omitted = ...,
    audio_scale: float | _Omitted = ...,
    pose_start_percent: float | _Omitted = ...,
    pose_end_percent: float | _Omitted = ...,
    audio_encoder_output: Any | _Omitted = ...,
    ref_latent: Any | _Omitted = ...,
    pose_latent: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    enable_framepack: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddSCAILPoseEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pose_images: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddSCAILReferenceEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    ref_image: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    clip_embeds: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddStandInLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    ip_image_latent: Any | _Omitted = ...,
    freq_offset: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddSteadyDancerEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    pose_latents_positive: Any | _Omitted = ...,
    pose_strength_spatial: float | _Omitted = ...,
    pose_strength_temporal: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pose_latents_negative: Any | _Omitted = ...,
    clip_vision_embeds: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddStoryMemLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    embeds: Any | _Omitted = ...,
    memory_images: Any | _Omitted = ...,
    rope_negative_offset: bool | _Omitted = ...,
    rope_negative_offset_frames: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddTTMLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    reference_latents: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    start_step: int | _Omitted = ...,
    end_step: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAddWanMoveTracks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_embeds: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    track_mask: Any | _Omitted = ...,
    track_coords: str | _Omitted = ...,
    tracks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoAnimateEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    frame_window_size: int | _Omitted = ...,
    colormatch: Literal['disabled', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = ...,
    pose_strength: float | _Omitted = ...,
    face_strength: float | _Omitted = ...,
    clip_embeds: Any | _Omitted = ...,
    ref_images: Any | _Omitted = ...,
    pose_images: Any | _Omitted = ...,
    face_images: Any | _Omitted = ...,
    bg_images: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    start_ref_image: Any | _Omitted = ...,
    tiled_vae: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoApplyNAG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    original_text_embeds: Any | _Omitted = ...,
    nag_text_embeds: Any | _Omitted = ...,
    nag_scale: float | _Omitted = ...,
    nag_tau: float | _Omitted = ...,
    nag_alpha: float | _Omitted = ...,
    inplace: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoBlockList(
    *args: VibeWorkflow,
    _id: str | None = ...,
    blocks: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoBlockSwap(
    *args: VibeWorkflow,
    _id: str | None = ...,
    blocks_to_swap: int | _Omitted = ...,
    offload_img_emb: bool | _Omitted = ...,
    offload_txt_emb: bool | _Omitted = ...,
    use_non_blocking: bool | _Omitted = ...,
    vace_blocks_to_swap: int | _Omitted = ...,
    prefetch_blocks: int | _Omitted = ...,
    block_swap_debug: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoClipVisionEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    image_1: Any | _Omitted = ...,
    strength_1: float | _Omitted = ...,
    strength_2: float | _Omitted = ...,
    crop: Literal['center', 'disabled'] | _Omitted = ...,
    combine_embeds: Literal['average', 'sum', 'concat', 'batch'] | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    image_2: Any | _Omitted = ...,
    negative_image: Any | _Omitted = ...,
    tiles: int | _Omitted = ...,
    ratio: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoCombineEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds_1: Any | _Omitted = ...,
    embeds_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoContextOptions(
    *args: VibeWorkflow,
    _id: str | None = ...,
    context_schedule: Literal['uniform_standard', 'uniform_looped', 'static_standard'] | _Omitted = ...,
    context_frames: int | _Omitted = ...,
    context_stride: int | _Omitted = ...,
    context_overlap: int | _Omitted = ...,
    freenoise: bool | _Omitted = ...,
    verbose: bool | _Omitted = ...,
    fuse_method: Literal['linear', 'pyramid'] | _Omitted = ...,
    reference_latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoControlEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    latents: Any | _Omitted = ...,
    fun_ref_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoControlnet(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    controlnet: Any | _Omitted = ...,
    control_images: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    control_stride: int | _Omitted = ...,
    control_start_percent: float | _Omitted = ...,
    control_end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoControlnetLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = ...,
    quantization: Literal['disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp8_e4m3fn_fast_no_ffn'] | _Omitted = ...,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoDecode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    enable_vae_tiling: bool | _Omitted = ...,
    tile_x: int | _Omitted = ...,
    tile_y: int | _Omitted = ...,
    tile_stride_x: int | _Omitted = ...,
    tile_stride_y: int | _Omitted = ...,
    normalization: Literal['default', 'minmax', 'none'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoDecodeOviAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mmaudio_vae: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoDiffusionForcingSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    text_embeds: Any | _Omitted = ...,
    image_embeds: Any | _Omitted = ...,
    addnoise_condition: int | _Omitted = ...,
    fps: float | _Omitted = ...,
    steps: int | _Omitted = ...,
    cfg: float | _Omitted = ...,
    shift: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    scheduler: Literal['unipc', 'unipc/beta', 'euler', 'euler/beta', 'lcm', 'lcm/beta'] | _Omitted = ...,
    samples: Any | _Omitted = ...,
    prefix_samples: Any | _Omitted = ...,
    denoise_strength: float | _Omitted = ...,
    cache_args: Any | _Omitted = ...,
    slg_args: Any | _Omitted = ...,
    rope_function: Literal['default', 'comfy'] | _Omitted = ...,
    experimental_args: Any | _Omitted = ...,
    unianimate_poses: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoEasyCache(
    *args: VibeWorkflow,
    _id: str | None = ...,
    easycache_thresh: float | _Omitted = ...,
    start_step: int | _Omitted = ...,
    end_step: int | _Omitted = ...,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoEmptyEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    control_embeds: Any | _Omitted = ...,
    extra_latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoEmptyMMAudioLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    length: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    enable_vae_tiling: bool | _Omitted = ...,
    tile_x: int | _Omitted = ...,
    tile_y: int | _Omitted = ...,
    tile_stride_x: int | _Omitted = ...,
    tile_stride_y: int | _Omitted = ...,
    noise_aug_strength: float | _Omitted = ...,
    latent_strength: float | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoEncodeLatentBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    enable_vae_tiling: bool | _Omitted = ...,
    tile_x: int | _Omitted = ...,
    tile_y: int | _Omitted = ...,
    tile_stride_x: int | _Omitted = ...,
    tile_stride_y: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoEncodeOviAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mmaudio_vae: Any | _Omitted = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoEnhanceAVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    weight: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoExperimentalArgs(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video_attention_split_steps: str | _Omitted = ...,
    cfg_zero_star: bool | _Omitted = ...,
    use_zero_init: bool | _Omitted = ...,
    zero_star_steps: int | _Omitted = ...,
    use_fresca: bool | _Omitted = ...,
    fresca_scale_low: float | _Omitted = ...,
    fresca_scale_high: float | _Omitted = ...,
    fresca_freq_cutoff: int | _Omitted = ...,
    use_tcfg: bool | _Omitted = ...,
    raag_alpha: float | _Omitted = ...,
    bidirectional_sampling: bool | _Omitted = ...,
    temporal_score_rescaling: bool | _Omitted = ...,
    tsr_k: float | _Omitted = ...,
    tsr_sigma: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoExtraModelSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
    extra_model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = ...,
    prev_model: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoFlashVSRDecoderLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = ...,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoFreeInitArgs(
    *args: VibeWorkflow,
    _id: str | None = ...,
    freeinit_num_iters: int | _Omitted = ...,
    freeinit_method: Literal['butterworth', 'ideal', 'gaussian', 'none'] | _Omitted = ...,
    freeinit_n: int | _Omitted = ...,
    freeinit_d_s: float | _Omitted = ...,
    freeinit_d_t: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoFunCameraEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    poses: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoImageClipEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    generation_width: int | _Omitted = ...,
    generation_height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    noise_aug_strength: float | _Omitted = ...,
    latent_strength: float | _Omitted = ...,
    clip_embed_strength: float | _Omitted = ...,
    adjust_resolution: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoImageResizeToClosest(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    generation_width: int | _Omitted = ...,
    generation_height: int | _Omitted = ...,
    aspect_ratio_preservation: Literal['keep_input', 'stretch_to_new', 'crop_to_new'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoImageToVideoEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    noise_aug_strength: float | _Omitted = ...,
    start_latent_strength: float | _Omitted = ...,
    end_latent_strength: float | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    vae: Any | _Omitted = ...,
    clip_embeds: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    end_image: Any | _Omitted = ...,
    control_embeds: Any | _Omitted = ...,
    fun_or_fl2v_model: bool | _Omitted = ...,
    temporal_mask: Any | _Omitted = ...,
    extra_latents: Any | _Omitted = ...,
    tiled_vae: bool | _Omitted = ...,
    add_cond_latents: Any | _Omitted = ...,
    augment_empty_frames: float | _Omitted = ...,
    empty_frame_pad_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoImageToVideoMultiTalk(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    frame_window_size: int | _Omitted = ...,
    motion_frame: int | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    colormatch: Literal['disabled', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    tiled_vae: bool | _Omitted = ...,
    clip_embeds: Any | _Omitted = ...,
    mode: Literal['auto', 'multitalk', 'infinitetalk'] | _Omitted = ...,
    output_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoImageToVideoSkyreelsv3_audio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    frame_window_size: int | _Omitted = ...,
    motion_frame: int | _Omitted = ...,
    drop_frames: int | _Omitted = ...,
    tiled_vae: bool | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    colormatch: Literal['disabled', 'reinhard_torch', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    reference_video: Any | _Omitted = ...,
    clip_embeds: Any | _Omitted = ...,
    output_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoLatentReScale(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    direction: Literal['comfy_to_wrapper', 'wrapper_to_comfy'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoLongCatAvatarExtendEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prev_latents: Any | _Omitted = ...,
    audio_embeds: Any | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    overlap: int | _Omitted = ...,
    frames_processed: int | _Omitted = ...,
    if_not_enough_audio: Any | _Omitted = ...,
    ref_frame_index: int | _Omitted = ...,
    ref_mask_frame_range: int | _Omitted = ...,
    ref_latent: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoLoopArgs(
    *args: VibeWorkflow,
    _id: str | None = ...,
    shift_skip: int | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoLoraBlockEdit(
    *args: VibeWorkflow,
    _id: str | None = ...,
    blocks_0: bool | _Omitted = ...,
    blocks_1: bool | _Omitted = ...,
    blocks_2: bool | _Omitted = ...,
    blocks_3: bool | _Omitted = ...,
    blocks_4: bool | _Omitted = ...,
    blocks_5: bool | _Omitted = ...,
    blocks_6: bool | _Omitted = ...,
    blocks_7: bool | _Omitted = ...,
    blocks_8: bool | _Omitted = ...,
    blocks_9: bool | _Omitted = ...,
    blocks_10: bool | _Omitted = ...,
    blocks_11: bool | _Omitted = ...,
    blocks_12: bool | _Omitted = ...,
    blocks_13: bool | _Omitted = ...,
    blocks_14: bool | _Omitted = ...,
    blocks_15: bool | _Omitted = ...,
    blocks_16: bool | _Omitted = ...,
    blocks_17: bool | _Omitted = ...,
    blocks_18: bool | _Omitted = ...,
    blocks_19: bool | _Omitted = ...,
    blocks_20: bool | _Omitted = ...,
    blocks_21: bool | _Omitted = ...,
    blocks_22: bool | _Omitted = ...,
    blocks_23: bool | _Omitted = ...,
    blocks_24: bool | _Omitted = ...,
    blocks_25: bool | _Omitted = ...,
    blocks_26: bool | _Omitted = ...,
    blocks_27: bool | _Omitted = ...,
    blocks_28: bool | _Omitted = ...,
    blocks_29: bool | _Omitted = ...,
    blocks_30: bool | _Omitted = ...,
    blocks_31: bool | _Omitted = ...,
    blocks_32: bool | _Omitted = ...,
    blocks_33: bool | _Omitted = ...,
    blocks_34: bool | _Omitted = ...,
    blocks_35: bool | _Omitted = ...,
    blocks_36: bool | _Omitted = ...,
    blocks_37: bool | _Omitted = ...,
    blocks_38: bool | _Omitted = ...,
    blocks_39: bool | _Omitted = ...,
    layer_filter: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lora: Literal['ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength: float | _Omitted = ...,
    prev_lora: Any | _Omitted = ...,
    blocks: Any | _Omitted = ...,
    low_mem_load: bool | _Omitted = ...,
    merge_loras: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoLoraSelectByName(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lora_name: str | _Omitted = ...,
    strength: float | _Omitted = ...,
    prev_lora: Any | _Omitted = ...,
    blocks: Any | _Omitted = ...,
    low_mem_load: bool | _Omitted = ...,
    merge_loras: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoLoraSelectMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    lora_0: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_0: float | _Omitted = ...,
    lora_1: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_1: float | _Omitted = ...,
    lora_2: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_2: float | _Omitted = ...,
    lora_3: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_3: float | _Omitted = ...,
    lora_4: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_4: float | _Omitted = ...,
    prev_lora: Any | _Omitted = ...,
    blocks: Any | _Omitted = ...,
    low_mem_load: bool | _Omitted = ...,
    merge_loras: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoMagCache(
    *args: VibeWorkflow,
    _id: str | None = ...,
    magcache_thresh: float | _Omitted = ...,
    magcache_K: int | _Omitted = ...,
    start_step: int | _Omitted = ...,
    end_step: int | _Omitted = ...,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoMiniMaxRemoverEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    latents: Any | _Omitted = ...,
    mask_latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = ...,
    base_precision: Literal['fp32', 'bf16', 'fp16', 'fp16_fast'] | _Omitted = ...,
    quantization: Literal['disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e4m3fn_scaled', 'fp8_e4m3fn_scaled_fast', 'fp8_e5m2', 'fp8_e5m2_fast', 'fp8_e5m2_scaled', 'fp8_e5m2_scaled_fast'] | _Omitted = ...,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    attention_mode: Literal['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn', 'sageattn_3', 'radial_sage_attention', 'sageattn_compiled', 'sageattn_ultravico', 'comfy'] | _Omitted = ...,
    compile_args: Any | _Omitted = ...,
    block_swap_args: Any | _Omitted = ...,
    lora: Any | _Omitted = ...,
    vram_management_args: Any | _Omitted = ...,
    extra_model: Any | _Omitted = ...,
    fantasytalking_model: Any | _Omitted = ...,
    multitalk_model: Any | _Omitted = ...,
    fantasyportrait_model: Any | _Omitted = ...,
    rms_norm_function: Literal['default', 'pytorch'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoOviCFG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    original_text_embeds: Any | _Omitted = ...,
    ovi_audio_cfg: float | _Omitted = ...,
    ovi_negative_text_embeds: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoPassImagesFromSamples(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoPhantomEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    num_frames: int | _Omitted = ...,
    phantom_latent_1: Any | _Omitted = ...,
    phantom_cfg_scale: float | _Omitted = ...,
    phantom_start_percent: float | _Omitted = ...,
    phantom_end_percent: float | _Omitted = ...,
    phantom_latent_2: Any | _Omitted = ...,
    phantom_latent_3: Any | _Omitted = ...,
    phantom_latent_4: Any | _Omitted = ...,
    vace_embeds: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoPreviewEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    embeds: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoPromptExtender(
    *args: VibeWorkflow,
    _id: str | None = ...,
    qwen: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    device: Literal['gpu', 'cpu'] | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    system_prompt: Literal['T2V Movie Director (Chinese)', 'T2V Movie Director (English)', 'I2V Rewriter (Chinese)', 'I2V Rewriter (English)', 'I2V Imagination (Chinese)', 'I2V Imagination (English)'] | _Omitted = ...,
    custom_system_prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoPromptExtenderSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    system_prompt: Literal['T2V Movie Director (Chinese)', 'T2V Movie Director (English)', 'I2V Rewriter (Chinese)', 'I2V Rewriter (English)', 'I2V Imagination (Chinese)', 'I2V Imagination (English)'] | _Omitted = ...,
    custom_system_prompt: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoReCamMasterCameraEmbed(
    *args: VibeWorkflow,
    _id: str | None = ...,
    camera_poses: Any | _Omitted = ...,
    latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoReCamMasterDefaultCamera(
    *args: VibeWorkflow,
    _id: str | None = ...,
    camera_type: Literal['pan_right', 'pan_left', 'tilt_up', 'tilt_down', 'zoom_in', 'zoom_out', 'translate_up', 'translate_down', 'arc_left', 'arc_right'] | _Omitted = ...,
    latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoReCamMasterGenerateOrbitCamera(
    *args: VibeWorkflow,
    _id: str | None = ...,
    num_frames: int | _Omitted = ...,
    degrees: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoRealisDanceLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ref_latent: Any | _Omitted = ...,
    pose_cond_start_percent: float | _Omitted = ...,
    pose_cond_end_percent: float | _Omitted = ...,
    smpl_latent: Any | _Omitted = ...,
    hamer_latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoRoPEFunction(
    *args: VibeWorkflow,
    _id: str | None = ...,
    rope_function: Literal['default', 'comfy', 'comfy_chunked'] | _Omitted = ...,
    ntk_scale_f: float | _Omitted = ...,
    ntk_scale_h: float | _Omitted = ...,
    ntk_scale_w: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSLG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    blocks: str | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSVIProEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    anchor_samples: Any | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    prev_samples: Any | _Omitted = ...,
    motion_latent_count: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    image_embeds: Any | _Omitted = ...,
    steps: int | _Omitted = ...,
    cfg: float | _Omitted = ...,
    shift: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    scheduler: Literal['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'] | _Omitted = ...,
    riflex_freq_index: int | _Omitted = ...,
    text_embeds: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    denoise_strength: float | _Omitted = ...,
    feta_args: Any | _Omitted = ...,
    context_options: Any | _Omitted = ...,
    cache_args: Any | _Omitted = ...,
    flowedit_args: Any | _Omitted = ...,
    batched_cfg: bool | _Omitted = ...,
    slg_args: Any | _Omitted = ...,
    rope_function: Literal['default', 'comfy', 'comfy_chunked'] | _Omitted = ...,
    loop_args: Any | _Omitted = ...,
    experimental_args: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    unianimate_poses: Any | _Omitted = ...,
    fantasytalking_embeds: Any | _Omitted = ...,
    uni3c_embeds: Any | _Omitted = ...,
    multitalk_embeds: Any | _Omitted = ...,
    freeinit_args: Any | _Omitted = ...,
    start_step: int | _Omitted = ...,
    end_step: int | _Omitted = ...,
    add_noise_to_samples: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSamplerExtraArgs(
    *args: VibeWorkflow,
    _id: str | None = ...,
    riflex_freq_index: int | _Omitted = ...,
    feta_args: Any | _Omitted = ...,
    context_options: Any | _Omitted = ...,
    cache_args: Any | _Omitted = ...,
    slg_args: Any | _Omitted = ...,
    rope_function: Literal['default', 'comfy', 'comfy_chunked'] | _Omitted = ...,
    loop_args: Any | _Omitted = ...,
    experimental_args: Any | _Omitted = ...,
    unianimate_poses: Any | _Omitted = ...,
    fantasytalking_embeds: Any | _Omitted = ...,
    uni3c_embeds: Any | _Omitted = ...,
    multitalk_embeds: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSamplerFromSettings(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sampler_inputs: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSamplerSettings(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    image_embeds: Any | _Omitted = ...,
    steps: int | _Omitted = ...,
    cfg: float | _Omitted = ...,
    shift: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    scheduler: Literal['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'] | _Omitted = ...,
    riflex_freq_index: int | _Omitted = ...,
    text_embeds: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    denoise_strength: float | _Omitted = ...,
    feta_args: Any | _Omitted = ...,
    context_options: Any | _Omitted = ...,
    cache_args: Any | _Omitted = ...,
    flowedit_args: Any | _Omitted = ...,
    batched_cfg: bool | _Omitted = ...,
    slg_args: Any | _Omitted = ...,
    rope_function: Literal['default', 'comfy', 'comfy_chunked'] | _Omitted = ...,
    loop_args: Any | _Omitted = ...,
    experimental_args: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    unianimate_poses: Any | _Omitted = ...,
    fantasytalking_embeds: Any | _Omitted = ...,
    uni3c_embeds: Any | _Omitted = ...,
    multitalk_embeds: Any | _Omitted = ...,
    freeinit_args: Any | _Omitted = ...,
    start_step: int | _Omitted = ...,
    end_step: int | _Omitted = ...,
    add_noise_to_samples: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSamplerv2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    image_embeds: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    scheduler: Any | _Omitted = ...,
    text_embeds: Any | _Omitted = ...,
    samples: Any | _Omitted = ...,
    add_noise_to_samples: bool | _Omitted = ...,
    extra_args: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    scheduler: Literal['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'] | _Omitted = ...,
    steps: int | _Omitted = ...,
    shift: float | _Omitted = ...,
    start_step: int | _Omitted = ...,
    end_step: int | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    enhance_hf: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSchedulerv2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    scheduler: Literal['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'] | _Omitted = ...,
    steps: int | _Omitted = ...,
    shift: float | _Omitted = ...,
    start_step: int | _Omitted = ...,
    end_step: int | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    enhance_hf: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSetAttentionModeOverride(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    attention_mode: Literal['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn', 'sageattn_3', 'radial_sage_attention', 'sageattn_compiled', 'sageattn_ultravico', 'comfy'] | _Omitted = ...,
    start_step: int | _Omitted = ...,
    end_step: int | _Omitted = ...,
    verbose: bool | _Omitted = ...,
    blocks: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSetBlockSwap(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    block_swap_args: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSetLoRAs(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    lora: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSetRadialAttention(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    dense_attention_mode: Literal['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn', 'sparse_sage_attention'] | _Omitted = ...,
    dense_blocks: int | _Omitted = ...,
    dense_vace_blocks: int | _Omitted = ...,
    dense_timesteps: int | _Omitted = ...,
    decay_factor: float | _Omitted = ...,
    block_size: Literal[128, 64] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoSigmaToStep(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigma: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoTeaCache(
    *args: VibeWorkflow,
    _id: str | None = ...,
    rel_l1_thresh: float | _Omitted = ...,
    start_step: int | _Omitted = ...,
    end_step: int | _Omitted = ...,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    use_coefficients: bool | _Omitted = ...,
    mode: Literal['e', 'e0'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoTextEmbedBridge(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoTextEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive_prompt: str | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    t5: Any | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    model_to_offload: Any | _Omitted = ...,
    use_disk_cache: bool | _Omitted = ...,
    device: Literal['gpu', 'cpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoTextEncodeCached(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = ...,
    precision: Literal['fp32', 'bf16'] | _Omitted = ...,
    positive_prompt: str | _Omitted = ...,
    negative_prompt: str | _Omitted = ...,
    quantization: Literal['disabled', 'fp8_e4m3fn'] | _Omitted = ...,
    use_disk_cache: bool | _Omitted = ...,
    device: Literal['gpu', 'cpu'] | _Omitted = ...,
    extender_args: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoTextEncodeSingle(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    t5: Any | _Omitted = ...,
    force_offload: bool | _Omitted = ...,
    model_to_offload: Any | _Omitted = ...,
    use_disk_cache: bool | _Omitted = ...,
    device: Literal['gpu', 'cpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoTinyVAELoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Any | _Omitted = ...,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = ...,
    parallel: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoTorchCompileSettings(
    *args: VibeWorkflow,
    _id: str | None = ...,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = ...,
    fullgraph: bool | _Omitted = ...,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = ...,
    dynamic: bool | _Omitted = ...,
    dynamo_cache_size_limit: int | _Omitted = ...,
    compile_transformer_blocks_only: bool | _Omitted = ...,
    dynamo_recompile_limit: int | _Omitted = ...,
    force_parameter_static_shapes: bool | _Omitted = ...,
    allow_unmerged_lora_compile: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoUltraVicoSettings(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    alpha: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoUni3C_ControlnetLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = ...,
    quantization: Literal['disabled', 'fp8_e4m3fn', 'fp8_e5m2'] | _Omitted = ...,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    attention_mode: Literal['sdpa', 'sageattn'] | _Omitted = ...,
    compile_args: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoUni3C_embeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    controlnet: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    render_latent: Any | _Omitted = ...,
    render_mask: Any | _Omitted = ...,
    offload: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoUniAnimateDWPoseDetector(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pose_images: Any | _Omitted = ...,
    score_threshold: float | _Omitted = ...,
    stick_width: int | _Omitted = ...,
    draw_body: bool | _Omitted = ...,
    body_keypoint_size: int | _Omitted = ...,
    draw_feet: bool | _Omitted = ...,
    draw_hands: bool | _Omitted = ...,
    hand_keypoint_size: int | _Omitted = ...,
    colorspace: Literal['RGB', 'BGR'] | _Omitted = ...,
    handle_not_detected: Literal['empty', 'repeat'] | _Omitted = ...,
    draw_head: bool | _Omitted = ...,
    reference_pose_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoUniAnimatePoseInput(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pose_images: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    start_percent: float | _Omitted = ...,
    end_percent: float | _Omitted = ...,
    reference_pose_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoUniLumosEmbeds(
    *args: VibeWorkflow,
    _id: str | None = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    foreground_latents: Any | _Omitted = ...,
    background_latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoVACEEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    vace_start_percent: float | _Omitted = ...,
    vace_end_percent: float | _Omitted = ...,
    input_frames: Any | _Omitted = ...,
    ref_images: Any | _Omitted = ...,
    input_masks: Any | _Omitted = ...,
    prev_vace_embeds: Any | _Omitted = ...,
    tiled_vae: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoVACEModelSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vace_model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoVACEStartToEndFrame(
    *args: VibeWorkflow,
    _id: str | None = ...,
    num_frames: int | _Omitted = ...,
    empty_frame_level: float | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    end_image: Any | _Omitted = ...,
    control_images: Any | _Omitted = ...,
    inpaint_mask: Any | _Omitted = ...,
    start_index: int | _Omitted = ...,
    end_index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoVAELoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = ...,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = ...,
    compile_args: Any | _Omitted = ...,
    use_cpu_cache: bool | _Omitted = ...,
    verbose: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoVRAMManagement(
    *args: VibeWorkflow,
    _id: str | None = ...,
    offload_percent: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanVideoWanDrawWanMoveTracks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    tracks: Any | _Omitted = ...,
    line_resolution: int | _Omitted = ...,
    circle_size: int | _Omitted = ...,
    opacity: float | _Omitted = ...,
    line_width: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Wav2VecModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = ...,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WhisperModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = ...,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
