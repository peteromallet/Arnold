"""Tests for the canonical Megaplan authored workflow source."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import yaml

from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline

from arnold_pipelines.megaplan import pipeline as pipeline_facade
from arnold_pipelines.megaplan import workflows
from arnold_pipelines.megaplan.workflows import planning


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "megaplan_m4_topology.yaml"


class TestAuthoredWorkflow:
    def test_build_pipeline_returns_m3_pipeline(self) -> None:
        pipeline = planning.build_pipeline()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == "megaplan"
        assert pipeline.version == "m4-phase3"

    def test_step_order_matches_fixture(self) -> None:
        pipeline = planning.build_pipeline()
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

    def test_route_table_is_complete(self) -> None:
        pipeline = planning.build_pipeline()
        route_labels = {(r.source, r.label) for r in pipeline.routes}
        expected = {
            ("prep", "default"),
            ("plan", "default"),
            ("critique", "default"),
            ("gate", "proceed"),
            ("gate", "iterate"),
            ("gate", "tiebreaker"),
            ("gate", "escalate"),
            ("gate", "abort"),
            ("gate", "suspend"),
            ("gate", "blocked_preflight"),
            ("gate", "force_proceed"),
            ("revise", "default"),
            ("tiebreaker_run", "default"),
            ("tiebreaker_decide", "iterate"),
            ("tiebreaker_decide", "proceed"),
            ("tiebreaker_decide", "escalate"),
            ("finalize", "default"),
            ("execute", "default"),
            ("review", "default"),
            ("review", "rework"),
            ("override", "abort"),
            ("override", "force_proceed"),
            ("override", "replan"),
        }
        assert route_labels == expected

    def test_facade_delegates_to_workflows_planning(self) -> None:
        assert pipeline_facade.build_pipeline is planning.build_pipeline

    def test_facade_compiled_output_matches_locked_topology(self) -> None:
        fixture = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
        manifest = pipeline_facade.build_and_compile_pipeline()
        assert manifest.id == fixture["manifest_id"]
        assert manifest.manifest_hash == fixture["manifest_hash"]
        assert manifest.topology_hash == fixture["topology_hash"]

    def test_lowerer_matches_phase1_normalized_shape(self) -> None:
        """The authored workflow lowerer must be identical to the facade."""
        from_facade = pipeline_facade.build_pipeline(max_critique_iterations=7)
        from_workflow = planning.build_pipeline(max_critique_iterations=7)
        assert from_facade == from_workflow

    def test_importing_planning_does_not_load_legacy_package(self) -> None:
        before = set(sys.modules.keys())
        importlib.reload(planning)
        loaded = {m for m in set(sys.modules.keys()) - before if m.startswith("arnold.pipelines.megaplan.")}
        assert loaded == set(), f"planning import loaded legacy modules: {loaded}"

    def test_prompt_provenance_in_components_not_manifest(self) -> None:
        """Prompt family refs are discoverable on components but must not leak
        into compiled manifest hash-participating fields.
        """
        pipeline = planning.build_pipeline()
        manifest = compile_pipeline(pipeline)
        # Topology hash equality with the locked fixture proves provenance did
        # not enter the topology. Also assert no step metadata carries prompt
        # resolver details, which would alter the manifest hash.
        for step in pipeline.steps:
            for key in step.metadata:
                assert "prompt" not in key.lower(), (
                    f"step {step.id} metadata key {key!r} may affect manifest hash"
                )
        fixture = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
        assert manifest.topology_hash == fixture["topology_hash"]

    def test_components_connect_to_workflow_steps(self) -> None:
        """Every authored DSL step has a matching product component."""
        pipeline = planning.build_pipeline()
        component_ids = {c.id.removeprefix("megaplan:") for c in workflows.ALL_STEP_COMPONENTS}
        step_ids = {step.id for step in pipeline.steps}
        assert step_ids == component_ids
