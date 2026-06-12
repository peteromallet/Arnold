"""
gold_template_wan_i2v.py — Hand-crafted pedagogical exemplar
=============================================================

A readable, annotated rewrite of the Wan 2.1 image-to-video ready template.
Based on ``ready_templates/video/wan_i2v.py`` (~115 lines generated).

**Design goals**

* Every section explains *why*, not just *what*.
* Uses the same public inputs, output contract, model assets, and node
  wiring as the generated template.
* Build-only by default — the ``build()`` function compiles and validates
  without queuing GPU work.
* Serves as a clean reference for writing your own templates.

**Template overview**

This template takes a start image and generates a ~2-second video clip
(33 frames at 16 fps) using the Wan 2.1 I2V 14B model.  The pipeline:

  Load models → Load start image → Encode text & vision →
  WanI2V (produces conditioning + latent) → KSampler →
  VAEDecode → CreateVideo → SaveVideo

"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
# We use the generated thin wrappers from vibecomfy.nodes.core.  Each wrapper
# is a function that creates a node in the active workflow (set by the
# ``with new_workflow(...) as wf:`` context manager).
#
# The wrappers accept the *same keyword arguments* as the ComfyUI node
# class, plus an optional ``_id`` for stable naming.  Passing a node-wrapper
# return value as a kwarg to another wrapper auto-wires an edge.

from vibecomfy.templates import (
    InputSpec,          # declares a user-tweakable public input
    ModelAsset,         # download URL + hash + subdir for a model file
    ReadyMetadata,      # bundles capability, inputs, models, provenance
    new_workflow,       # context manager that creates a VibeWorkflow
    ref,                # symbolic reference for InputSpec node binding
)

from vibecomfy.nodes.core import (
    CLIPLoader,         # loads a CLIP text encoder model
    CLIPTextEncode,     # encodes a text prompt into conditioning
    CLIPVisionEncode,   # encodes the start image for Wan's vision input
    CLIPVisionLoader,   # loads the CLIP vision model
    CreateVideo,        # assembles decoded frames into a video container
    KSampler,           # runs the diffusion sampling loop
    LoadImage,          # loads the start image from disk
    ModelSamplingSD3,   # applies SD3-style shift to the diffusion model
    SaveVideo,          # writes the video file to disk
    UNETLoader,         # loads the Wan diffusion (UNet) model
    VAEDecode,          # decodes latent samples into pixel frames
    VAELoader,          # loads the VAE model
    WanImageToVideo,    # Wan 2.1 I2V: produces conditioning + initial latent
)

from vibecomfy.workflow import VibeWorkflow


# =========================================================================
# 1. DEFAULTS — Constants that users can override via public inputs
# =========================================================================
# Every value here has a corresponding PUBLIC_INPUTS entry so the CLI,
# UI, or API caller can change it without editing this file.

DEFAULT_FPS = 16             # frames per second for the output video
DEFAULT_FRAMES = 33          # total frames (~2 seconds at 16 fps)
DEFAULT_PROMPT = (
    "a cute anime girl with massive fennec ears and a big fluffy tail "
    "wearing a maid outfit turning around"
)
# Wan uses a separate negative prompt for guidance
DEFAULT_PROMPT_2 = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，"
    "整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，"
    "画得不好的手部，画得不好的脸部，畸形的，形态畸形的肢体，手指融合，"
    "静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
)
DEFAULT_SEED = 987948718394761
GUIDE_STRENGTH = 6.0         # classifier-free guidance scale


# =========================================================================
# 2. MODEL FILENAMES — Short aliases used throughout the template
# =========================================================================
# These are the ComfyUI-expected filenames.  The framework resolves them
# to the appropriate ``models/<subdir>/<filename>`` path on disk.

MODEL_NAME       = "wan2.1_i2v_480p_14B_fp16.safetensors"   # diffusion model
MODEL_NAME_TEXT  = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"   # text encoder
MODEL_NAME_VAE   = "wan_2.1_vae.safetensors"                  # VAE
MODEL_NAME_VISION = "clip_vision_h.safetensors"               # CLIP vision


# =========================================================================
# 3. MODEL ASSETS — Download metadata for each model file
# =========================================================================
# Each ModelAsset records:
#   url         — canonical download location
#   sha256      — expected hash (validated after download)
#   subdir      — ComfyUI models/ subdirectory
#   hf_revision — HuggingFace commit hash (pinned for reproducibility)
#   size_bytes  — expected file size (for progress / disk checks)

MODELS: dict[str, ModelAsset] = {
    "diffusion_model": ModelAsset(
        url="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors",
        sha256="27988f6b510eb8d5fdd7485671b54897f8683f2bba7a772c5671be21d3491253",
        hf_revision="06e001fc51048fb03433a6fb25334de7836704a5",
        size_bytes=32791377504,
        subdir="diffusion_models",
    ),
    "text_encoder": ModelAsset(
        url="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        sha256="c3355d30191f1f066b26d93fba017ae9809dce6c627dda5f6a66eaa651204f68",
        hf_revision="06e001fc51048fb03433a6fb25334de7836704a5",
        size_bytes=6735906897,
        subdir="text_encoders",
    ),
    "vae": ModelAsset(
        url="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors",
        sha256="2fc39d31359a4b0a64f55876d8ff7fa8d780956ae2cb13463b0223e15148976b",
        hf_revision="06e001fc51048fb03433a6fb25334de7836704a5",
        size_bytes=253815318,
        subdir="vae",
    ),
    "clip_vision": ModelAsset(
        url="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors",
        sha256="64a7ef761bfccbadbaa3da77366aac4185a6c58fa5de5f589b42a65bcc21f161",
        hf_revision="06e001fc51048fb03433a6fb25334de7836704a5",
        size_bytes=1264219396,
        subdir="clip_vision",
    ),
}


# =========================================================================
# 4. PUBLIC INPUTS — User-tweakable knobs
# =========================================================================
# Each InputSpec declares:
#   node    — which node's field to bind (resolved via ref('label'))
#   field   — the node input/widget name to expose
#   default — value used when the user doesn't override
#
# Aliases (e.g. 'negative' and 'negative_prompt' both map to the same field)
# let different UIs use different naming conventions.

PUBLIC_INPUTS: dict[str, InputSpec] = {
    # ── Model ──────────────────────────────────────────────────────────
    "model": InputSpec(
        node=ref("unetloader"), field="unet_name", default=MODEL_NAME,
    ),
    # ── Prompt ─────────────────────────────────────────────────────────
    "prompt": InputSpec(
        node=ref("cliptextencode"), field="text", default=DEFAULT_PROMPT,
    ),
    "negative_prompt": InputSpec(
        node=ref("cliptextencode_2"), field="text", default=DEFAULT_PROMPT_2,
    ),
    "negative": InputSpec(                                          # alias
        node=ref("cliptextencode_2"), field="text", default=DEFAULT_PROMPT_2,
    ),
    # ── Sampling ───────────────────────────────────────────────────────
    "seed": InputSpec(
        node=ref("ksampler"), field="seed", default=DEFAULT_SEED,
    ),
    "steps": InputSpec(
        node=ref("ksampler"), field="steps", default=20,
    ),
    "cfg": InputSpec(
        node=ref("ksampler"), field="cfg", default=GUIDE_STRENGTH,
    ),
    "sampler_name": InputSpec(
        node=ref("ksampler"), field="sampler_name", default="uni_pc",
    ),
    # ── Dimensions ─────────────────────────────────────────────────────
    "width": InputSpec(
        node=ref("positive"), field="width", default=512,
    ),
    "height": InputSpec(
        node=ref("positive"), field="height", default=512,
    ),
    "length": InputSpec(
        node=ref("positive"), field="length", default=DEFAULT_FRAMES,
    ),
    "frames": InputSpec(                                             # alias
        node=ref("positive"), field="length", default=DEFAULT_FRAMES,
    ),
    # ── Input image ────────────────────────────────────────────────────
    "start_image": InputSpec(
        node=ref("image"), field="image",
        default="image_to_video_wan_start_image.png",
    ),
    "input_image": InputSpec(                                        # alias
        node=ref("image"), field="image",
        default="image_to_video_wan_start_image.png",
    ),
    "image": InputSpec(                                              # alias
        node=ref("image"), field="image",
        default="image_to_video_wan_start_image.png",
    ),
    # ── Output ─────────────────────────────────────────────────────────
    "output_fps": InputSpec(
        node=ref("createvideo"), field="fps", default=DEFAULT_FPS,
    ),
    "fps": InputSpec(                                                # alias
        node=ref("createvideo"), field="fps", default=DEFAULT_FPS,
    ),
}


# =========================================================================
# 5. METADATA — Template identity and provenance
# =========================================================================
# ReadyMetadata.build() assembles the template's public contract:
#   capability      — high-level tag: 'image_to_video'
#   inputs          — the PUBLIC_INPUTS dict above
#   models          — the MODELS dict above
#   output_prefix   — filesystem prefix for output files
#   provenance      — records where the workflow design came from

READY_METADATA = ReadyMetadata.build(
    capability="image_to_video",
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix="video/ComfyUI",
    provenance={"source_workflow": "ready_templates/sources/official/video/wan_i2v.json"},
)


# =========================================================================
# 6. BUILD — Assemble the workflow graph
# =========================================================================
# This is the heart of the template.  ``new_workflow(READY_METADATA)``
# activates a ContextVar; every wrapper call inside the ``with`` block
# implicitly binds to that workflow.
#
# Node naming convention: each variable name matches the ``ref('name')``
# label in PUBLIC_INPUTS, so InputSpec resolution works automatically.


def build() -> VibeWorkflow:
    """Build the Wan 2.1 I2V workflow graph (build-only, no GPU)."""

    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # ── 6a. Model loaders ──────────────────────────────────────────
        # Each loader creates a node that points ComfyUI at a model file.
        # The framework resolves filenames → full paths via models/ subdirs.

        unetloader = UNETLoader(unet_name=MODEL_NAME)
        """Diffusion model (Wan 2.1 I2V 14B fp16).  Outputs the UNet + CLIP
        vision components.  We only use the model output (index 0)."""

        cliploader = CLIPLoader(clip_name=MODEL_NAME_TEXT, type_="wan")
        """UMT5-XXL text encoder.  ``type_='wan'`` selects the Wan-specific
        CLIP loading path."""

        vaeloader = VAELoader(vae_name=MODEL_NAME_VAE)
        """Wan 2.1 VAE.  Used twice: once by WanImageToVideo (to encode the
        start image) and once by VAEDecode (to decode latents → pixels)."""

        clipvisionloader = CLIPVisionLoader(clip_name=MODEL_NAME_VISION)
        """CLIP ViT-H vision model.  Encodes the start image into a vision
        embedding that WanImageToVideo consumes."""

        # ── 6b. Start image ────────────────────────────────────────────
        # LoadImage returns a tuple: (image_handle, mask_handle).
        # The mask is unused but the tuple unpacking is required because
        # LoadImage always produces two outputs.

        image, _mask = LoadImage(image="image_to_video_wan_start_image.png")

        # ── 6c. Conditioning ───────────────────────────────────────────
        # Two CLIP text encodes: positive prompt + negative prompt.
        # Both share the same CLIP loader (cliploader).

        cliptextencode = CLIPTextEncode(
            text=DEFAULT_PROMPT,
            clip=cliploader,
        )

        cliptextencode_2 = CLIPTextEncode(
            text=DEFAULT_PROMPT_2,
            clip=cliploader,
        )

        # CLIP vision encode: converts the start image to a vision embedding.
        clipvisionencode = CLIPVisionEncode(
            crop="none",
            clip_vision=clipvisionloader,
            image=image,
        )

        # ── 6d. Model sampling shift ───────────────────────────────────
        # Wan 2.1 uses SD3-style timestep shifting.  ModelSamplingSD3
        # wraps the diffusion model with the appropriate schedule.

        modelsamplingsd3 = ModelSamplingSD3(
            shift=8,
            model=unetloader,
        )

        # ── 6e. WanImageToVideo (the core) ─────────────────────────────
        # This is the Wan 2.1-specific node.  It takes the start image
        # (via vae), text conditioning (positive + negative), and vision
        # embedding, and produces:
        #   positive  — conditioning for the sampler
        #   negative  — negative conditioning for the sampler
        #   latent    — initial noisy latent for the diffusion process
        #
        # Tuple unpacking matches the node's three outputs in order.

        positive, negative, latent = WanImageToVideo(
            height=512,
            length=DEFAULT_FRAMES,
            width=512,
            clip_vision_output=clipvisionencode,
            negative=cliptextencode_2,
            positive=cliptextencode,
            start_image=image,
            vae=vaeloader,
        )

        # ── 6f. Sampling ───────────────────────────────────────────────
        # KSampler runs the diffusion denoising loop.  It takes:
        #   model        — the shifted UNet
        #   positive     — conditioning from WanImageToVideo
        #   negative     — negative conditioning
        #   latent_image — the initial latent
        #
        # Output: a denoised latent ready for decoding.

        ksampler = KSampler(
            seed=DEFAULT_SEED,
            steps=20,
            cfg=GUIDE_STRENGTH,
            sampler_name="uni_pc",
            latent_image=latent,
            model=modelsamplingsd3,
            negative=negative,
            positive=positive,
        )

        # ── 6g. Decode ─────────────────────────────────────────────────
        # VAEDecode converts the denoised latent into pixel-space frames.
        # CreateVideo assembles those frames into a video container at the
        # target FPS.

        vaedecode = VAEDecode(
            samples=ksampler,
            vae=vaeloader,
        )

        createvideo = CreateVideo(
            fps=DEFAULT_FPS,
            images=vaedecode,
        )

        # ── 6h. Save ───────────────────────────────────────────────────
        # SaveVideo writes the video to disk under output_prefix.

        savevideo = SaveVideo(video=createvideo)

        # ── 6i. Finalize ───────────────────────────────────────────────
        # wf.finalize() binds the public inputs to their target nodes,
        # registers the output contract, and returns the completed workflow.
        # This is a build-only call — no GPU work is queued.

        return wf.finalize(
            PUBLIC_INPUTS,
            output_type="SaveVideo",
            name="video",
            artifact_kind="video",
            mime_type="video/mp4",
            expected_cardinality="one",
        )


# =========================================================================
# 7. Build-only validation (no GPU, no network)
# =========================================================================
# When run directly, this module builds the workflow and validates it
# by compiling to API JSON.  No model downloads or GPU inference occur.

if __name__ == "__main__":
    wf = build()
    print(f"Workflow: {wf.id}")
    print(f"  Nodes:  {len(wf.nodes)}")
    print(f"  Edges:  {len(wf.edges)}")
    print(f"  Inputs: {len(wf.inputs)} public")
    print(f"  Models: {len(MODELS)} registered")

    # Compile to ComfyUI API JSON to verify graph integrity
    api = wf.compile("api")
    print(f"  API nodes: {len(api)}")
    print("✓ Gold template built and validated — no GPU required.")
