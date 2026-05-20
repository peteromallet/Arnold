# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import ImageScaleBy
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine


MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    capability='video_enhance',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-VideoHelperSuite']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}},
    approach='VHS_LoadVideo -> ImageScaleBy -> VHS_VideoCombine, avoiding gated model downloads.',
    runtime_note='Frame interpolation is intentionally not enabled in the default app-active route because the prior GIMM-VFI asset is license-gated without HF_TOKEN.',
    provenance={'source_workflow': 'ready_templates/video/basic_video_enhance.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        vhs_loadvideo = VHS_LoadVideo(
            video='video_enhance_input.mp4',
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
        )

        imagescaleby = ImageScaleBy(
            upscale_method='lanczos',
            scale_by=2.0,
            image=vhs_loadvideo.out('IMAGE'),
        )

        vhs_videocombine = VHS_VideoCombine(
            frame_rate=16,
            filename_prefix='video-enhance',
            format='video/h264-mp4',
            crf=19,
            pix_fmt='yuv420p',
            save_metadata=True,
            trim_to_audio=False,
            audio=vhs_loadvideo.out('AUDIO'),
            images=imagescaleby,
        )

        wf._set_id_map({name: node.node.id for name, node in (('vhs_loadvideo', vhs_loadvideo), ('imagescaleby', imagescaleby), ('vhs_videocombine', vhs_videocombine))})

        return wf.finalize(PUBLIC_INPUTS, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='video-enhance')

