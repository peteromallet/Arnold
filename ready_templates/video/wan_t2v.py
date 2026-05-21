# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CreateVideo, EmptyHunyuanLatentVideo, KSampler, ModelSamplingSD3, SaveVideo, UNETLoader, VAEDecode, VAELoader


DEFAULT_FPS = 16
DEFAULT_FRAMES = 33
DEFAULT_PROMPT = 'a fox moving quickly in a beautiful winter scenery nature trees mountains daytime tracking camera'
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 82628696717253
GUIDE_STRENGTH = 6
MODEL_NAME = 'wan2.1_t2v_1.3B_fp16.safetensors'
MODEL_NAME_2 = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
MODEL_NAME_3 = 'wan_2.1_vae.safetensors'


MODELS = {
    'wan2_1_t2v_1_3b_fp16': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors', sha256='be531024cd9018cb5b48c40cfbb6a6191645b1c792eb8bf4f8c1c6e10f924dc5', hf_revision='06e001fc51048fb03433a6fb25334de7836704a5', size_bytes=2838303560, subdir='diffusion_models'),
    'umt5_xxl_fp8_e4m3fn_scaled': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors', hf_revision='main', subdir='text_encoders'),
    'wan_2_1_vae': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors', hf_revision='main', subdir='vae'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('positive'), field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('ksampler'), field='seed', default=DEFAULT_SEED),
    'steps': InputSpec(node=ref('ksampler'), field='steps', default=30),
    'negative_prompt': InputSpec(node=ref('negative'), field='text', default=DEFAULT_PROMPT_2),
    'negative': InputSpec(node=ref('negative'), field='text', default=DEFAULT_PROMPT_2),
    'width': InputSpec(node=ref('emptyhunyuanlatentvideo'), field='width', default=832),
    'height': InputSpec(node=ref('emptyhunyuanlatentvideo'), field='height', default=480),
    'output_fps': InputSpec(node=ref('createvideo'), field='fps', default=DEFAULT_FPS),
    'fps': InputSpec(node=ref('createvideo'), field='fps', default=DEFAULT_FPS),
    'cfg': InputSpec(node=ref('ksampler'), field='cfg', default=GUIDE_STRENGTH),
    'sampler_name': InputSpec(node=ref('ksampler'), field='sampler_name', default='uni_pc'),
    'length': InputSpec(node=ref('emptyhunyuanlatentvideo'), field='length', default=DEFAULT_FRAMES),
    'frames': InputSpec(node=ref('emptyhunyuanlatentvideo'), field='length', default=DEFAULT_FRAMES),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='video/ComfyUI',
    provenance={'source_workflow': 'workflow_corpus/official/video/wan_t2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Loaders
        unetloader = UNETLoader(unet_name=MODEL_NAME)
        cliploader = CLIPLoader(clip_name=MODEL_NAME_2, type_='wan')
        vaeloader = VAELoader(vae_name=MODEL_NAME_3)

        # Sampling
        emptyhunyuanlatentvideo = EmptyHunyuanLatentVideo(
            width=832,
            height=480,
            length=DEFAULT_FRAMES,
        )

        # Conditioning
        positive = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)
        negative = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader)
        modelsamplingsd3 = ModelSamplingSD3(shift=8, model=unetloader)

        # Sampling
        ksampler = KSampler(
            seed=DEFAULT_SEED,
            steps=30,
            cfg=GUIDE_STRENGTH,
            sampler_name='uni_pc',
            latent_image=emptyhunyuanlatentvideo,
            model=modelsamplingsd3,
            negative=negative,
            positive=positive,
        )

        # Decode
        vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)
        createvideo = CreateVideo(fps=DEFAULT_FPS, images=vaedecode)

        # Outputs
        savevideo = SaveVideo(video=createvideo)

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

