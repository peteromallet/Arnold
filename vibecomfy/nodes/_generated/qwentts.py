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
    _id: str | None = None,
    text: Any = _UNSET,
    speaker: Any = _UNSET,
    model_size: Any = _UNSET,
    language: Any = _UNSET,
    instruct: Any = _UNSET,
    unload_models: Any = _UNSET,
    seed: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Custom Voice (QwenTTS)
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    if text is not _UNSET:
        _kwargs['text'] = text
    if speaker is not _UNSET:
        _kwargs['speaker'] = speaker
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if language is not _UNSET:
        _kwargs['language'] = language
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSCustomVoice', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSCustomVoice_Advanced(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    text: Any = _UNSET,
    speaker: Any = _UNSET,
    model_size: Any = _UNSET,
    device: Any = _UNSET,
    precision: Any = _UNSET,
    language: Any = _UNSET,
    instruct: Any = _UNSET,
    max_new_tokens: Any = _UNSET,
    do_sample: Any = _UNSET,
    top_p: Any = _UNSET,
    top_k: Any = _UNSET,
    temperature: Any = _UNSET,
    repetition_penalty: Any = _UNSET,
    attention: Any = _UNSET,
    unload_models: Any = _UNSET,
    seed: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Custom Voice (QwenTTS) Advanced
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    if text is not _UNSET:
        _kwargs['text'] = text
    if speaker is not _UNSET:
        _kwargs['speaker'] = speaker
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if device is not _UNSET:
        _kwargs['device'] = device
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if language is not _UNSET:
        _kwargs['language'] = language
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    if do_sample is not _UNSET:
        _kwargs['do_sample'] = do_sample
    if top_p is not _UNSET:
        _kwargs['top_p'] = top_p
    if top_k is not _UNSET:
        _kwargs['top_k'] = top_k
    if temperature is not _UNSET:
        _kwargs['temperature'] = temperature
    if repetition_penalty is not _UNSET:
        _kwargs['repetition_penalty'] = repetition_penalty
    if attention is not _UNSET:
        _kwargs['attention'] = attention
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSCustomVoice_Advanced', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSLoadVoice(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    voice_name: Any = _UNSET,
    custom_path: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Voice (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: VOICE
    """
    _kwargs: dict[str, Any] = {}
    if voice_name is not _UNSET:
        _kwargs['voice_name'] = voice_name
    if custom_path is not _UNSET:
        _kwargs['custom_path'] = custom_path
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSLoadVoice', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceClone(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    target_text: Any = _UNSET,
    model_size: Any = _UNSET,
    language: Any = _UNSET,
    reference_audio: Any = _UNSET,
    reference_text: Any = _UNSET,
    x_vector_only: Any = _UNSET,
    voice: Any = _UNSET,
    unload_models: Any = _UNSET,
    seed: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Clone (QwenTTS)
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    if target_text is not _UNSET:
        _kwargs['target_text'] = target_text
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if language is not _UNSET:
        _kwargs['language'] = language
    if reference_audio is not _UNSET:
        _kwargs['reference_audio'] = reference_audio
    if reference_text is not _UNSET:
        _kwargs['reference_text'] = reference_text
    if x_vector_only is not _UNSET:
        _kwargs['x_vector_only'] = x_vector_only
    if voice is not _UNSET:
        _kwargs['voice'] = voice
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceClone', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceClone_Advanced(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    target_text: Any = _UNSET,
    model_size: Any = _UNSET,
    device: Any = _UNSET,
    precision: Any = _UNSET,
    language: Any = _UNSET,
    reference_audio: Any = _UNSET,
    reference_text: Any = _UNSET,
    x_vector_only: Any = _UNSET,
    voice: Any = _UNSET,
    max_new_tokens: Any = _UNSET,
    do_sample: Any = _UNSET,
    top_p: Any = _UNSET,
    top_k: Any = _UNSET,
    temperature: Any = _UNSET,
    repetition_penalty: Any = _UNSET,
    attention: Any = _UNSET,
    unload_models: Any = _UNSET,
    seed: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Clone (QwenTTS) Advanced
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    if target_text is not _UNSET:
        _kwargs['target_text'] = target_text
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if device is not _UNSET:
        _kwargs['device'] = device
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if language is not _UNSET:
        _kwargs['language'] = language
    if reference_audio is not _UNSET:
        _kwargs['reference_audio'] = reference_audio
    if reference_text is not _UNSET:
        _kwargs['reference_text'] = reference_text
    if x_vector_only is not _UNSET:
        _kwargs['x_vector_only'] = x_vector_only
    if voice is not _UNSET:
        _kwargs['voice'] = voice
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    if do_sample is not _UNSET:
        _kwargs['do_sample'] = do_sample
    if top_p is not _UNSET:
        _kwargs['top_p'] = top_p
    if top_k is not _UNSET:
        _kwargs['top_k'] = top_k
    if temperature is not _UNSET:
        _kwargs['temperature'] = temperature
    if repetition_penalty is not _UNSET:
        _kwargs['repetition_penalty'] = repetition_penalty
    if attention is not _UNSET:
        _kwargs['attention'] = attention
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceClone_Advanced', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceDesign(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    text: Any = _UNSET,
    instruct: Any = _UNSET,
    model_size: Any = _UNSET,
    language: Any = _UNSET,
    unload_models: Any = _UNSET,
    seed: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Design (QwenTTS)
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    if text is not _UNSET:
        _kwargs['text'] = text
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if language is not _UNSET:
        _kwargs['language'] = language
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceDesign', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceDesign_Advanced(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    text: Any = _UNSET,
    instruct: Any = _UNSET,
    model_size: Any = _UNSET,
    device: Any = _UNSET,
    precision: Any = _UNSET,
    language: Any = _UNSET,
    max_new_tokens: Any = _UNSET,
    do_sample: Any = _UNSET,
    top_p: Any = _UNSET,
    top_k: Any = _UNSET,
    temperature: Any = _UNSET,
    repetition_penalty: Any = _UNSET,
    attention: Any = _UNSET,
    unload_models: Any = _UNSET,
    seed: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Design (QwenTTS) Advanced
    
    Pack: AILab_QwenTTS
    Returns: audio
    """
    _kwargs: dict[str, Any] = {}
    if text is not _UNSET:
        _kwargs['text'] = text
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if device is not _UNSET:
        _kwargs['device'] = device
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if language is not _UNSET:
        _kwargs['language'] = language
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    if do_sample is not _UNSET:
        _kwargs['do_sample'] = do_sample
    if top_p is not _UNSET:
        _kwargs['top_p'] = top_p
    if top_k is not _UNSET:
        _kwargs['top_k'] = top_k
    if temperature is not _UNSET:
        _kwargs['temperature'] = temperature
    if repetition_penalty is not _UNSET:
        _kwargs['repetition_penalty'] = repetition_penalty
    if attention is not _UNSET:
        _kwargs['attention'] = attention
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceDesign_Advanced', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceInstruct(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    character: Any = _UNSET,
    style: Any = _UNSET,
    custom_instruct: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Voice Instruct (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: VOICE_INSTRUCT
    """
    _kwargs: dict[str, Any] = {}
    if character is not _UNSET:
        _kwargs['character'] = character
    if style is not _UNSET:
        _kwargs['style'] = style
    if custom_instruct is not _UNSET:
        _kwargs['custom_instruct'] = custom_instruct
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceInstruct', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceInstructZH(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    角色: Any = _UNSET,
    风格: Any = _UNSET,
    自定义风格指引: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    声音风格指引 (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: VOICE_INSTRUCT
    """
    _kwargs: dict[str, Any] = {}
    if 角色 is not _UNSET:
        _kwargs['角色'] = 角色
    if 风格 is not _UNSET:
        _kwargs['风格'] = 风格
    if 自定义风格指引 is not _UNSET:
        _kwargs['自定义风格指引'] = 自定义风格指引
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceInstructZH', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoicesLibrary(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    reference_audio: Any = _UNSET,
    reference_text: Any = _UNSET,
    model_size: Any = _UNSET,
    device: Any = _UNSET,
    precision: Any = _UNSET,
    x_vector_only: Any = _UNSET,
    voice_name: Any = _UNSET,
    save_path: Any = _UNSET,
    unload_models: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create Voice (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: VOICE
    """
    _kwargs: dict[str, Any] = {}
    if reference_audio is not _UNSET:
        _kwargs['reference_audio'] = reference_audio
    if reference_text is not _UNSET:
        _kwargs['reference_text'] = reference_text
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if device is not _UNSET:
        _kwargs['device'] = device
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if x_vector_only is not _UNSET:
        _kwargs['x_vector_only'] = x_vector_only
    if voice_name is not _UNSET:
        _kwargs['voice_name'] = voice_name
    if save_path is not _UNSET:
        _kwargs['save_path'] = save_path
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoicesLibrary', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSWhisperSTT(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    audio: Any = _UNSET,
    model_size: Any = _UNSET,
    language: Any = _UNSET,
    unload_models: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Whisper STT (QwenTTS)
    
    Pack: AILab_QwenTTS_Tools
    Returns: text
    """
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if language is not _UNSET:
        _kwargs['language'] = language
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSWhisperSTT', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['AILab_Qwen3TTSCustomVoice', 'AILab_Qwen3TTSCustomVoice_Advanced', 'AILab_Qwen3TTSLoadVoice', 'AILab_Qwen3TTSVoiceClone', 'AILab_Qwen3TTSVoiceClone_Advanced', 'AILab_Qwen3TTSVoiceDesign', 'AILab_Qwen3TTSVoiceDesign_Advanced', 'AILab_Qwen3TTSVoiceInstruct', 'AILab_Qwen3TTSVoiceInstructZH', 'AILab_Qwen3TTSVoicesLibrary', 'AILab_Qwen3TTSWhisperSTT']
