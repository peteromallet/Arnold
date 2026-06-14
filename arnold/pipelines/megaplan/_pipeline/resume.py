"""ResumeCursor — Sprint 5 Chunk D, third primitive.

Typed wrapper around the resume state legacy plans persist in
``state.json::resume_cursor``. Tied to the pipeline's stage names so
``resume_from(name)`` re-enters the pipeline at the right place.

Usage::

    cursor = ResumeCursor.load(plan_dir)
    if cursor:
        pipeline = pipeline.with_entry(cursor.stage)
        run_pipeline(pipeline, ctx, artifact_root=plan_dir)
    else:
        run_pipeline(pipeline, ctx, artifact_root=plan_dir)

    # After each stage:
    ResumeCursor(stage=node.name).save(plan_dir)

Sprint A addition: ``check_awaiting_user`` inspects ``awaiting_user.json``
so callers (e.g. ``handle_resume``) can dispatch to the human-gate resume
flow before falling through to ``state.json::resume_cursor`` recovery.

C3 addition: ``extract_suspended_contract_result`` reads the typed
``state.json::contract_result`` persisted by the executor, parses it with
``ContractResult.from_json()``, and returns only suspended contracts with
a usable ``Suspension``.  ``extract_typed_resume_metadata`` exposes
phase, pipeline/thread identity, choices, ``resume_input_schema``, and
decoded cursor data.  Both helpers fail soft — malformed, completed, or
failed-only data returns ``None`` so callers fall through to the next
resume source.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.types import HumanSuspension
from arnold.pipelines.megaplan._core.state import write_plan_state
from arnold.pipelines.megaplan._pipeline.types import Pipeline

COMPOSITE_SUSPENSION_KIND = "composite_suspension"
COMPOSITE_SUSPENSION_CURSOR_VERSION = 1


def load_resume_cursor_payload(plan_dir: Path) -> dict[str, Any] | None:
    path = Path(plan_dir) / "state.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    cursor = data.get("resume_cursor")
    if not isinstance(cursor, dict):
        return None
    return dict(cursor)


def is_composite_resume_cursor(cursor: Mapping[str, Any] | None) -> bool:
    if cursor is None:
        return False
    return cursor.get("kind") == COMPOSITE_SUSPENSION_KIND


def load_composite_resume_cursor(plan_dir: Path) -> dict[str, Any] | None:
    cursor = load_resume_cursor_payload(plan_dir)
    if is_composite_resume_cursor(cursor):
        return dict(cursor)
    # Fallback: try composite_resume_cursor.json via the generic persistence layer.
    # This keeps Megaplan coupling out of the generic module while recovering
    # composite cursors that were dual-written by save_composite_resume_cursor().
    from arnold.pipeline.resume import read_composite_resume_cursor

    return read_composite_resume_cursor(plan_dir)


def save_composite_resume_cursor(
    plan_dir: Path,
    *,
    children: Mapping[str, Any],
    version: int = COMPOSITE_SUSPENSION_CURSOR_VERSION,
    **extra: Any,
) -> Path:
    resolved_plan_dir = Path(plan_dir)
    payload: dict[str, Any] = {
        "kind": COMPOSITE_SUSPENSION_KIND,
        "version": version,
        "children": dict(children),
    }
    payload.update(extra)
    write_plan_state(
        resolved_plan_dir,
        mode="patch-key",
        key="resume_cursor",
        value=payload,
    )
    # Dual-write: also persist to composite_resume_cursor.json via the generic
    # persistence layer so the composite cursor can be recovered even when
    # state.json::resume_cursor is absent (e.g. after a partial migration or
    # manual state reset).
    from arnold.pipeline.resume import persist_composite_resume_cursor

    persist_composite_resume_cursor(
        resolved_plan_dir,
        children=dict(children),
        version=version,
        **extra,
    )
    return resolved_plan_dir / "state.json"


def extract_composite_child_resume_cursor(
    plan_dir: Path,
    child_id: str,
) -> Any | None:
    cursor = load_composite_resume_cursor(plan_dir)
    if cursor is None:
        return None
    children = cursor.get("children")
    if not isinstance(children, Mapping):
        return None
    return children.get(child_id)


def extract_all_composite_child_resume_cursors(plan_dir: Path) -> dict[str, Any]:
    cursor = load_composite_resume_cursor(plan_dir)
    if cursor is None:
        return {}
    children = cursor.get("children")
    if not isinstance(children, Mapping):
        return {}
    return {str(child_id): value for child_id, value in children.items()}


@dataclass(frozen=True)
class CompositeChildResumeTarget:
    child_id: str
    cursor: Any
    suspension: HumanSuspension
    pending_suspension: Mapping[str, Any]
    composite_cursor: Mapping[str, Any]


def extract_composite_child_resume_target(
    plan_dir: Path,
    child_id: str,
) -> CompositeChildResumeTarget | None:
    """Recover one targeted composite child and its serialized suspension.

    Composite resume uses two independent persisted surfaces: ``children``
    selects the opaque child cursor, while ``pending_suspensions`` carries the
    serialized suspension needed for declaration parsing.  A selected child
    without a suspension payload is invalid because treating it as no-op would
    bypass resume re-verification.
    """

    cursor = load_composite_resume_cursor(plan_dir)
    if cursor is None:
        return None
    children = cursor.get("children")
    if not isinstance(children, Mapping) or child_id not in children:
        return None

    pending = cursor.get("pending_suspensions")
    if not isinstance(pending, list):
        raise ValueError(
            f"composite child {child_id!r} is missing pending_suspensions; "
            "cannot recover resume suspension"
        )

    for entry in pending:
        if not isinstance(entry, Mapping) or entry.get("child_id") != child_id:
            continue
        suspension_payload = entry.get("suspension")
        if not isinstance(suspension_payload, Mapping):
            raise ValueError(
                f"composite child {child_id!r} is missing serialized suspension; "
                "cannot parse resume declaration"
            )
        return CompositeChildResumeTarget(
            child_id=child_id,
            cursor=children[child_id],
            suspension=HumanSuspension.from_json(suspension_payload),
            pending_suspension=entry,
            composite_cursor=cursor,
        )

    raise ValueError(
        f"composite child {child_id!r} has no pending_suspensions entry; "
        "cannot recover resume suspension"
    )


@dataclass(frozen=True)
class ResumeCursor:
    """Where the pipeline should re-enter on resume.

    ``stage`` names the Pipeline stage to start from. ``payload``
    carries anything extra a Step might need on resume (e.g. partial
    fan-out completion). The legacy ``state.json::resume_cursor``
    schema is preserved when loading + saving:

        {"phase": "<stage_name>", "retry_strategy": "...", ...}

    ``phase`` is the legacy key; ResumeCursor reads/writes it.
    """

    stage: str
    payload: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.payload is None:
            object.__setattr__(self, "payload", {})

    @classmethod
    def load(cls, plan_dir: Path) -> "ResumeCursor | None":
        cursor = load_resume_cursor_payload(plan_dir)
        if cursor is None or is_composite_resume_cursor(cursor):
            return None
        stage = cursor.get("phase") or cursor.get("stage")
        if not isinstance(stage, str):
            return None
        payload = {k: v for k, v in cursor.items() if k not in {"phase", "stage"}}
        return cls(stage=stage, payload=payload)

    def save(self, plan_dir: Path, *, overwrite_composite: bool = False) -> Path:
        resolved_plan_dir = Path(plan_dir)
        path = resolved_plan_dir / "state.json"
        existing_cursor = load_resume_cursor_payload(resolved_plan_dir)
        if is_composite_resume_cursor(existing_cursor) and not overwrite_composite:
            raise ValueError(
                "state.json::resume_cursor already contains a composite suspension "
                "cursor; call save_composite_resume_cursor() to preserve it or pass "
                "overwrite_composite=True to replace it intentionally"
            )
        write_plan_state(
            resolved_plan_dir,
            mode="patch-key",
            key="resume_cursor",
            value={"phase": self.stage, **dict(self.payload)},
        )
        # When overwriting a composite cursor, also remove the dual-written
        # composite_resume_cursor.json so the fallback does not resurrect the
        # stale composite cursor after the legacy overwrite.
        if overwrite_composite:
            composite_json = resolved_plan_dir / "composite_resume_cursor.json"
            try:
                composite_json.unlink()
            except FileNotFoundError:
                pass
        return path

    def with_payload(self, **overrides: Any) -> "ResumeCursor":
        merged = {**dict(self.payload), **overrides}
        return ResumeCursor(stage=self.stage, payload=merged)


def with_entry(pipeline: Pipeline, stage_name: str) -> Pipeline:
    """Return a copy of ``pipeline`` whose entry is ``stage_name``."""
    if stage_name not in pipeline.stages:
        raise KeyError(
            f"stage {stage_name!r} not in pipeline; available: "
            f"{sorted(pipeline.stages)}"
        )
    return Pipeline(
        stages=pipeline.stages,
        entry=stage_name,
        overlays=pipeline.overlays,
    )


def check_awaiting_user(plan_dir: Path) -> dict[str, Any] | None:
    """Check if ``plan_dir`` contains an ``awaiting_user.json`` pause file.

    Returns the parsed data if present and valid, ``None`` otherwise.
    This is the dispatch gate — callers check this before falling through
    to ``state.json::resume_cursor`` recovery.
    """
    awaiting_path = Path(plan_dir) / "awaiting_user.json"
    if not awaiting_path.exists():
        return None
    try:
        data = json.loads(awaiting_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


# ---------------------------------------------------------------------------
# C3: Typed suspended-contract extraction helpers
# ---------------------------------------------------------------------------


def _load_raw_contract_result(plan_dir: Path) -> dict[str, Any] | None:
    """Load the raw ``contract_result`` dict from ``state.json``.

    Returns ``None`` when the file is absent, unparseable, or the key is
    missing or not a dict — every failure mode maps to ``None`` so callers
    fall through to the next resume source.
    """
    path = Path(plan_dir) / "state.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    contract_result = data.get("contract_result")
    if not isinstance(contract_result, dict):
        return None
    return dict(contract_result)


def _decode_json_cursor(raw: str | None) -> Any:
    """Decode a JSON-encoded cursor string, preserving opaque non-JSON values.

    If *raw* is a JSON string, parse and return the resulting object.
    If *raw* is not valid JSON, return the original string unchanged so
    opaque cursors survive round-tripping.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def extract_suspended_contract_result(plan_dir: Path) -> Any | None:
    """Parse ``state.json::contract_result`` and return only suspended contracts.

    Returns the parsed :class:`~arnold.pipeline.ContractResult` when:
    * The raw ``contract_result`` key is present and valid JSON.
    * :meth:`ContractResult.from_json` succeeds without raising.
    * The ``status`` is ``SUSPENDED``.
    * A usable :class:`~arnold.pipeline.Suspension` is attached.

    Returns ``None`` (fail-soft) for every other case — missing key,
    malformed JSON, schema-version mismatch, completed/failed-only status,
    or suspended-but-no-suspension.
    """
    raw = _load_raw_contract_result(plan_dir)
    if raw is None:
        return None

    from arnold.pipeline import ContractResult, ContractStatus

    try:
        contract = ContractResult.from_json(raw)
    except (ValueError, TypeError, KeyError):
        return None

    if contract.status is not ContractStatus.SUSPENDED:
        return None

    if contract.suspension is None:
        return None

    return contract


@dataclass(frozen=True)
class TypedResumeMetadata:
    """Structured resume metadata extracted from a typed suspended contract.

    Every field is derived from the serialized :class:`ContractResult`
    and its :class:`Suspension`; absent fields default to ``None``.
    """

    contract: Any
    """The full :class:`~arnold.pipeline.ContractResult` object."""

    phase: str | None
    """Pipeline stage to re-enter, decoded from ``Suspension.resume_cursor``."""

    pipeline: str | None
    """Pipeline / thread identity from ``Suspension.thread_ref``."""

    choices: list[str] | None
    """Human-gate choices from ``resume_input_schema`` (if an enum schema)."""

    resume_input_schema: Mapping[str, Any]
    """The raw ``Suspension.resume_input_schema`` dict."""

    cursor_data: Any
    """Decoded ``Suspension.resume_cursor`` (JSON-parsed or opaque string)."""

    suspension_kind: str | None
    """The ``Suspension.kind`` value (e.g. ``\"human\"``)."""

    awaitable: str | None
    """The ``Suspension.awaitable`` value."""


def extract_typed_resume_metadata(plan_dir: Path) -> TypedResumeMetadata | None:
    """Extract structured resume metadata from a typed suspended contract.

    Returns a :class:`TypedResumeMetadata` when a valid suspended
    ``contract_result`` exists; returns ``None`` otherwise so callers
    fall through to the next resume source (e.g. ``awaiting_user.json``
    or composite cursor).
    """
    contract = extract_suspended_contract_result(plan_dir)
    if contract is None:
        return None

    suspension = contract.suspension
    cursor_str = suspension.resume_cursor if suspension else None
    cursor_data = _decode_json_cursor(cursor_str)

    # Derive ``phase`` from the decoded cursor, with the known legacy key
    # ``phase`` taking priority over ``stage``.
    phase: str | None = None
    if isinstance(cursor_data, Mapping):
        phase = cursor_data.get("phase") or cursor_data.get("stage")
        if not isinstance(phase, str) or not phase:
            phase = None

    # Derive ``choices`` from resume_input_schema when it uses JSON Schema
    # enum pattern.  Only the ``choice`` property is inspected.
    choices: list[str] | None = None
    resume_input_schema: Mapping[str, Any] = (
        dict(suspension.resume_input_schema)
        if suspension and isinstance(suspension.resume_input_schema, Mapping)
        else {}
    )
    if isinstance(resume_input_schema, Mapping):
        props = resume_input_schema.get("properties")
        if isinstance(props, Mapping):
            choice_prop = props.get("choice")
            if isinstance(choice_prop, Mapping):
                enum = choice_prop.get("enum")
                if isinstance(enum, list) and all(isinstance(c, str) for c in enum):
                    choices = [str(c) for c in enum]

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
