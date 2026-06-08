"""Cursor-survival invariant: `topology.predecessors(stage, policy=...)`
reproduces the legacy `_BLOCKED_RECOVERY_STATES` / `_RESUME_ACTIVE_STATES`
mappings exactly, and the projection is stable across a mid-run
set-robustness flip (the resume cursor — a stage name — remains a valid
key whatever the realized graph just became).
"""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan._core.topology import (
    RealizedGraph,
    RunTopologyConfig,
    STAGE_TO_STATE,
    STATE_TO_STAGE,
    _RECOVERY_POLICIES,
    build_topology,
    predecessors,
)


# Legacy tables, pinned verbatim from override.py / workflow.py prior to
# M3 Step 7. Both tables were byte-identical; we keep one canonical copy
# and assert both policies project to it.
_LEGACY_RECOVERY_AND_RESUME: dict[str, str] = {
    "prep": "initialized",
    "plan": "initialized",
    "critique": "planned",
    "gate": "critiqued",
    "revise": "critiqued",
    "finalize": "gated",
    "execute": "finalized",
    "review": "executed",
    "feedback": "reviewed",
}


@pytest.mark.parametrize("policy", sorted(_RECOVERY_POLICIES))
@pytest.mark.parametrize(
    "stage,expected", sorted(_LEGACY_RECOVERY_AND_RESUME.items())
)
def test_predecessors_reproduces_legacy_tables(
    policy: str, stage: str, expected: str
) -> None:
    assert predecessors(stage, policy=policy) == expected


@pytest.mark.parametrize("policy", sorted(_RECOVERY_POLICIES))
def test_unknown_stage_returns_none(policy: str) -> None:
    assert predecessors("does-not-exist", policy=policy) is None


@pytest.mark.parametrize("policy", sorted(_RECOVERY_POLICIES))
@pytest.mark.parametrize(
    "stage",
    [
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "finalize",
        "execute",
        "review",
        "feedback",
    ],
)
def test_recovery_predecessor_projection_tolerates_all_runtime_variants(
    policy: str, stage: str
) -> None:
    for robustness in ("bare", "light", "full", "thorough", "extreme"):
        for with_prep in (False, True):
            for with_feedback in (False, True):
                _ = build_topology(
                    RunTopologyConfig(
                        robustness=robustness,
                        with_prep=with_prep,
                        with_feedback=with_feedback,
                    )
                )
                assert predecessors(stage, policy=policy) == _LEGACY_RECOVERY_AND_RESUME[stage]


@pytest.mark.parametrize("policy", sorted(_RECOVERY_POLICIES))
def test_unknown_phase_projection_is_non_fatal(policy: str) -> None:
    assert predecessors("unknown-phase-from-resume-cursor", policy=policy) is None


def test_unknown_policy_raises() -> None:
    with pytest.raises(ValueError):
        predecessors("plan", policy="bogus")


def test_stage_mode_requires_string() -> None:
    with pytest.raises(TypeError):
        predecessors(
            build_topology(RunTopologyConfig()),
            policy="recovery",  # type: ignore[arg-type]
        )


def test_graph_query_mode_still_works() -> None:
    # Backward-compat: the existing (graph, state, condition) call shape
    # must still return tuple[Edge, ...]; this is what parity tests use.
    graph = build_topology(RunTopologyConfig(robustness="extreme"))
    result = predecessors(graph, "planned")
    assert isinstance(result, tuple)
    # `predecessors(graph, state)` matches the method on Graph.
    assert result == graph.predecessors("planned")


def test_explicit_stage_state_maps_preserve_feedback_reviewed() -> None:
    assert STAGE_TO_STATE["feedback"] == "reviewed"
    assert STATE_TO_STAGE["reviewed"] == ("feedback",)
    assert STATE_TO_STAGE["initialized"] == ("prep", "plan")
    assert STATE_TO_STAGE["critiqued"] == ("gate", "revise")


def test_realized_graph_next_label_uses_real_edge_space() -> None:
    graph = RealizedGraph(RunTopologyConfig(robustness="full", with_feedback=True))
    assert graph.next_label(
        "plan",
        {"current_state": "prepped", "config": {"robustness": "full"}},
        {"current_state": "planned", "config": {"robustness": "full"}},
    ) == "critique"
    assert graph.next_label(
        "review",
        {"current_state": "executed", "config": {"robustness": "full", "with_feedback": True}},
        {"current_state": "reviewed", "config": {"robustness": "full", "with_feedback": True}},
    ) == "feedback"


def test_realized_graph_next_steps_preserves_synthetic_step() -> None:
    graph = RealizedGraph(RunTopologyConfig(robustness="full"))
    for state in ("planned", "critiqued", "gated", "finalized"):
        assert "step" in graph.next_steps({"current_state": state, "config": {"robustness": "full"}})


@pytest.mark.parametrize("policy", sorted(_RECOVERY_POLICIES))
def test_cursor_survives_midrun_robustness_flip(policy: str) -> None:
    """Simulate a mid-run set-robustness: rebuild the topology for every
    supported robustness (and prep/feedback flag combo), and assert the
    legacy mapping is reproduced verbatim each time.

    The resume cursor is a stage name (e.g. "execute"); after a flip the
    cursor must still project to the same active source state, because
    state identity is preserved across the rewrite.
    """

    robustness_levels = ("extreme", "thorough", "full", "light", "bare")
    flag_combos = (
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    )
    for robustness in robustness_levels:
        for with_prep, with_feedback in flag_combos:
            # The graph is rebuilt under the new config (mimicking a
            # mid-run set-robustness). `predecessors(..., policy=...)`
            # must still return the legacy mapping for every stage,
            # regardless of the current run config.
            _ = build_topology(
                RunTopologyConfig(
                    robustness=robustness,
                    with_prep=with_prep,
                    with_feedback=with_feedback,
                )
            )
            for stage, expected in _LEGACY_RECOVERY_AND_RESUME.items():
                assert predecessors(stage, policy=policy) == expected, (
                    f"stage={stage!r} policy={policy!r} "
                    f"robustness={robustness!r} with_prep={with_prep} "
                    f"with_feedback={with_feedback}"
                )


def test_recovery_and_resume_policies_project_identically() -> None:
    """The two legacy tables were byte-identical; the projection must
    preserve that property for every stage in either table.
    """

    for stage in _LEGACY_RECOVERY_AND_RESUME:
        recovery = predecessors(stage, policy="recovery")
        resume = predecessors(stage, policy="resume")
        assert recovery == resume == _LEGACY_RECOVERY_AND_RESUME[stage]


def test_override_handler_uses_topology_projection() -> None:
    """`override._override_recover_blocked` no longer reads a sidecar
    dict; the legacy `_BLOCKED_RECOVERY_STATES` constant is gone."""

    from arnold.pipelines.megaplan.handlers import override as override_mod

    assert not hasattr(override_mod, "_BLOCKED_RECOVERY_STATES")


def test_resume_plan_uses_topology_projection() -> None:
    """`workflow.resume_plan` no longer reads a sidecar dict; the legacy
    `_RESUME_ACTIVE_STATES` constant is gone."""

    from arnold.pipelines.megaplan._core import workflow as workflow_mod

    assert not hasattr(workflow_mod, "_RESUME_ACTIVE_STATES")
