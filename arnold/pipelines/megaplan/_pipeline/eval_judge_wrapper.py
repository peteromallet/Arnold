"""M5 Evaluand wrapper for the deterministic demo clarity judge."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Mapping

from arnold.pipelines.megaplan._pipeline.demo_judges import JudgeClarity
from arnold.pipelines.megaplan._pipeline.judge_manifest import EVALUAND_RECORD_CONTENT_TYPE
from arnold.pipelines.megaplan._pipeline.types import PipelineVerdict, Port, PortRef, StepContext, StepResult
from arnold.pipelines.megaplan.observability import EvaluandRecord, write_evaluand_event


M5_WRAPPER_EVAL_NAME = "m5-wrapper-eval"
M5_WRAPPER_API_VERSION = "2026-05-31"
M5_WRAPPER_MODEL_IDENTITY = "model:deterministic-demo-clarity"
M5_WRAPPER_PIECE_VERSION = (
    "cdcc4c21c0e704028a3687d4817e517b62bce748f534b83f33080ee083ed1b6b"
)
M5_WRAPPER_RUBRIC_VERSION = (
    "9d8038c4693e8a04c5285b4bdd89b1c4f2c24f21bbbb84eb31c3f04bbf9cb1bd"
)
M5_WRAPPER_JUDGE_VERSION = (
    "fd0b5569af258678bd838da90bcce5c26648d7e420c520e192a5b77568525cd1"
)


def unified_evaluand_on() -> bool:
    """Return whether the M5 Evaluand event/artifact path is enabled."""

    return os.environ.get("UNIFIED_EVALUAND") == "1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_path(path: Path) -> dict[str, str]:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        digest = _sha256_text(str(path))
    return {"path": str(path), "sha256": digest}


def input_set_hash(inputs: Mapping[str, Path]) -> str:
    """Return a deterministic hash over the judge input labels and contents."""

    entries = [
        {"label": label, **_hash_path(Path(path))}
        for label, path in sorted(inputs.items(), key=lambda item: item[0])
    ]
    return _sha256_text(_canonical_json({"inputs": entries}))


def _run_id(ctx: StepContext) -> str:
    if isinstance(ctx.state, Mapping):
        for key in ("run_id", "name"):
            value = ctx.state.get(key)
            if value:
                return str(value)
    return f"{ctx.mode}:{Path(ctx.plan_dir).name}"


def _record_payload(run_id: str, record: EvaluandRecord) -> dict[str, Any]:
    payload = asdict(record)
    payload["run_id"] = run_id
    payload["attribution_key"] = list(record.attribution_key(strict=True))
    return payload


class EvaluandClarityJudge:
    """Flag-compatible wrapper around :class:`JudgeClarity`.

    With ``UNIFIED_EVALUAND`` unset, this returns the legacy demo
    ``PipelineVerdict(score=...)`` result unchanged. With the flag on, it also
    writes an attributable Evaluand event and an evaluand-record JSON artifact.
    """

    name = M5_WRAPPER_EVAL_NAME
    kind = "judge"
    prompt_key = None
    slot = None
    consumes = (PortRef("candidate", "text/markdown"),)
    produces = (Port("evaluand", EVALUAND_RECORD_CONTENT_TYPE),)

    def __init__(self, legacy_judge: JudgeClarity | None = None) -> None:
        self._legacy_judge = legacy_judge or JudgeClarity()

    def run(self, ctx: StepContext) -> StepResult:
        legacy_ctx = ctx
        if "doc" not in ctx.inputs and "candidate" in ctx.inputs:
            legacy_ctx = replace(ctx, inputs={"doc": Path(ctx.inputs["candidate"])})
        legacy_result = self._legacy_judge.run(legacy_ctx)
        if not unified_evaluand_on():
            return legacy_result

        if legacy_result.verdict is None:
            raise ValueError("EvaluandClarityJudge requires a legacy verdict score")

        run_id = _run_id(ctx)
        record = EvaluandRecord(
            judge_version=M5_WRAPPER_JUDGE_VERSION,
            rubric_version=M5_WRAPPER_RUBRIC_VERSION,
            input_set_hash=input_set_hash(ctx.inputs),
            score=float(legacy_result.verdict.score),
            piece_version=M5_WRAPPER_PIECE_VERSION,
            provenance={
                "source": "demo_judges.JudgeClarity",
                "wrapper": self.name,
                "mode": ctx.mode,
                "input_labels": sorted(ctx.inputs),
            },
            taint=() if ctx.envelope.taint == "clean" else (ctx.envelope.taint,),
        )

        artifact_path = Path(ctx.plan_dir) / "judges" / self.name / "evaluand-record.json"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(_record_payload(run_id, record), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_evaluand_event(
            run_id,
            record,
            plan_dir=ctx.plan_dir,
            phase="judge",
            scope=self.name,
            idempotency_key=f"{self.name}:{run_id}:{record.input_set_hash}",
        )

        outputs = dict(legacy_result.outputs)
        outputs["evaluand"] = artifact_path
        state_patch = dict(legacy_result.state_patch)
        state_patch["evaluand_record_path"] = str(artifact_path)
        return StepResult(
            outputs=outputs,
            verdict=PipelineVerdict(
                score=float(legacy_result.verdict.score),
                flags=tuple(legacy_result.verdict.flags),
                notes=legacy_result.verdict.notes,
                payload=dict(legacy_result.verdict.payload),
                recommendation=legacy_result.verdict.recommendation,
                override=legacy_result.verdict.override,
            ),
            next=legacy_result.next,
            state_patch=state_patch,
            envelope=legacy_result.envelope,
            contract_result=legacy_result.contract_result,
        )


__all__ = [
    "EvaluandClarityJudge",
    "M5_WRAPPER_API_VERSION",
    "M5_WRAPPER_EVAL_NAME",
    "M5_WRAPPER_JUDGE_VERSION",
    "M5_WRAPPER_MODEL_IDENTITY",
    "M5_WRAPPER_PIECE_VERSION",
    "M5_WRAPPER_RUBRIC_VERSION",
    "input_set_hash",
    "unified_evaluand_on",
]
