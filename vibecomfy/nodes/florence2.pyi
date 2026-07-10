# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DownloadAndLoadFlorence2Model(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['microsoft/Florence-2-base', 'microsoft/Florence-2-large', 'microsoft/Florence-2-base-ft', 'microsoft/Florence-2-large-ft'] | _Omitted = ...,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = ...,
    attention: Literal['sdpa', 'flash_attention_2', 'eager'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Florence2Run(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    florence2_model: Any | _Omitted = ...,
    text_input: str | _Omitted = ...,
    task: Literal['caption', 'detailed_caption', 'more_detailed_caption', 'caption_to_phrase_grounding', 'referring_expression_segmentation', 'region_to_segmentation', 'open_vocabulary_detection', 'dense_region_caption', 'region_proposal', 'ocr', 'ocr_with_region'] | _Omitted = ...,
    fill_mask: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
