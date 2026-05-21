# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, ref
from vibecomfy.nodes.core import ImageScaleBy, LoadImage, SaveImage


PUBLIC_INPUTS = {
    'image': InputSpec(node=ref('image'), field='image', default='image_upscale_input.png'),
    'input_image': InputSpec(node=ref('image'), field='image', default='image_upscale_input.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_upscale',
    inputs=PUBLIC_INPUTS,
    approach='Core ComfyUI lanczos ImageScaleBy; maps Reigh image-upscale parameters without external API calls.',
    runtime_note='This preserves the task contract but is not FlashVSR/RealESRGAN model super-resolution.',
    provenance={'source_workflow': 'ready_templates/image/basic_image_upscale.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        image, mask = LoadImage(image='image_upscale_input.png')
        imagescaleby = ImageScaleBy(upscale_method='lanczos', scale_by=2.0, image=image)
        saveimage = SaveImage(filename_prefix='image-upscale', images=imagescaleby)

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='image-upscale')

