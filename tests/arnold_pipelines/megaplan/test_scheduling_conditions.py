import pytest
from arnold_pipelines.megaplan.orchestration.phase_result import SchedulingCondition, PhaseResult, ExitKind


def test_scheduling_condition_is_lossless_through_phase_result():
    c = SchedulingCondition("c", "memory_cooldown", "p", "ph", "spec", "fam", "log", 1, 2.5, "2026-01-01", evidence={"x": 1})
    r = PhaseResult("ph", "inv", ExitKind.scheduling_condition.value, scheduling_condition=c)
    assert PhaseResult.from_dict(r.to_dict()).scheduling_condition == c


def test_invalid_reason_rejected():
    with pytest.raises(ValueError): SchedulingCondition("c", "failure", "p", "ph", "s", "f", "l", 1, 0, "t")
