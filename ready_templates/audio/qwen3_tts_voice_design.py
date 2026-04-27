from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'1': {'class_type': 'AILab_Qwen3TTSVoiceDesign',
       'inputs': {'text': 'This is a compact Qwen voice design smoke test for reusable VibeComfy audio templates.',
                  'instruct': 'A warm narrator voice with crisp diction and a neutral studio tone.',
                  'model_size': '1.7B',
                  'language': 'English',
                  'unload_models': True,
                  'seed': 3294}},
 '2': {'class_type': 'SaveAudioMP3',
       'inputs': {'filename_prefix': 'audio/qwen3_tts_voice_design', 'quality': 'V0', 'audio': ['1', 0]}}}

READY_METADATA = {'model_assets': [],
 'ready_template': 'audio/qwen3_tts_voice_design',
 'workflow_template': 'qwen3_tts_voice_design',
 'capability': 'text_to_speech_voice_design',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_design.json',
 'coverage_tier': 'supplemental',
 'approach': 'text-to-speech from a natural language voice description',
 'runtime_note': 'Voice design currently requires the 1.7B Qwen3-TTS path exposed by the custom node.',
 'discord_signal': None,
 'runtime_variant': 'qwen3-tts-smoke',
 'input_fixtures': []}

READY_REQUIREMENTS = {'models': [], 'custom_nodes': ['ComfyUI-QwenTTS']}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "audio/qwen3_tts_voice_design"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
