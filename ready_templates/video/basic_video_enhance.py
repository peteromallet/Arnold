# vibecomfy: manual
"""Public-asset video enhancement template for Reigh video_enhance.

Output: unknown.

Source:  ComfyUI core + VideoHelperSuite public-node baseline

Packs:   ComfyUI-VideoHelperSuite
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='basic_video_enhance',
    capability='video_enhance',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-VideoHelperSuite']},
    provenance={'approach': 'VHS_LoadVideo -> ImageScaleBy -> VHS_VideoCombine, avoiding gated model downloads.', 'source_role': 'reigh_parity_manual_template', 'source_workflow': 'ComfyUI core + VideoHelperSuite public-node baseline'},
    coverage_tier='production_baseline',
    runtime_note='Frame interpolation is intentionally not enabled in the default app-active route because the prior GIMM-VFI asset is license-gated without HF_TOKEN.',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    wf = new_workflow(READY_METADATA, source_path=__file__)
    # ════ LOADERS ════
    video = node(
        wf,
        "VHS_LoadVideo",
        "1",
        video='video_enhance_input.mp4',
        force_rate=0,
        custom_width=0,
        custom_height=0,
        frame_load_cap=0,
        skip_first_frames=0,
        select_every_nth=1,
    )
    # ════ IMAGE PREP ════
    upscaled = node(
        wf,
        "ImageScaleBy",
        "4",
        image=video.out(0),
        upscale_method="lanczos",
        scale_by=2.0,
    )
    node(
        wf,
        "VHS_VideoCombine",
        "5",
        images=upscaled.out(0),
        audio=video.out(2),
        frame_rate=16,
        loop_count=0,
        filename_prefix="video-enhance",
        format="video/h264-mp4",
        pix_fmt="yuv420p",
        crf=19,
        save_metadata=True,
        trim_to_audio=False,
        pingpong=False,
        save_output=True,
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

