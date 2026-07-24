"""Native contract tests for compiled Megaplan pipeline output.

These tests separate two concerns:

1. **Authored DSL preservation** — the DSL pipeline built by
   ``build_pipeline()`` must maintain its step IDs, kinds, route labels,
   capabilities, metadata, and entry point as the authored source of truth.
   This class asserts the DSL shape is invariant; it does not compare DSL
   output against any compiled or native projection.

2. **Native substrate contract** — the compiled pipeline produced by
   ``build_and_compile_pipeline()`` must expose a native substrate shape
   with correct identity, version, metadata, non-null native program,
   canonical route labels, and independent instruction routing.  These
   assertions are direct native-contract checks, not DSL-vs-native parity
   comparisons.
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
    """The authored DSL pipeline shape must be invariant.

    These tests lock the DSL surface returned by ``build_pipeline()``.
    They are **not** parity checks against a compiled or native projection —
    they assert the authored source of truth directly.
    """

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
            "Authored step order must be invariant"
        )
        assert step_kinds == EXPECTED_STEP_KINDS, (
            "Authored step kinds must be invariant"
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
            "Authored capabilities must be invariant"
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


class TestCompiledNativeContract:
    """The compiled pipeline must satisfy the native substrate contract.

    These assertions verify the compiled canonical pipeline exposes the
    required native substrate shape: identity, version, metadata, non-null
    native program, canonical route labels, and independent instruction
    routing.  They are direct native-contract checks, not DSL-vs-native
    parity comparisons.
    """

    def test_native_program_is_present(self) -> None:
        """The compiled pipeline must carry a non-null NativeProgram."""
        from arnold.pipeline.native.ir import NativeProgram
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        native_program = getattr(pipeline, "native_program", None)

        assert native_program is not None, (
            "Native contract: compiled pipeline must expose non-null native_program"
        )
        assert isinstance(native_program, NativeProgram), (
            f"native_program must be a NativeProgram instance, "
            f"got {type(native_program).__name__}"
        )

    def test_compiled_shell_is_neutral_pipeline(self) -> None:
        """The compiled output must be an arnold.pipeline.types.Pipeline."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        assert isinstance(pipeline, NeutralPipeline), (
            f"Native contract: compiled pipeline must be a NeutralPipeline, "
            f"got {type(pipeline).__name__}"
        )

    def test_compiled_native_identity(self) -> None:
        """Compiled pipeline must carry correct id, version, and metadata."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        assert pipeline.id == "megaplan", (
            "Native contract: compiled pipeline id must be 'megaplan'"
        )
        assert pipeline.version == "m4-phase3", (
            "Native contract: compiled pipeline version must be 'm4-phase3'"
        )
        assert pipeline.metadata == {
            "product": "megaplan",
            "max_critique_iterations": 4,
        }, "Native contract: compiled pipeline metadata must match canonical metadata"

    def test_compiled_native_route_labels(self) -> None:
        """Compiled edges must carry the canonical route labels."""
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        compiled_edges = tuple(
            (e.id, e.source, e.target, e.label)
            for e in sorted(pipeline.edges, key=lambda e: e.id)
        )
        assert compiled_edges == tuple(sorted(EXPECTED_ROUTE_LABELS)), (
            "Native contract: compiled route labels must match canonical route labels"
        )

    def test_native_instruction_routing_is_independent(self) -> None:
        """Native instruction routing must not embed Megaplan topology assumptions.

        The native routing layer is generic.  This test verifies that the
        compiled pipeline's metadata and native program do not inject
        Megaplan-specific stage-order assumptions that would couple the
        generic native substrate to Megaplan topology.
        """
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()

        # Compiled metadata must not carry stage-order routing hints.
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

        # Native program description must not imply Megaplan-specific ordering.
        native_program = getattr(pipeline, "native_program", None)
        if native_program is not None:
            desc = getattr(native_program, "description", "") or ""
            assert "megaplan" not in desc.lower() or "substrate" in desc.lower(), (
                "NativeProgram description must not imply Megaplan-specific "
                "stage ordering for generic native routing"
            )


class TestCompileIdempotency:
    """Compilation from the authored DSL must be deterministic."""

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

    Per the North Star doctrine gate, the native substrate is substrate proof
    only and must not claim final native representation report conformance.
    """
    import argparse

    from arnold_pipelines.megaplan.cli import handle_describe

    response = handle_describe(argparse.Namespace(pipeline_name="megaplan"))
    assert response["success"] is True, (
        "megaplan describe must succeed for the canonical pipeline"
    )

    captured = capsys.readouterr().out.lower()

    substrate_markers = [
        "substrate proof only",
        "not final megaplan report conformance",
        "m1 dispatch substrate proof",
    ]
    found = any(marker in captured for marker in substrate_markers)
    assert found, (
        "Native substrate describe output must carry substrate-proof-only language. "
        f"Captured output snippet: {captured[:500]}"
    )
