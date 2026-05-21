# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, ref
from vibecomfy.nodes.core import SaveAudioMP3
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSCustomVoice


DEFAULT_PROMPT = 'VibeComfy generated this short Qwen voice smoke test from a reusable Python template.'
DEFAULT_SEED = 3327


PUBLIC_INPUTS = {
    'seed': InputSpec(node=ref('ailab_qwen3ttscustomvoice'), field='seed', default=DEFAULT_SEED),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_speech_custom_voice',
    inputs=PUBLIC_INPUTS,
    requirements={'custom_nodes': ['ComfyUI-QwenTTS']},
    custom_node_packs={'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSCustomVoice'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'pinned'}},
    runtime_variant='qwen3-tts-smoke',
    approach='custom preset speaker text-to-speech',
    runtime_note='Uses the smaller 0.6B Qwen3-TTS model for runtime smoke validation.',
    input_fixtures=[],
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_custom_voice.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        ailab_qwen3ttscustomvoice = AILab_Qwen3TTSCustomVoice(
            instruct='Calm, clear, friendly delivery.',
            language='English',
            model_size='0.6B',
            seed=DEFAULT_SEED,
            text=DEFAULT_PROMPT,
        )

        saveaudiomp3 = SaveAudioMP3(
            filename_prefix='audio/qwen3_tts_custom_voice',
            audio=ailab_qwen3ttscustomvoice,
        )

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one')

