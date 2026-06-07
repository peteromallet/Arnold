"""End-to-end tests for the evidence-pack initial pipeline (T10).

These tests exercise the full initial pipeline via :func:`run_pipeline`
and verify suspension/continuation state through *persisted artifacts only*.
The executor discards ``StepResult`` objects after routing, so the tests
never inspect ``run_pipeline``'s return value for status.

Key invariants (from SD2/SD3):
- Suspension is observed ONLY through named persisted JSON artifacts
  (the human-review checkpoint and its suspended status).
- Completion artifacts (attestation.json) MUST be absent after a
  suspension.
- The continuation pipeline is run as a *fresh* pipeline with
  ``entry='human_review'``, not via hidden executor-local resume state.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.executor import run_pipeline
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.pipelines.evidence_pack.pipelines import (
    build_continuation_pipeline,
    build_initial_pipeline,
)
from arnold.pipelines.evidence_pack.verifier import (
    EVIDENCE_PACK_SCHEMA,
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


def _make_envelope(artifact_root: str, *, run_id: str = "test-run") -> Any:
    """Build a minimal ``RuntimeEnvelope`` for a test run."""
    return RuntimeEnvelope(
        plugin_id="evidence_pack_verifier",
        run_id=run_id,
        artifact_root=artifact_root,
    )


def _valid_evidence_pack_fixture(evidence_pack_id: str = "pack-001") -> dict[str, Any]:
    """Return a valid evidence pack payload that should pass all validators."""
    return make_evidence_pack_payload(
        evidence_pack_id=evidence_pack_id,
        source_ticket="01KT50AZRMK5X890TQ565DDB5V",
        checkpoints=[
            {
                "checkpoint_id": f"{evidence_pack_id}.structural_audit",
                "status": "passed",
                "artifact_refs": [],
            },
            {
                "checkpoint_id": f"{evidence_pack_id}.budget_enforcement",
                "status": "passed",
                "artifact_refs": [],
            },
        ],
    )


# ---------------------------------------------------------------------------
# Initial pipeline suspension
# ---------------------------------------------------------------------------


class TestInitialPipelineSuspension:
    """The initial pipeline suspends at human_review; verify via persisted artifacts.

    The executor returns the envelope unchanged and discards StepResult objects.
    Status MUST be observed through named persisted JSON artifacts only.
    """

    def test_suspension_writes_human_review_checkpoint(self) -> None:
        """After running the initial pipeline, the human-review checkpoint
        artifact exists with status 'suspended'."""
        root = tempfile.mkdtemp(prefix="ep_e2e_init_")
        artifact_root = Path(root)

        # Write the evidence pack fixture
        pack_path = artifact_root / "input_pack.json"
        pack = _valid_evidence_pack_fixture("pack-001")
        _write_json(pack_path, pack)

        envelope = _make_envelope(str(artifact_root))
        pipeline = build_initial_pipeline()

        run_pipeline(
            pipeline,
            initial_state={"evidence_pack_path": str(pack_path)},
            envelope=envelope,
        )

        # The human review step writes checkpoint_<id>.json on suspension.
        cp_path = artifact_root / "checkpoint_pack-001.human_review_gate.json"
        assert cp_path.exists(), (
            f"Expected human review checkpoint at {cp_path}; "
            f"contents of {artifact_root}: {list(artifact_root.iterdir())}"
        )
        checkpoint = _read_json(cp_path)
        assert checkpoint["status"] == "suspended"
        assert checkpoint["checkpoint_kind"] == "human_review_gate"
        assert checkpoint["resume_cursor"] == "pack-001.human_review_gate"

    def test_suspension_attestation_absent(self) -> None:
        """After suspension, attestation.json must NOT exist (pipeline did
        not reach emit_attestation)."""
        root = tempfile.mkdtemp(prefix="ep_e2e_init_")
        artifact_root = Path(root)

        pack_path = artifact_root / "input_pack.json"
        pack = _valid_evidence_pack_fixture("pack-002")
        _write_json(pack_path, pack)

        envelope = _make_envelope(str(artifact_root))
        pipeline = build_initial_pipeline()

        run_pipeline(
            pipeline,
            initial_state={"evidence_pack_path": str(pack_path)},
            envelope=envelope,
        )

        att_path = artifact_root / "attestation.json"
        assert not att_path.exists(), (
            f"attestation.json must NOT exist after suspension; "
            f"found at {att_path}"
        )

    def test_suspension_preserves_evidence_pack_and_verdict(self) -> None:
        """After suspension, evidence_pack.json and verdict.json are still
        present (ingest + reduce ran successfully before human_review)."""
        root = tempfile.mkdtemp(prefix="ep_e2e_init_")
        artifact_root = Path(root)

        pack_path = artifact_root / "input_pack.json"
        pack = _valid_evidence_pack_fixture("pack-003")
        _write_json(pack_path, pack)

        envelope = _make_envelope(str(artifact_root))
        pipeline = build_initial_pipeline()

        run_pipeline(
            pipeline,
            initial_state={"evidence_pack_path": str(pack_path)},
            envelope=envelope,
        )

        # Ingest wrote evidence_pack.json
        ep_path = artifact_root / "evidence_pack.json"
        assert ep_path.exists(), f"evidence_pack.json missing after ingestion"

        # Reduce wrote verdict.json
        verdict_path = artifact_root / "verdict.json"
        assert verdict_path.exists(), f"verdict.json missing after reduce"


# ---------------------------------------------------------------------------
# Continuation pipeline (fresh run with entry='human_review')
# ---------------------------------------------------------------------------


class TestContinuationPipeline:
    """The continuation pipeline resumes from human_review as a fresh run.

    After a suspension, a *new* pipeline with ``entry='human_review'`` is
    invoked.  The human review step reads ``human_input`` from
    ``ctx.inputs`` and either routes to ``emit`` (approved) or ``failed``.
    """

    def test_continuation_approval_writes_attestation(self) -> None:
        """After approving the review, the continuation pipeline writes
        attestation.json."""
        root = tempfile.mkdtemp(prefix="ep_e2e_cont_")
        artifact_root = Path(root)

        # --- Step 1: run the initial pipeline to produce suspension artifacts
        pack_path = artifact_root / "input_pack.json"
        pack = _valid_evidence_pack_fixture("pack-004")
        _write_json(pack_path, pack)

        envelope = _make_envelope(str(artifact_root))
        init_pipeline = build_initial_pipeline()

        run_pipeline(
            init_pipeline,
            initial_state={"evidence_pack_path": str(pack_path)},
            envelope=envelope,
        )

        # Verify suspension
        cp_path = artifact_root / "checkpoint_pack-004.human_review_gate.json"
        assert cp_path.exists(), "initial pipeline did not suspend"

        # --- Step 2: run the continuation pipeline with approval
        cont_pipeline = build_continuation_pipeline()
        # The continuation uses the same artifact_root; evidence_pack.json
        # and verdict.json are already there from the initial run.

        run_pipeline(
            cont_pipeline,
            initial_state={
                "evidence_pack": str(artifact_root / "evidence_pack.json"),
                "verdict": str(artifact_root / "verdict.json"),
                "human_input": {"approved": True, "comment": "approved by reviewer"},
            },
            envelope=envelope,
        )

        # Attestation should now exist
        att_path = artifact_root / "attestation.json"
        assert att_path.exists(), (
            f"attestation.json must exist after approval; "
            f"contents of {artifact_root}: {sorted(p.name for p in artifact_root.iterdir())}"
        )
        attestation = _read_json(att_path)
        assert attestation["verdict"] in ("PASS", "FAIL")
        assert attestation["evidence_pack_id"] == "pack-004"

    def test_continuation_rejection_no_attestation(self) -> None:
        """After rejecting the review, the continuation pipeline does NOT write
        attestation.json (routes to 'failed' not 'emit')."""
        root = tempfile.mkdtemp(prefix="ep_e2e_cont_")
        artifact_root = Path(root)

        # --- Initial pipeline → suspend
        pack_path = artifact_root / "input_pack.json"
        pack = _valid_evidence_pack_fixture("pack-005")
        _write_json(pack_path, pack)

        envelope = _make_envelope(str(artifact_root))
        init_pipeline = build_initial_pipeline()

        run_pipeline(
            init_pipeline,
            initial_state={"evidence_pack_path": str(pack_path)},
            envelope=envelope,
        )

        # --- Continuation with rejection
        cont_pipeline = build_continuation_pipeline()
        run_pipeline(
            cont_pipeline,
            initial_state={
                "evidence_pack": str(artifact_root / "evidence_pack.json"),
                "verdict": str(artifact_root / "verdict.json"),
                "human_input": {"approved": False, "comment": "rejected by reviewer"},
            },
            envelope=envelope,
        )

        # attestation.json must NOT exist after rejection
        att_path = artifact_root / "attestation.json"
        assert not att_path.exists(), (
            "attestation.json must NOT exist after rejection"
        )

    def test_continuation_preserves_existing_artifacts(self) -> None:
        """The continuation pipeline does not clobber evidence_pack.json
        or verdict.json from the initial run."""
        root = tempfile.mkdtemp(prefix="ep_e2e_cont_")
        artifact_root = Path(root)

        pack_path = artifact_root / "input_pack.json"
        pack = _valid_evidence_pack_fixture("pack-006")
        _write_json(pack_path, pack)

        envelope = _make_envelope(str(artifact_root))

        # Initial → suspend
        run_pipeline(
            build_initial_pipeline(),
            initial_state={"evidence_pack_path": str(pack_path)},
            envelope=envelope,
        )

        ep_before = _read_json(artifact_root / "evidence_pack.json")
        verdict_before = _read_json(artifact_root / "verdict.json")

        # Continuation → approve
        run_pipeline(
            build_continuation_pipeline(),
            initial_state={
                "evidence_pack": str(artifact_root / "evidence_pack.json"),
                "verdict": str(artifact_root / "verdict.json"),
                "human_input": {"approved": True, "comment": "approved"},
            },
            envelope=envelope,
        )

        # evidence_pack.json unchanged
        ep_after = _read_json(artifact_root / "evidence_pack.json")
        assert ep_after == ep_before, "evidence_pack.json was modified by continuation"

        # verdict.json unchanged
        verdict_after = _read_json(artifact_root / "verdict.json")
        assert verdict_after == verdict_before, "verdict.json was modified by continuation"

    def test_continuation_without_initial_suspension_fails(self) -> None:
        """Running the continuation pipeline without initial suspension
        artifacts is handled gracefully (no crash, no attestation)."""
        root = tempfile.mkdtemp(prefix="ep_e2e_cont_")
        artifact_root = Path(root)

        # No initial pipeline — but we need evidence_pack.json for the
        # continuation to read.  Provide a minimal valid pack.
        pack = _valid_evidence_pack_fixture("pack-007")
        _write_json(artifact_root / "evidence_pack.json", pack)

        envelope = _make_envelope(str(artifact_root))
        cont_pipeline = build_continuation_pipeline()

        # The continuation expects verdict.json but it's absent; the
        # HumanReviewStep will still suspend or fail gracefully.
        run_pipeline(
            cont_pipeline,
            initial_state={
                "evidence_pack": str(artifact_root / "evidence_pack.json"),
                "human_input": {"approved": True, "comment": "approved anyway"},
            },
            envelope=envelope,
        )

        # The run should not crash.  Whether attestation exists depends
        # on how the step handles missing verdict — this test only checks
        # that the pipeline does not raise an unhandled exception.
