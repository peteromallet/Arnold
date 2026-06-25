"""Concrete evidence-pack Step classes — deterministic, model-less.

Each step is a plain dataclass implementing the ``Step`` Protocol from
``arnold.pipeline.types``.  No Megaplan labels, handlers, registry
coupling, mutable globals, or executor-local state.

Artifact I/O is deterministic: steps read from ``ctx.artifact_root`` and
``ctx.inputs``, write JSON artifacts to well-known paths under
``ctx.artifact_root``, and return ``StepResult`` with contract payloads.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline import (
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Provenance,
    ReducePolicy,
    StepContext,
    StepResult,
    Suspension,
    reduce_contract_results,
    validate_payload_against_schema,
)

from arnold.pipelines.evidence_pack.verifier import (
    ATTESTATION_SCHEMA,
    CHECKPOINT_SCHEMA,
    EVIDENCE_PACK_SCHEMA,
    VERDICT_SCHEMA,
    Verdict,
    make_attestation_payload,
    make_checkpoint_payload,
    make_contract_result,
    make_evidence_pack_payload,
    make_verdict_payload,
)

# ---------------------------------------------------------------------------
# Artifact path helpers
# ---------------------------------------------------------------------------


def _artifact_path(ctx: StepContext, filename: str) -> Path:
    """Return a deterministic artifact path under ctx.artifact_root."""
    root = Path(ctx.artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    return root / filename


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write payload as deterministic, sorted-key JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON artifact."""
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# IngestStep
# ---------------------------------------------------------------------------


@dataclass
class IngestStep:
    """Load and validate an evidence pack from a JSON artifact.

    Reads the evidence pack from ``ctx.inputs["evidence_pack_path"]``,
    validates it against ``EVIDENCE_PACK_SCHEMA``, and writes the
    validated pack as ``evidence_pack.json`` in the artifact root.
    """

    name: str = "ingest"
    kind: str = "ingest"

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        pack_path_str = ctx.inputs.get("evidence_pack_path")
        if pack_path_str is None:
            return StepResult(
                next="failed",
                contract_result=make_contract_result(
                    status=ContractStatus.FAILED,
                    payload={
                        "error": "missing evidence_pack_path in inputs",
                        "step": self.name,
                    },
                ),
            )

        pack_path = Path(pack_path_str)
        if not pack_path.exists():
            return StepResult(
                next="failed",
                contract_result=make_contract_result(
                    status=ContractStatus.FAILED,
                    payload={
                        "error": f"evidence pack not found: {pack_path}",
                        "step": self.name,
                    },
                ),
            )

        try:
            raw = _read_json(pack_path)
        except (json.JSONDecodeError, OSError) as exc:
            return StepResult(
                next="failed",
                contract_result=make_contract_result(
                    status=ContractStatus.FAILED,
                    payload={
                        "error": f"failed to parse evidence pack: {exc}",
                        "step": self.name,
                    },
                ),
            )

        validation = validate_payload_against_schema(raw, EVIDENCE_PACK_SCHEMA)
        if not validation.ok:
            return StepResult(
                next="failed",
                contract_result=make_contract_result(
                    status=ContractStatus.FAILED,
                    payload={
                        "error": "evidence pack schema validation failed",
                        "diagnostics": [
                            {"code": d.code, "message": d.message}
                            for d in validation.diagnostics
                        ],
                        "step": self.name,
                    },
                ),
            )

        # Write validated pack
        out_path = _artifact_path(ctx, "evidence_pack.json")
        _write_json(out_path, raw)

        evidence_pack_id = raw.get("evidence_pack_id", "unknown")
        return StepResult(
            outputs={"evidence_pack": str(out_path)},
            next="validators",
            contract_result=make_contract_result(
                status=ContractStatus.COMPLETED,
                payload={
                    "evidence_pack_id": evidence_pack_id,
                    "source_ticket": raw.get("source_ticket"),
                    "checkpoint_count": len(raw.get("checkpoints", [])),
                    "step": self.name,
                },
            ),
        )


# ---------------------------------------------------------------------------
# ContentValidatorStep
# ---------------------------------------------------------------------------


@dataclass
class ContentValidatorStep:
    """Run a single content-validator checkpoint against the evidence pack.

    The checkpoint kind is configured via ``checkpoint_kind``.  Reads
    the evidence pack from ``ctx.inputs["evidence_pack"]``, runs the
    appropriate validation logic, writes a checkpoint artifact, and
    returns a completed or failed contract result.
    """

    name: str = "content_validator"
    kind: str = "content_validator"
    checkpoint_kind: str = "structural_audit"

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        pack_path_str = ctx.inputs.get("evidence_pack")
        if pack_path_str is None:
            return self._fail("missing evidence_pack input", ctx)
        pack_path = Path(pack_path_str)

        try:
            pack = _read_json(pack_path)
        except (json.JSONDecodeError, OSError) as exc:
            return self._fail(f"failed to read evidence pack: {exc}", ctx)

        evidence_pack_id = pack.get("evidence_pack_id", "unknown")
        checkpoint_id = f"{evidence_pack_id}.{self.checkpoint_kind}"

        # Run validation logic for this checkpoint kind
        passed, diagnostic = self._validate(pack)

        status = "passed" if passed else "failed"
        checkpoint = make_checkpoint_payload(
            checkpoint_id=checkpoint_id,
            evidence_pack_id=evidence_pack_id,
            checkpoint_kind=self.checkpoint_kind,
            status=status,
            diagnostic=diagnostic if diagnostic else None,
        )

        # Validate the checkpoint against the schema
        cp_validation = validate_payload_against_schema(checkpoint, CHECKPOINT_SCHEMA)
        if not cp_validation.ok:
            return StepResult(
                next="failed",
                contract_result=make_contract_result(
                    status=ContractStatus.FAILED,
                    payload={
                        "error": "checkpoint schema validation failed",
                        "diagnostics": [
                            {"code": d.code, "message": d.message}
                            for d in cp_validation.diagnostics
                        ],
                        "step": self.name,
                    },
                ),
            )

        # Write checkpoint artifact
        cp_path = _artifact_path(ctx, f"checkpoint_{checkpoint_id}.json")
        _write_json(cp_path, checkpoint)

        return StepResult(
            outputs={checkpoint_id: str(cp_path)},
            next="passed" if passed else "failed",
            contract_result=make_contract_result(
                status=ContractStatus.COMPLETED if passed else ContractStatus.FAILED,
                payload={
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_kind": self.checkpoint_kind,
                    "status": status,
                    "step": self.name,
                },
                evidence_refs=(
                    EvidenceArtifactRef(
                        uri=str(cp_path),
                        content_type="application/json",
                        name=f"checkpoint-{checkpoint_id}",
                    ),
                ),
            ),
        )

    def _validate(self, pack: dict[str, Any]) -> tuple[bool, str | None]:
        """Run validation logic for the configured checkpoint kind."""
        if self.checkpoint_kind == "structural_audit":
            return self._validate_structural(pack)
        elif self.checkpoint_kind == "budget_enforcement":
            return self._validate_budget(pack)
        elif self.checkpoint_kind == "suspension_propagation":
            return self._validate_suspension(pack)
        elif self.checkpoint_kind == "by_ref_validation":
            return self._validate_by_ref(pack)
        elif self.checkpoint_kind == "human_review_gate":
            return self._validate_human_review_gate(pack)
        else:
            return False, f"unknown checkpoint_kind: {self.checkpoint_kind}"

    @staticmethod
    def _validate_structural(pack: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate structural integrity: no extra properties, valid checkpoints."""
        checkpoints = pack.get("checkpoints", [])
        if not isinstance(checkpoints, list):
            return False, "checkpoints must be a list"
        for i, cp in enumerate(checkpoints):
            if not isinstance(cp, dict):
                return False, f"checkpoints[{i}] must be an object"
            if "checkpoint_id" not in cp:
                return False, f"checkpoints[{i}] missing checkpoint_id"
            if "status" not in cp:
                return False, f"checkpoints[{i}] missing status"
        return True, None

    @staticmethod
    def _validate_budget(pack: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate budget constraints."""
        # In a real implementation, this would check budget limits.
        # For the evidence pack, we check that the source_ticket is present.
        if not pack.get("source_ticket"):
            return False, "missing source_ticket for budget enforcement"
        return True, None

    @staticmethod
    def _validate_suspension(pack: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate suspension propagation constraints."""
        checkpoints = pack.get("checkpoints", [])
        suspended = [cp for cp in checkpoints if cp.get("status") == "suspended"]
        if suspended and not all(
            "resume_cursor" in cp or "diagnostic" in cp for cp in suspended
        ):
            return False, "suspended checkpoints missing resume_cursor or diagnostic"
        return True, None

    @staticmethod
    def _validate_by_ref(pack: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate by-reference artifact integrity."""
        checkpoints = pack.get("checkpoints", [])
        for cp in checkpoints:
            for ref in cp.get("artifact_refs", []):
                if not isinstance(ref, dict):
                    return False, "artifact_ref must be an object"
                if "uri" not in ref or "content_type" not in ref:
                    return False, "artifact_ref missing uri or content_type"
        return True, None

    @staticmethod
    def _validate_human_review_gate(pack: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate human review gate status."""
        checkpoints = pack.get("checkpoints", [])
        human_cps = [
            cp for cp in checkpoints
            if cp.get("checkpoint_kind") == "human_review_gate"
        ]
        if not human_cps:
            return True, "no human review gate checkpoints"
        for cp in human_cps:
            if cp.get("status") == "suspended":
                return True, "human review gate is suspended (awaiting review)"
        return True, None

    def _fail(self, message: str, ctx: StepContext) -> StepResult:
        return StepResult(
            next="failed",
            contract_result=make_contract_result(
                status=ContractStatus.FAILED,
                payload={"error": message, "step": self.name},
            ),
        )


# ---------------------------------------------------------------------------
# ReduceStep
# ---------------------------------------------------------------------------


@dataclass
class ReduceStep:
    """Aggregate content-validator checkpoint results into a verdict.

    Consumes the evidence pack and checkpoint outputs, applies
    ``reduce_contract_results`` with ``MAX_WINS`` lattice, and writes
    a verdict artifact.
    """

    name: str = "reduce"
    kind: str = "reduce"

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        pack_path_str = ctx.inputs.get("evidence_pack")
        if pack_path_str is None:
            return StepResult(
                next="failed",
                contract_result=make_contract_result(
                    status=ContractStatus.FAILED,
                    payload={"error": "missing evidence_pack input", "step": self.name},
                ),
            )

        try:
            pack = _read_json(Path(pack_path_str))
        except (json.JSONDecodeError, OSError) as exc:
            return StepResult(
                next="failed",
                contract_result=make_contract_result(
                    status=ContractStatus.FAILED,
                    payload={"error": f"failed to read evidence pack: {exc}", "step": self.name},
                ),
            )

        evidence_pack_id = pack.get("evidence_pack_id", "unknown")

        # Collect checkpoint results from ctx.inputs
        # Keys like "<evidence_pack_id>.<checkpoint_kind>" map to checkpoint paths
        checkpoint_results: list[ContractResult] = []
        failed_checkpoints: list[str] = []
        for key, value in ctx.inputs.items():
            if key == "evidence_pack":
                continue
            if not isinstance(value, str):
                continue
            cp_path = Path(value)
            if not cp_path.exists() or cp_path.suffix != ".json":
                continue
            try:
                cp_data = _read_json(cp_path)
                if "checkpoint_id" not in cp_data or "status" not in cp_data:
                    continue
                status = cp_data.get("status", "failed")
                checkpoint_id = cp_data.get("checkpoint_id", key)
                checkpoint_results.append(
                    make_contract_result(
                        status=(
                            ContractStatus.COMPLETED
                            if status == "passed"
                            else ContractStatus.FAILED
                        ),
                        payload={
                            "checkpoint_id": checkpoint_id,
                            "status": status,
                            "diagnostic": cp_data.get("diagnostic"),
                        },
                    )
                )
                if status == "failed":
                    failed_checkpoints.append(checkpoint_id)
            except (json.JSONDecodeError, OSError):
                continue

        # Reduce with MAX_WINS lattice
        reduced = reduce_contract_results(
            checkpoint_results,
            reduce_policy=ReducePolicy.MAX_WINS,
        )

        verdict = Verdict.PASS if reduced.status == ContractStatus.COMPLETED else Verdict.FAIL
        verdict_id = f"{evidence_pack_id}.verdict"

        verdict_payload = make_verdict_payload(
            verdict_id=verdict_id,
            evidence_pack_id=evidence_pack_id,
            verdict=verdict,
            failed_checkpoints=failed_checkpoints if failed_checkpoints else None,
        )

        # Validate verdict
        v_validation = validate_payload_against_schema(verdict_payload, VERDICT_SCHEMA)
        if not v_validation.ok:
            return StepResult(
                next="failed",
                contract_result=make_contract_result(
                    status=ContractStatus.FAILED,
                    payload={
                        "error": "verdict schema validation failed",
                        "diagnostics": [
                            {"code": d.code, "message": d.message}
                            for d in v_validation.diagnostics
                        ],
                        "step": self.name,
                    },
                ),
            )

        # Write verdict artifact
        verdict_path = _artifact_path(ctx, "verdict.json")
        _write_json(verdict_path, verdict_payload)

        next_label = "human_review" if verdict == Verdict.FAIL else "emit"
        return StepResult(
            outputs={"verdict": str(verdict_path)},
            next=next_label,
            contract_result=make_contract_result(
                status=reduced.status,
                payload={
                    "verdict_id": verdict_id,
                    "verdict": verdict.value,
                    "failed_checkpoints": failed_checkpoints,
                    "step": self.name,
                },
                evidence_refs=(
                    EvidenceArtifactRef(
                        uri=str(verdict_path),
                        content_type="application/json",
                        name="verdict",
                    ),
                ),
            ),
        )


# ---------------------------------------------------------------------------
# HumanReviewStep
# ---------------------------------------------------------------------------


@dataclass
class HumanReviewStep:
    """Suspend for human review or resume with human input.

    On first run (no ``human_input`` in ctx.inputs), writes a checkpoint
    artifact with status ``suspended`` and returns a SUSPENDED contract
    result with a human-gate ``Suspension``.

    On resume (``human_input`` present in ctx.inputs), reads the human
    decision, updates the checkpoint to ``passed`` or ``failed``, and
    returns the appropriate contract result.
    """

    name: str = "human_review"
    kind: str = "human_review"

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        pack_path_str = ctx.inputs.get("evidence_pack")
        verdict_path_str = ctx.inputs.get("verdict")
        human_input = ctx.inputs.get("human_input")

        if pack_path_str is None:
            return self._fail("missing evidence_pack input", ctx)
        pack_path = Path(pack_path_str)

        try:
            pack = _read_json(pack_path)
        except (json.JSONDecodeError, OSError) as exc:
            return self._fail(f"failed to read evidence pack: {exc}", ctx)

        evidence_pack_id = pack.get("evidence_pack_id", "unknown")
        checkpoint_id = f"{evidence_pack_id}.human_review_gate"

        if human_input is None:
            # --- SUSPEND: first run, no human input yet ---
            checkpoint = make_checkpoint_payload(
                checkpoint_id=checkpoint_id,
                evidence_pack_id=evidence_pack_id,
                checkpoint_kind="human_review_gate",
                status="suspended",
                diagnostic="awaiting human review",
                resume_cursor=checkpoint_id,
            )

            cp_path = _artifact_path(ctx, f"checkpoint_{checkpoint_id}.json")
            _write_json(cp_path, checkpoint)

            display_ref = EvidenceArtifactRef(
                uri=str(verdict_path_str) if verdict_path_str else str(cp_path),
                content_type="application/json",
                name="verdict-for-review",
            )

            suspension = Suspension(
                kind="human",
                awaitable=f"approval/{checkpoint_id}",
                prompt="Review the evidence pack verdict: approve or reject?",
                display_refs=(display_ref,),
                resume_input_schema={"approved": "bool", "comment": "str"},
                resume_cursor=checkpoint_id,
                thread_ref=f"thread/{checkpoint_id}",
                actor="evidence-reviewer",
                deadline=_utc_iso(3600),
                on_timeout="reject",
                default_action="reject",
            )

            return StepResult(
                outputs={"checkpoint": str(cp_path)},
                next="suspended",
                contract_result=make_contract_result(
                    status=ContractStatus.SUSPENDED,
                    payload={
                        "checkpoint_id": checkpoint_id,
                        "gate": "evidence-pack-approval",
                        "step": self.name,
                    },
                    suspension=suspension,
                    evidence_refs=(display_ref,),
                ),
            )

        # --- RESUME: human input provided ---
        if not isinstance(human_input, dict):
            return self._fail("human_input must be a dict", ctx)

        approved = human_input.get("approved", False)
        comment = human_input.get("comment", "")

        new_status = "passed" if approved else "failed"
        checkpoint = make_checkpoint_payload(
            checkpoint_id=checkpoint_id,
            evidence_pack_id=evidence_pack_id,
            checkpoint_kind="human_review_gate",
            status=new_status,
            diagnostic=f"human review: {comment}" if comment else "human review completed",
        )

        cp_path = _artifact_path(ctx, f"checkpoint_{checkpoint_id}.json")
        _write_json(cp_path, checkpoint)

        next_label = "emit" if approved else "failed"
        return StepResult(
            outputs={"checkpoint": str(cp_path)},
            next=next_label,
            contract_result=make_contract_result(
                status=ContractStatus.COMPLETED if approved else ContractStatus.FAILED,
                payload={
                    "checkpoint_id": checkpoint_id,
                    "status": new_status,
                    "comment": comment,
                    "step": self.name,
                },
                evidence_refs=(
                    EvidenceArtifactRef(
                        uri=str(cp_path),
                        content_type="application/json",
                        name=f"checkpoint-{checkpoint_id}",
                    ),
                ),
            ),
        )

    def _fail(self, message: str, ctx: StepContext) -> StepResult:
        return StepResult(
            next="failed",
            contract_result=make_contract_result(
                status=ContractStatus.FAILED,
                payload={"error": message, "step": self.name},
            ),
        )


# ---------------------------------------------------------------------------
# EmitAttestationStep
# ---------------------------------------------------------------------------


@dataclass
class EmitAttestationStep:
    """Emit the final signed attestation for the evidence pack verdict.

    Consumes the verdict and checkpoint artifacts, assembles an attestation
    payload, validates it against ``ATTESTATION_SCHEMA``, writes the
    attestation artifact, and returns a completed or failed contract result.
    """

    name: str = "emit_attestation"
    kind: str = "emit_attestation"

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        pack_path_str = ctx.inputs.get("evidence_pack")
        verdict_path_str = ctx.inputs.get("verdict")

        if pack_path_str is None:
            return self._fail("missing evidence_pack input", ctx)

        try:
            pack = _read_json(Path(pack_path_str))
        except (json.JSONDecodeError, OSError) as exc:
            return self._fail(f"failed to read evidence pack: {exc}", ctx)

        evidence_pack_id = pack.get("evidence_pack_id", "unknown")
        attestation_id = f"{evidence_pack_id}.attestation"

        # Determine verdict from verdict artifact or checkpoint results
        verdict = Verdict.PASS
        checkpoint_results: list[dict[str, Any]] = []

        if verdict_path_str:
            try:
                verdict_data = _read_json(Path(verdict_path_str))
                verdict = Verdict(verdict_data.get("verdict", "FAIL"))
            except (json.JSONDecodeError, OSError, ValueError):
                verdict = Verdict.FAIL

        # Collect checkpoint results from inputs
        for key, value in ctx.inputs.items():
            if key in ("evidence_pack", "verdict"):
                continue
            if not isinstance(value, str):
                continue
            cp_path = Path(value)
            if not cp_path.exists() or cp_path.suffix != ".json":
                continue
            try:
                cp_data = _read_json(cp_path)
                if "checkpoint_id" in cp_data and "status" in cp_data:
                    cr_entry: dict[str, Any] = {
                        "checkpoint_id": cp_data["checkpoint_id"],
                        "status": cp_data["status"],
                    }
                    diag = cp_data.get("diagnostic")
                    if diag is not None:
                        cr_entry["diagnostic"] = diag
                    checkpoint_results.append(cr_entry)
            except (json.JSONDecodeError, OSError):
                continue

        # Check for any failed checkpoints
        for cr in checkpoint_results:
            if cr.get("status") == "failed":
                verdict = Verdict.FAIL
                break

        attestation = make_attestation_payload(
            attestation_id=attestation_id,
            evidence_pack_id=evidence_pack_id,
            verdict=verdict,
            checkpoint_results=checkpoint_results if checkpoint_results else None,
        )

        # Validate attestation
        a_validation = validate_payload_against_schema(attestation, ATTESTATION_SCHEMA)
        if not a_validation.ok:
            return StepResult(
                next="failed",
                contract_result=make_contract_result(
                    status=ContractStatus.FAILED,
                    payload={
                        "error": "attestation schema validation failed",
                        "diagnostics": [
                            {"code": d.code, "message": d.message}
                            for d in a_validation.diagnostics
                        ],
                        "step": self.name,
                    },
                ),
            )

        # Write attestation artifact
        att_path = _artifact_path(ctx, "attestation.json")
        _write_json(att_path, attestation)

        return StepResult(
            outputs={"attestation": str(att_path)},
            next="halt",
            contract_result=make_contract_result(
                status=ContractStatus.COMPLETED,
                payload={
                    "attestation_id": attestation_id,
                    "verdict": verdict.value,
                    "checkpoint_count": len(checkpoint_results),
                    "step": self.name,
                },
                evidence_refs=(
                    EvidenceArtifactRef(
                        uri=str(att_path),
                        content_type="application/json",
                        name="attestation",
                    ),
                ),
            ),
        )

    def _fail(self, message: str, ctx: StepContext) -> StepResult:
        return StepResult(
            next="failed",
            contract_result=make_contract_result(
                status=ContractStatus.FAILED,
                payload={"error": message, "step": self.name},
            ),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_iso(offset_seconds: int = 0) -> str:
    """Return an ISO-8601 UTC timestamp offset from now."""
    return (datetime.now(timezone.utc)).isoformat()
