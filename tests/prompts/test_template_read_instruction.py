from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.prompts.critique_evaluator import _critique_evaluator_prompt
from arnold_pipelines.megaplan.prompts.gate import _gate_prompt


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _minimal_state(tmp_path: Path) -> dict[str, Any]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (plan_dir / "plan_v1.md").write_text("# Plan\n\nDo the work.\n", encoding="utf-8")
    _write_json(
        plan_dir / "plan_v1.meta.json",
        {"tasks": [{"id": "T1", "title": "Do work", "complexity": 1}]},
    )
    _write_json(plan_dir / "gate_signals_v1.json", {"signals": {}, "warnings": []})
    _write_json(plan_dir / "faults.json", {"flags": []})

    state: dict[str, Any] = {
        "name": "demo",
        "idea": "Fix the bug.",
        "iteration": 1,
        "config": {
            "project_dir": str(project_dir),
            "mode": "code",
            "robustness": "full",
        },
        "meta": {},
        "sessions": {},
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "history": [],
    }
    return state


def test_gate_prompt_pairs_template_path_with_exact_read_file_call(tmp_path: Path) -> None:
    state = _minimal_state(tmp_path)
    plan_dir = tmp_path / "plan"

    prompt = _gate_prompt(state, plan_dir, root=tmp_path)
    output_path = plan_dir / "gate_output.json"

    assert f"Your output template is at: {output_path}" in prompt
    assert f"calling `read_file` with `path` exactly `{output_path}`" in prompt
    assert "If you cannot supply that exact non-empty path, do not call `read_file`." in prompt


def test_gate_prompt_distinguishes_north_star_and_critique_severity_enums(
    tmp_path: Path,
) -> None:
    state = _minimal_state(tmp_path)
    plan_dir = tmp_path / "plan"

    prompt = _gate_prompt(state, plan_dir, root=tmp_path)

    assert (
        "The `severity` field on every North Star action accepts exactly "
        '`"blocking"` or `"advisory"`' in prompt
    )
    assert (
        'Critique flag severities such as `"significant"` and '
        '`"likely-significant"` are invalid here' in prompt
    )


def test_gate_prompt_treats_finalize_feasibility_as_post_gate_evidence(
    tmp_path: Path,
) -> None:
    state = _minimal_state(tmp_path)
    plan_dir = tmp_path / "plan"

    prompt = _gate_prompt(state, plan_dir, root=tmp_path)

    assert "Respect phase-order custody" in prompt
    assert "`task_feasibility.json`" in prompt
    assert "are post-gate" in prompt
    assert "Do not block gate merely because finalize has" in prompt
    assert "not yet regenerated them" in prompt
    assert "Finalizer and execute remain fail-closed" not in prompt
    assert "Finalize and execute remain fail-closed" in prompt


def test_critique_evaluator_prompt_pairs_template_path_with_exact_read_file_call(
    tmp_path: Path,
) -> None:
    state = _minimal_state(tmp_path)
    state["iteration"] = 2
    plan_dir = tmp_path / "plan"

    prompt = _critique_evaluator_prompt(state, plan_dir, root=tmp_path)
    output_path = plan_dir / "critique_evaluator_output.json"

    assert f"Your output template is at: {output_path}" in prompt
    assert f"calling `read_file` with `path` exactly `{output_path}`" in prompt
    assert "If you cannot supply that exact non-empty path, do not call `read_file`." in prompt


def test_critique_evaluator_prompt_forbids_invented_check_ids(tmp_path: Path) -> None:
    state = _minimal_state(tmp_path)
    plan_dir = tmp_path / "plan"

    prompt = _critique_evaluator_prompt(state, plan_dir, root=tmp_path)

    assert "Do not invent check IDs" in prompt
    assert 'check_id: "other"' in prompt
    assert "north_star_alignment" in prompt


def test_critique_evaluator_prompt_forbids_combined_flag_verification_lenses(
    tmp_path: Path,
) -> None:
    state = _minimal_state(tmp_path)
    state["iteration"] = 2
    plan_dir = tmp_path / "plan"

    prompt = _critique_evaluator_prompt(
        state,
        plan_dir,
        root=tmp_path,
        revise_resolutions=[
            {
                "id": "flag-1",
                "concern": "Concern.",
                "evidence": "Evidence.",
                "resolution": {"kind": "addressed", "claim": "Fixed.", "where": "T1"},
            }
        ],
        plan_diff="diff --git a/file b/file\n",
    )

    assert "Use exactly one catalog lens id for `lens`" in prompt
    assert "correctness/all_locations" in prompt
