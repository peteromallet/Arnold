# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import LoadAudio, SaveAudioMP3
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSVoiceClone


AUDIO = 'speech_smoke.wav'
DEFAULT_SEED = 3189


MODELS = {}

PUBLIC_INPUTS = {
    'seed': InputSpec(node=ref('ailab_qwen3ttsvoiceclone'), field='seed', default=DEFAULT_SEED),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_speech_voice_clone',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-QwenTTS']},
    custom_node_packs={'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSVoiceClone'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'pinned'}},
    approach='reference-audio voice cloning with a bundled smoke fixture',
    runtime_variant='qwen3-tts-smoke',
    runtime_note='Uses workflow_corpus/input/speech_smoke.wav as the reference clip for repeatable validation.',
    input_fixtures=['workflow_corpus/input/speech_smoke.wav'],
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadaudio = LoadAudio(_id='1', audio=AUDIO, widget_0='speech_smoke.wav')
        wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id
        ailab_qwen3ttsvoiceclone = AILab_Qwen3TTSVoiceClone(
            _id='2',
            language='English',
            model_size='0.6B',
            reference_text='This is a short reference audio sample for workflow smoke testing.',
            seed=DEFAULT_SEED,
            target_text='This Qwen voice clone template uses a tiny bundled reference clip and runs as a reusable audio smoke test.',
            reference_audio=loadaudio,
        )
        wf.metadata.setdefault('id_map', {})['ailab_qwen3ttsvoiceclone'] = ailab_qwen3ttsvoiceclone.node.id

        saveaudiomp3 = SaveAudioMP3(
            _id='3',
            filename_prefix='audio/qwen3_tts_voice_clone',
            audio=ailab_qwen3ttsvoiceclone,
        )
        wf.metadata.setdefault('id_map', {})['saveaudiomp3'] = saveaudiomp3.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one')

