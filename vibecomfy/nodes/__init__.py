from __future__ import annotations

from importlib import import_module

MODULES = ['core', 'kjnodes', 'ltxvideo', 'videohelpersuite', 'controlnet_aux', 'depthanythingv2', 'wanvideowrapper', 'qwentts', 'qwen3tts', 'gguf', 'rgthree', 'sam2', 'wananimatepreprocess', 'ailab_audioduration', 'custom_scripts', 'florence2', 'gimm_vfi', 'melbandroformer', 'vibecomfy_internal']


def _load_exports() -> list[str]:
    exports: set[str] = set()
    for module_name in MODULES:
        module = import_module(f"vibecomfy.nodes.{module_name}")
        for name in getattr(module, "__all__", ()):
            globals()[name] = getattr(module, name)
            exports.add(name)
    return [*sorted(exports), "MODULES"]


__all__ = _load_exports()

del _load_exports
