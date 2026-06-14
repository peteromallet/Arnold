from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines import megaplan
import arnold.pipelines.megaplan._core
import arnold.pipelines.megaplan._core.io as io_module
import arnold.pipelines.megaplan.cli as megaplan_cli
from arnold.pipelines.megaplan.orchestration.prep_research import PrepOrchestrationResult
from arnold.pipelines.megaplan.handlers import handle_plan, handle_prep
from arnold.pipelines.megaplan.prompts import create_claude_prompt
from arnold.pipelines.megaplan.prompts._shared import _render_prep_block
from arnold.pipelines.megaplan.receipts.extractors import load_and_extract
from arnold.pipelines.megaplan.workers import WorkerResult

from tests.conftest import make_args_factory


@pytest.fixture(autouse=True)
def _isolate_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "user-config"
    monkeypatch.setattr(
        "arnold.pipelines.megaplan._core.user_config.config_dir",
        lambda home=None: config_path,
    )


def _make_args(plan_name: str | None, project_dir: Path, **overrides: Any) -> Namespace:
    defaults: dict[str, Any] = {
        "plan": plan_name,
        "idea": "prep fanout skip",
        "name": plan_name,
        "robustness": "robust",
        "prep_direction": None,
    }
    defaults.update(overrides)
    return make_args_factory(project_dir)(**defaults)


def test_cli_registers_prep_command() -> None:
    parser = megaplan.cli.build_parser()
    parsed = parser.parse_args(["prep", "--plan", "demo"])

    assert parsed.command == "prep"
    assert parsed.plan == "demo"
    assert megaplan.cli.COMMAND_HANDLERS["prep"] is handle_prep


def test_cli_prep_direction_flag_parses() -> None:
    parser = megaplan.cli.build_parser()
    parsed = parser.parse_args(
        ["prep", "--plan", "demo", "--direction", "trace shutdown path"]
    )
    assert parsed.prep_direction == "trace shutdown path"


def test_cli_prep_direction_defaults_to_none() -> None:
    parser = megaplan.cli.build_parser()
    parsed = parser.parse_args(["prep", "--plan", "demo"])
    assert parsed.prep_direction is None


def test_cli_init_prep_direction_flag_parses(tmp_path) -> None:
    parser = megaplan.cli.build_parser()
    parsed = parser.parse_args(
        [
            "init",
            "--project-dir",
            str(tmp_path),
            "--prep-direction",
            "focus on cache invalidation",
            "an idea",
        ]
    )
    assert parsed.prep_direction == "focus on cache invalidation"


def test_cli_init_no_prep_clarify_flag_round_trips(tmp_path: Path) -> None:
    parser = megaplan.cli.build_parser()

    parsed_default = parser.parse_args(
        ["init", "--project-dir", str(tmp_path), "an idea"]
    )
    parsed_disabled = parser.parse_args(
        ["init", "--project-dir", str(tmp_path), "--no-prep-clarify", "an idea"]
    )

    assert parsed_default.prep_clarify is True
    assert parsed_disabled.prep_clarify is False


def test_handle_prep_zero_area_triage_writes_skip_artifacts_and_skips_fanout(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    triage_worker = WorkerResult(
        payload={"triage_framing": "No research needed.", "areas": []},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="triage",
    )

    with (
        patch("arnold.pipelines.megaplan.orchestration.prep_research.run_prep_triage", return_value=triage_worker),
        patch("arnold.pipelines.megaplan.orchestration.prep_research.run_research_fanout") as fanout,
    ):
        response = handle_prep(root, _make_args(plan_name, project_dir, plan=plan_name))

    assert response["state"] == "prepped"
    fanout.assert_not_called()
    prep = json.loads((plan_dir / "prep.json").read_text(encoding="utf-8"))
    metrics = json.loads((plan_dir / "prep_metrics.json").read_text(encoding="utf-8"))
    assert prep == {
        "skip": True,
        "task_summary": "",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "",
    }
    assert metrics["area_count"] == 0
    assert metrics["fanout_count"] == 0
    assert metrics["completed_count"] == 0
    assert metrics["partial_count"] == 0
    assert metrics["timed_out_count"] == 0
    assert metrics["error_count"] == 0
    assert metrics["missed_units"] == []
    assert metrics["total_cost_usd"] == 0.0
    assert metrics["prompt_tokens"] == 0
    assert metrics["completion_tokens"] == 0
    assert metrics["total_tokens"] == 0
    assert metrics["elapsed_time_ms"] == 0
    assert metrics["files"] == []
    assert metrics["code_refs"] == []
    assert metrics["per_unit"] == []
    assert metrics["gap_notes"] == []
    assert metrics["contradiction_notes"] == []
    assert metrics["overlap_groups"] == []
    assert metrics["cross_reference"] == {
        "performed": False,
        "checked_files": [],
        "existing_files": [],
        "missing_files": [],
        "shared_files": [],
        "to_be_built_files": [],
    }
    assert metrics["stage_metrics"] == {
        "triage": {
            "cost_usd": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "elapsed_time_ms": 0,
        },
        "fanout": {
            "cost_usd": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "elapsed_time_ms": 0,
        },
        "distill": {
            "cost_usd": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "elapsed_time_ms": 0,
        },
    }
    assert _render_prep_block(plan_dir) == ("", "")
    prep_state = megaplan._core.read_json(plan_dir / "state.json")
    plan_prompt = create_claude_prompt("plan", prep_state, plan_dir)
    assert "Engineering brief from PREP" not in plan_prompt
    assert "Prep skipped" not in plan_prompt


def test_handle_prep_uses_dedicated_orchestration_runner(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]
    prep_payload = {
        "skip": False,
        "task_summary": "summary",
        "key_evidence": [],
        "relevant_code": ["megaplan/orchestration/prep_research.py"],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "approach",
    }
    worker = WorkerResult(
        payload=prep_payload,
        raw_output="{}",
        duration_ms=3,
        cost_usd=0.0,
        session_id="prep-session",
    )
    orchestration = PrepOrchestrationResult(
        worker=worker,
        artifacts=["prep.json", "prep_dossier.md", "prep_metrics.json"],
        summary="orchestrated prep",
        agent="hermes",
        mode="ephemeral",
        refreshed=True,
        prep_metrics_hash="metrics-hash",
    )

    with (
        patch("arnold.pipelines.megaplan.orchestration.prep_research.run_prep_orchestration", return_value=orchestration) as runner,
        patch("arnold.pipelines.megaplan.handlers._run_worker") as legacy_worker,
    ):
        response = handle_prep(root, _make_args(plan_name, project_dir, plan=plan_name))

    runner.assert_called_once()
    legacy_worker.assert_not_called()
    assert response["summary"] == "orchestrated prep"
    assert response["prep_metrics_hash"] == "metrics-hash"
    assert response["state"] == "prepped"


def test_mocked_prep_orchestration_feeds_plan_prompt_without_changing_plan_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

    init_response = megaplan.handle_init(
        root,
        _make_args(None, project_dir, robustness="full"),
    )
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name
    state = megaplan._core.read_json(plan_dir / "state.json")
    state["config"]["robustness"] = "full"
    megaplan._core.atomic_write_json(plan_dir / "state.json", state, _plan_dir=plan_dir)

    triage_worker = WorkerResult(
        payload={
            "triage_framing": "Investigate the orchestration edges before planning.",
            "areas": [
                {"id": f"a{index}", "area": f"Area {index}", "brief": f"brief {index}"}
                for index in range(6)
            ],
        },
        raw_output="triage",
        duration_ms=10,
        cost_usd=0.1,
        session_id="triage-session",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
    )
    fanout_result = megaplan.orchestration.prep_research.GenericScatterResult(
        ordered_results=[
            {
                "area": "a0",
                "brief": "brief 0",
                "status": "complete",
                "findings": ["found the planner entrypoint"],
                "files": ["megaplan/handlers/plan.py"],
                "code_refs": ["arnold.pipelines.megaplan.handlers.plan.handle_plan"],
                "confidence": "high",
                "error": "",
            },
            {
                "area": "a1",
                "brief": "brief 1",
                "status": "partial",
                "findings": ["plan artifacts stay on the normal path"],
                "files": ["megaplan/handlers/shared.py"],
                "code_refs": ["arnold.pipelines.megaplan.handlers.shared._finish_step"],
                "confidence": "medium",
                "error": "",
            },
            {
                "area": "a2",
                "brief": "brief 2",
                "status": "timed_out",
                "findings": [],
                "files": [],
                "code_refs": [],
                "confidence": "low",
                "error": "research timeout",
            },
            {
                "area": "a3",
                "brief": "brief 3",
                "status": "error",
                "findings": [],
                "files": [],
                "code_refs": [],
                "confidence": "low",
                "error": "parse drift",
            },
        ],
        total_cost=0.2,
        total_prompt_tokens=3,
        total_completion_tokens=4,
        total_tokens=7,
        side_results=[
            {
                "area": "a0",
                "status": "complete",
                "elapsed_time_ms": 30,
                "files": ["megaplan/handlers/plan.py"],
                "code_refs": ["arnold.pipelines.megaplan.handlers.plan.handle_plan"],
            },
            {
                "area": "a1",
                "status": "partial",
                "elapsed_time_ms": 40,
                "files": ["megaplan/handlers/shared.py"],
                "code_refs": ["arnold.pipelines.megaplan.handlers.shared._finish_step"],
            },
            {
                "area": "a2",
                "status": "timed_out",
                "elapsed_time_ms": 50,
                "files": [],
                "code_refs": [],
            },
            {
                "area": "a3",
                "status": "error",
                "elapsed_time_ms": 60,
                "files": [],
                "code_refs": [],
            },
        ],
    )
    distill_worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "Prep found enough signal to plan against the orchestration path.",
            "key_evidence": [
                {
                    "point": "Plan artifacts are still written through _finish_step.",
                    "source": "research",
                    "relevance": "high",
                }
            ],
            "relevant_code": [
                {
                    "file_path": "megaplan/handlers/shared.py",
                    "why": "Plan artifacts are finalized here.",
                    "functions": ["_finish_step"],
                }
            ],
            "test_expectations": [
                {
                    "test_id": "tests/test_prep.py",
                    "what_it_checks": "prep prompt handoff preserves plan artifacts",
                    "status": "pass_to_pass",
                }
            ],
            "constraints": ["Keep `plan_vN.md` artifact naming unchanged."],
            "suggested_approach": "Use the prep brief as evidence and keep plan writes on the standard flow.",
        },
        raw_output="distill",
        duration_ms=20,
        cost_usd=0.3,
        session_id="distill-session",
        prompt_tokens=5,
        completion_tokens=6,
        total_tokens=11,
    )
    plan_worker = WorkerResult(
        payload={
            "plan": "# Plan\n\n## Overview\n\nUse the prep evidence.\n\n## Step 1: Update `megaplan/receipts/extractors.py`\n",
            "questions": [],
            "success_criteria": [
                {"criterion": "Prep remains compatible with PLAN.", "priority": "must"}
            ],
            "assumptions": [],
        },
        raw_output="plan",
        duration_ms=5,
        cost_usd=0.0,
        session_id="plan-session",
    )

    with (
        patch("arnold.pipelines.megaplan.orchestration.prep_research.run_prep_triage", return_value=triage_worker),
        patch("arnold.pipelines.megaplan.orchestration.prep_research.run_research_fanout", return_value=fanout_result),
        patch("arnold.pipelines.megaplan.orchestration.prep_research.distill_prep", return_value=distill_worker),
    ):
        prep_response = handle_prep(root, _make_args(plan_name, project_dir, plan=plan_name))

    assert prep_response["state"] == "prepped"
    assert prep_response["artifacts"] == [
        "prep.json",
        "prep_dossier.md",
        "prep_metrics.json",
        "prep_triage.json",
        "research.json",
    ]
    prep_receipt_metrics = load_and_extract(plan_dir, "prep", 0)
    assert prep_receipt_metrics["area_count"] == 6
    assert prep_receipt_metrics["fanout_count"] == 4
    assert prep_receipt_metrics["cap_applied"] is True
    assert prep_receipt_metrics["missed_units"] == ["a2", "a3"]
    assert prep_receipt_metrics["status_counts"] == {
        "complete": 1,
        "partial": 1,
        "timed_out": 1,
        "error": 1,
        "not_needed": 0,
    }

    prep_state = megaplan._core.read_json(plan_dir / "state.json")
    prompt = create_claude_prompt("plan", prep_state, plan_dir)
    assert "### Task Summary" in prompt
    assert "Prep found enough signal to plan against the orchestration path." in prompt
    assert "Plan artifacts are still written through _finish_step." in prompt
    assert "plan_v1.md" not in prompt

    with patch("arnold.pipelines.megaplan.handlers._run_worker", return_value=(plan_worker, "codex", "ephemeral", True)):
        plan_response = handle_plan(root, _make_args(plan_name, project_dir, plan=plan_name))

    assert plan_response["state"] == "planned"
    assert plan_response["artifacts"] == ["plan_v1.md", "plan_v1.meta.json"]
    assert (plan_dir / "plan_v1.md").exists()
    assert (plan_dir / "plan_v1.meta.json").exists()


# ---------------------------------------------------------------------------
# T12: Prep clarification gate tests (MOCK path, MEGAPLAN_MOCK=1)
# ---------------------------------------------------------------------------

def _mock_env(monkeypatch: Any) -> None:
    """Set up MEGAPLAN_MOCK_WORKERS=1 and mock shutil.which for MOCK prep path."""
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )


def _make_prep_worker(open_questions: list[dict[str, Any]] | None = None) -> WorkerResult:
    """Build a deterministic prep worker payload with optional open_questions."""
    payload: dict[str, Any] = {
        "skip": False,
        "task_summary": "Research complete.",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "Proceed as planned.",
    }
    if open_questions is not None:
        payload["open_questions"] = open_questions
    return WorkerResult(
        payload=payload,
        raw_output="{}",
        duration_ms=5,
        cost_usd=0.0,
        session_id="prep-mock",
    )


# (a) blocking question + clarify enabled → AWAITING_HUMAN
def test_prep_blocking_question_halts_at_awaiting_human(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)
    _mock_env(monkeypatch)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    blocking = [
        {
            "severity": "blocking",
            "question": "Which auth library should we use?",
        },
        {
            "severity": "blocking",
            "question": "Should the API be REST or GraphQL?",
            "assumption": "REST is the safer default.",
        },
    ]
    worker = _make_prep_worker(open_questions=blocking)

    with patch("arnold.pipelines.megaplan.handlers._run_worker", return_value=(worker, "claude", "ephemeral", True)):
        response = handle_prep(root, _make_args(plan_name, project_dir, plan=plan_name))

    assert response["state"] == "awaiting_human_verify"
    assert response["summary"].startswith("Prep halted:")
    assert "2 blocking questions" in response["summary"]

    state = megaplan._core.read_json(plan_dir / "state.json")
    clarification = state.get("clarification")
    assert clarification is not None
    assert clarification["source"] == "prep"
    assert len(clarification["questions"]) == 2
    assert "[blocking] Which auth library should we use?" in clarification["questions"]
    assert "[blocking] Should the API be REST or GraphQL?" in clarification["questions"]
    assert "resume-clarify" in clarification["intent_summary"]

    # prep.json should still contain open_questions
    prep = json.loads((plan_dir / "prep.json").read_text(encoding="utf-8"))
    assert prep.get("open_questions") == blocking


# (b) --no-prep-clarify → PREPPED, blocking question still in prep.json
def test_prep_blocking_question_no_prep_clarify_proceeds_to_prepped(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)
    _mock_env(monkeypatch)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    # disable prep_clarify
    state = megaplan._core.read_json(plan_dir / "state.json")
    state["config"]["prep_clarify"] = False
    megaplan._core.atomic_write_json(plan_dir / "state.json", state, _plan_dir=plan_dir)

    blocking = [{"severity": "blocking", "question": "Which auth library should we use?"}]
    worker = _make_prep_worker(open_questions=blocking)

    with patch("arnold.pipelines.megaplan.handlers._run_worker", return_value=(worker, "claude", "ephemeral", True)):
        response = handle_prep(root, _make_args(plan_name, project_dir, plan=plan_name))

    assert response["state"] == "prepped"
    assert "Prep complete" in response["summary"]

    # blocking question must still be in prep.json
    prep = json.loads((plan_dir / "prep.json").read_text(encoding="utf-8"))
    assert prep.get("open_questions") == blocking

    # clarification must NOT be set
    state = megaplan._core.read_json(plan_dir / "state.json")
    assert "clarification" not in state


# (c) assume_and_proceed never halts under either setting
def test_prep_assume_and_proceed_never_halts(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)
    _mock_env(monkeypatch)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]

    assume_items = [
        {
            "severity": "assume_and_proceed",
            "question": "Which cache backend?",
            "assumption": "Redis is fine for now.",
        },
        {
            "severity": "assume_and_proceed",
            "question": "Which serialization format?",
            "assumption": "JSON is adequate.",
        },
    ]
    worker = _make_prep_worker(open_questions=assume_items)

    with patch("arnold.pipelines.megaplan.handlers._run_worker", return_value=(worker, "claude", "ephemeral", True)):
        response = handle_prep(root, _make_args(plan_name, project_dir, plan=plan_name))

    assert response["state"] == "prepped"
    assert "Prep complete" in response["summary"]


# (c-alt) assume_and_proceed + blocking mix only halts on blocking when clarify enabled
def test_prep_mixed_severity_only_blocking_gates(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)
    _mock_env(monkeypatch)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    mixed = [
        {"severity": "assume_and_proceed", "question": "Which cache backend?", "assumption": "Redis."},
        {"severity": "blocking", "question": "Which auth library?"},
    ]
    worker = _make_prep_worker(open_questions=mixed)

    with patch("arnold.pipelines.megaplan.handlers._run_worker", return_value=(worker, "claude", "ephemeral", True)):
        response = handle_prep(root, _make_args(plan_name, project_dir, plan=plan_name))

    assert response["state"] == "awaiting_human_verify"
    clarification = megaplan._core.read_json(plan_dir / "state.json").get("clarification")
    assert len(clarification["questions"]) == 1  # only blocking
    assert "[blocking] Which auth library?" in clarification["questions"][0]


# (f) resume-clarify from prep-sourced AWAITING_HUMAN succeeds
def test_override_resume_clarify_from_prep_source_succeeds(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)
    _mock_env(monkeypatch)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    # Simulate a prep-sourced AWAITING_HUMAN state
    blocking = [{"severity": "blocking", "question": "Which auth library?"}]
    worker = _make_prep_worker(open_questions=blocking)

    with patch("arnold.pipelines.megaplan.handlers._run_worker", return_value=(worker, "claude", "ephemeral", True)):
        handle_prep(root, _make_args(plan_name, project_dir, plan=plan_name))

    state = megaplan._core.read_json(plan_dir / "state.json")
    assert state["current_state"] == "awaiting_human_verify"
    assert state["clarification"]["source"] == "prep"

    # Now resume via override resume-clarify
    resume_response = megaplan.handle_override(
        root,
        _make_args(
            plan_name,
            project_dir,
            plan=plan_name,
            override_action="resume-clarify",
        ),
    )

    assert resume_response["success"] is True
    assert resume_response["state"] == "prepped"
    assert "Prep clarification resolved" in resume_response["summary"]

    # state.json should be back to prepped
    state = megaplan._core.read_json(plan_dir / "state.json")
    assert state["current_state"] == "prepped"


# (f-reject) resume-clarify rejected when source != 'prep'
def test_override_resume_clarify_rejects_non_prep_source(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    # Manually set state to AWAITING_HUMAN with a non-prep clarification source
    state = megaplan._core.read_json(plan_dir / "state.json")
    state["current_state"] = "awaiting_human_verify"
    state["clarification"] = {
        "intent_summary": "Criteria verification needed.",
        "questions": ["Is the plan acceptable?"],
        "source": "criteria",
    }
    megaplan._core.atomic_write_json(plan_dir / "state.json", state, _plan_dir=plan_dir)

    with pytest.raises(megaplan.CliError, match="resume-clarify can only resume a prep-sourced"):
        megaplan.handle_override(
            root,
            _make_args(
                plan_name,
                project_dir,
                plan=plan_name,
                override_action="resume-clarify",
            ),
        )


# (f-reject2) resume-clarify rejected when not in AWAITING_HUMAN
def test_override_resume_clarify_rejects_wrong_state(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    # State is initialized — not awaiting_human
    state = megaplan._core.read_json(plan_dir / "state.json")
    assert state["current_state"] == "initialized"

    with pytest.raises(megaplan.CliError, match="resume-clarify requires state"):
        megaplan.handle_override(
            root,
            _make_args(
                plan_name,
                project_dir,
                plan=plan_name,
                override_action="resume-clarify",
            ),
        )


# (h) [defaults] prep_clarify=false makes a fresh init disable clarify absent the CLI flag
def test_init_prep_clarify_defaults_to_true_when_absent(
    tmp_path: Path, monkeypatch
) -> None:
    """Fresh init without --no-prep-clarify should leave prep_clarify absent (= True)."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

    init_response = megaplan.handle_init(root, _make_args(None, project_dir))
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name
    state = megaplan._core.read_json(plan_dir / "state.json")

    # prep_clarify should be absent (meaning True via .get("prep_clarify", True))
    assert "prep_clarify" not in state["config"]


def test_init_prep_clarify_false_via_no_prep_clarify_flag(
    tmp_path: Path, monkeypatch
) -> None:
    """--no-prep-clarify flag must write prep_clarify=False to config."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

    init_response = megaplan.handle_init(
        root, _make_args(None, project_dir, prep_clarify=False)
    )
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name
    state = megaplan._core.read_json(plan_dir / "state.json")

    assert state["config"].get("prep_clarify") is False
