# vibecomfy:generated
# pack: rgthree-comfy
# source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
# source_sha256: b18562bcb7dd82cfc56d64b6c2b1c334f073fcb4c239e3569fdd3f94faae7c79
# generator_version: 1.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 24
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers rgthree-comfy

"""Auto-generated typed wrappers for the rgthree-comfy custom-node pack.

Each class in this module wraps one ComfyUI node class. The wrappers
are thin builders around ``VibeWorkflow.node()`` — calling
``ClassName.add(wf, ...)`` is equivalent to ``wf.node('ClassType', ...)``
but gives editors type-checked kwargs and a place to attach docstrings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from vibecomfy.handles import Handle  # noqa: F401
    from vibecomfy.workflow import VibeWorkflow, _NodeBuilder  # noqa: F401


class Any_Switch_rgthree:
    """Typed wrapper for the ComfyUI node class ``Any Switch (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Any Switch (rgthree)'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
    ) -> "_NodeBuilder":
        """Add a ``Any Switch (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node('Any Switch (rgthree)')

class Context_rgthree:
    """Typed wrapper for the ComfyUI node class ``Context (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Context (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONTEXT', 'MODEL', 'CLIP', 'VAE', 'POSITIVE', 'NEGATIVE', 'LATENT', 'IMAGE', 'SEED')
    OUTPUT_TYPES: tuple[str, ...] = ('RGTHREE_CONTEXT', 'MODEL', 'CLIP', 'VAE', 'CONDITIONING', 'CONDITIONING', 'LATENT', 'IMAGE', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        base_ctx: "Handle" = None,
        clip: "Handle" = None,
        images: "Handle" = None,
        latent: "Handle" = None,
        model: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        seed: int = 0,
        vae: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``Context (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Context (rgthree)',
            base_ctx=base_ctx,
            clip=clip,
            images=images,
            latent=latent,
            model=model,
            negative=negative,
            positive=positive,
            seed=seed,
            vae=vae,
        )

class Context_Big_rgthree:
    """Typed wrapper for the ComfyUI node class ``Context Big (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Context Big (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONTEXT', 'MODEL', 'CLIP', 'VAE', 'POSITIVE', 'NEGATIVE', 'LATENT', 'IMAGE', 'SEED', 'STEPS', 'STEP_REFINER', 'CFG', 'CKPT_NAME', 'SAMPLER', 'SCHEDULER', 'CLIP_WIDTH', 'CLIP_HEIGHT', 'TEXT_POS_G', 'TEXT_POS_L', 'TEXT_NEG_G', 'TEXT_NEG_L', 'MASK', 'CONTROL_NET')
    OUTPUT_TYPES: tuple[str, ...] = ('RGTHREE_CONTEXT', 'MODEL', 'CLIP', 'VAE', 'CONDITIONING', 'CONDITIONING', 'LATENT', 'IMAGE', 'INT', 'INT', 'INT', 'FLOAT', "['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'illuminatiDiffusionV1_v11-unclip-h.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd21-unclip-h.ckpt', 'sd21-unclip-l.ckpt', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'stable_zero123.ckpt', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors', 'wd-1-5-beta2-aesthetic-unclip-h.safetensors']", "['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2']", "['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal']", 'INT', 'INT', 'STRING', 'STRING', 'STRING', 'STRING', 'MASK', 'CONTROL_NET')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        base_ctx: "Handle" = None,
        cfg: float = 0.0,
        ckpt_name: str = "",
        clip: "Handle" = None,
        clip_height: int = 0,
        clip_width: int = 0,
        control_net: "Handle" = None,
        images: "Handle" = None,
        latent: "Handle" = None,
        mask: "Handle" = None,
        model: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        sampler: str = "",
        scheduler: str = "",
        seed: int = 0,
        step_refiner: int = 0,
        steps: int = 0,
        text_neg_g: str = "",
        text_neg_l: str = "",
        text_pos_g: str = "",
        text_pos_l: str = "",
        vae: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``Context Big (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Context Big (rgthree)',
            base_ctx=base_ctx,
            cfg=cfg,
            ckpt_name=ckpt_name,
            clip=clip,
            clip_height=clip_height,
            clip_width=clip_width,
            control_net=control_net,
            images=images,
            latent=latent,
            mask=mask,
            model=model,
            negative=negative,
            positive=positive,
            sampler=sampler,
            scheduler=scheduler,
            seed=seed,
            step_refiner=step_refiner,
            steps=steps,
            text_neg_g=text_neg_g,
            text_neg_l=text_neg_l,
            text_pos_g=text_pos_g,
            text_pos_l=text_pos_l,
            vae=vae,
        )

class Context_Merge_rgthree:
    """Typed wrapper for the ComfyUI node class ``Context Merge (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Context Merge (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONTEXT', 'MODEL', 'CLIP', 'VAE', 'POSITIVE', 'NEGATIVE', 'LATENT', 'IMAGE', 'SEED')
    OUTPUT_TYPES: tuple[str, ...] = ('RGTHREE_CONTEXT', 'MODEL', 'CLIP', 'VAE', 'CONDITIONING', 'CONDITIONING', 'LATENT', 'IMAGE', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
    ) -> "_NodeBuilder":
        """Add a ``Context Merge (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node('Context Merge (rgthree)')

class Context_Merge_Big_rgthree:
    """Typed wrapper for the ComfyUI node class ``Context Merge Big (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Context Merge Big (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONTEXT', 'MODEL', 'CLIP', 'VAE', 'POSITIVE', 'NEGATIVE', 'LATENT', 'IMAGE', 'SEED', 'STEPS', 'STEP_REFINER', 'CFG', 'CKPT_NAME', 'SAMPLER', 'SCHEDULER', 'CLIP_WIDTH', 'CLIP_HEIGHT', 'TEXT_POS_G', 'TEXT_POS_L', 'TEXT_NEG_G', 'TEXT_NEG_L', 'MASK', 'CONTROL_NET')
    OUTPUT_TYPES: tuple[str, ...] = ('RGTHREE_CONTEXT', 'MODEL', 'CLIP', 'VAE', 'CONDITIONING', 'CONDITIONING', 'LATENT', 'IMAGE', 'INT', 'INT', 'INT', 'FLOAT', "['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'illuminatiDiffusionV1_v11-unclip-h.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd21-unclip-h.ckpt', 'sd21-unclip-l.ckpt', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'stable_zero123.ckpt', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors', 'wd-1-5-beta2-aesthetic-unclip-h.safetensors']", "['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2']", "['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal']", 'INT', 'INT', 'STRING', 'STRING', 'STRING', 'STRING', 'MASK', 'CONTROL_NET')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
    ) -> "_NodeBuilder":
        """Add a ``Context Merge Big (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node('Context Merge Big (rgthree)')

class Context_Switch_rgthree:
    """Typed wrapper for the ComfyUI node class ``Context Switch (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Context Switch (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONTEXT', 'MODEL', 'CLIP', 'VAE', 'POSITIVE', 'NEGATIVE', 'LATENT', 'IMAGE', 'SEED')
    OUTPUT_TYPES: tuple[str, ...] = ('RGTHREE_CONTEXT', 'MODEL', 'CLIP', 'VAE', 'CONDITIONING', 'CONDITIONING', 'LATENT', 'IMAGE', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
    ) -> "_NodeBuilder":
        """Add a ``Context Switch (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node('Context Switch (rgthree)')

class Context_Switch_Big_rgthree:
    """Typed wrapper for the ComfyUI node class ``Context Switch Big (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Context Switch Big (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONTEXT', 'MODEL', 'CLIP', 'VAE', 'POSITIVE', 'NEGATIVE', 'LATENT', 'IMAGE', 'SEED', 'STEPS', 'STEP_REFINER', 'CFG', 'CKPT_NAME', 'SAMPLER', 'SCHEDULER', 'CLIP_WIDTH', 'CLIP_HEIGHT', 'TEXT_POS_G', 'TEXT_POS_L', 'TEXT_NEG_G', 'TEXT_NEG_L', 'MASK', 'CONTROL_NET')
    OUTPUT_TYPES: tuple[str, ...] = ('RGTHREE_CONTEXT', 'MODEL', 'CLIP', 'VAE', 'CONDITIONING', 'CONDITIONING', 'LATENT', 'IMAGE', 'INT', 'INT', 'INT', 'FLOAT', "['AOM2-Hard.safetensors', 'AOM3A3.safetensors', 'Chroma1-Base.safetensors', 'LTX23_audio_vae_bf16.safetensors', 'Realistic_Vision_V5.1_fp16-no-ema.safetensors', 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', 'ace_step_1.5_turbo_aio.safetensors', 'ace_step_v1_3.5b.safetensors', 'albedobaseXL_v21.safetensors', 'anyloraCheckpoint_bakedvaeBlessedFp16.safetensors', 'aura_flow_0.1.safetensors', 'aura_flow_0.2.safetensors', 'cosxl.safetensors', 'cosxl_edit.safetensors', 'counterfeitV30_v30.safetensors', 'dreamshaperXL_v21TurboDPMSDE.safetensors', 'dreamshaper_8.safetensors', 'fantexiRealistic_v10.safetensors', 'flux1-dev-bnb-nf4-v2.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux1-dev-fp8.safetensors', 'flux1-schnell-bnb-nf4.safetensors', 'flux1-schnell-fp8.safetensors', 'hunyuan_dit_1.0.safetensors', 'hunyuan_dit_1.1.safetensors', 'hunyuan_dit_1.2.safetensors', 'illuminatiDiffusionV1_v11-unclip-h.safetensors', 'juggernautXL_v9Rundiffusionphoto2.safetensors', 'ltx-2-19b-dev-fp8.safetensors', 'ltx-2-19b-dev.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-distilled.safetensors', 'ltx-video-2b-v0.9.1.safetensors', 'ltx-video-2b-v0.9.5.safetensors', 'ltx-video-2b-v0.9.safetensors', 'lumina_2.safetensors', 'mochi_preview_fp8_scaled.safetensors', 'noosphere_v42.safetensors', 'picxReal_10.safetensors', 'realvisxlV40_v40Bakedvae.safetensors', 'revAnimated_v2Rebirth.safetensors', 'sd21-unclip-h.ckpt', 'sd21-unclip-l.ckpt', 'sd3.5_large.safetensors', 'sd3.5_large_fp8_scaled.safetensors', 'sd3.5_large_turbo.safetensors', 'sd3.5_medium.safetensors', 'sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors', 'sd3_medium.safetensors', 'sd3_medium_incl_clips.safetensors', 'sd3_medium_incl_clips_t5xxlfp8.safetensors', 'sd_xl_base_1.0.safetensors', 'sd_xl_refiner_1.0.safetensors', 'sd_xl_turbo_1.0_fp16.safetensors', 'sdpose_wholebody_fp16.safetensors', 'stable-audio-open-1.0.safetensors', 'stable_cascade_stage_b.safetensors', 'stable_cascade_stage_c.safetensors', 'stable_zero123.ckpt', 'svd.safetensors', 'svd_xt.safetensors', 'v1-5-pruned-emaonly-fp16.safetensors', 'v1-5-pruned-emaonly.safetensors', 'v2-inpainting-pruned-ema.safetensors', 'wd-1-5-beta2-aesthetic-unclip-h.safetensors']", "['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2']", "['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal']", 'INT', 'INT', 'STRING', 'STRING', 'STRING', 'STRING', 'MASK', 'CONTROL_NET')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
    ) -> "_NodeBuilder":
        """Add a ``Context Switch Big (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node('Context Switch Big (rgthree)')

class Display_Any_rgthree:
    """Typed wrapper for the ComfyUI node class ``Display Any (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Display Any (rgthree)'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        source: "Handle",
    ) -> "_NodeBuilder":
        """Add a ``Display Any (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Display Any (rgthree)',
            source=source,
        )

class Display_Int_rgthree:
    """Typed wrapper for the ComfyUI node class ``Display Int (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Display Int (rgthree)'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        input: int,
    ) -> "_NodeBuilder":
        """Add a ``Display Int (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Display Int (rgthree)',
            input=input,
        )

class Image_Comparer_rgthree:
    """Typed wrapper for the ComfyUI node class ``Image Comparer (rgthree)``.

    Category: rgthree

    Compares two images with a hover slider, or click from properties.
    """

    CLASS_TYPE = 'Image Comparer (rgthree)'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_a: "Handle" = None,
        image_b: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``Image Comparer (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Image Comparer (rgthree)',
            image_a=image_a,
            image_b=image_b,
        )

class Image_Inset_Crop_rgthree:
    """Typed wrapper for the ComfyUI node class ``Image Inset Crop (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Image Inset Crop (rgthree)'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        bottom: int = 0,
        left: int = 0,
        measurement: str,
        right: int = 0,
        top: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``Image Inset Crop (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Image Inset Crop (rgthree)',
            image=image,
            bottom=bottom,
            left=left,
            measurement=measurement,
            right=right,
            top=top,
        )

class Image_Resize_rgthree:
    """Typed wrapper for the ComfyUI node class ``Image Resize (rgthree)``.

    Category: rgthree

    Resize the image.
    """

    CLASS_TYPE = 'Image Resize (rgthree)'
    OUTPUTS: tuple[str, ...] = ('IMAGE', 'WIDTH', 'HEIGHT')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        fit: str,
        height: int = 0,
        measurement: str,
        method: str,
        width: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``Image Resize (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Image Resize (rgthree)',
            image=image,
            fit=fit,
            height=height,
            measurement=measurement,
            method=method,
            width=width,
        )

class Image_or_Latent_Size_rgthree:
    """Typed wrapper for the ComfyUI node class ``Image or Latent Size (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Image or Latent Size (rgthree)'
    OUTPUTS: tuple[str, ...] = ('WIDTH', 'HEIGHT')
    OUTPUT_TYPES: tuple[str, ...] = ('INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
    ) -> "_NodeBuilder":
        """Add a ``Image or Latent Size (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node('Image or Latent Size (rgthree)')

class KSampler_Config_rgthree:
    """Typed wrapper for the ComfyUI node class ``KSampler Config (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'KSampler Config (rgthree)'
    OUTPUTS: tuple[str, ...] = ('STEPS', 'REFINER_STEP', 'CFG', 'SAMPLER', 'SCHEDULER')
    OUTPUT_TYPES: tuple[str, ...] = ('INT', 'INT', 'FLOAT', "['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2', 'exp_heun_2_x0', 'exp_heun_2_x0_sde', 'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp', 'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_2m_sde_heun', 'dpmpp_2m_sde_heun_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm', 'ipndm', 'ipndm_v', 'deis', 'res_multistep', 'res_multistep_cfg_pp', 'res_multistep_ancestral', 'res_multistep_ancestral_cfg_pp', 'gradient_estimation', 'gradient_estimation_cfg_pp', 'er_sde', 'seeds_2', 'seeds_3', 'sa_solver', 'sa_solver_pece', 'ddim', 'uni_pc', 'uni_pc_bh2']", "['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal']")

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        cfg: float = 8.0,
        refiner_step: int = 24,
        sampler_name: str,
        scheduler: str,
        steps_total: int = 30,
    ) -> "_NodeBuilder":
        """Add a ``KSampler Config (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'KSampler Config (rgthree)',
            cfg=cfg,
            refiner_step=refiner_step,
            sampler_name=sampler_name,
            scheduler=scheduler,
            steps_total=steps_total,
        )

class Lora_Loader_Stack_rgthree:
    """Typed wrapper for the ComfyUI node class ``Lora Loader Stack (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Lora Loader Stack (rgthree)'
    OUTPUTS: tuple[str, ...] = ('MODEL', 'CLIP')
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL', 'CLIP')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip: "Handle" = None,
        model: "Handle" = None,
        lora_01: str,
        lora_02: str,
        lora_03: str,
        lora_04: str,
        strength_01: float = 1.0,
        strength_02: float = 1.0,
        strength_03: float = 1.0,
        strength_04: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``Lora Loader Stack (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Lora Loader Stack (rgthree)',
            clip=clip,
            model=model,
            lora_01=lora_01,
            lora_02=lora_02,
            lora_03=lora_03,
            lora_04=lora_04,
            strength_01=strength_01,
            strength_02=strength_02,
            strength_03=strength_03,
            strength_04=strength_04,
        )

class Power_Lora_Loader_rgthree:
    """Typed wrapper for the ComfyUI node class ``Power Lora Loader (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Power Lora Loader (rgthree)'
    OUTPUTS: tuple[str, ...] = ('MODEL', 'CLIP')
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL', 'CLIP')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip: "Handle" = None,
        model: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``Power Lora Loader (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Power Lora Loader (rgthree)',
            clip=clip,
            model=model,
        )

class Power_Primitive_rgthree:
    """Typed wrapper for the ComfyUI node class ``Power Primitive (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Power Primitive (rgthree)'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
    ) -> "_NodeBuilder":
        """Add a ``Power Primitive (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node('Power Primitive (rgthree)')

class Power_Prompt_rgthree:
    """Typed wrapper for the ComfyUI node class ``Power Prompt (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Power Prompt (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONDITIONING', 'MODEL', 'CLIP', 'TEXT')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'MODEL', 'CLIP', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        prompt: str,
        insert_embedding: str = "",
        insert_lora: str = "",
        insert_saved: str = "",
        opt_clip: "Handle" = None,
        opt_model: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``Power Prompt (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Power Prompt (rgthree)',
            prompt=prompt,
            insert_embedding=insert_embedding,
            insert_lora=insert_lora,
            insert_saved=insert_saved,
            opt_clip=opt_clip,
            opt_model=opt_model,
        )

class Power_Prompt_Simple_rgthree:
    """Typed wrapper for the ComfyUI node class ``Power Prompt - Simple (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Power Prompt - Simple (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONDITIONING', 'TEXT')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        prompt: str,
        insert_embedding: str = "",
        insert_saved: str = "",
        opt_clip: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``Power Prompt - Simple (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Power Prompt - Simple (rgthree)',
            prompt=prompt,
            insert_embedding=insert_embedding,
            insert_saved=insert_saved,
            opt_clip=opt_clip,
        )

class Power_Puter_rgthree:
    """Typed wrapper for the ComfyUI node class ``Power Puter (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Power Puter (rgthree)'
    OUTPUTS: tuple[str, ...] = ('*',)
    OUTPUT_TYPES: tuple[str, ...] = ('*',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
    ) -> "_NodeBuilder":
        """Add a ``Power Puter (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node('Power Puter (rgthree)')

class SDXL_Empty_Latent_Image_rgthree:
    """Typed wrapper for the ComfyUI node class ``SDXL Empty Latent Image (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'SDXL Empty Latent Image (rgthree)'
    OUTPUTS: tuple[str, ...] = ('LATENT', 'CLIP_WIDTH', 'CLIP_HEIGHT')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'INT', 'INT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        batch_size: int = 1,
        clip_scale: float = 2.0,
        dimensions: str = "1024 x 1024  (square)",
    ) -> "_NodeBuilder":
        """Add a ``SDXL Empty Latent Image (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'SDXL Empty Latent Image (rgthree)',
            batch_size=batch_size,
            clip_scale=clip_scale,
            dimensions=dimensions,
        )

class SDXL_Power_Prompt_Positive_rgthree:
    """Typed wrapper for the ComfyUI node class ``SDXL Power Prompt - Positive (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'SDXL Power Prompt - Positive (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONDITIONING', 'MODEL', 'CLIP', 'TEXT_G', 'TEXT_L')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'MODEL', 'CLIP', 'STRING', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        prompt_g: str,
        prompt_l: str,
        crop_height: int = -1,
        crop_width: int = -1,
        insert_embedding: str = "",
        insert_lora: str = "",
        insert_saved: str = "",
        opt_clip: "Handle" = None,
        opt_clip_height: int = 1024.0,
        opt_clip_width: int = 1024.0,
        opt_model: "Handle" = None,
        target_height: int = -1,
        target_width: int = -1,
    ) -> "_NodeBuilder":
        """Add a ``SDXL Power Prompt - Positive (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'SDXL Power Prompt - Positive (rgthree)',
            prompt_g=prompt_g,
            prompt_l=prompt_l,
            crop_height=crop_height,
            crop_width=crop_width,
            insert_embedding=insert_embedding,
            insert_lora=insert_lora,
            insert_saved=insert_saved,
            opt_clip=opt_clip,
            opt_clip_height=opt_clip_height,
            opt_clip_width=opt_clip_width,
            opt_model=opt_model,
            target_height=target_height,
            target_width=target_width,
        )

class SDXL_Power_Prompt_Simple_Negative_rgthree:
    """Typed wrapper for the ComfyUI node class ``SDXL Power Prompt - Simple / Negative (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'SDXL Power Prompt - Simple / Negative (rgthree)'
    OUTPUTS: tuple[str, ...] = ('CONDITIONING', 'TEXT_G', 'TEXT_L')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'STRING', 'STRING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        prompt_g: str,
        prompt_l: str,
        crop_height: int = -1,
        crop_width: int = -1,
        insert_embedding: str = "",
        insert_saved: str = "",
        opt_clip: "Handle" = None,
        opt_clip_height: int = 1024.0,
        opt_clip_width: int = 1024.0,
        target_height: int = -1,
        target_width: int = -1,
    ) -> "_NodeBuilder":
        """Add a ``SDXL Power Prompt - Simple / Negative (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'SDXL Power Prompt - Simple / Negative (rgthree)',
            prompt_g=prompt_g,
            prompt_l=prompt_l,
            crop_height=crop_height,
            crop_width=crop_width,
            insert_embedding=insert_embedding,
            insert_saved=insert_saved,
            opt_clip=opt_clip,
            opt_clip_height=opt_clip_height,
            opt_clip_width=opt_clip_width,
            target_height=target_height,
            target_width=target_width,
        )

class Seed_rgthree:
    """Typed wrapper for the ComfyUI node class ``Seed (rgthree)``.

    Category: rgthree
    """

    CLASS_TYPE = 'Seed (rgthree)'
    OUTPUTS: tuple[str, ...] = ('SEED',)
    OUTPUT_TYPES: tuple[str, ...] = ('INT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        seed: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``Seed (rgthree)`` node to ``wf`` and return the builder.

        Source: object_info snapshot rgthree-comfy@runpod-snapshot.json sha256:4f6ac103927b
        """
        return wf.node(
            'Seed (rgthree)',
            seed=seed,
        )
