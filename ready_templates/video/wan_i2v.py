# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CLIPVisionEncode, CLIPVisionLoader, CreateVideo, KSampler, LoadImage, ModelSamplingSD3, SaveVideo, UNETLoader, VAEDecode, VAELoader, WanImageToVideo


DEFAULT_FPS = 16
DEFAULT_FRAMES = 33
DEFAULT_PROMPT = 'a cute anime girl with massive fennec ears and a big fluffy tail wearing a maid outfit turning around'
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 987948718394761
GUIDE_STRENGTH = 6
MODEL_NAME = 'wan2.1_i2v_480p_14B_fp16.safetensors'
MODEL_NAME_2 = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
MODEL_NAME_3 = 'wan_2.1_vae.safetensors'
MODEL_NAME_4 = 'clip_vision_h.safetensors'


MODELS = {
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors', sha256='27988f6b510eb8d5fdd7485671b54897f8683f2bba7a772c5671be21d3491253', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=32791377504, subdir='diffusion_models'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors', sha256='c3355d30191f1f066b26d93fba017ae9809dce6c627dda5f6a66eaa651204f68', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=6735906897, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors', sha256='2fc39d31359a4b0a64f55876d8ff7fa8d780956ae2cb13463b0223e15148976b', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=253815318, subdir='vae'),
    'clip_vision': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors', sha256='64a7ef761bfccbadbaa3da77366aac4185a6c58fa5de5f589b42a65bcc21f161', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=1264219396, subdir='clip_vision'),
}


PUBLIC_INPUT_METADATA = {
    'model': InputSpec(node='1', field='unet_name', default=MODEL_NAME),
    'prompt': InputSpec(node='6', field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node='11', field='seed', default=DEFAULT_SEED),
    'steps': InputSpec(node='11', field='steps', default=20),
    'negative_prompt': InputSpec(node='7', field='text', default=DEFAULT_PROMPT_2),
    'negative': InputSpec(node='7', field='text', default=DEFAULT_PROMPT_2),
    'output_fps': InputSpec(node='13', field='fps', default=DEFAULT_FPS),
    'fps': InputSpec(node='13', field='fps', default=DEFAULT_FPS),
    'width': InputSpec(node='10', field='width', default=512),
    'height': InputSpec(node='10', field='height', default=512),
    'length': InputSpec(node='10', field='length', default=DEFAULT_FRAMES),
    'cfg': InputSpec(node='11', field='cfg', default=GUIDE_STRENGTH),
    'sampler_name': InputSpec(node='11', field='sampler_name', default='uni_pc'),
    'start_image': InputSpec(node='5', field='image', default='image_to_video_wan_start_image.png'),
    'input_image': InputSpec(node='5', field='image', default='image_to_video_wan_start_image.png'),
    'image': InputSpec(node='5', field='image', default='image_to_video_wan_start_image.png'),
    'frames': InputSpec(node='10', field='length', default=DEFAULT_FRAMES),
}


def PUBLIC_INPUTS(**nodes):
    unetloader = nodes['unetloader']
    cliptextencode = nodes['cliptextencode']
    ksampler = nodes['ksampler']
    ksampler = nodes['ksampler']
    cliptextencode_2 = nodes['cliptextencode_2']
    cliptextencode_2 = nodes['cliptextencode_2']
    createvideo = nodes['createvideo']
    createvideo = nodes['createvideo']
    positive = nodes['positive']
    positive = nodes['positive']
    positive = nodes['positive']
    ksampler = nodes['ksampler']
    ksampler = nodes['ksampler']
    image = nodes['image']
    image = nodes['image']
    image = nodes['image']
    positive = nodes['positive']
    return {
    'model': InputSpec(node=unetloader, field='unet_name', default=MODEL_NAME),
    'prompt': InputSpec(node=cliptextencode, field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ksampler, field='seed', default=DEFAULT_SEED),
    'steps': InputSpec(node=ksampler, field='steps', default=20),
    'negative_prompt': InputSpec(node=cliptextencode_2, field='text', default=DEFAULT_PROMPT_2),
    'negative': InputSpec(node=cliptextencode_2, field='text', default=DEFAULT_PROMPT_2),
    'output_fps': InputSpec(node=createvideo, field='fps', default=DEFAULT_FPS),
    'fps': InputSpec(node=createvideo, field='fps', default=DEFAULT_FPS),
    'width': InputSpec(node=positive, field='width', default=512),
    'height': InputSpec(node=positive, field='height', default=512),
    'length': InputSpec(node=positive, field='length', default=DEFAULT_FRAMES),
    'cfg': InputSpec(node=ksampler, field='cfg', default=GUIDE_STRENGTH),
    'sampler_name': InputSpec(node=ksampler, field='sampler_name', default='uni_pc'),
    'start_image': InputSpec(node=image, field='image', default='image_to_video_wan_start_image.png'),
    'input_image': InputSpec(node=image, field='image', default='image_to_video_wan_start_image.png'),
    'image': InputSpec(node=image, field='image', default='image_to_video_wan_start_image.png'),
    'frames': InputSpec(node=positive, field='length', default=DEFAULT_FRAMES),
    }

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video',
    inputs=PUBLIC_INPUT_METADATA,
    models=MODELS,
    output_prefix='video/ComfyUI',
    provenance={'source_workflow': 'workflow_corpus/official/video/wan_i2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Loaders
        unetloader = UNETLoader(unet_name=MODEL_NAME)
        cliploader = CLIPLoader(clip_name=MODEL_NAME_2, type_='wan')
        vaeloader = VAELoader(vae_name=MODEL_NAME_3)
        clipvisionloader = CLIPVisionLoader(clip_name=MODEL_NAME_4)

        # Inputs
        image, mask = LoadImage(image='image_to_video_wan_start_image.png')

        # Conditioning
        cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)
        cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader)

        clipvisionencode = CLIPVisionEncode(
            crop='none',
            clip_vision=clipvisionloader,
            image=image,
        )

        modelsamplingsd3 = ModelSamplingSD3(shift=8, model=unetloader)

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

        # Sampling
        ksampler = KSampler(
            seed=DEFAULT_SEED,
            steps=20,
            cfg=GUIDE_STRENGTH,
            sampler_name='uni_pc',
            latent_image=latent,
            model=modelsamplingsd3,
            negative=negative,
            positive=positive,
        )

        # Decode
        vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)
        createvideo = CreateVideo(fps=DEFAULT_FPS, images=vaedecode)

        # Outputs
        savevideo = SaveVideo(video=createvideo)

        return wf.finalize(PUBLIC_INPUTS(**locals()), output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

