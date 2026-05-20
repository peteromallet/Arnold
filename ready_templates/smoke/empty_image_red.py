# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import EmptyImage, SaveImage


MODELS = {}

PUBLIC_INPUTS = {
    'width': InputSpec(node=ref('emptyimage'), field='width', default=64),
    'height': InputSpec(node=ref('emptyimage'), field='height', default=64),
}

READY_METADATA = ReadyMetadata.build(
    capability='runtime_smoke',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    approach='minimal Python ready template for cloud/runtime/artifact validation',
    runtime_note='No model assets; use corpus/model matrices for production model coverage.',
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        emptyimage = EmptyImage(
            _id='1',
            color=16711680,
            height=64,
            width=64,
        )
        wf.metadata.setdefault('id_map', {})['emptyimage'] = emptyimage.node.id

        saveimage = SaveImage(
            _id='2',
            filename_prefix='vibecomfy_ready_smoke_red',
            images=emptyimage,
        )
        wf.metadata.setdefault('id_map', {})['saveimage'] = saveimage.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='vibecomfy_ready_smoke_red')

