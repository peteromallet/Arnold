"""Compatibility re-exports and workflow-local ref validation helpers.

Ownership:
    ``arnold.manifest.refs`` owns durable runtime coordinates and import/hook
    identity.  This module is the workflow package boundary for re-exporting
    those primitives and for the shared scalar ref checks used by explicit DSL
    objects, authoring contract objects, and source-compiler diagnostics.
"""

from __future__ import annotations

import re
from typing import Any

from arnold.manifest.refs import (
    EdgeRef,
    HookRef,
    ImportRef,
    ManifestCoordinate,
    ManifestCursor,
    NodeRef,
    RefDiagnosticError,
    SourceRef,
    SourceSpan,
    ValueRef,
    _require_ref_segment,
    _unstable_ref_error,
    canonical_alias,
    manifest_coordinate,
)

_MANIFEST_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def require_ref(name: str, value: str) -> str:
    """Validate one workflow ref scalar shared by authoring surfaces."""

    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    try:
        _require_ref_segment(name, value)
    except ValueError as exc:
        raise ValueError(f"{name} has invalid ref format: {value!r}") from exc
    return value


def optional_ref(name: str, value: str | None) -> str | None:
    """Validate an optional workflow ref scalar."""

    if value is None:
        return None
    return require_ref(name, value)


def is_ref(value: object) -> bool:
    """Return whether ``value`` is a valid workflow ref scalar."""

    if not isinstance(value, str):
        return False
    try:
        require_ref("ref", value)
    except ValueError:
        return False
    return True


def is_manifest_hash(value: object) -> bool:
    """Return whether ``value`` is a canonical manifest hash."""

    return isinstance(value, str) and _MANIFEST_HASH_RE.fullmatch(value) is not None


def require_manifest_hash(name: str, value: str) -> str:
    """Validate a canonical manifest hash without changing its casing."""

    if not is_manifest_hash(value):
        raise ValueError(f"{name} must be 'sha256:' followed by 64 lowercase hex characters")
    return value


def as_import_ref(
    value: Any,
    *,
    node_id: str | None = None,
    field: str | None = None,
) -> ImportRef:
    """Return a durable ``ImportRef`` from a string, existing ref, or callable.

    Strings must use ``module:qualname`` format and resolve to an importable
    symbol.  Callables must be module-level or class/static functions.
    """

    if isinstance(value, ImportRef):
        try:
            return value.validate_importable()
        except RefDiagnosticError:
            raise
        except Exception as exc:  # noqa: BLE001 - import systems raise diverse errors.
            raise _unstable_ref_error(
                f"invalid import ref {value.spec!r}: {exc}",
                node_id=node_id,
                field=field,
            ) from exc
    if isinstance(value, str):
        try:
            import_ref = ImportRef.parse(value)
        except ValueError as exc:
            raise _unstable_ref_error(
                f"invalid import ref {value!r}: {exc}",
                node_id=node_id,
                field=field,
            ) from exc
        try:
            return import_ref.validate_importable()
        except RefDiagnosticError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _unstable_ref_error(
                f"invalid import ref {value!r}: {exc}",
                node_id=node_id,
                field=field,
            ) from exc
    return ImportRef.from_callable(value, node_id=node_id, field=field)


def as_hook_ref(
    value: Any,
    *,
    node_id: str,
    field: str,
) -> HookRef:
    """Return a durable ``HookRef`` from a string, ref, or callable.

    Rejects lambdas, closures, local functions, bound methods, callable
    instances, and bad import strings, naming the node/field in the diagnostic.
    """

    if isinstance(value, HookRef):
        return value
    if isinstance(value, ImportRef):
        try:
            return HookRef(value.validate_callable(node_id=node_id, field=field))
        except RefDiagnosticError:
            raise
        except Exception as exc:  # noqa: BLE001 - import systems raise diverse errors.
            raise _unstable_ref_error(
                f"invalid hook ref {value.spec!r}: {exc}",
                node_id=node_id,
                field=field,
            ) from exc
    if isinstance(value, str):
        try:
            import_ref = ImportRef.parse(value)
        except ValueError as exc:
            raise _unstable_ref_error(
                f"invalid hook ref {value!r}: {exc}",
                node_id=node_id,
                field=field,
            ) from exc
        try:
            return HookRef(import_ref.validate_callable(node_id=node_id, field=field))
        except RefDiagnosticError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _unstable_ref_error(
                f"invalid hook ref {value!r}: {exc}",
                node_id=node_id,
                field=field,
            ) from exc
    return HookRef(ImportRef.from_callable(value, node_id=node_id, field=field))


def as_optional_hook_ref(
    value: Any | None,
    *,
    node_id: str,
    field: str,
) -> HookRef | None:
    """Return a durable ``HookRef`` or ``None``."""

    if value is None:
        return None
    return as_hook_ref(value, node_id=node_id, field=field)


__all__ = [
    "EdgeRef",
    "HookRef",
    "ImportRef",
    "ManifestCoordinate",
    "ManifestCursor",
    "NodeRef",
    "RefDiagnosticError",
    "SourceRef",
    "SourceSpan",
    "ValueRef",
    "_require_ref_segment",
    "as_hook_ref",
    "as_import_ref",
    "as_optional_hook_ref",
    "canonical_alias",
    "is_manifest_hash",
    "is_ref",
    "manifest_coordinate",
    "optional_ref",
    "require_manifest_hash",
    "require_ref",
]
