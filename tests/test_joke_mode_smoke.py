"""Joke-mode smoke tests — LEGACY ``--auto-start`` path coverage.

T14 (0.23) explicit three-way split for joke:

* LEGACY ``megaplan init --mode joke --auto-start`` — this file plus
  ``tests/test_handle_init_joke_mode.py``. Retained per USER DECISION 2:
  ``state['config']['mode'] = 'joke'`` is preserved (NOT rewritten to
  ``'creative'``) so the legacy planning + mode-overlay path keeps
  reading the same shape it always has.
* NEW ``megaplan run creative <brief> --form joke`` — covered by
  ``tests/pipelines/test_creative_pipeline.py`` (form dispatch,
  prompt-key routing, primary_criterion threading).
* DEPRECATION redirect (init-time warning + state seeding) — covered
  by ``tests/test_mode_deprecation.py``.

The three files are deliberately kept separate so future maintainers
do not collapse them into a single suite and lose either the legacy
or new-pipeline coverage.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from arnold.pipelines.megaplan._core import atomic_write_json, atomic_write_text
from arnold.pipelines.megaplan.audits.robustness import joke_checks_for_robustness
from arnold.pipelines.megaplan.prompts import (
    _CLAUDE_PROMPT_BUILDERS,
    _plan_prompt,
    _resolve_builder,
)
from arnold.pipelines.megaplan.prompts.critique import write_single_check_template
from arnold.pipelines.megaplan.pipelines.creative.prompts.critique_joke import (
    _critique_joke_prompt,
    single_check_critique_joke_prompt,
)
from arnold.pipelines.megaplan.pipelines.creative.prompts.execute_joke import _execute_joke_prompt
from arnold.pipelines.megaplan.pipelines.creative.prompts.prep_joke import _prep_joke_prompt
from arnold.pipelines.megaplan.prompts.review_joke import _review_joke_prompt
from arnold.pipelines.megaplan.pipelines.creative.prompts.revise_joke import _revise_joke_prompt
from arnold.pipelines.megaplan.types import PlanState


def _joke_state(project_dir: Path) -> PlanState:
    return {
        "name": "joke-smoke",
        "idea": "Two strangers try to return a broken umbrella in the weirdest coherent way possible.",
        "current_state": "critiqued",
        "iteration": 1,
        "created_at": "2026-04-01T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
            "mode": "joke",
            "output_path": "scenes/test.md",
            "primary_criterion": "weirdest coherent",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": 1,
                "file": "plan_v1.md",
                "hash": "sha256:test",
                "timestamp": "2026-04-01T00:00:00Z",
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
        "last_gate": {"recommendation": "ITERATE"},
    }


def _scaffold_joke_plan(tmp_path: Path) -> tuple[Path, PlanState]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    (project_dir / "scenes").mkdir()
    state = _joke_state(project_dir)

    atomic_write_text(
        plan_dir / "plan_v1.md",
        "# Scene Canvas: Umbrella Return\n## Premise\nTwo strangers argue over a broken umbrella in a cafe.\n",
    )
    atomic_write_json(
        plan_dir / "plan_v1.meta.json",
        {
            "version": 1,
            "timestamp": "2026-04-01T00:00:00Z",
            "hash": "sha256:test",
            "success_criteria": [
                {"criterion": "Scene serves the declared primary criterion", "priority": "must"}
            ],
            "questions": [],
            "assumptions": [],
        },
    )
    atomic_write_json(
        plan_dir / "gate.json",
        {
            "recommendation": "ITERATE",
            "rationale": "Push the weirdness without losing coherence.",
            "signals_assessment": "Needs another pass.",
            "warnings": [],
            "settled_decisions": [],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
        },
    )
    atomic_write_json(
        plan_dir / "faults.json",
        {
            "flags": [
                {
                    "id": "FLAG-001",
                    "concern": "Let the umbrella behave like a suspicious witness.",
                    "category": "correctness",
                    "severity_hint": "likely-significant",
                    "severity": "significant",
                    "status": "open",
                    "evidence": "The current prop beats are still too passive.",
                    "verified": False,
                    "raised_in": "critique_v1.json",
                }
            ]
        },
    )
    atomic_write_text(project_dir / "scenes" / "test.md", "The umbrella refuses to be returned.\n")
    return plan_dir, state


def test_resolve_builder_routes_joke_mode_builders(tmp_path: Path) -> None:
    plan_dir, state = _scaffold_joke_plan(tmp_path)
    del plan_dir

    assert _resolve_builder(_CLAUDE_PROMPT_BUILDERS, "prep", state, "Claude") is _prep_joke_prompt
    assert _resolve_builder(_CLAUDE_PROMPT_BUILDERS, "critique", state, "Claude") is _critique_joke_prompt
    assert _resolve_builder(_CLAUDE_PROMPT_BUILDERS, "revise", state, "Claude") is _revise_joke_prompt
    assert _resolve_builder(_CLAUDE_PROMPT_BUILDERS, "execute", state, "Claude") is _execute_joke_prompt

    review_builder = _resolve_builder(_CLAUDE_PROMPT_BUILDERS, "review", state, "Claude")
    assert isinstance(review_builder, partial)
    assert review_builder.func is _review_joke_prompt


def test_joke_checks_for_robustness_smoke() -> None:
    standard_checks = joke_checks_for_robustness("standard")

    assert len(standard_checks) == 3
    assert [check["id"] for check in standard_checks] == [
        "joke-cut-darling",
        "joke-force-button-first",
        "absurdist",
    ]
    assert joke_checks_for_robustness("tiny") == ()


def test_joke_critique_prompts_include_primary_criterion_and_lens_persona(tmp_path: Path) -> None:
    plan_dir, state = _scaffold_joke_plan(tmp_path)
    check = joke_checks_for_robustness("standard")[0]
    template_path = write_single_check_template(plan_dir, state, check, "critique_check_test.json")

    sequential_prompt = _critique_joke_prompt(state, plan_dir, root=tmp_path)
    single_prompt = single_check_critique_joke_prompt(state, plan_dir, tmp_path, check, template_path)

    assert "weirdest coherent" in sequential_prompt
    assert "joke-cut-darling" in sequential_prompt
    assert "weirdest coherent" in single_prompt
    assert "FLAG-joke-cut-darling" in single_prompt


def test_revise_joke_prompt_contains_rejection_licensing_clauses(tmp_path: Path) -> None:
    plan_dir, state = _scaffold_joke_plan(tmp_path)

    prompt = _revise_joke_prompt(state, plan_dir).lower()

    assert "reject" in prompt
    assert "menu" in prompt
    assert "primary criterion" in prompt


def test_plan_prompt_includes_joke_scene_canvas_contract(tmp_path: Path) -> None:
    plan_dir, state = _scaffold_joke_plan(tmp_path)

    prompt = _plan_prompt(state, plan_dir)

    assert "scene canvas" in prompt.lower()
    assert "weirdest coherent" in prompt
    assert "screenplay-style or short story" in prompt.lower()
