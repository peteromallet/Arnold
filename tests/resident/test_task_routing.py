from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident import subagent as subagent_module
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.subagent import (
    launch_subagent_task,
    route_delegated_task,
)


@pytest.mark.parametrize(
    ("task_kind", "difficulty", "model", "effort", "route_class"),
    [
        ("lookup", 1, "gpt-5.6-luna", "low", "bounded_mechanical"),
        ("mechanical", 3, "gpt-5.6-luna", "low", "bounded_mechanical"),
        ("lookup", 4, "gpt-5.6-terra", "medium", "routine"),
        ("routine", 4, "gpt-5.6-terra", "medium", "routine"),
        ("debugging", 6, "gpt-5.6-terra", "medium", "routine"),
        ("coding", 7, "gpt-5.6-sol", "high", "ambiguous_or_high_risk"),
        ("migration", 2, "gpt-5.6-sol", "high", "ambiguous_or_high_risk"),
    ],
)
def test_resident_task_kind_and_difficulty_routing(
    task_kind: str,
    difficulty: int,
    model: str,
    effort: str,
    route_class: str,
) -> None:
    route = route_delegated_task(task_kind=task_kind, difficulty=difficulty)  # type: ignore[arg-type]

    assert (route.model, route.reasoning_effort, route.route_class) == (
        model,
        effort,
        route_class,
    )


@pytest.mark.parametrize("difficulty", [0, 11, True])
def test_resident_difficulty_must_be_d1_through_d10(difficulty: object) -> None:
    with pytest.raises(ValueError, match="difficulty"):
        route_delegated_task(difficulty=difficulty)  # type: ignore[arg-type]


def test_routine_managed_launch_defaults_to_terra_medium(tmp_path: Path, monkeypatch) -> None:
    class _Process:
        pid = 4321

    monkeypatch.setattr(
        subagent_module.subprocess,
        "Popen",
        lambda *args, **kwargs: _Process(),
    )
    result = asyncio.run(
        launch_subagent_task(
            ResidentConfig(model_name="gpt-5.6-sol"),
            task="routine change",
            project_dir=str(tmp_path),
        )
    )

    manifest = json.loads(Path(result.manifest_path or "").read_text(encoding="utf-8"))
    assert manifest["model"] == "gpt-5.6-terra"
    assert manifest["reasoning_effort"] == "medium"
    assert manifest["task_kind"] == "routine"
    assert manifest["difficulty"] == 4
    assert manifest["route_class"] == "routine"


def test_explicit_model_and_effort_override_preserves_escape_hatch(
    tmp_path: Path, monkeypatch
) -> None:
    class _Process:
        pid = 4321

    monkeypatch.setattr(
        subagent_module.subprocess,
        "Popen",
        lambda *args, **kwargs: _Process(),
    )
    result = asyncio.run(
        launch_subagent_task(
            ResidentConfig(),
            task="specialized task",
            project_dir=str(tmp_path),
            task_kind="coding",
            difficulty=2,
            model="gpt-custom",
            reasoning_effort="xhigh",
        )
    )

    manifest = json.loads(Path(result.manifest_path or "").read_text(encoding="utf-8"))
    assert manifest["model"] == "gpt-custom"
    assert manifest["reasoning_effort"] == "xhigh"
    assert manifest["route_class"] == "explicit_override"
