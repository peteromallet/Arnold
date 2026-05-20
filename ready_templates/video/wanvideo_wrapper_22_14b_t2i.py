# vibecomfy: manual
"""Wan 2.2 14B single-frame T2I template for Reigh parity.

Output: unknown.

Source:  ComfyUI-WanVideoWrapper/example_workflows/wanvideo_2_2_14B_Pusa_extension_example_01.json

Packs:   ComfyUI-WanVideoWrapper
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

DEFAULT_PROMPT = "A compact cinematic still of a red cube on a clean white tabletop."
DEFAULT_NEGATIVE = "fading, breaking, shot cuts, jumpcuts, blurry, noise, distorted"
MODELS = {
    "wan2_2_t2v_a14b_high": ModelAsset(
        filename="Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
        url="https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
        subdir="diffusion_models/WanVideo/2_2",
        sha256='15384a1da9b5aa463464ba50a596b84f6c0929bfb72ec47df6bb48cb2e0b6f0c',
        hf_revision='5571ff9d81a631ee97946a703e94911d63214c44',
        size_bytes=15001361458,
    ),
    "wan2_2_t2v_a14b_low": ModelAsset(
        filename="Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
        url="https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
        subdir="diffusion_models/WanVideo/2_2",
        sha256='ce74fff05e37f995a0ae845f53510e43f98b838f4e75d846eb3e2929e7f555cc',
        hf_revision='5571ff9d81a631ee97946a703e94911d63214c44',
        size_bytes=15001361458,
    ),
    "wan_lightx2v_lora": ModelAsset(
        filename="lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors",
        url="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors",
        subdir="loras/WanVideo/Lightx2v",
        sha256='37d49218544b9e0bfb8e831d1399f451fbc5068aff6474f42a90c928363c3573',
        hf_revision='87badb1f794c15daf51db60838a433ca08bb218f',
        size_bytes=630697104,
    ),
    "wan_vae": ModelAsset(
        filename="Wan2_1_VAE_bf16.safetensors",
        url="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors",
        subdir="vae",
        sha256='1ab9a32cc2c740f6e39d80d367ce5dcc28db8c71b79b28670546b8973e9d75f9',
        hf_revision='87badb1f794c15daf51db60838a433ca08bb218f',
        size_bytes=253806278,
    ),
    "wan_text_encoder": ModelAsset(
        filename="umt5-xxl-enc-bf16.safetensors",
        url="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors",
        subdir="text_encoders",
        sha256='4fa971faf306cad919033d5bbe192e571dc08452f800cbf2ec3c73977c01b2cc',
        hf_revision='87badb1f794c15daf51db60838a433ca08bb218f',
        size_bytes=11361845464,
    ),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_22_14b_t2i',
    capability='text_to_image_single_frame',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-WanVideoWrapper']},
    provenance={'approach': 'Wan 2.2 14B high/low two-phase text-to-video graph decoded as one image frame', 'smoke_resolution': '832x480x1_frame', 'source_role': 'reigh_parity_manual_template', 'source_workflow': 'ComfyUI-WanVideoWrapper/example_workflows/wanvideo_2_2_14B_Pusa_extension_example_01.json'},
    coverage_tier='production_parity_candidate',
    runtime_note='Intended to match Reigh wan_2_2_t2i, which forces video_length=1 and returns PNG.',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ LOADERS ════
    vae = node(wf, "WanVideoVAELoader", "38", model_name="wanvideo\\Wan2_1_VAE_bf16.safetensors", precision="bf16")
    # ════ SAMPLING ════
    block_swap = node(wf, "WanVideoBlockSwap", "39", blocks_to_swap=30, offload_img_emb=False, offload_txt_emb=False, use_non_blocking=False, vace_blocks_to_swap=0, prefetch_blocks=0, block_swap_debug=False)
    high_lora = node(wf, "WanVideoLoraSelectMulti", "98", widget_0="WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", lora_0="WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", strength_0=1.0, lora_1="none", strength_1=1, lora_2="none", strength_2=1, lora_3="none", strength_3=1, lora_4="none", strength_4=1, low_mem_load=False, merge_loras=False)
    low_lora = node(wf, "WanVideoLoraSelectMulti", "93", widget_0="WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", lora_0="WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", strength_0=1.0, lora_1="none", strength_1=1, lora_2="none", strength_2=1, lora_3="none", strength_3=1, lora_4="none", strength_4=1, low_mem_load=False, merge_loras=False)
    high_model_raw = node(wf, "WanVideoModelLoader", "22", model="WanVideo\\2_2\\Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors", widget_1="fp16", base_precision="fp16", quantization="fp8_e4m3fn_scaled", load_device="offload_device", attention_mode="sdpa")
    low_model_raw = node(wf, "WanVideoModelLoader", "92", model="WanVideo\\2_2\\Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", widget_1="fp16", base_precision="fp16", quantization="fp8_e4m3fn_scaled", load_device="offload_device", attention_mode="sdpa")
    high_model_lora = node(wf, "WanVideoSetLoRAs", "79", model=high_model_raw.out(0), lora=high_lora.out(0))
    low_model_lora = node(wf, "WanVideoSetLoRAs", "80", model=low_model_raw.out(0), lora=low_lora.out(0))
    high_model = node(wf, "WanVideoSetBlockSwap", "86", model=high_model_lora.out(0), block_swap_args=block_swap.out(0))
    low_model = node(wf, "WanVideoSetBlockSwap", "91", model=low_model_lora.out(0), block_swap_args=block_swap.out(0))
    embeds = node(wf, "WanVideoEmptyEmbeds", "78", widget_0=832, widget_1=480, widget_2=1, width=832, height=480, num_frames=1)
    # ════ TEXT CONDITIONING ════
    text = node(wf, "WanVideoTextEncodeCached", "16", model_name=MODELS["wan_text_encoder"].filename, precision="bf16", positive_prompt=DEFAULT_PROMPT, negative_prompt=DEFAULT_NEGATIVE, quantization="disabled", use_disk_cache=True, device="gpu")
    high_samples = node(wf, "WanVideoSampler", "27", steps=6,  cfg=3.0, shift=5, seed=12345,force_offload=True, scheduler="euler", riflex_freq_index=0, denoise_strength=1, batched_cfg="", rope_function="comfy", start_step=0,  add_noise_to_samples=False, model=high_model.out(0), image_embeds=embeds.out(0), text_embeds=text.out(0), end_step=2)
    low_samples = node(wf, "WanVideoSampler", "87", steps=6,  cfg=1.0, shift=5, seed=12345,force_offload=True, scheduler="euler", riflex_freq_index=0, denoise_strength=1, batched_cfg="", rope_function="comfy",  end_step=-1, add_noise_to_samples=False, model=low_model.out(0), image_embeds=embeds.out(0), text_embeds=text.out(0), samples=high_samples.out(0), start_step=2)
    # ════ DECODE ════
    decoded = node(wf, "WanVideoDecode", "28", enable_vae_tiling=False, tile_x=272, tile_y=272, tile_stride_x=144, tile_stride_y=128, normalization="default", samples=low_samples.out(0), vae=vae.out(0))
    node(wf, "SaveImage", "60", filename_prefix="Wan-2-2-T2I", images=decoded.out(0))

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )
