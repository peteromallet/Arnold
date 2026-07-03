"""Resume helpers for the native-first evidence-pack pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native.checkpoint import (
    NativeCursorCorruptError,
    classify_resume_cursor,
    read_native_cursor,
)
from arnold.pipeline.native.runtime import NativeRuntimeError, run_native_pipeline
from arnold.pipeline.resume_validation import ResumeReverifyResult, reverify_resume_produces
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.types import HumanSuspension

from arnold_pipelines.evidence_pack.native import build_native_program


@dataclass(frozen=True)
class EvidencePackResumeResult:
    """Resume wrapper result for evidence-pack native resumes."""

    resumed: bool
    envelope: Any = None
    cursor: Mapping[str, Any] | None = None
    reverify: ResumeReverifyResult | None = None
    native_result: Any = None


class EvidencePackResumeError(Exception):
    """Raised when evidence-pack resume encounters an unrecoverable error."""


def _normalize_human_input(human_input: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(human_input, Mapping):
        raise EvidencePackResumeError("human_input must be a mapping with boolean approved")
    approved = human_input.get("approved")
    if not isinstance(approved, bool):
        raise EvidencePackResumeError("human_input must be a mapping with boolean approved")
    normalized = dict(human_input)
    normalized["choice"] = "emit" if approved else "failed"
    return normalized


def _load_resume_cursor(artifact_root: Path) -> dict[str, Any]:
    try:
        cursor_kind = classify_resume_cursor(artifact_root)
    except NativeCursorCorruptError as exc:
        raise EvidencePackResumeError(exc.detail) from exc

    if cursor_kind == "none":
        raise EvidencePackResumeError("missing native resume cursor")
    if cursor_kind != "native":
        raise EvidencePackResumeError(
            "missing native resume cursor: graph-born cursors are not supported"
        )

    try:
        cursor = read_native_cursor(artifact_root)
    except NativeCursorCorruptError as exc:
        raise EvidencePackResumeError(exc.detail) from exc

    if cursor is None:
        raise EvidencePackResumeError("missing native resume cursor")
    return cursor


def _validate_human_review_cursor(cursor: Mapping[str, Any]) -> None:
    native = cursor.get("native")
    if not isinstance(native, Mapping) or native.get("suspension_kind") != "human_gate":
        raise EvidencePackResumeError("resume cursor is not a suspended human-review cursor")

    artifact_stage = cursor.get("artifact_stage")
    stage = cursor.get("stage")
    if artifact_stage != "human_review" or not isinstance(stage, str) or "human_review" not in stage:
        raise EvidencePackResumeError("resume cursor must target human_review")


def _normalize_suspension(suspension: HumanSuspension | Mapping[str, Any] | None) -> HumanSuspension | None:
    if suspension is None:
        return None
    if isinstance(suspension, HumanSuspension):
        return suspension
    if isinstance(suspension, Mapping):
        return HumanSuspension.from_json(suspension)
    raise EvidencePackResumeError("suspension must be a HumanSuspension or mapping")


def resume_evidence_pack(
    artifact_root: str | Path,
    *,
    envelope: Any = None,
    human_input: Mapping[str, Any] | None = None,
    suspension: HumanSuspension | Mapping[str, Any] | None = None,
    resume_cursor: Mapping[str, Any] | None = None,
    extra_state: Mapping[str, Any] | None = None,
    schema_registry: ContractSchemaRegistry | None = None,
) -> EvidencePackResumeResult:
    """Resume a suspended evidence-pack pipeline run through the native runtime."""

    root = Path(artifact_root)
    normalized_human_input = _normalize_human_input(human_input)
    cursor = _load_resume_cursor(root)
    _validate_human_review_cursor(cursor)

    if resume_cursor is not None:
        if not isinstance(resume_cursor, Mapping):
            raise EvidencePackResumeError("resume_cursor must be a native cursor mapping")
        if dict(resume_cursor) != dict(cursor):
            raise EvidencePackResumeError("supplied resume_cursor does not match persisted cursor")

    normalized_suspension = _normalize_suspension(suspension)
    reverify: ResumeReverifyResult | None = None
    if normalized_suspension is not None:
        reverify = reverify_resume_produces(
            normalized_suspension,
            artifact_root=root,
            schema_registry=schema_registry,
            producer_stage="human_review",
        )
        if reverify.outcome == "invalid":
            return EvidencePackResumeResult(
                resumed=False,
                envelope=envelope,
                cursor=cursor,
                reverify=reverify,
            )

    initial_state = dict(extra_state or {})
    initial_state["human_input"] = normalized_human_input

    try:
        native_result = run_native_pipeline(
            build_native_program(),
            artifact_root=root,
            initial_state=initial_state,
            resume=True,
            human_input=normalized_human_input,
            initial_envelope=envelope,
        )
    except NativeRuntimeError as exc:
        raise EvidencePackResumeError(str(exc)) from exc

    return EvidencePackResumeResult(
        resumed=not bool(getattr(native_result, "suspended", False)),
        envelope=getattr(native_result, "envelope", envelope),
        cursor=cursor,
        reverify=reverify,
        native_result=native_result,
    )


__all__ = [
    "EvidencePackResumeError",
    "EvidencePackResumeResult",
    "resume_evidence_pack",
]
