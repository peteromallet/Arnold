# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, ComfySwitchNode, EmptySD3LatentImage, KSampler, LoraLoaderModelOnly, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAELoader


CLIP_NAME = 'qwen_2.5_vl_7b_fp8_scaled.safetensors'
DEFAULT_PROMPT = 'Urban alleyway at dusk. Tall, statuesque high-fashion model striding elegantly, mid distant full body shot from an angular perspective, cinematic/editorial with bold contrasts and tactile materials. They wear a rose-gold metallic trench coat with deconstructed elements over a black long-sleeved turtleneck with subtle texture; paired with forest-green pleated pants with raw hems and a soft texture. Long braided dark hair, medium complexion. They carry a vibrant yellow designer handbag with geometric details and a structured silhouette. White architectural sneakers with bold geometric cutouts. Bold, high-contrast, tactile, urban-grit meets high-fashion impact, extreme clarity, extreme layering, post-processing with transparent light-transmitting ultra-smooth high-definition film effect, removing all noise and grain, removing all blur, removing all vintage feel, removing all roughness, drawn with 32K pixel precision, unparalleled fine line drawing of every single detail, the entire image like a brand new photograph, photorealistic\n'
DEFAULT_PROMPT_2 = '低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲'
DEFAULT_SEED = 464857551335368
LORA_NAME = 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors'
UNET_NAME = 'qwen_image_2512_fp8_e4m3fn.safetensors'
VAE_NAME = 'qwen_image_vae.safetensors'


PUBLIC_INPUT_METADATA = {
    'model': InputSpec(node='3', field='unet_name', default=UNET_NAME),
    'prompt': InputSpec(node='8', field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node='12', field='seed', default=DEFAULT_SEED),
    'width': InputSpec(node='4', field='width', default=1328),
    'height': InputSpec(node='4', field='height', default=1328),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors', 'euler', 'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_image_2512_fp8_e4m3fn.safetensors', 'qwen_image_vae.safetensors']},
    source_path='workflow_corpus/official/image/qwen_image_2512.json',
    source_id='qwen_image_2512',
    source_type='api',
    source_workflow_path='workflow_corpus/official/image/qwen_image_2512.json',
    source_hash='sha256:1825da34e2124e9d6d54c8fbcf5b9f1ab901d2fe39be03b358130bb30f06fbdb',
    output_mode='ready_template',
    ready_id='image/qwen_image_2512',
    provenance={'source_path': 'workflow_corpus/official/image/qwen_image_2512.json', 'source_id': 'qwen_image_2512', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/official/image/qwen_image_2512.json', 'source_hash': 'sha256:1825da34e2124e9d6d54c8fbcf5b9f1ab901d2fe39be03b358130bb30f06fbdb', 'output_mode': 'ready_template', 'ready_id': 'image/qwen_image_2512', 'source_workflow': 'workflow_corpus/official/image/qwen_image_2512.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Loaders
    cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='qwen_image')
    vaeloader = VAELoader(vae_name=VAE_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME)

    # Sampling
    emptysd3latentimage = EmptySD3LatentImage(width=1328, height=1328)

    comfyswitchnode = ComfySwitchNode(
        switch=['238:229', 0],
        on_false=['238:224', 0],
        on_true=['238:225', 0],
    )

    comfyswitchnode_2 = ComfySwitchNode(
        switch=['238:229', 0],
        on_false=['238:223', 0],
        on_true=['238:218', 0],
    )

    loraloadermodelonly = LoraLoaderModelOnly(lora_name=LORA_NAME, model=unetloader)

    # Conditioning
    positive = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)
    negative = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader)

    comfyswitchnode_3 = ComfySwitchNode(
        switch=['238:229', 0],
        on_false=unetloader,
        on_true=loraloadermodelonly,
    )

    modelsamplingauraflow = ModelSamplingAuraFlow(
        shift=3.1000000000000005,
        model=comfyswitchnode_3,
    )

    ksampler = KSampler(
        seed=DEFAULT_SEED,
        sampler_name='euler',
        steps=comfyswitchnode,
        cfg=comfyswitchnode_2,
        latent_image=emptysd3latentimage,
        model=modelsamplingauraflow,
        negative=negative,
        positive=positive,
    )

    # Decode
    vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

    # Outputs
    saveimage = SaveImage(filename_prefix='Qwen-Image-2512', images=vaedecode)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Qwen-Image-2512')

