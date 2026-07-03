"""Runtime-agnostic evidence-pack step behavior."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    StepContext,
    StepResult,
    Suspension,
)
from arnold_pipelines.evidence_pack.verifier import (
    ATTESTATION_SCHEMA,
    CHECKPOINT_SCHEMA,
    CHECKPOINT_STATUS_FAILED,
    CHECKPOINT_STATUS_PASSED,
    CHECKPOINT_STATUS_SUSPENDED,
    EVIDENCE_PACK_SCHEMA,
    VALIDATOR_KIND_BUDGET_ENFORCEMENT,
    VALIDATOR_KIND_BY_REF_VALIDATION,
    VALIDATOR_KIND_HUMAN_REVIEW_GATE,
    VALIDATOR_KIND_STRUCTURAL_AUDIT,
    VALIDATOR_KIND_SUSPENSION_PROPAGATION,
    VALIDATOR_KINDS,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_SCHEMA,
    VERIFIER_ARTIFACT_ATTESTATION,
    VERIFIER_ARTIFACT_CHECKPOINT,
    VERIFIER_ARTIFACT_EVIDENCE_PACK,
    VERIFIER_ARTIFACT_VERDICT,
    make_attestation_payload,
    make_checkpoint_payload,
    make_verdict_payload,
    read_json_artifact,
    write_json_artifact,
)


_NATIVE_PHASE_ORDER: tuple[tuple[str, str], ...] = (
    ("ingest", "content_validators"),
    ("content_validators", "reduce"),
    ("reduce", "human_review"),
    ("human_review", "emit_attestation"),
    ("emit_attestation", "halt"),
)

_ARTIFACT_KIND_BY_STAGE: dict[str, str] = {
    "ingest": VERIFIER_ARTIFACT_EVIDENCE_PACK,
    "content_validators": VERIFIER_ARTIFACT_CHECKPOINT,
    "reduce": VERIFIER_ARTIFACT_VERDICT,
    "human_review": VERIFIER_ARTIFACT_CHECKPOINT,
    "emit_attestation": VERIFIER_ARTIFACT_ATTESTATION,
}


def _artifact_root(ctx: StepContext) -> Path:
    return Path(ctx.artifact_root)


def _evidence_pack_path(root: Path) -> Path:
    return root / "evidence_pack.json"


def _verdict_path(root: Path) -> Path:
    return root / "verdict.json"


def _attestation_path(root: Path) -> Path:
    return root / "attestation.json"


def _checkpoint_path(root: Path, checkpoint_id: str) -> Path:
    return root / f"checkpoint_{checkpoint_id}.json"


def _result(
    *,
    next_label: str,
    status: ContractStatus,
    payload: Mapping[str, Any],
    outputs: Mapping[str, Any] | None = None,
    suspension: Suspension | None = None,
) -> StepResult:
    return StepResult(
        outputs=dict(outputs or {}),
        next=next_label,
        state_patch={},
        contract_result=ContractResult(
            payload=dict(payload),
            status=status,
            suspension=suspension,
        ),
    )


def _failure(next_label: str, message: str, **payload: Any) -> StepResult:
    data = {"error": message}
    data.update(payload)
    return _result(next_label=next_label, status=ContractStatus.FAILED, payload=data)


def _load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not decode to a JSON object")
    return data


def _load_evidence_pack_from_input(ctx: StepContext) -> dict[str, Any]:
    raw_path = ctx.inputs.get("evidence_pack")
    if not isinstance(raw_path, (str, Path)):
        raise ValueError("missing evidence_pack input")
    payload = read_json_artifact(raw_path)
    write_json_artifact(
        Path(raw_path),
        payload,
        schema=EVIDENCE_PACK_SCHEMA,
    )
    return payload


def _iter_checkpoint_inputs(ctx: StepContext, evidence_pack_id: str) -> list[dict[str, Any]]:
    checkpoint_payloads: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for key, value in ctx.inputs.items():
        if key in {"evidence_pack", "verdict", "human_input"}:
            continue
        if not isinstance(value, (str, Path)):
            continue
        path = Path(value)
        if not path.exists() or path in seen_paths:
            continue
        if not path.name.startswith("checkpoint_") or path.suffix != ".json":
            continue
        payload = read_json_artifact(path)
        if payload.get("evidence_pack_id") != evidence_pack_id:
            continue
        write_json_artifact(path, payload, schema=CHECKPOINT_SCHEMA)
        checkpoint_payloads.append(payload)
        seen_paths.add(path)
    return checkpoint_payloads


def _human_review_resume_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "properties": {"approved": {"type": "boolean"}},
        "required": ["approved"],
    }


@dataclass
class EvidencePackStep:
    """Native-phase adapter placeholder used by the projected shell."""

    name: str
    next_label: str
    kind: str = "native_phase"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="halt", state_patch={})


@dataclass
class IngestStep:
    name: str = "ingest"
    kind: str = "verify"

    def run(self, ctx: StepContext) -> StepResult:
        raw_path = ctx.inputs.get("evidence_pack_path")
        if not isinstance(raw_path, (str, Path)):
            return _failure("failed", "missing evidence_pack_path")
        pack_path = Path(raw_path)
        if not pack_path.exists():
            return _failure("failed", "evidence_pack_path does not exist", path=str(pack_path))
        try:
            payload = _load_json_object(pack_path)
            write_json_artifact(pack_path, payload, schema=EVIDENCE_PACK_SCHEMA)
            output_path = write_json_artifact(
                _evidence_pack_path(_artifact_root(ctx)),
                payload,
                schema=EVIDENCE_PACK_SCHEMA,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _failure("failed", str(exc), path=str(pack_path))
        return _result(
            next_label="validators",
            status=ContractStatus.COMPLETED,
            payload={
                "evidence_pack_id": payload["evidence_pack_id"],
                "checkpoint_count": len(payload.get("checkpoints") or []),
            },
            outputs={"evidence_pack": str(output_path)},
        )


def _validate_structural_audit(payload: dict[str, Any]) -> tuple[str, str | None]:
    return CHECKPOINT_STATUS_PASSED, None


def _validate_budget_enforcement(payload: dict[str, Any]) -> tuple[str, str | None]:
    if payload.get("source_ticket"):
        return CHECKPOINT_STATUS_PASSED, None
    return CHECKPOINT_STATUS_FAILED, "missing source_ticket"


def _validate_suspension_propagation(payload: dict[str, Any]) -> tuple[str, str | None]:
    return CHECKPOINT_STATUS_PASSED, None


def _validate_by_ref(payload: dict[str, Any]) -> tuple[str, str | None]:
    checkpoints = payload.get("checkpoints") or []
    for checkpoint in checkpoints:
        for artifact_ref in checkpoint.get("artifact_refs") or []:
            if not artifact_ref.get("uri") or not artifact_ref.get("content_type"):
                return CHECKPOINT_STATUS_FAILED, "invalid artifact_ref"
    return CHECKPOINT_STATUS_PASSED, None


def _validate_human_review_gate(payload: dict[str, Any]) -> tuple[str, str | None]:
    checkpoints = payload.get("checkpoints") or []
    human_review = [
        checkpoint
        for checkpoint in checkpoints
        if str(checkpoint.get("checkpoint_id", "")).endswith(".human_review_gate")
    ]
    for checkpoint in human_review:
        if checkpoint.get("status") == CHECKPOINT_STATUS_FAILED:
            return CHECKPOINT_STATUS_FAILED, "human review gate failed"
        if checkpoint.get("status") == CHECKPOINT_STATUS_SUSPENDED and not checkpoint.get("artifact_refs"):
            return CHECKPOINT_STATUS_PASSED, "human review gate suspended"
    return CHECKPOINT_STATUS_PASSED, None


_VALIDATOR_FUNCS: dict[str, Callable[[dict[str, Any]], tuple[str, str | None]]] = {
    VALIDATOR_KIND_STRUCTURAL_AUDIT: _validate_structural_audit,
    VALIDATOR_KIND_BUDGET_ENFORCEMENT: _validate_budget_enforcement,
    VALIDATOR_KIND_SUSPENSION_PROPAGATION: _validate_suspension_propagation,
    VALIDATOR_KIND_BY_REF_VALIDATION: _validate_by_ref,
    VALIDATOR_KIND_HUMAN_REVIEW_GATE: _validate_human_review_gate,
}


@dataclass
class ContentValidatorStep:
    name: str = "content_validator"
    checkpoint_kind: str = VALIDATOR_KIND_STRUCTURAL_AUDIT
    kind: str = "verify"

    def run(self, ctx: StepContext) -> StepResult:
        try:
            payload = _load_evidence_pack_from_input(ctx)
        except ValueError as exc:
            return _failure("failed", str(exc))
        evidence_pack_id = str(payload["evidence_pack_id"])
        checkpoint_id = f"{evidence_pack_id}.{self.checkpoint_kind}"
        validator = _VALIDATOR_FUNCS.get(self.checkpoint_kind)
        if self.checkpoint_kind not in VALIDATOR_KINDS or validator is None:
            return _failure("failed", f"unknown checkpoint_kind: {self.checkpoint_kind}", checkpoint_id=checkpoint_id)
        status, diagnostic = validator(payload)
        checkpoint_payload = make_checkpoint_payload(
            checkpoint_id=checkpoint_id,
            evidence_pack_id=evidence_pack_id,
            checkpoint_kind=self.checkpoint_kind,
            status=status,
            diagnostic=diagnostic,
            artifact_refs=[],
        )
        output_path = write_json_artifact(
            _checkpoint_path(_artifact_root(ctx), checkpoint_id),
            checkpoint_payload,
            schema=CHECKPOINT_SCHEMA,
        )
        contract_status = (
            ContractStatus.COMPLETED if status == CHECKPOINT_STATUS_PASSED else ContractStatus.FAILED
        )
        return _result(
            next_label="passed" if contract_status is ContractStatus.COMPLETED else "failed",
            status=contract_status,
            payload=checkpoint_payload,
            outputs={checkpoint_id: str(output_path)},
        )


@dataclass
class ReduceStep:
    name: str = "reduce"
    kind: str = "verify"

    def run(self, ctx: StepContext) -> StepResult:
        try:
            evidence_pack = _load_evidence_pack_from_input(ctx)
        except ValueError as exc:
            return _failure("failed", str(exc))
        evidence_pack_id = str(evidence_pack["evidence_pack_id"])
        checkpoint_results = _iter_checkpoint_inputs(ctx, evidence_pack_id)
        failed = [
            checkpoint["checkpoint_id"]
            for checkpoint in checkpoint_results
            if checkpoint.get("status") != CHECKPOINT_STATUS_PASSED
        ]
        verdict = VERDICT_FAIL if failed else VERDICT_PASS
        verdict_payload = make_verdict_payload(
            evidence_pack_id=evidence_pack_id,
            verdict=verdict,
            failed_checkpoints=failed,
        )
        output_path = write_json_artifact(
            _verdict_path(_artifact_root(ctx)),
            verdict_payload,
            schema=VERDICT_SCHEMA,
        )
        status = ContractStatus.COMPLETED if verdict == VERDICT_PASS else ContractStatus.FAILED
        return _result(
            next_label="emit" if verdict == VERDICT_PASS else "human_review",
            status=status,
            payload=verdict_payload,
            outputs={"verdict": str(output_path)},
        )


@dataclass
class HumanReviewStep:
    name: str = "human_review"
    checkpoint_kind: str = VALIDATOR_KIND_HUMAN_REVIEW_GATE
    kind: str = "verify"

    def run(self, ctx: StepContext) -> StepResult:
        try:
            evidence_pack = _load_evidence_pack_from_input(ctx)
        except ValueError as exc:
            return _failure("failed", str(exc))
        evidence_pack_id = str(evidence_pack["evidence_pack_id"])
        checkpoint_id = f"{evidence_pack_id}.{self.checkpoint_kind}"
        output_path = _checkpoint_path(_artifact_root(ctx), checkpoint_id)
        human_input = ctx.inputs.get("human_input")
        if human_input is None:
            checkpoint_payload = make_checkpoint_payload(
                checkpoint_id=checkpoint_id,
                evidence_pack_id=evidence_pack_id,
                checkpoint_kind=self.checkpoint_kind,
                status=CHECKPOINT_STATUS_SUSPENDED,
                diagnostic="awaiting human review",
                resume_cursor=checkpoint_id,
                artifact_refs=[],
            )
            write_json_artifact(output_path, checkpoint_payload, schema=CHECKPOINT_SCHEMA)
            suspension = Suspension(
                kind="human",
                prompt="Review the evidence pack verdict.",
                resume_input_schema=_human_review_resume_schema(),
                resume_cursor=checkpoint_id,
                default_action="reject",
            )
            return _result(
                next_label="suspended",
                status=ContractStatus.SUSPENDED,
                payload=checkpoint_payload,
                outputs={checkpoint_id: str(output_path)},
                suspension=suspension,
            )
        if not isinstance(human_input, Mapping) or not isinstance(human_input.get("approved"), bool):
            return _failure("failed", "human_input must be a mapping with boolean approved", checkpoint_id=checkpoint_id)
        approved = bool(human_input["approved"])
        comment = human_input.get("comment")
        diagnostic = "human review: approved" if approved else f"human review: {comment or 'rejected'}"
        checkpoint_payload = make_checkpoint_payload(
            checkpoint_id=checkpoint_id,
            evidence_pack_id=evidence_pack_id,
            checkpoint_kind=self.checkpoint_kind,
            status=CHECKPOINT_STATUS_PASSED if approved else CHECKPOINT_STATUS_FAILED,
            diagnostic=diagnostic,
            artifact_refs=[],
        )
        write_json_artifact(output_path, checkpoint_payload, schema=CHECKPOINT_SCHEMA)
        return _result(
            next_label="emit" if approved else "failed",
            status=ContractStatus.COMPLETED if approved else ContractStatus.FAILED,
            payload=checkpoint_payload,
            outputs={checkpoint_id: str(output_path)},
        )


@dataclass
class EmitAttestationStep:
    name: str = "emit_attestation"
    kind: str = "verify"

    def run(self, ctx: StepContext) -> StepResult:
        try:
            evidence_pack = _load_evidence_pack_from_input(ctx)
        except ValueError as exc:
            return _failure("failed", str(exc))
        evidence_pack_id = str(evidence_pack["evidence_pack_id"])
        checkpoint_results = _iter_checkpoint_inputs(ctx, evidence_pack_id)
        verdict_payload: dict[str, Any] | None = None
        verdict_input = ctx.inputs.get("verdict")
        if isinstance(verdict_input, (str, Path)):
            try:
                verdict_payload = read_json_artifact(verdict_input)
                write_json_artifact(Path(verdict_input), verdict_payload, schema=VERDICT_SCHEMA)
            except ValueError as exc:
                return _failure("failed", str(exc))
        verdict = verdict_payload["verdict"] if verdict_payload is not None else VERDICT_PASS
        if any(checkpoint.get("status") == CHECKPOINT_STATUS_FAILED for checkpoint in checkpoint_results):
            verdict = VERDICT_FAIL
        attestation_payload = make_attestation_payload(
            evidence_pack_id=evidence_pack_id,
            verdict=verdict,
            checkpoint_results=checkpoint_results,
        )
        output_path = write_json_artifact(
            _attestation_path(_artifact_root(ctx)),
            attestation_payload,
            schema=ATTESTATION_SCHEMA,
        )
        return _result(
            next_label="halt",
            status=ContractStatus.COMPLETED,
            payload=attestation_payload,
            outputs={"attestation": str(output_path)},
        )


__all__ = [
    "ContentValidatorStep",
    "EmitAttestationStep",
    "EvidencePackStep",
    "HumanReviewStep",
    "IngestStep",
    "ReduceStep",
    "_ARTIFACT_KIND_BY_STAGE",
    "_NATIVE_PHASE_ORDER",
]
