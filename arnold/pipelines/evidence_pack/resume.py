"""Package-local resume driver for evidence-pack continuations.

The neutral executor does not own resume semantics. Evidence-pack resumes are
fresh continuation-pipeline runs seeded from durable artifacts under the
artifact root, with optional re-verification of a declared human suspension
before the continuation is allowed to proceed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline import run_pipeline
from arnold.pipeline.resume import read_resume_cursor
from arnold.pipeline.resume_validation import (
    ResumeReverifyResult,
    reverify_resume_produces,
)
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.types import Suspension
from arnold.pipelines.evidence_pack.hooks import EvidencePackHooks
from arnold.pipelines.evidence_pack.pipelines import build_continuation_pipeline
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

    envelope: RuntimeEnvelope
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

    This is intentionally package-local orchestration:

    * cursor resolution is limited to ``resume_cursor.json`` or an explicit
      caller-supplied cursor;
    * state is seeded from named package artifacts, not executor-local replay;
    * optional resume re-verification runs before the continuation pipeline;
    * the continuation pipeline is a normal fresh ``run_pipeline`` call.
    """

    root = Path(artifact_root)
    cursor = _resolve_resume_cursor(root, resume_cursor)
    stage = cursor.get("stage")
    if stage != "human_review":
        raise EvidencePackResumeError(
            f"evidence-pack resumes can only re-enter 'human_review'; got {stage!r}"
        )

    if not isinstance(human_input, Mapping):
        raise EvidencePackResumeError("human_input must be a mapping")

    if envelope is None:
        envelope = RuntimeEnvelope(
            plugin_id="evidence_pack_verifier",
            run_id=str(cursor.get("run_id") or "resume"),
            artifact_root=str(root),
        )

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
    run_pipeline(
        build_continuation_pipeline(),
        state,
        envelope,
        hooks=EvidencePackHooks(root),
    )
    return EvidencePackResumeResult(
        envelope=envelope,
        resumed=True,
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

    # Prefer a native-first resume cursor when available; otherwise fall back to
    # the legacy graph cursor shape so older tooling that overwrites the cursor
    # still produces a valid human_review gate check.
    try:
        from arnold.pipeline.native.checkpoint import read_native_cursor

        native_cursor = read_native_cursor(artifact_root)
        if native_cursor is not None:
            return dict(native_cursor)
    except Exception:
        pass

    cursor = read_resume_cursor(artifact_root)
    if cursor is None:
        raise EvidencePackResumeError(f"missing resume cursor under {artifact_root}")
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
