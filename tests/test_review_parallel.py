from __future__ import annotations

from pathlib import Path

from megaplan._core import atomic_write_json, atomic_write_text
from megaplan.prompts.review import _filtered_prior_flags
from megaplan.review.checks import get_check_by_id
from megaplan.review.parallel import _run_check
from megaplan.types import PlanState


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


def test_run_check_passes_prior_flags_to_prompt(monkeypatch, tmp_path: Path) -> None:
    plan_dir, project_dir, state = _scaffold(tmp_path)
    check = get_check_by_id("coverage")
    assert check is not None
    captured: dict[str, object] = {}

    def fake_prompt(state, plan_dir, root, check, output_path, pre_check_flags, prior_flags):
        captured["prior_flags"] = prior_flags
        return "prompt"

    monkeypatch.setattr("megaplan.review.parallel.single_check_review_prompt", fake_prompt)

    def fake_import_runtime():
        class FakeAgent:
            def __init__(self, **kwargs):
                self._print_fn = None

            def run_conversation(self, *, user_message):
                return {
                    "final_response": "{}",
                    "estimated_cost_usd": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }

        class FakeSessionDB:
            pass

        return FakeAgent, FakeSessionDB

    monkeypatch.setattr("megaplan.workers.hermes._import_hermes_runtime", fake_import_runtime)
    monkeypatch.setattr("megaplan.review.parallel._resolve_model", lambda model: ("mock", {}))
    monkeypatch.setattr("megaplan.review.parallel._toolsets_for_phase", lambda phase: [])
    monkeypatch.setattr(
        "megaplan.review.parallel.parse_agent_output",
        lambda *args, **kwargs: (
            {
                "checks": [{"id": "coverage", "question": check.question, "findings": [{"detail": "x", "flagged": False, "status": "n/a"}]}],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            "{}",
        ),
    )

    _run_check(
        0,
        check,
        state=state,
        plan_dir=plan_dir,
        root=tmp_path,
        model="mock",
        schema={},
        project_dir=project_dir,
        pre_check_flags=[],
        prior_flags=[{"id": "FLAG-1"}],
    )

    assert captured["prior_flags"] == [{"id": "FLAG-1"}]

