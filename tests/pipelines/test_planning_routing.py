"""Tests for :mod:`megaplan.pipelines.planning.routing` (T8)."""

from __future__ import annotations

from arnold.pipeline.types import Edge


class TestPlanningLiterals:
    """Verify the four planning decision literals and override spelling."""

    def test_four_planning_decision_literals_defined(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import (
            PLAN_ESCALATE,
            PLAN_ITERATE,
            PLAN_PROCEED,
            PLAN_TIEBREAKER,
        )

        assert PLAN_PROCEED == "proceed"
        assert PLAN_ITERATE == "iterate"
        assert PLAN_TIEBREAKER == "tiebreaker"
        assert PLAN_ESCALATE == "escalate"

    def test_planning_decisions_tuple_contains_all_four(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import PLANNING_DECISIONS

        assert PLANNING_DECISIONS == ("proceed", "iterate", "tiebreaker", "escalate")

    def test_override_spelling_force_proceed(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import (
            OVERRIDE_FORCE_PROCEED,
            OVERRIDE_FORCE_PROCEED_CLI,
        )

        assert OVERRIDE_FORCE_PROCEED == "force_proceed"
        assert OVERRIDE_FORCE_PROCEED_CLI == "force-proceed"

    def test_cli_to_internal_override_maps_force_proceed(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import cli_to_internal_override

        assert cli_to_internal_override("force-proceed") == "force_proceed"

    def test_internal_to_cli_override_maps_force_proceed(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import internal_to_cli_override

        assert internal_to_cli_override("force_proceed") == "force-proceed"

    def test_override_spelling_roundtrip(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import (
            cli_to_internal_override,
            internal_to_cli_override,
        )

        assert internal_to_cli_override(cli_to_internal_override("force-proceed")) == "force-proceed"

    def test_unknown_override_passthrough(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import (
            cli_to_internal_override,
            internal_to_cli_override,
        )

        assert cli_to_internal_override("unknown") == "unknown"
        assert internal_to_cli_override("unknown") == "unknown"


class TestPlanningGateEdges:
    """Tests for :func:`planning_gate_edges`."""

    def test_four_decision_edges_with_correct_targets(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import planning_gate_edges

        edges = planning_gate_edges(
            on_proceed="finalize",
            on_iterate="revise",
            on_tiebreaker="tiebreaker_stage",
            on_escalate="finalize",
        )
        assert len(edges) == 4
        all_decision = all(e.kind == "decision" for e in edges)
        assert all_decision, f"Expected all decision edges, got kinds: {[e.kind for e in edges]}"

        labels = {e.label for e in edges}
        assert labels == {"proceed", "iterate", "tiebreaker", "escalate"}

        label_to_target = {e.label: e.target for e in edges}
        assert label_to_target["proceed"] == "finalize"
        assert label_to_target["iterate"] == "revise"
        assert label_to_target["tiebreaker"] == "tiebreaker_stage"
        assert label_to_target["escalate"] == "finalize"

    def test_no_kind_gate_edges(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import planning_gate_edges

        edges = planning_gate_edges(
            on_proceed="p",
            on_iterate="i",
            on_tiebreaker="t",
            on_escalate="e",
        )
        assert not any(e.kind == "gate" for e in edges), (
            "planning_gate_edges must not produce kind='gate'"
        )

    def test_gate_extra_edges_appended(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import planning_gate_edges

        extra = (Edge(label="custom", target="somewhere", kind="normal"),)
        edges = planning_gate_edges(
            on_proceed="p",
            on_iterate="i",
            on_tiebreaker="t",
            on_escalate="e",
            gate_extra_edges=extra,
        )
        assert len(edges) == 5
        assert edges[4].label == "custom"
        assert edges[4].kind == "normal"

    def test_preserves_existing_targets(self) -> None:
        """Edges must preserve the exact target names passed by the caller."""
        from arnold.pipelines.megaplan.pipelines.planning.routing import planning_gate_edges

        edges = planning_gate_edges(
            on_proceed="finalize_phase",
            on_iterate="revise_phase",
            on_tiebreaker="tiebreaker_phase",
            on_escalate="escalation_handler",
        )
        targets = {e.target for e in edges}
        assert "finalize_phase" in targets
        assert "revise_phase" in targets
        assert "tiebreaker_phase" in targets
        assert "escalation_handler" in targets


class TestTiebreakerEdges:
    """Tests for :func:`tiebreaker_edges`."""

    def test_three_decision_edges_with_populated_labels(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import tiebreaker_edges

        edges = tiebreaker_edges(
            on_iterate="revise",
            on_proceed="finalize",
            on_escalate="escalation",
        )
        assert len(edges) == 3

        for edge in edges:
            assert edge.kind == "decision", f"Expected kind='decision', got {edge.kind!r}"
            assert edge.label != "", "Tiebreaker edge label must NOT be empty"

        labels = {e.label for e in edges}
        assert labels == {"iterate", "proceed", "escalate"}

    def test_tiebreaker_labels_are_populated_not_empty(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import tiebreaker_edges

        edges = tiebreaker_edges(
            on_iterate="r",
            on_proceed="f",
            on_escalate="e",
        )
        for edge in edges:
            assert edge.label, f"Tiebreaker edge has empty label (target={edge.target!r})"

    def test_tiebreaker_preserves_existing_targets(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import tiebreaker_edges

        edges = tiebreaker_edges(
            on_iterate="revise_stage",
            on_proceed="finalize_stage",
            on_escalate="escalate_stage",
        )
        label_to_target = {e.label: e.target for e in edges}
        assert label_to_target["iterate"] == "revise_stage"
        assert label_to_target["proceed"] == "finalize_stage"
        assert label_to_target["escalate"] == "escalate_stage"


class TestPlanningOverrideEdges:
    """Tests for :func:`planning_override_edges`."""

    def test_override_edges_use_correct_kind_and_label(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import planning_override_edges

        edges = planning_override_edges(
            overrides={"force_proceed": "finalize", "abort": "halt"}
        )
        assert len(edges) == 2
        for edge in edges:
            assert edge.kind == "override"
        labels = {e.label for e in edges}
        assert labels == {"override force_proceed", "override abort"}

    def test_empty_overrides_returns_empty(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import planning_override_edges

        edges = planning_override_edges(overrides={})
        assert edges == ()


class TestCritiqueReviseGateRouting:
    """Tests for :func:`critique_revise_gate_routing`."""

    def test_returns_three_keys(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import critique_revise_gate_routing

        result = critique_revise_gate_routing(
            on_proceed="finalize",
            on_iterate="revise",
            on_tiebreaker="tiebreaker",
            on_escalate="finalize",
        )
        assert set(result.keys()) == {"critique", "gate", "revise"}

    def test_critique_edge_targets_gate(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import critique_revise_gate_routing

        result = critique_revise_gate_routing(
            on_proceed="p",
            on_iterate="i",
            on_tiebreaker="t",
            on_escalate="e",
        )
        critique_edges = result["critique"]
        assert len(critique_edges) == 1
        assert critique_edges[0].kind == "normal"
        assert critique_edges[0].label == "gate"
        assert critique_edges[0].target == "gate"

    def test_gate_has_four_decision_edges(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import critique_revise_gate_routing

        result = critique_revise_gate_routing(
            on_proceed="finalize",
            on_iterate="revise",
            on_tiebreaker="tiebreaker",
            on_escalate="escalation",
        )
        gate_edges = result["gate"]
        assert len(gate_edges) == 4
        assert all(e.kind == "decision" for e in gate_edges)

    def test_revise_edge_loops_back_to_critique_by_default(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import critique_revise_gate_routing

        result = critique_revise_gate_routing(
            on_proceed="p",
            on_iterate="i",
            on_tiebreaker="t",
            on_escalate="e",
        )
        revise_edges = result["revise"]
        assert len(revise_edges) == 1
        assert revise_edges[0].kind == "normal"
        assert revise_edges[0].label == "critique"
        assert revise_edges[0].target == "critique"

    def test_revise_target_customizable(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import critique_revise_gate_routing

        result = critique_revise_gate_routing(
            on_proceed="p",
            on_iterate="i",
            on_tiebreaker="t",
            on_escalate="e",
            on_revise="gate",
        )
        assert result["revise"][0].target == "gate"

    def test_gate_extra_edges_preserved(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import critique_revise_gate_routing

        extra = (Edge(label="extra", target="somewhere", kind="override"),)
        result = critique_revise_gate_routing(
            on_proceed="p",
            on_iterate="i",
            on_tiebreaker="t",
            on_escalate="e",
            gate_extra_edges=extra,
        )
        assert len(result["gate"]) == 5
        assert result["gate"][4].label == "extra"

    def test_no_kind_gate_in_output(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import critique_revise_gate_routing

        result = critique_revise_gate_routing(
            on_proceed="p",
            on_iterate="i",
            on_tiebreaker="t",
            on_escalate="e",
        )
        for key in ("critique", "gate", "revise"):
            for edge in result[key]:
                assert edge.kind != "gate", (
                    f"Edge in {key!r} has kind='gate' — must use kind='decision'"
                )

    def test_preserves_existing_targets(self) -> None:
        from arnold.pipelines.megaplan.pipelines.planning.routing import critique_revise_gate_routing

        result = critique_revise_gate_routing(
            on_proceed="target_proceed",
            on_iterate="target_iterate",
            on_tiebreaker="target_tiebreaker",
            on_escalate="target_escalate",
        )
        gate_targets = {e.target for e in result["gate"]}
        assert "target_proceed" in gate_targets
        assert "target_iterate" in gate_targets
        assert "target_tiebreaker" in gate_targets
        assert "target_escalate" in gate_targets
