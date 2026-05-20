# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import ImageScaleBy, LoadImage, SaveImage


MODELS = {}

PUBLIC_INPUTS = {
    'image': InputSpec(node=ref('loadimage'), field='image', default='image_upscale_input.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='image_upscale_input.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_upscale',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    approach='Core ComfyUI lanczos ImageScaleBy; maps Reigh image-upscale parameters without external API calls.',
    runtime_note='This preserves the task contract but is not FlashVSR/RealESRGAN model super-resolution.',
    provenance={'source_workflow': 'ready_templates/image/basic_image_upscale.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadimage = LoadImage(
            image='image_upscale_input.png',
            _outputs=('IMAGE', 'MASK'),
        )

        imagescaleby = ImageScaleBy(
            upscale_method='lanczos',
            scale_by=2.0,
            image=loadimage.out('IMAGE'),
        )

        saveimage = SaveImage(filename_prefix='image-upscale', images=imagescaleby)

        wf._set_id_map({name: node.node.id for name, node in (('loadimage', loadimage), ('imagescaleby', imagescaleby), ('saveimage', saveimage))})

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='image-upscale')

