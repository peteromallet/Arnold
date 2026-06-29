from __future__ import annotations

from arnold.pipeline.topology import compute_topology_hash
from arnold.workflow.validator import validate
from arnold.pipelines.megaplan.pipeline import _build_legacy_graph_pipeline
from arnold.pipelines.megaplan.routing import tiebreaker_edges


EXPECTED_LEGACY_TOPOLOGY_HASH = (
    "sha256:f11cd2e61fdb8fcb8aac558db6ceb5aef2a936cd2a58c0277a7e45523512ba30"
)

EXPECTED_LEGACY_VALIDATOR_DEFECTS = (
    "stage 'critique': dependency 'plan_payload' is unsatisfied (missing from predecessor 'revise')",
    "stage 'critique': dependency 'revise_payload' is unsatisfied (missing from predecessor 'plan')",
    "stage 'critique': dependency 'tiebreaker_payload' is unsatisfied (missing from predecessor 'plan')",
)

EXPECTED_LEGACY_EDGE_MAP = {
    "prep": (
        ("pass", "plan", "normal"),
        ("fail", "halt", "normal"),
        ("plan", "plan", "normal"),
    ),
    "plan": (("critique", "critique", "normal"),),
    "critique": (
        ("gate_unset:gate", "gate", "normal"),
        ("gate", "gate", "normal"),
    ),
    "gate": (
        ("proceed", "finalize", "decision"),
        ("iterate", "revise", "decision"),
        ("tiebreaker", "tiebreaker", "decision"),
        ("escalate", "finalize", "decision"),
        ("revise", "revise", "normal"),
        ("gate", "finalize", "normal"),
        ("override force-proceed", "finalize", "normal"),
        ("override abort", "halt", "normal"),
    ),
    "revise": (("critique", "critique", "normal"),),
    "finalize": (("execute", "execute", "normal"),),
    "execute": (("review", "review", "normal"),),
    "review": (
        ("review", "halt", "normal"),
        ("halt", "halt", "normal"),
    ),
    "tiebreaker": (
        ("iterate", "critique", "decision"),
        ("proceed", "finalize", "decision"),
        ("escalate", "finalize", "decision"),
    ),
}

EXPECTED_GATE_DECISION_LABELS = ("proceed", "iterate", "tiebreaker", "escalate")
EXPECTED_GATE_OVERRIDE_LABELS = ("override force-proceed", "override abort")
EXPECTED_TIEBREAKER_LABELS = ("iterate", "proceed", "escalate")


def _edge_map(pipeline) -> dict[str, tuple[tuple[str, str, str], ...]]:
    return {
        stage_name: tuple((edge.label, edge.target, edge.kind) for edge in stage.edges)
        for stage_name, stage in pipeline.stages.items()
    }


def test_legacy_pipeline_topology_hash_and_validator_status_are_baselined() -> None:
    pipeline = _build_legacy_graph_pipeline()

    assert compute_topology_hash(pipeline) == EXPECTED_LEGACY_TOPOLOGY_HASH

    diagnostics = validate(pipeline)
    assert diagnostics.ok is False
    assert tuple(str(defect) for defect in diagnostics.defects) == (
        EXPECTED_LEGACY_VALIDATOR_DEFECTS
    )


def test_legacy_pipeline_edges_and_branch_labels_are_baselined() -> None:
    pipeline = _build_legacy_graph_pipeline()

    assert _edge_map(pipeline) == EXPECTED_LEGACY_EDGE_MAP

    gate_edges = pipeline.stages["gate"].edges
    assert tuple(
        edge.label for edge in gate_edges if edge.kind == "decision"
    ) == EXPECTED_GATE_DECISION_LABELS
    assert tuple(
        edge.label for edge in gate_edges if edge.label.startswith("override ")
    ) == EXPECTED_GATE_OVERRIDE_LABELS

    assert tuple(
        edge.label
        for edge in tiebreaker_edges(
            on_iterate="critique",
            on_proceed="finalize",
            on_escalate="finalize",
        )
    ) == EXPECTED_TIEBREAKER_LABELS
