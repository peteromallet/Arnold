"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def AILab_Qwen3TTSCustomVoice(
    wf: VibeWorkflow,
    *,
    text: Any = 'Hello from Qwen3-TTS.',
    speaker: Any = 'Ryan',
    model_size: Any = '1.7B',
    language: Any = 'Auto',
    instruct: Any = '',
    unload_models: Any = True,
    seed: Any = -1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Custom Voice (QwenTTS)
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['text'] = text
    _kwargs['speaker'] = speaker
    _kwargs['model_size'] = model_size
    _kwargs['language'] = language
    _kwargs['instruct'] = instruct
    _kwargs['unload_models'] = unload_models
    _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSCustomVoice', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSCustomVoice_Advanced(
    wf: VibeWorkflow,
    *,
    text: Any = 'Hello from Qwen3-TTS.',
    speaker: Any = 'Ryan',
    model_size: Any = '1.7B',
    device: Any = 'auto',
    precision: Any = 'bf16',
    language: Any = 'Auto',
    instruct: Any = '',
    max_new_tokens: Any = 2048,
    do_sample: Any = False,
    top_p: Any = 0.9,
    top_k: Any = 50,
    temperature: Any = 0.9,
    repetition_penalty: Any = 1.0,
    attention: Any = 'auto',
    unload_models: Any = True,
    seed: Any = -1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Custom Voice (QwenTTS) Advanced
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['text'] = text
    _kwargs['speaker'] = speaker
    _kwargs['model_size'] = model_size
    _kwargs['device'] = device
    _kwargs['precision'] = precision
    _kwargs['language'] = language
    _kwargs['instruct'] = instruct
    _kwargs['max_new_tokens'] = max_new_tokens
    _kwargs['do_sample'] = do_sample
    _kwargs['top_p'] = top_p
    _kwargs['top_k'] = top_k
    _kwargs['temperature'] = temperature
    _kwargs['repetition_penalty'] = repetition_penalty
    _kwargs['attention'] = attention
    _kwargs['unload_models'] = unload_models
    _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSCustomVoice_Advanced', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSLoadVoice(
    wf: VibeWorkflow,
    *,
    voice_name: Any = '',
    custom_path: Any = '',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Voice (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: VOICE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['voice_name'] = voice_name
    _kwargs['custom_path'] = custom_path
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSLoadVoice', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceClone(
    wf: VibeWorkflow,
    *,
    target_text: Any = 'Hello, this is a cloned voice.',
    model_size: Any = '1.7B',
    language: Any = 'Auto',
    reference_audio: Any = _UNSET,
    reference_text: Any = '',
    x_vector_only: Any = False,
    voice: Any = _UNSET,
    unload_models: Any = True,
    seed: Any = -1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Clone (QwenTTS)
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['target_text'] = target_text
    _kwargs['model_size'] = model_size
    _kwargs['language'] = language
    if reference_audio is not _UNSET:
        _kwargs['reference_audio'] = reference_audio
    _kwargs['reference_text'] = reference_text
    _kwargs['x_vector_only'] = x_vector_only
    if voice is not _UNSET:
        _kwargs['voice'] = voice
    _kwargs['unload_models'] = unload_models
    _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceClone', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceClone_Advanced(
    wf: VibeWorkflow,
    *,
    target_text: Any = 'Hello, this is a cloned voice.',
    model_size: Any = '1.7B',
    device: Any = 'auto',
    precision: Any = 'bf16',
    language: Any = 'Auto',
    reference_audio: Any = _UNSET,
    reference_text: Any = '',
    x_vector_only: Any = False,
    voice: Any = _UNSET,
    max_new_tokens: Any = 2048,
    do_sample: Any = False,
    top_p: Any = 0.9,
    top_k: Any = 50,
    temperature: Any = 0.9,
    repetition_penalty: Any = 1.0,
    attention: Any = 'auto',
    unload_models: Any = True,
    seed: Any = -1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Clone (QwenTTS) Advanced
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['target_text'] = target_text
    _kwargs['model_size'] = model_size
    _kwargs['device'] = device
    _kwargs['precision'] = precision
    _kwargs['language'] = language
    if reference_audio is not _UNSET:
        _kwargs['reference_audio'] = reference_audio
    _kwargs['reference_text'] = reference_text
    _kwargs['x_vector_only'] = x_vector_only
    if voice is not _UNSET:
        _kwargs['voice'] = voice
    _kwargs['max_new_tokens'] = max_new_tokens
    _kwargs['do_sample'] = do_sample
    _kwargs['top_p'] = top_p
    _kwargs['top_k'] = top_k
    _kwargs['temperature'] = temperature
    _kwargs['repetition_penalty'] = repetition_penalty
    _kwargs['attention'] = attention
    _kwargs['unload_models'] = unload_models
    _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceClone_Advanced', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceDesign(
    wf: VibeWorkflow,
    *,
    text: Any = 'Hello from Qwen3-TTS VoiceDesign.',
    instruct: Any = 'A warm, gentle female voice.',
    model_size: Any = '1.7B',
    language: Any = 'Auto',
    unload_models: Any = True,
    seed: Any = -1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Design (QwenTTS)
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['text'] = text
    _kwargs['instruct'] = instruct
    _kwargs['model_size'] = model_size
    _kwargs['language'] = language
    _kwargs['unload_models'] = unload_models
    _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceDesign', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceDesign_Advanced(
    wf: VibeWorkflow,
    *,
    text: Any = 'Hello from Qwen3-TTS VoiceDesign.',
    instruct: Any = 'A warm, gentle female voice.',
    model_size: Any = '1.7B',
    device: Any = 'auto',
    precision: Any = 'bf16',
    language: Any = 'Auto',
    max_new_tokens: Any = 2048,
    do_sample: Any = False,
    top_p: Any = 0.9,
    top_k: Any = 50,
    temperature: Any = 0.9,
    repetition_penalty: Any = 1.0,
    attention: Any = 'auto',
    unload_models: Any = True,
    seed: Any = -1,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Design (QwenTTS) Advanced
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['text'] = text
    _kwargs['instruct'] = instruct
    _kwargs['model_size'] = model_size
    _kwargs['device'] = device
    _kwargs['precision'] = precision
    _kwargs['language'] = language
    _kwargs['max_new_tokens'] = max_new_tokens
    _kwargs['do_sample'] = do_sample
    _kwargs['top_p'] = top_p
    _kwargs['top_k'] = top_k
    _kwargs['temperature'] = temperature
    _kwargs['repetition_penalty'] = repetition_penalty
    _kwargs['attention'] = attention
    _kwargs['unload_models'] = unload_models
    _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceDesign_Advanced', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceInstruct(
    wf: VibeWorkflow,
    *,
    character: Any = 'Auto',
    style: Any = 'Auto',
    custom_instruct: Any = '',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Instruct (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: VOICE_INSTRUCT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['character'] = character
    _kwargs['style'] = style
    _kwargs['custom_instruct'] = custom_instruct
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceInstruct', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceInstructZH(
    wf: VibeWorkflow,
    *,
    角色: Any = '自动',
    风格: Any = '自动',
    自定义风格指引: Any = '',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    声音风格指引 (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: VOICE_INSTRUCT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['角色'] = 角色
    _kwargs['风格'] = 风格
    _kwargs['自定义风格指引'] = 自定义风格指引
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceInstructZH', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoicesLibrary(
    wf: VibeWorkflow,
    *,
    reference_audio: Any,
    reference_text: Any = '',
    model_size: Any = '1.7B',
    device: Any = 'auto',
    precision: Any = 'bf16',
    x_vector_only: Any = False,
    voice_name: Any = 'voice_1',
    save_path: Any = '',
    unload_models: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create Voice (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: VOICE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['reference_audio'] = reference_audio
    _kwargs['reference_text'] = reference_text
    _kwargs['model_size'] = model_size
    _kwargs['device'] = device
    _kwargs['precision'] = precision
    _kwargs['x_vector_only'] = x_vector_only
    _kwargs['voice_name'] = voice_name
    _kwargs['save_path'] = save_path
    _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoicesLibrary', pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSWhisperSTT(
    wf: VibeWorkflow,
    *,
    audio: Any,
    model_size: Any = 'small',
    language: Any = 'auto',
    unload_models: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Whisper STT (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: text
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['audio'] = audio
    _kwargs['model_size'] = model_size
    _kwargs['language'] = language
    _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSWhisperSTT', pass_raw=pass_raw, **_kwargs)

__all__ = ['AILab_Qwen3TTSCustomVoice', 'AILab_Qwen3TTSCustomVoice_Advanced', 'AILab_Qwen3TTSLoadVoice', 'AILab_Qwen3TTSVoiceClone', 'AILab_Qwen3TTSVoiceClone_Advanced', 'AILab_Qwen3TTSVoiceDesign', 'AILab_Qwen3TTSVoiceDesign_Advanced', 'AILab_Qwen3TTSVoiceInstruct', 'AILab_Qwen3TTSVoiceInstructZH', 'AILab_Qwen3TTSVoicesLibrary', 'AILab_Qwen3TTSWhisperSTT']
