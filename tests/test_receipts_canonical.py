from __future__ import annotations

from pathlib import Path

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan._core import read_json
from arnold.pipelines.megaplan.prompts import create_hermes_prompt
from arnold.pipelines.megaplan.receipts.canonical import hash_prompts


def test_hash_prompts_canonicalizes_transient_fields(tmp_path: Path) -> None:
    project_a = tmp_path / "project-a-11111111-1111-4111-8111-111111111111"
    project_b = tmp_path / "project-b-22222222-2222-4222-8222-222222222222"
    plan_a = project_a / ".megaplan" / "plans" / "alpha-plan"
    plan_b = project_b / ".megaplan" / "plans" / "beta-plan"
    body = "Use the same stable instructions for this phase."
    prompt_a = (
        f"{body}\nproject={project_a}\nplan_dir={plan_a}\nplan=alpha-plan\n"
        "timestamp=2026-04-24T10:15:30+00:00\n"
        "session=33333333-3333-4333-8333-333333333333\n"
    )
    prompt_b = (
        f"{body}\nproject={project_b}\nplan_dir={plan_b}\nplan=beta-plan\n"
        "timestamp=2026-04-25T11:16:31+00:00\n"
        "session=44444444-4444-4444-8444-444444444444\n"
    )

    raw_a, canonical_a = hash_prompts(
        prompt_a,
        project_dir=project_a,
        plan_dir=plan_a,
        plan_id="alpha-plan",
    )
    raw_b, canonical_b = hash_prompts(
        prompt_b,
        project_dir=project_b,
        plan_dir=plan_b,
        plan_id="beta-plan",
    )

    assert raw_a != raw_b
    assert canonical_a == canonical_b


def test_hermes_plan_prompt_canonical_hash_is_stable_across_transients(
    tmp_path: Path,
    plan_fixture,
) -> None:
    fixture_a = plan_fixture
    project_b = tmp_path / "project-b"
    root_b = tmp_path / "root-b"
    project_b.mkdir()
    root_b.mkdir()
    (project_b / ".git").mkdir()
    response_b = megaplan.handle_init(
        root_b,
        fixture_a.make_args(
            name="different-plan-id",
            project_dir=str(project_b),
            robustness="standard",
        ),
    )
    plan_dir_b = megaplan.plans_root(root_b) / response_b["plan"]
    state_a = read_json(fixture_a.plan_dir / "state.json")
    state_b = read_json(plan_dir_b / "state.json")
    state_b["created_at"] = "2026-04-25T11:16:31+00:00"
    state_b["meta"]["notes"].append(
        {
            "timestamp": "2026-04-25T11:16:31+00:00",
            "note": "same stable note 55555555-5555-4555-8555-555555555555",
        }
    )
    state_a["meta"]["notes"].append(
        {
            "timestamp": "2026-04-24T10:15:30+00:00",
            "note": "same stable note 66666666-6666-4666-8666-666666666666",
        }
    )

    prompt_a = create_hermes_prompt("plan", state_a, fixture_a.plan_dir)
    prompt_b = create_hermes_prompt("plan", state_b, plan_dir_b)

    raw_a, canonical_a = hash_prompts(
        prompt_a,
        project_dir=fixture_a.project_dir,
        plan_dir=fixture_a.plan_dir,
        plan_id=state_a["name"],
    )
    raw_b, canonical_b = hash_prompts(
        prompt_b,
        project_dir=project_b,
        plan_dir=plan_dir_b,
        plan_id=state_b["name"],
    )

    assert raw_a != raw_b
    assert canonical_a == canonical_b
