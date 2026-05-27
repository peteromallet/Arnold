# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import ConditioningZeroOut, DualCLIPLoader, KSampler, ModelSamplingAuraFlow, SaveAudioMP3, UNETLoader, VAEDecodeAudio, VAELoader


CLIP_NAME = 'qwen_0.6b_ace15.safetensors'
CLIP_NAME_2 = 'qwen_4b_ace15.safetensors'
DEFAULT_SEED = 561594583201063
GUIDE_STRENGTH = 1
UNET_NAME = 'acestep_v1.5_turbo.safetensors'
VAE_NAME = 'ace_1.5_vae.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='3', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['ace_1.5_vae.safetensors', 'acestep_v1.5_turbo.safetensors', 'euler'], 'custom_nodes': ['EmptyAceStep1', 'TextEncodeAceStepAudio1']},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/audio/ace_step_1_5_t2a_song.json', 'source_id': 'ace_step_1_5_t2a_song', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/official/audio/ace_step_1_5_t2a_song.json', 'output_mode': 'ready_template', 'ready_id': 'audio/ace_step_1_5_t2a_song'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Loaders
    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_NAME_2,
        type_='ace',
        device='default',
    )

    vaeloader = VAELoader(vae_name=VAE_NAME)
    emptyacestep1_5latentaudio = raw_call('EmptyAceStep1.5LatentAudio', '122', seconds=2.0)
    unetloader = UNETLoader(unet_name=UNET_NAME)
    modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=unetloader)

    textencodeacestepaudio1_5 = raw_call('TextEncodeAceStepAudio1.5', '124',
        tags='synthwave, techno, synthpop, futuristic, electro, with liquid drum & bass drive.\nRestless, confident, dreamy mood at 128 BPM.\nAnalog bass, pulsating arps, percussive synth stabs, gated drums.\nQuick build,  then explosive drum burst, then clean fade.\nBreathy, rhythmic female vocals, minimal emotion, metallic echo.',
        lyrics='Verse\nNeon rain on my screen,\nDreams compile in silver sheen.\nNo weight, just motion,\nI’m plugged into emotion.\n\nChorus\nComfy Cloud — breathing light,\nCode and color, spark and wire.\nDrift through data, feel alive,\nIn your circuits, I arrive.',
        seed=DEFAULT_SEED,
        duration=2.0,
        bpm=2,
        timesignature='4',
        language='en',
        keyscale='E minor',
        cfg_scale=1.5,
        clip=dualcliploader,
    )

    conditioningzeroout = ConditioningZeroOut(conditioning=textencodeacestepaudio1_5)

    # Sampling
    ksampler = KSampler(
        seed=DEFAULT_SEED,
        steps=1,
        cfg=GUIDE_STRENGTH,
        sampler_name='euler',
        latent_image=emptyacestep1_5latentaudio,
        model=modelsamplingauraflow,
        negative=conditioningzeroout,
        positive=textencodeacestepaudio1_5,
    )

    vaedecodeaudio = VAEDecodeAudio(samples=ksampler, vae=vaeloader)

    # Outputs
    saveaudiomp3 = SaveAudioMP3(
        filename_prefix='audio/vibecomfy_ace_step_smoke',
        audioUI='',
        audio=vaedecodeaudio,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveaudiomp3, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one', filename_prefix='audio/vibecomfy_ace_step_smoke')

