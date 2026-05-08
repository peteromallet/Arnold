# vibecomfy: manual
"""Public-asset video enhancement template for Reigh video_enhance."""
from __future__ import annotations

from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


READY_METADATA = {
    "model_assets": [],
    "unbound_inputs": {
        "video": "1.video",
        "scale_factor": "4.scale_by",
    },
    "ready_template": "video/basic_video_enhance",
    "workflow_template": "basic_video_enhance",
    "capability": "video_enhance",
    "source_role": "reigh_parity_manual_template",
    "source_workflow": "ComfyUI core + VideoHelperSuite public-node baseline",
    "coverage_tier": "production_baseline",
    "approach": "VHS_LoadVideo -> ImageScaleBy -> VHS_VideoCombine, avoiding gated model downloads.",
    "runtime_note": "Frame interpolation is intentionally not enabled in the default app-active route because the prior GIMM-VFI asset is license-gated without HF_TOKEN.",
}

READY_REQUIREMENTS = {
    "models": READY_METADATA["model_assets"],
    "custom_nodes": ["ComfyUI-VideoHelperSuite"],
}


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(id=READY_METADATA["ready_template"], path=__file__, source_type="ready_template"),
    )
    video = _node(
        wf,
        "VHS_LoadVideo",
        "1",
        video="video_enhance_input.mp4",
        force_rate=0,
        custom_width=0,
        custom_height=0,
        frame_load_cap=0,
        skip_first_frames=0,
        select_every_nth=1,
    )
    upscaled = _node(
        wf,
        "ImageScaleBy",
        "4",
        image=video.out(0),
        upscale_method="lanczos",
        scale_by=2.0,
    )
    _node(
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

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, **kwargs):
    builder = wf.node(class_type, **kwargs)
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
