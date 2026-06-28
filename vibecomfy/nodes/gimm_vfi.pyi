# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DownloadAndLoadGIMMVFIModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['GIMMVFI_flow_S.pkl', 'GIMMVFI_flow_M.pkl', 'GIMMVFI_noflow_S.pkl', 'GIMMVFI_noflow_M.pkl'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GIMMVFI_interpolate(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    multiplier: int | _Omitted = ...,
    scale: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
