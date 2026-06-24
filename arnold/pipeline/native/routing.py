"""Runtime routing helpers for native and graph pipeline execution.

The helpers in this module keep resume cursor precedence, explicit runtime
markers, and fresh-run defaults in one place so CLI state persistence and
executor dispatch make the same ownership decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from arnold.pipeline.native.checkpoint import classify_resume_cursor

RuntimeOwner = Literal["native", "graph"]

RUNTIME_NATIVE: RuntimeOwner = "native"
RUNTIME_GRAPH: RuntimeOwner = "graph"

@dataclass(frozen=True)
class RuntimeDispatchDecision:
    """Resolved runtime for a pipeline dispatch call."""

    runtime: RuntimeOwner
    resume: bool
    reason: str


def normalize_runtime_owner(value: Any) -> RuntimeOwner | None:
    """Return a canonical runtime owner for recognised marker values."""

    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {RUNTIME_NATIVE, RUNTIME_GRAPH}:
            return lowered  # type: ignore[return-value]
    return None


def runtime_owner_from_state(state: Mapping[str, Any] | None) -> RuntimeOwner | None:
    """Resolve an explicit runtime marker from in-memory state.

    New state uses ``runtime_envelope.runtime`` and ``meta.executor``.  The
    legacy ``_native_execution`` flag remains a compatibility alias only.
    """

    if not isinstance(state, Mapping):
        return None

    runtime_envelope = state.get("runtime_envelope")
    if isinstance(runtime_envelope, Mapping):
        owner = normalize_runtime_owner(runtime_envelope.get("runtime"))
        if owner is not None:
            return owner

    meta = state.get("meta")
    if isinstance(meta, Mapping):
        owner = normalize_runtime_owner(meta.get("executor"))
        if owner is not None:
            return owner

    native_alias = state.get("_native_execution")
    if native_alias is True:
        return RUNTIME_NATIVE
    if native_alias is False:
        return RUNTIME_GRAPH

    return None


def persisted_runtime_owner(artifact_root: str | Path) -> RuntimeOwner | None:
    """Read runtime ownership markers from ``state.json`` if available."""

    state_path = Path(artifact_root) / "state.json"
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    return runtime_owner_from_state(payload)


def explicit_runtime_owner(
    state: Mapping[str, Any] | None,
    *,
    artifact_root: str | Path | None = None,
) -> RuntimeOwner | None:
    """Resolve explicit runtime ownership from state, then persisted state."""

    owner = runtime_owner_from_state(state)
    if owner is not None:
        return owner
    if artifact_root is None:
        return None
    return persisted_runtime_owner(artifact_root)


def has_native_dispatch_capability(
    pipeline: Any,
    *,
    pipeline_key: str | None = None,
) -> bool:
    """Return whether *pipeline* can be executed by the native runtime.

    A pipeline is native-capable if it carries a first-class
    :class:`NativeProgram` on ``pipeline.native_program``, a legacy bare
    ``NativeProgram`` resource bundle, or a bundle exposing
    ``run_native_pipeline`` (e.g. a runner adapter).
    """

    from arnold.pipeline.native.ir import NativeProgram

    del pipeline_key

    if isinstance(getattr(pipeline, "native_program", None), NativeProgram):
        return True

    resource_bundles = tuple(getattr(pipeline, "resource_bundles", ()) or ())
    for bundle in resource_bundles:
        if isinstance(bundle, NativeProgram):
            return True
        if hasattr(bundle, "run_native_pipeline"):
            return True

    return False


def select_fresh_runtime_owner(
    pipeline: Any,
    *,
    state: Mapping[str, Any] | None = None,
    artifact_root: str | Path | None = None,
    pipeline_key: str | None = None,
) -> RuntimeOwner:
    """Resolve runtime ownership for a fresh dispatch or fresh state file."""

    explicit = explicit_runtime_owner(state, artifact_root=artifact_root)
    if explicit is not None:
        return explicit
    if has_native_dispatch_capability(pipeline, pipeline_key=pipeline_key):
        return RUNTIME_NATIVE
    return RUNTIME_GRAPH


def select_runtime_for_dispatch(
    pipeline: Any,
    *,
    state: Mapping[str, Any] | None,
    artifact_root: str | Path,
    pipeline_key: str,
) -> RuntimeDispatchDecision:
    """Resolve dispatch runtime with resume cursors taking precedence."""

    cursor_kind = classify_resume_cursor(artifact_root)
    if cursor_kind == RUNTIME_NATIVE:
        return RuntimeDispatchDecision(RUNTIME_NATIVE, True, "native_cursor")
    if cursor_kind == RUNTIME_GRAPH:
        return RuntimeDispatchDecision(RUNTIME_GRAPH, True, "graph_cursor")

    runtime = select_fresh_runtime_owner(
        pipeline,
        state=state,
        artifact_root=artifact_root,
        pipeline_key=pipeline_key,
    )
    if runtime == RUNTIME_NATIVE:
        return RuntimeDispatchDecision(RUNTIME_NATIVE, False, "native_fresh")
    return RuntimeDispatchDecision(RUNTIME_GRAPH, False, "graph_fresh")


__all__ = [
    "RUNTIME_GRAPH",
    "RUNTIME_NATIVE",
    "RuntimeDispatchDecision",
    "RuntimeOwner",
    "explicit_runtime_owner",
    "has_native_dispatch_capability",
    "normalize_runtime_owner",
    "persisted_runtime_owner",
    "runtime_owner_from_state",
    "select_fresh_runtime_owner",
    "select_runtime_for_dispatch",
]
