from __future__ import annotations

from vibecomfy.patches.controlnet import patch as controlnet
from vibecomfy.patches.gguf_unet import patch as gguf_unet
from vibecomfy.patches.ltx_lowvram import patch as ltx_lowvram
from vibecomfy.patches.types import Patch


BUILTIN_PATCHES: tuple[Patch, ...] = (controlnet, gguf_unet, ltx_lowvram)
