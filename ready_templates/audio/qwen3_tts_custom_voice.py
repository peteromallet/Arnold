# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Text To Speech Custom Voice.

Output: unknown.

Source:  workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_custom_voice.json

Packs:   ComfyUI-QwenTTS
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='qwen3_tts_custom_voice',
    capability='text_to_speech_custom_voice',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-QwenTTS'], 'custom_node_refs': [{'slug': 'ComfyUI-QwenTTS', 'source': 'git', 'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git'}]},
    provenance={'runtime_variant': 'qwen3-tts-smoke', 'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_custom_voice.json', 'approach': 'custom preset speaker text-to-speech'},
    coverage_tier='supplemental',
    runtime_note='Uses the smaller 0.6B Qwen3-TTS model for runtime smoke validation.',
    input_fixtures=[],
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    ailab__qwen3_ttscustom_voice = node(wf, 'AILab_Qwen3TTSCustomVoice', '1',
        instruct='Calm, clear, friendly delivery.',
        language='English',
        model_size='0.6B',
        seed=3327,
        speaker='Ryan',
        text='VibeComfy generated this short Qwen voice smoke test from a reusable Python template.',
        unload_models=True,
    )
    # ════ OUTPUT ════
    save_audio = node(wf, 'SaveAudioMP3', '2',
        filename_prefix='audio/qwen3_tts_custom_voice',
        quality='V0',
        audio=ailab__qwen3_ttscustom_voice.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

