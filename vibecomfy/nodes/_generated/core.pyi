"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def AudioConcat(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio1: Any | _Omitted = ...,
    audio2: Any | _Omitted = ...,
    direction: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioEncoderEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_encoder: Any | _Omitted = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AudioEncoderLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_encoder_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BasicScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    scheduler: Any | _Omitted = ...,
    steps: int | _Omitted = ...,
    denoise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CFGGuider(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    cfg: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CFGNorm(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_name: Literal['ViT-L-14-BEST-smooth-GmP-TE-only-HF-format.safetensors', 'ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors', 'byt5_small_glyphxl_fp16.safetensors', 'clip_g.safetensors', 'clip_g_hidream.safetensors', 'clip_l.safetensors', 'clip_l_hidream.safetensors', 'ernie-image-prompt-enhancer.safetensors', 'full_encoder_small_decoder.safetensors', 'gemma_2_2b_fp16.safetensors', 'gemma_3_12B_it.safetensors', 'gemma_3_12B_it_fp4_mixed.safetensors', 'gemma_3_12B_it_fp8_scaled.safetensors', 'gemma_3_4b_it_bf16.safetensors', 'jina_clip_v2_bf16.safetensors', 'llama_3.1_8b_instruct_fp8_scaled.safetensors', 'llava_llama3_fp16.safetensors', 'llava_llama3_fp8_scaled.safetensors', 'ltx-2-19b-embeddings_connector_distill_bf16.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'ministral-3-3b.safetensors', 'mistral_3_small_flux2_bf16.safetensors', 'mistral_3_small_flux2_fp8.safetensors', 'oldt5_xxl_fp16.safetensors', 'oldt5_xxl_fp8_e4m3fn_scaled.safetensors', 'ovis_2.5.safetensors', 'qwen3.5_4b_bf16.safetensors', 'qwen_0.6b_ace15.safetensors', 'qwen_1.7b_ace15.safetensors', 'qwen_2.5_vl_7b.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_fp16.safetensors', 'qwen_3_06b_base.safetensors', 'qwen_3_4b.safetensors', 'qwen_3_8b.safetensors', 'qwen_3_8b_fp8mixed.safetensors', 'qwen_4b_ace15.safetensors', 't5-base.safetensors', 't5_base.safetensors', 't5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'] | _Omitted = ...,
    type_: Literal['stable_diffusion', 'stable_cascade', 'sd3', 'stable_audio', 'mochi', 'ltxv', 'pixart', 'cosmos', 'lumina2', 'wan', 'hidream', 'chroma', 'ace', 'omnigen2', 'qwen_image', 'hunyuan_image', 'flux2', 'ovis', 'longcat_image'] | _Omitted = ...,
    device: Literal['default', 'cpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPTextEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    text: str | _Omitted = ...,
    clip: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPVisionEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_vision: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    crop: Literal['center', 'none'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CLIPVisionLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_name: Literal['CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors', 'clip_vision_g.safetensors', 'clip_vision_h.safetensors', 'llava_llama3_vision.safetensors', 'sigclip_vision_patch14_384.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CheckpointLoaderSimple(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Literal['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ComfyMathExpression(
    *args: VibeWorkflow,
    _id: str | None = ...,
    expression: str | _Omitted = ...,
    values: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ComfySwitchNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    switch: bool | _Omitted = ...,
    on_false: Any | _Omitted = ...,
    on_true: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ConditioningZeroOut(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CreateVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    fps: float | _Omitted = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DualCLIPLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_name1: Literal['ViT-L-14-BEST-smooth-GmP-TE-only-HF-format.safetensors', 'ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors', 'byt5_small_glyphxl_fp16.safetensors', 'clip_g.safetensors', 'clip_g_hidream.safetensors', 'clip_l.safetensors', 'clip_l_hidream.safetensors', 'ernie-image-prompt-enhancer.safetensors', 'flux1-dev-Q4_K_S.gguf', 'flux1-dev-Q8_0.gguf', 'flux1-schnell-Q4_K_S.gguf', 'flux1-schnell-Q8_0.gguf', 'full_encoder_small_decoder.safetensors', 'gemma_2_2b_fp16.safetensors', 'gemma_3_12B_it.safetensors', 'gemma_3_12B_it_fp4_mixed.safetensors', 'gemma_3_12B_it_fp8_scaled.safetensors', 'gemma_3_4b_it_bf16.safetensors', 'jina_clip_v2_bf16.safetensors', 'llama_3.1_8b_instruct_fp8_scaled.safetensors', 'llava_llama3_fp16.safetensors', 'llava_llama3_fp8_scaled.safetensors', 'ltx-2-19b-embeddings_connector_distill_bf16.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'ministral-3-3b.safetensors', 'mistral_3_small_flux2_bf16.safetensors', 'mistral_3_small_flux2_fp8.safetensors', 'oldt5_xxl_fp16.safetensors', 'oldt5_xxl_fp8_e4m3fn_scaled.safetensors', 'ovis_2.5.safetensors', 'qwen3.5_4b_bf16.safetensors', 'qwen_0.6b_ace15.safetensors', 'qwen_1.7b_ace15.safetensors', 'qwen_2.5_vl_7b.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_fp16.safetensors', 'qwen_3_06b_base.safetensors', 'qwen_3_4b.safetensors', 'qwen_3_8b.safetensors', 'qwen_3_8b_fp8mixed.safetensors', 'qwen_4b_ace15.safetensors', 't5-base.safetensors', 't5-v1_1-xxl-encoder-Q4_K_M.gguf', 't5-v1_1-xxl-encoder-Q8_0.gguf', 't5_base.safetensors', 't5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'] | _Omitted = ...,
    clip_name2: Literal['ViT-L-14-BEST-smooth-GmP-TE-only-HF-format.safetensors', 'ViT-L-14-TEXT-detail-improved-hiT-GmP-TE-only-HF.safetensors', 'byt5_small_glyphxl_fp16.safetensors', 'clip_g.safetensors', 'clip_g_hidream.safetensors', 'clip_l.safetensors', 'clip_l_hidream.safetensors', 'ernie-image-prompt-enhancer.safetensors', 'flux1-dev-Q4_K_S.gguf', 'flux1-dev-Q8_0.gguf', 'flux1-schnell-Q4_K_S.gguf', 'flux1-schnell-Q8_0.gguf', 'full_encoder_small_decoder.safetensors', 'gemma_2_2b_fp16.safetensors', 'gemma_3_12B_it.safetensors', 'gemma_3_12B_it_fp4_mixed.safetensors', 'gemma_3_12B_it_fp8_scaled.safetensors', 'gemma_3_4b_it_bf16.safetensors', 'jina_clip_v2_bf16.safetensors', 'llama_3.1_8b_instruct_fp8_scaled.safetensors', 'llava_llama3_fp16.safetensors', 'llava_llama3_fp8_scaled.safetensors', 'ltx-2-19b-embeddings_connector_distill_bf16.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'ministral-3-3b.safetensors', 'mistral_3_small_flux2_bf16.safetensors', 'mistral_3_small_flux2_fp8.safetensors', 'oldt5_xxl_fp16.safetensors', 'oldt5_xxl_fp8_e4m3fn_scaled.safetensors', 'ovis_2.5.safetensors', 'qwen3.5_4b_bf16.safetensors', 'qwen_0.6b_ace15.safetensors', 'qwen_1.7b_ace15.safetensors', 'qwen_2.5_vl_7b.safetensors', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_fp16.safetensors', 'qwen_3_06b_base.safetensors', 'qwen_3_4b.safetensors', 'qwen_3_8b.safetensors', 'qwen_3_8b_fp8mixed.safetensors', 'qwen_4b_ace15.safetensors', 't5-base.safetensors', 't5-v1_1-xxl-encoder-Q4_K_M.gguf', 't5-v1_1-xxl-encoder-Q8_0.gguf', 't5_base.safetensors', 't5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors', 't5xxl_fp8_e4m3fn_scaled.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'] | _Omitted = ...,
    type_: Literal['sdxl', 'sd3', 'flux', 'hunyuan_video', 'hidream', 'hunyuan_image', 'hunyuan_video_15', 'kandinsky5', 'kandinsky5_image', 'ltxv', 'newbie', 'ace'] | _Omitted = ...,
    device: Literal['default', 'cpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyAceStep1_5LatentAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    seconds: float | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    duration: float | _Omitted = ...,
    sample_rate: int | _Omitted = ...,
    channels: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyFlux2LatentImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyHunyuanLatentVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    color: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptyLTXVLatentVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def EmptySD3LatentImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Flux2Scheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    steps: int | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetImageRangeFromBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    start_index: int | _Omitted = ...,
    num_frames: int | _Omitted = ...,
    images: Any | _Omitted = ...,
    masks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetImageSize(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetVideoComponents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GrowMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    expand: int | _Omitted = ...,
    tapered_corners: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBlend(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image1: Any | _Omitted = ...,
    image2: Any | _Omitted = ...,
    blend_factor: float | _Omitted = ...,
    blend_mode: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBlur(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    blur_radius: int | _Omitted = ...,
    sigma: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageFromBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    batch_index: int | _Omitted = ...,
    length: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageScale(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    crop: Literal['disabled', 'center'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageScaleBy(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    scale_by: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageScaleToTotalPixels(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    upscale_method: Any | _Omitted = ...,
    megapixels: float | _Omitted = ...,
    resolution_steps: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    cfg: float | _Omitted = ...,
    sampler_name: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = ...,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    latent_image: Any | _Omitted = ...,
    denoise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KSamplerSelect(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sampler_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXAVTextEncoderLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    text_encoder: Any | _Omitted = ...,
    ckpt_name: Any | _Omitted = ...,
    device: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddGuide(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    frame_idx: int | _Omitted = ...,
    strength: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAddGuideMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    num_guides: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAudioVAEDecode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    audio_vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAudioVAEEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    audio_vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAudioVAELoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ckpt_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVConcatAVLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video_latent: Any | _Omitted = ...,
    audio_latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVConditioning(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    frame_rate: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVCropGuides(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVEmptyLatentAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    frames_number: int | _Omitted = ...,
    frame_rate: int | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    audio_vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVImgToVideoInplace(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    strength: float | _Omitted = ...,
    bypass: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVLatentUpsampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    upscale_model: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVPreprocess(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    img_compression: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVScheduler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    steps: int | _Omitted = ...,
    max_shift: float | _Omitted = ...,
    base_shift: float | _Omitted = ...,
    stretch: bool | _Omitted = ...,
    terminal: float | _Omitted = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVSeparateAVLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    av_latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LatentUpscaleModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model_name: Literal['hunyuanvideo15_latent_upsampler_1080p.safetensors', 'ltx-2-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x1.5-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'ltx-2.3-temporal-upscaler-x2-1.0.safetensors'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    file: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoraLoaderModelOnly(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    lora_name: Literal['Flux2TurboComfyv2.safetensors', 'Flux_2-Turbo-LoRA_comfyui.safetensors', 'GoodHands-beta2.safetensors', 'Hyper-SD15-12steps-CFG-lora.safetensors', 'Hyper-SDXL-12steps-CFG-lora.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'PixelArtRedmond15V-PixelArt-PIXARFK.safetensors', 'Qwen-Edit-2509-Multiple-angles.safetensors', 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', 'Qwen-Image-Edit-2509-Anything2RealAlpha.safetensors', 'Qwen-Image-Edit-2509-Fusion.safetensors', 'Qwen-Image-Edit-2509-Light-Migration.safetensors', 'Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-2509-Relight.safetensors', 'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors', 'Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors', 'Qwen-Image-Edit-Lightning-8steps-V1.0.safetensors', 'Qwen-Image-Lightning-4steps-V2.0.safetensors', 'Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors', 'Qwen-Image-Lightning-8steps-V2.0.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'Wuli-Qwen-Image-2512-Turbo-LoRA-2steps-V1.0-bf16.safetensors', 'blur_control_xl_v1.safetensors', 'chronoedit_distill_lora.safetensors', 'flux1-canny-dev-lora.safetensors', 'flux1-depth-dev-lora.safetensors', 'gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors', 'gummycandy_qwen.safetensors', 'illustration-1.0-qwen-image.safetensors', 'ip-adapter-faceid-plus_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sd15_lora.safetensors', 'ip-adapter-faceid-plusv2_sdxl_lora.safetensors', 'ip-adapter-faceid_sd15_lora.safetensors', 'ip-adapter-faceid_sdxl_lora.safetensors', 'lcm_lora_sdxl.safetensors', 'lightx2v_14B_T2V_cfg_step_distill_lora_adaptive_rank_quantile_0.15_bf16.safetensors', 'ltx-2-19b-distilled-lora-384.safetensors', 'ltx-2-19b-ic-lora-canny-control.safetensors', 'ltx-2-19b-ic-lora-depth-control.safetensors', 'ltx-2-19b-ic-lora-pose-control.safetensors', 'ltx-2-19b-lora-camera-control-dolly-left.safetensors', 'ltx-2.3-22b-distilled-lora-384.safetensors', 'ltx-2.3-id-lora-talkvid-3k.safetensors', 'ltx2-squish.safetensors', 'ltx2.3-transition.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'openxl_handsfix.safetensors', 'qwen-image-edit-2511-multiple-angles-lora.safetensors', 'qwen_image_union_diffsynth_lora.safetensors', 'uso-flux1-dit-lora-v1.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors', 'wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors', 'wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors', 'wan_alpha_2.1_rgba_lora.safetensors'] | _Omitted = ...,
    strength_model: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ManualSigmas(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sigmas: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MaskPreview(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MaskToImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingAuraFlow(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    shift: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ModelSamplingSD3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    shift: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PixelPerfectResolution(
    *args: VibeWorkflow,
    _id: str | None = ...,
    original_image: Any | _Omitted = ...,
    image_gen_width: int | _Omitted = ...,
    image_gen_height: int | _Omitted = ...,
    resize_mode: Literal['Just Resize', 'Crop and Resize', 'Resize and Fill'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewAny(
    *args: VibeWorkflow,
    _id: str | None = ...,
    source: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PrimitiveStringMultiline(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RandomNoise(
    *args: VibeWorkflow,
    _id: str | None = ...,
    noise_seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ReferenceLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    conditioning: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def RepeatImageBatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    amount: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ResizeImageMaskNode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input: Any | _Omitted = ...,
    resize_type: Any | _Omitted = ...,
    scale_method: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ResizeImagesByLongerEdge(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    longer_edge: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerCustomAdvanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    noise: Any | _Omitted = ...,
    guider: Any | _Omitted = ...,
    sampler: Any | _Omitted = ...,
    sigmas: Any | _Omitted = ...,
    latent_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SamplerEulerAncestral(
    *args: VibeWorkflow,
    _id: str | None = ...,
    eta: float | _Omitted = ...,
    s_noise: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveAudioMP3(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    quality: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SaveVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    format: Any | _Omitted = ...,
    codec: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SetLatentNoiseMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SimpleMath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: str | _Omitted = ...,
    a: Any | _Omitted = ...,
    b: Any | _Omitted = ...,
    c: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SolidMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: float | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def StringConcatenate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    string_a: str | _Omitted = ...,
    string_b: str | _Omitted = ...,
    delimiter: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextEncodeAceStepAudio1_5(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    tags: str | _Omitted = ...,
    lyrics: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    bpm: int | _Omitted = ...,
    duration: float | _Omitted = ...,
    timesignature: Any | _Omitted = ...,
    language: Any | _Omitted = ...,
    keyscale: Any | _Omitted = ...,
    generate_audio_codes: bool | _Omitted = ...,
    cfg_scale: float | _Omitted = ...,
    temperature: float | _Omitted = ...,
    top_p: float | _Omitted = ...,
    top_k: int | _Omitted = ...,
    min_p: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextEncodeQwenImageEdit(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    vae: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TextGenerateLTX2Prompt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip: Any | _Omitted = ...,
    prompt: str | _Omitted = ...,
    max_length: int | _Omitted = ...,
    sampling_mode: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    thinking: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TrimAudioDuration(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    start_index: float | _Omitted = ...,
    duration: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def TrimVideoLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    trim_amount: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UNETLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    unet_name: Any | _Omitted = ...,
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e5m2', 'fp8_e4m3fn_fast'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecodeAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEDecodeTiled(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    tile_size: int | _Omitted = ...,
    overlap: int | _Omitted = ...,
    temporal_size: int | _Omitted = ...,
    temporal_overlap: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAEEncode(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pixels: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAELoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae_name: Literal['LTX23_video_vae_bf16.safetensors', 'Wan2_1_VAE_bf16.safetensors', 'Wan2_2_VAE_bf16.safetensors', 'ace_1.5_vae.safetensors', 'ae.safetensors', 'cosmos_cv8x8x8_1.0.safetensors', 'flux2-vae.safetensors', 'hunyuan_image_2.1_vae_fp16.safetensors', 'hunyuan_image_refiner_vae_fp16.safetensors', 'hunyuan_video_vae_bf16.safetensors', 'hunyuanvideo15_vae_fp16.safetensors', 'lumina_image_2.0-ae.safetensors', 'mochi_vae.safetensors', 'qwen_image_layered_vae.safetensors', 'qwen_image_vae.safetensors', 'sdxl_vae.safetensors', 'taeltx2_3.safetensors', 'vae-ft-mse-840000-ema-pruned.safetensors', 'wan2.2_vae.safetensors', 'wan_2.1_vae.safetensors', 'wan_alpha_2.1_vae_alpha_channel.safetensors', 'wan_alpha_2.1_vae_rgb_channel.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors', 'z_image_turbo_vae.safetensors', 'pixel_space'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanAnimateToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    continue_motion_max_frames: int | _Omitted = ...,
    video_frame_offset: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    reference_image: Any | _Omitted = ...,
    face_video: Any | _Omitted = ...,
    pose_video: Any | _Omitted = ...,
    background_video: Any | _Omitted = ...,
    character_mask: Any | _Omitted = ...,
    continue_motion: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WanImageToVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    length: int | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    clip_vision_output: Any | _Omitted = ...,
    start_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
