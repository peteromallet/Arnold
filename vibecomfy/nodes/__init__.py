from __future__ import annotations

from importlib import import_module

from vibecomfy.nodes._generated import MODULES as _MODULES


def _load_exports() -> list[str]:
    exports: set[str] = set()
    for module_name in _MODULES:
        module = import_module(f"vibecomfy.nodes.{module_name}")
        for name in getattr(module, "__all__", ()):
            globals()[name] = getattr(module, name)
            exports.add(name)
    return sorted(exports)


__all__ = _load_exports()

del _load_exports
