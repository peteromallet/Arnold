from __future__ import annotations

from collections.abc import Iterable

from vibecomfy.patches.builtins import BUILTIN_PATCHES
from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeWorkflow


_PATCHES: dict[str, Patch] = {}


def register(patch: Patch) -> Patch:
    """Register an external auto-applicable singleton patch.

    Built-in patches live in ``BUILTIN_PATCHES`` and are not copied into this
    mutable registry. Parameterized transformations should be exposed as
    factory functions returning ``Patch`` instances and should not register
    every configured variant globally.
    """
    _PATCHES[patch.name] = patch
    return patch


def bootstrap_builtin_patches() -> tuple[Patch, ...]:
    """Return the explicit built-in patch registry without mutating globals."""
    return BUILTIN_PATCHES


def registered_patches(*, include_builtins: bool = True) -> tuple[Patch, ...]:
    external = tuple(_PATCHES.values())
    if include_builtins:
        return (*BUILTIN_PATCHES, *external)
    return external


def find_applicable(workflow: VibeWorkflow, *, patches: Iterable[Patch] | None = None) -> list[Patch]:
    candidates = registered_patches() if patches is None else patches
    return [patch for patch in candidates if patch.applies_to(workflow)]


__all__ = ["BUILTIN_PATCHES", "bootstrap_builtin_patches", "find_applicable", "register", "registered_patches"]
