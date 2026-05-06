"""Direct tests for megaplan.workers."""

from __future__ import annotations

import json
import subprocess
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from megaplan.evaluation import validate_plan_structure
from megaplan._core import PHASE_RUNTIME_POLICY
from megaplan.types import CliError
from megaplan.workers import (
    _build_mock_payload,
    _codex_child_env,
    _codex_timeout_for_step,
    _external_worker_env,
    _merge_partial_output,
    WorkerResult,
    extract_session_id,
    parse_claude_envelope,
    parse_json_file,
    _recover_codex_payload,
    resolve_agent_mode,
    session_key_for,
    update_session_state,
    validate_payload,
)


def _make_args(**overrides: object) -> Namespace:
    data = {
        "agent": None,
        "ephemeral": False,
        "fresh": False,
        "persist": False,
        "confirm_self_review": False,
        "hermes": None,
        "phase_model": [],
    }
    data.update(overrides)
    return Namespace(**data)


def test_parse_claude_envelope_prefers_structured_output() -> None:
    raw = json.dumps({"structured_output": {"plan": "x"}, "total_cost_usd": 0.01})
    envelope, payload = parse_claude_envelope(raw)
    assert envelope["total_cost_usd"] == 0.01
    assert payload == {"plan": "x"}


def test_external_worker_env_strips_progress_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGAPLAN_PROGRESS_ENABLED", "1")
    monkeypatch.setenv("MEGAPLAN_PROGRESS_EPIC_ID", "epic-1")
    monkeypatch.setenv("CODEX_THREAD_ID", "outer-thread")
    monkeypatch.setenv("CODEX_CI", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    claude_env = _external_worker_env()
    codex_env = _codex_child_env()

    assert "MEGAPLAN_PROGRESS_ENABLED" not in claude_env
    assert "MEGAPLAN_PROGRESS_EPIC_ID" not in claude_env
    assert claude_env["OPENAI_API_KEY"] == "secret"
    assert "MEGAPLAN_PROGRESS_ENABLED" not in codex_env
    assert "MEGAPLAN_PROGRESS_EPIC_ID" not in codex_env
    assert "CODEX_THREAD_ID" not in codex_env
    assert "CODEX_CI" not in codex_env
    assert codex_env["OPENAI_API_KEY"] == "secret"


def test_parse_claude_envelope_rejects_invalid_json() -> None:
    with pytest.raises(CliError, match="valid JSON"):
        parse_claude_envelope("not json")


def test_parse_claude_envelope_classifies_not_logged_in_as_auth_error() -> None:
    raw = json.dumps({"is_error": True, "result": "Not logged in · Please run /login"})
    with pytest.raises(CliError) as exc_info:
        parse_claude_envelope(raw)
    assert exc_info.value.code == "auth_error"
    assert "not logged in" in exc_info.value.message.lower()


@pytest.mark.parametrize(
    ("step", "payload"),
    [
        ("plan", {"plan": "x", "questions": [], "success_criteria": [{"criterion": "test", "priority": "must"}], "assumptions": []}),
        (
            "prep",
            {
                "skip": False,
                "task_summary": "Prepare context before planning.",
                "key_evidence": [],
                "relevant_code": [],
                "test_expectations": [],
                "constraints": [],
                "suggested_approach": "Use the brief as primary context.",
            },
        ),
        (
            "revise",
            {
                "plan": "x",
                "changes_summary": "y",
                "flags_addressed": [],
                "assumptions": [],
                "success_criteria": [],
                "questions": [],
            },
        ),
        (
            "gate",
            {
                "recommendation": "PROCEED",
                "rationale": "ok",
                "signals_assessment": "ok",
                "warnings": [],
                "settled_decisions": [],
                "flag_resolutions": [],
                "accepted_tradeoffs": [],
            },
        ),
        (
            "finalize",
            {
                "tasks": [
                    {
                        "id": "T1",
                        "description": "Do work",
                        "depends_on": [],
                        "status": "pending",
                        "executor_notes": "",
                        "files_changed": [],
                        "commands_run": [],
                        "evidence_files": [],
                        "reviewer_verdict": "",
                    }
                ],
                "watch_items": [],
                "sense_checks": [
                    {
                        "id": "SC1",
                        "task_id": "T1",
                        "question": "Did it work?",
                        "executor_note": "",
                        "verdict": "",
                    }
                ],
                "user_actions": [],
                "meta_commentary": "ok",
                "validation": {
                    "plan_steps_covered": [{"plan_step_summary": "Do work", "finalize_item_ids": ["T1"]}],
                    "orphan_tasks": [],
                    "completeness_notes": "All covered.",
                    "coverage_complete": True,
                },
            },
        ),
        (
            "execute",
            {
                "output": "done",
                "files_changed": [],
                "commands_run": [],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Implemented.",
                        "files_changed": ["megaplan/workers.py"],
                        "commands_run": ["pytest tests/test_workers.py"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed."}
                ],
            },
        ),
        (
            "review",
            {
                "review_verdict": "approved",
                "checks": [],
                "pre_check_flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
                "criteria": [],
                "issues": [],
                "rework_items": [],
                "summary": "ok",
                "task_verdicts": [
                    {
                        "task_id": "T1",
                        "reviewer_verdict": "Pass",
                        "evidence_files": ["megaplan/workers.py"],
                    }
                ],
                "sense_check_verdicts": [{"sense_check_id": "SC1", "verdict": "Confirmed"}],
            },
        ),
    ],
)
def test_validate_payload_accepts_current_worker_steps(step: str, payload: dict[str, object]) -> None:
    validate_payload(step, payload)


def test_validate_payload_rejects_missing_gate_key() -> None:
    with pytest.raises(CliError, match="signals_assessment"):
        validate_payload(
            "gate",
            {
                "recommendation": "PROCEED",
                "rationale": "x",
                "warnings": [],
                "settled_decisions": [],
                "flag_resolutions": [],
                "accepted_tradeoffs": [],
            },
        )


def test_validate_payload_accepts_review_without_parallel_check_bookkeeping() -> None:
    validate_payload(
        "review",
        {
            "review_verdict": "approved",
            "criteria": [],
            "issues": [],
            "rework_items": [],
            "summary": "ok",
            "task_verdicts": [],
            "sense_check_verdicts": [],
        },
    )


def test_validate_payload_accepts_execute_batch_shape() -> None:
    validate_payload(
        "execute",
        {
            "task_updates": [
                {
                    "task_id": "T8",
                    "status": "done",
                    "executor_notes": "Implemented batch task.",
                    "files_changed": ["reigh-worker/tests/test_preview_harness.py"],
                    "commands_run": ["pytest tests/test_preview_harness.py -v"],
                }
            ],
            "sense_check_acknowledgments": [
                {
                    "sense_check_id": "SC8",
                    "executor_note": "Confirmed batch verification.",
                }
            ],
        },
    )


def test_session_key_for_matches_new_roles() -> None:
    assert session_key_for("plan", "claude") == "claude_planner"
    assert session_key_for("revise", "codex") == "codex_planner"
    assert session_key_for("critique", "codex") == "codex_critic"
    assert session_key_for("gate", "claude") == "claude_gatekeeper"
    assert session_key_for("execute", "claude") == "claude_executor"


def test_update_session_state_preserves_created_at() -> None:
    result = update_session_state(
        "gate",
        "claude",
        "session-123",
        mode="persistent",
        refreshed=False,
        existing_sessions={"claude_gatekeeper": {"created_at": "2026-01-01T00:00:00Z"}},
    )
    assert result is not None
    key, entry = result
    assert key == "claude_gatekeeper"
    assert entry["created_at"] == "2026-01-01T00:00:00Z"


def test_extract_session_id_supports_jsonl() -> None:
    raw = '{"type":"thread.started","thread_id":"abc-123"}\n'
    assert extract_session_id(raw) == "abc-123"


def test_parse_json_file_reads_object(tmp_path: Path) -> None:
    path = tmp_path / "out.json"
    path.write_text(json.dumps({"ok": True}), encoding="utf-8")
    assert parse_json_file(path) == {"ok": True}


def test_recover_codex_payload_handles_stderr_bleed_in_output_file(tmp_path: Path) -> None:
    """Codex sometimes appends stderr/log noise to the -o output file after the JSON.

    parse_json_file() uses strict json.loads() and rejects trailing junk. The recovery
    path must also feed the file contents through _extract_json_candidates_from_raw
    so the leading valid JSON object can still be salvaged.
    """
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "critique_output.json"
    valid_payload = {
        "checks": [
            {
                "id": "check-1",
                "question": "Is the plan grounded in the repository?",
                "findings": [
                    {"detail": "Plan references the actual files.", "flagged": False}
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    polluted = (
        json.dumps(valid_payload)
        + "\n2026-04-27T00:16:08.726626Z ERROR codex_core::session: "
        + "failed to record rollout items: thread x not found\n"
        + "tokens used\n674,216\n"
    )
    output_path.write_text(polluted, encoding="utf-8")

    recovered = _recover_codex_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )
    assert recovered == valid_payload


def test_recover_codex_payload_prefers_valid_output_file_over_raw_transcript(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "critique_output.json"
    file_payload = {
        "checks": [],
        "flags": [
            {
                "id": "FLAG-001",
                "concern": "The plan should revise the RunPod disk defaults.",
                "evidence": "runpod-lifecycle config still contains stale defaults.",
                "severity": "medium",
                "category": "correctness",
            }
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    raw_payload = {
        "checks": [
            {
                "id": "disk-defaults",
                "question": "Are disk defaults aligned?",
                "findings": [
                    {
                        "detail": "Intermediate transcript JSON should not outrank the output file.",
                        "flagged": True,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    output_path.write_text(json.dumps(file_payload), encoding="utf-8")

    recovered = _recover_codex_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw=f"thinking...\n{json.dumps(raw_payload)}\n",
    )

    assert recovered == file_payload


def test_recover_codex_payload_prefers_completed_critique_template_over_schema_summary(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"
    summary_payload = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the plan address the brief?",
                "findings": [
                    {
                        "detail": "Wrote the critique output file with the detailed findings.",
                        "flagged": False,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    completed_payload = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the plan address the brief?",
                "findings": [
                    {
                        "detail": "Found one concrete issue in the issue-hints lens.",
                        "flagged": True,
                    }
                ],
            },
            {
                "id": "correctness",
                "question": "Is the plan technically correct?",
                "findings": [
                    {
                        "detail": "Found one concrete issue in the correctness lens.",
                        "flagged": True,
                    }
                ],
            },
            {
                "id": "scope",
                "question": "Is the plan scoped correctly?",
                "findings": [
                    {
                        "detail": "Found one concrete issue in the scope lens.",
                        "flagged": True,
                    }
                ],
            },
        ],
        "flags": [
            {
                "id": "FLAG-001",
                "concern": "Detailed critique should win over a schema-summary payload.",
                "evidence": "The side-effect template contains more completed checks.",
                "category": "correctness",
                "severity_hint": "likely-significant",
            }
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    output_path.write_text(json.dumps(summary_payload), encoding="utf-8")
    (plan_dir / "critique_output.json").write_text(json.dumps(completed_payload), encoding="utf-8")

    recovered = _recover_codex_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == completed_payload


def test_recover_codex_payload_keeps_meaningful_critique_when_template_is_empty(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"
    meaningful_payload = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the plan address the brief?",
                "findings": [
                    {
                        "detail": "The output file contains the only meaningful critique finding.",
                        "flagged": True,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    empty_template = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the plan address the brief?",
                "findings": [],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    output_path.write_text(json.dumps(meaningful_payload), encoding="utf-8")
    (plan_dir / "critique_output.json").write_text(json.dumps(empty_template), encoding="utf-8")

    recovered = _recover_codex_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == meaningful_payload


def test_recover_codex_payload_normalizes_execute_batch_aliases(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "execute_output.json"
    output_path.write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "id": "T3",
                        "status": "completed",
                        "executor_notes": "Generated the template index.",
                        "files_changed": ["vibecomfy/template_index.json"],
                        "commands_run": ["python -m json.tool template_index.json"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {
                        "id": "SC3",
                        "executor_note": "Template index count is 51.",
                        "verdict": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    recovered = _recover_codex_payload(
        "execute",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered is not None
    assert recovered["task_updates"][0]["task_id"] == "T3"
    assert recovered["task_updates"][0]["status"] == "done"
    assert recovered["sense_check_acknowledgments"][0]["sense_check_id"] == "SC3"


def test_recover_codex_payload_accepts_review_without_checks_and_trailing_telemetry(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "review_output.json"
    valid_payload = {
        "review_verdict": "approved",
        "criteria": [
            {
                "name": "Regression coverage exists",
                "priority": "must",
                "pass": "pass",
                "evidence": "Focused worker tests cover review JSON recovery.",
            }
        ],
        "issues": [],
        "rework_items": [],
        "summary": "Approved. All must criteria pass.",
        "task_verdicts": [
            {
                "task_id": "T1",
                "reviewer_verdict": "Pass. The implementation matches the task.",
                "evidence_files": ["megaplan/workers.py"],
            }
        ],
        "sense_check_verdicts": [
            {"sense_check_id": "SC1", "verdict": "Confirmed. Review recovery accepts the newer shape."}
        ],
    }
    output_path.write_text(
        json.dumps(valid_payload)
        + "\n2026-05-03T12:00:00Z INFO codex telemetry: tokens used 1234\n",
        encoding="utf-8",
    )

    recovered = _recover_codex_payload(
        "review",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == {
        **valid_payload,
        "checks": [],
        "pre_check_flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }


def test_recover_codex_payload_reports_missing_required_keys_for_json_object(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "plan_output.json"
    output_path.write_text(json.dumps({"plan": "# Plan\nDo it."}), encoding="utf-8")

    with pytest.raises(CliError) as exc_info:
        _recover_codex_payload(
            "plan",
            plan_dir=plan_dir,
            output_path=output_path,
            raw="",
        )

    assert "plan output missing required keys" in exc_info.value.message
    assert "not valid JSON" not in exc_info.value.message


def test_resolve_agent_mode_uses_configured_fallback() -> None:
    with patch("megaplan.workers.shutil.which", side_effect=lambda name: None if name == "claude" else "/usr/bin/codex"):
        with patch("megaplan.workers.detect_available_agents", return_value=["codex"]):
            with patch("megaplan.workers.load_config", return_value={"agents": {"plan": "claude"}}):
                args = _make_args()
                agent, mode, refreshed, model = resolve_agent_mode("plan", args)
    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is False
    assert args._agent_fallback["requested"] == "claude"


def test_resolve_agent_mode_for_review_claude_defaults_to_fresh() -> None:
    with patch("megaplan.workers.shutil.which", return_value="/usr/bin/claude"):
        agent, mode, refreshed, model = resolve_agent_mode("review", _make_args(agent="claude"))
    assert agent == "claude"
    assert mode == "persistent"
    assert refreshed is True


# ---------------------------------------------------------------------------
# Mock worker tests
# ---------------------------------------------------------------------------


def _mock_state(tmp_path: Path, *, iteration: int = 1) -> tuple[Path, dict]:
    import textwrap
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    state = {
        "name": "test-plan",
        "idea": "test the mock workers",
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
            {"version": iteration, "file": f"plan_v{iteration}.md", "hash": "sha256:test", "timestamp": "2026-03-20T00:00:00Z"}
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
    (plan_dir / f"plan_v{iteration}.md").write_text("# Plan\nDo it.\n", encoding="utf-8")
    (plan_dir / f"plan_v{iteration}.meta.json").write_text(
        json.dumps({"version": iteration, "timestamp": "2026-03-20T00:00:00Z", "hash": "sha256:test", "success_criteria": [{"criterion": "criterion", "priority": "must"}], "questions": [], "assumptions": []}),
        encoding="utf-8",
    )
    (plan_dir / "faults.json").write_text(json.dumps({"flags": []}), encoding="utf-8")
    (plan_dir / "gate.json").write_text(
        json.dumps(
            {
                "passed": True,
                "recommendation": "PROCEED",
                "rationale": "ok",
                "signals_assessment": "ok",
                "warnings": [],
                "settled_decisions": [],
                "criteria_check": {},
                "preflight_results": {},
                "unresolved_flags": [],
                "override_forced": False,
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "execution.json").write_text(
        json.dumps(_build_mock_payload("execute", state, plan_dir, output="done")),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            _build_mock_payload(
                "finalize",
                state,
                plan_dir,
                watch_items=["Watch repository assumptions."],
                tasks=[
                    {
                        "id": "T1",
                        "description": "Do work",
                        "depends_on": [],
                        "status": "pending",
                        "executor_notes": "",
                        "files_changed": [],
                        "commands_run": [],
                        "evidence_files": [],
                        "reviewer_verdict": "",
                    },
                    {
                        "id": "T2",
                        "description": "Verify work",
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
                    {"id": "SC1", "task_id": "T1", "question": "Did it work?", "executor_note": "", "verdict": ""},
                    {"id": "SC2", "task_id": "T2", "question": "Was it verified?", "executor_note": "", "verdict": ""},
                ],
                meta_commentary="Mock finalize output.",
            )
        ),
        encoding="utf-8",
    )
    return plan_dir, state


def test_mock_plan_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("plan", state, plan_dir)
    assert "plan" in result.payload
    assert "questions" in result.payload
    assert "success_criteria" in result.payload
    assert "assumptions" in result.payload
    assert validate_plan_structure(result.payload["plan"]) == []


def test_mock_prep_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("prep", state, plan_dir)
    assert "task_summary" in result.payload
    assert "key_evidence" in result.payload
    assert "relevant_code" in result.payload
    assert "test_expectations" in result.payload
    assert "constraints" in result.payload
    assert "suggested_approach" in result.payload


def test_build_mock_payload_execute_returns_complete_payload(tmp_path: Path) -> None:
    plan_dir, state = _mock_state(tmp_path)
    payload = _build_mock_payload(
        "execute",
        state,
        plan_dir,
        task_updates=[
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Verified the targeted execute payload override keeps the schema intact.",
                "files_changed": ["megaplan/workers.py"],
                "commands_run": ["pytest tests/test_workers.py -k build_mock_payload"],
            }
        ],
    )

    assert payload["output"] == "Mock execution completed successfully."
    assert payload["task_updates"][0]["task_id"] == "T1"
    assert len(payload["task_updates"]) == 1
    assert payload["sense_check_acknowledgments"]


def test_build_mock_payload_execute_scopes_batch_from_prompt_override(tmp_path: Path) -> None:
    plan_dir, state = _mock_state(tmp_path)
    payload = _build_mock_payload(
        "execute",
        state,
        plan_dir,
        prompt_override="Only produce task_updates for these tasks: [T2]",
    )

    assert [item["task_id"] for item in payload["task_updates"]] == ["T2"]
    assert [item["sense_check_id"] for item in payload["sense_check_acknowledgments"]] == ["SC2"]


def test_mock_critique_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("critique", state, plan_dir)
    assert "flags" in result.payload
    assert isinstance(result.payload["flags"], list)


def test_mock_revise_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("revise", state, plan_dir)
    assert "plan" in result.payload
    assert "changes_summary" in result.payload
    assert "flags_addressed" in result.payload
    assert "assumptions" in result.payload
    assert "success_criteria" in result.payload
    assert "questions" in result.payload
    assert validate_plan_structure(result.payload["plan"]) == []


def test_mock_gate_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("gate", state, plan_dir)
    assert "recommendation" in result.payload
    assert result.payload["recommendation"] in {"PROCEED", "ITERATE", "ESCALATE"}
    assert "rationale" in result.payload
    assert "signals_assessment" in result.payload
    assert "warnings" in result.payload
    assert "settled_decisions" in result.payload
    assert "flag_resolutions" in result.payload
    assert "accepted_tradeoffs" in result.payload


def test_mock_finalize_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("finalize", state, plan_dir)
    validate_payload("finalize", result.payload)
    assert "tasks" in result.payload
    assert "watch_items" in result.payload
    assert "sense_checks" in result.payload
    assert "meta_commentary" in result.payload
    assert "validation" in result.payload
    assert "baseline_test_failures" not in result.payload
    assert "baseline_test_command" not in result.payload
    assert "baseline_test_note" not in result.payload
    assert isinstance(result.payload["tasks"], list)
    assert isinstance(result.payload["watch_items"], list)
    assert result.payload["tasks"][0]["status"] == "pending"
    assert result.payload["sense_checks"][0]["task_id"] == "T1"
    validation = result.payload["validation"]
    assert "plan_steps_covered" in validation
    assert "orphan_tasks" in validation
    assert "coverage_complete" in validation
    assert isinstance(validation["plan_steps_covered"], list)


def test_mock_execute_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("execute", state, plan_dir)
    assert "output" in result.payload
    assert "files_changed" in result.payload
    assert "commands_run" in result.payload
    assert "deviations" in result.payload
    assert "task_updates" in result.payload
    assert "sense_check_acknowledgments" in result.payload
    assert result.payload["task_updates"][0]["task_id"] == "T1"


def test_mock_review_returns_valid_payload(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    result = mock_worker_output("review", state, plan_dir)
    assert result.payload["review_verdict"] == "approved"
    assert "checks" in result.payload
    assert "pre_check_flags" in result.payload
    assert "verified_flag_ids" in result.payload
    assert "disputed_flag_ids" in result.payload
    assert "criteria" in result.payload
    assert "issues" in result.payload
    assert "rework_items" in result.payload
    assert "summary" in result.payload
    assert "task_verdicts" in result.payload
    assert "sense_check_verdicts" in result.payload
    assert result.payload["rework_items"] == []


def test_mock_unsupported_step_raises(tmp_path: Path) -> None:
    from megaplan.workers import mock_worker_output
    plan_dir, state = _mock_state(tmp_path)
    with pytest.raises(CliError, match="does not support"):
        mock_worker_output("nonexistent", state, plan_dir)


# ---------------------------------------------------------------------------
# Session key mapping tests
# ---------------------------------------------------------------------------


def test_session_key_for_all_steps() -> None:
    assert session_key_for("plan", "claude") == "claude_planner"
    assert session_key_for("revise", "claude") == "claude_planner"
    assert session_key_for("critique", "claude") == "claude_critic"
    assert session_key_for("gate", "claude") == "claude_gatekeeper"
    assert session_key_for("execute", "claude") == "claude_executor"
    assert session_key_for("review", "claude") == "claude_reviewer"
    assert session_key_for("plan", "codex") == "codex_planner"
    assert session_key_for("revise", "codex") == "codex_planner"
    assert session_key_for("critique", "codex") == "codex_critic"
    assert session_key_for("gate", "codex") == "codex_gatekeeper"
    assert session_key_for("execute", "codex") == "codex_executor"
    assert session_key_for("review", "codex") == "codex_reviewer"


def test_session_key_for_unknown_step_uses_step_name() -> None:
    assert session_key_for("custom", "claude") == "claude_custom"


# ---------------------------------------------------------------------------
# Schema filename mapping tests
# ---------------------------------------------------------------------------


def test_step_schema_filenames_cover_all_steps() -> None:
    from megaplan.workers import STEP_SCHEMA_FILENAMES
    required_steps = {"plan", "prep", "revise", "critique", "gate", "finalize", "execute", "review"}
    assert required_steps.issubset(set(STEP_SCHEMA_FILENAMES.keys()))


def test_step_schema_filenames_reference_existing_schemas() -> None:
    from megaplan.workers import STEP_SCHEMA_FILENAMES
    from megaplan.schemas import SCHEMAS
    for step, filename in STEP_SCHEMA_FILENAMES.items():
        assert filename in SCHEMAS, f"Step '{step}' references non-existent schema '{filename}'"


# ---------------------------------------------------------------------------
# resolve_agent_mode additional tests
# ---------------------------------------------------------------------------


def test_resolve_agent_mode_cli_flag_override() -> None:
    with patch("megaplan.workers.shutil.which", return_value="/usr/bin/codex"):
        agent, mode, refreshed, model = resolve_agent_mode("plan", _make_args(agent="codex"))
    assert agent == "codex"


def test_resolve_agent_mode_config_override() -> None:
    with patch("megaplan.workers.shutil.which", return_value="/usr/bin/codex"):
        with patch("megaplan.workers.load_config", return_value={"agents": {"plan": "codex"}}):
            agent, mode, refreshed, model = resolve_agent_mode("plan", _make_args())
    assert agent == "codex"


def test_resolve_agent_mode_explicit_missing_raises() -> None:
    with patch("megaplan.workers.shutil.which", return_value=None):
        with pytest.raises(CliError, match="not found"):
            resolve_agent_mode("plan", _make_args(agent="nosuchagent"))


def test_resolve_agent_mode_no_agents_raises() -> None:
    with patch("megaplan.workers.shutil.which", return_value=None):
        with patch("megaplan.workers.load_config", return_value={}):
            with patch("megaplan.workers.detect_available_agents", return_value=[]):
                with pytest.raises(CliError, match="No supported agents"):
                    resolve_agent_mode("plan", _make_args())


def test_resolve_agent_mode_conflicting_flags_raises() -> None:
    with patch("megaplan.workers.shutil.which", return_value="/usr/bin/claude"):
        with pytest.raises(CliError, match="Cannot combine"):
            resolve_agent_mode("plan", _make_args(fresh=True, ephemeral=True))


def test_resolve_agent_mode_ephemeral_mode() -> None:
    with patch("megaplan.workers.shutil.which", return_value="/usr/bin/claude"):
        agent, mode, refreshed, model = resolve_agent_mode("plan", _make_args(agent="claude", ephemeral=True))
    assert mode == "ephemeral"
    assert refreshed is True


# ---------------------------------------------------------------------------
# update_session_state tests
# ---------------------------------------------------------------------------


def test_update_session_state_returns_none_for_no_session_id() -> None:
    result = update_session_state("plan", "claude", None, mode="persistent", refreshed=False)
    assert result is None


def test_update_session_state_creates_new_entry() -> None:
    result = update_session_state("plan", "claude", "sess-abc", mode="persistent", refreshed=False)
    assert result is not None
    key, entry = result
    assert key == "claude_planner"
    assert entry["id"] == "sess-abc"
    assert entry["mode"] == "persistent"


# ---------------------------------------------------------------------------
# validate_payload edge cases
# ---------------------------------------------------------------------------


def test_validate_payload_critique_requires_flags() -> None:
    with pytest.raises(CliError, match="flags"):
        validate_payload("critique", {"verified_flag_ids": [], "disputed_flag_ids": []})


def test_validate_payload_execute_requires_output() -> None:
    with pytest.raises(CliError, match="output"):
        validate_payload(
            "execute",
            {"files_changed": [], "commands_run": [], "deviations": [], "sense_check_acknowledgments": []},
        )


def test_validate_payload_review_requires_criteria() -> None:
    with pytest.raises(CliError, match="criteria"):
        validate_payload(
            "review",
            {
                "review_verdict": "approved",
                "checks": [],
                "pre_check_flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
                "issues": [],
                "rework_items": [],
                "summary": "ok",
                "task_verdicts": [],
                "sense_check_verdicts": [],
            },
        )


# ---------------------------------------------------------------------------
# Subprocess-mocked tests for run_claude_step and run_codex_step
# ---------------------------------------------------------------------------


def test_run_claude_step_parses_structured_output(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    claude_output = json.dumps({
        "structured_output": plan_payload,
        "total_cost_usd": 0.05,
        "session_id": "sess-abc",
    })
    fake_result = CommandResult(
        command=["claude"],
        cwd=tmp_path,
        returncode=0,
        stdout=claude_output,
        stderr="",
        duration_ms=500,
    )
    with patch("megaplan.workers.run_command", return_value=fake_result):
        result = run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True)
    assert result.payload == plan_payload
    assert result.cost_usd == 0.05
    assert result.session_id == "sess-abc"
    assert result.duration_ms == 500


def test_run_claude_step_passes_effort_flag(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    claude_output = json.dumps({
        "structured_output": plan_payload,
        "total_cost_usd": 0.0,
        "session_id": "sess-effort",
    })
    fake_result = CommandResult(
        command=["claude"],
        cwd=tmp_path,
        returncode=0,
        stdout=claude_output,
        stderr="",
        duration_ms=10,
    )
    with patch("megaplan.workers.run_command", return_value=fake_result) as run_command:
        run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True, effort="low")
    invoked_cmd = run_command.call_args.args[0]
    assert "--effort" in invoked_cmd
    assert invoked_cmd[invoked_cmd.index("--effort") + 1] == "low"


def test_run_claude_step_rejects_invalid_effort(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    with pytest.raises(CliError, match="Unsupported claude effort level"):
        run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True, effort="bogus")


def test_run_codex_step_passes_effort_flag(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    captured: dict[str, list[str]] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=10,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True, effort="low",
        )
    invoked_cmd = captured["command"]
    assert "model_reasoning_effort=low" in invoked_cmd
    idx = invoked_cmd.index("model_reasoning_effort=low")
    assert invoked_cmd[idx - 1] == "-c"


def test_run_codex_step_rejects_invalid_effort(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    with pytest.raises(CliError, match="Unsupported codex effort level"):
        run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True, effort="bogus",
        )


def test_run_claude_step_uses_prompt_override_without_builder(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    fake_result = CommandResult(
        command=["claude"],
        cwd=tmp_path,
        returncode=0,
        stdout=json.dumps({"structured_output": {"plan": "x", "questions": [], "success_criteria": [{"criterion": "test", "priority": "must"}], "assumptions": []}}),
        stderr="",
        duration_ms=10,
    )
    with patch("megaplan.workers.create_claude_prompt", side_effect=AssertionError("builder should not run")):
        with patch("megaplan.workers.run_command", return_value=fake_result) as run_command:
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True, prompt_override="custom prompt")
    assert run_command.call_args.kwargs["stdin_text"] == "custom prompt"


def test_run_claude_step_raises_on_invalid_payload(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    # Missing required keys for "plan" step
    claude_output = json.dumps({
        "structured_output": {"plan": "x"},
        "total_cost_usd": 0.0,
    })
    fake_result = CommandResult(
        command=["claude"],
        cwd=tmp_path,
        returncode=0,
        stdout=claude_output,
        stderr="",
        duration_ms=100,
    )
    with patch("megaplan.workers.run_command", return_value=fake_result):
        with pytest.raises(CliError, match="missing required keys"):
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True)


def test_run_claude_step_attaches_session_id_on_timeout(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][session_key_for("plan", "claude")] = {
        "id": "claude-session",
        "mode": "persistent",
        "created_at": "2026-03-20T00:00:00Z",
        "last_used_at": "2026-03-20T00:00:00Z",
        "refreshed": False,
    }

    timeout_error = CliError("worker_timeout", "Claude timed out", extra={"raw_output": "partial"})
    with patch("megaplan.workers.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=False)

    assert exc_info.value.extra["session_id"] == "claude-session"


def test_run_codex_step_uses_prompt_override_without_builder(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    output_path = tmp_path / "codex-output.json"

    def fake_named_tempfile(*args: object, **kwargs: object):
        class _TempFile:
            name = str(output_path)

            def close(self) -> None:
                return None

        return _TempFile()

    def fake_run_command(*args: object, **kwargs: object) -> CommandResult:
        output_path.write_text(
            json.dumps({"plan": "# Plan", "questions": [], "success_criteria": [{"criterion": "test", "priority": "must"}], "assumptions": []}),
            encoding="utf-8",
        )
        return CommandResult(
            command=["codex"],
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=10,
        )

    with patch("megaplan.workers.create_codex_prompt", side_effect=AssertionError("builder should not run")):
        with patch("megaplan.workers.tempfile.NamedTemporaryFile", side_effect=fake_named_tempfile):
            with patch("megaplan.workers.run_command", side_effect=fake_run_command):
                run_codex_step(
                    "plan",
                    state,
                    plan_dir,
                    root=tmp_path,
                    persistent=False,
                    prompt_override="custom prompt",
                )


def test_run_step_with_worker_passes_prompt_override(tmp_path: Path) -> None:
    from megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    payload = {"output": "done", "files_changed": [], "commands_run": [], "deviations": [], "task_updates": [], "sense_check_acknowledgments": []}
    with patch(
        "megaplan.workers.run_codex_step",
        return_value=type("Result", (), {"payload": payload, "raw_output": "", "duration_ms": 1, "cost_usd": 0.0, "session_id": "sess", "trace_output": None})(),
    ) as run_codex:
        run_step_with_worker(
            "execute",
            state,
            plan_dir,
            _make_args(agent="codex"),
            root=tmp_path,
            resolved=("codex", "persistent", False, None),
            prompt_override="custom execute prompt",
        )
    assert run_codex.call_args.kwargs["prompt_override"] == "custom execute prompt"


def test_run_codex_step_parses_output_file(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        # Codex writes output to -o file; find the output path in the command
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=300,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True,
        )
    assert result.payload == plan_payload
    assert result.duration_ms == 300
    assert result.cost_usd == 0.0


def test_run_codex_step_reports_schema_validation_error_for_json_payload(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps({"plan": "# Plan\nDo it."}), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=300,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        with pytest.raises(CliError) as exc_info:
            run_codex_step(
                "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True,
            )

    assert "plan output missing required keys" in exc_info.value.message
    assert "not valid JSON" not in exc_info.value.message


def test_run_codex_step_uses_full_auto_for_critique_template_writes(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    critique_payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is the plan correct?",
                "guidance": "",
                "findings": [
                    {
                        "detail": "Checked the plan and found a concrete risk.",
                        "flagged": True,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        assert "--full-auto" in command
        add_dir_idx = command.index("--add-dir") + 1
        assert Path(command[add_dir_idx]) == plan_dir
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(critique_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("megaplan.workers._trusted_container", return_value=False), \
         patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step("critique", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == critique_payload


def test_run_codex_step_trusted_container_bypasses_sandbox_for_critique(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    critique_payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is the plan correct?",
                "guidance": "",
                "findings": [
                    {
                        "detail": "Checked the plan and found no issue in the trusted-container command path.",
                        "flagged": False,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        assert "--dangerously-bypass-approvals-and-sandbox" in command
        assert "--full-auto" not in command
        assert not any(str(arg).startswith("sandbox_workspace_write.writable_roots") for arg in command)
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(critique_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step("critique", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == critique_payload


def test_run_codex_step_grants_plan_dir_when_project_dir_differs(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step, set_work_dir_override

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    # Pin the work dir to the plan's project_dir so this test continues to
    # exercise the "grant plan_dir via --add-dir" path without also triggering
    # the worktree warning.
    set_work_dir_override(Path(state["config"]["project_dir"]))
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        cd_idx = command.index("-C") + 1
        add_dir_idx = command.index("--add-dir") + 1
        assert Path(command[cd_idx]) == Path(state["config"]["project_dir"])
        assert Path(command[add_dir_idx]) == plan_dir
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    try:
        with patch("megaplan.workers.run_command", side_effect=fake_run_command):
            result = run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)
    finally:
        set_work_dir_override(None)

    assert result.payload == plan_payload


def test_run_codex_step_accepts_empty_light_critique_payload(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    critique_payload = {
        "checks": [],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(critique_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step("critique", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == critique_payload


def test_run_codex_step_normalizes_revise_payload_missing_changes_summary(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    revise_payload = {
        "plan": "# Revised Plan\nDo it.",
        "flags_addressed": [],
        "assumptions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "questions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(revise_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step("revise", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload["changes_summary"] == "No critique flags were raised; refined the plan for execution."


def test_run_codex_step_raises_on_nonzero_exit(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=1,
            stdout="",
            stderr="Something went wrong",
            duration_ms=100,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        with pytest.raises(CliError, match="failed with exit code"):
            run_codex_step(
                "plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True,
            )


def test_run_codex_step_extracts_session_id_from_timeout_output(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": '{"type":"thread.started","thread_id":"codex-timeout-session"}\n'},
    )

    with patch("megaplan.workers.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_codex_step("execute", state, plan_dir, root=tmp_path, persistent=True, fresh=True, json_trace=True)

    assert exc_info.value.extra["session_id"] == "codex-timeout-session"


def test_run_command_decodes_timeout_byte_streams(tmp_path: Path) -> None:
    from megaplan.workers import run_command

    timeout_error = subprocess.TimeoutExpired(
        cmd=["codex", "exec", "-"],
        timeout=300,
        output=b'prefix\n```json\n{"checks":[],"flags":[],"verified_flag_ids":[],"disputed_flag_ids":[]}\n```',
        stderr=b"\nextra stderr",
    )

    with patch("megaplan.workers.subprocess.run", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_command(["codex", "exec", "-"], cwd=tmp_path, stdin_text="prompt", timeout=300)

    raw_output = exc_info.value.extra["raw_output"]
    assert isinstance(raw_output, str)
    assert "```json" in raw_output
    assert raw_output.startswith("prefix")
    assert "extra stderr" in raw_output


def test_run_codex_step_recovers_critique_payload_from_timeout_raw_output(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    critique_payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Is the plan correct?",
                "guidance": "Check the real code.",
                "findings": [
                    {
                        "detail": "Checked the repository path and found missing propagation for shot metadata.",
                        "flagged": True,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={
            "raw_output": (
                "OpenAI Codex v0.118.0\n"
                '{"type":"thread.started","thread_id":"codex-timeout-session"}\n'
                f"```json\n{json.dumps(critique_payload)}\n```"
            ),
        },
    )

    with patch("megaplan.workers.run_command", side_effect=timeout_error):
        result = run_codex_step("critique", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == critique_payload
    assert result.duration_ms == 0
    assert result.cost_usd == 0.0


def test_run_codex_step_recovers_gate_payload_from_mixed_raw_output(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"]["codex_gatekeeper"] = {
        "id": "gate-session-1",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
    }
    gate_payload = {
        "recommendation": "PROCEED",
        "rationale": "The revised plan is ready.",
        "signals_assessment": "Score dropped and preflight remains healthy.",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [
            {
                "flag_id": "FLAG-001",
                "action": "dispute",
                "evidence": "Verified in workers.py: resolve_agent_mode is already the single routing source of truth.",
                "rationale": "",
            }
        ],
        "accepted_tradeoffs": [],
    }
    raw_output = (
        json.dumps(gate_payload)
        + "\nOpenAI Codex v0.118.0 (research preview)\n--------\n"
        + "user\nExtra transcript text with braces later: {not-json}\n"
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=raw_output,
            stderr="",
            duration_ms=25,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "gate",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            prompt_override="gate prompt",
        )

    assert result.payload == gate_payload
    assert result.session_id == "gate-session-1"
    assert result.duration_ms == 25


def test_run_codex_step_recovers_execute_payload_from_jsonl_agent_message(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"]["codex_executor"] = {
        "id": "execute-session-1",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
    }
    execute_payload = {
        "output": "Implemented batch 2 tasks.",
        "files_changed": ["reigh-worker/source/task_handlers/queue/task_queue.py"],
        "commands_run": ["pytest tests/test_workers.py -k jsonl_agent_message"],
        "deviations": [],
        "task_updates": [
            {
                "task_id": "T6",
                "status": "done",
                "executor_notes": "Recovered from Codex JSONL agent message output.",
                "files_changed": ["reigh-worker/source/task_handlers/queue/task_queue.py"],
                "commands_run": ["pytest tests/test_workers.py -k jsonl_agent_message"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC6", "executor_note": "Confirmed."}
        ],
    }
    raw_output = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "execute-session-1"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_0",
                        "type": "agent_message",
                        "text": json.dumps(execute_payload),
                    },
                }
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text("{not-json}", encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=raw_output,
            stderr="",
            duration_ms=25,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            json_trace=True,
            prompt_override="execute prompt",
        )

    assert result.payload == execute_payload
    assert result.session_id == "execute-session-1"
    assert result.trace_output == raw_output
    assert result.duration_ms == 25


def test_run_codex_step_recovers_execute_batch_payload_from_jsonl_agent_message(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"]["codex_executor"] = {
        "id": "execute-session-2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
    }
    execute_payload = {
        "task_updates": [
            {
                "task_id": "T8",
                "status": "done",
                "executor_notes": "Recovered batch payload from Codex JSONL agent message output.",
                "files_changed": ["reigh-worker/tests/test_preview_harness.py"],
                "commands_run": ["pytest tests/test_preview_harness.py -v"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC8", "executor_note": "Confirmed."}
        ],
    }
    raw_output = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "execute-session-2"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_0",
                        "type": "agent_message",
                        "text": json.dumps(execute_payload),
                    },
                }
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text("{not-json}", encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=raw_output,
            stderr="",
            duration_ms=25,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            json_trace=True,
            prompt_override="Only produce `task_updates` for these tasks: [T8]",
        )

    assert result.payload == execute_payload
    assert result.session_id == "execute-session-2"
    assert result.trace_output == raw_output
    assert result.duration_ms == 25


def test_run_codex_step_resume_omits_add_dir_for_current_codex_cli(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"]["codex_gatekeeper"] = {
        "id": "gate-session-2",
        "created_at": "2026-01-01T00:00:00Z",
        "last_used_at": "2026-01-01T00:00:00Z",
        "mode": "persistent",
        "refreshed": False,
    }
    gate_payload = {
        "recommendation": "PROCEED",
        "rationale": "Ready.",
        "signals_assessment": "Healthy.",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        assert command[:3] == ["codex", "exec", "resume"]
        assert "--add-dir" not in command
        assert "--skip-git-repo-check" in command
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(gate_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=12,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "gate",
            state,
            plan_dir,
            root=tmp_path,
            persistent=True,
            fresh=False,
            prompt_override="gate prompt",
        )

    assert result.payload == gate_payload
    assert result.session_id == "gate-session-2"
    assert result.duration_ms == 12


def test_diagnose_codex_failure_prefers_connection_errors_over_thread_id_numbers() -> None:
    from megaplan.workers import _diagnose_codex_failure

    raw = (
        "thread 'reqwest-internal-sync-runtime' (42967821) panicked\n"
        "failed to connect to websocket: IO error: failed to lookup address information: "
        "nodename nor servname provided, or not known\n"
        "stream disconnected before completion: error sending request for url "
        "(https://chatgpt.com/backend-api/codex/responses)\n"
    )

    code, message = _diagnose_codex_failure(raw, 1)

    assert code == "connection_error"
    assert "connect" in message.lower() or "resolve" in message.lower()


def test_diagnose_codex_failure_detects_real_http_429() -> None:
    from megaplan.workers import _diagnose_codex_failure

    code, message = _diagnose_codex_failure("request failed with HTTP 429 rate limit exceeded", 1)

    assert code == "rate_limit"
    assert "rate limit" in message.lower()


def test_phase_runtime_policy_covers_all_worker_steps() -> None:
    from megaplan.workers import STEP_SCHEMA_FILENAMES

    assert set(PHASE_RUNTIME_POLICY) == set(STEP_SCHEMA_FILENAMES)


def test_codex_timeout_for_step_caps_non_execute_steps() -> None:
    assert _codex_timeout_for_step("plan") == 900


def test_codex_timeout_for_step_preserves_execute_timeout() -> None:
    assert _codex_timeout_for_step("execute") == 7200


def test_codex_child_env_strips_parent_session_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from megaplan.workers import _codex_child_env

    monkeypatch.setenv("CODEX_THREAD_ID", "parent-thread")
    monkeypatch.setenv("CODEX_CI", "1")
    monkeypatch.setenv("CODEX_MANAGED_BY_NPM", "1")

    env = _codex_child_env()

    assert "CODEX_THREAD_ID" not in env
    assert "CODEX_CI" not in env
    assert env["CODEX_MANAGED_BY_NPM"] == "1"


def test_merge_partial_output_appends_output_file_contents(tmp_path: Path) -> None:
    output_path = tmp_path / "partial.json"
    output_path.write_text('{"partial": true}', encoding="utf-8")

    merged = _merge_partial_output("stderr text", output_path)

    assert "stderr text" in merged
    assert "[partial_output_file]" in merged
    assert '{"partial": true}' in merged


def test_run_codex_step_uses_step_timeout_for_plan(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        assert kwargs["timeout"] == 900
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == plan_payload


def test_run_codex_step_reclassifies_timeout_connection_errors(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": "failed to connect to websocket: failed to lookup address information"},
    )

    with patch("megaplan.workers.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert exc_info.value.code == "connection_error"
    assert "connect" in exc_info.value.message.lower() or "resolve" in exc_info.value.message.lower()
    assert "--agent claude" not in exc_info.value.message


def test_run_codex_step_timeout_guidance_prefers_same_step_retry(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": ""},
    )

    with patch("megaplan.workers.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert exc_info.value.code == "worker_timeout"
    assert "re-run the same step on codex once" in exc_info.value.message.lower()
    assert "--agent claude" not in exc_info.value.message


def test_run_step_with_worker_retries_non_execute_codex_timeout_once(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import WorkerResult, run_step_with_worker

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": "", "session_id": "retry-session"},
    )
    worker = WorkerResult(
        payload=payload,
        raw_output="",
        duration_ms=1,
        cost_usd=0.0,
        session_id="retry-session",
    )

    with patch("megaplan.workers.run_codex_step", side_effect=[timeout_error, worker]) as mocked:
        result, agent, mode, refreshed = run_step_with_worker(
            "plan",
            state,
            plan_dir,
            Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, model=None),
            root=tmp_path,
        )

    assert mocked.call_count == 2
    assert result == worker
    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is False
    assert state["sessions"]["codex_planner"]["id"] == "retry-session"


def test_run_step_with_worker_does_not_retry_execute_codex_timeout(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_step_with_worker

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    timeout_error = CliError(
        "worker_timeout",
        "Codex timed out",
        extra={"raw_output": "", "session_id": "execute-session"},
    )

    with patch("megaplan.workers.run_codex_step", side_effect=timeout_error) as mocked:
        with pytest.raises(CliError) as exc_info:
            run_step_with_worker(
                "execute",
                state,
                plan_dir,
                Namespace(agent="codex", ephemeral=False, fresh=False, persist=False, model=None),
                root=tmp_path,
            )

    assert mocked.call_count == 1
    assert exc_info.value.code == "worker_timeout"


def test_run_step_with_worker_falls_back_from_claude_auth_error_to_codex(tmp_path: Path) -> None:
    from megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    args = _make_args()
    auth_error = CliError(
        "auth_error",
        "Claude step failed: Not logged in · Please run /login",
        extra={"raw_output": "Not logged in · Please run /login"},
    )
    worker = WorkerResult(
        payload={
            "plan": "# Plan\nDo it.",
            "questions": [],
            "success_criteria": [{"criterion": "criterion", "priority": "must"}],
            "assumptions": [],
        },
        raw_output="",
        duration_ms=1,
        cost_usd=0.0,
        session_id="codex-fallback-session",
    )

    with patch("megaplan.workers.resolve_agent_mode", return_value=("claude", "persistent", False, None)):
        with patch("megaplan.workers.detect_available_agents", return_value=["claude", "codex"]):
            with patch("megaplan.workers.run_claude_step", side_effect=auth_error) as mocked_claude:
                with patch("megaplan.workers.run_codex_step", return_value=worker) as mocked_codex:
                    result, agent, mode, refreshed = run_step_with_worker(
                        "plan",
                        state,
                        plan_dir,
                        args,
                        root=tmp_path,
                    )

    assert mocked_claude.call_count == 1
    assert mocked_codex.call_count == 1
    assert result == worker
    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is True
    assert args._agent_fallback == {
        "requested": "claude",
        "resolved": "codex",
        "reason": "claude runtime unhealthy: auth_error",
    }


def test_run_step_with_worker_does_not_fallback_for_explicit_agent_runtime_error(tmp_path: Path) -> None:
    from megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    args = _make_args(agent="codex")
    connection_error = CliError(
        "connection_error",
        "Codex could not resolve the backend host. Re-run the same step on Codex once before changing agent.",
        extra={"raw_output": "failed to lookup address information"},
    )

    with patch("megaplan.workers.resolve_agent_mode", return_value=("codex", "persistent", False, None)):
        with patch("megaplan.workers.run_codex_step", side_effect=connection_error) as mocked_codex:
            with pytest.raises(CliError) as exc_info:
                run_step_with_worker(
                    "plan",
                    state,
                    plan_dir,
                    args,
                    root=tmp_path,
                )

    assert mocked_codex.call_count == 2
    assert exc_info.value.code == "connection_error"
    assert not hasattr(args, "_agent_fallback")


def test_run_codex_step_sanitizes_codex_child_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    monkeypatch.setenv("CODEX_THREAD_ID", "outer-thread")
    monkeypatch.setenv("CODEX_CI", "1")
    monkeypatch.setenv("CODEX_MANAGED_BY_NPM", "1")

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        env = kwargs["env"]
        assert isinstance(env, dict)
        assert "CODEX_THREAD_ID" not in env
        assert "CODEX_CI" not in env
        assert env["CODEX_MANAGED_BY_NPM"] == "1"
        output_idx = command.index("-o") + 1
        output_path = Path(command[output_idx])
        output_path.write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)

    assert result.payload == plan_payload


# ---------------------------------------------------------------------------
# Worktree isolation: subprocess workers should receive the CWD (or an
# explicit --work-dir override) for --add-dir / -C, not the plan's stored
# project_dir. This preserves git-worktree isolation across parallel runs.
# ---------------------------------------------------------------------------


def test_run_claude_step_uses_cwd_for_add_dir_when_worktree_differs(
    tmp_path: Path,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import (
        CommandResult,
        run_claude_step,
        set_work_dir_override,
    )

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    # Simulate a worktree: project_dir is /tmp/.../project but the current
    # "checkout" is /tmp/.../worktree.
    worktree_dir = tmp_path / "worktree"
    worktree_dir.mkdir()
    set_work_dir_override(worktree_dir)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    captured: dict[str, Any] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=json.dumps({"result": json.dumps(plan_payload), "total_cost_usd": 0.0}),
            stderr="",
            duration_ms=1,
        )

    try:
        with patch("megaplan.workers.run_command", side_effect=fake_run_command):
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True)
    finally:
        set_work_dir_override(None)

    command = captured["command"]
    add_dir_idx = command.index("--add-dir") + 1
    assert Path(command[add_dir_idx]) == worktree_dir
    assert Path(command[add_dir_idx]) != Path(state["config"]["project_dir"])
    assert Path(captured["cwd"]) == worktree_dir


def test_run_claude_step_honors_explicit_work_dir_override(
    tmp_path: Path,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import (
        CommandResult,
        run_claude_step,
        set_work_dir_override,
    )

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    # project_dir lives at tmp_path/project; --work-dir explicitly forces a
    # different path (simulating the operator passing --work-dir on the CLI).
    forced_dir = tmp_path / "forced"
    forced_dir.mkdir()
    set_work_dir_override(forced_dir)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    captured: dict[str, Any] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=json.dumps({"result": json.dumps(plan_payload), "total_cost_usd": 0.0}),
            stderr="",
            duration_ms=1,
        )

    try:
        with patch("megaplan.workers.run_command", side_effect=fake_run_command):
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True)
    finally:
        set_work_dir_override(None)

    command = captured["command"]
    add_dir_idx = command.index("--add-dir") + 1
    assert Path(command[add_dir_idx]) == forced_dir


def test_run_codex_step_uses_work_dir_for_dash_c_not_project_dir(
    tmp_path: Path,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import (
        CommandResult,
        run_codex_step,
        set_work_dir_override,
    )

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    worktree_dir = tmp_path / "worktree"
    worktree_dir.mkdir()
    set_work_dir_override(worktree_dir)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    captured: dict[str, Any] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    try:
        with patch("megaplan.workers.run_command", side_effect=fake_run_command):
            run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)
    finally:
        set_work_dir_override(None)

    command = captured["command"]
    cd_idx = command.index("-C") + 1
    add_dir_idx = command.index("--add-dir") + 1
    # -C (source-code cwd) should follow the worktree, NOT project_dir.
    assert Path(command[cd_idx]) == worktree_dir
    assert Path(command[cd_idx]) != Path(state["config"]["project_dir"])
    # --add-dir still grants access to the plan's artifacts directory
    # (unchanged by the worktree fix).
    assert Path(command[add_dir_idx]) == plan_dir


def test_resolve_work_dir_defaults_to_project_dir_when_no_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: without --work-dir and without any override set,
    resolve_work_dir() should return the plan's stored project_dir rather
    than falling back to the shell's CWD. This prevents codex from being
    sandboxed to an arbitrary subdirectory when the operator cd's around
    between ``megaplan init`` and ``megaplan execute``.
    """
    from megaplan.workers import resolve_work_dir, set_work_dir_override

    _plan_dir, state = _mock_state(tmp_path)
    project_dir = Path(state["config"]["project_dir"])

    # Simulate the shell being somewhere else (a child directory of the
    # project) when execute fires. Without fix 1, resolve_work_dir would
    # return this narrower CWD.
    narrower_cwd = project_dir / "child-subdir"
    narrower_cwd.mkdir()
    monkeypatch.chdir(narrower_cwd)

    set_work_dir_override(None)
    try:
        resolved = resolve_work_dir(state)
    finally:
        set_work_dir_override(None)

    assert resolved == project_dir, (
        "resolve_work_dir must default to the plan's project_dir when no "
        f"--work-dir override is set (got {resolved})"
    )


def test_warn_if_work_dir_differs_from_project_dir_prints_on_divergence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fix 2: a divergent work_dir must surface a stderr WARNING, not a
    buried info line. The message must identify both directories and offer
    a concrete remediation.
    """
    from megaplan.workers import (
        set_work_dir_override,
        warn_if_work_dir_differs_from_project_dir,
    )

    _plan_dir, state = _mock_state(tmp_path)
    project_dir = Path(state["config"]["project_dir"])
    narrower = project_dir / "subdir"
    narrower.mkdir()

    set_work_dir_override(narrower)
    try:
        warn_if_work_dir_differs_from_project_dir(state)
    finally:
        set_work_dir_override(None)

    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert str(project_dir) in captured.err
    assert str(narrower) in captured.err
    assert "--work-dir" in captured.err


def test_warn_if_work_dir_differs_from_project_dir_silent_when_matching(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from megaplan.workers import (
        set_work_dir_override,
        warn_if_work_dir_differs_from_project_dir,
    )

    _plan_dir, state = _mock_state(tmp_path)
    project_dir = Path(state["config"]["project_dir"])

    set_work_dir_override(project_dir)
    try:
        warn_if_work_dir_differs_from_project_dir(state)
    finally:
        set_work_dir_override(None)

    captured = capsys.readouterr()
    assert captured.err == ""


def test_resolve_work_dir_explicit_override_still_wins(tmp_path: Path) -> None:
    """Fix 1 must remain backward-compatible with --work-dir: an explicit
    override should still beat the project_dir default.
    """
    from megaplan.workers import resolve_work_dir, set_work_dir_override

    _plan_dir, state = _mock_state(tmp_path)
    forced = tmp_path / "forced"
    forced.mkdir()

    set_work_dir_override(forced)
    try:
        resolved = resolve_work_dir(state)
    finally:
        set_work_dir_override(None)

    assert resolved == forced


# ---------------------------------------------------------------------------
# Poisoned-session detection + recovery (v0.14.6)
# ---------------------------------------------------------------------------


def test_is_poisoned_environmental_failure_matches_bwrap_namespace_error() -> None:
    from megaplan.workers import _is_poisoned_environmental_failure

    raw = "something happened\nbwrap: Creating new namespace failed: Permission denied\nmore"
    assert _is_poisoned_environmental_failure(raw) is True


def test_is_poisoned_environmental_failure_matches_permission_denied_sandbox() -> None:
    from megaplan.workers import _is_poisoned_environmental_failure

    raw = "error: Permission denied while trying to start the sandbox. cannot start sandbox."
    assert _is_poisoned_environmental_failure(raw) is True


def test_is_poisoned_environmental_failure_matches_repo_cmd_unavailable_sandbox() -> None:
    from megaplan.workers import _is_poisoned_environmental_failure

    raw = (
        "Repository command execution is currently unavailable because the sandbox "
        "could not be initialized."
    )
    assert _is_poisoned_environmental_failure(raw) is True


def test_is_poisoned_environmental_failure_ignores_unrelated_errors() -> None:
    from megaplan.workers import _is_poisoned_environmental_failure

    assert _is_poisoned_environmental_failure("") is False
    assert _is_poisoned_environmental_failure("TypeError: foo is not callable") is False
    # A lone "Permission denied" without sandbox context must not trip patterns.
    assert _is_poisoned_environmental_failure("Permission denied: /root/.cache") is False


def test_is_session_too_large_for_compact_matches_real_codex_error() -> None:
    from megaplan.workers import _is_session_too_large_for_compact

    raw = (
        '{"type":"error","message":"Error running remote compact task: '
        'exceeded retry limit, last status: 429 Too Many Requests, '
        'request id: req_e45c8eddc3204adbb0ce791f23557be9"}'
    )
    assert _is_session_too_large_for_compact(raw) is True


def test_is_session_too_large_for_compact_ignores_unrelated_errors() -> None:
    from megaplan.workers import _is_session_too_large_for_compact

    assert _is_session_too_large_for_compact("") is False
    # 429 alone (without remote-compact context) is generic rate limiting.
    assert _is_session_too_large_for_compact("429 Too Many Requests on /chat") is False
    # remote compact mention without 429 is not the failure mode.
    assert _is_session_too_large_for_compact("remote compact task succeeded") is False


def test_run_codex_step_resumed_session_retries_fresh_on_poisoned_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resumed Codex session whose output contains a stale bwrap failure line
    should cause run_codex_step to drop the session id and recursively
    re-invoke itself with fresh=True."""
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"] = {
        "codex_executor": {
            "id": "sess-poisoned",
            "mode": "persistent",
            "created_at": "2026-04-15T00:00:00Z",
            "last_used_at": "2026-04-15T00:00:00Z",
            "refreshed": False,
        }
    }
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")

    poisoned_raw = (
        "bwrap: Creating new namespace failed: Permission denied\n"
        "cannot continue\n"
    )
    call_counter = {"n": 0}

    def fake_run_command(command, **kwargs):
        call_counter["n"] += 1
        if call_counter["n"] == 1:
            return CommandResult(
                command=command,
                cwd=tmp_path,
                returncode=1,
                stdout="",
                stderr=poisoned_raw,
                duration_ms=5,
            )
        out_idx = command.index("-o") + 1
        output_path = Path(command[out_idx])
        payload = {
            "output": "done",
            "files_changed": [],
            "commands_run": [],
            "deviations": [],
            "task_updates": [],
            "sense_check_acknowledgments": [],
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=json.dumps({"type": "thread.started", "thread_id": "sess-fresh"}) + "\n",
            stderr="",
            duration_ms=5,
        )

    with patch("megaplan.workers.create_codex_prompt", return_value="prompt"):
        with patch("megaplan.workers.run_command", side_effect=fake_run_command):
            result = run_codex_step(
                "execute",
                state,
                plan_dir,
                root=tmp_path,
                persistent=True,
                fresh=False,
            )

    assert call_counter["n"] == 2
    assert result.payload.get("output") == "done"
    assert result.session_id == "sess-fresh"
    # Stale session id must have been dropped from state before the recursive
    # call; the new session id is installed by the caller (apply_session_update).
    assert state["sessions"].get("codex_executor", {}).get("id") != "sess-poisoned"


def test_run_codex_step_skips_poison_retry_when_fresh_already(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With fresh=True the poisoned-session branch must not engage."""
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")

    poisoned_raw = "bwrap: Creating new namespace failed: Permission denied\n"

    def fake_run_command(command, **kwargs):
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=1,
            stdout="",
            stderr=poisoned_raw,
            duration_ms=1,
        )

    with patch("megaplan.workers.create_codex_prompt", return_value="prompt"):
        with patch("megaplan.workers.run_command", side_effect=fake_run_command):
            with pytest.raises(CliError):
                run_codex_step(
                    "execute",
                    state,
                    plan_dir,
                    root=tmp_path,
                    persistent=False,
                    fresh=True,
                )


# ---------------------------------------------------------------------------
# Codex token-usage / cost capture (codex_pricing + run_codex_step wiring)
# ---------------------------------------------------------------------------


def _write_codex_rollout(
    codex_home: Path,
    session_id: str,
    total_token_usage: dict,
    *,
    date: str = "2026/05/05",
    timestamp: str = "0000-1234567890",
) -> Path:
    """Write a fake codex rollout JSONL and return its path."""
    sessions_dir = codex_home / "sessions" / date
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = sessions_dir / f"rollout-{timestamp}-{session_id}.jsonl"
    lines = [
        json.dumps({
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "timestamp": "2026-05-05T09:00:00Z",
                "model_provider": "openai",
            },
        }),
        json.dumps({
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": total_token_usage,
                    "last_token_usage": total_token_usage,
                    "model_context_window": 258400,
                },
            },
        }),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_codex_pricing_table() -> None:
    from megaplan.codex_pricing import (
        DEFAULT_MODEL,
        PRICING,
        cost_from_usage,
    )

    # Spec example: 66607 in (4864 cached), 1089 out, 230 reasoning -> $0.350717
    usage = {
        "input_tokens": 66607,
        "cached_input_tokens": 4864,
        "output_tokens": 1089,
        "reasoning_output_tokens": 230,
    }
    expected = (
        (66607 - 4864) * 5.00
        + 4864 * 0.50
        + (1089 + 230) * 30.00
    ) / 1_000_000
    assert cost_from_usage(usage, "gpt-5.5") == pytest.approx(expected)
    # Unknown model falls back to default rates.
    assert cost_from_usage(usage, "totally-made-up") == pytest.approx(expected)
    # Default model resolves the same way.
    assert DEFAULT_MODEL in PRICING
    assert cost_from_usage(usage) == pytest.approx(expected)
    # Empty / None usage -> 0.
    assert cost_from_usage(None) == 0.0
    assert cost_from_usage({}) == 0.0
    # gpt-5 cheaper rates apply.
    cheap = cost_from_usage(usage, "gpt-5")
    assert 0 < cheap < expected


def test_codex_step_extracts_token_usage_from_session_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    codex_home = tmp_path / "codex_home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    session_id = "019df78d-2a47-7981-a7d1-fadf79f5b240"
    total_usage = {
        "input_tokens": 66607,
        "cached_input_tokens": 4864,
        "output_tokens": 1089,
        "reasoning_output_tokens": 230,
        "total_tokens": 67696,
    }
    _write_codex_rollout(codex_home, session_id, total_usage)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=f'{{"type":"thread.started","thread_id":"{session_id}"}}\n',
            stderr="",
            duration_ms=300,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=True, fresh=True,
        )

    expected_cost = (
        (66607 - 4864) * 5.00
        + 4864 * 0.50
        + (1089 + 230) * 30.00
    ) / 1_000_000
    assert result.cost_usd == pytest.approx(expected_cost)
    assert result.prompt_tokens == 66607
    assert result.completion_tokens == 1089 + 230
    assert result.total_tokens == 66607 + 1089 + 230
    assert result.session_id == session_id


def test_codex_step_handles_missing_session_jsonl_gracefully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    # Point CODEX_HOME at an empty dir so no rollout matches.
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty_codex_home"))

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout='{"type":"thread.started","thread_id":"abc-1234-no-rollout"}\n',
            stderr="",
            duration_ms=300,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        result = run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=True, fresh=True,
        )

    assert result.cost_usd == 0.0
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    captured = capsys.readouterr()
    assert "Could not locate codex rollout" in captured.out


def test_codex_step_incremental_cost_within_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_codex_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    codex_home = tmp_path / "codex_home2"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    session_id = "session-incr-0001"
    # First step: cumulative totals after step 1.
    first_total = {
        "input_tokens": 1000,
        "cached_input_tokens": 0,
        "output_tokens": 500,
        "reasoning_output_tokens": 0,
        "total_tokens": 1500,
    }
    rollout_path = _write_codex_rollout(codex_home, session_id, first_total)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=f'{{"type":"thread.started","thread_id":"{session_id}"}}\n',
            stderr="",
            duration_ms=200,
        )

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        first = run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=True, fresh=True,
        )

    expected_first = (1000 * 5.00 + 500 * 30.00) / 1_000_000
    assert first.cost_usd == pytest.approx(expected_first)
    # Session entry should now carry the running totals.
    session_key = "codex_planner"
    assert state["sessions"][session_key]["last_total_tokens"]["input_tokens"] == 1000

    # Second step: rollout grows. Rewrite the file with a larger cumulative.
    second_total = {
        "input_tokens": 3000,
        "cached_input_tokens": 200,
        "output_tokens": 1500,
        "reasoning_output_tokens": 100,
        "total_tokens": 4600,
    }
    rollout_path.unlink()
    _write_codex_rollout(codex_home, session_id, second_total)

    # Pre-seed session id so the second call resumes (mirroring real flow).
    state["sessions"][session_key]["id"] = session_id

    with patch("megaplan.workers.run_command", side_effect=fake_run_command):
        second = run_codex_step(
            "plan", state, plan_dir, root=tmp_path, persistent=True, fresh=False,
        )

    delta_input = 3000 - 1000  # 2000 new input tokens
    delta_cached = 200  # all new
    delta_full_input = delta_input - delta_cached  # 1800
    delta_output = (1500 + 100) - (500 + 0)  # 1100
    expected_second = (
        delta_full_input * 5.00 + delta_cached * 0.50 + delta_output * 30.00
    ) / 1_000_000
    assert second.cost_usd == pytest.approx(expected_second)
    # Cumulative bookkeeping advanced.
    assert state["sessions"][session_key]["last_total_tokens"]["input_tokens"] == 3000
