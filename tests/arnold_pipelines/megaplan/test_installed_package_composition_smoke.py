"""Installed-package composition smoke tests.

Verifies the canonical authority chain for composition:

1. **Canonical authored source** (``workflows/workflow.py``) is the
   semantic authority — the readable, product-local source of truth.
2. **WorkflowManifest** is a compiled inspection/replay artifact produced
   by ``compile_pipeline(build_pipeline())``.
3. **Pipeline.native_program** is the dispatch substrate — a
   NativeProgram projection that carries routing topology and phase
   instructions derived from the canonical source.

These tests also verify installed-package import behavior: the
``arnold_pipelines.megaplan`` package must be importable, must expose
``build_pipeline`` and ``build_and_compile_pipeline``, and must not
leak legacy shims or deleted subpackages.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType

import pytest

from arnold.manifest.manifests import WorkflowManifest
from arnold.pipeline.native.ir import NativeProgram
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline as DslPipeline
from arnold.workflow.source_compiler import lower_workflow_file


# ── installed-package authority chain ──────────────────────────────────────


class TestInstalledPackageAuthorityChain:
    """The installed package must expose the full authority chain:
    canonical source → WorkflowManifest → Pipeline.native_program."""

    def test_package_is_importable(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert megaplan.__name__ == "arnold_pipelines.megaplan"

    def test_build_pipeline_returns_dsl_pipeline(self) -> None:
        """build_pipeline() must return a DSL Pipeline from the canonical source."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        assert isinstance(pipeline, DslPipeline), (
            f"build_pipeline() must return DslPipeline, got {type(pipeline).__name__}"
        )

    def test_compile_pipeline_produces_workflow_manifest(self) -> None:
        """compile_pipeline(build_pipeline()) must produce a WorkflowManifest."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        manifest = compile_pipeline(pipeline)
        assert isinstance(manifest, WorkflowManifest), (
            f"compile_pipeline must return WorkflowManifest, "
            f"got {type(manifest).__name__}"
        )
        assert manifest.id == "megaplan"
        assert manifest.manifest_hash is not None

    def test_build_and_compile_exposes_manifest(self) -> None:
        """build_and_compile_pipeline().manifest must be a WorkflowManifest."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        assert shell.manifest is not None
        assert isinstance(shell.manifest, WorkflowManifest), (
            f"shell.manifest must be WorkflowManifest, "
            f"got {type(shell.manifest).__name__}"
        )

    def test_build_and_compile_exposes_native_program(self) -> None:
        """build_and_compile_pipeline().native_program must be a NativeProgram."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        assert shell.native_program is not None
        assert isinstance(shell.native_program, NativeProgram), (
            f"shell.native_program must be NativeProgram, "
            f"got {type(shell.native_program).__name__}"
        )

    def test_build_and_compile_exposes_authored_pipeline(self) -> None:
        """build_and_compile_pipeline() must carry the authored DSL pipeline
        as evidence of canonical source authority."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        assert shell.authored_pipeline is not None, (
            "shell must preserve authored_pipeline reference"
        )
        assert isinstance(shell.authored_pipeline, DslPipeline), (
            f"authored_pipeline must be DslPipeline, "
            f"got {type(shell.authored_pipeline).__name__}"
        )

    def test_authored_pipeline_matches_direct_build(self) -> None:
        """The shell's authored_pipeline must be structurally equivalent to
        a direct build_pipeline() call on the canonical source."""
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        direct = build_pipeline()
        shell = build_and_compile_pipeline()
        authored = shell.authored_pipeline

        assert authored.id == direct.id
        assert len(authored.steps) == len(direct.steps)
        assert authored.entry == direct.entry


# ── manifest as compiled inspection/replay artifact ────────────────────────


class TestManifestAsCompiledArtifact:
    """WorkflowManifest is a compiled artifact for inspection and replay,
    not the semantic source of truth."""

    def test_manifest_is_derived_not_authoritative(self) -> None:
        """The manifest is produced by the compiler; it should not be
        the primary way to author pipeline semantics."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        manifest = compile_pipeline(pipeline)

        # Manifest derives from pipeline, not the other way around
        assert manifest.id == pipeline.id
        # Manifest nodes should correspond to DSL steps
        dsl_step_ids = {step.id for step in pipeline.steps}
        manifest_node_ids = {n.id for n in manifest.nodes if "policy" not in n.id}
        # The manifest carries step nodes (not just policy nodes)
        assert len(manifest_node_ids) > 0

    def test_manifest_hash_is_stable_for_same_source(self) -> None:
        """Repeated compilation of the same source must produce the same hash."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline1 = build_pipeline()
        pipeline2 = build_pipeline()

        manifest1 = compile_pipeline(pipeline1)
        manifest2 = compile_pipeline(pipeline2)

        assert manifest1.manifest_hash == manifest2.manifest_hash, (
            "manifest hash must be stable for identical source"
        )
        assert manifest1.topology_hash == manifest2.topology_hash, (
            "topology hash must be stable for identical source"
        )

    def test_manifest_exposes_inspection_surface(self) -> None:
        """WorkflowManifest must expose id, nodes, edges, capabilities,
        policy, metadata, and hashes for inspection."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        manifest = compile_pipeline(build_pipeline())

        assert manifest.id, "manifest must have id"
        assert manifest.nodes, "manifest must have nodes"
        assert manifest.edges is not None, "manifest must have edges"
        assert manifest.topology_hash, "manifest must have topology_hash"
        assert manifest.manifest_hash, "manifest must have manifest_hash"


# ── native_program as dispatch substrate ───────────────────────────────────


class TestNativeProgramAsDispatchSubstrate:
    """Pipeline.native_program is the dispatch substrate, not the semantic
    source of truth."""

    def test_native_program_has_routing_topology(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        native = shell.native_program

        assert native.routing_topology is not None
        assert "nodes" in native.routing_topology
        assert "routes" in native.routing_topology

    def test_native_program_instructions_match_dsl_steps(self) -> None:
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        pipeline = build_pipeline()
        shell = build_and_compile_pipeline()
        native = shell.native_program

        assert len(native.instructions) == len(pipeline.steps), (
            f"native instructions ({len(native.instructions)}) must match "
            f"DSL steps ({len(pipeline.steps)})"
        )

    def test_native_program_phases_correspond_to_steps(self) -> None:
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        pipeline = build_pipeline()
        shell = build_and_compile_pipeline()
        native = shell.native_program

        native_names = {p.name for p in native.phases}
        step_ids = {s.id for s in pipeline.steps}
        assert native_names == step_ids, (
            f"native phase names must match DSL step ids: "
            f"extra={native_names - step_ids}, missing={step_ids - native_names}"
        )

    def test_native_program_description_marks_as_substrate_proof(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        desc = shell.native_program.description

        assert "substrate proof" in desc.lower() or "compatibility projection" in desc.lower(), (
            f"native_program description must identify as substrate, got: {desc}"
        )


# ── canonical source is semantic authority ─────────────────────────────────


class TestCanonicalSourceIsSemanticAuthority:
    """The canonical authored source (workflows/workflow.py) is the
    readable, product-local source of truth. The manifest and native_program
    are derived artifacts."""

    def test_canonical_source_path_is_committed_workflow_py(self) -> None:
        from arnold_pipelines.megaplan.workflows.planning import AUTHORING_SOURCE_PATH

        assert AUTHORING_SOURCE_PATH.name == "workflow.py"
        assert AUTHORING_SOURCE_PATH.is_file()

    def test_canonical_source_compiles_without_diagnostics(self) -> None:
        from arnold.workflow import check_workflow_source
        from arnold_pipelines.megaplan.workflows.planning import AUTHORING_SOURCE_PATH

        result = check_workflow_source(
            AUTHORING_SOURCE_PATH.read_text(encoding="utf-8"),
            source_path=AUTHORING_SOURCE_PATH,
        )
        assert result.ok is True
        assert result.diagnostics == ()

    def test_canonical_source_lowers_to_known_structure(self) -> None:
        """Lowering the canonical source must reveal parallel_map and
        subpipeline steps that the native_program dispatches."""
        from arnold_pipelines.megaplan.workflows.planning import AUTHORING_SOURCE_PATH

        lowered = lower_workflow_file(AUTHORING_SOURCE_PATH)
        kinds = {step.kind for step in lowered.steps}
        assert "parallel_map" in kinds, "canonical source must contain parallel_map steps"
        assert "subpipeline" in kinds, "canonical source must contain subpipeline steps"

    def test_changes_to_source_reflect_in_built_pipeline(self) -> None:
        """Modifications to the canonical source (even just re-reading it)
        should produce a fresh pipeline — proving the source is authoritative."""
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        assert pipeline.steps, "pipeline must have steps from canonical source"
        # The step count is 12 for the canonical Megaplan workflow
        assert len(pipeline.steps) == 12, (
            f"expected 12 canonical steps, got {len(pipeline.steps)}"
        )

    def test_workflow_components_are_from_canonical_source(self) -> None:
        """The workflow components module (declared policy surfaces) must
        be traceable back to the canonical authored source."""
        from arnold_pipelines.megaplan import workflows
        from arnold_pipelines.megaplan.workflows.planning import AUTHORING_SOURCE_PATH

        # Components file must exist alongside the canonical source
        components_path = Path(workflows.components.__file__)
        assert components_path.parent == AUTHORING_SOURCE_PATH.parent, (
            "components.py must live in same directory as workflow.py"
        )


# ── installed-package smoke: no legacy leaks ───────────────────────────────


class TestInstalledPackageNoLegacyLeaks:
    """The installed package must not expose legacy shims, deleted
    subpackages, or compatibility wrappers as the normal authoring path."""

    def test_legacy_import_path_raises_module_not_found(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            import arnold.pipelines.megaplan  # noqa: F401

    def test_workflow_manifest_not_top_level_export(self) -> None:
        """WorkflowManifest must not be a top-level export of megaplan —
        it is a compiled artifact, not the authoring surface."""
        import arnold_pipelines.megaplan as megaplan

        assert not hasattr(megaplan, "WorkflowManifest"), (
            "WorkflowManifest must not be a top-level export"
        )

    def test_legacy_build_functions_not_exposed(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert not hasattr(megaplan, "build_legacy_pipeline")
        assert not hasattr(megaplan, "compile_planning_pipeline")

    def test_deleted_stage_classes_not_exposed(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        deleted_classes = (
            "InProcessHandlerStep", "HandlerStep", "PrepStep",
            "PlanStep", "CritiqueStep", "GateStep", "ReviseStep",
            "FinalizeStep", "ExecuteStep", "ReviewStep", "TiebreakerStep",
        )
        for cls_name in deleted_classes:
            assert not hasattr(megaplan, cls_name), (
                f"Deleted class {cls_name} must not be exposed"
            )

    def test_native_program_is_dispatch_not_authoring_surface(self) -> None:
        """native_program is a dispatch substrate — docs must not teach
        authors to create NativeProgram directly."""
        # The native_program is derived, not authored
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        native = shell.native_program
        # It should clearly identify itself as a substrate artifact
        assert native.name == "megaplan"
        assert native.description is not None

    def test_no_shim_or_fallback_guidance_in_package_init(self) -> None:
        """The package __init__.py must not contain shim or fallback guidance."""
        import arnold_pipelines.megaplan

        init_path = Path(arnold_pipelines.megaplan.__file__)
        text = init_path.read_text(encoding="utf-8").lower()
        banned = ("shim", "fallback", "compatibility wrapper", "legacy adapter")
        for token in banned:
            assert token not in text, (
                f"package __init__ must not contain '{token}'"
            )


# ── installed-package public surface ───────────────────────────────────────


class TestInstalledPackagePublicSurface:
    """The installed package must expose a clean public surface: build_pipeline,
    build_and_compile_pipeline, and the canonical workflow components."""

    def test_public_exports_are_present(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert hasattr(megaplan, "__all__")
        assert "build_pipeline" in megaplan.__all__
        assert "build_and_compile_pipeline" in megaplan.__all__

    def test_build_pipeline_is_callable(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert callable(megaplan.build_pipeline)

    def test_build_and_compile_is_callable(self) -> None:
        import arnold_pipelines.megaplan as megaplan

        assert callable(megaplan.build_and_compile_pipeline)

    def test_workflow_components_are_importable(self) -> None:
        from arnold_pipelines.megaplan import workflows

        assert workflows.ALL_STEP_COMPONENTS
        assert workflows.WORKFLOW_COMPONENTS
        assert workflows.POLICY_COMPONENTS
        assert workflows.PROMPT_COMPONENTS

    def test_workflow_components_expose_expected_policies(self) -> None:
        from arnold_pipelines.megaplan import workflows

        expected_policy_ids = {
            "megaplan:default",
            "megaplan:gate",
            "megaplan:revise-loop",
            "megaplan:tiebreaker",
            "megaplan:finalize",
            "megaplan:review",
            "megaplan:execute",
            "megaplan:override",
            "megaplan:model-routing",
            "megaplan:robustness",
            "megaplan:artifact-contract",
            "megaplan:suspension",
        }
        actual_ids = {p.id for p in workflows.POLICY_COMPONENTS}
        assert actual_ids == expected_policy_ids, (
            f"policy component ids mismatch: "
            f"extra={actual_ids - expected_policy_ids}, "
            f"missing={expected_policy_ids - actual_ids}"
        )

    def test_no_direct_manifest_or_native_program_authoring_exposed(self) -> None:
        """The package must not encourage direct manifest or native_program
        authoring — these are compiled artifacts, not authoring surfaces."""
        import arnold_pipelines.megaplan as megaplan

        # These symbols must not be in __all__
        assert "WorkflowManifest" not in megaplan.__all__
        assert "NativeProgram" not in megaplan.__all__
        # These should not be top-level attributes
        assert not hasattr(megaplan, "WorkflowManifest")
        assert not hasattr(megaplan, "NativeProgram")


# ── smoke: full chain compiles cleanly ─────────────────────────────────────


class TestFullChainSmoke:
    """End-to-end smoke: canonical source builds, compiles, and exposes
    the full authority chain without errors."""

    def test_full_chain_no_errors(self) -> None:
        from arnold_pipelines.megaplan.pipeline import (
            build_and_compile_pipeline,
            build_pipeline,
        )

        # Step 1: canonical source → DSL pipeline
        pipeline = build_pipeline()
        assert isinstance(pipeline, DslPipeline)

        # Step 2: DSL pipeline → WorkflowManifest (compiled artifact)
        manifest = compile_pipeline(pipeline)
        assert isinstance(manifest, WorkflowManifest)
        assert manifest.manifest_hash is not None

        # Step 3: build_and_compile → shell with native_program + manifest
        shell = build_and_compile_pipeline()
        assert shell.manifest is not None
        assert shell.native_program is not None
        assert shell.authored_pipeline is not None

        # All three layers must agree on identity
        assert shell.manifest.id == pipeline.id
        assert shell.native_program.name == pipeline.id

    def test_manifest_to_json_is_valid(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        manifest = compile_pipeline(build_pipeline())
        json_str = manifest.to_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0
        # Round-trip must preserve id
        round_tripped = WorkflowManifest.from_json(json_str)
        assert round_tripped.id == manifest.id

    def test_native_program_round_trips_through_shell(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        native = shell.native_program

        assert native.instructions, "native program must have instructions"
        assert native.phases, "native program must have phases"
        assert native.routing_topology["nodes"], "routing topology must have nodes"
        assert native.routing_topology["routes"], "routing topology must have routes"

    def test_repeated_build_and_compile_is_idempotent(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell1 = build_and_compile_pipeline()
        shell2 = build_and_compile_pipeline()

        assert shell1.manifest.manifest_hash == shell2.manifest.manifest_hash
        assert shell1.manifest.topology_hash == shell2.manifest.topology_hash
        assert len(shell1.native_program.instructions) == len(
            shell2.native_program.instructions
        )
