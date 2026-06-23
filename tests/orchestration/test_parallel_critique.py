from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.hermes_fanout import GenericScatterResult
from arnold_pipelines.megaplan.orchestration import parallel_critique
from arnold_pipelines.megaplan.types import AgentMode, CliError


def test_parallel_critique_persists_raw_output_on_worker_error(
    tmp_path: Path, monkeypatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    def fake_prompt(*_args: Any, **_kwargs: Any) -> str:
        return "critique prompt"

    def fake_scatter_worker_units(*, units, on_unit_error, **_kwargs):
        payload, cost, pt, ct, tt = on_unit_error(
            0,
            CliError(
                "worker_parse_error",
                "model emitted unsupported tool-call markup; critique template unchanged",
                extra={"raw_output": '<read_file path="critique_check_scope.json"/>'},
            ),
        )
        return GenericScatterResult(
            ordered_results=[payload],
            total_cost=cost,
            total_prompt_tokens=pt,
            total_completion_tokens=ct,
            total_tokens=tt,
            side_results=[],
        )

    monkeypatch.setattr(parallel_critique, "single_check_critique_prompt", fake_prompt)
    monkeypatch.setattr(parallel_critique, "scatter_worker_units", fake_scatter_worker_units)

    state = {
        "config": {"mode": "code", "project_dir": str(tmp_path)},
        "iteration": 1,
    }
    check = {
        "id": "scope",
        "question": "Does the plan cover scope?",
        "complexity": 4,
        "_resolved_agent_mode": AgentMode(
            agent="hermes",
            mode="fresh",
            refreshed=False,
            model="deepseek:deepseek-v4-pro",
            resolved_model="deepseek:deepseek-v4-pro",
        ),
    }

    worker = parallel_critique.run_parallel_critique(
        state,
        plan_dir,
        root=tmp_path,
        model="deepseek:deepseek-v4-pro",
        checks=(check,),
    )

    raw_path = plan_dir / "critique_check_scope_raw.txt"
    assert raw_path.read_text(encoding="utf-8") == '<read_file path="critique_check_scope.json"/>'
    assert worker.payload["checks"][0]["id"] == "scope"
    assert worker.payload["checks"][0]["status"] == "unverifiable"

