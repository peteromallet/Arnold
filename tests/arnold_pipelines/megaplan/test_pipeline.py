"""Tests for the M4 Megaplan planning pipeline facade."""

from __future__ import annotations

import pytest

from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline


class TestM4Pipeline:
    def test_build_pipeline_returns_m4_pipeline(self) -> None:
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        pipeline = build_pipeline()
        assert isinstance(pipeline, Pipeline)
        assert pipeline.id == "megaplan"
        assert callable(build_and_compile_pipeline)

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

    def test_public_facade_exports_are_stable(self) -> None:
        import arnold_pipelines.megaplan.pipeline as pipeline_mod
        from arnold_pipelines.megaplan.workflows import planning

        assert pipeline_mod.__all__ == [
            "build_and_compile_pipeline",
            "build_pipeline",
        ]
        assert pipeline_mod.build_pipeline is planning.build_pipeline
        assert callable(pipeline_mod.build_pipeline)
        assert callable(pipeline_mod.build_and_compile_pipeline)

    def test_pipeline_compiles_to_valid_manifest(self) -> None:
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        pipeline = build_pipeline()
        manifest = build_and_compile_pipeline()
        compiled_from_public_builder = compile_pipeline(pipeline)
        assert manifest.id == "megaplan"
        assert manifest.manifest_hash is not None
        assert manifest.topology_hash is not None
        assert manifest.to_json() == compiled_from_public_builder.to_json()

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

    def test_gate_tiebreaker_and_review_route_order_is_stable(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        route_labels_by_source = {
            source: [route.label for route in pipeline.routes if route.source == source]
            for source in ("gate", "tiebreaker_decide", "review")
        }

        assert route_labels_by_source["gate"] == [
            "proceed",
            "iterate",
            "tiebreaker",
            "escalate",
            "abort",
            "suspend",
            "blocked_preflight",
            "force_proceed",
        ]
        assert route_labels_by_source["tiebreaker_decide"] == [
            "iterate",
            "proceed",
            "escalate",
        ]
        assert route_labels_by_source["review"] == [
            "default",
            "rework",
        ]

    def test_revise_loop_is_bounded(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline(max_critique_iterations=5)
        revise = next(step for step in pipeline.steps if step.id == "revise")
        assert revise.policy is not None
        assert revise.policy.loop is not None
        assert revise.policy.loop.max_iterations == 4

    def test_tiebreaker_loop_is_bounded(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline(max_critique_iterations=7)
        decide = next(step for step in pipeline.steps if step.id == "tiebreaker_decide")
        assert decide.policy is not None
        assert decide.policy.loop is not None
        assert decide.policy.loop.max_iterations == 4

    def test_compile_idempotency(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline

        m1 = compile_pipeline(build_pipeline())
        m2 = build_and_compile_pipeline()
        assert m1.manifest_hash == m2.manifest_hash
        assert m1.topology_hash == m2.topology_hash

    # ── Absence tests: removed legacy names must not be importable ──────────

    def test_build_legacy_pipeline_not_importable(self) -> None:
        import arnold_pipelines.megaplan.pipeline as pipeline_mod

        assert not hasattr(pipeline_mod, "build_legacy_pipeline")
        with pytest.raises(AttributeError):
            getattr(pipeline_mod, "build_legacy_pipeline")

    def test_compile_planning_pipeline_not_importable_from_pipeline(self) -> None:
        import arnold_pipelines.megaplan.pipeline as pipeline_mod

        assert not hasattr(pipeline_mod, "compile_planning_pipeline")
        with pytest.raises(AttributeError):
            getattr(pipeline_mod, "compile_planning_pipeline")

    def test_legacy_names_not_in_pipeline_module_all(self) -> None:
        import arnold_pipelines.megaplan.pipeline as pipeline_mod

        pipeline_all = getattr(pipeline_mod, "__all__", [])
        for removed_name in ("build_legacy_pipeline", "compile_planning_pipeline"):
            assert removed_name not in pipeline_all, (
                f"{removed_name!r} must not appear in pipeline.__all__"
            )

    # ── Absence tests: deleted submodules must not be importable ─────────

    _DELETED_SUBMODULES = (
        "arnold_pipelines.megaplan._pipeline",
        "arnold_pipelines.megaplan._pipeline._bridge",
        "arnold_pipelines.megaplan._pipeline.builder",
        "arnold_pipelines.megaplan._pipeline.dispatch",
        "arnold_pipelines.megaplan._pipeline.runtime",
        "arnold_pipelines.megaplan._pipeline.types",
        "arnold_pipelines.megaplan.stages",
        "arnold_pipelines.megaplan.stages.inprocess_step",
    )

    def test_deleted_submodules_raise_module_not_found(self) -> None:
        """Deleted _pipeline and stages submodules must
        raise ModuleNotFoundError on import."""
        import importlib

        for mod_name in self._DELETED_SUBMODULES:
            with pytest.raises(ModuleNotFoundError):
                importlib.import_module(mod_name)

    def test_deleted_submodules_not_in_sys_modules(self) -> None:
        """No deleted prefix keys should leak into sys.modules after importing
        the pipeline module."""
        import sys

        # Ensure we've imported the pipeline module
        import arnold_pipelines.megaplan.pipeline  # noqa: F401

        deleted_prefixes = (
            "arnold_pipelines.megaplan._pipeline",
            "arnold_pipelines.megaplan.stages",
        )
        leaked = [
            key
            for key in sys.modules
            if any(key == prefix or key.startswith(prefix + ".") for prefix in deleted_prefixes)
        ]
        assert not leaked, f"sys.modules contains deleted module keys: {leaked}"

    def test_top_level_deleted_symbols_not_in_pipeline_module(self) -> None:
        """Top-level legacy symbols must not be accessible from the pipeline
        module as direct attributes or via getattr."""
        import arnold_pipelines.megaplan.pipeline as pipeline_mod

        for name in (
            "build_legacy_pipeline",
            "compile_planning_pipeline",
            "WorkflowManifest",
            "run_pipeline",
            "InProcessHandlerStep",
            "HandlerStep",
            "Stage",
            "build_planning_pipeline",
        ):
            assert not hasattr(pipeline_mod, name), (
                f"hasattr(pipeline, {name!r}) must be False"
            )
            with pytest.raises(AttributeError):
                getattr(pipeline_mod, name)
