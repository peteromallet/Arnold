from __future__ import annotations

from pathlib import Path

from arnold.pipeline.types import StepContext
from arnold.pipelines.megaplan._pipeline.artifact_adapter import artifact_root_as_plan_dir


def test_artifact_root_as_plan_dir_returns_artifact_root() -> None:
    ctx = StepContext(artifact_root="/tmp/my_plan", state={})

    result = artifact_root_as_plan_dir(ctx)

    assert result == "/tmp/my_plan"


def test_artifact_root_as_plan_dir_is_string() -> None:
    ctx = StepContext(artifact_root="/tmp/foo", state={})

    result = artifact_root_as_plan_dir(ctx)

    assert isinstance(result, str)


def test_bridge_adapter_provides_plan_dir_value() -> None:
    """artifact_root_as_plan_dir gives a value usable as plan_dir in bridge code."""
    ctx = StepContext(artifact_root="/tmp/bridge_test", state={})
    plan_dir_str = artifact_root_as_plan_dir(ctx)
    # In real bridge code this would be:
    #   mega_ctx = MegaplanStepContext(plan_dir=Path(plan_dir_str), ...)
    # Here we just verify the value is correct.
    assert plan_dir_str == "/tmp/bridge_test"
    assert Path(plan_dir_str).as_posix() == "/tmp/bridge_test"
