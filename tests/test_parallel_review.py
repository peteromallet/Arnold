from __future__ import annotations

from pathlib import Path

import pytest

from megaplan._core import (
    WorkerUnit,
    WorkerUnitResult,
    atomic_write_json,
    atomic_write_text,
    ensure_runtime_layout,
    scatter_worker_unit,
    scatter_worker_units,
)
from megaplan._core.hermes_fanout import GenericScatterResult
from megaplan.review.parallel import _parse_parallel_review_result, run_parallel_review
from megaplan.review.checks import checks_for_robustness
from megaplan.types import AgentMode, CliError, PlanState
from megaplan.workers import WorkerResult, _build_mock_payload


REPO_ROOT = Path(__file__).resolve().parents[1]


def _state(project_dir: Path, *, iteration: int = 1) -> PlanState:
    return {
        "name": "test-plan",
        "idea": "parallelize review",
        "current_state": "executed",
        "iteration": iteration,
        "created_at": "2026-04-07T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "superrobust",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": iteration,
                "file": f"plan_v{iteration}.md",
                "hash": "sha256:test",
                "timestamp": "2026-04-07T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {
            "significant_counts": [],
            "weighted_scores": [],
            "plan_deltas": [],
            "recurring_critiques": [],
            "total_cost_usd": 0.0,
            "overrides": [],
            "notes": [],
        },
        "last_gate": {},
    }


def _scaffold(tmp_path: Path, *, iteration: int = 1) -> tuple[Path, Path, PlanState]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    ensure_runtime_layout(project_dir)
    state = _state(project_dir, iteration=iteration)

    atomic_write_text(plan_dir / f"plan_v{iteration}.md", "# Plan\nDo it.\n")
    atomic_write_json(
        plan_dir / f"plan_v{iteration}.meta.json",
        {
            "version": iteration,
            "timestamp": "2026-04-07T00:00:00Z",
            "hash": "sha256:test",
            "success_criteria": [{"criterion": "criterion", "priority": "must"}],
            "questions": [],
            "assumptions": [],
        },
    )
    atomic_write_json(plan_dir / "finalize.json", _build_mock_payload("finalize", state, plan_dir))
    atomic_write_json(plan_dir / "gate.json", {"settled_decisions": []})
    atomic_write_json(plan_dir / "faults.json", {"flags": []})
    return plan_dir, project_dir, state


def _finding(detail: str, *, flagged: bool, status: str) -> dict[str, object]:
    return {"detail": detail, "flagged": flagged, "status": status}


def _check_payload(check: object, detail: str, *, flagged: bool = False, status: str = "n/a") -> dict[str, object]:
    return {
        "id": check.id,
        "question": check.question,
        "concerned_task_ids": [],
        "findings": [_finding(detail, flagged=flagged, status=status)],
    }


def _review_worker_unit(
    plan_dir: Path,
    check: object,
    *,
    model: str = "minimax:MiniMax-M2",
    resolved_model: str = "qwen/qwen3-32b",
) -> WorkerUnit:
    check_id = check.id
    output_path = plan_dir / f"review_check_{check_id}.json"
    return WorkerUnit(
        step="review",
        resolved=AgentMode(agent="hermes", mode="persistent", refreshed=False, model=model),
        prompt=f"review prompt for {check_id}",
        output_path=output_path,
        read_only=True,
        extra={
            "check_id": check_id,
            "worker_options": {
                "template_path": str(output_path),
                "session_db_path": str(plan_dir / ".hermes_state" / f"review_{check_id}.db"),
                "max_tokens": 40000,
                "resolved_model": resolved_model,
                "reasoning_config": {"enabled": False},
            },
        },
    )


def test_run_parallel_review_merges_check_results_in_original_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan_dir, project_dir, state = _scaffold(tmp_path)
    checks = checks_for_robustness("superrobust")
    criteria_payload = _build_mock_payload("review", state, plan_dir, review_verdict="approved")
    prompt_calls: list[tuple[str, list[dict[str, object]], list[dict[str, object]]]] = []
    atomic_write_json(
        plan_dir / "faults.json",
        {
            "flags": [
                {
                    "id": "FLAG-ADDRESSED",
                    "concern": "old coverage concern",
                    "category": "completeness",
                    "status": "addressed",
                    "severity": "medium",
                    "evidence": "coverage evidence",
                },
                {
                    "id": "FLAG-OPEN",
                    "concern": "irrelevant open concern",
                    "category": "other",
                    "status": "open",
                    "severity": "low",
                    "evidence": "ignored",
                },
            ]
        },
    )

    def fake_single_check_prompt(state_arg, plan_dir_arg, root_arg, check, output_path, pre_check_flags, prior_flags=None):
        del state_arg, plan_dir_arg, root_arg, output_path
        prompt_calls.append((check.id, pre_check_flags, prior_flags or []))
        return f"focused prompt {check.id}"

    def fake_scatter_worker_units(**kwargs: object) -> GenericScatterResult:
        units = kwargs["units"]
        side_units = kwargs["side_units"]
        assert len(units) == len(checks)
        assert len(side_units) == 1
        assert kwargs["max_concurrent"] is None
        assert kwargs["args"].phase_model == []
        assert all(unit.step == "review" for unit in units)
        assert all(unit.resolved.agent == "hermes" for unit in units)
        assert [unit.extra["check_id"] for unit in units] == [check.id for check in checks]
        assert [unit.output_path.name for unit in units] == [f"review_check_{check.id}.json" for check in checks]
        assert all(unit.extra["worker_options"]["template_path"] == str(unit.output_path) for unit in units)
        assert all(unit.extra["worker_options"]["session_db_path"].endswith(f"state_review_{unit.extra['check_id']}.db") for unit in units)
        assert side_units[0].output_path.name == "review_criteria_verdict.json"
        assert side_units[0].extra["worker_options"]["session_db_path"].endswith("state_review_criteria_verdict.db")

        ordered_results = []
        for index, unit in enumerate(units):
            payload = {
                "checks": [
                    _check_payload(
                        checks[index],
                        f"Checked {checks[index].id} in detail for ordered merge coverage.",
                        flagged=False,
                    )
                ],
                "verified_flag_ids": [f"FLAG-{index}", "FLAG-DISPUTED"],
                "disputed_flag_ids": ["FLAG-DISPUTED"] if index == 0 else [],
            }
            ordered_results.append(
                kwargs["parse_result"](
                    index,
                    WorkerUnitResult(
                        payload=payload,
                        raw_output="{}",
                        duration_ms=1,
                        cost_usd=0.25,
                        rate_limit={"provider": f"check-{index}", "remaining": index},
                    ),
                    unit,
                )
            )
        side_results = [
            kwargs["parse_side_result"](
                0,
                WorkerUnitResult(
                    payload=criteria_payload,
                    raw_output="{}",
                    duration_ms=1,
                    cost_usd=0.5,
                    rate_limit={"provider": "criteria", "remaining": 11},
                ),
                side_units[0],
            )
        ]
        return GenericScatterResult(
            ordered_results=ordered_results,
            total_cost=1.25,
            total_prompt_tokens=21,
            total_completion_tokens=13,
            total_tokens=34,
            side_results=side_results,
        )

    monkeypatch.setattr("megaplan.review.parallel._resolve_model", lambda model: ("qwen/qwen3-32b", {}))
    monkeypatch.setattr("megaplan.review.parallel.single_check_review_prompt", fake_single_check_prompt)
    monkeypatch.setattr("megaplan.review.parallel.scatter_worker_units", fake_scatter_worker_units)

    result = run_parallel_review(
        state,
        plan_dir,
        root=project_dir,
        model="mock-model",
        checks=checks,
        pre_check_flags=[{"id": "PRECHECK-1"}],
    )

    assert [check["id"] for check in result.payload["checks"]] == [check.id for check in checks]
    assert result.payload["criteria_payload"] == criteria_payload
    assert result.payload["verified_flag_ids"] == [f"FLAG-{index}" for index in range(len(checks))]
    assert result.payload["disputed_flag_ids"] == ["FLAG-DISPUTED"]
    assert result.cost_usd == 1.25
    assert result.prompt_tokens == 21
    assert result.completion_tokens == 13
    assert result.total_tokens == 34
    assert result.rate_limit == {
        "values": [
            {"provider": f"check-{index}", "remaining": index}
            for index in range(len(checks))
        ] + [{"provider": "criteria", "remaining": 11}]
    }
    assert prompt_calls[0][1] == [{"id": "PRECHECK-1"}]
    assert prompt_calls[0][2][0]["id"] == "FLAG-ADDRESSED"


def test_review_worker_path_parse_hook_cleans_payload_and_extracts_flags(tmp_path: Path) -> None:
    plan_dir, _project_dir, _state = _scaffold(tmp_path)
    check = checks_for_robustness("standard")[0]
    unit = _review_worker_unit(plan_dir, check)
    worker_result = WorkerResult(
        payload={
            "checks": [
                {
                    "id": check.id,
                    "question": check.question,
                    "guidance": check.guidance,
                    "prior_findings": [{"detail": "legacy"}],
                    "concerned_task_ids": [],
                    "findings": [_finding("worker path clean-up preserved the useful finding.", flagged=False, status="n/a")],
                }
            ],
            "verified_flag_ids": ["FLAG-VERIFIED"],
            "disputed_flag_ids": ["FLAG-DISPUTED"],
        },
        raw_output="{}",
        duration_ms=17,
        cost_usd=0.33,
        prompt_tokens=11,
        completion_tokens=7,
        total_tokens=18,
        rate_limit={"provider": "check", "remaining": 5},
    )

    parsed = _parse_parallel_review_result(0, WorkerUnitResult.from_worker_result(worker_result, unit), unit)

    index, check_payload, verified_ids, disputed_ids, cost_usd, pt, ct, tt, rate_limit = parsed
    assert index == 0
    assert check_payload == {
        "id": check.id,
        "question": check.question,
        "concerned_task_ids": [],
        "findings": [
            {
                "detail": "worker path clean-up preserved the useful finding.",
                "flagged": False,
                "status": "n/a",
            }
        ],
    }
    assert verified_ids == ["FLAG-VERIFIED"]
    assert disputed_ids == ["FLAG-DISPUTED"]
    assert (cost_usd, pt, ct, tt) == (0.33, 11, 7, 18)
    assert rate_limit == {"provider": "check", "remaining": 5}
    assert unit.extra["worker_options"]["template_path"].endswith(f"review_check_{check.id}.json")
    assert unit.extra["worker_options"]["session_db_path"].endswith(f"review_{check.id}.db")


def test_review_worker_path_parse_hook_requires_exactly_one_check(tmp_path: Path) -> None:
    plan_dir, _project_dir, _state = _scaffold(tmp_path)
    check = checks_for_robustness("standard")[0]
    unit = _review_worker_unit(plan_dir, check)
    worker_result = WorkerResult(
        payload={
            "checks": [
                _check_payload(check, "first", flagged=False),
                _check_payload(check, "second", flagged=False),
            ]
        },
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
    )

    with pytest.raises(CliError, match="exactly one check"):
        _parse_parallel_review_result(0, WorkerUnitResult.from_worker_result(worker_result, unit), unit)


def test_run_parallel_review_supports_zero_checks_with_criteria_side_unit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan_dir, project_dir, state = _scaffold(tmp_path)
    criteria_payload = _build_mock_payload("review", state, plan_dir, review_verdict="approved")

    def fake_scatter_worker_units(**kwargs: object) -> GenericScatterResult:
        units = kwargs["units"]
        side_units = kwargs["side_units"]
        assert units == []
        assert len(side_units) == 1
        assert kwargs["max_concurrent"] is None
        assert side_units[0].output_path.name == "review_criteria_verdict.json"
        assert side_units[0].extra["worker_options"]["template_path"] == str(side_units[0].output_path)
        assert side_units[0].extra["worker_options"]["session_db_path"].endswith("state_review_criteria_verdict.db")
        parsed_side = kwargs["parse_side_result"](
            0,
            WorkerUnitResult(
                payload=criteria_payload,
                raw_output="{}",
                duration_ms=23,
                cost_usd=0.4,
                prompt_tokens=13,
                completion_tokens=5,
                total_tokens=18,
            ),
            side_units[0],
        )
        return GenericScatterResult(
            ordered_results=[],
            total_cost=0.4,
            total_prompt_tokens=13,
            total_completion_tokens=5,
            total_tokens=18,
            side_results=[parsed_side],
        )

    monkeypatch.setattr("megaplan.review.parallel._resolve_model", lambda model: ("qwen/qwen3-32b", {}))
    monkeypatch.setattr("megaplan.review.parallel.scatter_worker_units", fake_scatter_worker_units)

    result = run_parallel_review(
        state=state,
        plan_dir=plan_dir,
        root=project_dir,
        model="mock-model",
        checks=(),
        pre_check_flags=[],
    )

    assert result.payload["checks"] == []
    assert result.payload["criteria_payload"] == criteria_payload
    assert result.payload["verified_flag_ids"] == []
    assert result.payload["disputed_flag_ids"] == []
    assert result.cost_usd == 0.4
    assert result.prompt_tokens == 13
    assert result.completion_tokens == 5
    assert result.total_tokens == 18


def test_scatter_worker_unit_forwards_review_worker_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plan_dir, _project_dir, state = _scaffold(tmp_path)
    check = checks_for_robustness("standard")[0]
    unit = _review_worker_unit(plan_dir, check)
    args = type("Args", (), {"agent": None, "hermes": None, "phase_model": [], "ephemeral": True, "fresh": False, "persist": False})()
    worker = WorkerResult(
        payload={"checks": []},
        raw_output="{}",
        duration_ms=9,
        cost_usd=0.12,
        prompt_tokens=3,
        completion_tokens=2,
        total_tokens=5,
    )

    def fake_run_step_with_worker(step: str, state_arg: PlanState, plan_dir_arg: Path, args_arg: object, **kwargs: object):
        assert step == "review"
        assert state_arg == state
        assert plan_dir_arg == plan_dir
        assert args_arg == args
        assert kwargs["read_only"] is True
        assert kwargs["output_path"] == unit.output_path
        assert kwargs["worker_options"] == unit.extra["worker_options"]
        return worker, "hermes", "persistent", False

    monkeypatch.setattr("megaplan.workers.run_step_with_worker", fake_run_step_with_worker)

    index, payload, cost_usd, pt, ct, tt = scatter_worker_unit(
        0,
        unit,
        state=state,
        plan_dir=plan_dir,
        root=tmp_path,
        args=args,
        isolation="thread",
    )

    assert index == 0
    assert isinstance(payload, WorkerUnitResult)
    assert payload.output_path == str(unit.output_path)
    assert payload.extra["worker_options"]["resolved_model"] == "qwen/qwen3-32b"
    assert (cost_usd, pt, ct, tt) == (0.12, 3, 2, 5)
