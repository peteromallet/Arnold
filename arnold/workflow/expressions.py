"""Inert workflow expression references.

Expression refs carry stable dependency identities for later compiler and
pattern code. They deliberately do not evaluate Python values or participate in
truthiness checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from arnold.workflow.refs import HookRef, ImportRef, _require_ref_segment


@dataclass(frozen=True, order=True)
class ExpressionRef:
    """Stable reference to a named expression plus its declared dependencies."""

    id: str
    dependencies: tuple[str, ...] = ()
    hook: HookRef | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_ref_segment("expression id", self.id))
        object.__setattr__(
            self,
            "dependencies",
            tuple(_require_ref_segment("expression dependency", dependency) for dependency in self.dependencies),
        )

    @property
    def key(self) -> str:
        base = f"expr:{self.id}"
        if self.hook is None:
            return base
        return f"{base}@{self.hook.key}"

    def __bool__(self) -> bool:
        raise TypeError("ExpressionRef is an inert reference and has no runtime truthiness")

    def __str__(self) -> str:
        return self.key


def expression_ref(
    id: str,
    *,
    dependencies: Iterable[str] = (),
    hook: HookRef | ImportRef | str | None = None,
) -> ExpressionRef:
    """Create an inert expression ref from stable string/import identities."""

    hook_ref: HookRef | None
    if hook is None:
        hook_ref = None
    elif isinstance(hook, HookRef):
        hook_ref = hook
    elif isinstance(hook, ImportRef):
        hook_ref = HookRef(hook)
    else:
        hook_ref = HookRef.parse(hook)
    return ExpressionRef(id=id, dependencies=tuple(dependencies), hook=hook_ref)
