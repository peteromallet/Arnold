from __future__ import annotations

import json
import math
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


def test_gate_prompt_bounds_repeated_history_but_keeps_current_raw_findings(
    tmp_path: Path,
) -> None:
    state = _minimal_state(tmp_path)
    plan_dir = tmp_path / "plan"
    old_history = "OLD_REPEATED_ATTEMPT_SHOULD_NOT_REACH_GATE_" * 20_000
    state["iteration"] = 6
    state["plan_versions"] = [{"version": 6, "file": "plan_v6.md"}]
    state["history"] = [
        {"step": "critique", "result": "success", "raw_attempt": old_history}
        for _ in range(12)
    ]
    (plan_dir / "plan_v6.md").write_text(
        "# Current plan v6\n\nCURRENT_PLAN_V6_SEMANTICS\n",
        encoding="utf-8",
    )
    _write_json(
        plan_dir / "plan_v6.meta.json",
        {
            "version": 6,
            "changes_summary": "CURRENT_PLAN_DELTA",
            "success_criteria": ["CURRENT_SUCCESS_CRITERION"],
            "test_blast_radius": old_history,
            "flags_addressed": [old_history],
        },
    )
    _write_json(
        plan_dir / "critique_v6.json",
        {
            "checks": [
                {
                    "id": "correctness",
                    "question": "Is it correct?",
                    "status": "complete",
                    "unverifiable_reason": "",
                    "findings": [
                        {
                            "detail": "CURRENT_CANONICAL_FINDING",
                            "flagged": True,
                        }
                    ],
                }
            ],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
            "unverifiable_checks": [],
        },
    )
    producer = "EXTERNAL_RAW_FINDING_FROM_CURRENT_CRITIQUE"
    (plan_dir / "critique_check_correctness_producer_v6.json").write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "id": "correctness",
                        "findings": [{"detail": producer, "flagged": True}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_json(
        plan_dir / "critique_custody_v6.json",
        {
            "raw_sources": [
                {
                    "artifact": "critique_check_correctness_producer_v6.json",
                    "sha256": "sha256:" + "a" * 64,
                }
            ]
        },
    )
    _write_json(
        plan_dir / "gate_signals_v6.json",
        {
            "signals": {
                "weighted_score": 4.0,
                "weighted_history": [1.0, 2.0, 4.0],
                "unresolved_flags": [{"concern": old_history}],
                "addressed_flags": [
                    {
                        "id": "current-addressed",
                        "concern": "CURRENT_ADDRESSED_FLAG",
                        "evidence": "CURRENT_ADDRESSED_EVIDENCE",
                        "severity": "significant",
                        "status": "addressed",
                    }
                ],
                "resolved_flags": [{"concern": old_history}],
                "debt_overlaps": [{"detail": old_history}],
            },
            "unresolved_flags": [{"concern": old_history}],
            "warnings": [],
        },
    )
    (plan_dir / "critique_check_correctness_raw_v1.txt").write_text(
        old_history,
        encoding="utf-8",
    )

    prompt = _gate_prompt(state, plan_dir, root=tmp_path)
    conservative_tokens = math.ceil(len(prompt.encode("utf-8")) / 3 * 1.25)

    assert "CURRENT_PLAN_V6_SEMANTICS" in prompt
    assert "CURRENT_SUCCESS_CRITERION" in prompt
    assert "CURRENT_CANONICAL_FINDING" in prompt
    assert producer in prompt
    assert "CURRENT_ADDRESSED_FLAG" in prompt
    assert "CURRENT_ADDRESSED_EVIDENCE" in prompt
    assert "OLD_REPEATED_ATTEMPT_SHOULD_NOT_REACH_GATE" not in prompt
    assert conservative_tokens < 120_000


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
