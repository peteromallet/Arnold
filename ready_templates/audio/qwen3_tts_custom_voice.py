from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'1': {'class_type': 'AILab_Qwen3TTSCustomVoice',
       'inputs': {'text': 'VibeComfy generated this short Qwen voice smoke test from a reusable Python template.',
                  'speaker': 'Ryan',
                  'model_size': '0.6B',
                  'language': 'English',
                  'instruct': 'Calm, clear, friendly delivery.',
                  'unload_models': True,
                  'seed': 3327}},
 '2': {'class_type': 'SaveAudioMP3',
       'inputs': {'filename_prefix': 'audio/qwen3_tts_custom_voice', 'quality': 'V0', 'audio': ['1', 0]}}}

READY_METADATA = {'model_assets': [],
 'ready_template': 'audio/qwen3_tts_custom_voice',
 'workflow_template': 'qwen3_tts_custom_voice',
 'capability': 'text_to_speech_custom_voice',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_custom_voice.json',
 'coverage_tier': 'supplemental',
 'approach': 'custom preset speaker text-to-speech',
 'runtime_note': 'Uses the smaller 0.6B Qwen3-TTS model for runtime smoke validation.',
 'discord_signal': None,
 'runtime_variant': 'qwen3-tts-smoke',
 'input_fixtures': []}

READY_REQUIREMENTS = {'models': [], 'custom_nodes': ['ComfyUI-QwenTTS']}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "audio/qwen3_tts_custom_voice"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
