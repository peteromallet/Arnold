"""Native contract tests: canonical Megaplan vs native-backed subpipelines.

These tests assert that the canonical megaplan pipeline satisfies the same
``native_program`` contract that subpipelines (creative, doc, jokes, etc.)
already satisfy.  The canonical pipeline must:

- Carry a non-null ``native_program`` (same contract as subpipelines).
- Have route-label alignment between DSL and native projection.
- Carry canonical metadata consistent with DSL metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.native.ir import NativePipeline, NativeProgram
from arnold.pipeline.types import Pipeline as NeutralPipeline
from arnold.workflow.source_compiler import lower_workflow_file
from arnold_pipelines.megaplan.workflows.planning import AUTHORING_SOURCE_PATH


# ── Subpipeline baselines (what the canonical pipeline must match) ────────


def _assert_subpipeline_native_contract(
    build_fn: Any,
    pipeline_name: str,
) -> NeutralPipeline:
    """Verify a subpipeline satisfies the native contract and return it."""
    pipeline = build_fn()
    assert isinstance(pipeline, NeutralPipeline), (
        f"{pipeline_name}: build_pipeline() must return NeutralPipeline"
    )
    native = pipeline.native_program
    assert native is not None, (
        f"{pipeline_name}: native_program must not be None"
    )
    assert isinstance(native, NativeProgram), (
        f"{pipeline_name}: native_program must be NativeProgram, "
        f"got {type(native).__name__}"
    )
    assert native.name, (
        f"{pipeline_name}: NativeProgram must have non-empty name"
    )
    assert native.instructions, (
        f"{pipeline_name}: NativeProgram must have instructions"
    )
    return pipeline


class TestSubpipelineNativeContractBaseline:
    """Existing subpipelines already satisfy the native contract.

    These tests serve as the *target* for the canonical megaplan pipeline.
    They document the contract the canonical
    pipeline must match.
    """

    def test_creative_satisfies_native_contract(self) -> None:
        from arnold_pipelines.megaplan.pipelines.creative import (
            build_pipeline as build_creative,
        )

        pipeline = _assert_subpipeline_native_contract(build_creative, "creative")
        assert pipeline.native_program.name == "creative"
        assert len(pipeline.native_program.instructions) >= 5, (
            "creative must have at least 5 native instructions"
        )

    def test_doc_satisfies_native_contract(self) -> None:
        from arnold_pipelines.megaplan.pipelines.doc import (
            build_pipeline as build_doc,
        )

        pipeline = _assert_subpipeline_native_contract(build_doc, "doc")
        assert pipeline.native_program.name == "doc"
        assert len(pipeline.native_program.instructions) >= 5

    def test_jokes_satisfies_native_contract(self) -> None:
        from arnold_pipelines.megaplan.pipelines.jokes import (
            build_pipeline as build_jokes,
        )

        pipeline = _assert_subpipeline_native_contract(build_jokes, "jokes")
        assert pipeline.native_program.name == "jokes"
        assert pipeline.entry == "draft"

    def test_live_supervisor_satisfies_native_contract(self) -> None:
        from arnold_pipelines.megaplan.pipelines.live_supervisor import (
            build_pipeline as build_live_supervisor,
        )

        pipeline = _assert_subpipeline_native_contract(
            build_live_supervisor, "live_supervisor"
        )
        assert pipeline.native_program.name == "live-supervisor"

    def test_select_tournament_satisfies_native_contract(self) -> None:
        from arnold_pipelines.megaplan.pipelines.select_tournament import (
            build_pipeline as build_select_tournament,
        )

        pipeline = _assert_subpipeline_native_contract(
            build_select_tournament, "select_tournament"
        )
        assert pipeline.native_program.name == "select-tournament"

    def test_writing_panel_strict_satisfies_native_contract(self) -> None:
        from arnold_pipelines.megaplan.pipelines.writing_panel_strict import (
            build_pipeline as build_writing_panel_strict,
        )

        pipeline = _assert_subpipeline_native_contract(
            build_writing_panel_strict, "writing_panel_strict"
        )
        assert pipeline.native_program.name == "writing-panel-strict"


# ── Canonical Megaplan native contract assertions ─────────────────────────


class TestCanonicalMegaplanNativeContract:
    """The canonical megaplan pipeline must satisfy the native contract.

    These assertions verify that ``build_pipeline()`` exposes a
    ``native_program`` consistent with the subpipeline contract.
    """

    def test_canonical_has_native_program_like_subpipelines(self) -> None:
        """Canonical megaplan must carry native_program (same contract)."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        native_program = getattr(pipeline, "native_program", None)

        assert native_program is not None, (
            "Native contract: canonical megaplan build_pipeline() "
            "must expose native_program just like creative, doc, jokes, "
            "and all other subpipelines.  Currently: None."
        )

    def test_canonical_native_program_is_nativeprogram_instance(self) -> None:
        """If native_program exists, it must be a NativeProgram."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        native_program = getattr(pipeline, "native_program", None)

        if native_program is not None:
            assert isinstance(native_program, NativeProgram), (
                f"native_program must be NativeProgram, "
                f"got {type(native_program).__name__}"
            )

    def test_canonical_native_program_has_instructions(self) -> None:
        """Native program must have a non-empty instruction sequence."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        native_program = getattr(pipeline, "native_program", None)

        if native_program is not None:
            assert native_program.instructions, (
                "NativeProgram must have non-empty instructions"
            )

    def test_canonical_is_neutral_pipeline_or_has_native_bundle(self) -> None:
        """Pipeline must be a NeutralPipeline or carry native dispatch evidence."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        is_neutral = isinstance(pipeline, NeutralPipeline)
        has_native = getattr(pipeline, "native_program", None) is not None

        # At minimum, the pipeline must be native-dispatch-capable.
        from arnold.pipeline.native.routing import has_native_dispatch_capability

        capable = has_native_dispatch_capability(pipeline)
        assert capable or is_neutral or has_native, (
            "Native contract: canonical megaplan must be native-dispatch-capable "
            "or expose native_program.  has_native_dispatch_capability() "
            f"returned {capable}"
        )

    def test_canonical_step_count_consistent_with_subpipelines(self) -> None:
        """Canonical pipeline has 12 steps; subpipelines have 3-10.

        The absolute number is not enforced — just that we can count them.
        """
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        pipeline = build_pipeline()
        compiled = build_and_compile_pipeline()
        # DSL pipelines have .steps, neutral pipelines have .stages
        if hasattr(pipeline, "steps"):
            step_count = len(pipeline.steps)
        elif hasattr(pipeline, "stages"):
            step_count = len(pipeline.stages)
        else:
            step_count = 0

        assert step_count > 0, (
            "Canonical megaplan pipeline must have steps or stages"
        )
        assert step_count == len(compiled.native_program.instructions), (
            "Canonical megaplan shell must preserve the visible stage count "
            f"(pipeline={step_count}, native={len(compiled.native_program.instructions)})"
        )

    def test_canonical_metadata_consistent_dsl_vs_native(self) -> None:
        """Canonical metadata must be consistent between DSL and native views."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline
        from arnold_pipelines.megaplan.planning.operations import canonical_metadata
        from arnold_pipelines.megaplan.workflows import planning as workflow_planning

        pipeline = build_and_compile_pipeline()
        metadata = getattr(pipeline, "metadata", {}) or {}
        canonical = canonical_metadata()

        # DSL metadata carries product + max_critique_iterations
        assert metadata.get("product") == "megaplan", (
            "Canonical pipeline metadata must identify product=megaplan"
        )
        assert canonical["authored_source_path"] == str(workflow_planning.AUTHORING_SOURCE_PATH.resolve())

        native_program = getattr(pipeline, "native_program", None)
        if native_program is not None:
            # Native program name should align with pipeline id
            pipeline_id = getattr(pipeline, "id", None) or pipeline.__class__.__name__
            native_name = native_program.name
            assert native_name, (
                f"NativeProgram name should not be empty "
                f"(pipeline id: {pipeline_id})"
            )

    def test_authoring_source_can_expand_wrapper_nodes_without_breaking_native_shell(self) -> None:
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        shell = build_and_compile_pipeline()
        pipeline = build_pipeline()
        lowered = lower_workflow_file(AUTHORING_SOURCE_PATH)

        assert len(shell.native_program.instructions) == len(pipeline.steps)
        assert len(lowered.steps) > len(shell.native_program.instructions)
        assert {step.id for step in lowered.steps}.issuperset(
            {"gate_abort", "tiebreaker_finalize", "override_finalize"}
        )

    def test_native_program_shell_is_projection_not_canonical_traceability_proof(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        lowered = lower_workflow_file(AUTHORING_SOURCE_PATH)

        instruction_names = {instruction.name for instruction in shell.native_program.instructions}
        lowered_step_ids = {step.id for step in lowered.steps}

        # The projected shell intentionally collapses wrapper nodes, so it cannot
        # stand in for row-level correctness proof when canonical source exists.
        assert {"gate_abort", "tiebreaker_finalize", "override_finalize"} <= lowered_step_ids
        assert {"gate_abort", "tiebreaker_finalize", "override_finalize"}.isdisjoint(
            instruction_names
        )
        assert str(AUTHORING_SOURCE_PATH).endswith("workflow.pypeline")


class TestNativeRoutingIndependence:
    """Native routing must work generically, not via Megaplan stage-order."""

    def test_select_fresh_runtime_does_not_reference_megaplan_stages(
        self,
    ) -> None:
        """Fresh runtime selection must not hard-code Megaplan stage names."""
        import inspect

        from arnold.pipeline.native import routing as native_routing

        source = inspect.getsource(native_routing.select_fresh_runtime_owner)
        # The fresh-runtime selector must not mention Megaplan stage names
        megaplan_stages = {
            "prep", "plan", "critique", "gate", "revise",
            "tiebreaker", "finalize", "execute", "review",
            "override", "halt", "tiebreaker_run", "tiebreaker_decide",
        }
        source_lower = source.lower()
        found = [s for s in megaplan_stages if s in source_lower]
        assert not found, (
            f"select_fresh_runtime_owner must not reference Megaplan "
            f"stage names: {found}"
        )

    def test_select_runtime_for_dispatch_is_generic(self) -> None:
        """Runtime dispatch must not depend on Megaplan stage order."""
        import inspect

        from arnold.pipeline.native import routing as native_routing

        source = inspect.getsource(native_routing.select_runtime_for_dispatch)
        megaplan_stages = {
            "prep", "plan", "critique", "gate", "revise",
            "tiebreaker", "finalize", "execute", "review",
        }
        source_lower = source.lower()
        found = [s for s in megaplan_stages if s in source_lower]
        assert not found, (
            f"select_runtime_for_dispatch must not reference Megaplan "
            f"stage names: {found}"
        )

    def test_has_native_dispatch_capability_is_generic(self) -> None:
        """Native dispatch capability check must not be Megaplan-specific."""
        import inspect

        from arnold.pipeline.native import routing as native_routing

        source = inspect.getsource(native_routing.has_native_dispatch_capability)
        # This function must not import megaplan or reference megaplan stages
        assert "megaplan" not in source.lower(), (
            "has_native_dispatch_capability must not reference 'megaplan'"
        )

    def test_native_routing_module_has_no_megaplan_imports(self) -> None:
        """The native routing module must not import from arnold_pipelines.megaplan."""
        import ast
        from pathlib import Path

        routing_path = (
            Path(__file__).resolve().parents[3]
            / "arnold/pipeline/native/routing.py"
        )
        tree = ast.parse(routing_path.read_text(encoding="utf-8"))

        megaplan_imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "megaplan" in alias.name:
                        megaplan_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "megaplan" in module:
                    megaplan_imports.append(module)

        assert not megaplan_imports, (
            f"arnold/pipeline/native/routing.py must not import from "
            f"megaplan: {megaplan_imports}"
        )


# ── Substrate-proof-only assertion ────────────────────────────────────────

def test_substrate_proof_only_native_routing_is_generic() -> None:
    """Generic native routing must not have Megaplan-specific fallback logic.

    Per success criterion #5: Native routing and executor substrate files
    contain no Megaplan-specific stage-order or topology fallback logic.
    """
    from pathlib import Path

    import ast

    root = Path(__file__).resolve().parents[3]
    substrate_files = [
        root / "arnold/pipeline/native/routing.py",
        root / "arnold/pipeline/executor.py",
    ]

    # Only flag stage names that are unambiguously Megaplan-specific.
    # Generic concepts like "halt" (reserved termination target),
    # "entry", and "target" are legitimate pipeline vocabulary in
    # the neutral executor and must not be flagged.
    megaplan_stage_names = {
        "prep", "plan", "critique", "gate", "revise",
        "tiebreaker", "finalize", "execute", "review",
        "override",
    }

    for file_path in substrate_files:
        assert file_path.is_file(), f"Substrate file missing: {file_path}"
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        source = file_path.read_text(encoding="utf-8").lower()

        # Check for Megaplan stage names used as string literals
        # (which would indicate stage-order assumptions)
        for stage in megaplan_stage_names:
            # Only flag if the stage name appears as a string literal
            # that looks like routing logic (not in comments/docstrings)
            if f'"{stage}"' in source or f"'{stage}'" in source:
                # Check if it's in a non-docstring context
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        if node.value == stage:
                            # Found a string literal — check if it's in a docstring
                            parent = getattr(node, 'parent', None)
                            assert False, (
                                f"{file_path.name} contains Megaplan stage "
                                f"name '{stage}' as a string literal — "
                                f"potential stage-order assumption leak"
                            )
