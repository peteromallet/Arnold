# vibecomfy:generated
# pack: ComfyUI-LTXVideo
# source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
# source_sha256: 68ee01812b496297e5ffc753b6de123ae1ac4c0f39c030f8f5e49cd1a9a9efba
# generator_version: 1.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 75
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers ComfyUI-LTXVideo

"""Auto-generated typed wrappers for the ComfyUI-LTXVideo custom-node pack.

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


class APGGuider:
    """Typed wrapper for the ComfyUI node class ``APGGuider``.

    Display name: 🅛🅣🅧 APG Guider

    Category: lightricks/LTXV

    The APG Guider implements Adaptive Projected Guidance (APG).
    """

    CLASS_TYPE = 'APGGuider'
    OUTPUTS: tuple[str, ...] = ('GUIDER',)
    OUTPUT_TYPES: tuple[str, ...] = ('GUIDER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        cfg_scale: float = 1.0,
        eta: float = 1.0,
        momentum_coefficient: float = -0.9,
        norm_threshold: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``APGGuider`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'APGGuider',
            model=model,
            negative=negative,
            positive=positive,
            cfg_scale=cfg_scale,
            eta=eta,
            momentum_coefficient=momentum_coefficient,
            norm_threshold=norm_threshold,
        )

class DynamicConditioning:
    """Typed wrapper for the ComfyUI node class ``DynamicConditioning``.

    Display name: 🅛🅣🅧 Dynamic Conditioning

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'DynamicConditioning'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        only_first_frame: bool = True,
        power: float = 1.3,
    ) -> "_NodeBuilder":
        """Add a ``DynamicConditioning`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'DynamicConditioning',
            model=model,
            only_first_frame=only_first_frame,
            power=power,
        )

class GemmaAPITextEncode:
    """Typed wrapper for the ComfyUI node class ``GemmaAPITextEncode``.

    Display name: 🅛🅣🅧 Gemma API Text Encode

    Category: api node/text/Lightricks
    """

    CLASS_TYPE = 'GemmaAPITextEncode'
    OUTPUTS: tuple[str, ...] = ('conditioning',)
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        api_key: str = "",
        ckpt_name: str,
        enhance_prompt: bool = True,
        prompt: str = "",
    ) -> "_NodeBuilder":
        """Add a ``GemmaAPITextEncode`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'GemmaAPITextEncode',
            api_key=api_key,
            ckpt_name=ckpt_name,
            enhance_prompt=enhance_prompt,
            prompt=prompt,
        )

class GuiderParameters:
    """Typed wrapper for the ComfyUI node class ``GuiderParameters``.

    Display name: 🅛🅣🅧 Guider Parameters

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'GuiderParameters'
    OUTPUTS: tuple[str, ...] = ('GUIDER_PARAMETERS',)
    OUTPUT_TYPES: tuple[str, ...] = ('GUIDER_PARAMETERS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        cfg: float = 1.0,
        cross_attn: bool = True,
        modality: str = "VIDEO",
        modality_scale: float = 0.0,
        perturb_attn: bool = True,
        rescale: float = 0.7,
        skip_step: int = 0,
        stg: float = 1.0,
        parameters: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``GuiderParameters`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'GuiderParameters',
            cfg=cfg,
            cross_attn=cross_attn,
            modality=modality,
            modality_scale=modality_scale,
            perturb_attn=perturb_attn,
            rescale=rescale,
            skip_step=skip_step,
            stg=stg,
            parameters=parameters,
        )

class ImageToCPU:
    """Typed wrapper for the ComfyUI node class ``ImageToCPU``.

    Display name: 🅛🅣🅧 Image to CPU

    Category: utility
    """

    CLASS_TYPE = 'ImageToCPU'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ImageToCPU`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'ImageToCPU',
            image=image,
        )

class LTXAddVideoICLoRAGuide:
    """Typed wrapper for the ComfyUI node class ``LTXAddVideoICLoRAGuide``.

    Display name: 🅛🅣🅧 Add Video IC-LoRA Guide

    Category: Lightricks/IC-LoRA

    Adds one or more conditioning frames starting at the specified frame index. Supports both single images and multi-frame videos. The latent_downscale_factor resizes input to a fraction of the target size (1 = original, 2 = half, 3 = third, etc.) for IC-LoRA on small grids.
    """

    CLASS_TYPE = 'LTXAddVideoICLoRAGuide'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        latent: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        vae: "Handle" = None,
        crop: str = "disabled",
        frame_idx: int = 0,
        latent_downscale_factor: float = 1.0,
        strength: float = 1.0,
        tile_overlap: int = 64,
        tile_size: int = 256,
        use_tiled_encode: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``LTXAddVideoICLoRAGuide`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXAddVideoICLoRAGuide',
            image=image,
            latent=latent,
            negative=negative,
            positive=positive,
            vae=vae,
            crop=crop,
            frame_idx=frame_idx,
            latent_downscale_factor=latent_downscale_factor,
            strength=strength,
            tile_overlap=tile_overlap,
            tile_size=tile_size,
            use_tiled_encode=use_tiled_encode,
        )

class LTXAddVideoICLoRAGuideAdvanced:
    """Typed wrapper for the ComfyUI node class ``LTXAddVideoICLoRAGuideAdvanced``.

    Display name: 🅛🅣🅧 Add Video IC-LoRA Guide Advanced

    Category: Lightricks/IC-LoRA

    Adds IC-LoRA guide conditioning with per-guide attention strength control. Same as LTXAddVideoICLoRAGuide, but allows controlling how strongly this guide influences generation via self-attention, optionally with a spatial mask.
    """

    CLASS_TYPE = 'LTXAddVideoICLoRAGuideAdvanced'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        latent: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        vae: "Handle" = None,
        attention_strength: float = 1.0,
        crop: str = "disabled",
        frame_idx: int = 0,
        latent_downscale_factor: float = 1.0,
        strength: float = 1.0,
        tile_overlap: int = 64,
        tile_size: int = 256,
        use_tiled_encode: bool = False,
        attention_mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXAddVideoICLoRAGuideAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXAddVideoICLoRAGuideAdvanced',
            image=image,
            latent=latent,
            negative=negative,
            positive=positive,
            vae=vae,
            attention_strength=attention_strength,
            crop=crop,
            frame_idx=frame_idx,
            latent_downscale_factor=latent_downscale_factor,
            strength=strength,
            tile_overlap=tile_overlap,
            tile_size=tile_size,
            use_tiled_encode=use_tiled_encode,
            attention_mask=attention_mask,
        )

class LTXAttentioOverride:
    """Typed wrapper for the ComfyUI node class ``LTXAttentioOverride``.

    Display name: LTX Attn Block Override

    Category: ltxtricks
    """

    CLASS_TYPE = 'LTXAttentioOverride'
    OUTPUTS: tuple[str, ...] = ('LTX_BLOCKS',)
    OUTPUT_TYPES: tuple[str, ...] = ('LTX_BLOCKS',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        blocks: str,
    ) -> "_NodeBuilder":
        """Add a ``LTXAttentioOverride`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXAttentioOverride',
            blocks=blocks,
        )

class LTXAttentionBank:
    """Typed wrapper for the ComfyUI node class ``LTXAttentionBank``.

    Display name: LTX Attention Bank

    Category: ltxtricks
    """

    CLASS_TYPE = 'LTXAttentionBank'
    OUTPUTS: tuple[str, ...] = ('ATTN_BANK',)
    OUTPUT_TYPES: tuple[str, ...] = ('ATTN_BANK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        blocks: str,
        save_steps: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``LTXAttentionBank`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXAttentionBank',
            blocks=blocks,
            save_steps=save_steps,
        )

class LTXAttnOverride:
    """Typed wrapper for the ComfyUI node class ``LTXAttnOverride``.

    Display name: LTX Attention Override

    Category: ltxtricks/attn
    """

    CLASS_TYPE = 'LTXAttnOverride'
    OUTPUTS: tuple[str, ...] = ('ATTN_OVERRIDE',)
    OUTPUT_TYPES: tuple[str, ...] = ('ATTN_OVERRIDE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        layers: str,
    ) -> "_NodeBuilder":
        """Add a ``LTXAttnOverride`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXAttnOverride',
            layers=layers,
        )

class LTXFetaEnhance:
    """Typed wrapper for the ComfyUI node class ``LTXFetaEnhance``.

    Display name: LTX Feta Enhance

    Category: ltxtricks
    """

    CLASS_TYPE = 'LTXFetaEnhance'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        feta_weight: float = 4,
        attn_override: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXFetaEnhance`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXFetaEnhance',
            model=model,
            feta_weight=feta_weight,
            attn_override=attn_override,
        )

class LTXFloatToInt:
    """Typed wrapper for the ComfyUI node class ``LTXFloatToInt``.

    Display name: 🅛🅣🅧 Float To Int

    Category: math/conversion
    """

    CLASS_TYPE = 'LTXFloatToInt'
    OUTPUTS: tuple[str, ...] = ('INT',)
    OUTPUT_TYPES: tuple[str, ...] = ('INT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        a: float = 0.0,
    ) -> "_NodeBuilder":
        """Add a ``LTXFloatToInt`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXFloatToInt',
            a=a,
        )

class LTXFlowEditCFGGuider:
    """Typed wrapper for the ComfyUI node class ``LTXFlowEditCFGGuider``.

    Display name: LTX Flow Edit CFG Guider

    Category: ltxtricks
    """

    CLASS_TYPE = 'LTXFlowEditCFGGuider'
    OUTPUTS: tuple[str, ...] = ('GUIDER',)
    OUTPUT_TYPES: tuple[str, ...] = ('GUIDER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        source_neg: "Handle" = None,
        source_pos: "Handle" = None,
        target_neg: "Handle" = None,
        target_pos: "Handle" = None,
        source_cfg: float = 2,
        target_cfg: float = 4.5,
    ) -> "_NodeBuilder":
        """Add a ``LTXFlowEditCFGGuider`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXFlowEditCFGGuider',
            model=model,
            source_neg=source_neg,
            source_pos=source_pos,
            target_neg=target_neg,
            target_pos=target_pos,
            source_cfg=source_cfg,
            target_cfg=target_cfg,
        )

class LTXFlowEditSampler:
    """Typed wrapper for the ComfyUI node class ``LTXFlowEditSampler``.

    Display name: LTX Flow Edit Sampler

    Category: ltxtricks
    """

    CLASS_TYPE = 'LTXFlowEditSampler'
    OUTPUTS: tuple[str, ...] = ('SAMPLER',)
    OUTPUT_TYPES: tuple[str, ...] = ('SAMPLER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        refine_steps: int = 0,
        seed: int = 0,
        skip_steps: int = 4,
    ) -> "_NodeBuilder":
        """Add a ``LTXFlowEditSampler`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXFlowEditSampler',
            refine_steps=refine_steps,
            seed=seed,
            skip_steps=skip_steps,
        )

class LTXForwardModelSamplingPred:
    """Typed wrapper for the ComfyUI node class ``LTXForwardModelSamplingPred``.

    Display name: LTX Forward Model Pred

    Category: ltxtricks
    """

    CLASS_TYPE = 'LTXForwardModelSamplingPred'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXForwardModelSamplingPred`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXForwardModelSamplingPred',
            model=model,
        )

class LTXICLoRALoaderModelOnly:
    """Typed wrapper for the ComfyUI node class ``LTXICLoRALoaderModelOnly``.

    Display name: 🅛🅣🅧 IC-LoRA Loader Model Only

    Category: Lightricks/IC-LoRA

    Loads a LoRA model and extracts the latent_downscale_factor from the safetensors metadata.
    """

    CLASS_TYPE = 'LTXICLoRALoaderModelOnly'
    OUTPUTS: tuple[str, ...] = ('model', 'latent_downscale_factor')
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL', 'FLOAT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        lora_name: str,
        strength_model: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``LTXICLoRALoaderModelOnly`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXICLoRALoaderModelOnly',
            model=model,
            lora_name=lora_name,
            strength_model=strength_model,
        )

class LTXPerturbedAttention:
    """Typed wrapper for the ComfyUI node class ``LTXPerturbedAttention``.

    Display name: LTX Apply Perturbed Attention

    Category: ltxtricks/attn
    """

    CLASS_TYPE = 'LTXPerturbedAttention'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        cfg: float = 3.0,
        rescale: float = 0.5,
        scale: float = 2.0,
        attn_override: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXPerturbedAttention`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXPerturbedAttention',
            model=model,
            cfg=cfg,
            rescale=rescale,
            scale=scale,
            attn_override=attn_override,
        )

class LTXPrepareAttnInjections:
    """Typed wrapper for the ComfyUI node class ``LTXPrepareAttnInjections``.

    Display name: LTX Prepare Attn Injection

    Category: fluxtapoz
    """

    CLASS_TYPE = 'LTXPrepareAttnInjections'
    OUTPUTS: tuple[str, ...] = ('LATENT', 'ATTN_INJ')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'ATTN_INJ')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        attn_bank: "Handle" = None,
        latent: "Handle" = None,
        inject_steps: int = 0,
        key: bool = False,
        query: bool = False,
        value: bool = False,
        blocks: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXPrepareAttnInjections`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXPrepareAttnInjections',
            attn_bank=attn_bank,
            latent=latent,
            inject_steps=inject_steps,
            key=key,
            query=query,
            value=value,
            blocks=blocks,
        )

class LTXQ8Patch:
    """Typed wrapper for the ComfyUI node class ``LTXQ8Patch``.

    Display name: 🅛🅣🅧 LTXQ8Patch

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'LTXQ8Patch'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        quantization_preset: str = "0.9.8",
        quantize_cross_attn: bool = True,
        quantize_ffn: bool = True,
        quantize_self_attn: bool = True,
        use_fp8_attention: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``LTXQ8Patch`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXQ8Patch',
            model=model,
            quantization_preset=quantization_preset,
            quantize_cross_attn=quantize_cross_attn,
            quantize_ffn=quantize_ffn,
            quantize_self_attn=quantize_self_attn,
            use_fp8_attention=use_fp8_attention,
        )

class LTXRFForwardODESampler:
    """Typed wrapper for the ComfyUI node class ``LTXRFForwardODESampler``.

    Display name: LTX Rf-Inv Forward Sampler

    Category: ltxtricks
    """

    CLASS_TYPE = 'LTXRFForwardODESampler'
    OUTPUTS: tuple[str, ...] = ('SAMPLER',)
    OUTPUT_TYPES: tuple[str, ...] = ('SAMPLER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        end_step: int = 5,
        gamma: float = 0.5,
        gamma_trend: str,
        start_step: int = 0,
        attn_bank: "Handle" = None,
        order: str = "",
        seed: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``LTXRFForwardODESampler`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXRFForwardODESampler',
            end_step=end_step,
            gamma=gamma,
            gamma_trend=gamma_trend,
            start_step=start_step,
            attn_bank=attn_bank,
            order=order,
            seed=seed,
        )

class LTXRFReverseODESampler:
    """Typed wrapper for the ComfyUI node class ``LTXRFReverseODESampler``.

    Display name: LTX Rf-Inv Reverse Sampler

    Category: ltxtricks
    """

    CLASS_TYPE = 'LTXRFReverseODESampler'
    OUTPUTS: tuple[str, ...] = ('SAMPLER',)
    OUTPUT_TYPES: tuple[str, ...] = ('SAMPLER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent_image: "Handle" = None,
        model: "Handle" = None,
        end_step: int = 15,
        eta: float = 0.8,
        start_step: int = 0,
        attn_inj: "Handle" = None,
        eta_trend: str = "",
        order: str = "",
    ) -> "_NodeBuilder":
        """Add a ``LTXRFReverseODESampler`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXRFReverseODESampler',
            latent_image=latent_image,
            model=model,
            end_step=end_step,
            eta=eta,
            start_step=start_step,
            attn_inj=attn_inj,
            eta_trend=eta_trend,
            order=order,
        )

class LTXReverseModelSamplingPred:
    """Typed wrapper for the ComfyUI node class ``LTXReverseModelSamplingPred``.

    Display name: LTX Reverse Model Pred

    Category: ltxtricks
    """

    CLASS_TYPE = 'LTXReverseModelSamplingPred'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXReverseModelSamplingPred`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXReverseModelSamplingPred',
            model=model,
        )

class LTXVAdainLatent:
    """Typed wrapper for the ComfyUI node class ``LTXVAdainLatent``.

    Display name: 🅛🅣🅧 LTXV Adain Latent

    Category: Lightricks/latents
    """

    CLASS_TYPE = 'LTXVAdainLatent'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latents: "Handle" = None,
        reference: "Handle" = None,
        factor: float = 1.0,
        per_frame: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``LTXVAdainLatent`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVAdainLatent',
            latents=latents,
            reference=reference,
            factor=factor,
            per_frame=per_frame,
        )

class LTXVAddGuideAdvanced:
    """Typed wrapper for the ComfyUI node class ``LTXVAddGuideAdvanced``.

    Display name: 🅛🅣🅧 LTXV Add Guide Advanced

    Category: conditioning/video_models

    Adds a conditioning frame or a video at a specific frame index. This node is used to add a keyframe or a video segment which should appear in the generated video at a specified index. It resizes the image to the correct size and applies preprocessing to it.
    """

    CLASS_TYPE = 'LTXVAddGuideAdvanced'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        latent: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        vae: "Handle" = None,
        blur_radius: int = 0,
        crf: int = 29,
        crop: str = "disabled",
        frame_idx: int = 0,
        interpolation: str = "lanczos",
        strength: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``LTXVAddGuideAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVAddGuideAdvanced',
            image=image,
            latent=latent,
            negative=negative,
            positive=positive,
            vae=vae,
            blur_radius=blur_radius,
            crf=crf,
            crop=crop,
            frame_idx=frame_idx,
            interpolation=interpolation,
            strength=strength,
        )

class LTXVAddGuideAdvancedAttention:
    """Typed wrapper for the ComfyUI node class ``LTXVAddGuideAdvancedAttention``.

    Display name: 🅛🅣🅧 LTXV Add Guide Advanced Attention

    Category: conditioning/video_models

    Adds a conditioning frame/video at a specific frame index with per-guide attention strength control. Same preprocessing as LTXVAddGuideAdvanced, plus attention_strength and optional spatial attention_mask.
    """

    CLASS_TYPE = 'LTXVAddGuideAdvancedAttention'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        latent: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        vae: "Handle" = None,
        attention_strength: float = 1.0,
        blur_radius: int = 0,
        crf: int = 29,
        crop: str = "disabled",
        frame_idx: int = 0,
        interpolation: str = "lanczos",
        strength: float = 1.0,
        attention_mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVAddGuideAdvancedAttention`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVAddGuideAdvancedAttention',
            image=image,
            latent=latent,
            negative=negative,
            positive=positive,
            vae=vae,
            attention_strength=attention_strength,
            blur_radius=blur_radius,
            crf=crf,
            crop=crop,
            frame_idx=frame_idx,
            interpolation=interpolation,
            strength=strength,
            attention_mask=attention_mask,
        )

class LTXVAddLatentGuide:
    """Typed wrapper for the ComfyUI node class ``LTXVAddLatentGuide``.

    Display name: 🅛🅣🅧 LTXV Add Latent Guide

    Category: ltxtricks

    Adds a keyframe or a video segment at a specific frame index.
    """

    CLASS_TYPE = 'LTXVAddLatentGuide'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        guiding_latent: "Handle" = None,
        latent: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        vae: "Handle" = None,
        latent_idx: int = 0,
        strength: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``LTXVAddLatentGuide`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVAddLatentGuide',
            guiding_latent=guiding_latent,
            latent=latent,
            negative=negative,
            positive=positive,
            vae=vae,
            latent_idx=latent_idx,
            strength=strength,
        )

class LTXVAddLatents:
    """Typed wrapper for the ComfyUI node class ``LTXVAddLatents``.

    Display name: 🅛🅣🅧 LTXV Add Latents

    Category: latent/video

    Concatenates two video latents along the frames dimension. latents1 and latents2 must have the same dimensions except for the frames dimension.
    """

    CLASS_TYPE = 'LTXVAddLatents'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latents1: "Handle" = None,
        latents2: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVAddLatents`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVAddLatents',
            latents1=latents1,
            latents2=latents2,
        )

class LTXVApplySTG:
    """Typed wrapper for the ComfyUI node class ``LTXVApplySTG``.

    Display name: 🅛🅣🅧 LTXV Apply STG

    Category: lightricks/LTXV

    Defines the blocks to apply the STG to.
    """

    CLASS_TYPE = 'LTXVApplySTG'
    OUTPUTS: tuple[str, ...] = ('model',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        block_indices: str = "14, 19",
    ) -> "_NodeBuilder":
        """Add a ``LTXVApplySTG`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVApplySTG',
            model=model,
            block_indices=block_indices,
        )

class LTXVBaseSampler:
    """Typed wrapper for the ComfyUI node class ``LTXVBaseSampler``.

    Display name: 🅛🅣🅧 LTXV Base Sampler

    Category: sampling
    """

    CLASS_TYPE = 'LTXVBaseSampler'
    OUTPUTS: tuple[str, ...] = ('denoised', 'positive', 'negative')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'CONDITIONING', 'CONDITIONING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        guider: "Handle" = None,
        model: "Handle" = None,
        noise: "Handle" = None,
        sampler: "Handle" = None,
        sigmas: "Handle" = None,
        vae: "Handle" = None,
        height: int = 512,
        num_frames: int = 97,
        width: int = 768,
        blur: int = 0,
        crf: int = 35,
        crop: str = "disabled",
        optional_cond_images: "Handle" = None,
        optional_cond_indices: str = "",
        strength: float = 0.9,
    ) -> "_NodeBuilder":
        """Add a ``LTXVBaseSampler`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVBaseSampler',
            guider=guider,
            model=model,
            noise=noise,
            sampler=sampler,
            sigmas=sigmas,
            vae=vae,
            height=height,
            num_frames=num_frames,
            width=width,
            blur=blur,
            crf=crf,
            crop=crop,
            optional_cond_images=optional_cond_images,
            optional_cond_indices=optional_cond_indices,
            strength=strength,
        )

class LTXVDilateLatent:
    """Typed wrapper for the ComfyUI node class ``LTXVDilateLatent``.

    Display name: 🅛🅣🅧 LTXV Dilate Latent

    Category: latent/video

    Dilates a latent by a grid size.
    """

    CLASS_TYPE = 'LTXVDilateLatent'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latent: "Handle" = None,
        horizontal_scale: int = 1,
        vertical_scale: int = 1,
    ) -> "_NodeBuilder":
        """Add a ``LTXVDilateLatent`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVDilateLatent',
            latent=latent,
            horizontal_scale=horizontal_scale,
            vertical_scale=vertical_scale,
        )

class LTXVDilateVideoMask:
    """Typed wrapper for the ComfyUI node class ``LTXVDilateVideoMask``.

    Display name: 🅛🅣🅧 LTXV Dilate Video Mask

    Category: Lightricks/mask_operations

    Dilates a video mask spatially and/or temporally using separable max-pooling and thresholds the result.
    """

    CLASS_TYPE = 'LTXVDilateVideoMask'
    OUTPUTS: tuple[str, ...] = ('mask',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        spatial_radius: int = 1,
        temporal_radius: int = 0,
        image_as_mask: "Handle" = None,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVDilateVideoMask`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVDilateVideoMask',
            spatial_radius=spatial_radius,
            temporal_radius=temporal_radius,
            image_as_mask=image_as_mask,
            mask=mask,
        )

class LTXVDrawTracks:
    """Typed wrapper for the ComfyUI node class ``LTXVDrawTracks``.

    Display name: 🅛🅣🅧 LTX Draw Sparse Tracks

    Category: Lightricks/motion_tracking

    GPU-accelerated sparse track renderer. Rasterises circles at high resolution and downscales with bilinear interpolation.
    """

    CLASS_TYPE = 'LTXVDrawTracks'
    OUTPUTS: tuple[str, ...] = ('IMAGE',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        height: int = 512,
        tracks: str,
        width: int = 512,
    ) -> "_NodeBuilder":
        """Add a ``LTXVDrawTracks`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVDrawTracks',
            height=height,
            tracks=tracks,
            width=width,
        )

class LTXVExtendSampler:
    """Typed wrapper for the ComfyUI node class ``LTXVExtendSampler``.

    Display name: 🅛🅣🅧 LTXV Extend Sampler

    Category: sampling
    """

    CLASS_TYPE = 'LTXVExtendSampler'
    OUTPUTS: tuple[str, ...] = ('denoised_video', 'positive', 'negative')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'CONDITIONING', 'CONDITIONING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        guider: "Handle" = None,
        latents: "Handle" = None,
        model: "Handle" = None,
        noise: "Handle" = None,
        sampler: "Handle" = None,
        sigmas: "Handle" = None,
        vae: "Handle" = None,
        frame_overlap: int = 16,
        num_new_frames: int = 80,
        strength: float = 0.5,
        cond_image_strength: float = 1.0,
        optional_cond_images: "Handle" = None,
        optional_cond_indices: str = "",
        optional_guiding_latents: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVExtendSampler`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVExtendSampler',
            guider=guider,
            latents=latents,
            model=model,
            noise=noise,
            sampler=sampler,
            sigmas=sigmas,
            vae=vae,
            frame_overlap=frame_overlap,
            num_new_frames=num_new_frames,
            strength=strength,
            cond_image_strength=cond_image_strength,
            optional_cond_images=optional_cond_images,
            optional_cond_indices=optional_cond_indices,
            optional_guiding_latents=optional_guiding_latents,
        )

class LTXVGemmaCLIPModelLoader:
    """Typed wrapper for the ComfyUI node class ``LTXVGemmaCLIPModelLoader``.

    Display name: 🅛🅣🅧 Gemma 3 Model Loader

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'LTXVGemmaCLIPModelLoader'
    OUTPUTS: tuple[str, ...] = ('clip',)
    OUTPUT_TYPES: tuple[str, ...] = ('CLIP',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        gemma_path: str,
        ltxv_path: str,
        max_length: int = 1024,
    ) -> "_NodeBuilder":
        """Add a ``LTXVGemmaCLIPModelLoader`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVGemmaCLIPModelLoader',
            gemma_path=gemma_path,
            ltxv_path=ltxv_path,
            max_length=max_length,
        )

class LTXVGemmaEnhancePrompt:
    """Typed wrapper for the ComfyUI node class ``LTXVGemmaEnhancePrompt``.

    Display name: 🅛🅣🅧 Gemma 3 Prompt Enhancer

    Category: lightricks/LTXV

    Enhance text prompts using Gemma 3 VLLM for improved video generation.
    """

    CLASS_TYPE = 'LTXVGemmaEnhancePrompt'
    OUTPUTS: tuple[str, ...] = ('enhanced_prompt',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip: "Handle" = None,
        bypass_i2v: bool = False,
        max_tokens: int = 512,
        prompt: str = "",
        system_prompt: str = "You are a Creative Assistant. Given a user's raw input prompt describing a scene or concept, expand it into a detailed video generation prompt with specific visuals and integrated audio to guide a text-to-video model.\n\n#### Guidelines\n- Strictly follow all aspects of the user's raw input: include every element requested (style, visuals, motions, actions, camera movement, audio).\n    - If the input is vague, invent concrete details: lighting, textures, materials, scene settings, etc.\n        - For characters: describe gender, clothing, hair, expressions. DO NOT invent unrequested characters.\n- Use active language: present-progressive verbs (\"is walking,\" \"speaking\"). If no action specified, describe natural movements.\n- Maintain chronological flow: use temporal connectors (\"as,\" \"then,\" \"while\").\n- Audio layer: Describe complete soundscape (background audio, ambient sounds, SFX, speech/music when requested). Integrate sounds chronologically alongside actions. Be specific (e.g., \"soft footsteps on tile\"), not vague (e.g., \"ambient sound is present\").\n- Speech (only when requested):\n    - For ANY speech-related input (talking, conversation, singing, etc.), ALWAYS include exact words in quotes with voice characteristics (e.g., \"The man says in an excited voice: 'You won't believe what I just saw!'\").\n    - Specify language if not English and accent if relevant.\n- Style: Include visual style at the beginning: \"Style: <style>, <rest of prompt>.\" Default to cinematic-realistic if unspecified. Omit if unclear.\n- Visual and audio only: NO non-visual/auditory senses (smell, taste, touch).\n- Restrained language: Avoid dramatic/exaggerated terms. Use mild, natural phrasing.\n    - Colors: Use plain terms (\"red dress\"), not intensified (\"vibrant blue,\" \"bright red\").\n    - Lighting: Use neutral descriptions (\"soft overhead light\"), not harsh (\"blinding light\").\n    - Facial features: Use delicate modifiers for subtle features (i.e., \"subtle freckles\").\n\n#### Important notes:\n- Analyze the user's raw input carefully. In cases of FPV or POV, exclude the description of the subject whose POV is requested.\n- Camera motion: DO NOT invent camera motion unless requested by the user.\n- Speech: DO NOT modify user-provided character dialogue unless it's a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Format: DO NOT use phrases like \"The scene opens with...\". Start directly with Style (optional) and chronological scene description.\n- Format: DO NOT start your response with special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- If the user's raw input prompt is highly detailed, chronological and in the requested format: DO NOT make major edits or introduce new elements. Add/enhance audio descriptions if missing.\n\n#### Output Format (Strict):\n- Single continuous paragraph in natural language (English).\n- NO titles, headings, prefaces, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\nYour output quality is CRITICAL. Generate visually rich, dynamic prompts with integrated audio for high-quality video generation.\n\n#### Example\nInput: \"A woman at a coffee shop talking on the phone\"\nOutput:\nStyle: realistic with cinematic lighting. In a medium close-up, a woman in her early 30s with shoulder-length brown hair sits at a small wooden table by the window. She wears a cream-colored turtleneck sweater, holding a white ceramic coffee cup in one hand and a smartphone to her ear with the other. Ambient cafe sounds fill the space\u2014espresso machine hiss, quiet conversations, gentle clinking of cups. The woman listens intently, nodding slightly, then takes a sip of her coffee and sets it down with a soft clink. Her face brightens into a warm smile as she speaks in a clear, friendly voice, 'That sounds perfect! I'd love to meet up this weekend. How about Saturday afternoon?' She laughs softly\u2014a genuine chuckle\u2014and shifts in her chair. Behind her, other patrons move subtly in and out of focus. 'Great, I'll see you then,' she concludes cheerfully, lowering the phone.",
        image: "Handle" = None,
        seed: int = 42,
    ) -> "_NodeBuilder":
        """Add a ``LTXVGemmaEnhancePrompt`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVGemmaEnhancePrompt',
            clip=clip,
            bypass_i2v=bypass_i2v,
            max_tokens=max_tokens,
            prompt=prompt,
            system_prompt=system_prompt,
            image=image,
            seed=seed,
        )

class LTXVHDRDecodePostprocess:
    """Typed wrapper for the ComfyUI node class ``LTXVHDRDecodePostprocess``.

    Display name: 🅛🅣🅧 LTXVHDR Decode Postprocess

    Category: Lightricks/HDR

    Decompresses VAE-decoded output from HDR IC-LoRA (LogC3) and applies Reinhard tonemapping. Place after VAE Decode. 'tonemapped' is the SDR preview; 'hdr_linear' is raw linear HDR for downstream use. Enable 'save_exr' to write an EXR image sequence.if save_exr is enabled, make sure to set OPENCV_IO_ENABLE_OPENEXR=1 environment in the command line
    """

    CLASS_TYPE = 'LTXVHDRDecodePostprocess'
    OUTPUTS: tuple[str, ...] = ('tonemapped', 'hdr_linear')
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE', 'IMAGE')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        exposure: float = 0.0,
        filename_prefix: str = "frame",
        half_precision: bool = True,
        output_dir: str = "output/hdr_exr",
        save_exr: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``LTXVHDRDecodePostprocess`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVHDRDecodePostprocess',
            image=image,
            exposure=exposure,
            filename_prefix=filename_prefix,
            half_precision=half_precision,
            output_dir=output_dir,
            save_exr=save_exr,
        )

class LTXVImgToVideoAdvanced:
    """Typed wrapper for the ComfyUI node class ``LTXVImgToVideoAdvanced``.

    Display name: 🅛🅣🅧 LTXV Img To Video Advanced

    Category: conditioning/video_models

    Adds a conditioning frame or a video at index 0. This node is used to add a keyframe or a video segment which should appear in the generated video at index 0. It resizes the image to the correct size and applies preprocessing to it.
    """

    CLASS_TYPE = 'LTXVImgToVideoAdvanced'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'latent')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        vae: "Handle" = None,
        batch_size: int = 1,
        blur_radius: int = 0,
        crf: int = 29,
        crop: str = "disabled",
        height: int = 512,
        interpolation: str = "lanczos",
        length: int = 97,
        strength: float = 0.9,
        width: int = 768,
    ) -> "_NodeBuilder":
        """Add a ``LTXVImgToVideoAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVImgToVideoAdvanced',
            image=image,
            negative=negative,
            positive=positive,
            vae=vae,
            batch_size=batch_size,
            blur_radius=blur_radius,
            crf=crf,
            crop=crop,
            height=height,
            interpolation=interpolation,
            length=length,
            strength=strength,
            width=width,
        )

class LTXVImgToVideoConditionOnly:
    """Typed wrapper for the ComfyUI node class ``LTXVImgToVideoConditionOnly``.

    Display name: 🅛🅣🅧 LTXV Img To Video Condition Only

    Category: conditioning/video_models

    Applies image conditioning to the first frames of an existing latent. Creates a noise mask to control conditioning strength.
    """

    CLASS_TYPE = 'LTXVImgToVideoConditionOnly'
    OUTPUTS: tuple[str, ...] = ('latent',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        latent: "Handle" = None,
        vae: "Handle" = None,
        strength: float = 1.0,
        bypass: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``LTXVImgToVideoConditionOnly`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVImgToVideoConditionOnly',
            image=image,
            latent=latent,
            vae=vae,
            strength=strength,
            bypass=bypass,
        )

class LTXVInContextSampler:
    """Typed wrapper for the ComfyUI node class ``LTXVInContextSampler``.

    Display name: 🅛🅣🅧 LTXV In Context Sampler

    Category: sampling
    """

    CLASS_TYPE = 'LTXVInContextSampler'
    OUTPUTS: tuple[str, ...] = ('denoised_video', 'positive', 'negative')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'CONDITIONING', 'CONDITIONING')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        guider: "Handle" = None,
        guiding_latents: "Handle" = None,
        noise: "Handle" = None,
        sampler: "Handle" = None,
        sigmas: "Handle" = None,
        vae: "Handle" = None,
        num_frames: int = -1,
        optional_cond_images: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVInContextSampler`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVInContextSampler',
            guider=guider,
            guiding_latents=guiding_latents,
            noise=noise,
            sampler=sampler,
            sigmas=sigmas,
            vae=vae,
            num_frames=num_frames,
            optional_cond_images=optional_cond_images,
        )

class LTXVInpaintPreprocess:
    """Typed wrapper for the ComfyUI node class ``LTXVInpaintPreprocess``.

    Display name: 🅛🅣🅧 LTXV Inpaint Preprocess

    Category: Lightricks/image_processing

    Composites images with a green background where mask is active, for inpainting conditioning.
    """

    CLASS_TYPE = 'LTXVInpaintPreprocess'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        images: "Handle" = None,
        mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVInpaintPreprocess`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVInpaintPreprocess',
            images=images,
            mask=mask,
        )

class LTXVLaplacianPyramidBlend:
    """Typed wrapper for the ComfyUI node class ``LTXVLaplacianPyramidBlend``.

    Display name: 🅛🅣🅧 LTX Laplacian Pyramid Blend

    Category: Lightricks/utility

    Blend two images seamlessly using Laplacian pyramid blending.
    """

    CLASS_TYPE = 'LTXVLaplacianPyramidBlend'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_a: "Handle" = None,
        image_b: "Handle" = None,
        mask: "Handle" = None,
        mask_low_res_dilation: int = 5,
        trim_to_shortest: bool = True,
    ) -> "_NodeBuilder":
        """Add a ``LTXVLaplacianPyramidBlend`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVLaplacianPyramidBlend',
            image_a=image_a,
            image_b=image_b,
            mask=mask,
            mask_low_res_dilation=mask_low_res_dilation,
            trim_to_shortest=trim_to_shortest,
        )

class LTXVLinearOverlapLatentTransition:
    """Typed wrapper for the ComfyUI node class ``LTXVLinearOverlapLatentTransition``.

    Display name: 🅛🅣🅧 LTXV Linear Overlap Latent Transition

    Category: Lightricks/latent
    """

    CLASS_TYPE = 'LTXVLinearOverlapLatentTransition'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        samples1: "Handle" = None,
        samples2: "Handle" = None,
        overlap: int = 1,
        axis: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``LTXVLinearOverlapLatentTransition`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVLinearOverlapLatentTransition',
            samples1=samples1,
            samples2=samples2,
            overlap=overlap,
            axis=axis,
        )

class LTXVLoadConditioning:
    """Typed wrapper for the ComfyUI node class ``LTXVLoadConditioning``.

    Display name: 🅛🅣🅧 LTXV Load Conditioning

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'LTXVLoadConditioning'
    OUTPUTS: tuple[str, ...] = ('CONDITIONING',)
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        device: str,
        file_name: str,
    ) -> "_NodeBuilder":
        """Add a ``LTXVLoadConditioning`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVLoadConditioning',
            device=device,
            file_name=file_name,
        )

class LTXVLoopingSampler:
    """Typed wrapper for the ComfyUI node class ``LTXVLoopingSampler``.

    Display name: 🅛🅣🅧 LTXV Looping Sampler

    Category: sampling
    """

    CLASS_TYPE = 'LTXVLoopingSampler'
    OUTPUTS: tuple[str, ...] = ('denoised_output',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        guider: "Handle" = None,
        latents: "Handle" = None,
        model: "Handle" = None,
        noise: "Handle" = None,
        sampler: "Handle" = None,
        sigmas: "Handle" = None,
        vae: "Handle" = None,
        cond_image_strength: float = 1.0,
        guiding_strength: float = 1.0,
        horizontal_tiles: int = 1,
        spatial_overlap: int = 1,
        temporal_overlap: int = 24,
        temporal_overlap_cond_strength: float = 0.5,
        temporal_tile_size: int = 80,
        vertical_tiles: int = 1,
        adain_factor: float = 0.0,
        guiding_end_step: int = 1000,
        guiding_start_step: int = 0,
        optional_cond_image_indices: str = "0",
        optional_cond_images: "Handle" = None,
        optional_guiding_latents: "Handle" = None,
        optional_negative_index_latents: "Handle" = None,
        optional_normalizing_latents: "Handle" = None,
        optional_positive_conditionings: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVLoopingSampler`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVLoopingSampler',
            guider=guider,
            latents=latents,
            model=model,
            noise=noise,
            sampler=sampler,
            sigmas=sigmas,
            vae=vae,
            cond_image_strength=cond_image_strength,
            guiding_strength=guiding_strength,
            horizontal_tiles=horizontal_tiles,
            spatial_overlap=spatial_overlap,
            temporal_overlap=temporal_overlap,
            temporal_overlap_cond_strength=temporal_overlap_cond_strength,
            temporal_tile_size=temporal_tile_size,
            vertical_tiles=vertical_tiles,
            adain_factor=adain_factor,
            guiding_end_step=guiding_end_step,
            guiding_start_step=guiding_start_step,
            optional_cond_image_indices=optional_cond_image_indices,
            optional_cond_images=optional_cond_images,
            optional_guiding_latents=optional_guiding_latents,
            optional_negative_index_latents=optional_negative_index_latents,
            optional_normalizing_latents=optional_normalizing_latents,
            optional_positive_conditionings=optional_positive_conditionings,
        )

class LTXVMultiPromptProvider:
    """Typed wrapper for the ComfyUI node class ``LTXVMultiPromptProvider``.

    Display name: 🅛🅣🅧 LTXV Multi Prompt Provider

    Category: prompt
    """

    CLASS_TYPE = 'LTXVMultiPromptProvider'
    OUTPUTS: tuple[str, ...] = ('conditionings',)
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip: "Handle" = None,
        prompts: str,
    ) -> "_NodeBuilder":
        """Add a ``LTXVMultiPromptProvider`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVMultiPromptProvider',
            clip=clip,
            prompts=prompts,
        )

class LTXVNormalizingSampler:
    """Typed wrapper for the ComfyUI node class ``LTXVNormalizingSampler``.

    Display name: 🅛🅣🅧 LTXV Normalizing Sampler

    Category: utility
    """

    CLASS_TYPE = 'LTXVNormalizingSampler'
    OUTPUTS: tuple[str, ...] = ('denoised_output',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        guider: "Handle" = None,
        latent_image: "Handle" = None,
        noise: "Handle" = None,
        sampler: "Handle" = None,
        sigmas: "Handle" = None,
        audio_normalization_factors: str = "1,1,0.25,1,1,0.25,1,1",
        video_normalization_factors: str = "1,1,1,1,1,1,1,1",
    ) -> "_NodeBuilder":
        """Add a ``LTXVNormalizingSampler`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVNormalizingSampler',
            guider=guider,
            latent_image=latent_image,
            noise=noise,
            sampler=sampler,
            sigmas=sigmas,
            audio_normalization_factors=audio_normalization_factors,
            video_normalization_factors=video_normalization_factors,
        )

class LTXVPatcherVAE:
    """Typed wrapper for the ComfyUI node class ``LTXVPatcherVAE``.

    Display name: 🅛🅣🅧 LTXV Patcher VAE

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'LTXVPatcherVAE'
    OUTPUTS: tuple[str, ...] = ('VAE',)
    OUTPUT_TYPES: tuple[str, ...] = ('VAE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        vae: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVPatcherVAE`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVPatcherVAE',
            vae=vae,
        )

class LTXVPerStepAdainPatcher:
    """Typed wrapper for the ComfyUI node class ``LTXVPerStepAdainPatcher``.

    Display name: 🅛🅣🅧 LTXV Per Step Adain Patcher

    Category: Lightricks/latents
    """

    CLASS_TYPE = 'LTXVPerStepAdainPatcher'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        reference: "Handle" = None,
        factors: str = "0.9, 0.75, 0.0",
        per_frame: bool = False,
    ) -> "_NodeBuilder":
        """Add a ``LTXVPerStepAdainPatcher`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVPerStepAdainPatcher',
            model=model,
            reference=reference,
            factors=factors,
            per_frame=per_frame,
        )

class LTXVPerStepStatNormPatcher:
    """Typed wrapper for the ComfyUI node class ``LTXVPerStepStatNormPatcher``.

    Display name: 🅛🅣🅧 LTXV Per Step Stat Norm Patcher

    Category: Lightricks/latents
    """

    CLASS_TYPE = 'LTXVPerStepStatNormPatcher'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        clip_outliers: bool = False,
        factors: str = "0.9, 0.75, 0.0",
        percentile: float = 95.0,
        target_mean: float = 0.0,
        target_std: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``LTXVPerStepStatNormPatcher`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVPerStepStatNormPatcher',
            model=model,
            clip_outliers=clip_outliers,
            factors=factors,
            percentile=percentile,
            target_mean=target_mean,
            target_std=target_std,
        )

class LTXVPreprocessMasks:
    """Typed wrapper for the ComfyUI node class ``LTXVPreprocessMasks``.

    Display name: 🅛🅣🅧 LTXV Preprocess Masks

    Category: Lightricks/mask_operations

    Preprocess masks to be used for masking latents in the LTXVideo model.
    """

    CLASS_TYPE = 'LTXVPreprocessMasks'
    OUTPUTS: tuple[str, ...] = ('MASK',)
    OUTPUT_TYPES: tuple[str, ...] = ('MASK',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        masks: "Handle" = None,
        vae: "Handle" = None,
        clamp_max: float = 1.0,
        clamp_min: float = 0.5,
        grow_mask: int = 0,
        ignore_first_mask: bool = True,
        invert_input_masks: bool = False,
        pooling_method: str = "max",
        tapered_corners: bool = True,
    ) -> "_NodeBuilder":
        """Add a ``LTXVPreprocessMasks`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVPreprocessMasks',
            masks=masks,
            vae=vae,
            clamp_max=clamp_max,
            clamp_min=clamp_min,
            grow_mask=grow_mask,
            ignore_first_mask=ignore_first_mask,
            invert_input_masks=invert_input_masks,
            pooling_method=pooling_method,
            tapered_corners=tapered_corners,
        )

class LTXVPromptEnhancer:
    """Typed wrapper for the ComfyUI node class ``LTXVPromptEnhancer``.

    Display name: 🅛🅣🅧 LTXV Prompt Enhancer

    Category: lightricks/LTXV

    Enhances text prompts for image generation using LLMs. Optionally incorporates reference images to create more contextually relevant descriptions.
    """

    CLASS_TYPE = 'LTXVPromptEnhancer'
    OUTPUTS: tuple[str, ...] = ('str',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        prompt_enhancer: "Handle" = None,
        max_resulting_tokens: int = 256,
        prompt: str,
        image_prompt: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVPromptEnhancer`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVPromptEnhancer',
            prompt_enhancer=prompt_enhancer,
            max_resulting_tokens=max_resulting_tokens,
            prompt=prompt,
            image_prompt=image_prompt,
        )

class LTXVPromptEnhancerLoader:
    """Typed wrapper for the ComfyUI node class ``LTXVPromptEnhancerLoader``.

    Display name: 🅛🅣🅧 LTXV Prompt Enhancer Loader

    Category: lightricks/LTXV

    Downloads and initializes LLM and image captioning models from Hugging Face to enhance text prompts for image generation.
    """

    CLASS_TYPE = 'LTXVPromptEnhancerLoader'
    OUTPUTS: tuple[str, ...] = ('prompt_enhancer',)
    OUTPUT_TYPES: tuple[str, ...] = ('LTXV_PROMPT_ENHANCER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image_captioner_name: str = ["MiaoshouAI/Florence-2-large-PromptGen-v2.0"],
        llm_name: str = ["unsloth/Llama-3.2-3B-Instruct"],
    ) -> "_NodeBuilder":
        """Add a ``LTXVPromptEnhancerLoader`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVPromptEnhancerLoader',
            image_captioner_name=image_captioner_name,
            llm_name=llm_name,
        )

class LTXVQ8LoraModelLoader:
    """Typed wrapper for the ComfyUI node class ``LTXVQ8LoraModelLoader``.

    Display name: 🅛🅣🅧 LTXVQ8Lora Model Loader

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'LTXVQ8LoraModelLoader'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        lora_name: str,
        strength_model: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``LTXVQ8LoraModelLoader`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVQ8LoraModelLoader',
            model=model,
            lora_name=lora_name,
            strength_model=strength_model,
        )

class LTXVSaveConditioning:
    """Typed wrapper for the ComfyUI node class ``LTXVSaveConditioning``.

    Display name: 🅛🅣🅧 LTXV Save Conditioning

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'LTXVSaveConditioning'
    OUTPUTS: tuple[str, ...] = ()
    OUTPUT_TYPES: tuple[str, ...] = ()

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        conditioning: "Handle" = None,
        dtype: str,
        filename: str = "conditioning",
    ) -> "_NodeBuilder":
        """Add a ``LTXVSaveConditioning`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVSaveConditioning',
            conditioning=conditioning,
            dtype=dtype,
            filename=filename,
        )

class LTXVSelectLatents:
    """Typed wrapper for the ComfyUI node class ``LTXVSelectLatents``.

    Display name: 🅛🅣🅧 LTXV Select Latents

    Category: latent/video

    Selects a range of frames from the video latent. start_index and end_index define a closed interval (inclusive of both endpoints).
    """

    CLASS_TYPE = 'LTXVSelectLatents'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        samples: "Handle" = None,
        end_index: int = -1,
        start_index: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``LTXVSelectLatents`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVSelectLatents',
            samples=samples,
            end_index=end_index,
            start_index=start_index,
        )

class LTXVSetAudioRefTokens:
    """Typed wrapper for the ComfyUI node class ``LTXVSetAudioRefTokens``.

    Display name: 🅛🅣🅧 Set Audio Ref Tokens

    Category: Lightricks/IC-LoRA

    Provides speaker identity context for audio generation by attaching reference audio tokens to the conditioning. The tokens are prepended with negative temporal positions so the model treats them as context rather than generation targets.
    """

    CLASS_TYPE = 'LTXVSetAudioRefTokens'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'frozen_audio')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        audio_latent: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVSetAudioRefTokens`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVSetAudioRefTokens',
            audio_latent=audio_latent,
            negative=negative,
            positive=positive,
        )

class LTXVSetAudioVideoMaskByTime:
    """Typed wrapper for the ComfyUI node class ``LTXVSetAudioVideoMaskByTime``.

    Display name: 🅛🅣🅧 LTXV Set Audio Video Mask By Time

    Category: utility

    Sets the audio and video mask by time.
    """

    CLASS_TYPE = 'LTXVSetAudioVideoMaskByTime'
    OUTPUTS: tuple[str, ...] = ('positive', 'negative', 'av_latent', 'video_latent_blend_coefficients', 'video_pixel_blend_coefficients')
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING', 'CONDITIONING', 'LATENT', 'FLOAT', 'FLOAT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        audio_vae: "Handle" = None,
        av_latent: "Handle" = None,
        model: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        vae: "Handle" = None,
        end_time: float = 10.0,
        mask_audio: bool = True,
        mask_init_value_audio: float = 0.0,
        mask_init_value_video: float = 0.0,
        mask_video: bool = True,
        slope_len: int = 3,
        start_time: float = 0.0,
        video_fps: float = 24.0,
        spatial_mask: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVSetAudioVideoMaskByTime`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVSetAudioVideoMaskByTime',
            audio_vae=audio_vae,
            av_latent=av_latent,
            model=model,
            negative=negative,
            positive=positive,
            vae=vae,
            end_time=end_time,
            mask_audio=mask_audio,
            mask_init_value_audio=mask_init_value_audio,
            mask_init_value_video=mask_init_value_video,
            mask_video=mask_video,
            slope_len=slope_len,
            start_time=start_time,
            video_fps=video_fps,
            spatial_mask=spatial_mask,
        )

class LTXVSetVideoLatentNoiseMasks:
    """Typed wrapper for the ComfyUI node class ``LTXVSetVideoLatentNoiseMasks``.

    Display name: 🅛🅣🅧 LTXV Set Video Latent Noise Masks

    Category: latent/video

    Applies multiple masks to a video latent. masks can be 2D, 3D, or 4D tensors. If there are fewer masks than frames, the last mask will be reused.
    """

    CLASS_TYPE = 'LTXVSetVideoLatentNoiseMasks'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        masks: "Handle" = None,
        samples: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LTXVSetVideoLatentNoiseMasks`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVSetVideoLatentNoiseMasks',
            masks=masks,
            samples=samples,
        )

class LTXVSparseTrackEditor:
    """Typed wrapper for the ComfyUI node class ``LTXVSparseTrackEditor``.

    Display name: 🅛🅣🅧 LTX Sparse Track Editor

    Category: Lightricks/motion_tracking

    Interactive spline editor for drawing sparse motion tracks on a reference image.
    """

    CLASS_TYPE = 'LTXVSparseTrackEditor'
    OUTPUTS: tuple[str, ...] = ('tracks',)
    OUTPUT_TYPES: tuple[str, ...] = ('STRING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        image: "Handle" = None,
        coordinates: str = "[]",
        points_store: str = "[]",
        points_to_sample: int = 121,
    ) -> "_NodeBuilder":
        """Add a ``LTXVSparseTrackEditor`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVSparseTrackEditor',
            image=image,
            coordinates=coordinates,
            points_store=points_store,
            points_to_sample=points_to_sample,
        )

class LTXVSpatioTemporalTiledVAEDecode:
    """Typed wrapper for the ComfyUI node class ``LTXVSpatioTemporalTiledVAEDecode``.

    Display name: 🅛🅣🅧 LTXV Spatio Temporal Tiled VAE Decode

    Category: latent
    """

    CLASS_TYPE = 'LTXVSpatioTemporalTiledVAEDecode'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latents: "Handle" = None,
        vae: "Handle" = None,
        last_frame_fix: bool = False,
        spatial_overlap: int = 1,
        spatial_tiles: int = 4,
        temporal_overlap: int = 1,
        temporal_tile_length: int = 16,
        working_device: str = "auto",
        working_dtype: str = "auto",
    ) -> "_NodeBuilder":
        """Add a ``LTXVSpatioTemporalTiledVAEDecode`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVSpatioTemporalTiledVAEDecode',
            latents=latents,
            vae=vae,
            last_frame_fix=last_frame_fix,
            spatial_overlap=spatial_overlap,
            spatial_tiles=spatial_tiles,
            temporal_overlap=temporal_overlap,
            temporal_tile_length=temporal_tile_length,
            working_device=working_device,
            working_dtype=working_dtype,
        )

class LTXVStatNormLatent:
    """Typed wrapper for the ComfyUI node class ``LTXVStatNormLatent``.

    Display name: 🅛🅣🅧 LTXV Stat Norm Latent

    Category: Lightricks/latents
    """

    CLASS_TYPE = 'LTXVStatNormLatent'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latents: "Handle" = None,
        clip_outliers: bool = False,
        factor: float = 1.0,
        percentile: float = 95.0,
        target_mean: float = 0.0,
        target_std: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``LTXVStatNormLatent`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVStatNormLatent',
            latents=latents,
            clip_outliers=clip_outliers,
            factor=factor,
            percentile=percentile,
            target_mean=target_mean,
            target_std=target_std,
        )

class LTXVTiledSampler:
    """Typed wrapper for the ComfyUI node class ``LTXVTiledSampler``.

    Display name: 🅛🅣🅧 LTXV Tiled Sampler

    Category: sampling
    """

    CLASS_TYPE = 'LTXVTiledSampler'
    OUTPUTS: tuple[str, ...] = ('output', 'denoised_output')
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT', 'LATENT')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        guider: "Handle" = None,
        latents: "Handle" = None,
        model: "Handle" = None,
        noise: "Handle" = None,
        sampler: "Handle" = None,
        sigmas: "Handle" = None,
        vae: "Handle" = None,
        boost_latent_similarity: bool = False,
        crop: str = "disabled",
        horizontal_tiles: int = 1,
        latents_cond_strength: float = 0.15,
        overlap: int = 1,
        vertical_tiles: int = 1,
        images_cond_strengths: str = "0.9",
        optional_cond_images: "Handle" = None,
        optional_cond_indices: str = "0",
    ) -> "_NodeBuilder":
        """Add a ``LTXVTiledSampler`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVTiledSampler',
            guider=guider,
            latents=latents,
            model=model,
            noise=noise,
            sampler=sampler,
            sigmas=sigmas,
            vae=vae,
            boost_latent_similarity=boost_latent_similarity,
            crop=crop,
            horizontal_tiles=horizontal_tiles,
            latents_cond_strength=latents_cond_strength,
            overlap=overlap,
            vertical_tiles=vertical_tiles,
            images_cond_strengths=images_cond_strengths,
            optional_cond_images=optional_cond_images,
            optional_cond_indices=optional_cond_indices,
        )

class LTXVTiledVAEDecode:
    """Typed wrapper for the ComfyUI node class ``LTXVTiledVAEDecode``.

    Display name: 🅛🅣🅧 LTXV Tiled VAE Decode

    Category: latent
    """

    CLASS_TYPE = 'LTXVTiledVAEDecode'
    OUTPUTS: tuple[str, ...] = ('image',)
    OUTPUT_TYPES: tuple[str, ...] = ('IMAGE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        latents: "Handle" = None,
        vae: "Handle" = None,
        horizontal_tiles: int = 1,
        last_frame_fix: bool = False,
        overlap: int = 1,
        vertical_tiles: int = 1,
        working_device: str = "auto",
        working_dtype: str = "auto",
    ) -> "_NodeBuilder":
        """Add a ``LTXVTiledVAEDecode`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LTXVTiledVAEDecode',
            latents=latents,
            vae=vae,
            horizontal_tiles=horizontal_tiles,
            last_frame_fix=last_frame_fix,
            overlap=overlap,
            vertical_tiles=vertical_tiles,
            working_device=working_device,
            working_dtype=working_dtype,
        )

class LinearOverlapLatentTransition:
    """Typed wrapper for the ComfyUI node class ``LinearOverlapLatentTransition``.

    Display name: 🅛🅣🅧 Linear transition with overlap

    Category: Lightricks/latent
    """

    CLASS_TYPE = 'LinearOverlapLatentTransition'
    OUTPUTS: tuple[str, ...] = ('LATENT',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        samples1: "Handle" = None,
        samples2: "Handle" = None,
        overlap: int = 1,
        axis: int = 0,
    ) -> "_NodeBuilder":
        """Add a ``LinearOverlapLatentTransition`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LinearOverlapLatentTransition',
            samples1=samples1,
            samples2=samples2,
            overlap=overlap,
            axis=axis,
        )

class LowVRAMAudioVAELoader:
    """Typed wrapper for the ComfyUI node class ``LowVRAMAudioVAELoader``.

    Display name: 🅛🅣🅧 Low VRAM Audio VAE Loader

    Category: LTXV/loaders

    Loads an LTXV Audio VAE checkpoint with dependency support. Connect 'dependencies' to a previous loader's output to ensure sequential loading and reduce peak VRAM usage.
    """

    CLASS_TYPE = 'LowVRAMAudioVAELoader'
    OUTPUTS: tuple[str, ...] = ('audio_vae',)
    OUTPUT_TYPES: tuple[str, ...] = ('VAE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        ckpt_name: str,
        dependencies: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LowVRAMAudioVAELoader`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LowVRAMAudioVAELoader',
            ckpt_name=ckpt_name,
            dependencies=dependencies,
        )

class LowVRAMCheckpointLoader:
    """Typed wrapper for the ComfyUI node class ``LowVRAMCheckpointLoader``.

    Display name: 🅛🅣🅧 Low VRAM Checkpoint Loader

    Category: LTXV/loaders

    Loads a diffusion model checkpoint with dependency support. Connect 'dependencies' to a previous loader's output to ensure sequential loading and reduce peak VRAM usage.
    """

    CLASS_TYPE = 'LowVRAMCheckpointLoader'
    OUTPUTS: tuple[str, ...] = ('MODEL', 'CLIP', 'VAE')
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL', 'CLIP', 'VAE')

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        ckpt_name: str,
        dependencies: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``LowVRAMCheckpointLoader`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LowVRAMCheckpointLoader',
            ckpt_name=ckpt_name,
            dependencies=dependencies,
        )

class LowVRAMLatentUpscaleModelLoader:
    """Typed wrapper for the ComfyUI node class ``LowVRAMLatentUpscaleModelLoader``.

    Display name: 🅛🅣🅧 Low VRAM Latent Upscale Model Loader

    Category: loaders
    """

    CLASS_TYPE = 'LowVRAMLatentUpscaleModelLoader'
    OUTPUTS: tuple[str, ...] = ('LATENT_UPSCALE_MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('LATENT_UPSCALE_MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model_name: str,
    ) -> "_NodeBuilder":
        """Add a ``LowVRAMLatentUpscaleModelLoader`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'LowVRAMLatentUpscaleModelLoader',
            model_name=model_name,
        )

class ModifyLTXModel:
    """Typed wrapper for the ComfyUI node class ``ModifyLTXModel``.

    Display name: Modify LTX Model

    Category: ltxtricks
    """

    CLASS_TYPE = 'ModifyLTXModel'
    OUTPUTS: tuple[str, ...] = ('MODEL',)
    OUTPUT_TYPES: tuple[str, ...] = ('MODEL',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``ModifyLTXModel`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'ModifyLTXModel',
            model=model,
        )

class MultiPromptProvider:
    """Typed wrapper for the ComfyUI node class ``MultiPromptProvider``.

    Display name: 🅛🅣🅧 Multi Prompt Provider

    Category: prompt
    """

    CLASS_TYPE = 'MultiPromptProvider'
    OUTPUTS: tuple[str, ...] = ('conditionings',)
    OUTPUT_TYPES: tuple[str, ...] = ('CONDITIONING',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        clip: "Handle" = None,
        prompts: str,
    ) -> "_NodeBuilder":
        """Add a ``MultiPromptProvider`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'MultiPromptProvider',
            clip=clip,
            prompts=prompts,
        )

class MultimodalGuider:
    """Typed wrapper for the ComfyUI node class ``MultimodalGuider``.

    Display name: 🅛🅣🅧 Multimodal Guider

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'MultimodalGuider'
    OUTPUTS: tuple[str, ...] = ('GUIDER',)
    OUTPUT_TYPES: tuple[str, ...] = ('GUIDER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        negative: "Handle" = None,
        parameters: "Handle" = None,
        positive: "Handle" = None,
        skip_blocks: str = "",
    ) -> "_NodeBuilder":
        """Add a ``MultimodalGuider`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'MultimodalGuider',
            model=model,
            negative=negative,
            parameters=parameters,
            positive=positive,
            skip_blocks=skip_blocks,
        )

class STGAdvancedPresets:
    """Typed wrapper for the ComfyUI node class ``STGAdvancedPresets``.

    Display name: 🅛🅣🅧 STG Advanced Presets

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'STGAdvancedPresets'
    OUTPUTS: tuple[str, ...] = ('STG_ADVANCED_PRESET',)
    OUTPUT_TYPES: tuple[str, ...] = ('STG_ADVANCED_PRESET',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        preset: str = "13b Balanced",
    ) -> "_NodeBuilder":
        """Add a ``STGAdvancedPresets`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'STGAdvancedPresets',
            preset=preset,
        )

class STGGuider:
    """Typed wrapper for the ComfyUI node class ``STGGuider``.

    Display name: 🅛🅣🅧 STG Guider

    Category: lightricks/LTXV

    Implements Spatiotemporal Skip Guidance (STG), a training-free method enhancing transformer-based video diffusion models by selectively skipping layers during sampling. This approach improves video quality without sacrificing diversity or motion fidelity.Reference: https://arxiv.org/abs/2411.18664.
    """

    CLASS_TYPE = 'STGGuider'
    OUTPUTS: tuple[str, ...] = ('GUIDER',)
    OUTPUT_TYPES: tuple[str, ...] = ('GUIDER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        cfg: float = 1.0,
        rescale: float = 0.7,
        stg: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``STGGuider`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'STGGuider',
            model=model,
            negative=negative,
            positive=positive,
            cfg=cfg,
            rescale=rescale,
            stg=stg,
        )

class STGGuiderAdvanced:
    """Typed wrapper for the ComfyUI node class ``STGGuiderAdvanced``.

    Display name: 🅛🅣🅧 STG Guider Advanced

    Category: lightricks/LTXV

    The Advanced STG Guider implements sophisticated techniques for controlling the denoising process:
    """

    CLASS_TYPE = 'STGGuiderAdvanced'
    OUTPUTS: tuple[str, ...] = ('GUIDER',)
    OUTPUT_TYPES: tuple[str, ...] = ('GUIDER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        cfg_star_rescale: bool = True,
        cfg_values: str = "8, 6, 6, 4, 3, 1",
        sigmas: str = "1.0, 0.9933, 0.9850, 0.9767, 0.9008, 0.6180",
        skip_steps_sigma_threshold: float = 0.998,
        stg_layers_indices: str = "[29], [29], [29], [29], [29], [29]",
        stg_rescale_values: str = "1, 1, 1, 1, 1, 1",
        stg_scale_values: str = "4, 4, 3, 2, 1, 0",
        apg_cfg_scale: float = 1.0,
        apply_apg: bool = False,
        eta: float = 1.0,
        norm_threshold: float = 0.0,
        preset: "Handle" = None,
    ) -> "_NodeBuilder":
        """Add a ``STGGuiderAdvanced`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'STGGuiderAdvanced',
            model=model,
            negative=negative,
            positive=positive,
            cfg_star_rescale=cfg_star_rescale,
            cfg_values=cfg_values,
            sigmas=sigmas,
            skip_steps_sigma_threshold=skip_steps_sigma_threshold,
            stg_layers_indices=stg_layers_indices,
            stg_rescale_values=stg_rescale_values,
            stg_scale_values=stg_scale_values,
            apg_cfg_scale=apg_cfg_scale,
            apply_apg=apply_apg,
            eta=eta,
            norm_threshold=norm_threshold,
            preset=preset,
        )

class STGGuiderNode:
    """Typed wrapper for the ComfyUI node class ``STGGuiderNode``.

    Display name: 🅛🅣🅧 STG Guider Node

    Category: lightricks/LTXV

    Implements Spatiotemporal Skip Guidance (STG), a training-free method enhancing transformer-based video diffusion models by selectively skipping layers during sampling. This approach improves video quality without sacrificing diversity or motion fidelity.Reference: https://arxiv.org/abs/2411.18664.
    """

    CLASS_TYPE = 'STGGuiderNode'
    OUTPUTS: tuple[str, ...] = ('GUIDER',)
    OUTPUT_TYPES: tuple[str, ...] = ('GUIDER',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle" = None,
        negative: "Handle" = None,
        positive: "Handle" = None,
        cfg: float = 1.0,
        rescale: float = 0.7,
        stg: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``STGGuiderNode`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'STGGuiderNode',
            model=model,
            negative=negative,
            positive=positive,
            cfg=cfg,
            rescale=rescale,
            stg=stg,
        )

class Set_VAE_Decoder_Noise:
    """Typed wrapper for the ComfyUI node class ``Set VAE Decoder Noise``.

    Display name: 🅛🅣🅧 Set VAE Decoder Noise

    Category: lightricks/LTXV
    """

    CLASS_TYPE = 'Set VAE Decoder Noise'
    OUTPUTS: tuple[str, ...] = ('VAE',)
    OUTPUT_TYPES: tuple[str, ...] = ('VAE',)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        vae: "Handle" = None,
        scale: float = 0.025,
        seed: int = 42,
        timestep: float = 0.05,
    ) -> "_NodeBuilder":
        """Add a ``Set VAE Decoder Noise`` node to ``wf`` and return the builder.

        Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:ae02bd88cfb9
        """
        return wf.node(
            'Set VAE Decoder Noise',
            vae=vae,
            scale=scale,
            seed=seed,
            timestep=timestep,
        )
