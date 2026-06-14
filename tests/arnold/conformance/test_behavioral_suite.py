from __future__ import annotations

from arnold.conformance import run_conformance_suite
from arnold.pipeline.hooks import NullExecutorHooks
from arnold.pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult
from arnold.pipelines.evidence_pack import (
    build_continuation_pipeline,
    build_initial_pipeline,
)


class _Step:
    name = "step"
    kind = "compute"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="continue")


def _routing_pipeline() -> Pipeline:
    return Pipeline(
        stages={
            "router": Stage(
                name="router",
                step=_Step(),
                decision_vocabulary=frozenset({"proceed"}),
                override_vocabulary=frozenset({"skip"}),
                edges=(
                    Edge(label="continue", target="done", kind="normal"),
                    Edge(label="proceed", target="done", kind="decision"),
                    Edge(label="override skip", target="done", kind="override"),
                ),
            ),
            "done": Stage(name="done", step=_Step()),
        },
        entry="router",
    )


def test_suite_runs_routing_checks_for_supplied_pipeline() -> None:
    suite = run_conformance_suite(pipelines=[_routing_pipeline()])

    check_ids = {check.check_id for check in suite.checks}

    assert suite.passed is True
    assert "routing-vocabulary-coverage" in check_ids
    assert "routing-vocabulary-edge-consistency" in check_ids
    assert "resolve-edge-decision-match" in check_ids
    assert "resolve-edge-override-match" in check_ids


def test_suite_reports_seeded_routing_violation() -> None:
    pipeline = Pipeline(
        stages={
            "router": Stage(
                name="router",
                step=_Step(),
                decision_vocabulary=frozenset({"proceed"}),
                edges=(Edge(label="wrong", target="done", kind="decision"),),
            ),
            "done": Stage(name="done", step=_Step()),
        },
        entry="router",
    )

    suite = run_conformance_suite(pipelines=[pipeline])

    assert suite.passed is False
    assert "routing-vocabulary-coverage" in {
        check.check_id for check in suite.failures
    }


def test_suite_runs_join_checks_for_supplied_hooks() -> None:
    suite = run_conformance_suite(hooks=[NullExecutorHooks()])

    check_ids = {check.check_id for check in suite.checks}

    assert suite.passed is True
    assert "join-delegation" in check_ids
    assert "join-delegation-child-results" in check_ids
    assert "join-delegation-context-forwarding" in check_ids


def test_evidence_pack_pipelines_pass_opt_in_behavioral_suite() -> None:
    for pipeline in (build_initial_pipeline(), build_continuation_pipeline()):
        suite = run_conformance_suite(pipelines=[pipeline])

        assert suite.passed is True
        assert suite.check_count >= 7
