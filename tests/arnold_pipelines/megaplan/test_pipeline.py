"""Tests for the M3 explicit-node Megaplan pipeline."""

from __future__ import annotations

import pytest

from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline


class TestM3Pipeline:
    def test_build_pipeline_returns_m3_pipeline(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == "megaplan"

    def test_pipeline_steps_are_stable(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        step_ids = [step.id for step in pipeline.steps]
        assert step_ids == [
            "prep",
            "plan",
            "critique",
            "gate",
            "revise",
            "tiebreaker_run",
            "tiebreaker_decide",
            "finalize",
            "execute",
            "review",
            "halt",
            "override",
        ]

    def test_pipeline_compiles_to_valid_manifest(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        manifest = compile_pipeline(pipeline)
        assert manifest.id == "megaplan"
        assert manifest.manifest_hash is not None
        assert manifest.topology_hash is not None

    def test_gate_routes_encoded(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        gate_edges = {edge.label: edge for edge in pipeline.routes if edge.source == "gate"}
        for label in (
            "proceed",
            "iterate",
            "tiebreaker",
            "escalate",
            "abort",
            "suspend",
            "blocked_preflight",
            "force_proceed",
        ):
            assert label in gate_edges, f"missing gate route: {label}"

    def test_revise_loop_is_bounded(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline(max_critique_iterations=5)
        revise = next(step for step in pipeline.steps if step.id == "revise")
        assert revise.policy is not None
        assert revise.policy.loop is not None
        assert revise.policy.loop.max_iterations == 5

    def test_tiebreaker_loop_is_bounded(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline(max_critique_iterations=7)
        decide = next(step for step in pipeline.steps if step.id == "tiebreaker_decide")
        assert decide.policy is not None
        assert decide.policy.loop is not None
        assert decide.policy.loop.max_iterations == 7

    def test_compile_idempotency(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        m1 = compile_pipeline(build_pipeline())
        m2 = compile_pipeline(build_pipeline())
        assert m1.manifest_hash == m2.manifest_hash

    def test_legacy_pipeline_still_available(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_legacy_pipeline, compile_planning_pipeline

        legacy = build_legacy_pipeline()
        assert legacy is not None
        assert compile_planning_pipeline() is not None
