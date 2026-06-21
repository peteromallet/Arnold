"""Internal pattern primitives.

Stability:
    internal: ``PatternBlock`` and ``_as_hook_ref``

Pattern constructors return pure data values.  They never capture closures,
callable instances, live objects, or mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arnold.workflow import HookRef, ImportRef, RefDiagnosticError, Step, Route


@dataclass(frozen=True)
class PatternBlock:
    """A composite pattern value: explicit steps and deterministic routes."""

    steps: tuple[Step, ...] = ()
    routes: tuple[Route, ...] = ()


def _as_hook_ref(
    value: Any,
    *,
    node_id: str,
    field: str,
) -> HookRef:
    """Convert a string/ImportRef/HookRef into a validated durable hook ref."""

    if isinstance(value, HookRef):
        return value
    if isinstance(value, ImportRef):
        return HookRef(value)
    if isinstance(value, str):
        try:
            return HookRef.parse(value)
        except RefDiagnosticError as exc:
            # Re-raise with caller node/field context if the original lacks it.
            message = str(exc)
            if node_id is not None or field is not None:
                parts = []
                if node_id is not None:
                    parts.append(f"node {node_id!r}")
                if field is not None:
                    parts.append(f"field {field!r}")
                prefix = " ".join(parts)
                if prefix and not message.startswith(prefix):
                    message = f"{prefix}: {message}"
            raise RefDiagnosticError(message) from exc
        except Exception as exc:  # noqa: BLE001 - wrap unexpected parsing errors.
            raise RefDiagnosticError(
                f"node {node_id!r} field {field!r}: invalid hook ref {value!r}: {exc}"
            ) from exc
    raise RefDiagnosticError(
        f"node {node_id!r} field {field!r}: "
        "hook refs must be a durable 'module:qualname' string, ImportRef, or HookRef"
    )


def _as_optional_hook_ref(
    value: Any | None,
    *,
    node_id: str,
    field: str,
) -> HookRef | None:
    if value is None:
        return None
    return _as_hook_ref(value, node_id=node_id, field=field)
