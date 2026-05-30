"""Direct tests for megaplan.prompts."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from megaplan.types import PlanState
from megaplan._core import (
    atomic_write_json,
    atomic_write_text,
    collect_git_diff_summary,
    intent_brief_reference,
    intent_and_notes_block,
    json_dump,
    latest_plan_meta_path,
    latest_plan_path,
    load_debt_registry,
    read_json,
    resolve_debt,
    save_debt_registry,
    save_flag_registry,
)
from megaplan.prompts.review import (
    _review_prompt,
    _settled_decisions_block,
    _settled_decisions_instruction,
    parallel_criteria_review_prompt,
)
from megaplan.prompts.tiebreaker_challenger import challenger_prompt
from megaplan.prompts.tiebreaker_researcher import researcher_prompt
from megaplan.prompts._shared import _gate_summary_or_skipped
from megaplan.prompts import (
    _execute_batch_prompt,
    _execute_doc_batch_prompt,
    _execute_doc_prompt,
    _plan_prompt,
    _prep_distill_prompt,
    _prep_prompt,
    _prep_research_prompt,
    _prep_triage_prompt,
    _render_prep_block,
    create_claude_prompt,
    create_codex_prompt,
)
from megaplan.prompts.execute import _execute_approval_note, _execute_prompt
from megaplan.prompts.review_doc import _review_doc_prompt
from megaplan.prompts.review_joke import _review_joke_prompt
from megaplan.workers import _build_mock_payload


def _state(project_dir: Path, *, iteration: int = 1) -> PlanState:
    return {
        "name": "test-plan",
        "idea": "collapse the workflow",
        "current_state": "critiqued",
        "iteration": iteration,
        "created_at": "2026-03-20T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": iteration,
                "file": f"plan_v{iteration}.md",
                "hash": "sha256:test",
                "timestamp": "2026-03-20T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {
            "significant_counts": [],
            "weighted_scores": [3.5] if iteration > 1 else [],
            "plan_deltas": [42.0] if iteration > 1 else [],
            "recurring_critiques": [],
            "total_cost_usd": 0.0,
            "overrides": [],
            "notes": [],
        },
        "last_gate": {},
    }


def _scaffold(tmp_path: Path, *, iteration: int = 1) -> tuple[Path, PlanState]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    state = _state(project_dir, iteration=iteration)

    atomic_write_text(plan_dir / f"plan_v{iteration}.md", "# Plan\nDo the thing.\n")
    atomic_write_json(
        plan_dir / f"plan_v{iteration}.meta.json",
        {
            "version": iteration,
            "timestamp": "2026-03-20T00:00:00Z",
            "hash": "sha256:test",
            "success_criteria": [{"criterion": "criterion", "priority": "must"}],
            "questions": ["question"],
            "assumptions": ["assumption"],
        },
    )
    atomic_write_json(
        plan_dir / f"critique_v{iteration}.json",
        {"flags": [], "verified_flag_ids": [], "disputed_flag_ids": []},
    )
    atomic_write_json(
        plan_dir / f"gate_signals_v{iteration}.json",
        {
            "robustness": "standard",
            "signals": {
                "iteration": iteration,
                "weighted_score": 2.0,
                "weighted_history": [3.5] if iteration > 1 else [],
                "plan_delta_from_previous": 25.0,
                "recurring_critiques": ["same issue"] if iteration > 1 else [],
                "loop_summary": "Iteration summary",
                "scope_creep_flags": [],
            },
            "warnings": ["watch it"],
            "criteria_check": {"count": 1, "items": ["criterion"]},
            "preflight_results": {
                "project_dir_exists": True,
                "project_dir_writable": True,
                "success_criteria_present": True,
                "claude_available": True,
                "codex_available": True,
            },
            "unresolved_flags": [
                {
                    "id": "FLAG-001",
                    "concern": "still open",
                    "category": "correctness",
                    "severity": "significant",
                    "status": "open",
                    "evidence": "because",
                }
            ],
        },
    )
    atomic_write_json(
        plan_dir / "gate.json",
        {
            **_build_mock_payload(
                "gate",
                state,
                plan_dir,
                recommendation="ITERATE",
                rationale="revise it",
                signals_assessment="not ready",
            ),
            "passed": False,
            "criteria_check": {"count": 1, "items": ["criterion"]},
            "preflight_results": {
                "project_dir_exists": True,
                "project_dir_writable": True,
                "success_criteria_present": True,
                "claude_available": True,
                "codex_available": True,
            },
            "unresolved_flags": [],
            "override_forced": False,
            "robustness": "standard",
            "signals": {"loop_summary": "Iteration summary"},
        },
    )
    atomic_write_json(
        plan_dir / "execution.json",
        _build_mock_payload(
            "execute",
            state,
            plan_dir,
            output="done",
            files_changed=[],
            commands_run=[],
            deviations=[],
            task_updates=[
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Verified the prompt changes and matched them against focused prompt tests.",
                    "files_changed": ["megaplan/prompts.py"],
                    "commands_run": ["pytest tests/test_prompts.py"],
                }
            ],
            sense_check_acknowledgments=[
                {"sense_check_id": "SC1", "executor_note": "Confirmed prompt coverage."}
            ],
        ),
    )
    atomic_write_json(
        plan_dir / "finalize.json",
        _build_mock_payload(
            "finalize",
            state,
            plan_dir,
            tasks=[
                {
                    "id": "T1",
                    "description": "Do the thing",
                    "depends_on": [],
                    "status": "done",
                    "executor_notes": "Verified the prompt changes and matched them against focused prompt tests.",
                    "files_changed": ["megaplan/prompts.py"],
                    "commands_run": ["pytest tests/test_prompts.py"],
                    "evidence_files": [],
                    "reviewer_verdict": "",
                }
            ],
            watch_items=["Check assumptions."],
            sense_checks=[
                {
                    "id": "SC1",
                    "task_id": "T1",
                    "question": "Did it work?",
                    "executor_note": "Confirmed prompt coverage.",
                    "verdict": "",
                }
            ],
            meta_commentary="Stay focused.",
        ),
    )
    save_flag_registry(
        plan_dir,
        {
            "flags": [
                {
                    "id": "FLAG-001",
                    "concern": "still open",
                    "category": "correctness",
                    "severity_hint": "likely-significant",
                    "evidence": "because",
                    "status": "open",
                    "severity": "significant",
                    "verified": False,
                    "raised_in": f"critique_v{iteration}.json",
                }
            ]
        },
    )
    return plan_dir, state


def _render_codex_review_prompt(
    state: PlanState,
    plan_dir: Path,
    *,
    pre_check_flags: list[dict[str, object]] | None = None,
) -> str:
    return _review_prompt(
        state,
        plan_dir,
        review_intro="Review the implementation against the success criteria.",
        criteria_guidance="Verify each success criterion explicitly.",
        task_guidance="Cross-reference each task's `files_changed` and `commands_run` against the git diff and any audit findings.",
        sense_check_guidance="Review every `sense_check` explicitly and treat perfunctory acknowledgments as a reason to dig deeper.",
        pre_check_flags=pre_check_flags,
    )


def test_gate_summary_prefers_recommendation_only_carry(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    atomic_write_json(
        plan_dir / "gate_carry.json",
        {
            "version": 1,
            "recommendation": "PROCEED",
            "passed": True,
            "settled_decisions": [],
        },
    )

    gate = _gate_summary_or_skipped(plan_dir)

    assert gate["recommendation"] == "PROCEED"
    assert "verdict" not in gate


def test_gate_summary_reads_legacy_verdict_only_carry(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    atomic_write_json(
        plan_dir / "gate_carry.json",
        {
            "version": 1,
            "verdict": "ITERATE",
            "passed": False,
            "settled_decisions": [],
        },
    )

    gate = _gate_summary_or_skipped(plan_dir)

    assert gate["recommendation"] == "ITERATE"


def _baseline_codex_review_prompt_snapshot(state: PlanState, plan_dir: Path) -> str:
    project_dir = Path(state["config"]["project_dir"])
    latest_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    latest_meta = read_json(latest_plan_meta_path(plan_dir, state))
    execution = read_json(plan_dir / "execution.json")
    gate = _gate_summary_or_skipped(plan_dir)
    finalize_data = read_json(plan_dir / "finalize.json")
    settled_decisions_block = _settled_decisions_block(gate)
    settled_decisions_instruction = _settled_decisions_instruction(gate)
    diff_summary = collect_git_diff_summary(project_dir)
    audit_path = plan_dir / "execution_audit.json"
    if audit_path.exists():
        audit_block = textwrap.dedent(
            f"""
            Execution audit (`execution_audit.json`):
            {json_dump(read_json(audit_path)).strip()}
            """
        ).strip()
    else:
        audit_block = "Execution audit (`execution_audit.json`): not present. Skip that artifact gracefully and rely on `finalize.json`, `execution.json`, and the git diff."
    return textwrap.dedent(
        f"""
        Review the implementation against the success criteria.

        Project directory:
        {project_dir}

        {intent_brief_reference(state)}

        Approved plan:
        {latest_plan}

        Execution tracking state (`finalize.json`):
        {json_dump(finalize_data).strip()}

        Plan metadata:
        {json_dump(latest_meta).strip()}

        Gate summary:
        {json_dump(gate).strip()}

        {settled_decisions_block}

        Execution summary:
        {json_dump(execution).strip()}

        {audit_block}

        Git diff summary:
        {diff_summary}

        Requirements:
        - Verify each success criterion explicitly.
        - Trust executor evidence by default. Dig deeper only where the git diff, `execution_audit.json`, or vague notes make the claim ambiguous.
        - Each criterion has a `priority` (`must`, `should`, or `info`). Apply these rules:
          - `must` criteria are hard gates. A `must` criterion that fails means `needs_rework`.
          - `should` criteria are quality targets. If the spirit is met but the letter is not, mark `pass` with evidence explaining the gap. Only mark `fail` if the intent was clearly missed. A `should` failure alone does NOT require `needs_rework`.
          - `info` criteria are for human reference. Mark them `waived` with a note — do not evaluate them.
          - If a criterion has `requires` capabilities that are not satisfiable by container workers (e.g., `drive_browser`, `subjective_judgment`), mark it `deferred_human` — NOT `fail` or `waived`. Deferred-human criteria do NOT count toward `needs_rework`.
          - If a criterion (any priority) cannot be verified in this context (e.g., requires manual testing or runtime observation), mark it `waived` with an explanation.
        - Set `review_verdict` to `needs_rework` only when at least one `must` criterion fails or actual implementation work is incomplete. Use `approved` when all `must` criteria pass, even if some `should` criteria are flagged.
        {settled_decisions_instruction}
        - baseline_test_failures in finalize.json lists tests that were already failing before execution. Do not flag these as rework items unless the executor introduced new failures in those same tests.
        - Cross-reference each task's `files_changed` and `commands_run` against the git diff and any audit findings.
        - Review every `sense_check` explicitly and treat perfunctory acknowledgments as a reason to dig deeper.
        - Follow this JSON shape exactly:
        ```json
        {{
          "review_verdict": "approved",
          "criteria": [
            {{
              "name": "All existing tests pass",
              "priority": "must",
              "pass": "pass",
              "evidence": "Test suite ran green — 42 passed, 0 failed."
            }},
            {{
              "name": "File under ~300 lines",
              "priority": "should",
              "pass": "pass",
              "evidence": "File is 375 lines — above the target but reasonable given the component's responsibilities. Spirit met."
            }},
            {{
              "name": "Manual smoke tests pass",
              "priority": "info",
              "pass": "waived",
              "evidence": "Cannot be verified in automated review. Noted for manual QA."
            }}
          ],
          "issues": [],
          "rework_items": [],
          "summary": "Approved. All must criteria pass. The should criterion on line count is close enough given the component scope.",
          "task_verdicts": [
            {{
              "task_id": "T6",
              "reviewer_verdict": "Pass. Claimed handler changes and command evidence match the repo state.",
              "evidence_files": ["megaplan/handlers.py", "megaplan/evaluation.py"]
            }}
          ],
          "sense_check_verdicts": [
            {{
              "sense_check_id": "SC6",
              "verdict": "Confirmed. The execute blocker only fires when both evidence arrays are empty."
            }}
          ]
        }}
        ```
        - `rework_items` must be an array of structured rework directives. When `review_verdict` is `needs_rework`, populate one entry per issue with:
          - `task_id`: which finalize task this issue relates to
          - `issue`: what is wrong
          - `expected`: what correct behavior looks like
          - `actual`: what was observed
          - `evidence_file` (optional): file path supporting the finding
          - `flag_id`: critique/review flag ID when applicable, otherwise `null`
          - `source`: short machine-readable source tag when applicable, otherwise `null`
        - `issues` must still be populated as a flat one-line-per-item summary derived from `rework_items` (for backward compatibility). When approved, both `issues` and `rework_items` should be empty arrays.
        - When the work needs another execute pass, keep the same shape and change only `review_verdict` to `needs_rework`; make `issues`, `rework_items`, `summary`, and task verdicts specific enough for the executor to act on directly.
        """
    ).strip()


def test_codex_plan_prompt_includes_nested_harness_guard(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)

    prompt = create_codex_prompt("plan", state, plan_dir)

    assert "already running inside the megaplan harness" in prompt
    assert "Do NOT invoke the `megaplan` CLI" in prompt
    assert "`megaplan` skill" in prompt
    assert "Avoid `.megaplan/`, prior plan artifacts" in prompt
    assert "Stay focused on the requested idea" in prompt


def test_claude_prep_prompt_includes_nested_harness_guard(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)

    prompt = create_claude_prompt("prep", state, plan_dir, root=tmp_path)

    assert "already running inside the megaplan harness" in prompt
    assert "Do NOT invoke the `megaplan` CLI" in prompt


def _write_debt_registry(tmp_path: Path, entries: list[dict[str, object]]) -> None:
    save_debt_registry(tmp_path, {"entries": entries})


def _debt_entry(
    *,
    debt_id: str = "DEBT-001",
    subsystem: str = "timeout-recovery",
    concern: str = "timeout recovery: retry backoff remains brittle",
    flag_ids: list[str] | None = None,
    plan_ids: list[str] | None = None,
    occurrence_count: int = 1,
    resolved: bool = False,
) -> dict[str, object]:
    return {
        "id": debt_id,
        "subsystem": subsystem,
        "concern": concern,
        "flag_ids": flag_ids or ["FLAG-001"],
        "plan_ids": plan_ids or ["plan-a"],
        "occurrence_count": occurrence_count,
        "created_at": "2026-03-20T00:00:00Z",
        "updated_at": "2026-03-20T00:00:00Z",
        "resolved": resolved,
        "resolved_by": "plan-fixed" if resolved else None,
        "resolved_at": "2026-03-21T00:00:00Z" if resolved else None,
    }


def _write_prep_brief(plan_dir: Path) -> None:
    atomic_write_json(
        plan_dir / "prep.json",
        {
            "task_summary": "PREP_SENTINEL downstream prompts should not broadcast this.",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "Use the prep sentinel only where prep is in scope.",
        },
    )


def test_plan_prompt_absorbs_clarification_when_missing(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("plan", state, plan_dir)
    assert "Identify ambiguities" in prompt
    assert "questions" in prompt
    assert state["idea"] in prompt


def test_prep_prompt_contains_idea_and_root_path(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = _prep_prompt(state, plan_dir, root=tmp_path)
    assert state["idea"] in prompt
    assert str(tmp_path) in prompt
    assert "prep.json" in prompt


def test_prep_prompt_renders_user_notes(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["meta"]["notes"] = [
        {"timestamp": "2026-05-18T00:00:00Z", "note": "focus on shutdown path"},
        {"timestamp": "2026-05-18T00:01:00Z", "note": "skip the CLI plumbing"},
    ]
    prompt = _prep_prompt(state, plan_dir, root=tmp_path)
    assert "User notes and answers:" in prompt
    assert "- focus on shutdown path" in prompt
    assert "- skip the CLI plumbing" in prompt


def test_prep_prompt_renders_prep_direction(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["prep_direction"] = (
        "focus on the worker shutdown path; skip CLI plumbing"
    )
    prompt = _prep_prompt(state, plan_dir, root=tmp_path)
    assert "User direction for prep" in prompt
    assert "focus on the worker shutdown path; skip CLI plumbing" in prompt


def test_prep_prompt_omits_direction_block_when_unset(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"].pop("prep_direction", None)
    prompt = _prep_prompt(state, plan_dir, root=tmp_path)
    assert "User direction for prep" not in prompt


def test_prep_prompt_does_not_duplicate_idea_when_notes_present(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["meta"]["notes"] = [{"timestamp": "2026-05-18T00:00:00Z", "note": "n1"}]
    prompt = _prep_prompt(state, plan_dir, root=tmp_path)
    assert prompt.count(state["idea"]) == 1


def test_render_prep_block_returns_empty_strings_when_missing(tmp_path: Path) -> None:
    plan_dir, _ = _scaffold(tmp_path)
    assert _render_prep_block(plan_dir) == ("", "")


def test_render_prep_block_formats_existing_brief(tmp_path: Path) -> None:
    plan_dir, _ = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "prep.json",
        {
            "skip": False,
            "task_summary": "Add the prep phase before planning.",
            "key_evidence": [
                {"point": "Task requires a prep phase", "source": "idea", "relevance": "high"},
            ],
            "relevant_code": [
                {
                    "file_path": "megaplan/prompts.py",
                    "why": "Prompt injection happens here.",
                    "functions": ["_plan_prompt", "_render_prep_block"],
                }
            ],
            "test_expectations": [
                {
                    "test_id": "FAIL_TO_PASS::prep-phase",
                    "what_it_checks": "Prep artifacts are rendered before planning.",
                    "status": "fail_to_pass",
                }
            ],
            "constraints": ["Do not break standard robustness routing."],
            "suggested_approach": "Render the brief before the raw task context in downstream prompts.",
        },
    )

    block, instruction = _render_prep_block(plan_dir)

    assert "### Task Summary" in block
    assert "Task requires a prep phase" in block
    assert "| File | Functions | Why |" in block
    assert "megaplan/prompts.py" in block
    assert "FAIL_TO_PASS::prep-phase" in block
    assert "Do not break standard robustness routing." in block
    assert "Render the brief before the raw task context in downstream prompts." in block
    assert instruction == (
        "The engineering brief above is evidence gathered from the codebase. "
        "Treat it as the default working context, challenge its conclusions when the code disagrees, "
        "and only do targeted repository lookups when a concrete gap remains."
    )


def test_render_prep_block_omits_skipped_compatible_prep(tmp_path: Path) -> None:
    plan_dir, _ = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "prep.json",
        {
            "skip": True,
            "task_summary": "",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "",
        },
    )

    assert _render_prep_block(plan_dir) == ("", "")


def test_prep_triage_prompt_routes_research_without_final_findings(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = _prep_triage_prompt(state, plan_dir, root=tmp_path)

    assert "prep_triage.json" in prompt
    assert "Route only; do not produce the final prep brief yet." in prompt
    assert "Returning `areas: []` is the explicit skip path" in prompt
    assert "Do not emit final findings" in prompt


def test_prep_research_prompt_is_area_scoped(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = _prep_research_prompt(
        state,
        plan_dir,
        area={
            "id": "callers",
            "area": "Caller coverage",
            "brief": "Find every call site that depends on the changed contract.",
            "suggested_files": ["megaplan/workers.py"],
        },
        root=tmp_path,
    )

    assert "Investigate one prep research area" in prompt
    assert '"id": "callers"' in prompt
    assert "`status`: one of `complete`, `partial`, `timed_out`, `error`, `not_needed`." in prompt
    assert "Stay inside this area; do not try to solve the entire task." in prompt


def test_prep_distill_prompt_preserves_compatible_prep_contract(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = _prep_distill_prompt(
        state,
        plan_dir,
        triage={"triage_framing": "Need targeted investigation", "areas": []},
        findings=[
            {
                "area": "callers",
                "brief": "Trace call sites",
                "status": "partial",
                "findings": ["One caller still uses the old shape."],
                "files": ["megaplan/workers.py"],
                "code_refs": ["megaplan.workers.handle_prep"],
                "confidence": "medium",
                "error": "",
            }
        ],
        root=tmp_path,
    )

    assert "prep_dossier.md" in prompt
    assert "prep_metrics.json" in prompt
    assert "Do not add new required fields to the compatible `prep.json` payload." in prompt
    assert "Resolve overlaps across areas into one coherent prep view" in prompt
    assert "bounded read-only cross-reference" in prompt
    assert "keep any further repository lookup tightly targeted to that gap." in prompt


def test_light_plan_prompt_uses_normal_plan_prompt(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["robustness"] = "light"
    prompt = create_claude_prompt("plan", state, plan_dir)
    # Light now uses the standard plan prompt, no self_flags or gate fields
    assert "self_flags" not in prompt
    assert "gate_recommendation" not in prompt
    assert "plan" in prompt.lower()


def test_plan_prompt_uses_existing_clarification_context(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["clarification"] = {"intent_summary": "Keep it simple", "questions": ["What changes?"], "refined_idea": "Refined"}
    prompt = create_claude_prompt("plan", state, plan_dir)
    assert "Existing clarification context" in prompt
    assert "Keep it simple" in prompt



def test_revise_prompt_reads_gate_summary(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("revise", state, plan_dir)
    assert "Gate summary" in prompt
    assert "revise it" in prompt


def test_gate_prompt_includes_loop_signals_and_preflight(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path, iteration=2)
    prompt = create_codex_prompt("gate", state, plan_dir)
    assert "Gate signals" in prompt
    assert "Iteration summary" in prompt
    assert "preflight" in prompt.lower()
    assert "PROCEED, ITERATE, ESCALATE" in prompt


def test_gate_prompt_includes_escalated_debt_warning_when_threshold_met(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path, iteration=2)
    _write_debt_registry(
        tmp_path,
        [
            _debt_entry(
                concern="timeout recovery: retry backoff remains brittle",
                occurrence_count=4,
                plan_ids=["plan-a", "plan-b", "plan-c"],
            )
        ],
    )

    prompt = create_codex_prompt("gate", state, plan_dir, root=tmp_path)

    assert "Escalated debt subsystems" in prompt
    assert '"total_occurrences": 4' in prompt
    assert "holistic redesign" in prompt


def test_review_prompt_includes_execution_and_gate(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("review", state, plan_dir)
    assert "Gate summary" in prompt
    assert "Execution summary" in prompt
    assert "Execution tracking state (`finalize.json`)" in prompt


def test_plan_prompt_is_nonempty(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("plan", state, plan_dir)
    assert len(prompt) > 100


def test_plan_prompt_includes_concrete_template(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("plan", state, plan_dir)
    assert "# Implementation Plan: [Title]" in prompt
    assert "## Overview" in prompt
    assert "## Step 1: Audit the current behavior" in prompt
    assert "## Execution Order" in prompt
    assert "## Validation Order" in prompt


def test_critique_prompt_contains_intent_and_robustness(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["idea"] = "collapse the workflow. VERBATIM_DETAIL_SHOULD_NOT_BROADCAST"
    prompt = create_claude_prompt("critique", state, plan_dir)
    assert "Brief summary: collapse the workflow" in prompt
    assert "VERBATIM_DETAIL_SHOULD_NOT_BROADCAST" not in prompt
    assert "Robustness level" in prompt
    assert "standard" in prompt
    assert "simplest approach" in prompt
    assert "Over-engineering:" in prompt
    assert "maintainability" in prompt


def test_critique_prompt_includes_debt_context_when_registry_exists(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    _write_debt_registry(
        tmp_path,
        [
            _debt_entry(
                concern="timeout recovery: retry backoff remains brittle",
                occurrence_count=2,
                plan_ids=["plan-a", "plan-b"],
            )
        ],
    )

    prompt = create_claude_prompt("critique", state, plan_dir, root=tmp_path)

    assert "Known accepted debt grouped by subsystem" in prompt
    assert "timeout-recovery" in prompt
    assert "retry backoff remains brittle" in prompt
    assert "Do not re-flag them unless the current plan makes them worse" in prompt


def test_critique_prompt_includes_structure_guidance_and_warnings(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "plan_v1.meta.json",
        {
            "version": 1,
            "timestamp": "2026-03-20T00:00:00Z",
            "hash": "sha256:test",
            "success_criteria": [{"criterion": "criterion", "priority": "must"}],
            "questions": ["question"],
            "assumptions": ["assumption"],
            "structure_warnings": ["Plan should include a `## Overview` section."],
        },
    )
    prompt = create_claude_prompt("critique", state, plan_dir)
    assert "Plan structure warnings from validator" in prompt
    assert "Plan should include a `## Overview` section." in prompt
    assert "Verify that the plan follows the expected structure" in prompt


def test_critique_light_robustness(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["robustness"] = "light"
    prompt = create_claude_prompt("critique", state, plan_dir)
    assert "pragmatic" in prompt.lower() or "light" in prompt.lower()


def test_revise_prompt_contains_intent(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["idea"] = "collapse the workflow. VERBATIM_DETAIL_SHOULD_NOT_BROADCAST"
    prompt = create_claude_prompt("revise", state, plan_dir)
    assert "Brief summary: collapse the workflow" in prompt
    assert "VERBATIM_DETAIL_SHOULD_NOT_BROADCAST" not in prompt
    assert "Gate summary" in prompt


def test_downstream_prompts_use_brief_reference_and_trim_prep(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["idea"] = "collapse the workflow. VERBATIM_DETAIL_SHOULD_NOT_BROADCAST"
    _write_prep_brief(plan_dir)

    prompts = {
        "critique": create_claude_prompt("critique", state, plan_dir),
        "revise": create_claude_prompt("revise", state, plan_dir),
        "gate": create_claude_prompt("gate", state, plan_dir),
        "finalize": create_claude_prompt("finalize", state, plan_dir),
        "review": create_claude_prompt("review", state, plan_dir),
        "execute_batch": _execute_batch_prompt(state, plan_dir, ["T1"], set()),
        "tiebreaker_researcher": researcher_prompt("Pick A or B?", state, plan_dir),
        "tiebreaker_challenger": challenger_prompt(
            "Pick A or B?",
            {"options": [], "preliminary_pick": "A"},
            state,
            plan_dir,
        ),
    }

    for name, prompt in prompts.items():
        assert "Brief summary: collapse the workflow" in prompt, name
        assert "VERBATIM_DETAIL_SHOULD_NOT_BROADCAST" not in prompt, name

    for name in [
        "critique",
        "revise",
        "finalize",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
    ]:
        assert "PREP_SENTINEL" not in prompts[name], name
        assert "Engineering brief produced from the codebase" not in prompts[name], name

    plan_prompt = create_claude_prompt("plan", state, plan_dir)
    execute_prompt = create_claude_prompt("execute", state, plan_dir)
    assert "PREP_SENTINEL" in plan_prompt
    assert "PREP_SENTINEL" in execute_prompt


def test_revise_prompt_does_not_include_plan_template(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("revise", state, plan_dir)
    assert "# Implementation Plan: [Title]" not in prompt
    assert "## Step 1: Audit the current behavior" not in prompt


def test_codex_matches_claude_for_shared_steps(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    for step in ["plan", "prep", "critique", "revise", "gate", "execute"]:
        claude_prompt = create_claude_prompt(step, state, plan_dir)
        codex_prompt = create_codex_prompt(step, state, plan_dir)
        assert claude_prompt == codex_prompt, f"Prompts differ for step '{step}'"


def test_review_prompts_differ_between_agents(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    claude_prompt = create_claude_prompt("review", state, plan_dir)
    codex_prompt = create_codex_prompt("review", state, plan_dir)
    # Review prompts should be different across agents even though both include gate context.
    assert claude_prompt != codex_prompt


def test_execute_prompt_auto_approve_note(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["auto_approve"] = True
    prompt = create_claude_prompt("execute", state, plan_dir)
    assert "auto-approve" in prompt
    assert "task_updates" in prompt
    assert "sense_check_acknowledgments" in prompt
    assert '"files_changed": ["megaplan/handlers.py"' in prompt
    assert "verification-focused" in prompt


def test_execute_prompt_user_approved_note(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["meta"]["user_approved_gate"] = True
    prompt = create_claude_prompt("execute", state, plan_dir)
    assert "explicitly approved" in prompt
    assert "Execution tracking source of truth (`finalize.json`)" in prompt


def test_execute_single_and_batch_approval_note_match_auto_approve(tmp_path: Path) -> None:
    """Single-task and batch prompts emit identical approval-note text for auto-approve."""
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["auto_approve"] = True
    single_prompt = _execute_prompt(state, plan_dir, root=None)
    batch_prompt = _execute_batch_prompt(state, plan_dir, ["T1"], set())
    expected = _execute_approval_note(state)
    assert expected in single_prompt
    assert expected in batch_prompt


def test_execute_single_and_batch_approval_note_match_user_approved_gate(tmp_path: Path) -> None:
    """Single-task and batch prompts emit identical approval-note text for user-approved gate."""
    plan_dir, state = _scaffold(tmp_path)
    state["meta"]["user_approved_gate"] = True
    single_prompt = _execute_prompt(state, plan_dir, root=None)
    batch_prompt = _execute_batch_prompt(state, plan_dir, ["T1"], set())
    expected = _execute_approval_note(state)
    assert expected in single_prompt
    assert expected in batch_prompt


def test_execute_single_and_batch_approval_note_match_review_mode(tmp_path: Path) -> None:
    """Single-task and batch prompts emit identical approval-note text for review mode."""
    plan_dir, state = _scaffold(tmp_path)
    # Neither auto_approve nor user_approved_gate set → review mode
    single_prompt = _execute_prompt(state, plan_dir, root=None)
    batch_prompt = _execute_batch_prompt(state, plan_dir, ["T1"], set())
    expected = _execute_approval_note(state)
    assert expected in single_prompt
    assert expected in batch_prompt


def test_execute_prompt_surfaces_sense_checks_and_watch_items(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("execute", state, plan_dir)
    assert "Sense checks to keep in mind during execution" in prompt
    assert "SC1 (T1): Did it work?" in prompt
    assert "Watch items to keep visible during execution:" in prompt
    assert "Check assumptions." in prompt


def test_execute_prompt_includes_debt_watch_items(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    _write_debt_registry(
        tmp_path,
        [
            _debt_entry(
                concern="timeout recovery: retry backoff remains brittle",
                occurrence_count=3,
                plan_ids=["plan-a", "plan-b"],
            )
        ],
    )

    prompt = create_claude_prompt("execute", state, plan_dir, root=tmp_path)

    assert "Debt watch items (do not make these worse):" in prompt
    assert "[DEBT] timeout-recovery: timeout recovery: retry backoff remains brittle" in prompt
    assert "flagged 3 times across 2 plans" in prompt


def test_resolved_debt_no_longer_appears_in_subsequent_prompts(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    _write_debt_registry(tmp_path, [_debt_entry()])

    before_prompt = create_claude_prompt("execute", state, plan_dir, root=tmp_path)
    registry = load_debt_registry(tmp_path)
    resolve_debt(registry, "DEBT-001", "plan-fixed")
    save_debt_registry(tmp_path, registry)
    after_prompt = create_claude_prompt("execute", state, plan_dir, root=tmp_path)

    assert "retry backoff remains brittle" in before_prompt
    assert "retry backoff remains brittle" not in after_prompt


def test_execute_prompt_includes_finalize_path_and_checkpoint_instructions(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("execute", state, plan_dir)
    # Single-batch checkpoint should go to execution_checkpoint.json, NOT finalize.json
    assert str(plan_dir / "execution_checkpoint.json") in prompt
    assert "Best-effort progress checkpointing" in prompt
    assert "full read-modify-write" in prompt
    assert "Structured output remains the authoritative final summary" in prompt
    assert "Do not create or rewrite tracking artifacts directly." not in prompt
    # finalize.json should still appear as the source of truth, but NOT as the checkpoint target
    assert "source of truth" in prompt
    assert "harness owns" in prompt.lower() or "not `finalize.json`" in prompt.lower()


def test_finalize_prompt_requests_structured_tracking_fields(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("finalize", state, plan_dir)
    assert "tasks" in prompt
    assert "sense_checks" in prompt
    assert "executor_notes" in prompt
    assert "reviewer_verdict" in prompt
    assert "Do not include `validation` or `coverage_complete` fields" in prompt
    assert "plan_steps_covered" not in prompt
    assert "orphan_tasks" not in prompt
    assert "final_plan" not in prompt
    assert "_notes:_" not in prompt
    assert "_verdict:_" not in prompt


def test_finalize_prompt_handles_tiny_without_gate(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["robustness"] = "tiny"
    state["config"]["mode"] = "doc"
    (plan_dir / "gate.json").unlink()
    prompt = create_claude_prompt("finalize", state, plan_dir)
    assert "No gate phase ran for this robustness level" in prompt
    assert "emit exactly one task" in prompt
    assert "tasks" in prompt


def test_execute_prompts_handle_tiny_without_gate(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    (plan_dir / "gate.json").unlink()
    code_prompt = create_claude_prompt("execute", state, plan_dir)
    assert "No gate phase ran for this robustness level" in code_prompt

    state["config"]["mode"] = "doc"
    state["config"]["output_path"] = "docs/out.md"
    doc_prompt = create_claude_prompt("execute", state, plan_dir)
    assert "No gate phase ran for this robustness level" in doc_prompt
    assert "docs/out.md" in doc_prompt


def test_review_prompts_request_verdict_arrays(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    claude_prompt = create_claude_prompt("review", state, plan_dir)
    codex_prompt = create_codex_prompt("review", state, plan_dir)
    assert "review_verdict" in claude_prompt
    assert "task_verdicts" in claude_prompt
    assert "sense_check_verdicts" in claude_prompt
    assert "evidence_files" in claude_prompt
    assert "execution_audit.json" in claude_prompt
    assert "needs_rework" in claude_prompt
    assert "rework_items" in claude_prompt
    assert "review_verdict" in codex_prompt
    assert "task_verdicts" in codex_prompt
    assert "sense_check_verdicts" in codex_prompt
    assert "evidence_files" in codex_prompt
    assert "execution_audit.json" in codex_prompt
    assert "needs_rework" in codex_prompt
    assert "rework_items" in codex_prompt
    assert "final.md" not in claude_prompt
    assert "final.md" not in codex_prompt


def test_review_prompt_includes_reverify_block_for_addressed_flags(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    save_flag_registry(
        plan_dir,
        {
            "flags": [
                {
                    "id": "FLAG-ADDRESSED-001",
                    "concern": "The addressed branch still needs final-diff verification.",
                    "category": "correctness",
                    "severity_hint": "likely-significant",
                    "severity": "significant",
                    "status": "addressed",
                }
            ]
        },
    )

    prompt = create_codex_prompt("review", state, plan_dir)

    assert "FLAG-ADDRESSED-001" in prompt
    assert "verify whether the final diff actually addresses the concern" in prompt


def test_review_prompt_includes_reverify_block_for_open_flags(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    save_flag_registry(
        plan_dir,
        {
            "flags": [
                {
                    "id": "FLAG-OPEN-001",
                    "concern": "The open branch still needs final-diff verification.",
                    "category": "correctness",
                    "severity_hint": "likely-significant",
                    "severity": "significant",
                    "status": "open",
                }
            ]
        },
    )

    prompt = create_codex_prompt("review", state, plan_dir)

    assert "FLAG-OPEN-001" in prompt
    assert "verify whether the final diff actually addresses the concern" in prompt


def test_review_prompt_without_flags_or_prechecks_matches_snapshot(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    save_flag_registry(plan_dir, {"flags": []})

    prompt = _render_codex_review_prompt(state, plan_dir, pre_check_flags=None)

    assert prompt == _baseline_codex_review_prompt_snapshot(state, plan_dir)


def test_review_prompt_with_only_prechecks_adds_mechanical_block(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    save_flag_registry(plan_dir, {"flags": []})

    prompt = _render_codex_review_prompt(
        state,
        plan_dir,
        pre_check_flags=[
            {
                "id": "PRECHECK-1",
                "check": "source_touch",
                "detail": "Advisory only.",
                "severity": "minor",
            }
        ],
    )

    assert "Advisory mechanical pre-check flags" in prompt
    assert "Copy this list verbatim into the output `pre_check_flags` field." in prompt
    assert "Critique flags to re-verify against the final diff" not in prompt


def test_execute_prompt_includes_previous_review_when_present(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "review.json",
        {
            "review_verdict": "needs_rework",
            "criteria": [],
            "issues": ["Need another execute pass."],
            "summary": "Rework needed.",
            "task_verdicts": [
                {
                    "task_id": "T1",
                    "reviewer_verdict": "Incomplete implementation.",
                    "evidence_files": ["megaplan/prompts.py"],
                }
            ],
            "sense_check_verdicts": [{"sense_check_id": "SC1", "verdict": "Needs follow-up."}],
        },
    )
    prompt = create_claude_prompt("execute", state, plan_dir)
    assert "Previous review findings to address" in prompt
    assert "Need another execute pass." in prompt


def test_execute_prompt_forbids_pending_task_updates_and_explains_manual_skip(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)

    prompt = create_claude_prompt("execute", state, plan_dir)

    assert '`task_updates[].status` must be either `done` or `skipped`.' in prompt
    assert 'Never return `pending` in execute output.' in prompt
    assert 'missing devices' in prompt
    assert 'manual-only validation' in prompt
    assert 'return `status: "skipped"`' in prompt


def test_execute_batch_prompt_scopes_tasks_and_sense_checks(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "finalize.json",
        _build_mock_payload(
            "finalize",
            state,
            plan_dir,
            tasks=[
                {
                    "id": "T1",
                    "description": "First",
                    "depends_on": [],
                    "status": "done",
                    "executor_notes": "Completed already.",
                    "files_changed": ["megaplan/prompts.py"],
                    "commands_run": ["pytest tests/test_prompts.py"],
                    "evidence_files": [],
                    "reviewer_verdict": "",
                },
                {
                    "id": "T2",
                    "description": "Second",
                    "depends_on": ["T1"],
                    "status": "pending",
                    "executor_notes": "",
                    "files_changed": [],
                    "commands_run": [],
                    "evidence_files": [],
                    "reviewer_verdict": "",
                },
            ],
            sense_checks=[
                {"id": "SC1", "task_id": "T1", "question": "Done?", "executor_note": "Confirmed.", "verdict": ""},
                {"id": "SC2", "task_id": "T2", "question": "Next?", "executor_note": "", "verdict": ""},
            ],
        ),
    )
    atomic_write_json(
        plan_dir / "execution_batch_1.json",
        _build_mock_payload(
            "execute",
            state,
            plan_dir,
            deviations=["Advisory quality: megaplan/prompts.py grew by 220 lines (threshold 200)."],
        ),
    )
    prompt = _execute_batch_prompt(state, plan_dir, ["T2"], {"T1"})
    assert "Execute batch 2 of 2." in prompt
    assert "Only produce `task_updates` for these tasks: [T2]" in prompt
    assert "Only produce `sense_check_acknowledgments` for these sense checks: [SC2]" in prompt
    assert '"id": "T2"' in prompt
    assert '"id": "SC2"' in prompt
    assert "Prior batch deviations (address if applicable):" in prompt
    assert "Advisory quality: megaplan/prompts.py grew by 220 lines (threshold 200)." in prompt
    # Batch prompt checkpoint should reference execution_batch_2.json, not finalize.json
    assert "execution_batch_2.json" in prompt
    assert "not `finalize.json`" in prompt.lower() or "harness owns" in prompt.lower()


def test_execute_batch_prompt_handles_first_batch_without_prior_deviations(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "finalize.json",
        _build_mock_payload(
            "finalize",
            state,
            plan_dir,
            tasks=[
                {
                    "id": "T1",
                    "description": "First",
                    "depends_on": [],
                    "status": "pending",
                    "executor_notes": "",
                    "files_changed": [],
                    "commands_run": [],
                    "evidence_files": [],
                    "reviewer_verdict": "",
                }
            ],
            sense_checks=[
                {"id": "SC1", "task_id": "T1", "question": "Done?", "executor_note": "", "verdict": ""},
            ],
        ),
    )

    prompt = _execute_batch_prompt(state, plan_dir, ["T1"], set())

    assert "Execute batch 1 of 1." in prompt
    assert "Prior batch deviations (address if applicable):" in prompt
    assert "None" in prompt


def test_review_prompt_gracefully_handles_missing_audit(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("review", state, plan_dir)
    assert "not present" in prompt
    assert "Skip that artifact gracefully" in prompt


def test_review_prompt_includes_settled_decisions_when_present(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "gate.json",
        {
            **_build_mock_payload(
                "gate",
                state,
                plan_dir,
                recommendation="PROCEED",
                rationale="ready",
                signals_assessment="stable",
                settled_decisions=[
                    {
                        "id": "DECISION-001",
                        "decision": "Treat FLAG-006 softening as settled.",
                        "rationale": "The gate already approved the tradeoff.",
                    }
                ],
            ),
            "passed": True,
            "criteria_check": {"count": 1, "items": ["criterion"]},
            "preflight_results": {
                "project_dir_exists": True,
                "project_dir_writable": True,
                "success_criteria_present": True,
                "claude_available": True,
                "codex_available": True,
            },
            "unresolved_flags": [],
            "override_forced": False,
            "robustness": "standard",
            "signals": {"loop_summary": "Iteration summary"},
        },
    )
    prompt = create_claude_prompt("review", state, plan_dir)
    assert "verify the executor implemented these correctly" in prompt
    assert "DECISION-001" in prompt
    assert "Treat FLAG-006 softening as settled." in prompt


def test_review_prompt_omits_settled_decisions_when_empty(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_codex_prompt("review", state, plan_dir)
    assert "Settled decisions (verify the executor implemented these correctly)" not in prompt


def test_parallel_criteria_review_prompt_uses_issue_anchored_context_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan_dir, state = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "gate.json",
        {
            "settled_decisions": [
                {
                    "id": "DECISION-001",
                    "decision": "Keep the parser fix source-local.",
                    "rationale": "The gate already approved this tradeoff.",
                }
            ]
        },
    )
    monkeypatch.setattr(
        "megaplan.prompts.review.collect_git_diff_patch",
        lambda project_dir: "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n+print('patched')\n",
    )

    prompt = parallel_criteria_review_prompt(state, plan_dir, tmp_path, plan_dir / "review_criteria_verdict.json")

    assert "Approved plan:" not in prompt
    assert "Plan metadata:" not in prompt
    assert "Execution summary:" not in prompt
    assert "Execution audit" not in prompt
    assert "Gate summary:" not in prompt
    assert intent_brief_reference(state) in prompt
    assert "diff --git a/app.py b/app.py" in prompt
    assert '"tasks": [' in prompt
    assert "DECISION-001" in prompt
    assert "Keep the parser fix source-local." in prompt


def test_plan_prompt_includes_notes_when_present(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["meta"]["notes"] = [{"note": "Keep it simple", "timestamp": "2026-03-20T00:00:00Z"}]
    prompt = create_claude_prompt("plan", state, plan_dir)
    assert "Keep it simple" in prompt


def test_execute_doc_prompt_renders_from_doc_path_even_without_imported_decisions(
    tmp_path: Path,
) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["mode"] = "doc"
    state["config"]["output_path"] = "docs/design.md"
    state["config"]["from_doc"] = "docs/prior.md"
    state["meta"]["imported_decisions"] = []

    prompt = _execute_doc_prompt(state, plan_dir)

    assert "Prior doc imported via --from-doc:" in prompt
    assert "docs/prior.md" in prompt
    assert "Imported decisions (from the source doc's ## Settled Decisions section): 0" in prompt
    assert "## Settled Decisions" in prompt
    assert "Downstream plans can import these via `megaplan init --from-doc`." in prompt


def test_execute_doc_batch_prompt_lists_imported_decisions_when_present(
    tmp_path: Path,
) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["mode"] = "doc"
    state["config"]["output_path"] = "docs/design.md"
    state["config"]["from_doc"] = "docs/prior.md"
    state["meta"]["imported_decisions"] = [
        {
            "id": "SD-001",
            "decision": "Keep SQLite",
            "rationale": "Existing workflows depend on it.",
            "load_bearing": True,
        }
    ]

    prompt = _execute_doc_batch_prompt(state, plan_dir, ["T1"])

    assert "Prior doc imported via --from-doc:" in prompt
    assert "docs/prior.md" in prompt
    assert "Imported decisions (from the source doc's ## Settled Decisions section): 1" in prompt
    assert "- SD-001: Keep SQLite" in prompt
    assert "load_bearing: True" in prompt
    assert "Downstream plans can import these via `megaplan init --from-doc`." in prompt


def test_plan_prompt_includes_prior_doc_fallback_when_no_decisions(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["from_doc"] = "docs/prior.md"
    state["meta"]["imported_decisions"] = []

    prompt = _plan_prompt(state, plan_dir)

    assert "Prior doc imported via --from-doc:" in prompt
    assert "docs/prior.md" in prompt
    assert "No ## Settled Decisions section found — path stored for reference only." in prompt


def test_plan_prompt_includes_imported_decision_guidance(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    state["config"]["from_doc"] = "docs/prior.md"
    state["meta"]["imported_decisions"] = [
        {
            "id": "SD-001",
            "decision": "Keep SQLite",
            "rationale": "Existing workflows depend on it.",
            "load_bearing": True,
        },
        {
            "id": "SD-002",
            "decision": "Keep docs flat",
            "rationale": "Reviewers expect it.",
            "load_bearing": False,
        },
    ]

    prompt = _plan_prompt(state, plan_dir)

    assert "Prior doc imported via --from-doc:" in prompt
    assert "- SD-001: Keep SQLite" in prompt
    assert "- SD-002: Keep docs flat" in prompt
    assert "include a success criterion with priority: 'must' referencing the SD-NNN id." in prompt
    assert "include a success criterion with priority: 'info' referencing the SD-NNN id." in prompt


def test_unsupported_step_raises(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    with pytest.raises(Exception):
        create_claude_prompt("clarify", state, plan_dir)


def test_unsupported_codex_step_raises(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    with pytest.raises(Exception):
        create_codex_prompt("clarify", state, plan_dir)


# ---------------------------------------------------------------------------
# _review_doc_prompt and _review_joke_prompt snapshot tests
# ---------------------------------------------------------------------------


def _scaffold_doc_review(tmp_path: Path) -> tuple[Path, PlanState]:
    """Scaffold minimal state for _review_doc_prompt rendering."""
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    output_path = "output.md"
    output_file = project_dir / output_path
    output_file.write_text("# Final Document\n\nAll sections present.\n", encoding="utf-8")

    state: PlanState = {
        "name": "doc-review-test",
        "idea": "Write a document about testing.",
        "current_state": "executed",
        "iteration": 1,
        "created_at": "2026-05-01T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
            "mode": "doc",
            "output_path": output_path,
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": 1,
                "file": "plan_v1.md",
                "hash": "sha256:doc",
                "timestamp": "2026-05-01T00:00:00Z",
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

    atomic_write_text(plan_dir / "plan_v1.md", "# Doc Plan\n## Sections\n- Intro\n- Body\n- Conclusion\n")
    atomic_write_json(
        plan_dir / "plan_v1.meta.json",
        {
            "version": 1,
            "timestamp": "2026-05-01T00:00:00Z",
            "hash": "sha256:doc",
            "success_criteria": [
                {"criterion": "Document covers all planned sections", "priority": "must"}
            ],
            "questions": [],
            "assumptions": [],
        },
    )
    atomic_write_json(
        plan_dir / "execution.json",
        {
            "output": "done",
            "files_changed": ["output.md"],
            "commands_run": [],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Wrote all sections.",
                    "files_changed": ["output.md"],
                    "commands_run": [],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Done."}
            ],
        },
    )
    atomic_write_json(
        plan_dir / "gate.json",
        {
            "recommendation": "PROCEED",
            "rationale": "Plan looks good.",
            "settled_decisions": [],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
            "warnings": [],
        },
    )
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "T1",
                    "description": "Write the document",
                    "status": "done",
                    "executor_notes": "Wrote all sections.",
                    "files_changed": ["output.md"],
                    "commands_run": [],
                }
            ],
            "sense_checks": [
                {
                    "id": "SC1",
                    "task_id": "T1",
                    "question": "Does the output exist?",
                    "executor_note": "Done.",
                    "verdict": "",
                }
            ],
            "meta_commentary": "All good.",
        },
    )
    return plan_dir, state


def _scaffold_joke_review(tmp_path: Path) -> tuple[Path, PlanState]:
    """Scaffold minimal state for _review_joke_prompt rendering."""
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    output_path = "scenes/scene.md"
    (project_dir / "scenes").mkdir()
    output_file = project_dir / output_path
    output_file.write_text("The umbrella refuses to be returned.\n", encoding="utf-8")

    state: PlanState = {
        "name": "joke-review-test",
        "idea": "Two strangers try to return a broken umbrella.",
        "current_state": "executed",
        "iteration": 1,
        "created_at": "2026-05-01T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
            "mode": "joke",
            "output_path": output_path,
            "primary_criterion": "weirdest coherent",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": 1,
                "file": "plan_v1.md",
                "hash": "sha256:joke",
                "timestamp": "2026-05-01T00:00:00Z",
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

    atomic_write_text(plan_dir / "plan_v1.md", "# Scene Canvas: Umbrella Return\n## Premise\nTwo strangers argue over a broken umbrella.\n")
    atomic_write_json(
        plan_dir / "plan_v1.meta.json",
        {
            "version": 1,
            "timestamp": "2026-05-01T00:00:00Z",
            "hash": "sha256:joke",
            "success_criteria": [
                {"criterion": "Scene serves the declared primary criterion", "priority": "must"}
            ],
            "questions": [],
            "assumptions": [],
        },
    )
    atomic_write_json(
        plan_dir / "execution.json",
        {
            "output": "done",
            "files_changed": ["scenes/scene.md"],
            "commands_run": [],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Wrote a scene.",
                    "files_changed": ["scenes/scene.md"],
                    "commands_run": [],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Done."}
            ],
        },
    )
    atomic_write_json(
        plan_dir / "gate.json",
        {
            "recommendation": "ITERATE",
            "rationale": "Push the weirdness.",
            "settled_decisions": [],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
            "warnings": [],
        },
    )
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "T1",
                    "description": "Write the scene",
                    "status": "done",
                    "executor_notes": "Wrote a scene.",
                    "files_changed": ["scenes/scene.md"],
                    "commands_run": [],
                }
            ],
            "sense_checks": [
                {
                    "id": "SC1",
                    "task_id": "T1",
                    "question": "Does the scene exist?",
                    "executor_note": "Done.",
                    "verdict": "",
                }
            ],
            "meta_commentary": "Looking good.",
        },
    )
    return plan_dir, state


def test_review_doc_prompt_key_strings(tmp_path: Path) -> None:
    """_review_doc_prompt renders document-specific key strings and JSON example."""
    plan_dir, state = _scaffold_doc_review(tmp_path)

    prompt = _review_doc_prompt(
        state,
        plan_dir,
        review_intro="Review the document critically against user intent and observable success criteria.",
        criteria_guidance="Judge against the success criteria, not plan elegance.",
        task_guidance="Review each task by cross-referencing the executor's per-task `sections_written` against the output document.",
        sense_check_guidance="Review every sense check explicitly.",
    )

    # Key exact strings that distinguish the doc review prompt
    assert "Approved plan:" in prompt
    assert "Output document content:" in prompt
    # Doc JSON example — criteria name and evidence
    assert '"name": "Document covers all planned sections"' in prompt
    assert '"evidence": "All 5 planned sections are present and non-empty."' in prompt
    # Doc task verdict example
    assert '"reviewer_verdict": "Pass. Introduction section covers scope and audience as planned."' in prompt
    # Doc sense check verdict example
    assert '"verdict": "Confirmed. The introduction references prior art as required."' in prompt
    # Doc review_verdict example
    assert '"review_verdict": "approved"' in prompt
    # Should not contain joke/scene-specific strings
    assert "Approved scene canvas:" not in prompt
    assert "Output scene content:" not in prompt
    assert "Primary criterion:" not in prompt


def test_review_joke_prompt_key_strings(tmp_path: Path) -> None:
    """_review_joke_prompt renders joke-specific key strings and JSON example."""
    plan_dir, state = _scaffold_joke_review(tmp_path)

    prompt = _review_joke_prompt(
        state,
        plan_dir,
        review_intro="Review the scene critically against the brief, the declared primary criterion, and the approved scene canvas.",
        criteria_guidance="Judge first against the declared primary criterion, then against the remaining success criteria and scene-canvas commitments.",
        task_guidance="Review each task by cross-referencing the executor's per-task `sections_written` against the output scene prose.",
        sense_check_guidance="Review every sense check explicitly.",
    )

    # Key exact strings that distinguish the joke/scene review prompt
    assert "Approved scene canvas:" in prompt
    assert "Output scene content:" in prompt
    assert "Primary criterion:" in prompt
    assert "weirdest coherent" in prompt
    # Joke JSON example — criteria name and evidence
    assert '"name": "Scene serves the declared primary criterion"' in prompt
    assert '"evidence": "The final scene preserves the intended comic engine from opening through button."' in prompt
    # Joke task verdict example
    assert '"reviewer_verdict": "Pass. The written scene beats align with the planned canvas and primary criterion."' in prompt
    # Joke sense check verdict example
    assert '"verdict": "Confirmed. The final scene still serves the declared primary criterion."' in prompt
    # Joke review_verdict example
    assert '"review_verdict": "approved"' in prompt
    # Should not contain doc-specific strings
    assert "Approved plan:" not in prompt
    assert "Output document content:" not in prompt


def test_review_doc_and_joke_json_examples_differ(tmp_path: Path) -> None:
    """The JSON examples embedded in _review_doc_prompt and _review_joke_prompt differ in criteria name, evidence, and verdict phrasing."""
    doc_root = tmp_path / "doc"
    doc_root.mkdir()
    plan_dir, state = _scaffold_doc_review(doc_root)

    doc_prompt = _review_doc_prompt(
        state,
        plan_dir,
        review_intro="Review the document critically against user intent and observable success criteria.",
        criteria_guidance="Judge against the success criteria, not plan elegance.",
        task_guidance="Review each task by cross-referencing the executor's per-task `sections_written` against the output document.",
        sense_check_guidance="Review every sense check explicitly.",
    )

    joke_root = tmp_path / "joke"
    joke_root.mkdir()
    plan_dir2, state2 = _scaffold_joke_review(joke_root)
    joke_prompt = _review_joke_prompt(
        state2,
        plan_dir2,
        review_intro="Review the scene critically against the brief, the declared primary criterion, and the approved scene canvas.",
        criteria_guidance="Judge first against the declared primary criterion, then against the remaining success criteria and scene-canvas commitments.",
        task_guidance="Review each task by cross-referencing the executor's per-task `sections_written` against the output scene prose.",
        sense_check_guidance="Review every sense check explicitly.",
    )

    # ---- Criteria name differs ----
    doc_criterion = '"name": "Document covers all planned sections"'
    joke_criterion = '"name": "Scene serves the declared primary criterion"'
    assert doc_criterion in doc_prompt
    assert joke_criterion not in doc_prompt
    assert joke_criterion in joke_prompt
    assert doc_criterion not in joke_prompt

    # ---- Criteria evidence differs ----
    doc_evidence = '"evidence": "All 5 planned sections are present and non-empty."'
    joke_evidence = '"evidence": "The final scene preserves the intended comic engine from opening through button."'
    assert doc_evidence in doc_prompt
    assert joke_evidence not in doc_prompt
    assert joke_evidence in joke_prompt
    assert doc_evidence not in joke_prompt

    # ---- Task verdict example differs ----
    doc_verdict = '"reviewer_verdict": "Pass. Introduction section covers scope and audience as planned."'
    joke_verdict = '"reviewer_verdict": "Pass. The written scene beats align with the planned canvas and primary criterion."'
    assert doc_verdict in doc_prompt
    assert joke_verdict not in doc_prompt
    assert joke_verdict in joke_prompt
    assert doc_verdict not in joke_prompt

    # ---- Sense check verdict example differs ----
    doc_sc_verdict = '"verdict": "Confirmed. The introduction references prior art as required."'
    joke_sc_verdict = '"verdict": "Confirmed. The final scene still serves the declared primary criterion."'
    assert doc_sc_verdict in doc_prompt
    assert joke_sc_verdict not in doc_prompt
    assert joke_sc_verdict in joke_prompt
    assert doc_sc_verdict not in joke_prompt

    # ---- Summary example differs ----
    assert '"summary": "Approved. All must criteria pass."' in doc_prompt
    assert '"summary": "Approved. The scene meets the brief and the primary criterion."' in joke_prompt


def test_finalize_prompt_has_harness_verification_framing(tmp_path: Path) -> None:
    """T1: finalize.py prompt must contain harness-owns-verification framing and
    must NOT contain banned loop phrases (re-run until, never stop, until they pass)."""
    plan_dir, state = _scaffold(tmp_path)
    prompt = create_claude_prompt("finalize", state, plan_dir, root=tmp_path)

    # New framing must be present
    assert "harness owns test verification" in prompt.lower() or (
        "do NOT author a run-until-pass task" in prompt
        and "The harness will run the authoritative post-execute suite" in prompt
    )
    assert "introduce no new failures vs the recorded baseline" in prompt

    # Banned phrases must be absent
    banned = ["re-run until", "never stop", "until they pass"]
    for phrase in banned:
        assert phrase not in prompt, f"Banned phrase '{phrase}' found in finalize prompt"


def test_execute_prompt_has_harness_framing_no_loop(tmp_path: Path) -> None:
    """T1: execute.py:94 single-execute prompt must contain authoritative-harness
    framing and must NOT contain the old re-run-until-pass / never-stop phrasing."""
    plan_dir, state = _scaffold(tmp_path)
    prompt = _execute_prompt(state, plan_dir)

    # New framing must be present
    assert (
        "A mechanical post-execute suite run by the harness — not you — is the authoritative regression check"
        in prompt
    )
    assert "Run tests for your own fix loop if needed, then stop; do not loop the suite to make pre-existing failures pass" in prompt

    # Banned phrases must be absent
    banned = ["re-run until", "never stop", "until they pass"]
    for phrase in banned:
        assert phrase not in prompt, f"Banned phrase '{phrase}' found in execute single prompt"


def test_execute_batch_prompt_has_harness_framing_no_loop(tmp_path: Path) -> None:
    """T1: execute.py:596 batch prompt must contain authoritative-harness framing
    and must NOT contain the old re-run-until-pass / never-stop phrasing."""
    plan_dir, state = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "finalize.json",
        _build_mock_payload(
            "finalize",
            state,
            plan_dir,
            tasks=[
                {
                    "id": "T1",
                    "description": "First task",
                    "depends_on": [],
                    "status": "pending",
                    "executor_notes": "",
                    "files_changed": [],
                    "commands_run": [],
                    "evidence_files": [],
                    "reviewer_verdict": "",
                },
            ],
            sense_checks=[
                {"id": "SC1", "task_id": "T1", "question": "Done?", "executor_note": "", "verdict": ""},
            ],
        ),
    )
    prompt = _execute_batch_prompt(state, plan_dir, ["T1"], set())

    # New framing must be present
    assert (
        "A mechanical post-execute suite run by the harness — not you — is the authoritative regression check"
        in prompt
    )
    assert "Run tests for your own fix loop if needed, then stop; do not loop the suite to make pre-existing failures pass" in prompt

    # Banned phrases must be absent
    banned = ["re-run until", "never stop", "until they pass"]
    for phrase in banned:
        assert phrase not in prompt, f"Banned phrase '{phrase}' found in execute batch prompt"


def test_plan_template_has_no_megaplan_path_references() -> None:
    """PLAN_TEMPLATE must use neutral example paths (e.g. src/), not megaplan/."""
    from megaplan.prompts.planning import PLAN_TEMPLATE

    lines = PLAN_TEMPLATE.split("\n")
    offending = [
        f"  line {i + 1}: {line.strip()}"
        for i, line in enumerate(lines)
        if "megaplan/" in line
    ]
    assert not offending, (
        f"PLAN_TEMPLATE contains {len(offending)} megaplan/ path reference(s):\n"
        + "\n".join(offending)
    )
