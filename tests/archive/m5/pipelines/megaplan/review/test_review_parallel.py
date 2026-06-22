from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan._core import atomic_write_json, atomic_write_text, ensure_runtime_layout
from arnold.pipelines.megaplan._core.hermes_fanout import GenericScatterResult
from arnold.pipelines.megaplan._core.worker_fanout import WorkerUnitResult
from arnold.pipelines.megaplan.prompts.review import _filtered_prior_flags
from arnold.pipelines.megaplan.review.checks import get_check_by_id
from arnold.pipelines.megaplan.review.parallel import run_parallel_review
from arnold.pipelines.megaplan.types import PlanState


def _state(project_dir: Path) -> PlanState:
    return {
        "name": "plan",
        "idea": "fix the issue",
        "current_state": "executed",
        "iteration": 1,
        "created_at": "2026-05-21T00:00:00Z",
        "config": {"project_dir": str(project_dir), "robustness": "full"},
        "sessions": {},
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "history": [],
        "meta": {},
    }


def _scaffold(tmp_path: Path) -> tuple[Path, Path, PlanState]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    ensure_runtime_layout(project_dir)
    atomic_write_text(plan_dir / "plan_v1.md", "# Plan\n")
    atomic_write_json(plan_dir / "plan_v1.meta.json", {"success_criteria": []})
    atomic_write_json(plan_dir / "finalize.json", {"tasks": [], "sense_checks": []})
    atomic_write_json(plan_dir / "gate.json", {"settled_decisions": []})
    return plan_dir, project_dir, _state(project_dir)


def test_parallel_check_agent_receives_filtered_flags() -> None:
    flags = [
        {"id": "FLAG-COMP", "category": "completeness", "status": "open", "concern": "missing case"},
        {"id": "FLAG-CORR-PATH", "category": "correctness", "status": "open", "concern": "bad path in pkg/module.py"},
        {"id": "FLAG-CORR-CALL", "category": "correctness", "status": "open", "concern": "caller still broken"},
        {"id": "FLAG-MAINT", "category": "maintainability", "status": "open", "concern": "too broad"},
        {"id": "FLAG-ADDR", "category": "security", "status": "addressed", "concern": "resolved concern"},
    ]

    assert [flag["id"] for flag in _filtered_prior_flags(get_check_by_id("coverage"), flags)] == [
        "FLAG-COMP",
        "FLAG-ADDR",
    ]
    assert [flag["id"] for flag in _filtered_prior_flags(get_check_by_id("placement"), flags)] == [
        "FLAG-CORR-PATH",
        "FLAG-ADDR",
    ]
    assert [flag["id"] for flag in _filtered_prior_flags(get_check_by_id("adjacent_calls"), flags)] == [
        "FLAG-CORR-CALL",
        "FLAG-ADDR",
    ]
    assert [flag["id"] for flag in _filtered_prior_flags(get_check_by_id("simplicity"), flags)] == [
        "FLAG-MAINT",
        "FLAG-ADDR",
    ]


def test_run_parallel_review_passes_prior_flags_to_prompt(monkeypatch, tmp_path: Path) -> None:
    plan_dir, project_dir, state = _scaffold(tmp_path)
    check = get_check_by_id("coverage")
    assert check is not None
    captured: dict[str, object] = {}
    atomic_write_json(
        plan_dir / "faults.json",
        {"flags": [{"id": "FLAG-1", "category": "completeness", "status": "open", "concern": "missing case"}]},
    )

    def fake_prompt(state, plan_dir, root, check, output_path, pre_check_flags, prior_flags):
        captured["prior_flags"] = prior_flags
        return "prompt"

    monkeypatch.setattr("arnold.pipelines.megaplan.review.parallel.single_check_review_prompt", fake_prompt)
    monkeypatch.setattr("arnold.pipelines.megaplan.review.parallel._resolve_model", lambda model: ("mock", {}))

    def fake_scatter_worker_units(**kwargs):
        unit = kwargs["units"][0]
        side_unit = kwargs["side_units"][0]
        parsed = kwargs["parse_result"](
            0,
            WorkerUnitResult(
                payload={
                    "checks": [
                        {
                            "id": "coverage",
                            "question": check.question,
                            "findings": [{"detail": "x", "flagged": False, "status": "n/a"}],
                        }
                    ],
                    "verified_flag_ids": [],
                    "disputed_flag_ids": [],
                },
                raw_output="{}",
                duration_ms=1,
                cost_usd=0.0,
            ),
            unit,
        )
        side = kwargs["parse_side_result"](
            0,
            WorkerUnitResult(payload={"review_verdict": "approved"}, raw_output="{}", duration_ms=1, cost_usd=0.0),
            side_unit,
        )
        return GenericScatterResult([parsed], 0.0, 0, 0, 0, [side])

    monkeypatch.setattr("arnold.pipelines.megaplan.review.parallel.scatter_worker_units", fake_scatter_worker_units)

    run_parallel_review(
        state,
        plan_dir,
        root=project_dir,
        model="mock",
        checks=(check,),
        pre_check_flags=[],
    )

    assert captured["prior_flags"] == [{"id": "FLAG-1", "concern": "missing case", "category": "completeness", "status": "open", "severity": "uncertain", "evidence": ""}]
