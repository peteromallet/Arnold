# vibecomfy: manual
"""Z-Image Turbo image-to-image template for Reigh parity."""
from __future__ import annotations

from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


DEFAULT_PROMPT = "A compact red cube on a clean white tabletop, product-photo lighting."
DEFAULT_NEGATIVE = ""

READY_METADATA = {
    "model_assets": [
        {
            "name": "ZImageTurbo_bf16.safetensors",
            "url": "https://huggingface.co/DeepBeepMeep/Z-Image/resolve/main/ZImageTurbo_bf16.safetensors",
            "directory": "diffusion_models",
        },
        {
            "name": "qwen_3_4b.safetensors",
            "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
            "directory": "text_encoders",
        },
        {
            "name": "ae.safetensors",
            "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
            "directory": "vae",
        },
    ],
    "ready_template": "image/z_image_img2img",
    "workflow_template": "z_image_img2img",
    "capability": "image_to_image",
    "source_role": "reigh_parity_manual_template",
    "source_workflow": "Wan2GP/defaults/z_image_img2img.json",
    "coverage_tier": "production_parity_candidate",
    "approach": "Z-Image Turbo img2img via VAEEncode init latent and KSampler denoise strength",
    "runtime_note": "Intended to match Reigh z_image_turbo_i2i production semantics.",
    "smoke_resolution": "1024x1024",
}

READY_REQUIREMENTS = {"models": READY_METADATA["model_assets"], "custom_nodes": []}


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(id=READY_METADATA["ready_template"], path=__file__, source_type="ready_template"),
    )

    input_image = wf.node("LoadImage", image="image_z_image_img2img_input.png")
    unet = wf.node("UNETLoader", unet_name="ZImageTurbo_bf16.safetensors", weight_dtype="default")
    clip = wf.node("CLIPLoader", clip_name="qwen_3_4b.safetensors", type="lumina2", device="default")
    vae = wf.node("VAELoader", vae_name="ae.safetensors")
    model = wf.node("ModelSamplingAuraFlow", model=unet.out(0), shift=3)
    positive = wf.node("CLIPTextEncode", clip=clip.out(0), text=DEFAULT_PROMPT)
    negative = wf.node("CLIPTextEncode", clip=clip.out(0), text=DEFAULT_NEGATIVE)
    resized = wf.node(
        "ImageScale",
        image=input_image.out(0),
        upscale_method="lanczos",
        width=1024,
        height=1024,
        crop="center",
    )
    latent = wf.node("VAEEncode", pixels=resized.out(0), vae=vae.out(0))
    sampled = wf.node(
        "KSampler",
        model=model.out(0),
        positive=positive.out(0),
        negative=negative.out(0),
        latent_image=latent.out(0),
        seed=770044821593082,
        steps=12,
        cfg=0.0,
        sampler_name="res_multistep",
        scheduler="simple",
        denoise=0.7,
    )
    decoded = wf.node("VAEDecode", samples=sampled.out(0), vae=vae.out(0))
    wf.node("SaveImage", images=decoded.out(0), filename_prefix="z-image-img2img")

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf

