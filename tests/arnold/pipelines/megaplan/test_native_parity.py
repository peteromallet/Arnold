"""M4 Megaplan native parity fixture catalog — scenario inventory and descriptor tests.

Pins the eight-scenario parity matrix defined in the M4 plan:
happy finalize, revise loop, tiebreaker, escalate, override force-proceed,
override abort, suspension/resume, and execute/review artifact path.

These tests validate the **fixture descriptors only** — stable branch labels,
golden output locations, and scenario inventory completeness. The full parity
runner is built in a later step (T4+). No runtime execution logic lives here.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from tests.arnold.pipelines.megaplan.data.native_parity.scenarios import (
    PARITY_SCENARIOS,
    PARITY_SCENARIO_BY_ID,
    ParityScenario,
    SCENARIO_ESCALATE,
    SCENARIO_EXECUTE_REVIEW_ARTIFACT,
    SCENARIO_HAPPY_FINALIZE,
    SCENARIO_OVERRIDE_ABORT,
    SCENARIO_OVERRIDE_FORCE_PROCEED,
    SCENARIO_REVISE_LOOP,
    SCENARIO_SUSPENSION_RESUME,
    SCENARIO_TIEBREAKER,
)


# ═══════════════════════════════════════════════════════════════════════
# Scenario inventory completeness
# ═══════════════════════════════════════════════════════════════════════


class TestScenarioInventory:
    """The parity catalog covers exactly the eight required scenarios."""

    REQUIRED_IDS: tuple[str, ...] = (
        "happy_finalize",
        "revise_loop",
        "tiebreaker",
        "escalate",
        "override_force_proceed",
        "override_abort",
        "suspension_resume",
        "execute_review_artifact",
    )

    def test_exactly_eight_scenarios(self) -> None:
        """The PARITY_SCENARIOS tuple contains exactly 8 entries."""
        assert len(PARITY_SCENARIOS) == 8, (
            f"Expected 8 parity scenarios, got {len(PARITY_SCENARIOS)}"
        )

    def test_all_required_ids_present(self) -> None:
        """Every required scenario_id appears in the catalog."""
        actual_ids = {s.scenario_id for s in PARITY_SCENARIOS}
        missing = set(self.REQUIRED_IDS) - actual_ids
        extra = actual_ids - set(self.REQUIRED_IDS)
        assert not missing, f"Missing scenario ids: {missing}"
        assert not extra, f"Unexpected scenario ids: {extra}"

    def test_no_duplicate_scenario_ids(self) -> None:
        """No two scenarios share the same scenario_id."""
        ids = [s.scenario_id for s in PARITY_SCENARIOS]
        assert len(ids) == len(set(ids)), f"Duplicate scenario ids: {ids}"

    def test_lookup_by_id_covers_all(self) -> None:
        """PARITY_SCENARIO_BY_ID contains every scenario."""
        for scenario in PARITY_SCENARIOS:
            assert PARITY_SCENARIO_BY_ID[scenario.scenario_id] is scenario

    def test_scenario_ids_are_stable_strings(self) -> None:
        """Scenario ids are non-empty, kebab-case stable identifiers."""
        for scenario in PARITY_SCENARIOS:
            assert isinstance(scenario.scenario_id, str)
            assert scenario.scenario_id, "scenario_id must not be empty"
            assert " " not in scenario.scenario_id, (
                f"scenario_id '{scenario.scenario_id}' contains whitespace"
            )


# ═══════════════════════════════════════════════════════════════════════
# Branch label assertions — per-scenario expected gate decisions
# ═══════════════════════════════════════════════════════════════════════


class TestBranchLabels:
    """Each scenario declares stable expected branch labels."""

    def test_happy_finalize_branch_labels(self) -> None:
        assert SCENARIO_HAPPY_FINALIZE.expected_branch_labels == ("proceed",)

    def test_revise_loop_branch_labels(self) -> None:
        assert SCENARIO_REVISE_LOOP.expected_branch_labels == ("iterate", "proceed")

    def test_tiebreaker_branch_labels(self) -> None:
        assert SCENARIO_TIEBREAKER.expected_branch_labels == ("tiebreaker", "proceed")

    def test_escalate_branch_labels(self) -> None:
        assert SCENARIO_ESCALATE.expected_branch_labels == ("escalate",)

    def test_override_force_proceed_branch_labels(self) -> None:
        assert SCENARIO_OVERRIDE_FORCE_PROCEED.expected_branch_labels == (
            "override force-proceed",
        )

    def test_override_abort_branch_labels(self) -> None:
        assert SCENARIO_OVERRIDE_ABORT.expected_branch_labels == ("override abort",)

    def test_suspension_resume_branch_labels(self) -> None:
        assert SCENARIO_SUSPENSION_RESUME.expected_branch_labels == ("proceed",)

    def test_execute_review_artifact_branch_labels(self) -> None:
        assert SCENARIO_EXECUTE_REVIEW_ARTIFACT.expected_branch_labels == ("proceed",)

    def test_all_branch_labels_are_valid_gate_decisions(self) -> None:
        """Every declared branch label is a known Megaplan gate decision."""
        from arnold.pipelines.megaplan.routing import PLANNING_DECISIONS

        valid_decisions = set(PLANNING_DECISIONS)
        # Override labels are not planning decisions — they are override edges
        valid_overrides = {"override force-proceed", "override abort"}

        for scenario in PARITY_SCENARIOS:
            for label in scenario.expected_branch_labels:
                assert label in valid_decisions or label in valid_overrides, (
                    f"Scenario '{scenario.scenario_id}' declares unknown "
                    f"branch label '{label}'. Known decisions: {valid_decisions}, "
                    f"known overrides: {valid_overrides}"
                )


# ═══════════════════════════════════════════════════════════════════════
# Stage sequence assertions — per-scenario expected stage order
# ═══════════════════════════════════════════════════════════════════════


class TestStageSequences:
    """Each scenario declares a stable expected stage sequence."""

    def test_happy_finalize_stage_sequence(self) -> None:
        assert SCENARIO_HAPPY_FINALIZE.expected_stage_sequence == (
            "prep", "plan", "critique", "gate",
            "finalize", "execute", "review",
        )

    def test_revise_loop_stage_sequence(self) -> None:
        assert SCENARIO_REVISE_LOOP.expected_stage_sequence == (
            "prep", "plan", "critique", "gate",
            "revise", "critique", "gate",
            "finalize", "execute", "review",
        )

    def test_tiebreaker_stage_sequence(self) -> None:
        assert SCENARIO_TIEBREAKER.expected_stage_sequence == (
            "prep", "plan", "critique", "gate",
            "tiebreaker", "critique", "gate",
            "finalize", "execute", "review",
        )

    def test_escalate_stage_sequence(self) -> None:
        assert SCENARIO_ESCALATE.expected_stage_sequence == (
            "prep", "plan", "critique", "gate",
            "finalize", "execute", "review",
        )

    def test_override_force_proceed_stage_sequence(self) -> None:
        assert SCENARIO_OVERRIDE_FORCE_PROCEED.expected_stage_sequence == (
            "prep", "plan", "critique", "gate",
            "finalize", "execute", "review",
        )

    def test_override_abort_stage_sequence(self) -> None:
        assert SCENARIO_OVERRIDE_ABORT.expected_stage_sequence == (
            "prep", "plan", "critique", "gate",
        )

    def test_suspension_resume_stage_sequence(self) -> None:
        assert SCENARIO_SUSPENSION_RESUME.expected_stage_sequence == (
            "prep", "plan", "critique", "gate",
            "finalize",
            "execute", "review",
        )

    def test_execute_review_artifact_stage_sequence(self) -> None:
        assert SCENARIO_EXECUTE_REVIEW_ARTIFACT.expected_stage_sequence == (
            "prep", "plan", "critique", "gate",
            "finalize", "execute", "review",
        )

    def test_all_stage_names_are_valid_megaplan_stages(self) -> None:
        """Every declared stage name is a known Megaplan pipeline stage."""
        valid_stages = {
            "prep", "plan", "critique", "gate", "revise",
            "finalize", "execute", "review", "tiebreaker",
        }
        for scenario in PARITY_SCENARIOS:
            for stage in scenario.expected_stage_sequence:
                assert stage in valid_stages, (
                    f"Scenario '{scenario.scenario_id}' declares unknown "
                    f"stage '{stage}'. Known stages: {valid_stages}"
                )

    def test_all_sequences_start_with_prep(self) -> None:
        """Every stage sequence begins with 'prep'."""
        for scenario in PARITY_SCENARIOS:
            assert scenario.expected_stage_sequence[0] == "prep", (
                f"Scenario '{scenario.scenario_id}' does not start with 'prep': "
                f"{scenario.expected_stage_sequence}"
            )

    def test_all_sequences_end_with_review_or_gate(self) -> None:
        """Every stage sequence ends with 'review' (normal completion) or
        'gate' (early termination like override abort)."""
        for scenario in PARITY_SCENARIOS:
            last = scenario.expected_stage_sequence[-1]
            assert last in ("review", "gate"), (
                f"Scenario '{scenario.scenario_id}' ends with '{last}', "
                f"expected 'review' or 'gate'"
            )


# ═══════════════════════════════════════════════════════════════════════
# Golden output location assertions
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenOutputLocations:
    """Each scenario declares stable golden output paths."""

    def test_golden_paths_are_under_data_directory(self) -> None:
        """Golden trace paths live under data/native_parity/."""
        data_dir = Path(__file__).resolve().parent / "data" / "native_parity"
        for scenario in PARITY_SCENARIOS:
            graph = scenario.golden_graph_trace_path
            native = scenario.golden_native_trace_path
            cursor = scenario.golden_cursor_path
            assert data_dir in graph.parents, (
                f"graph trace path '{graph}' is not under {data_dir}"
            )
            assert data_dir in native.parents, (
                f"native trace path '{native}' is not under {data_dir}"
            )
            assert data_dir in cursor.parents, (
                f"cursor path '{cursor}' is not under {data_dir}"
            )

    def test_golden_paths_use_scenario_id_as_stem(self) -> None:
        """Golden filenames embed the scenario id for traceability."""
        for scenario in PARITY_SCENARIOS:
            sid = scenario.scenario_id
            assert scenario.golden_graph_trace_path.stem == f"{sid}_golden_graph_trace"
            assert scenario.golden_native_trace_path.stem == f"{sid}_golden_native_trace"
            assert scenario.golden_cursor_path.stem == f"{sid}_golden_composite_cursor"

    def test_golden_files_are_json(self) -> None:
        """All golden files use .json suffix."""
        for scenario in PARITY_SCENARIOS:
            assert scenario.golden_graph_trace_path.suffix == ".json"
            assert scenario.golden_native_trace_path.suffix == ".json"
            assert scenario.golden_cursor_path.suffix == ".json"

    def test_golden_graph_traces_exist_after_t4(self) -> None:
        """After T4, every scenario's golden graph trace file must exist.

        Native traces and composite cursors are delivered by later tasks
        (T13+) and are not required yet.
        """
        missing_graph: list[str] = []
        premature_native: list[str] = []
        premature_cursor: list[str] = []

        for scenario in PARITY_SCENARIOS:
            if not scenario.golden_graph_trace_path.exists():
                missing_graph.append(str(scenario.golden_graph_trace_path))
            if scenario.golden_native_trace_path.exists():
                premature_native.append(str(scenario.golden_native_trace_path))
            if scenario.golden_cursor_path.exists():
                premature_cursor.append(str(scenario.golden_cursor_path))

        assert not missing_graph, (
            "Golden graph trace files missing after T4 — "
            f"missing: {missing_graph}"
        )
        assert not premature_native, (
            "Native golden trace files should not exist yet (T13+) — "
            f"unexpected: {premature_native}"
        )
        assert not premature_cursor, (
            "Composite cursor files should not exist yet (T13+) — "
            f"unexpected: {premature_cursor}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Scenario immutability
# ═══════════════════════════════════════════════════════════════════════


class TestScenarioImmutability:
    """ParityScenario is frozen — descriptors cannot be mutated."""

    def test_scenarios_are_frozen_dataclasses(self) -> None:
        """Each descriptor is a frozen dataclass instance."""
        for scenario in PARITY_SCENARIOS:
            assert isinstance(scenario, ParityScenario)

            # Attempting to set an attribute should raise FrozenInstanceError
            try:
                scenario.scenario_id = "mutated"  # type: ignore[misc]
                raise AssertionError(
                    f"Scenario '{scenario.scenario_id}' is not frozen"
                )
            except dataclasses.FrozenInstanceError:
                pass  # Expected — frozen


# ═══════════════════════════════════════════════════════════════════════
# No premature runner logic
# ═══════════════════════════════════════════════════════════════════════


class TestNoPrematureRunnerLogic:
    """The fixture catalog does not contain runner/execution logic.

    This module and the scenarios module must remain pure descriptors.
    No compile_pipeline, run_native_pipeline, project_graph, or
    build_pipeline calls should appear.
    """

    def test_scenarios_module_has_no_runner_imports(self) -> None:
        """The scenarios module imports no runtime/compiler symbols."""
        import ast
        from tests.arnold.pipelines.megaplan.data.native_parity import scenarios

        source = Path(scenarios.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden_imports = {
            "compile_pipeline",
            "run_native_pipeline",
            "project_graph",
            "build_pipeline",
            "NativeRuntime",
            "GraphExecutor",
        }

        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                for alias in node.names:
                    if alias.name in forbidden_imports:
                        violations.append(
                            f"Line {node.lineno}: imports {alias.name} "
                            f"from {node.module}"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(f in alias.name for f in forbidden_imports):
                        violations.append(
                            f"Line {node.lineno}: imports {alias.name}"
                        )

        assert not violations, (
            "Scenarios module contains premature runner imports:\n"
            + "\n".join(violations)
        )

    def test_test_module_has_no_runner_calls(self) -> None:
        """This test module does not invoke compile/run/build/execute."""
        import ast

        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden_calls = {
            "compile_pipeline",
            "run_native_pipeline",
            "project_graph",
            "build_pipeline",
        }

        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in forbidden_calls:
                        violations.append(
                            f"Line {node.lineno}: calls {node.func.id}()"
                        )
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in forbidden_calls:
                        violations.append(
                            f"Line {node.lineno}: calls .{node.func.attr}()"
                        )

        assert not violations, (
            "Test module contains premature runner calls:\n"
            + "\n".join(violations)
        )
