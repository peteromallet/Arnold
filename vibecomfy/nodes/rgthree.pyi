# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def Any_Switch_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    base_ctx: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    clip: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    base_ctx: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    clip: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    positive: Any | _Omitted = ...,
    negative: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    steps: int | _Omitted = ...,
    step_refiner: int | _Omitted = ...,
    cfg: float | _Omitted = ...,
    ckpt_name: Any | _Omitted = ...,
    sampler: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = ...,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = ...,
    clip_width: int | _Omitted = ...,
    clip_height: int | _Omitted = ...,
    text_pos_g: str | _Omitted = ...,
    text_pos_l: str | _Omitted = ...,
    text_neg_g: str | _Omitted = ...,
    text_neg_l: str | _Omitted = ...,
    mask: Any | _Omitted = ...,
    control_net: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Merge_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Merge_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Switch_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Context_Switch_Big_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Display_Any_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    source: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Display_Int_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    input: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Image_Comparer_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_a: Any | _Omitted = ...,
    image_b: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Image_Inset_Crop_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    measurement: Literal['Pixels', 'Percentage'] | _Omitted = ...,
    left: int | _Omitted = ...,
    right: int | _Omitted = ...,
    top: int | _Omitted = ...,
    bottom: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Image_Resize_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    measurement: Literal['pixels', 'percentage'] | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    fit: Literal['crop', 'pad', 'contain'] | _Omitted = ...,
    method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Image_or_Latent_Size_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def KSampler_Config_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    steps_total: int | _Omitted = ...,
    refiner_step: int | _Omitted = ...,
    cfg: float | _Omitted = ...,
    sampler_name: Literal['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2'] | _Omitted = ...,
    scheduler: Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Lora_Loader_Stack_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    clip: Any | _Omitted = ...,
    lora_01: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_01: float | _Omitted = ...,
    lora_02: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_02: float | _Omitted = ...,
    lora_03: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_03: float | _Omitted = ...,
    lora_04: Literal['None', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = ...,
    strength_04: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Lora_Loader_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    clip: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Primitive_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Prompt_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    opt_model: Any | _Omitted = ...,
    opt_clip: Any | _Omitted = ...,
    insert_lora: Literal['CHOOSE', 'DISABLE LORAS', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16'] | _Omitted = ...,
    insert_embedding: Literal['CHOOSE'] | _Omitted = ...,
    insert_saved: Literal['CHOOSE'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Prompt_Simple_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: str | _Omitted = ...,
    opt_clip: Any | _Omitted = ...,
    insert_embedding: Literal['CHOOSE'] | _Omitted = ...,
    insert_saved: Literal['CHOOSE'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Power_Puter_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDXL_Empty_Latent_Image_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    dimensions: Literal['1536 x 640   (landscape)', '1344 x 768   (landscape)', '1216 x 832   (landscape)', '1152 x 896   (landscape)', '1024 x 1024  (square)', ' 896 x 1152  (portrait)', ' 832 x 1216  (portrait)', ' 768 x 1344  (portrait)', ' 640 x 1536  (portrait)'] | _Omitted = ...,
    clip_scale: float | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDXL_Power_Prompt_Positive_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt_g: str | _Omitted = ...,
    prompt_l: str | _Omitted = ...,
    opt_model: Any | _Omitted = ...,
    opt_clip: Any | _Omitted = ...,
    opt_clip_width: int | _Omitted = ...,
    opt_clip_height: int | _Omitted = ...,
    insert_lora: Literal['CHOOSE', 'DISABLE LORAS', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16'] | _Omitted = ...,
    insert_embedding: Literal['CHOOSE'] | _Omitted = ...,
    insert_saved: Literal['CHOOSE'] | _Omitted = ...,
    target_width: int | _Omitted = ...,
    target_height: int | _Omitted = ...,
    crop_width: int | _Omitted = ...,
    crop_height: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SDXL_Power_Prompt_Simple_Negative_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt_g: str | _Omitted = ...,
    prompt_l: str | _Omitted = ...,
    opt_clip: Any | _Omitted = ...,
    opt_clip_width: int | _Omitted = ...,
    opt_clip_height: int | _Omitted = ...,
    insert_embedding: Literal['CHOOSE'] | _Omitted = ...,
    insert_saved: Literal['CHOOSE'] | _Omitted = ...,
    target_width: int | _Omitted = ...,
    target_height: int | _Omitted = ...,
    crop_width: int | _Omitted = ...,
    crop_height: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Seed_rgthree(
    *args: VibeWorkflow,
    _id: str | None = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
