# vibecomfy: manual
"""Lightricks LTX 2.3 two-stage first/last parity template.

Pure-Python ready template using the official Lightricks two-stage spine
for no-control first/last frame video generation.  No Runexx, IC-LoRA,
raw-video guide, or sageattention dependencies.
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


LTX_LIGHTRICKS_MODEL_ASSETS = [
    {
        "name": "ltx-2.3-22b-dev-fp8.safetensors",
        "url": "https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-2.3-22b-dev-fp8.safetensors",
        "subdir": "checkpoints",
    },
    {
        "name": "gemma_3_12B_it_fp4_mixed.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors",
        "subdir": "text_encoders",
    },
    {
        "name": "ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-lora-384-1.1.safetensors",
        "subdir": "loras",
    },
]

READY_METADATA = {
    "model_assets": LTX_LIGHTRICKS_MODEL_ASSETS,
    "unbound_inputs": {"seed": 3779},
    "ready_template": "video/ltx2_3_lightricks_first_last_parity",
    "workflow_template": "ltx2_3_lightricks_first_last_parity",
    "capability": "first_last_frame_video",
    "source_role": "manual_ready_python_template",
    "source_workflow": None,
    "coverage_tier": "required",
    "approach": "Official Lightricks two-stage first/last spine",
    "runtime_note": "Patches named inputs for prompt, negative, seeds, dimensions, frames, fps, first/last images.",
    "discord_signal": "First/last frame video generation for LTX 2.3 travel segments.",
    "smoke_resolution": "256x256x5_frames",
    "ltx_best_practices": [
        "Use the official Lightricks workflows as runtime gates where possible.",
        "Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.",
    ],
    "comfy_configuration": {"reserve_vram": 12, "cache_none": True, "fp8_e4m3fn_text_enc": True},
}

READY_REQUIREMENTS = {
    "models": [],
    "custom_nodes": ["ComfyUI-KJNodes", "ComfyUI-LTXVideo"],
}


def build() -> VibeWorkflow:
    """Build the Lightricks two-stage first/last parity workflow."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    # ── image inputs (first + last) ──────────────────────────────────
    loadimage_first = _node(wf, "LoadImage", "2004", image="example.png", widget_0="example.png", widget_1="image")
    loadimage_last = _node(wf, "LoadImage", "2005", image="example.png", widget_0="example.png", widget_1="image")

    # ── model / VAE loader ───────────────────────────────────────────
    lowvramcheckpointloader = _node(
        wf, "LowVRAMCheckpointLoader", "3940", ckpt_name="ltx-2.3-22b-dev-fp8.safetensors"
    )
    lowvramaudiovaeloader = _node(
        wf, "LowVRAMAudioVAELoader", "4010", ckpt_name="ltx-2.3-22b-dev-fp8.safetensors"
    )

    # ── samplers ─────────────────────────────────────────────────────
    ksamplerselect = _node(wf, "KSamplerSelect", "4831", sampler_name="euler_ancestral_cfg_pp")
    ksamplerselect_2 = _node(wf, "KSamplerSelect", "4976", sampler_name="euler_cfg_pp")

    # ── seeds ────────────────────────────────────────────────────────
    randomnoise_first = _node(wf, "RandomNoise", "4832", noise_seed=43, control_after_generate="fixed")
    randomnoise_last = _node(wf, "RandomNoise", "4967", noise_seed=42, control_after_generate="fixed")

    # ── text encoder ─────────────────────────────────────────────────
    ltxavtextencoderloader = _node(
        wf,
        "LTXAVTextEncoderLoader",
        "4982",
        ckpt_name="ltx-2.3-22b-dev-fp8.safetensors",
        text_encoder="gemma_3_12B_it_fp4_mixed.safetensors",
        widget_0="gemma_3_12B_it_fp4_mixed.safetensors",
        widget_1="ltx-2.3-22b-dev-fp8.safetensors",
        widget_2="default",
    )

    # ── sigmas ───────────────────────────────────────────────────────
    manualsigmas_stage1 = _node(
        wf, "ManualSigmas", "4984", widget_0="1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
    )
    manualsigmas_stage2 = _node(wf, "ManualSigmas", "4985", widget_0="0.909375, 0.725, 0.421875, 0.0")

    # ── dimensions / frames / fps ────────────────────────────────────
    primitiveint_frames = _node(wf, "PrimitiveInt", "4988", value=5, widget_1="fixed")
    primitivefloat_fps = _node(wf, "PrimitiveFloat", "4989", value=8)

    # ── prompt / negative ────────────────────────────────────────────
    cliptextencode_prompt = _node(
        wf,
        "CLIPTextEncode",
        "2483",
        text="A serene Japanese tea ceremony in a traditional tatami room.",
        clip=ltxavtextencoderloader.out(0),
    )
    cliptextencode_negative = _node(
        wf,
        "CLIPTextEncode",
        "2612",
        text="pc game, console game, video game, cartoon, childish, ugly",
        clip=ltxavtextencoderloader.out(0),
    )

    # ── latent video ─────────────────────────────────────────────────
    emptyltxvlatentvideo = _node(
        wf,
        "EmptyLTXVLatentVideo",
        "3059",
        width=256,
        height=256,
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        length=primitiveint_frames.out(0),
    )

    # ── LoRA ─────────────────────────────────────────────────────────
    loraloadermodelonly = _node(
        wf,
        "LoraLoaderModelOnly",
        "4922",
        lora_name="ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors",
        strength_model=0.5,
        model=lowvramcheckpointloader.out(0),
    )

    # ── image preprocessing (first + last) ───────────────────────────
    resizeimagemask_first = _node(
        wf,
        "ResizeImageMaskNode",
        "4990",
        widget_0="scale longer dimension",
        widget_1=256,
        widget_2="lanczos",
        input=loadimage_first.out(0),
    )
    resizeimagemask_last = _node(
        wf,
        "ResizeImageMaskNode",
        "4991",
        widget_0="scale longer dimension",
        widget_1=256,
        widget_2="lanczos",
        input=loadimage_last.out(0),
    )

    ltxvpreprocess_first = _node(
        wf, "LTXVPreprocess", "3336", widget_0=18, image=resizeimagemask_first.out(0)
    )
    ltxvpreprocess_last = _node(
        wf, "LTXVPreprocess", "3337", widget_0=18, image=resizeimagemask_last.out(0)
    )

    # ── conditioning ─────────────────────────────────────────────────
    ltxfloattoint = _node(wf, "LTXFloatToInt", "5000", widget_0=0, a=primitivefloat_fps.out(0))

    ltxvconditioning = _node(
        wf,
        "LTXVConditioning",
        "1241",
        widget_0=8,
        frame_rate=primitivefloat_fps.out(0),
        negative=cliptextencode_negative.out(0),
        positive=cliptextencode_prompt.out(0),
    )

    # ── audio latent (empty — required for two-stage spine) ──────────
    ltxvemptylatentaudio = _node(
        wf,
        "LTXVEmptyLatentAudio",
        "3980",
        widget_0=5,
        widget_1=8,
        widget_2=1,
        audio_vae=lowvramaudiovaeloader.out(0),
        frame_rate=ltxfloattoint.out(0),
        frames_number=primitiveint_frames.out(0),
    )

    # ── stage 1: first frame conditioning ────────────────────────────
    ltxvimgtovideoconditiononly_first = _node(
        wf,
        "LTXVImgToVideoConditionOnly",
        "3159",
        widget_0=1.0,
        widget_1=False,
        bypass=None,
        image=ltxvpreprocess_first.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=lowvramcheckpointloader.out(2),
    )

    cfgguider = _node(
        wf,
        "CFGGuider",
        "4828",
        cfg=2.5,
        model=loraloadermodelonly.out(0),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
    )

    ltxvconcatavlatent_first = _node(
        wf,
        "LTXVConcatAVLatent",
        "4528",
        audio_latent=ltxvemptylatentaudio.out(0),
        video_latent=ltxvimgtovideoconditiononly_first.out(0),
    )

    samplercustomadvanced_first = _node(
        wf,
        "SamplerCustomAdvanced",
        "4829",
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent_first.out(0),
        noise=randomnoise_first.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=manualsigmas_stage1.out(0),
    )

    ltxvseparateavlatent_first = _node(
        wf,
        "LTXVSeparateAVLatent",
        "4845",
        av_latent=samplercustomadvanced_first.out(0),
    )

    # ── stage 2: last frame conditioning ─────────────────────────────
    ltxvimgtovideoconditiononly_last = _node(
        wf,
        "LTXVImgToVideoConditionOnly",
        "4970",
        widget_0=1.0,
        widget_1=False,
        bypass=None,
        image=resizeimagemask_last.out(0),
        latent=ltxvseparateavlatent_first.out(0),
        vae=lowvramcheckpointloader.out(2),
    )

    cfgguider_2 = _node(
        wf,
        "CFGGuider",
        "4964",
        cfg=2.5,
        model=loraloadermodelonly.out(0),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
    )

    ltxvconcatavlatent_last = _node(
        wf,
        "LTXVConcatAVLatent",
        "4969",
        audio_latent=ltxvseparateavlatent_first.out(1),
        video_latent=ltxvimgtovideoconditiononly_last.out(0),
    )

    samplercustomadvanced_last = _node(
        wf,
        "SamplerCustomAdvanced",
        "4971",
        guider=cfgguider_2.out(0),
        latent_image=ltxvconcatavlatent_last.out(0),
        noise=randomnoise_last.out(0),
        sampler=ksamplerselect_2.out(0),
        sigmas=manualsigmas_stage2.out(0),
    )

    ltxvseparateavlatent_last = _node(
        wf,
        "LTXVSeparateAVLatent",
        "4973",
        av_latent=samplercustomadvanced_last.out(0),
    )

    # ── decode ───────────────────────────────────────────────────────
    ltxvaudiovaedecode = _node(
        wf,
        "LTXVAudioVAEDecode",
        "4848",
        audio_vae=lowvramaudiovaeloader.out(0),
        samples=ltxvseparateavlatent_last.out(1),
    )

    ltxvtiledvaedecode = _node(
        wf,
        "LTXVTiledVAEDecode",
        "4995",
        widget_0=2,
        widget_1=2,
        widget_2=6,
        widget_3=False,
        widget_4="auto",
        widget_5="auto",
        latents=ltxvseparateavlatent_last.out(0),
        vae=lowvramcheckpointloader.out(2),
    )

    createvideo = _node(
        wf,
        "CreateVideo",
        "4849",
        widget_0=8,
        fps=primitivefloat_fps.out(0),
        audio=ltxvaudiovaedecode.out(0),
        images=ltxvtiledvaedecode.out(0),
    )

    savevideo = _node(
        wf,
        "SaveVideo",
        "4852",
        filename_prefix="output",
        format="auto",
        codec="auto",
        video=createvideo.out(0),
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)

    # ── register named inputs for worker patching (after finalize_metadata) ──
    wf.register_input("prompt", "2483", "text", value=cliptextencode_prompt.node.inputs.get("text"))
    wf.register_input("negative_prompt", "2612", "text", value=cliptextencode_negative.node.inputs.get("text"))
    wf.register_input("seed_first", "4832", "noise_seed", value=43)
    wf.register_input("seed_last", "4967", "noise_seed", value=42)
    wf.register_input("width", "3059", "width", value=256)
    wf.register_input("height", "3059", "height", value=256)
    wf.register_input("frames", "4988", "value", value=5)
    wf.register_input("fps", "4989", "value", value=8)
    wf.register_input("first_image", "2004", "image", value="example.png")
    wf.register_input("last_image", "2005", "image", value="example.png")
    wf.register_input("model", "3940", "ckpt_name", value="ltx-2.3-22b-dev-fp8.safetensors")

    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs):
    """Create a node, preserving the original node id from the source workflow."""
    from vibecomfy.handles import Handle

    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
