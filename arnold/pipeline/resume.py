"""Pipeline resume-cursor persistence helpers.

The executor and package hooks can publish a small, opaque cursor document for
external tooling to discover where a suspended pipeline should re-enter. The
helper owns only durable JSON persistence; it does not interpret cursor bodies.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal, Mapping

from arnold.runtime.state_persistence import atomic_write_json

RESUME_CURSOR_FILENAME = "resume_cursor.json"
COMPOSITE_RESUME_CURSOR_FILENAME = "composite_resume_cursor.json"

ResumeCursorRuntime = str
ResumeSurfaceSource = Literal[
    "state_resume_cursor",
    "typed_contract",
    "composite_resume_cursor",
    "awaiting_user",
    "resume_cursor",
    "none",
]


@dataclass(frozen=True)
class TypedResumeMetadata:
    contract: Any
    phase: str | None
    pipeline: str | None
    choices: list[str] | None
    resume_input_schema: Mapping[str, Any]
    cursor_data: Any
    suspension_kind: str | None
    awaitable: str | None


@dataclass(frozen=True)
class ResumeSurfaceObservation:
    source: ResumeSurfaceSource
    present: bool
    valid: bool
    kind: str
    path: str | None = None
    payload: Any = None
    diagnostic: str | None = None


@dataclass(frozen=True)
class ResolvedResumeSurface:
    source: ResumeSurfaceSource
    kind: str
    blocked: bool
    payload: Any = None
    path: str | None = None
    diagnostic: str | None = None
    observations: tuple[ResumeSurfaceObservation, ...] = ()


def _is_valid_relative_cursor_path(value: Any) -> bool:
    """Return whether *value* is a safe relative child cursor path."""

    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    if path.is_absolute():
        return False
    return ".." not in path.parts


def _has_valid_composite_parent_child_shape(payload: dict[str, Any]) -> bool:
    """Return whether *payload* carries a valid parent/child composite frame."""

    composite = payload.get("composite")
    if composite is None:
        return True
    if not isinstance(composite, dict):
        return False
    if composite.get("kind") != "parent_child":
        return False

    parent = composite.get("parent")
    child = composite.get("child")
    if not isinstance(parent, dict) or not isinstance(child, dict):
        return False

    if not isinstance(parent.get("pc"), int):
        return False
    run_path = parent.get("run_path")
    if run_path is not None and not isinstance(run_path, str):
        return False
    path_stack = parent.get("path_stack")
    if path_stack is not None and not isinstance(path_stack, list):
        return False
    if not isinstance(parent.get("state"), dict):
        return False
    if not isinstance(parent.get("stages"), list):
        return False
    if not isinstance(parent.get("loops"), dict):
        return False
    if not isinstance(parent.get("frames"), dict):
        return False
    cursor_id = parent.get("cursor_id")
    if cursor_id is not None and not isinstance(cursor_id, str):
        return False

    if not _is_valid_relative_cursor_path(child.get("cursor_path")):
        return False
    child_run_path = child.get("run_path")
    if child_run_path is not None and not isinstance(child_run_path, str):
        return False
    call_site_path = child.get("call_site_path")
    if call_site_path is not None:
        if not isinstance(call_site_path, (list, tuple)):
            return False
        if any(not isinstance(segment, str) or not segment for segment in call_site_path):
            return False

    return True


def classify_resume_cursor_payload(payload: Any) -> ResumeCursorRuntime:
    """Classify a decoded resume cursor payload by runtime ownership.

    Returns ``"native"`` when the payload carries a valid additive native
    cursor, ``"graph"`` when it is a graph-era cursor with no native payload,
    ``"corrupt_native"`` when the payload claims native ownership but the
    native discriminator is malformed, and ``"none"`` when no cursor payload
    is available.
    """

    if not isinstance(payload, dict):
        return "none"

    native = payload.get("native")
    if native is None:
        return "graph"
    if not isinstance(native, dict):
        return "corrupt_native"
    if not isinstance(native.get("pc"), int):
        return "corrupt_native"
    if not isinstance(native.get("version"), int):
        return "corrupt_native"
    if not _has_valid_composite_parent_child_shape(payload):
        return "corrupt_native"
    return "native"


def persist_resume_cursor(
    artifact_root: str | Path,
    *,
    stage: str,
    resume_cursor: str | None = None,
    **extra: Any,
) -> Path:
    """Atomically write ``resume_cursor.json`` under *artifact_root*."""

    path = Path(artifact_root) / RESUME_CURSOR_FILENAME
    payload: dict[str, Any] = {
        "stage": stage,
        "resume_cursor": resume_cursor,
    }
    payload.update(extra)
    atomic_write_json(path, payload)
    return path


def read_resume_cursor(artifact_root: str | Path) -> dict[str, Any] | None:
    """Read ``resume_cursor.json``; return ``None`` for absent or malformed data."""

    path = Path(artifact_root) / RESUME_CURSOR_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def read_state_resume_cursor(artifact_root: str | Path) -> dict[str, Any] | None:
    """Read ``state.json::resume_cursor`` when it is a JSON object."""

    data = _read_json_object(Path(artifact_root) / "state.json")
    if not isinstance(data, dict):
        return None
    cursor = data.get("resume_cursor")
    if not isinstance(cursor, dict):
        return None
    return dict(cursor)


def persist_composite_resume_cursor(
    artifact_root: str | Path,
    *,
    children: dict[str, Any],
    version: int = 1,
    **extra: Any,
) -> Path:
    """Atomically write a fan-out/composite resume cursor document."""

    path = Path(artifact_root) / COMPOSITE_RESUME_CURSOR_FILENAME
    payload: dict[str, Any] = {
        "kind": "composite_suspension",
        "version": version,
        "children": children,
    }
    payload.update(extra)
    atomic_write_json(path, payload)
    return path


def read_composite_resume_cursor(artifact_root: str | Path) -> dict[str, Any] | None:
    """Read ``composite_resume_cursor.json``; return ``None`` if invalid."""

    path = Path(artifact_root) / COMPOSITE_RESUME_CURSOR_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def read_awaiting_user_checkpoint(artifact_root: str | Path) -> dict[str, Any] | None:
    """Read ``awaiting_user.json`` when present and valid."""

    data = _read_json_object(Path(artifact_root) / "awaiting_user.json")
    return dict(data) if isinstance(data, dict) else None


def extract_suspended_contract_result(artifact_root: str | Path) -> Any | None:
    """Return the suspended ``contract_result`` from ``state.json``, if any."""

    data = _read_json_object(Path(artifact_root) / "state.json")
    if not isinstance(data, dict):
        return None
    contract_result = data.get("contract_result")
    if not isinstance(contract_result, dict):
        return None

    from arnold.pipeline.types import ContractResult, ContractStatus

    try:
        contract = ContractResult.from_json(contract_result)
    except (ValueError, TypeError, KeyError):
        return None
    if contract.status is not ContractStatus.SUSPENDED:
        return None
    if contract.suspension is None:
        return None
    return contract


def extract_typed_resume_metadata(artifact_root: str | Path) -> TypedResumeMetadata | None:
    """Extract typed resume metadata from ``state.json::contract_result``."""

    contract = extract_suspended_contract_result(artifact_root)
    if contract is None:
        return None

    suspension = contract.suspension
    cursor_data = _decode_json_cursor(suspension.resume_cursor if suspension else None)

    phase: str | None = None
    if isinstance(cursor_data, Mapping):
        phase = cursor_data.get("phase") or cursor_data.get("stage")
        if not isinstance(phase, str) or not phase:
            phase = None

    choices: list[str] | None = None
    resume_input_schema: Mapping[str, Any] = (
        dict(suspension.resume_input_schema)
        if suspension and isinstance(suspension.resume_input_schema, Mapping)
        else {}
    )
    props = resume_input_schema.get("properties")
    if isinstance(props, Mapping):
        choice_prop = props.get("choice")
        if isinstance(choice_prop, Mapping):
            enum = choice_prop.get("enum")
            if isinstance(enum, list) and all(isinstance(choice, str) for choice in enum):
                choices = [str(choice) for choice in enum]

    return TypedResumeMetadata(
        contract=contract,
        phase=phase,
        pipeline=suspension.thread_ref if suspension else None,
        choices=choices,
        resume_input_schema=resume_input_schema,
        cursor_data=cursor_data,
        suspension_kind=suspension.kind if suspension else None,
        awaitable=suspension.awaitable if suspension else None,
    )


def resolve_resume_surface(artifact_root: str | Path) -> ResolvedResumeSurface:
    """Inspect shared resume surfaces and return the first authoritative one.

    Precedence matches the existing plan-owned resume chain:
    ``state.json::resume_cursor`` -> typed suspended ``contract_result`` ->
    ``composite_resume_cursor.json`` -> ``awaiting_user.json`` ->
    ``resume_cursor.json``.
    """

    root = Path(artifact_root)
    observations = (
        _inspect_state_resume_cursor(root),
        _inspect_typed_contract(root),
        _inspect_composite_resume_cursor(root),
        _inspect_awaiting_user(root),
        _inspect_resume_cursor(root),
    )

    for observation in observations:
        if not observation.present:
            continue
        return ResolvedResumeSurface(
            source=observation.source,
            kind=observation.kind,
            blocked=not observation.valid,
            payload=observation.payload,
            path=observation.path,
            diagnostic=observation.diagnostic,
            observations=observations,
        )

    return ResolvedResumeSurface(
        source="none",
        kind="none",
        blocked=False,
        observations=observations,
    )


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(raw) if isinstance(raw, dict) else None


def _read_json_payload(path: Path) -> tuple[bool, Any, str | None]:
    if not path.exists():
        return False, None, None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return True, None, f"{path.name} is not readable JSON: {exc}"
    if not isinstance(raw, dict):
        return True, raw, f"{path.name} must contain a JSON object"
    return True, raw, None


def _decode_json_cursor(raw: str | None) -> Any:
    if raw is None or not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _inspect_state_resume_cursor(root: Path) -> ResumeSurfaceObservation:
    path = root / "state.json"
    present, payload, diagnostic = _read_json_payload(path)
    if not present:
        return ResumeSurfaceObservation(
            source="state_resume_cursor",
            present=False,
            valid=False,
            kind="none",
            path=str(path),
        )
    if diagnostic is not None:
        return ResumeSurfaceObservation(
            source="state_resume_cursor",
            present=True,
            valid=False,
            kind="invalid_state",
            path=str(path),
            diagnostic=diagnostic,
        )
    assert isinstance(payload, dict)
    cursor = payload.get("resume_cursor")
    if cursor is None:
        return ResumeSurfaceObservation(
            source="state_resume_cursor",
            present=False,
            valid=False,
            kind="none",
            path=str(path),
        )
    if not isinstance(cursor, dict):
        return ResumeSurfaceObservation(
            source="state_resume_cursor",
            present=True,
            valid=False,
            kind="invalid_state_resume_cursor",
            path=str(path),
            payload=cursor,
            diagnostic="state.json::resume_cursor must be a JSON object",
        )
    return ResumeSurfaceObservation(
        source="state_resume_cursor",
        present=True,
        valid=True,
        kind="state_resume_cursor",
        path=str(path),
        payload=dict(cursor),
    )


def _inspect_typed_contract(root: Path) -> ResumeSurfaceObservation:
    path = root / "state.json"
    metadata = extract_typed_resume_metadata(root)
    if metadata is None:
        return ResumeSurfaceObservation(
            source="typed_contract",
            present=False,
            valid=False,
            kind="none",
            path=str(path),
        )
    return ResumeSurfaceObservation(
        source="typed_contract",
        present=True,
        valid=True,
        kind="typed_contract",
        path=str(path),
        payload=metadata,
    )


def _inspect_composite_resume_cursor(root: Path) -> ResumeSurfaceObservation:
    path = root / COMPOSITE_RESUME_CURSOR_FILENAME
    present, payload, diagnostic = _read_json_payload(path)
    if not present:
        return ResumeSurfaceObservation(
            source="composite_resume_cursor",
            present=False,
            valid=False,
            kind="none",
            path=str(path),
        )
    if diagnostic is not None:
        return ResumeSurfaceObservation(
            source="composite_resume_cursor",
            present=True,
            valid=False,
            kind="invalid_composite_resume_cursor",
            path=str(path),
            diagnostic=diagnostic,
        )
    assert isinstance(payload, dict)
    if payload.get("kind") != "composite_suspension":
        return ResumeSurfaceObservation(
            source="composite_resume_cursor",
            present=True,
            valid=False,
            kind="invalid_composite_resume_cursor",
            path=str(path),
            payload=payload,
            diagnostic="composite_resume_cursor.json must declare kind='composite_suspension'",
        )
    return ResumeSurfaceObservation(
        source="composite_resume_cursor",
        present=True,
        valid=True,
        kind="composite_resume_cursor",
        path=str(path),
        payload=payload,
    )


def _inspect_awaiting_user(root: Path) -> ResumeSurfaceObservation:
    path = root / "awaiting_user.json"
    present, payload, diagnostic = _read_json_payload(path)
    if not present:
        return ResumeSurfaceObservation(
            source="awaiting_user",
            present=False,
            valid=False,
            kind="none",
            path=str(path),
        )
    if diagnostic is not None:
        return ResumeSurfaceObservation(
            source="awaiting_user",
            present=True,
            valid=False,
            kind="invalid_awaiting_user",
            path=str(path),
            diagnostic=diagnostic,
        )
    return ResumeSurfaceObservation(
        source="awaiting_user",
        present=True,
        valid=True,
        kind="awaiting_user",
        path=str(path),
        payload=payload,
    )


def _inspect_resume_cursor(root: Path) -> ResumeSurfaceObservation:
    path = root / RESUME_CURSOR_FILENAME
    present, payload, diagnostic = _read_json_payload(path)
    if not present:
        return ResumeSurfaceObservation(
            source="resume_cursor",
            present=False,
            valid=False,
            kind="none",
            path=str(path),
        )
    if diagnostic is not None:
        return ResumeSurfaceObservation(
            source="resume_cursor",
            present=True,
            valid=False,
            kind="invalid_resume_cursor",
            path=str(path),
            diagnostic=diagnostic,
        )
    runtime = classify_resume_cursor_payload(payload)
    if runtime == "corrupt_native":
        return ResumeSurfaceObservation(
            source="resume_cursor",
            present=True,
            valid=False,
            kind="corrupt_native",
            path=str(path),
            payload=payload,
            diagnostic="resume_cursor.json claims native ownership but the native payload is invalid",
        )
    return ResumeSurfaceObservation(
        source="resume_cursor",
        present=True,
        valid=True,
        kind=f"{runtime}_resume_cursor",
        path=str(path),
        payload=payload,
    )


__all__ = [
    "COMPOSITE_RESUME_CURSOR_FILENAME",
    "RESUME_CURSOR_FILENAME",
    "ResolvedResumeSurface",
    "ResumeSurfaceObservation",
    "TypedResumeMetadata",
    "classify_resume_cursor_payload",
    "extract_suspended_contract_result",
    "extract_typed_resume_metadata",
    "persist_composite_resume_cursor",
    "persist_resume_cursor",
    "read_awaiting_user_checkpoint",
    "read_composite_resume_cursor",
    "read_resume_cursor",
    "read_state_resume_cursor",
    "resolve_resume_surface",
]
