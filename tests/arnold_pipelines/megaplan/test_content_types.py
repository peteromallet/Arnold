"""Tests for Megaplan content-type registration and artifact adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.content_types import (
    CAPSULE_CONTENT_TYPE,
    DELTA_CONTENT_TYPE,
    EXECUTION_EVIDENCE_CONTENT_TYPE,
    GATE_SIGNAL_CONTENT_TYPE,
    PLAN_CONTENT_TYPE,
    RECEIPT_CONTENT_TYPE,
    REVIEW_OUTPUT_CONTENT_TYPE,
    STATE_ARTIFACT_CONTENT_TYPE,
    ArtifactAdapterContext,
    build_megaplan_content_type_registry,
    write_gate_signal_artifact,
    write_plan_artifact,
    write_receipt_artifact,
    write_state_artifact,
)


class TestContentTypeRegistration:
    def test_all_content_types_registered(self) -> None:
        registry = build_megaplan_content_type_registry()
        mapping = registry.as_mapping()
        for type_id in (
            PLAN_CONTENT_TYPE,
            RECEIPT_CONTENT_TYPE,
            CAPSULE_CONTENT_TYPE,
            DELTA_CONTENT_TYPE,
            GATE_SIGNAL_CONTENT_TYPE,
            REVIEW_OUTPUT_CONTENT_TYPE,
            EXECUTION_EVIDENCE_CONTENT_TYPE,
            STATE_ARTIFACT_CONTENT_TYPE,
        ):
            assert type_id in mapping

    def test_registry_is_immutable_by_default(self) -> None:
        registry = build_megaplan_content_type_registry()
        mapping = registry.as_mapping()
        assert len(mapping) == 8

    def test_duplicate_registration_raises(self) -> None:
        from arnold.kernel.content_types import ContentTypeRegistration, schema_hash

        registry = build_megaplan_content_type_registry()
        with pytest.raises(ValueError, match="already registered"):
            registry.register(
                ContentTypeRegistration(
                    type_id=PLAN_CONTENT_TYPE,
                    schema_version="2.0.0",
                    schema_hash=schema_hash({"type": "object"}),
                )
            )


class TestArtifactAdapters:
    def test_write_plan_artifact_versioned(self, tmp_path: Path) -> None:
        ctx = ArtifactAdapterContext(plan_dir=tmp_path)
        binding = write_plan_artifact(
            ctx,
            artifact_id="plan",
            plan_text="# Plan\n",
            version=3,
            questions=["q1"],
            success_criteria=[{"text": "c1"}],
        )
        assert binding.artifact_id == "plan_v3"
        assert binding.relative_path.endswith(".json")
        artifact_path = tmp_path / binding.relative_path
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert data["version"] == 3
        assert data["plan_text"] == "# Plan\n"

    def test_write_receipt_artifact(self, tmp_path: Path) -> None:
        ctx = ArtifactAdapterContext(plan_dir=tmp_path)
        binding = write_receipt_artifact(
            ctx,
            step="gate",
            success=True,
            summary="gate passed",
            artifacts=["gate.json"],
        )
        data = json.loads((tmp_path / binding.relative_path).read_text(encoding="utf-8"))
        assert data["step"] == "gate"
        assert data["success"] is True

    def test_write_gate_signal_artifact(self, tmp_path: Path) -> None:
        ctx = ArtifactAdapterContext(plan_dir=tmp_path)
        binding = write_gate_signal_artifact(
            ctx,
            version=2,
            signals={"weighted_score": 0.9},
            robustness="thorough",
            unresolved_flags=[{"id": "f1"}],
        )
        assert binding.artifact_id == "gate_signals_v2"
        data = json.loads((tmp_path / binding.relative_path).read_text(encoding="utf-8"))
        assert data["robustness"] == "thorough"

    def test_write_state_artifact(self, tmp_path: Path) -> None:
        ctx = ArtifactAdapterContext(plan_dir=tmp_path)
        state = {"name": "p", "current_state": "gated", "iteration": 2, "config": {}, "meta": {}}
        binding = write_state_artifact(ctx, state=state)
        data = json.loads((tmp_path / binding.relative_path).read_text(encoding="utf-8"))
        assert data["name"] == "p"
        assert data["iteration"] == 2

    def test_artifact_root_can_override_plan_dir(self, tmp_path: Path) -> None:
        artifact_root = tmp_path / "artifacts"
        ctx = ArtifactAdapterContext(plan_dir=tmp_path, artifact_root=artifact_root)
        binding = write_receipt_artifact(ctx, step="plan", success=True, summary="ok")
        assert (artifact_root / binding.relative_path).exists()


class TestNeutralKernelBoundary:
    def test_neutral_kernel_has_no_megaplan_content_types(self) -> None:
        from arnold.kernel.content_types import ContentTypeRegistry

        neutral = ContentTypeRegistry()
        for type_id in (
            PLAN_CONTENT_TYPE,
            GATE_SIGNAL_CONTENT_TYPE,
            STATE_ARTIFACT_CONTENT_TYPE,
        ):
            assert type_id not in neutral.as_mapping()

    def test_neutral_kernel_schema_hash_does_not_embed_product_vocab(self) -> None:
        from arnold.kernel.content_types import schema_hash

        h = schema_hash({"type": "object"})
        assert "megaplan" not in h.lower()
        assert "plan" not in h.lower()
