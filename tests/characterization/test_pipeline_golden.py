"""Golden characterization for the canonical Megaplan pipeline surface.

The public ``build_pipeline()`` surface now returns a workflow-first
``arnold.workflow.dsl.Pipeline`` graph. This characterization pins the
deterministic graph shape exposed by the canonical megaplan pipeline.
"""

from __future__ import annotations

from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.dsl import Pipeline
from arnold_pipelines.megaplan.pipeline import build_pipeline


EXPECTED_STEP_ORDER = (
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

EXPECTED_ROUTES = (
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


def test_build_pipeline_returns_workflow_first_pipeline() -> None:
    pipeline = build_pipeline()

    assert isinstance(pipeline, Pipeline)
    assert pipeline.id == "megaplan"
    assert pipeline.version == "m4-phase3"
    assert pipeline.entry == "prep"
    assert tuple(s.id for s in pipeline.steps) == EXPECTED_STEP_ORDER
    assert tuple((s.id, s.kind) for s in pipeline.steps) == EXPECTED_STEP_KINDS


def test_build_pipeline_route_shape_matches_graph_contract() -> None:
    pipeline = build_pipeline()

    assert tuple(
        (r.id, r.source, r.target, r.label) for r in pipeline.routes
    ) == EXPECTED_ROUTES


def test_build_pipeline_capabilities_match_workflow_manifest() -> None:
    pipeline = build_pipeline()

    assert tuple(
        (c.id, c.route, c.required) for c in pipeline.capabilities
    ) == EXPECTED_CAPABILITIES


def test_compiled_manifest_preserves_workflow_graph_shape() -> None:
    pipeline = build_pipeline()
    manifest = compile_pipeline(pipeline)

    assert manifest.id == "megaplan"
    assert manifest.version == "m4-phase3"
    assert manifest.schema_version == "arnold.workflow.manifest.v1"
    assert manifest.metadata == {"product": "megaplan", "max_critique_iterations": 4}

    assert tuple((n.id, n.kind) for n in sorted(manifest.nodes, key=lambda n: n.id)) == tuple(
        sorted(EXPECTED_STEP_KINDS)
    )
    assert tuple(
        (e.id, e.source, e.target, e.label)
        for e in sorted(manifest.edges, key=lambda e: e.id)
    ) == tuple(sorted(EXPECTED_ROUTES))
    assert tuple(
        (c.capability_id, c.route, c.required) for c in manifest.capabilities
    ) == EXPECTED_CAPABILITIES
