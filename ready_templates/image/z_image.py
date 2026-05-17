# vibecomfy: manual — hand-authored reference, do not regenerate
"""z_image text-to-image template — hand-authored real Python.

Sample of what a fully-converted ready_template should look like:
  * No UUID class types. The original z_image opaque subgraph
    (`9b9009e4-2d3d-445f-9be5-6063f465757e` in workflow_corpus/official/image/
    z_image.json :: definitions.subgraphs[0]) is inlined into named ComfyUI
    nodes so HiddenSwitch / vanilla ComfyUI can execute it without ever
    seeing the subgraph wrapper.
  * No `widget_0`/`widget_1`/... position-indexed widget names. Real input
    names from the node schema (`unet_name`, `text`, `cfg`, ...) — these are
    what ComfyUI's API expects, what shows up in /object_info, and what an
    author actually wants to read.
  * No NODES tuple of ('id', 'type', {...}) JSON-flavoured Python. Just bound
    variables wired through `.out(slot)` handles, top-to-bottom data flow.
  * Single source of truth: nothing in here reaches back into
    `workflow_corpus/*.json` at runtime.

Pipeline:
    UNETLoader → ModelSamplingAuraFlow ─┐
    CLIPLoader ─→ CLIPTextEncode (pos) ─┤
                ─→ CLIPTextEncode (neg) ─┼→ KSampler → VAEDecode → SaveImage
    EmptySD3LatentImage ────────────────┤              ↑
    VAELoader ───────────────────────────────────────── ┘
"""
from __future__ import annotations

from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_input, bind_output
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


NODE_POSITIVE_PROMPT = "5"
NODE_NEGATIVE_PROMPT = "6"
NODE_LATENT = "7"
NODE_SAMPLER = "8"
NODE_IMAGE_OUTPUT = "10"
IMAGE_OUTPUT_NAME = "image"
IMAGE_OUTPUT_PREFIX = "z-image"
IMAGE_OUTPUT_MIME = "image/png"

DEFAULT_PROMPT = (
    "A fashion photography work full of surreal romanticism, using a low-angle upward shooting "
    "composition, with a clear light blue sky as the background, and the visual focus concentrated "
    "on the fantasy blue vegetation and the model walking through it.\n"
    "\n"
    "The vegetation in the picture is processed into varying shades of blue, from light ice blue to "
    "deep cobalt blue. The textures of the leaves and branches are delicate and realistic. The warm "
    "brown tree trunks form a sharp contrast with the cool blue leaves, resembling a dreamy forest "
    "from another world. An African-American model wearing a yellow and white vertical striped long "
    "dress walks slowly on the sand. The warm tones of the dress echo with the surrounding cool blue "
    "vegetation. The noon sun casts clear shadows on the sand, enhancing the sense of space and "
    "reality in the picture.\n"
    "\n"
    "The entire scene, with its clean and transparent colors and fantasy settings, not only exudes "
    "the vastness of the natural wilderness but also presents a quiet and poetic high-fashion sense "
    "due to the surreal vegetation."
)


READY_METADATA = {
    "model_assets": [
        {
            "name": "qwen_3_4b.safetensors",
            "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
            "subdir": "text_encoders",
        },
        {
            "name": "ae.safetensors",
            "url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
            "subdir": "vae",
        },
        {
            "name": "z_image_bf16.safetensors",
            "url": "https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/diffusion_models/z_image_bf16.safetensors",
            "subdir": "diffusion_models",
        },
    ],
    "unbound_inputs": {"seed": 1732},
    "ready_template": "image/z_image",
    "workflow_template": "z_image",
    "capability": "text_to_image",
    "source_role": "authored_ready_python_template",
    "source_workflow": "workflow_corpus/official/image/z_image.json",
    "coverage_tier": "required",
    "approach": None,
    "runtime_note": None,
    "discord_signal": None,
}


READY_REQUIREMENTS = {
    "models": READY_METADATA["model_assets"],
    "custom_nodes": [],
}


def build() -> VibeWorkflow:
    """Build the z_image text-to-image workflow."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    # Models
    unet = wf.node(
        "UNETLoader",
        unet_name="z_image_bf16.safetensors",
        weight_dtype="default",
    )
    clip = wf.node(
        "CLIPLoader",
        clip_name="qwen_3_4b.safetensors",
        type="lumina2",
        device="default",
    )
    vae = wf.node("VAELoader", vae_name="ae.safetensors")

    # Aura Flow shift schedule applied on top of the loaded UNet
    sampling_model = wf.node(
        "ModelSamplingAuraFlow",
        model=unet.out(0),
        shift=3,
    )

    # Conditioning — real text= input, no widget_0
    positive = wf.node(
        "CLIPTextEncode",
        clip=clip.out(0),
        text=DEFAULT_PROMPT,
    )
    negative = wf.node(
        "CLIPTextEncode",
        clip=clip.out(0),
        text="",
    )

    # Empty starting latent at the requested resolution
    latent = wf.node(
        "EmptySD3LatentImage",
        width=1024,
        height=1024,
        batch_size=1,
    )

    # Sampler
    sampled = wf.node(
        "KSampler",
        model=sampling_model.out(0),
        positive=positive.out(0),
        negative=negative.out(0),
        latent_image=latent.out(0),
        seed=770044821593082,
        steps=25,
        cfg=4.0,
        sampler_name="res_multistep",
        scheduler="simple",
        denoise=1.0,
    )

    # Decode + save
    decoded = wf.node("VAEDecode", samples=sampled.out(0), vae=vae.out(0))
    wf.node(
        "SaveImage",
        images=decoded.out(0),
        filename_prefix=IMAGE_OUTPUT_PREFIX,
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    bind_input(
        wf,
        "prompt",
        "5",
        "text",
        type="STRING",
        required=True,
        media_semantics="text",
    )
    bind_input(
        wf,
        "negative_prompt",
        "6",
        "text",
        type="STRING",
        aliases=["negative"],
        media_semantics="text",
    )
    bind_input(wf, "seed", "8", "seed", type="INT")
    bind_input(wf, "steps", "8", "steps", type="INT")
    bind_input(wf, "width", "7", "width", type="INT")
    bind_input(wf, "height", "7", "height", type="INT")
    bind_output(
        wf,
        "10",
        output_type="SaveImage",
        name="image",
        artifact_kind="image",
        mime_type="image/png",
        filename_prefix="z-image",
        expected_cardinality="one",
    )
    return wf
