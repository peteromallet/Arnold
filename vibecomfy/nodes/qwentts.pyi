# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def AILab_Qwen3TTSCustomVoice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    text: str | _Omitted = ...,
    speaker: Literal['Aiden', 'Dylan', 'Eric', 'Ono_Anna', 'Ryan', 'Serena', 'Sohee', 'Uncle_Fu', 'Vivian'] | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    instruct: str | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSCustomVoice_Advanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    text: str | _Omitted = ...,
    speaker: Literal['Aiden', 'Dylan', 'Eric', 'Ono_Anna', 'Ryan', 'Serena', 'Sohee', 'Uncle_Fu', 'Vivian'] | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = ...,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    instruct: str | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    do_sample: bool | _Omitted = ...,
    top_p: float | _Omitted = ...,
    top_k: int | _Omitted = ...,
    temperature: float | _Omitted = ...,
    repetition_penalty: float | _Omitted = ...,
    attention: Literal['auto', 'sage_attn', 'flash_attn', 'sdpa', 'eager'] | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSLoadVoice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    voice_name: Literal[''] | _Omitted = ...,
    custom_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceClone(
    *args: VibeWorkflow,
    _id: str | None = ...,
    target_text: str | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    reference_audio: Any | _Omitted = ...,
    reference_text: str | _Omitted = ...,
    x_vector_only: bool | _Omitted = ...,
    voice: Any | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceClone_Advanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    target_text: str | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = ...,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    reference_audio: Any | _Omitted = ...,
    reference_text: str | _Omitted = ...,
    x_vector_only: bool | _Omitted = ...,
    voice: Any | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    do_sample: bool | _Omitted = ...,
    top_p: float | _Omitted = ...,
    top_k: int | _Omitted = ...,
    temperature: float | _Omitted = ...,
    repetition_penalty: float | _Omitted = ...,
    attention: Literal['auto', 'sage_attn', 'flash_attn', 'sdpa', 'eager'] | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceDesign(
    *args: VibeWorkflow,
    _id: str | None = ...,
    text: str | _Omitted = ...,
    instruct: str | _Omitted = ...,
    model_size: Literal['1.7B'] | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceDesign_Advanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    text: str | _Omitted = ...,
    instruct: str | _Omitted = ...,
    model_size: Literal['1.7B'] | _Omitted = ...,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = ...,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    do_sample: bool | _Omitted = ...,
    top_p: float | _Omitted = ...,
    top_k: int | _Omitted = ...,
    temperature: float | _Omitted = ...,
    repetition_penalty: float | _Omitted = ...,
    attention: Literal['auto', 'sage_attn', 'flash_attn', 'sdpa', 'eager'] | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceInstruct(
    *args: VibeWorkflow,
    _id: str | None = ...,
    character: Literal['Auto', 'Female', 'Male', 'Young Female', 'Young Male', 'Girl', 'Boy', 'Child', 'Teen', 'Adult', 'Senior Female', 'Senior Male', 'Narrator', 'Announcer'] | _Omitted = ...,
    style: Literal['Auto', 'Warm', 'Gentle', 'Calm', 'Cheerful', 'Friendly', 'Serious', 'Sad', 'Angry', 'Excited', 'Soft', 'Deep', 'Clear', 'Emotional', 'Dramatic', 'Whisper', 'Breathy', 'Husky', 'Authoritative', 'Storytelling', 'News Anchor', 'Documentary', 'Customer Support', 'Teacher', 'Audiobook', 'Energetic', 'Relaxed', 'Playful', 'Mysterious', 'Romantic', 'Inspirational', 'Formal', 'Casual', 'ASMR', 'Noir', 'Cinematic', 'Trailer', 'Motivational', 'Robotic', 'Vintage Radio', 'Lullaby', 'Comedy', 'Interview', 'Poetic', 'Philosophical', 'Sportscaster', 'Meditation'] | _Omitted = ...,
    custom_instruct: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceInstructZH(
    *args: VibeWorkflow,
    _id: str | None = ...,
    角色: Literal['自动', '女声', '男声', '年轻女声', '年轻男声', '小女孩', '小男孩', '童声', '青少年', '成年', '老年女声', '老年男声', '旁白', '播报'] | _Omitted = ...,
    风格: Literal['自动', '温暖', '轻柔', '平静', '愉快', '友好', '严肃', '悲伤', '愤怒', '兴奋', '轻声', '低沉', '清晰', '情感', '戏剧', '耳语', '气声', '沙哑', '权威', '讲故事', '新闻主播', '纪录片', '客服', '老师', '有声书', '有活力', '放松', '俏皮', '神秘', '浪漫', '励志', '正式', '随意', 'ASMR', '黑色电影', '电影感', '预告片', '激励', '机械', '复古电台', '摇篮曲', '喜剧', '访谈', '诗意', '哲思', '体育解说', '冥想'] | _Omitted = ...,
    自定义风格指引: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoicesLibrary(
    *args: VibeWorkflow,
    _id: str | None = ...,
    reference_audio: Any | _Omitted = ...,
    reference_text: str | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = ...,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    x_vector_only: bool | _Omitted = ...,
    voice_name: str | _Omitted = ...,
    save_path: str | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSWhisperSTT(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    model_size: Literal['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3', 'large-v3-turbo'] | _Omitted = ...,
    language: Literal['auto', 'en', 'zh', 'ja', 'ko', 'de', 'fr', 'es', 'it', 'pt', 'ru'] | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
