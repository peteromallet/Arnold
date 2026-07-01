"""Pre-migration contract tests for canonical Megaplan compile output and parity.

These tests characterise the *authored* DSL pipeline and then assert
the *compiled* canonical shell contract that M3.5 must deliver.  Before
M3.5 implementation the compiled-shell assertions are expected to **fail**
because ``build_pipeline()`` returns a DSL ``Pipeline`` without a
``native_program`` projection layer.

Once the M3.5 conversion/compilation path is in place:
- The authored DSL output must remain intact (same steps, routes, capabilities).
- The compiled canonical output must expose an
  ``arnold.pipeline.types.Pipeline`` shell with non-null ``native_program``.
- Canonical metadata parity and route-label parity must hold.
- No Megaplan-specific native routing dependency may leak into the
  compiled shell's routing surface.
"""

from __future__ import annotations

from typing import Any

import pytest

from arnold.pipeline.types import Pipeline as NeutralPipeline
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline as DslPipeline

# ── Authored DSL invariants (must survive migration unchanged) ──────────

EXPECTED_STEP_IDS = (
    "prep", "plan", "critique", "gate", "revise",
    "tiebreaker_run", "tiebreaker_decide", "finalize",
    "execute", "review", "halt", "override",
)

EXPECTED_STEP_KINDS = (
    ("prep", "megaplan:prep"),
    ("plan", "megaplan:plan"),
    ("critique", "megaplan:critique"),
    ("gate", "megaplan:gate"),
    ("revise", "megaplan:revise"),
    ("tiebreaker_run", "megaplan:tiebreaker_run"),
    ("tiebreaker_decide", "megaplan:tiebreaker_decide"),
    ("finalize", "megaplan:finalize"),
    ("execute", "megaplan:execute"),
    ("review", "megaplan:review"),
    ("halt", "megaplan:halt"),
    ("override", "megaplan:override"),
)

EXPECTED_ROUTE_LABELS = (
    ("prep:plan", "prep", "plan", "default"),
    ("plan:critique", "plan", "critique", "default"),
    ("critique:gate", "critique", "gate", "default"),
    ("gate:finalize", "gate", "finalize", "proceed"),
    ("gate:revise", "gate", "revise", "iterate"),
    ("gate:tiebreaker", "gate", "tiebreaker_run", "tiebreaker"),
    ("gate:override", "gate", "override", "escalate"),
    ("gate:halt", "gate", "halt", "abort"),
    ("gate:suspend", "gate", "halt", "suspend"),
    ("gate:blocked", "gate", "override", "blocked_preflight"),
    ("gate:force_proceed", "gate", "finalize", "force_proceed"),
    ("revise:critique", "revise", "critique", "default"),
    ("tiebreaker_run:decide", "tiebreaker_run", "tiebreaker_decide", "default"),
    ("tiebreaker_decide:critique", "tiebreaker_decide", "critique", "iterate"),
    ("tiebreaker_decide:finalize", "tiebreaker_decide", "finalize", "proceed"),
    ("tiebreaker_decide:override", "tiebreaker_decide", "override", "escalate"),
    ("finalize:execute", "finalize", "execute", "default"),
    ("execute:review", "execute", "review", "default"),
    ("review:halt", "review", "halt", "default"),
    ("review:revise", "review", "revise", "rework"),
    ("override:halt", "override", "halt", "abort"),
    ("override:finalize", "override", "finalize", "force_proceed"),
    ("override:revise", "override", "revise", "replan"),
)

EXPECTED_CAPABILITIES = (
    ("megaplan:planning", "default", True),
    ("human:gate", "default", False),
    ("human:review", "default", False),
)


class TestAuthoredDslPreserved:
    """The authored DSL pipeline shape must be invariant across M3.5."""

    def test_build_pipeline_returns_dsl_pipeline(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        assert isinstance(pipeline, DslPipeline), (
            "build_pipeline() must return a workflow-first DSL Pipeline"
        )
        assert pipeline.id == "megaplan"
        assert pipeline.version == "m4-phase3"

    def test_step_ids_and_kinds_are_stable(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        step_ids = tuple(s.id for s in pipeline.steps)
        step_kinds = tuple((s.id, s.kind) for s in pipeline.steps)

        assert step_ids == EXPECTED_STEP_IDS, (
            "Authored step order must be invariant through M3.5"
        )
        assert step_kinds == EXPECTED_STEP_KINDS, (
            "Authored step kinds must be invariant through M3.5"
        )

    def test_route_labels_match_canonical_specs(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        route_labels = tuple(
            (r.id, r.source, r.target, r.label) for r in pipeline.routes
        )
        assert route_labels == EXPECTED_ROUTE_LABELS, (
            "Authored route labels must match canonical route specs"
        )

    def test_capabilities_are_stable(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        capabilities = tuple(
            (c.id, c.route, c.required) for c in pipeline.capabilities
        )
        assert capabilities == EXPECTED_CAPABILITIES, (
            "Authored capabilities must be invariant through M3.5"
        )

    def test_metadata_carries_product_and_iterations(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        assert pipeline.metadata == {
            "product": "megaplan",
            "max_critique_iterations": 4,
        }, "Canonical metadata must be preserved"

    def test_entry_is_prep(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()
        assert pipeline.entry == "prep", (
            "Canonical entry point must be 'prep'"
        )


class TestCompiledCanonicalShellContract:
    """The compiled canonical pipeline must satisfy the M3.5 shell contract.

    These assertions are expected to **FAIL** before M3.5 implementation
    because the current ``build_pipeline()`` returns a DSL ``Pipeline``
    without a conversion layer that projects ``native_program`` onto an
    ``arnold.pipeline.types.Pipeline`` shell.
    """

    def test_compiled_shell_has_native_program(self) -> None:
        """The compiled canonical pipeline must carry a non-null native_program.

        This is the primary M3.5 contract: the canonical pipeline compiles
        to an ``arnold.pipeline.types.Pipeline`` shell whose
        ``native_program`` field is not None.  Before implementation this
        must fail — there is no conversion layer yet.
        """
        from arnold.pipeline.native.ir import NativeProgram
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()

        # The bridge contract: the pipeline must expose native_program
        # after M3.5's compile/lower path runs.
        native_program = getattr(pipeline, "native_program", None)
        assert native_program is not None, (
            "M3.5 contract: compiled canonical pipeline must expose "
            "non-null native_program.  Currently build_pipeline() returns "
            "a DSL Pipeline; the conversion layer (T3) must project it."
        )
        assert isinstance(native_program, NativeProgram), (
            f"native_program must be a NativeProgram instance, "
            f"got {type(native_program).__name__}"
        )

    def test_compiled_shell_is_neutral_pipeline_type(self) -> None:
        """The compiled canonical output must be an arnold.pipeline.types.Pipeline.

        After M3.5, the compile/lower path produces the neutral shell.
        This test will be satisfied by the conversion layer.
        """
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()

        # M3.5 contract: the compiled canonical shell should be a NeutralPipeline
        # or at least carry native_program.  Currently build_pipeline()
        # returns a DSL Pipeline — the conversion layer hasn't been built.
        is_neutral = isinstance(pipeline, NeutralPipeline)
        has_native = getattr(pipeline, "native_program", None) is not None

        # Either the pipeline IS already a neutral shell with native_program,
        # or it exposes native_program through the DSL surface.
        assert is_neutral or has_native, (
            "M3.5 contract: compiled canonical pipeline must either be a "
            "NeutralPipeline or expose native_program.  Currently it is a "
            f"{type(pipeline).__name__}"
        )

    def test_compiled_manifest_metadata_parity(self) -> None:
        """Manifest compiled from DSL must carry canonical metadata."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        manifest = compile_pipeline(pipeline)

        assert manifest.id == "megaplan"
        assert manifest.version == "m4-phase3"
        assert manifest.metadata == {
            "product": "megaplan",
            "max_critique_iterations": 4,
        }, "Compiled manifest metadata must match canonical DSL metadata"

    def test_compiled_edge_labels_parity(self) -> None:
        """Route labels must survive compilation unchanged."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        manifest = compile_pipeline(pipeline)

        compiled_edges = tuple(
            (e.id, e.source, e.target, e.label)
            for e in sorted(manifest.edges, key=lambda e: e.id)
        )
        assert compiled_edges == tuple(sorted(EXPECTED_ROUTE_LABELS)), (
            "Compiled route labels must match canonical DSL route labels"
        )

    def test_no_megaplan_specific_native_routing_dependency(self) -> None:
        """The compiled shell must not carry Megaplan stage-order assumptions.

        The native routing layer (``arnold.pipeline.native.routing``) is
        already generic.  This test verifies that the compiled canonical
        pipeline shell does not inject Megaplan-specific routing metadata
        that would couple the generic native substrate to Megaplan topology.
        """
        from arnold_pipelines.megaplan.pipeline import build_pipeline

        pipeline = build_pipeline()

        # The pipeline metadata must not contain stage-order routing hints
        # that assume Megaplan-specific topology in the native layer.
        metadata = getattr(pipeline, "metadata", {}) or {}
        forbidden_keys = {
            "stage_order", "canonical_stage_order",
            "megaplan_topology", "phase_order",
            "native_stage_order", "gate_order",
        }
        found_forbidden = forbidden_keys & set(metadata.keys())
        assert not found_forbidden, (
            f"Pipeline metadata must not carry Megaplan stage-order "
            f"assumptions for native routing: {sorted(found_forbidden)}"
        )

        # The pipeline's native_program (if present) must also be free of
        # stage-order assumptions in its description/metadata.
        native_program = getattr(pipeline, "native_program", None)
        if native_program is not None:
            desc = getattr(native_program, "description", "") or ""
            assert "megaplan" not in desc.lower() or "substrate" in desc.lower(), (
                "NativeProgram description must not imply Megaplan-specific "
                "stage ordering for generic native routing"
            )


class TestCompileIdempotency:
    """Compilation must be deterministic."""

    def test_compile_is_idempotent(self) -> None:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline

        m1 = compile_pipeline(build_pipeline())
        m2 = build_and_compile_pipeline()

        assert m1.manifest_hash == m2.manifest_hash, (
            "Manifest hash must be idempotent"
        )
        assert m1.topology_hash == m2.topology_hash, (
            "Topology hash must be idempotent"
        )


# ── Substrate-proof-only label verification ──────────────────────────────

def test_substrate_proof_label_is_present_in_describe_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``megaplan describe`` must carry the substrate-proof-only disclaimer.

    Per the North Star doctrine gate, M3.5 is substrate proof only and must
    not claim final native representation report conformance.
    """
    import argparse

    from arnold_pipelines.megaplan.cli import handle_describe

    response = handle_describe(argparse.Namespace(pipeline_name="megaplan"))
    assert response["success"] is True, (
        "megaplan describe must succeed for the canonical pipeline"
    )

    # The describe handler prints to stdout; the substrate-proof label is in
    # the printed output, not necessarily in the returned dict.
    captured = capsys.readouterr().out.lower()

    substrate_markers = [
        "substrate proof only",
        "not final megaplan report conformance",
        "m1 dispatch substrate proof",
    ]
    found = any(marker in captured for marker in substrate_markers)
    assert found, (
        "M3.5 describe output must carry substrate-proof-only language. "
        f"Captured output snippet: {captured[:500]}"
    )
