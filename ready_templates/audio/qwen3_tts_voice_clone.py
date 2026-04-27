from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'1': {'class_type': 'LoadAudio', 'inputs': {'audio': 'speech_smoke.wav', 'widget_0': 'speech_smoke.wav'}},
 '2': {'class_type': 'AILab_Qwen3TTSVoiceClone',
       'inputs': {'target_text': 'This Qwen voice clone template uses a tiny bundled reference clip and runs as a '
                                 'reusable audio smoke test.',
                  'model_size': '0.6B',
                  'language': 'English',
                  'reference_text': 'This is a short reference audio sample for workflow smoke testing.',
                  'x_vector_only': False,
                  'unload_models': True,
                  'seed': 3189,
                  'reference_audio': ['1', 0]}},
 '3': {'class_type': 'SaveAudioMP3',
       'inputs': {'filename_prefix': 'audio/qwen3_tts_voice_clone', 'quality': 'V0', 'audio': ['2', 0]}}}

READY_METADATA = {'model_assets': [],
 'ready_template': 'audio/qwen3_tts_voice_clone',
 'workflow_template': 'qwen3_tts_voice_clone',
 'capability': 'text_to_speech_voice_clone',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json',
 'coverage_tier': 'supplemental',
 'approach': 'reference-audio voice cloning with a bundled smoke fixture',
 'runtime_note': 'Uses workflow_corpus/input/speech_smoke.wav as the reference clip for repeatable validation.',
 'discord_signal': None,
 'runtime_variant': 'qwen3-tts-smoke',
 'input_fixtures': ['workflow_corpus/input/speech_smoke.wav']}

READY_REQUIREMENTS = {'models': [], 'custom_nodes': ['ComfyUI-QwenTTS']}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "audio/qwen3_tts_voice_clone"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
