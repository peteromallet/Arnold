"""Compatibility shim for the canonical porting emitter.

The canonical implementation lives in :mod:`vibecomfy.porting.emitter`.
This module remains so legacy ``vibecomfy.porting.emit.emitter`` imports keep
resolving while the old fork stays out of the execution path.
"""
from __future__ import annotations

from vibecomfy.porting import emitter as _canonical
from vibecomfy.porting.emitter import *  # noqa: F401,F403
from vibecomfy.porting.emitter import (  # noqa: F401
    RESERVED_WRAPPER_INPUT_NAMES,
    _CURATED_SCHEMA_DEFAULTS,
    _drain_lookup_warning_diagnostics,
    _emit_build_function,
    _identity_for_node,
    _identity_for_node_id,
    _node_local_arity_check,
    _node_local_class_defaults,
    _node_local_output_names,
    _record_lookup_warning,
    _resolve_graph_field_get_string,
    _ui_widget_aliases,
    _use_object_info_identities,
    _wrapper_module_for_class,
)

__all__ = list(getattr(_canonical, "__all__", ()))


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted({*globals(), *dir(_canonical)})
