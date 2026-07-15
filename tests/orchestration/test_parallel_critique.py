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


def test_parallel_critique_flags_only_verifiability_payload_becomes_unverifiable_check(
    tmp_path: Path, monkeypatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    def fake_prompt(*_args: Any, **_kwargs: Any) -> str:
        return "critique prompt"

    def fake_scatter_worker_units(**_kwargs):
        return GenericScatterResult(
            ordered_results=[
                {
                    "checks": [],
                    "flags": [
                        {
                            "id": "cannot-access-local-path",
                            "category": "verifiability",
                            "concern": "shell/file access is blocked in this environment",
                            "evidence": (
                                "Attempts to inspect /workspace/tmp via local commands "
                                "failed with a sandbox namespace error."
                            ),
                        }
                    ],
                    "verified_flag_ids": ["cannot-access-local-path"],
                    "disputed_flag_ids": [],
                }
            ],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(parallel_critique, "single_check_critique_prompt", fake_prompt)
    monkeypatch.setattr(parallel_critique, "scatter_worker_units", fake_scatter_worker_units)

    state = {
        "config": {"mode": "code", "project_dir": str(tmp_path)},
        "iteration": 1,
    }
    check = {
        "id": "correctness",
        "question": "Is the plan technically correct?",
        "complexity": 4,
        "_resolved_agent_mode": AgentMode(
            agent="codex",
            mode="fresh",
            refreshed=False,
            model="gpt-5.4",
            resolved_model="gpt-5.4",
        ),
    }

    worker = parallel_critique.run_parallel_critique(
        state,
        plan_dir,
        root=tmp_path,
        model="gpt-5.4",
        checks=(check,),
    )

    payload = worker.payload["checks"][0]
    assert payload["id"] == "correctness"
    assert payload["status"] == "unverifiable"
    assert payload["unverifiable_cause"] == "sandbox_namespace"
    assert payload["unverifiable_error_kind"] == "sandbox_namespace"


def test_parallel_critique_flags_only_scope_payload_preserves_blocking_findings(
    tmp_path: Path, monkeypatch
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    monkeypatch.setattr(
        parallel_critique,
        "single_check_critique_prompt",
        lambda *_args, **_kwargs: "critique prompt",
    )
    monkeypatch.setattr(
        parallel_critique,
        "scatter_worker_units",
        lambda **_kwargs: GenericScatterResult(
            ordered_results=[
                {
                    "checks": [],
                    "flags": [
                        {
                            "id": "god-task",
                            "category": "scope",
                            "concern": "Step 2 combines independent objectives.",
                            "evidence": "The step spans protocol, migration, and broad tests.",
                        }
                    ],
                    "verified_flag_ids": [],
                    "disputed_flag_ids": [],
                }
            ],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        ),
    )
    state = {"config": {"mode": "code", "project_dir": str(tmp_path)}, "iteration": 1}
    check = {
        "id": "scope",
        "question": "Are steps bounded?",
        "complexity": 5,
        "_resolved_agent_mode": AgentMode(
            agent="codex",
            mode="fresh",
            refreshed=False,
            model="gpt-5.5",
            resolved_model="gpt-5.5",
        ),
    }

    worker = parallel_critique.run_parallel_critique(
        state, plan_dir, root=tmp_path, model="gpt-5.5", checks=(check,)
    )

    payload = worker.payload["checks"][0]
    assert payload["status"] == "complete"
    assert payload["findings"] == [
        {"detail": "The step spans protocol, migration, and broad tests.", "flagged": True}
    ]
    assert worker.payload["flags"] == [
        {
            "id": "god-task",
            "category": "completeness",
            "producer_category": "scope",
            "concern": "Step 2 combines independent objectives.",
            "evidence": "The step spans protocol, migration, and broad tests.",
            "severity_hint": "uncertain",
            "source_check_id": "scope",
        }
    ]
