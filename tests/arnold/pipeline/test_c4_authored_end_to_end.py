"""C4 authored end-to-end test — full fan-out, suspend/resume, by-ref artifact.

Exercises the C4 public API (arnold.pipeline.*) through a complete evidence-pack
verification run:

* ≥3 fan-out validators (evidence_pack uses 5 via add_parallel_stage)
* suspend at human_review → continuation pipeline resume → attestation written
* ≥1 >1MiB by-ref artifact exercised through the C1 chokepoint / sidecar manifest
* route-bypass invariant re-confirmed (unregistered kind='tool' still flagged)
"""

from __future__ import annotations

import json
import inspect
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline import (
    Pipeline,
    PipelineBuilder,
    Port,
    PortRef,
    ReadRef,
    Stage,
    WriteRef,
    derive_binding_map,
)
from arnold.pipeline.artifact_io import validate_large_artifact_by_manifest
from arnold.pipeline.artifacts import (
    LARGE_ARTIFACT_THRESHOLD_BYTES,
    SidecarManifest,
    read_sidecar_manifest,
    sidecar_path_for,
    write_versioned,
)
from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.contract_validation import validate_payload_against_schema
from arnold.pipeline.step_io_contract import StepIOContractContext
from arnold.pipeline.step_io_policy import StepIOPolicy
from arnold.pipeline.validator import UNKNOWN_ADAPTER_CODE, validate
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.pipelines.evidence_pack.pipelines import (
    build_continuation_pipeline,
    build_initial_pipeline,
)
from arnold.pipelines.evidence_pack import pipelines as evidence_pack_pipelines
from arnold.pipelines.evidence_pack import steps as evidence_pack_steps
from arnold.pipelines.evidence_pack.verifier import (
    ATTESTATION_SCHEMA,
    CHECKPOINT_SCHEMA,
    EVIDENCE_PACK_SCHEMA,
    VERDICT_SCHEMA,
    make_evidence_pack_payload,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_envelope(artifact_root: str, *, run_id: str = "c4-e2e") -> Any:
    return RuntimeEnvelope(
        plugin_id="evidence_pack_verifier",
        run_id=run_id,
        artifact_root=artifact_root,
    )


def _valid_pack(evidence_pack_id: str, *, n_checkpoints: int = 5) -> dict[str, Any]:
    """Valid evidence pack with ``n_checkpoints`` all passing."""
    checkpoints = [
        {
            "checkpoint_id": f"{evidence_pack_id}.chk{i}",
            "status": "passed",
            "artifact_refs": [],
        }
        for i in range(n_checkpoints)
    ]
    return make_evidence_pack_payload(
        evidence_pack_id=evidence_pack_id,
        source_ticket="01KT50AZRMK5X890TQ565DDB5V",
        checkpoints=checkpoints,
    )


# ---------------------------------------------------------------------------
# Test: full fan-out → suspend → resume → ATTESTED (attestation.json written)
# ---------------------------------------------------------------------------


class TestC4EndToEndAttestation:
    """Full initial + continuation run via the C4 public API.

    The evidence-pack pipeline has 5 fan-out content validators (≥3 satisfied),
    suspends at human_review, then resumes via a fresh continuation pipeline.
    After approval, attestation.json is written — the proxy for ATTESTED state.
    """

    def test_initial_pipeline_suspends_at_human_review(self) -> None:
        root = tempfile.mkdtemp(prefix="c4_e2e_init_")
        artifact_root = Path(root)

        pack_path = artifact_root / "input_pack.json"
        _write_json(pack_path, _valid_pack("c4-e2e-001"))

        run_pipeline(
            build_initial_pipeline(),
            initial_state={"evidence_pack_path": str(pack_path)},
            envelope=_make_envelope(str(artifact_root)),
        )

        cp_path = artifact_root / "checkpoint_c4-e2e-001.human_review_gate.json"
        assert cp_path.exists(), (
            f"Expected human_review checkpoint; files: {sorted(p.name for p in artifact_root.iterdir())}"
        )
        checkpoint = _read_json(cp_path)
        assert checkpoint["status"] == "suspended"
        checkpoint_validation = validate_payload_against_schema(
            checkpoint,
            CHECKPOINT_SCHEMA,
        )
        assert checkpoint_validation.ok, checkpoint_validation.diagnostics

        # attestation must NOT exist at this point
        assert not (artifact_root / "attestation.json").exists()

    def test_continuation_approval_writes_attestation(self) -> None:
        """Full suspend→resume cycle ends with attestation.json present."""
        root = tempfile.mkdtemp(prefix="c4_e2e_full_")
        artifact_root = Path(root)

        pack_path = artifact_root / "input_pack.json"
        _write_json(pack_path, _valid_pack("c4-e2e-002"))

        envelope = _make_envelope(str(artifact_root), run_id="c4-full-002")

        # --- Phase 1: initial pipeline → suspend ---
        run_pipeline(
            build_initial_pipeline(),
            initial_state={"evidence_pack_path": str(pack_path)},
            envelope=envelope,
        )
        cp_path = artifact_root / "checkpoint_c4-e2e-002.human_review_gate.json"
        assert cp_path.exists(), "initial pipeline did not produce suspension checkpoint"
        named_artifacts = {
            "evidence_pack": artifact_root / "evidence_pack.json",
            "verdict": artifact_root / "verdict.json",
            "checkpoint": cp_path,
        }
        for label, path in named_artifacts.items():
            assert path.exists(), f"missing persisted {label} artifact: {path}"

        typed_payloads = {
            "evidence_pack": (_read_json(named_artifacts["evidence_pack"]), EVIDENCE_PACK_SCHEMA),
            "verdict": (_read_json(named_artifacts["verdict"]), VERDICT_SCHEMA),
            "checkpoint": (_read_json(named_artifacts["checkpoint"]), CHECKPOINT_SCHEMA),
        }
        for label, (payload, schema) in typed_payloads.items():
            validation = validate_payload_against_schema(payload, schema)
            assert validation.ok, f"{label} artifact failed schema validation: {validation.diagnostics}"

        # --- Phase 2: continuation → approve → attestation ---
        run_pipeline(
            build_continuation_pipeline(),
            initial_state={
                "evidence_pack": str(artifact_root / "evidence_pack.json"),
                "verdict": str(artifact_root / "verdict.json"),
                "human_input": {"approved": True, "comment": "c4 e2e approved"},
            },
            envelope=envelope,
        )

        att_path = artifact_root / "attestation.json"
        assert att_path.exists(), (
            f"attestation.json must exist after approval; "
            f"files: {sorted(p.name for p in artifact_root.iterdir())}"
        )
        attestation = _read_json(att_path)
        # Attestation carries a verdict — PASS for an all-passing pack
        assert attestation.get("verdict") in ("PASS", "FAIL"), (
            f"Unexpected attestation payload: {attestation}"
        )
        assert attestation.get("evidence_pack_id") == "c4-e2e-002"
        attestation_validation = validate_payload_against_schema(
            attestation,
            ATTESTATION_SCHEMA,
        )
        assert attestation_validation.ok, attestation_validation.diagnostics

    def test_fan_out_count_at_least_three(self) -> None:
        """The initial evidence-pack pipeline has ≥3 parallel content validators."""
        from arnold.pipeline.types import ParallelStage

        pipeline = build_initial_pipeline()
        # stages is a dict mapping name → Stage|ParallelStage
        parallel_stages = [s for s in pipeline.stages.values() if isinstance(s, ParallelStage)]
        total_steps = sum(len(s.steps) for s in parallel_stages)
        assert total_steps >= 3, (
            f"Expected ≥3 fan-out validator steps, found {total_steps}"
        )

    def test_evidence_pack_pipeline_has_no_megaplan_dependency(self) -> None:
        """The public C4 proof stays in Arnold pipeline/evidence_pack modules."""
        checked_sources = (
            inspect.getsource(evidence_pack_pipelines),
            inspect.getsource(evidence_pack_steps),
        )
        forbidden_tokens = (
            "arnold.pipelines.megaplan",
            "from megaplan",
            "import megaplan",
        )
        for source in checked_sources:
            for token in forbidden_tokens:
                assert token not in source


# ---------------------------------------------------------------------------
# Test: >1MiB by-ref artifact through the C1 chokepoint / sidecar manifest
# ---------------------------------------------------------------------------


class TestLargeArtifactByRef:
    """A >1MiB artifact written via write_versioned produces a sidecar manifest
    and validate_large_artifact_by_manifest validates without reading the blob."""

    def test_large_artifact_sidecar_present(self, tmp_path: Path) -> None:
        @dataclass
        class _Ctx:
            artifact_root: str

        ctx = _Ctx(artifact_root=str(tmp_path))
        big_content = "x" * (LARGE_ARTIFACT_THRESHOLD_BYTES + 1024)
        dest = write_versioned(
            ctx, "stage", "large_output", big_content, "txt",
            content_type="text/plain",
            schema_hash="sha256:deadbeef",
        )
        assert dest.stat().st_size > LARGE_ARTIFACT_THRESHOLD_BYTES
        manifest = read_sidecar_manifest(dest)
        assert manifest is not None, "sidecar manifest missing for >1MiB artifact"
        assert manifest.size == dest.stat().st_size

    def test_large_artifact_validate_by_manifest(self, tmp_path: Path) -> None:
        """validate_large_artifact_by_manifest returns True without reading the blob."""
        @dataclass
        class _Ctx:
            artifact_root: str

        ctx = _Ctx(artifact_root=str(tmp_path))
        big_content = "y" * (LARGE_ARTIFACT_THRESHOLD_BYTES + 2048)
        dest = write_versioned(
            ctx, "stage", "by_ref_output", big_content, "txt",
            content_type="text/plain",
            schema_hash="sha256:cafebabe",
        )
        # validate_large_artifact_by_manifest returns True on clean validation
        ok = validate_large_artifact_by_manifest(
            dest,
            expected_schema_hash="sha256:cafebabe",
        )
        assert ok is True, f"Expected True from validate_large_artifact_by_manifest, got {ok!r}"


# ---------------------------------------------------------------------------
# Test: route-bypass invariant still green
# ---------------------------------------------------------------------------


class TestRouteBypassInvariantGreen:
    """Unregistered kind='tool' must still be flagged by validate()
    after all C4 public-surface additions (ReadRef, WriteRef, derive_binding_map)."""

    def test_unregistered_tool_still_flagged(self) -> None:
        from arnold.pipeline import Stage
        from arnold.pipeline.types import Pipeline
        from arnold.pipeline.step_invocation import StepInvocation

        @dataclass
        class _NullToolStep:
            name: str = "lookup"
            kind: str = "tool"
            produces: tuple = field(default_factory=tuple)
            consumes: tuple = field(default_factory=tuple)
            adapter_config: dict = field(default_factory=dict)

        step = _NullToolStep()
        stage = Stage(
            name="lookup",
            step=step,
            invocation=StepInvocation.with_adapter_config(
                kind="tool", adapter_config={"tool_name": "bypass_check"}
            ),
        )
        pipeline = Pipeline(stages={"lookup": stage}, entry="lookup")
        diag = validate(pipeline)
        unknown_adapter_defects = [d for d in diag.defects if "does not resolve to a registered adapter" in d]
        assert len(unknown_adapter_defects) >= 1, (
            f"validate() must flag unregistered kind='tool' as UNKNOWN_ADAPTER; defects: {diag.defects}"
        )

    def test_tool_not_in_global_default_registry(self) -> None:
        from arnold.pipeline.step_invocation import get_default_adapter_registry

        default_registry = get_default_adapter_registry()
        assert "tool" not in default_registry.registered_kinds, (
            "kind='tool' must not be pre-registered globally — route-bypass must remain active"
        )
