from __future__ import annotations

from typing import Any

from vibecomfy.patches.types import Patch


def __getattr__(name: str) -> Any:
    if name == "controlnet":
        from vibecomfy.patches.controlnet import patch

        return patch
    if name == "gguf_unet":
        from vibecomfy.patches.gguf_unet import patch

        return patch
    if name == "ltx_lowvram":
        from vibecomfy.patches.ltx_lowvram import patch

        return patch
    if name == "resolution":
        from vibecomfy.patches.resolution import resolution

        return resolution
    if name == "save_prefix":
        from vibecomfy.patches.save_prefix import save_prefix

        return save_prefix
    if name == "seed":
        from vibecomfy.patches.seed import seed

        return seed
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["Patch", "controlnet", "gguf_unet", "ltx_lowvram", "resolution", "save_prefix", "seed"]
