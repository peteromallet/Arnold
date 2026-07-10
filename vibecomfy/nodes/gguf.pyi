# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DualCLIPLoaderGGUF(
    *args: VibeWorkflow,
    _id: str | None = ...,
    clip_name1: Any | _Omitted = ...,
    clip_name2: Any | _Omitted = ...,
    type_: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def UnetLoaderGGUF(
    *args: VibeWorkflow,
    _id: str | None = ...,
    unet_name: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
