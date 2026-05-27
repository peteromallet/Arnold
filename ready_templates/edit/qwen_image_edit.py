# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGNorm, CLIPLoader, ComfySwitchNode, ImageScaleToTotalPixels, KSampler, LoadImage, LoraLoaderModelOnly, ModelSamplingAuraFlow, SaveImage, TextEncodeQwenImageEdit, UNETLoader, VAEDecode, VAEEncode, VAELoader


CLIP_NAME = 'qwen_2.5_vl_7b_fp8_scaled.safetensors'
DEFAULT_PROMPT = 'Remove all UI text elements from the image. Keep the feeling that the characters and scene are in water. Also, remove the green UI elements at the bottom.'
DEFAULT_SEED = 344147753686358
GUIDE_STRENGTH = 1
LORA_NAME = 'Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors'
UNET_NAME = 'qwen_image_edit_fp8_e4m3fn.safetensors'
VAE_NAME = 'qwen_image_vae.safetensors'


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='78', field='image', default='image_qwen_image_edit_input_image.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='102:3', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors', 'euler', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_image_edit_fp8_e4m3fn.safetensors', 'qwen_image_vae.safetensors']},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/qwen_image_edit.json', 'source_id': 'qwen_image_edit', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/qwen_image_edit.json', 'output_mode': 'ready_template', 'ready_id': 'edit/qwen_image_edit'},
)

# === Subgraph functions ===

def qwen_image_edit(
    *,
    image,
    prompt: str,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    lora_name: str,
    enable_turbo_mode: bool,
):
    """Qwen-Image-Edit - single-image variant.

    Materialized from subgraph 74a8e1e2-9cb8-4112-978e-06ce1b5793f1 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/edit/qwen_image_edit.json.
    # vibecomfy source hash: sha256:b7fc773a3b338bd4ce58cdc36f425635b40eb71bc0eb73b9f007ec3160c52b36
    Inner nodes: VAELoader, TextEncodeQwenImageEditx2, CFGNorm, ModelSamplingAuraFlow, VAEDecode, CLIPLoader, VAEEncode, MarkdownNote, LoraLoaderModelOnly, UNETLoader, KSampler, ComfySwitchNodex3.
    """

    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='qwen_image', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    markdownnote = raw_call('MarkdownNote', '97',
        unused_widget_0='You can test and find the best setting by yourself. The following table is for reference.\n\n| Model            | Steps | CFG |\n|---------------------|---------------|---------------|\n| Offical             | 50               | 4.0               \n| comfy             | 20                | 2.5               |\n| fp8_e4m3fn + 4steps LoRA    | 4               | 1.0               |\n',
    )

    comfyswitchnode_2 = ComfySwitchNode(switch=False)
    comfyswitchnode_3 = ComfySwitchNode(switch=False)

    textencodeqwenimageedit = TextEncodeQwenImageEdit(
        prompt=prompt,
        clip=cliploader,
        image=image,
        vae=vaeloader,
    )

    textencodeqwenimageedit_2 = TextEncodeQwenImageEdit(
        prompt='',
        clip=cliploader,
        image=image,
        vae=vaeloader,
    )

    vaeencode = VAEEncode(pixels=image, vae=vaeloader)
    loraloadermodelonly = LoraLoaderModelOnly(lora_name=lora_name, model=unetloader)

    comfyswitchnode = ComfySwitchNode(
        switch=False,
        on_false=unetloader,
        on_true=loraloadermodelonly,
    )

    modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=comfyswitchnode)
    cfgnorm = CFGNorm(widget_0=1, model=modelsamplingauraflow)

    ksampler = KSampler(
        seed=344147753686358,
        sampler_name='euler',
        unused_widget_1='randomize',
        steps=comfyswitchnode_3,
        cfg=comfyswitchnode_2,
        latent_image=vaeencode,
        model=cfgnorm,
        negative=textencodeqwenimageedit_2,
        positive=textencodeqwenimageedit,
    )

    vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

    return vaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, mask = LoadImage(image='image_qwen_image_edit_input_image.png')

    # Loaders
    unetloader = UNETLoader(unet_name=UNET_NAME)
    cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='qwen_image')
    vaeloader = VAELoader(vae_name=VAE_NAME)

    comfyswitchnode_2 = ComfySwitchNode(
        switch=['102:111', 0],
        on_false=['102:107', 0],
        on_true=['102:105', 0],
    )

    comfyswitchnode_3 = ComfySwitchNode(
        switch=['102:111', 0],
        on_false=['102:106', 0],
        on_true=['102:103', 0],
    )

    imagescaletototalpixels = ImageScaleToTotalPixels(
        upscale_method='lanczos',
        megapixels=1.5,
        image=image,
    )

    textencodeqwenimageedit = TextEncodeQwenImageEdit(
        prompt=DEFAULT_PROMPT,
        clip=cliploader,
        image=image,
        vae=vaeloader,
    )

    textencodeqwenimageedit_2 = TextEncodeQwenImageEdit(
        prompt='',
        clip=cliploader,
        image=image,
        vae=vaeloader,
    )

    vaeencode = VAEEncode(pixels=image, vae=vaeloader)
    loraloadermodelonly = LoraLoaderModelOnly(lora_name=LORA_NAME, model=unetloader)

    comfyswitchnode = ComfySwitchNode(
        switch=['102:111', 0],
        on_false=unetloader,
        on_true=loraloadermodelonly,
    )

    modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=comfyswitchnode)
    cfgnorm = CFGNorm(model=modelsamplingauraflow)

    # Sampling
    ksampler = KSampler(
        seed=DEFAULT_SEED,
        sampler_name='euler',
        steps=comfyswitchnode_3,
        cfg=comfyswitchnode_2,
        latent_image=vaeencode,
        model=cfgnorm,
        negative=textencodeqwenimageedit_2,
        positive=textencodeqwenimageedit,
    )

    # Decode
    vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

    # Outputs
    saveimage = SaveImage(images=vaedecode)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='ComfyUI')

