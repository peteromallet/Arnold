"""Plugin-operation carrier types and the ``OperationRegistry`` seam.

This module declares the six neutral operation kinds, a runtime-neutral
:class:`OperationRequest` / :class:`OperationResult` pair, the
:class:`OperationRegistry` :class:`typing.Protocol`, and a stub
:class:`NullOperationRegistry` whose dispatch returns an explicit
unsupported result for every operation kind without raising.

The six kinds correspond to the brief's enumeration: run phase,
status/control projection, resume, override-list, override-apply, and
profile-validate.  Status and control are intentionally collapsed into a
single ``status_projection`` operation per the brief's "one operation or
a small operation family" guidance and the M2a locked decision to keep
the carrier surface minimum.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals (see
``tests/arnold/runtime/test_package_boundary.py`` for the static gate).
Override actions remain opaque strings inside ``payload["action"]`` —
Arnold never interprets the action label.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable

__all__ = [
    "OperationKind",
    "OperationRequest",
    "OperationResult",
    "OperationRegistry",
    "NullOperationRegistry",
]


class OperationKind(str, Enum):
    """The six neutral operation kinds the runtime may dispatch.

    Each value is a runtime-neutral identifier; none contain Megaplan
    phase names, override actions, or gate labels.
    """

    EXECUTE = "run_phase"
    STATUS_PROJECTION = "status_projection"
    RESUME = "resume"
    OVERRIDE_LIST = "override_list"
    OVERRIDE_APPLY = "override_apply"
    PROFILE_VALIDATE = "profile_validate"


@dataclass(frozen=True)
class OperationRequest:
    """A request handed to a plugin operation.

    ``payload`` is opaque to Arnold — plugins own its interpretation.
    The override-list / override-apply kinds, for example, carry the
    plugin's action vocabulary inside ``payload["action"]`` as an
    opaque string the runtime never reads.
    """

    kind: OperationKind
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationResult:
    """The result returned by a plugin operation.

    ``ok`` is the only field Arnold interprets directly.  ``errors`` is
    a tuple of opaque strings; convention is that the first entry is a
    runtime-neutral error class (``"unsupported"``, ``"timeout"``,
    ``"invalid_request"``, …) and the rest are plugin-specific detail.
    """

    ok: bool
    payload: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


@runtime_checkable
class OperationRegistry(Protocol):
    """Protocol that plugin operation registries implement.

    ``supported_operations`` declares the set of kinds the plugin
    implements.  ``dispatch`` runs an operation and returns an
    :class:`OperationResult`.  Implementations MUST NOT raise on an
    unsupported kind — the unsupported case is encoded as
    ``OperationResult(ok=False, errors=("unsupported", <kind>))``.
    """

    def supported_operations(self) -> frozenset[OperationKind]:  # pragma: no cover - protocol
        ...

    def dispatch(self, request: OperationRequest) -> OperationResult:  # pragma: no cover - protocol
        ...


class NullOperationRegistry:
    """Registry that implements no operations.

    ``supported_operations()`` returns the empty frozen set.  Every
    ``dispatch`` call returns an explicit unsupported result rather
    than raising or silently defaulting — consumers can detect the
    no-op shape from the ``("unsupported", <kind>)`` errors tuple.
    """

    def supported_operations(self) -> frozenset[OperationKind]:
        return frozenset()

    def dispatch(self, request: OperationRequest) -> OperationResult:
        kind_value = (
            request.kind.value
            if isinstance(request.kind, OperationKind)
            else str(request.kind)
        )
        return OperationResult(
            ok=False,
            payload={},
            errors=("unsupported", kind_value),
        )
