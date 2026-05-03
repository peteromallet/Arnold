"""Database-backed store skeleton for Sprint 1."""

from __future__ import annotations

import inspect

from .base import Store


def _not_implemented_method(name: str):
    def _method(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError(f"DBStore.{name}() is implemented in Sprint 2")

    _method.__name__ = name
    _method.__qualname__ = f"DBStore.{name}"
    return _method


class DBStore:
    """Protocol-complete DB store skeleton.

    Sprint 1 intentionally leaves every method unimplemented while keeping the
    import and structural typing seam in place for Sprint 2.
    """


for _name, _value in inspect.getmembers(Store, predicate=inspect.isfunction):
    if _name.startswith("_"):
        continue
    setattr(DBStore, _name, _not_implemented_method(_name))


__all__ = ["DBStore"]
