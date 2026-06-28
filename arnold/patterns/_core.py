"""Internal pattern primitives.

Stability:
    internal: ``PatternBlock`` and ``_as_hook_ref``

Pattern constructors return pure data values.  They never capture closures,
callable instances, live objects, or mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arnold.workflow import Step, Route
from arnold.workflow.refs import HookRef, RefDiagnosticError, as_hook_ref


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

    try:
        return as_hook_ref(value, node_id=node_id, field=field)
    except RefDiagnosticError:
        raise
    except Exception as exc:  # noqa: BLE001 - wrap unexpected resolver errors.
        raise RefDiagnosticError(
            f"node {node_id!r} field {field!r}: invalid hook ref {value!r}: {exc}"
        ) from exc


def _as_optional_hook_ref(
    value: Any | None,
    *,
    node_id: str,
    field: str,
) -> HookRef | None:
    if value is None:
        return None
    return _as_hook_ref(value, node_id=node_id, field=field)
