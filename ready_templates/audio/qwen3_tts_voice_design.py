# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Text To Speech Voice Design.

Output: unknown.

Source:  workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_design.json

Packs:   ComfyUI-QwenTTS
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='qwen3_tts_voice_design',
    capability='text_to_speech_voice_design',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-QwenTTS'], 'custom_node_refs': [{'slug': 'ComfyUI-QwenTTS', 'source': 'git', 'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git'}]},
    provenance={'approach': 'text-to-speech from a natural language voice description', 'runtime_variant': 'qwen3-tts-smoke', 'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_design.json', 'source_role': 'materialized_ready_python_template'},
    coverage_tier='supplemental',
    runtime_note='Voice design currently requires the 1.7B Qwen3-TTS path exposed by the custom node.',
    input_fixtures=[],
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    ailab__qwen3_ttsvoice_design = node(wf, 'AILab_Qwen3TTSVoiceDesign', '1',
        instruct='A warm narrator voice with crisp diction and a neutral studio tone.',
        language='English',
        model_size='1.7B',
        seed=3294,
        text='This is a compact Qwen voice design smoke test for reusable VibeComfy audio templates.',
        unload_models=True,
    )
    # ════ OUTPUT ════
    save_audio = node(wf, 'SaveAudioMP3', '2',
        filename_prefix='audio/qwen3_tts_voice_design',
        quality='V0',
        audio=ailab__qwen3_ttsvoice_design.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

