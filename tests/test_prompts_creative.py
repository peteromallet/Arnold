from __future__ import annotations

from pathlib import Path

from megaplan._core import atomic_write_json, atomic_write_text
from megaplan.audits.robustness import joke_checks_for_robustness
from megaplan.forms import get_form
from megaplan.forms.provocations import select_active_checks
from megaplan.prompts import create_claude_prompt
from megaplan.pipelines.creative.prompts.critique_creative import (
    _STANCE_AUTHENTICITY_SUBPROVOCATION,
    _critique_creative_prompt,
)
from megaplan.prompts.execute import _execute_prompt
from megaplan.pipelines.creative.prompts.execute_creative import _execute_creative_prompt


def _state(project_dir: Path, *, mode: str = "creative", form: str = "joke", iteration: int = 1) -> dict:
    config = {
        "project_dir": str(project_dir),
        "auto_approve": False,
        "robustness": "standard",
        "mode": mode,
        "output_path": "out.md",
        "primary_criterion": "sharpest image",
    }
    if form:
        config["form"] = form
    return {
        "name": "creative-prompt",
        "idea": "make a thing",
        "current_state": "planned",
        "iteration": iteration,
        "created_at": "2026-04-01T00:00:00Z",
        "config": config,
        "sessions": {},
        "plan_versions": [{"version": iteration, "file": f"plan_v{iteration}.md", "hash": "sha256:test"}],
        "history": [],
        "meta": {"notes": [], "overrides": [], "total_cost_usd": 0.0},
        "last_gate": {},
    }


def _scaffold(tmp_path: Path, *, mode: str = "creative", form: str = "joke", iteration: int = 1) -> tuple[Path, dict]:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    state = _state(project_dir, mode=mode, form=form, iteration=iteration)
    atomic_write_text(plan_dir / f"plan_v{iteration}.md", "# Creative Canvas\n## opening_image\n...\n## turn\n...\n## close\n...\n")
    atomic_write_json(
        plan_dir / f"plan_v{iteration}.meta.json",
        {"success_criteria": [], "assumptions": [], "questions": [], "structure_warnings": []},
    )
    atomic_write_json(plan_dir / "faults.json", {"flags": []})
    atomic_write_json(plan_dir / "gate.json", {"recommendation": "PROCEED", "passed": True})
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "T1",
                    "description": "Write the artifact.",
                    "depends_on": [],
                    "status": "pending",
                    "executor_notes": "",
                    "sections_written": [],
                }
            ],
            "sense_checks": [],
        },
    )
    return plan_dir, state


def test_critique_creative_prompt_mentions_one_cut_force_and_spark(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path, form="joke")
    prompt = _critique_creative_prompt(state, plan_dir, form=get_form("joke"))
    checks = select_active_checks(state, "standard", plan_dir=plan_dir)

    assert [check["provocation"]["vector"] for check in checks] == ["cut", "force", "spark"]
    for check in checks:
        assert prompt.count(f"{check['id']} (") == 1


def test_critique_creative_prompt_uses_poem_beats(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path, form="poem")
    prompt = _critique_creative_prompt(state, plan_dir, form=get_form("poem"))

    assert "opening_image" in prompt
    assert "turn" in prompt
    assert "close" in prompt
    assert "inciting" not in prompt
    assert "button" not in prompt


def test_execute_creative_prompt_includes_stance_and_stop_affordance(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path, form="poem")
    prompt = _execute_creative_prompt(state, plan_dir)

    assert "stance" in prompt
    assert "stop_signal" in prompt
    assert "Stop affordance" in prompt
    assert "hedging verbs" in prompt


def test_code_execute_prompt_excludes_stop_affordance(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path, mode="code", form="")
    prompt = _execute_prompt(state, plan_dir, root=tmp_path)

    assert "stop_signal" not in prompt
    assert "Stop affordance" not in prompt


def test_iteration_two_critique_excludes_prior_provocation_ids(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path, form="joke", iteration=2)
    prior_ids = ["joke-cut-darling", "joke-force-button-first", "absurdist"]
    atomic_write_json(
        plan_dir / "directors_notes.json",
        {
            "form": "joke",
            "primary_criterion": "sharpest image",
            "passes": [
                {
                    "iteration": 1,
                    "provocateur_voice": None,
                    "provocations_fired": [
                        {"id": prior_ids[0], "vector": "cut", "subtype": "kill_darling"},
                        {"id": prior_ids[1], "vector": "force", "subtype": "reorder"},
                        {"id": prior_ids[2], "vector": "spark", "subtype": "borrowed_lens"},
                    ],
                    "stances": [],
                    "stop_requested": False,
                    "stop_defense": "",
                }
            ],
        },
    )
    prompt = _critique_creative_prompt(state, plan_dir, form=get_form("joke"))

    for prior_id in prior_ids:
        assert prior_id not in prompt


def test_joke_and_creative_form_joke_critique_prompts_match(tmp_path: Path) -> None:
    plan_dir, joke_state = _scaffold(tmp_path, mode="joke", form="", iteration=1)
    creative_state = dict(joke_state)
    creative_state["config"] = dict(joke_state["config"], mode="creative", form="joke")

    assert create_claude_prompt("critique", joke_state, plan_dir, root=tmp_path) == create_claude_prompt(
        "critique",
        creative_state,
        plan_dir,
        root=tmp_path,
    )


def test_select_active_checks_matches_joke_compatibility_shim() -> None:
    state = {"config": {"mode": "joke", "robustness": "standard"}, "iteration": 1}
    assert select_active_checks(state, "standard") == joke_checks_for_robustness("standard")


def test_prior_stance_violations_add_authenticity_subprovocation(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path, form="poem")
    atomic_write_json(
        plan_dir / "directors_notes.json",
        {
            "form": "poem",
            "primary_criterion": "sharpest image",
            "passes": [
                {
                    "iteration": 1,
                    "provocateur_voice": None,
                    "provocations_fired": [],
                    "stances": [{"task_id": "T1", "stance_violations": ["stance must use first person"]}],
                    "stop_requested": False,
                    "stop_defense": "",
                }
            ],
        },
    )

    prompt = _critique_creative_prompt(state, plan_dir)

    assert _STANCE_AUTHENTICITY_SUBPROVOCATION in prompt
