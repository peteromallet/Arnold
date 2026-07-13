from arnold_pipelines.megaplan.execute.aggregation import (
    phase_quality_deviations_for_current_attempt,
)


def test_current_attempt_quality_deviations_do_not_replay_stale_batches() -> None:
    # The historical artifact is intentionally represented by not passing it:
    # the reducer owns the current invocation payloads, while execution.json
    # remains the cross-attempt audit trail.
    blockers, deferred = phase_quality_deviations_for_current_attempt(
        [
            {
                "deviations": [
                    "Advisory: e2e test could not run because ComfyUI server is unavailable.",
                    "Expected environment limitation; recorded as command evidence only.",
                ]
            }
        ],
        blocking_reasons=[],
    )

    assert blockers == []
    assert deferred == [
        "Advisory: e2e test could not run because ComfyUI server is unavailable.",
        "Expected environment limitation; recorded as command evidence only.",
    ]


def test_current_real_quality_failure_remains_a_blocker() -> None:
    blockers, deferred = phase_quality_deviations_for_current_attempt(
        [{"deviations": ["pytest failed: tests/test_runtime.py::test_contract"]}],
        blocking_reasons=["1/1 tasks have no executor update"],
    )

    assert blockers == [
        "1/1 tasks have no executor update",
        "pytest failed: tests/test_runtime.py::test_contract",
    ]
    assert deferred == []
