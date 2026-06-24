"""Package-local resume driver for evidence-pack (native-first).

M4 replaces the legacy continuation-pipeline resume with a thin wrapper around
:func:`arnold.pipeline.native.runtime.run_native_pipeline`.  The wrapper:

* validates that a native resume cursor exists and points at ``human_review``;
* optionally runs resume re-verification when a ``Suspension`` is supplied;
* seeds the resumed run with persisted ``evidence_pack`` / ``verdict`` paths
  plus the caller's ``human_input``;
* returns an :class:`EvidencePackResumeResult` matching the legacy contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native.checkpoint import read_native_cursor
from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipeline.resume_validation import (
    ResumeReverifyResult,
    reverify_resume_produces,
)
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.types import Suspension
from arnold.runtime.envelope import RuntimeEnvelope

__all__ = [
    "EvidencePackResumeError",
    "EvidencePackResumeResult",
    "resume_evidence_pack",
]


class EvidencePackResumeError(ValueError):
    """Raised when an evidence-pack resume request is structurally invalid."""


@dataclass(frozen=True)
class EvidencePackResumeResult:
    """Visible result of a package-owned resume attempt."""

    envelope: RuntimeEnvelope | None
    resumed: bool
    cursor: Mapping[str, Any]
    reverify: ResumeReverifyResult | None = None


def resume_evidence_pack(
    artifact_root: str | Path,
    *,
    human_input: Mapping[str, Any],
    envelope: RuntimeEnvelope | None = None,
    resume_cursor: Mapping[str, Any] | str | None = None,
    suspension: Suspension | None = None,
    schema_registry: ContractSchemaRegistry | None = None,
    extra_state: Mapping[str, Any] | None = None,
) -> EvidencePackResumeResult:
    """Resume an evidence-pack run from its persisted human-review cursor.

    The native runtime restores the working state from ``resume_cursor.json``
    and re-executes the ``human_review`` phase.  Caller-supplied ``human_input``
    is merged into that restored state so the phase resolves the gate instead
    of suspending again.
    """
    from arnold.pipelines.evidence_pack.pipeline import build_pipeline

    root = Path(artifact_root)

    cursor = _resolve_resume_cursor(root, resume_cursor)
    stage = cursor.get("stage")
    # Native cursors store a stable stage id like "evidence_pack__human_review__pc{N}".
    if stage is None or "human_review" not in str(stage):
        raise EvidencePackResumeError(
            f"evidence-pack resumes can only re-enter 'human_review'; got {stage!r}"
        )

    if not isinstance(human_input, Mapping):
        raise EvidencePackResumeError("human_input must be a mapping")

    reverify = None
    if suspension is not None:
        reverify = reverify_resume_produces(
            suspension,
            artifact_root=root,
            schema_registry=schema_registry,
            producer_stage="human_review",
        )
        if reverify.outcome == "invalid":
            if (
                reverify.declaration is not None
                and reverify.declaration.invalid_policy == "fail"
            ):
                detail = "resume re-verification failed"
                if isinstance(reverify.diagnostic, Mapping):
                    detail = str(reverify.diagnostic.get("detail") or detail)
                raise EvidencePackResumeError(detail)
            return EvidencePackResumeResult(
                envelope=envelope,
                resumed=False,
                cursor=cursor,
                reverify=reverify,
            )

    state = _continuation_state(root, human_input=human_input, extra_state=extra_state)
    program = build_pipeline().native_program
    if program is None:
        raise EvidencePackResumeError("evidence-pack pipeline has no native program")

    result = run_native_pipeline(
        program,
        artifact_root=root,
        resume=True,
        initial_state=state,
        initial_envelope=envelope,
    )

    return EvidencePackResumeResult(
        envelope=result.envelope,
        resumed=not result.suspended,
        cursor=cursor,
        reverify=reverify,
    )


def _resolve_resume_cursor(
    artifact_root: Path,
    resume_cursor: Mapping[str, Any] | str | None,
) -> dict[str, Any]:
    if resume_cursor is not None:
        if isinstance(resume_cursor, str):
            return {"stage": resume_cursor, "resume_cursor": None}
        return dict(resume_cursor)

    cursor = read_native_cursor(artifact_root)
    if cursor is None:
        raise EvidencePackResumeError(f"missing native resume cursor under {artifact_root}")
    return dict(cursor)


def _continuation_state(
    artifact_root: Path,
    *,
    human_input: Mapping[str, Any],
    extra_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "human_input": dict(human_input),
    }
    evidence_pack = artifact_root / "evidence_pack.json"
    verdict = artifact_root / "verdict.json"
    if evidence_pack.exists():
        state["evidence_pack"] = str(evidence_pack)
    if verdict.exists():
        state["verdict"] = str(verdict)
    if extra_state:
        state.update(dict(extra_state))
    return state
