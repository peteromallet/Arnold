from __future__ import annotations

import pickle
from pathlib import Path
import queue
import threading
from typing import Any
from unittest.mock import patch

import pytest

from megaplan.orchestration import prep_research
from megaplan.types import CliError, PlanState
from megaplan.workers import WorkerResult


def _slow_research_child(payload: dict[str, Any], out_queue: Any) -> None:
    del payload, out_queue
    import time

    time.sleep(5)


def _state(project_dir: Path) -> PlanState:
    return {
        "name": "prep-test",
        "idea": "research the safe prep path",
        "current_state": "initialized",
        "iteration": 0,
        "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": str(project_dir), "robustness": "standard"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"total_cost_usd": 0.0, "notes": []},
        "last_gate": {},
    }


@pytest.mark.parametrize(
    ("stage", "spec", "expected_agent"),
    [
        ("triage", "claude:low", "claude"),
        ("triage", "shannon:claude-opus-4-7", "shannon"),
        ("distill", "codex:gpt-5.4", "codex"),
        ("fanout", "hermes:deepseek:deepseek-v4-pro", "hermes"),
    ],
)
def test_explicit_read_only_prep_models_are_accepted(
    tmp_path: Path, stage: str, spec: str, expected_agent: str
) -> None:
    state = _state(tmp_path)
    state["config"]["prep_models"] = {stage: spec}

    resolved = prep_research.resolve_prep_stage_model(state, stage)

    assert resolved.agent == expected_agent


@pytest.mark.parametrize(
    ("stage", "spec"),
    [
        ("triage", "openai:gpt-5"),
        ("fanout", "fireworks:accounts/fireworks/models/deepseek-v3"),
    ],
)
def test_explicit_non_read_only_prep_models_are_rejected(
    tmp_path: Path, stage: str, spec: str
) -> None:
    state = _state(tmp_path)
    state["config"]["prep_models"] = {stage: spec}

    with pytest.raises(CliError) as exc_info:
        prep_research.resolve_prep_stage_model(state, stage)

    assert exc_info.value.code == "invalid_prep_model"
    assert f"prep_models.{stage}" in exc_info.value.message


def test_scatter_over_worker_step_is_picklable_with_representative_payload(tmp_path: Path) -> None:
    state = _state(tmp_path)
    unit = {
        "area": {"id": "a", "area": "Area A", "brief": "inspect A", "suggested_files": ["src/a.py"]},
        "state": state,
        "plan_dir": str(tmp_path / "plan"),
        "root": str(tmp_path),
        "resolved_model_spec": "claude:low",
    }

    encoded = pickle.dumps((prep_research.scatter_over_worker_step, unit))
    decoded_fn, decoded_unit = pickle.loads(encoded)

    assert decoded_fn is prep_research.scatter_over_worker_step
    assert decoded_unit == unit
    process_encoded = pickle.dumps((prep_research.scatter_over_worker_step_process, unit))
    process_fn, process_unit = pickle.loads(process_encoded)
    assert process_fn is prep_research.scatter_over_worker_step_process
    assert process_unit == unit


@pytest.mark.parametrize(
    ("resolved_model_spec", "expected_agent", "expected_model", "expected_effort"),
    [
        ("hermes:deepseek:deepseek-v4-pro", "hermes", "deepseek:deepseek-v4-pro", None),
        ("codex:gpt-5.4:medium", "codex", "gpt-5.4", "medium"),
        ("claude:low", "claude", None, "low"),
        ("shannon:claude-opus-4-7", "shannon", "claude-opus-4-7", None),
    ],
)
def test_scatter_over_worker_step_dispatches_read_only_and_normalizes_payload(
    tmp_path: Path,
    resolved_model_spec: str,
    expected_agent: str,
    expected_model: str | None,
    expected_effort: str | None,
) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    area = {
        "id": "a",
        "area": "Area A",
        "brief": "Inspect files",
        "suggested_files": ["src/a.py"],
    }
    unit = {
        "area": area,
        "state": state,
        "plan_dir": str(plan_dir),
        "root": str(tmp_path),
        "resolved_model_spec": resolved_model_spec,
    }
    worker = WorkerResult(
        payload={
            "area": "",
            "brief": "",
            "status": "complete",
            "findings": "first finding\nsecond finding",
            "files": {"src/a.py": "read"},
            "code_refs": "pkg.a, pkg.b",
            "confidence": "high",
            "error": "",
        },
        raw_output="research",
        duration_ms=17,
        cost_usd=0.2,
        session_id="research-session",
        prompt_tokens=5,
        completion_tokens=8,
        total_tokens=13,
    )

    with (
        patch.object(prep_research, "_prep_research_prompt", return_value="research prompt") as prompt_fn,
        patch.object(
            prep_research,
            "run_step_with_worker",
            return_value=(worker, expected_agent, "ephemeral", True),
        ) as run_step,
    ):
        index, payload, cost, pt, ct, tt = prep_research.scatter_over_worker_step(3, unit)

    assert index == 3
    assert payload == {
        "finding": {
            "area": "a",
            "brief": "Inspect files",
            "status": "complete",
            "findings": ["first finding", "second finding"],
            "files": ["src/a.py"],
            "code_refs": ["pkg.a", "pkg.b"],
            "confidence": "high",
            "error": "",
        },
        "metrics": {
            "area": "a",
            "status": "complete",
            "elapsed_time_ms": 17,
            "files": ["src/a.py"],
            "code_refs": ["pkg.a", "pkg.b"],
        },
    }
    assert (cost, pt, ct, tt) == (0.2, 5, 8, 13)
    prompt_fn.assert_called_once_with(
        state,
        plan_dir,
        area=area,
        output_path=plan_dir / ".hermes_state" / "prep_research_3.json",
        root=tmp_path,
    )
    run_step.assert_called_once()
    assert run_step.call_args.args[:4] == (
        "prep-research",
        state,
        plan_dir,
        prep_research._prep_worker_args(),
    )
    assert run_step.call_args.kwargs["root"] == tmp_path
    assert run_step.call_args.kwargs["prompt_override"] == "research prompt"
    assert run_step.call_args.kwargs["read_only"] is True
    resolved = run_step.call_args.kwargs["resolved"]
    assert resolved.agent == expected_agent
    assert resolved.model == expected_model
    assert resolved.effort == expected_effort


def test_run_prep_triage_dispatches_via_worker_read_only_and_updates_session(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    resolved = prep_research.AgentMode(
        agent="codex",
        mode="ephemeral",
        refreshed=True,
        model="gpt-5.4",
        effort="medium",
        resolved_model="gpt-5.4",
    )
    worker = WorkerResult(
        payload={"triage_framing": "Investigate", "areas": []},
        raw_output="triage",
        duration_ms=10,
        cost_usd=0.1,
        session_id="triage-session",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
    )

    with (
        patch.object(prep_research, "resolve_prep_stage_model", return_value=resolved),
        patch.object(prep_research, "_prep_triage_prompt", return_value="triage prompt"),
        patch.object(
            prep_research,
            "run_step_with_worker",
            return_value=(worker, "codex", "ephemeral", True),
        ) as run_step,
        patch.object(
            prep_research,
            "update_session_state",
            return_value=("prep-triage:codex", {"id": "triage-session", "mode": "ephemeral"}),
        ) as update_session,
    ):
        result = prep_research.run_prep_triage(state, plan_dir, root=tmp_path)

    assert result is worker
    assert run_step.call_args.args[:3] == ("prep-triage", state, plan_dir)
    args = run_step.call_args.args[3]
    assert args.ephemeral is True
    assert args.agent is None
    assert args.hermes is None
    assert args.phase_model == []
    assert run_step.call_args.kwargs["root"] == tmp_path
    assert run_step.call_args.kwargs["resolved"] is resolved
    assert run_step.call_args.kwargs["prompt_override"] == "triage prompt"
    assert run_step.call_args.kwargs["read_only"] is True
    update_session.assert_called_once_with(
        "prep-triage",
        "codex",
        "triage-session",
        mode="ephemeral",
        refreshed=True,
        model="gpt-5.4",
        existing_sessions=state["sessions"],
    )
    assert state["sessions"]["prep-triage:codex"] == {"id": "triage-session", "mode": "ephemeral"}


def test_distill_prep_dispatches_via_worker_and_normalizes_payload(tmp_path: Path) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    resolved = prep_research.AgentMode(
        agent="hermes",
        mode="ephemeral",
        refreshed=True,
        model="deepseek:deepseek-v4-pro",
        effort=None,
        resolved_model="deepseek:deepseek-v4-pro",
    )
    worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "summary",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "approach",
            "open_questions": [{"severity": "blocking", "question": "Which API?"}],
            "extra_field": "strip me",
        },
        raw_output="distill",
        duration_ms=10,
        cost_usd=0.2,
        session_id="distill-session",
        prompt_tokens=3,
        completion_tokens=4,
        total_tokens=7,
    )

    with (
        patch.object(prep_research, "resolve_prep_stage_model", return_value=resolved),
        patch.object(prep_research, "_prep_distill_prompt", return_value="distill prompt"),
        patch.object(
            prep_research,
            "run_step_with_worker",
            return_value=(worker, "hermes", "ephemeral", True),
        ) as run_step,
        patch.object(
            prep_research,
            "update_session_state",
            return_value=("prep-distill:hermes", {"id": "distill-session", "mode": "ephemeral"}),
        ) as update_session,
    ):
        result = prep_research.distill_prep(
            state,
            plan_dir,
            root=tmp_path,
            triage={"areas": []},
            findings=[],
        )

    assert result is worker
    assert run_step.call_args.args[:3] == ("prep-distill", state, plan_dir)
    assert run_step.call_args.kwargs["resolved"] is resolved
    assert run_step.call_args.kwargs["prompt_override"] == "distill prompt"
    assert run_step.call_args.kwargs["read_only"] is True
    update_session.assert_called_once_with(
        "prep-distill",
        "hermes",
        "distill-session",
        mode="ephemeral",
        refreshed=True,
        model="deepseek:deepseek-v4-pro",
        existing_sessions=state["sessions"],
    )
    assert result.payload == {
        "skip": False,
        "task_summary": "summary",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "approach",
        "open_questions": [{"severity": "blocking", "question": "Which API?"}],
    }
    assert state["sessions"]["prep-distill:hermes"] == {
        "id": "distill-session",
        "mode": "ephemeral",
    }


# ---------------------------------------------------------------------------
# T9: Triage/distill dispatch across all read-only agents
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent", "model", "effort", "resolved_model"),
    [
        ("hermes", "deepseek:deepseek-v4-pro", None, "deepseek:deepseek-v4-pro"),
        ("codex", "gpt-5.4", "medium", "gpt-5.4"),
        ("claude", "claude-opus-4-7", None, "claude-opus-4-7"),
        ("shannon", "claude-opus-4-7", None, "claude-opus-4-7"),
    ],
)
def test_run_prep_triage_dispatches_for_all_read_only_agents(
    tmp_path: Path,
    agent: str,
    model: str,
    effort: str | None,
    resolved_model: str,
) -> None:
    """Triage dispatch must use read_only=True for every read-only agent family."""
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    resolved = prep_research.AgentMode(
        agent=agent,
        mode="ephemeral",
        refreshed=True,
        model=model,
        effort=effort,
        resolved_model=resolved_model,
    )
    worker = WorkerResult(
        payload={"triage_framing": "Investigate", "areas": []},
        raw_output="triage",
        duration_ms=10,
        cost_usd=0.1,
        session_id="triage-session",
        prompt_tokens=50,
        completion_tokens=60,
        total_tokens=110,
    )
    session_key = f"prep-triage:{agent}"
    session_entry = {"id": "triage-session", "mode": "ephemeral"}

    with (
        patch.object(prep_research, "resolve_prep_stage_model", return_value=resolved),
        patch.object(prep_research, "_prep_triage_prompt", return_value="triage prompt"),
        patch.object(
            prep_research,
            "run_step_with_worker",
            return_value=(worker, agent, "ephemeral", True),
        ) as run_step,
        patch.object(
            prep_research,
            "update_session_state",
            return_value=(session_key, session_entry),
        ) as update_session,
    ):
        result = prep_research.run_prep_triage(state, plan_dir, root=tmp_path)

    assert result is worker
    assert run_step.call_args.args[:3] == ("prep-triage", state, plan_dir)
    assert run_step.call_args.kwargs["resolved"] is resolved
    assert run_step.call_args.kwargs["prompt_override"] == "triage prompt"
    assert run_step.call_args.kwargs["read_only"] is True
    update_session.assert_called_once_with(
        "prep-triage",
        agent,
        "triage-session",
        mode="ephemeral",
        refreshed=True,
        model=resolved_model,
        existing_sessions=state["sessions"],
    )
    assert state["sessions"][session_key] == session_entry
    # Cost accounting: worker preserves cost/token fields unmodified
    assert result.cost_usd == 0.1
    assert result.prompt_tokens == 50
    assert result.completion_tokens == 60
    assert result.total_tokens == 110


@pytest.mark.parametrize(
    ("agent", "model", "effort", "resolved_model"),
    [
        ("hermes", "deepseek:deepseek-v4-pro", None, "deepseek:deepseek-v4-pro"),
        ("codex", "gpt-5.4", "medium", "gpt-5.4"),
        ("claude", "claude-opus-4-7", None, "claude-opus-4-7"),
        ("shannon", "claude-opus-4-7", None, "claude-opus-4-7"),
    ],
)
def test_distill_prep_dispatches_for_all_read_only_agents_and_normalizes_payload(
    tmp_path: Path,
    agent: str,
    model: str,
    effort: str | None,
    resolved_model: str,
) -> None:
    """Distill dispatch must use read_only=True and apply _compatible_prep_payload for every agent."""
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    resolved = prep_research.AgentMode(
        agent=agent,
        mode="ephemeral",
        refreshed=True,
        model=model,
        effort=effort,
        resolved_model=resolved_model,
    )
    worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "summary",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "approach",
            "open_questions": [{"severity": "blocking", "question": "Which API?"}],
            "extra_field": "strip me",
        },
        raw_output="distill",
        duration_ms=10,
        cost_usd=0.2,
        session_id="distill-session",
        prompt_tokens=70,
        completion_tokens=80,
        total_tokens=150,
    )
    session_key = f"prep-distill:{agent}"
    session_entry = {"id": "distill-session", "mode": "ephemeral"}

    with (
        patch.object(prep_research, "resolve_prep_stage_model", return_value=resolved),
        patch.object(prep_research, "_prep_distill_prompt", return_value="distill prompt"),
        patch.object(
            prep_research,
            "run_step_with_worker",
            return_value=(worker, agent, "ephemeral", True),
        ) as run_step,
        patch.object(
            prep_research,
            "update_session_state",
            return_value=(session_key, session_entry),
        ) as update_session,
    ):
        result = prep_research.distill_prep(
            state,
            plan_dir,
            root=tmp_path,
            triage={"areas": []},
            findings=[],
        )

    assert run_step.call_args.args[:3] == ("prep-distill", state, plan_dir)
    assert run_step.call_args.kwargs["resolved"] is resolved
    assert run_step.call_args.kwargs["prompt_override"] == "distill prompt"
    assert run_step.call_args.kwargs["read_only"] is True
    update_session.assert_called_once_with(
        "prep-distill",
        agent,
        "distill-session",
        mode="ephemeral",
        refreshed=True,
        model=resolved_model,
        existing_sessions=state["sessions"],
    )
    assert state["sessions"][session_key] == session_entry
    # _compatible_prep_payload must strip extra_field but preserve open_questions
    assert result.payload == {
        "skip": False,
        "task_summary": "summary",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "approach",
        "open_questions": [{"severity": "blocking", "question": "Which API?"}],
    }
    # Cost accounting: worker preserves cost/token fields unmodified
    assert result.cost_usd == 0.2
    assert result.prompt_tokens == 70
    assert result.completion_tokens == 80
    assert result.total_tokens == 150


# ---------------------------------------------------------------------------
# T9(g): prep_triage.json / prep.json artifact payload compatibility
# ---------------------------------------------------------------------------


def test_run_prep_orchestration_writes_compatible_prep_triage_json(
    tmp_path: Path,
) -> None:
    """prep_triage.json written by orchestration must contain the raw triage payload."""
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    triage_worker = WorkerResult(
        payload={
            "triage_framing": "Investigate areas.",
            "areas": [{"id": "a1", "area": "Area 1", "brief": "first"}],
        },
        raw_output="triage",
        duration_ms=10,
        cost_usd=0.1,
        session_id="triage-session",
        prompt_tokens=50,
        completion_tokens=60,
        total_tokens=110,
    )
    distill_worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "summary",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "approach",
            "open_questions": [],
        },
        raw_output="distill",
        duration_ms=20,
        cost_usd=0.2,
        session_id="distill-session",
        prompt_tokens=70,
        completion_tokens=80,
        total_tokens=150,
    )
    fanout_result = prep_research.GenericScatterResult(
        ordered_results=[
            {
                "area": "a1",
                "brief": "first",
                "status": "complete",
                "findings": ["found"],
                "files": [],
                "code_refs": [],
                "confidence": "high",
                "error": "",
            },
        ],
        total_cost=0.0,
        total_prompt_tokens=0,
        total_completion_tokens=0,
        total_tokens=0,
        side_results=[
            {"area": "a1", "status": "complete", "elapsed_time_ms": 30, "files": [], "code_refs": []},
        ],
    )

    with (
        patch.object(prep_research, "run_prep_triage", return_value=triage_worker),
        patch.object(prep_research, "run_research_fanout", return_value=fanout_result),
        patch.object(prep_research, "distill_prep", return_value=distill_worker),
    ):
        prep_research.run_prep_orchestration(state, plan_dir, root=tmp_path)

    triage_json = prep_research.json.loads(
        (plan_dir / "prep_triage.json").read_text(encoding="utf-8")
    )
    assert triage_json == triage_worker.payload
    assert triage_json["triage_framing"] == "Investigate areas."
    assert len(triage_json["areas"]) == 1


def test_run_prep_orchestration_writes_compatible_prep_json(
    tmp_path: Path,
) -> None:
    """prep.json written by orchestration must contain only PREP_COMPATIBLE_KEYS."""
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    triage_worker = WorkerResult(
        payload={
            "triage_framing": "Investigate.",
            "areas": [{"id": "a1", "area": "Area 1", "brief": "first"}],
        },
        raw_output="triage",
        duration_ms=10,
        cost_usd=0.1,
        session_id="triage-session",
        prompt_tokens=50,
        completion_tokens=60,
        total_tokens=110,
    )
    distill_worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "summary",
            "key_evidence": [{"point": "evidence", "source": "research", "relevance": "high"}],
            "relevant_code": [
                {"file_path": "a.py", "why": "important", "functions": ["f"]}
            ],
            "test_expectations": [
                {"test_id": "t.py", "what_it_checks": "x", "status": "pass_to_pass"}
            ],
            "constraints": ["no writes"],
            "suggested_approach": "use read_only",
            "open_questions": [{"severity": "blocking", "question": "Q?"}],
            # Extra key not in PREP_COMPATIBLE_KEYS
            "extra_field": "should be stripped",
        },
        raw_output="distill",
        duration_ms=20,
        cost_usd=0.2,
        session_id="distill-session",
        prompt_tokens=70,
        completion_tokens=80,
        total_tokens=150,
    )
    fanout_result = prep_research.GenericScatterResult(
        ordered_results=[
            {
                "area": "a1",
                "brief": "first",
                "status": "complete",
                "findings": ["found"],
                "files": [],
                "code_refs": [],
                "confidence": "high",
                "error": "",
            },
        ],
        total_cost=0.0,
        total_prompt_tokens=0,
        total_completion_tokens=0,
        total_tokens=0,
        side_results=[
            {"area": "a1", "status": "complete", "elapsed_time_ms": 30, "files": [], "code_refs": []},
        ],
    )

    with (
        patch.object(prep_research, "run_prep_triage", return_value=triage_worker),
        patch.object(prep_research, "run_research_fanout", return_value=fanout_result),
        patch.object(prep_research, "distill_prep", return_value=distill_worker),
    ):
        prep_research.run_prep_orchestration(state, plan_dir, root=tmp_path)

    prep_json = prep_research.json.loads(
        (plan_dir / "prep.json").read_text(encoding="utf-8")
    )
    # Only PREP_COMPATIBLE_KEYS survive
    for key in prep_json:
        assert key in prep_research.PREP_COMPATIBLE_KEYS, f"prep.json key {key!r} not in PREP_COMPATIBLE_KEYS"
    assert "extra_field" not in prep_json
    assert prep_json["open_questions"] == [{"severity": "blocking", "question": "Q?"}]
    assert prep_json["constraints"] == ["no writes"]
    assert prep_json["suggested_approach"] == "use read_only"


def test_run_prep_orchestration_tracks_aggregate_cost_and_tokens(
    tmp_path: Path,
) -> None:
    """Orchestration WorkerResult must aggregate cost/tokens across triage+fanout+distill."""
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    triage_worker = WorkerResult(
        payload={
            "triage_framing": "Investigate.",
            "areas": [{"id": "a1", "area": "Area 1", "brief": "first"}],
        },
        raw_output="triage",
        duration_ms=100,
        cost_usd=0.10,
        session_id="triage-session",
        prompt_tokens=100,
        completion_tokens=200,
        total_tokens=300,
    )
    fanout_result = prep_research.GenericScatterResult(
        ordered_results=[
            {
                "area": "a1",
                "brief": "first",
                "status": "complete",
                "findings": ["found"],
                "files": [],
                "code_refs": [],
                "confidence": "high",
                "error": "",
            },
        ],
        total_cost=0.20,
        total_prompt_tokens=400,
        total_completion_tokens=500,
        total_tokens=900,
        side_results=[
            {"area": "a1", "status": "complete", "elapsed_time_ms": 30, "files": [], "code_refs": []},
        ],
    )
    distill_worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "summary",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "approach",
        },
        raw_output="distill",
        duration_ms=50,
        cost_usd=0.05,
        session_id="distill-session",
        prompt_tokens=50,
        completion_tokens=60,
        total_tokens=110,
    )

    with (
        patch.object(prep_research, "run_prep_triage", return_value=triage_worker),
        patch.object(prep_research, "run_research_fanout", return_value=fanout_result),
        patch.object(prep_research, "distill_prep", return_value=distill_worker),
    ):
        result = prep_research.run_prep_orchestration(state, plan_dir, root=tmp_path)

    # Aggregate cost
    assert result.worker.cost_usd == pytest.approx(0.10 + 0.20 + 0.05)
    # Aggregate tokens
    assert result.worker.prompt_tokens == 100 + 400 + 50
    assert result.worker.completion_tokens == 200 + 500 + 60
    assert result.worker.total_tokens == 300 + 900 + 110
    # metrics on disk
    metrics = prep_research.json.loads(
        (plan_dir / "prep_metrics.json").read_text(encoding="utf-8")
    )
    assert metrics["total_cost_usd"] == pytest.approx(0.35)
    assert metrics["prompt_tokens"] == 550
    assert metrics["completion_tokens"] == 760
    assert metrics["total_tokens"] == 1310


@pytest.mark.parametrize(
    "fanout_model_spec",
    [
        "hermes:deepseek:deepseek-v4-pro",
        "codex:gpt-5.4:medium",
        "claude:low",
        "shannon:claude-opus-4-7",
    ],
)
def test_fanout_research_uses_vendor_agnostic_process_path_and_preserves_ordered_sentinels(
    tmp_path: Path,
    fanout_model_spec: str,
) -> None:
    state = _state(tmp_path)
    state["config"]["prep_models"] = {"fanout": fanout_model_spec}
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    areas = [
        {"id": "a", "area": "A", "brief": "first", "suggested_files": []},
        {"id": "b", "area": "B", "brief": "second", "suggested_files": []},
        {"id": "c", "area": "C", "brief": "third", "suggested_files": []},
    ]
    expected_model_spec = prep_research._prep_stage_agent_spec(
        prep_research.resolve_prep_stage_model(state, "fanout")
    )

    def fake_scatter_processes(**kwargs: Any) -> prep_research.GenericScatterResult:
        assert kwargs["run_unit_fn"] is prep_research.scatter_over_worker_step_process
        assert kwargs["timeout_seconds"] == 1.0
        assert kwargs["max_concurrent"] == 3
        assert "submit_unit_fn" not in kwargs
        assert "side_tasks" not in kwargs
        units = kwargs["units"]
        assert [unit["area"]["id"] for unit in units] == ["a", "b", "c"]
        assert all(unit["resolved_model_spec"] == expected_model_spec for unit in units)
        ordered_results: list[dict[str, Any]] = []
        total_cost = 0.0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0
        for index, unit in enumerate(units):
            if index == 1:
                payload, cost_usd, pt, ct, tt = kwargs["on_unit_error"](index, RuntimeError("unit failed"))
            elif index == 2:
                payload, cost_usd, pt, ct, tt = kwargs["on_unit_error"](index, TimeoutError("took too long"))
            else:
                finding = {
                    "area": unit["area"]["id"],
                    "brief": unit["area"]["brief"],
                    "status": "complete",
                    "findings": [f"finding-{index}"],
                    "files": [f"src/{unit['area']['id']}.py"],
                    "code_refs": [f"pkg.{unit['area']['id']}"],
                    "confidence": "high",
                    "error": "",
                }
                payload = prep_research._research_unit_payload(finding, elapsed_time_ms=11)
                cost_usd, pt, ct, tt = 0.25, 3, 4, 7
            ordered_results.append(payload)
            total_cost += cost_usd
            total_prompt_tokens += pt
            total_completion_tokens += ct
            total_tokens += tt
        return prep_research.GenericScatterResult(
            ordered_results=ordered_results,
            total_cost=total_cost,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_tokens=total_tokens,
            side_results=[],
        )

    with (
        patch.object(prep_research, "scatter_gather_processes", side_effect=fake_scatter_processes),
        patch("megaplan._core.hermes_fanout.scatter_gather", side_effect=AssertionError("old thread fanout path should not be used")),
    ):
        result = prep_research.run_research_fanout(
            state,
            plan_dir,
            root=tmp_path,
            areas=areas,
            timeout_seconds=1.0,
            max_concurrent=3,
        )

    assert [item["area"] for item in result.ordered_results] == ["a", "b", "c"]
    assert result.ordered_results[1]["status"] == "error"
    assert result.ordered_results[1]["error"] == "unit failed"
    assert result.ordered_results[2]["status"] == "timed_out"
    assert result.ordered_results[2]["error"] == "research timeout"
    assert result.total_cost == 0.25
    assert result.total_prompt_tokens == 3
    assert result.total_completion_tokens == 4
    assert result.total_tokens == 7
    assert result.side_results[0]["files"] == ["src/a.py"]
    assert result.side_results[1]["status"] == "error"
    assert result.side_results[2]["status"] == "timed_out"


def test_run_prep_orchestration_caps_fanout_writes_dossier_and_returns_worker(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state["config"]["robustness"] = "full"
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (tmp_path / "megaplan").mkdir()
    (tmp_path / "megaplan" / "a.py").write_text("def a():\n    pass\n", encoding="utf-8")
    (tmp_path / "megaplan" / "b.py").write_text("def b():\n    pass\n", encoding="utf-8")
    (tmp_path / "megaplan" / "orchestration").mkdir()
    (tmp_path / "megaplan" / "orchestration" / "prep_research.py").write_text(
        "def run():\n    pass\n",
        encoding="utf-8",
    )
    areas = [
        {"id": f"a{index}", "area": f"Area {index}", "brief": f"brief {index}"}
        for index in range(6)
    ]
    triage_worker = WorkerResult(
        payload={"triage_framing": "Investigate bounded areas.", "areas": areas},
        raw_output="triage",
        duration_ms=10,
        cost_usd=0.1,
        session_id="triage-session",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
    )
    fanout_result = prep_research.GenericScatterResult(
        ordered_results=[
            {
                "area": "a0",
                "brief": "b0",
                "status": "complete",
                "findings": ["f0"],
                "files": ["megaplan/a.py"],
                "code_refs": ["pkg.a0"],
                "confidence": "high",
                "error": "",
            },
            {
                "area": "a1",
                "brief": "b1",
                "status": "partial",
                "findings": ["f1"],
                "files": ["megaplan/a.py", "megaplan/b.py"],
                "code_refs": ["pkg.a1"],
                "confidence": "medium",
                "error": "",
            },
            {
                "area": "a2",
                "brief": "b2",
                "status": "timed_out",
                "findings": [],
                "files": [],
                "code_refs": [],
                "confidence": "low",
                "error": "slow",
            },
            {
                "area": "a3",
                "brief": "b3",
                "status": "error",
                "findings": [],
                "files": [],
                "code_refs": [],
                "confidence": "low",
                "error": "bad",
            },
        ],
        total_cost=0.2,
        total_prompt_tokens=3,
        total_completion_tokens=4,
        total_tokens=7,
        side_results=[
            {"area": "a0", "status": "complete", "elapsed_time_ms": 30, "files": ["megaplan/a.py"], "code_refs": ["pkg.a0"]},
            {"area": "a1", "status": "partial", "elapsed_time_ms": 40, "files": ["megaplan/a.py", "megaplan/b.py"], "code_refs": ["pkg.a1"]},
            {"area": "a2", "status": "timed_out", "elapsed_time_ms": 50, "files": [], "code_refs": []},
            {"area": "a3", "status": "error", "elapsed_time_ms": 60, "files": [], "code_refs": []},
        ],
    )
    distill_worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "summary",
            "key_evidence": [{"point": "evidence", "source": "research", "relevance": "high"}],
            "relevant_code": [
                {
                    "file_path": "megaplan/orchestration/prep_research.py",
                    "why": "final assembly",
                    "functions": ["run_prep_orchestration"],
                }
            ],
            "test_expectations": [
                {
                    "test_id": "tests/test_prep_research.py",
                    "what_it_checks": "prep orchestration sidecars",
                    "status": "pass_to_pass",
                }
            ],
            "constraints": [],
            "suggested_approach": "approach",
        },
        raw_output="distill",
        duration_ms=20,
        cost_usd=0.3,
        session_id="distill-session",
        prompt_tokens=5,
        completion_tokens=6,
        total_tokens=11,
    )

    with (
        patch.object(prep_research, "run_prep_triage", return_value=triage_worker),
        patch.object(prep_research, "run_research_fanout", return_value=fanout_result) as fanout,
        patch.object(prep_research, "distill_prep", return_value=distill_worker),
    ):
        result = prep_research.run_prep_orchestration(state, plan_dir, root=tmp_path)

    fanout.assert_called_once()
    assert [area["id"] for area in fanout.call_args.kwargs["areas"]] == ["a0", "a1", "a2", "a3"]
    assert result.worker.payload["task_summary"] == "summary"
    assert result.worker.cost_usd == pytest.approx(0.6)
    assert result.worker.prompt_tokens == 9
    assert result.worker.completion_tokens == 12
    assert result.worker.total_tokens == 21
    assert result.artifacts == [
        "prep.json",
        "prep_dossier.md",
        "prep_metrics.json",
        "prep_triage.json",
        "research.json",
    ]
    metrics = prep_research.json.loads((plan_dir / "prep_metrics.json").read_text(encoding="utf-8"))
    assert metrics["area_count"] == 6
    assert metrics["fanout_count"] == 4
    assert metrics["completed_count"] == 1
    assert metrics["partial_count"] == 1
    assert metrics["timed_out_count"] == 1
    assert metrics["error_count"] == 1
    assert metrics["missed_units"] == ["a2", "a3"]
    assert metrics["total_cost_usd"] == pytest.approx(0.6)
    assert metrics["prompt_tokens"] == 9
    assert metrics["completion_tokens"] == 12
    assert metrics["total_tokens"] == 21
    assert metrics["elapsed_time_ms"] == 210
    assert metrics["files"] == ["megaplan/a.py", "megaplan/b.py"]
    assert metrics["code_refs"] == ["pkg.a0", "pkg.a1"]
    assert [item["status"] for item in metrics["per_unit"]] == ["complete", "partial", "timed_out", "error"]
    assert metrics["gap_notes"] == [
        "a1: research returned partial coverage.",
        "a2: research timed out before the area could be closed.",
        "a3: research failed with bad.",
    ]
    assert metrics["contradiction_notes"] == [
        "file megaplan/a.py appears in multiple areas with differing evidence/status: a0=complete, a1=partial"
    ]
    assert metrics["overlap_groups"] == [
        {"kind": "file", "value": "megaplan/a.py", "areas": ["a0", "a1"]}
    ]
    assert metrics["cross_reference"] == {
        "performed": True,
        "checked_files": [
            "megaplan/a.py",
            "megaplan/b.py",
            "megaplan/orchestration/prep_research.py",
        ],
        "existing_files": [
            "megaplan/a.py",
            "megaplan/b.py",
            "megaplan/orchestration/prep_research.py",
        ],
        "missing_files": [],
        "shared_files": [],
        "to_be_built_files": [],
    }
    assert metrics["stage_metrics"]["triage"]["total_tokens"] == 3
    assert metrics["stage_metrics"]["fanout"]["total_tokens"] == 7
    assert metrics["stage_metrics"]["distill"]["total_tokens"] == 11
    dossier = (plan_dir / "prep_dossier.md").read_text(encoding="utf-8")
    assert "Investigate bounded areas." in dossier
    assert "a2 (timed_out)" in dossier
    assert "## Adjudication" in dossier
    assert "a2: research timed out before the area could be closed." in dossier
    assert "file megaplan/a.py appears in multiple areas with differing evidence/status" in dossier
    assert (plan_dir / "prep.json").exists()
    assert (plan_dir / "research.json").exists()


def test_research_unit_process_timeout_returns_sentinel_without_sibling_state(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    area = {"id": "slow", "area": "Slow", "brief": "times out", "suggested_files": []}

    index, unit_payload, cost, pt, ct, tt = prep_research.run_hermes_research_unit_process(
        index=0,
        area=area,
        state=state,
        plan_dir=plan_dir,
        root=tmp_path,
        model="deepseek:deepseek-v4-flash",
        timeout_seconds=0.05,
        hard_kill_grace_seconds=0.05,
        child_target=_slow_research_child,
    )

    assert index == 0
    assert unit_payload["finding"]["status"] == "timed_out"
    assert unit_payload["finding"]["error"] == "research timeout"
    assert unit_payload["metrics"]["status"] == "timed_out"
    assert (cost, pt, ct, tt) == (0.0, 0, 0, 0)


def test_research_child_watchdog_calls_child_local_interrupt(tmp_path: Path) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    out: queue.Queue = queue.Queue()
    interrupted: list[str] = []
    agents: list["FakeAgent"] = []

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAgent:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs
            agents.append(self)

        def interrupt(self, message: str) -> None:
            interrupted.append(message)

        def run_conversation(self, user_message: str, **kwargs: Any) -> dict[str, Any]:
            del kwargs
            import time

            time.sleep(0.08)
            return {
                "final_response": '{"area":"a","brief":"b","status":"complete","findings":[],"files":[],"code_refs":[],"confidence":"high","error":""}',
                "estimated_cost_usd": 0.1,
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "total_tokens": 3,
            }

    payload = {
        "index": 0,
        "area": {"id": "a", "area": "A", "brief": "b", "suggested_files": []},
        "state": state,
        "plan_dir": str(plan_dir),
        "root": str(tmp_path),
        "model": "deepseek:deepseek-v4-flash",
        "timeout_seconds": 0.01,
        "max_iterations": 7,
    }

    with patch.object(prep_research, "_import_hermes_runtime", return_value=(FakeAgent, FakeSessionDB)):
        prep_research._run_research_child(payload, out)

    result = out.get_nowait()
    assert result["ok"] is True
    assert interrupted == ["research timeout"]
    assert agents[0].kwargs["enabled_toolsets"] == ["file-readonly", "web"]
    assert agents[0].kwargs["max_iterations"] == 7
    assert agents[0].kwargs["session_id"]
    assert isinstance(agents[0].kwargs["session_db"], FakeSessionDB)


def test_research_child_timeout_interrupt_is_isolated_from_concurrent_sibling(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    out: queue.Queue = queue.Queue()
    released = threading.Event()
    interrupted: dict[int, list[str]] = {0: [], 1: []}

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAgent:
        def __init__(self, **kwargs: Any):
            self.index = int(str(kwargs["session_id"]).split("-")[-1])

        def interrupt(self, message: str) -> None:
            interrupted[self.index].append(message)
            released.set()

        def run_conversation(self, user_message: str, **kwargs: Any) -> dict[str, Any]:
            del kwargs
            del user_message
            released.wait(timeout=1.0)
            return {
                "final_response": (
                    '{"area":"a","brief":"b","status":"complete",'
                    '"findings":[],"files":[],"code_refs":[],"confidence":"high","error":""}'
                ),
                "estimated_cost_usd": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

    payloads = [
        {
            "index": 0,
            "area": {"id": "slow", "area": "Slow", "brief": "times out", "suggested_files": []},
            "state": state,
            "plan_dir": str(plan_dir),
            "root": str(tmp_path),
            "model": "deepseek:deepseek-v4-flash",
            "timeout_seconds": 0.01,
            "max_iterations": 7,
        },
        {
            "index": 1,
            "area": {"id": "sibling", "area": "Sibling", "brief": "continues", "suggested_files": []},
            "state": state,
            "plan_dir": str(plan_dir),
            "root": str(tmp_path),
            "model": "deepseek:deepseek-v4-flash",
            "timeout_seconds": 1.0,
            "max_iterations": 7,
        },
    ]

    session_ids = iter(["session-0", "session-1"])

    with (
        patch.object(prep_research, "_import_hermes_runtime", return_value=(FakeAgent, FakeSessionDB)),
        patch.object(prep_research.uuid, "uuid4", side_effect=lambda: next(session_ids)),
    ):
        threads = [
            threading.Thread(target=prep_research._run_research_child, args=(payload, out))
            for payload in payloads
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)

    assert all(not thread.is_alive() for thread in threads)
    results = sorted((out.get_nowait() for _ in threads), key=lambda item: item["index"])
    assert [item["ok"] for item in results] == [True, True]
    assert interrupted[0] == ["research timeout"]
    assert interrupted[1] == []


def test_research_child_parse_failure_becomes_error_sentinel(tmp_path: Path) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    out: queue.Queue = queue.Queue()

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAgent:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

        def interrupt(self, message: str) -> None:
            del message

        def run_conversation(self, user_message: str, **kwargs: Any) -> dict[str, Any]:
            del kwargs
            del user_message
            return {
                "final_response": "not json",
                "messages": [{"role": "assistant", "content": "not json"}],
                "estimated_cost_usd": 0.0,
                "prompt_tokens": 2,
                "completion_tokens": 3,
                "total_tokens": 5,
            }

    payload = {
        "index": 0,
        "area": {"id": "a", "area": "A", "brief": "b", "suggested_files": []},
        "state": state,
        "plan_dir": str(plan_dir),
        "root": str(tmp_path),
        "model": "deepseek:deepseek-v4-flash",
        "timeout_seconds": 0.5,
        "max_iterations": 7,
    }

    with patch.object(prep_research, "_import_hermes_runtime", return_value=(FakeAgent, FakeSessionDB)):
        prep_research._run_research_child(payload, out)

    result = out.get_nowait()
    assert result["ok"] is False
    assert result["payload"]["finding"]["status"] == "error"
    assert "invalid json" in result["payload"]["finding"]["error"].lower()
    assert result["cost_usd"] == 0.0


def test_research_child_uses_parse_fallback_chain_and_keeps_metrics(tmp_path: Path) -> None:
    state = _state(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    out: queue.Queue = queue.Queue()

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAgent:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs
            self.calls: list[tuple[str, object]] = []

        def interrupt(self, message: str) -> None:
            del message

        def run_conversation(self, *, user_message: str, conversation_history: object = None, **kwargs: Any) -> dict[str, Any]:
            del kwargs
            self.calls.append((user_message, conversation_history))
            if len(self.calls) == 1:
                return {
                    "final_response": "",
                    "messages": [
                        {
                            "role": "assistant",
                            "tool_calls": [{"function": {"name": "read_file", "arguments": "{}"}}],
                        }
                    ],
                    "estimated_cost_usd": 0.42,
                    "prompt_tokens": 5,
                    "completion_tokens": 6,
                    "total_tokens": 11,
                }
            return {
                "final_response": (
                    '{"area":"a","brief":"b","status":"complete","findings":["f"],'
                    '"files":["megaplan/orchestration/prep_research.py"],'
                    '"code_refs":["prep_research.run_research_fanout"],'
                    '"confidence":"high","error":""}'
                ),
                "messages": [{"role": "assistant", "content": "{}"}],
                "estimated_cost_usd": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

    payload = {
        "index": 0,
        "area": {"id": "a", "area": "A", "brief": "b", "suggested_files": []},
        "state": state,
        "plan_dir": str(plan_dir),
        "root": str(tmp_path),
        "model": "deepseek:deepseek-v4-flash",
        "timeout_seconds": 0.5,
        "max_iterations": 7,
    }

    with patch.object(prep_research, "_import_hermes_runtime", return_value=(FakeAgent, FakeSessionDB)):
        prep_research._run_research_child(payload, out)

    result = out.get_nowait()
    assert result["ok"] is True
    assert result["payload"]["finding"]["status"] == "complete"
    assert result["payload"]["metrics"]["files"] == ["megaplan/orchestration/prep_research.py"]
    assert result["payload"]["metrics"]["code_refs"] == ["prep_research.run_research_fanout"]
    assert result["cost_usd"] == pytest.approx(0.42)
    assert result["prompt_tokens"] == 5
    assert result["completion_tokens"] == 6
    assert result["total_tokens"] == 11


# ---------------------------------------------------------------------------
# T12(g): _compatible_prep_payload preserves open_questions
# ---------------------------------------------------------------------------


def test_compatible_prep_payload_preserves_open_questions() -> None:
    """open_questions must survive the _compatible_prep_payload filter."""
    payload = {
        "skip": False,
        "task_summary": "summary",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "approach",
        "open_questions": [
            {"severity": "blocking", "question": "Which auth library?"},
            {"severity": "assume_and_proceed", "question": "Which cache?", "assumption": "Redis."},
        ],
        # Extra key not in PREP_COMPATIBLE_KEYS
        "extra_field": "should be stripped",
    }
    result = prep_research._compatible_prep_payload(payload)
    assert "open_questions" in result
    assert result["open_questions"] == payload["open_questions"]
    assert "extra_field" not in result
    # Verify other keys are preserved
    assert result["skip"] is False
    assert result["task_summary"] == "summary"


def test_compatible_prep_payload_handles_absent_open_questions() -> None:
    """Payload without open_questions should pass through unchanged (minus extra keys)."""
    payload = {
        "skip": False,
        "task_summary": "summary",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "approach",
    }
    result = prep_research._compatible_prep_payload(payload)
    assert "open_questions" not in result
    assert result["skip"] is False


# ---------------------------------------------------------------------------
# T5: forced upstream-summary prep research areas
# ---------------------------------------------------------------------------


def test_forced_upstream_areas_returns_empty_when_no_chain_policy() -> None:
    """No forced areas when state lacks chain_policy."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {"total_cost_usd": 0.0, "notes": []},
        "last_gate": {},
    }
    assert prep_research._forced_upstream_areas(state) == []


def test_forced_upstream_areas_returns_empty_when_not_plan_only() -> None:
    """No forced areas when contract_context has plan_only=False."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {
            "total_cost_usd": 0.0, "notes": [],
            "chain_policy": {
                "contract_context": {
                    "plan_only": False,
                    "dependency_labels": ["m1"],
                    "upstream_contracts": [
                        {
                            "milestone_label": "m1",
                            "provides": [{
                                "name": "P",
                                "interfaces": [{"symbol": "P.run", "path": "megaplan/p.py", "signature": "P.run()"}],
                            }],
                        }
                    ],
                },
            },
        },
        "last_gate": {},
    }
    assert prep_research._forced_upstream_areas(state) == []


def test_forced_upstream_areas_derives_one_area_per_dependency_label() -> None:
    """Each dependency_label becomes one forced area with upstream path context."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {
            "total_cost_usd": 0.0, "notes": [],
            "chain_policy": {
                "contract_context": {
                    "plan_only": True,
                    "dependency_labels": ["m1", "m2"],
                    "upstream_contracts": [
                        {
                            "milestone_label": "m1",
                            "provides": [{
                                "name": "Planner surface",
                                "interfaces": [
                                    {"symbol": "Planner.run", "path": "megaplan/planner.py", "signature": "Planner.run()"},
                                ],
                            }],
                        },
                        {
                            "milestone_label": "m2",
                            "provides": [{
                                "name": "Executor surface",
                                "interfaces": [
                                    {"symbol": "Executor.run", "path": "megaplan/executor.py", "signature": "Executor.run()"},
                                ],
                            }],
                        },
                    ],
                },
            },
        },
        "last_gate": {},
    }
    forced = prep_research._forced_upstream_areas(state)
    assert len(forced) == 2
    assert forced[0]["id"] == "upstream-m1"
    assert "megaplan/planner.py" in forced[0]["suggested_files"]
    assert forced[1]["id"] == "upstream-m2"
    assert "megaplan/executor.py" in forced[1]["suggested_files"]
    # Deduplication within forced areas
    state["meta"]["chain_policy"]["contract_context"]["dependency_labels"] = ["m1", "m1", "m2"]
    deduped = prep_research._forced_upstream_areas(state)
    assert len(deduped) == 2
    assert [a["id"] for a in deduped] == ["upstream-m1", "upstream-m2"]


def test_deduplicate_areas_keeps_forced_first_and_drops_duplicate_ids() -> None:
    """Forced areas appear first; triage areas with same id are dropped."""
    forced = [{"id": "f1", "area": "forced-1"}, {"id": "f2", "area": "forced-2"}]
    triage = [{"id": "t1", "area": "triage-1"}, {"id": "f1", "area": "triage-f1-dup"}, {"id": "t2", "area": "triage-2"}]
    merged = prep_research._deduplicate_areas(forced, triage)
    ids = [a.get("id") for a in merged]
    assert ids == ["f1", "f2", "t1", "t2"]


def test_cap_research_areas_retains_forced_when_forced_count_exceeds_cap(tmp_path: Path) -> None:
    """When forced_count >= cap, all slots go to forced areas; triage is culled."""
    state = _state(tmp_path)
    state["config"]["robustness"] = "light"  # cap = 2
    areas = [
        {"id": "forced-a", "area": "FA"},
        {"id": "forced-b", "area": "FB"},
        {"id": "forced-c", "area": "FC"},  # 3 forced
        {"id": "triage-a", "area": "TA"},
    ]
    capped, cap = prep_research._cap_research_areas(state, areas, forced_count=3)
    assert cap == 2
    assert len(capped) == 3  # all forced areas retained, triage dropped
    assert [a["id"] for a in capped] == ["forced-a", "forced-b", "forced-c"]


def test_cap_research_areas_normal_cap_when_forced_fewer_than_cap(tmp_path: Path) -> None:
    """When forced_count < cap, normal slicing applies to merged areas."""
    state = _state(tmp_path)
    state["config"]["robustness"] = "full"  # cap = 4
    areas = [
        {"id": "forced-a", "area": "FA"},
        {"id": "triage-a", "area": "TA"},
        {"id": "triage-b", "area": "TB"},
        {"id": "triage-c", "area": "TC"},
        {"id": "triage-d", "area": "TD"},
    ]
    capped, cap = prep_research._cap_research_areas(state, areas, forced_count=1)
    assert cap == 4
    assert len(capped) == 4
    assert capped[0]["id"] == "forced-a"


def test_prep_metrics_includes_forced_count() -> None:
    """_prep_metrics records forced_count in the returned dict."""
    fanout = prep_research.GenericScatterResult(
        ordered_results=[],
        total_cost=0.0,
        total_prompt_tokens=0,
        total_completion_tokens=0,
        total_tokens=0,
        side_results=[],
    )
    triage = WorkerResult(
        payload={}, raw_output="", duration_ms=0, cost_usd=0.0,
        session_id="s", prompt_tokens=0, completion_tokens=0, total_tokens=0,
    )
    distill = WorkerResult(
        payload={}, raw_output="", duration_ms=0, cost_usd=0.0,
        session_id="s", prompt_tokens=0, completion_tokens=0, total_tokens=0,
    )
    metrics = prep_research._prep_metrics(
        original_area_count=5,
        capped_area_count=3,
        forced_count=2,
        findings=[],
        fanout=fanout,
        triage_worker=triage,
        distill_worker=distill,
    )
    assert metrics["forced_count"] == 2
    assert metrics["area_count"] == 5
    assert metrics["fanout_count"] == 3


def test_minimal_prep_metrics_has_forced_count() -> None:
    """minimal_prep_metrics includes forced_count=0."""
    metrics = prep_research.minimal_prep_metrics()
    assert "forced_count" in metrics
    assert metrics["forced_count"] == 0


# ---------------------------------------------------------------------------
# T6: upstream-provided path cross-reference classification
# ---------------------------------------------------------------------------


def test_collect_upstream_provided_paths_returns_path_map() -> None:
    """_collect_upstream_provided_paths maps interface paths to milestone labels."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {
            "total_cost_usd": 0.0, "notes": [],
            "chain_policy": {
                "contract_context": {
                    "plan_only": True,
                    "dependency_labels": ["m1"],
                    "upstream_contracts": [
                        {
                            "milestone_label": "m1",
                            "provides": [{
                                "name": "Planner surface",
                                "interfaces": [
                                    {"symbol": "Planner.run", "path": "megaplan/planner.py", "signature": "Planner.run()"},
                                    {"symbol": "Planner.init", "path": "megaplan/init.py", "signature": "Planner.init()"},
                                ],
                            }],
                        },
                    ],
                },
            },
        },
        "last_gate": {},
    }
    paths = prep_research._collect_upstream_provided_paths(state)
    assert paths == {"megaplan/planner.py": "m1", "megaplan/init.py": "m1"}


def test_collect_upstream_provided_paths_returns_empty_without_policy() -> None:
    """_collect_upstream_provided_paths returns empty dict when plan_only is not True."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": "/tmp", "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {"total_cost_usd": 0.0, "notes": []},
        "last_gate": {},
    }
    assert prep_research._collect_upstream_provided_paths(state) == {}


def test_cross_reference_classifies_upstream_paths_as_to_be_built(tmp_path: Path) -> None:
    """Upstream-provided paths appear in to_be_built_files and are excluded from missing_files."""
    # Create a file that exists locally
    (tmp_path / "megaplan").mkdir(parents=True)
    (tmp_path / "megaplan" / "existing.py").write_text("# exists")

    findings = [
        {
            "area": "a", "brief": "b", "status": "complete",
            "findings": ["f"], "files": ["megaplan/upstream.py", "megaplan/existing.py"],
            "code_refs": [], "confidence": "high", "error": "",
        }
    ]
    prep_payload: dict[str, Any] = {
        "relevant_code": [{"file_path": "megaplan/missing.py"}],
    }
    upstream_paths = {"megaplan/upstream.py": "m1"}

    cr = prep_research._cross_reference_prep_output(
        root=tmp_path,
        findings=findings,
        prep_payload=prep_payload,
        upstream_provided_paths=upstream_paths,
    )
    assert cr["performed"] is True
    assert "megaplan/upstream.py" in cr["checked_files"]
    # upstream.py should be to-be-built, NOT missing
    assert "megaplan/upstream.py" not in cr["missing_files"]
    to_be_built = {(item["path"], item["upstream_milestone"]) for item in cr["to_be_built_files"]}
    assert ("megaplan/upstream.py", "m1") in to_be_built
    # existing.py exists locally → in existing_files
    assert "megaplan/existing.py" in cr["existing_files"]
    # missing.py doesn't exist and isn't upstream → missing
    assert "megaplan/missing.py" in cr["missing_files"]


def test_cross_reference_only_uses_declared_dependency_contract_paths(tmp_path: Path) -> None:
    """Sibling-only paths stay missing; only declared dependency paths become to-be-built."""
    state: PlanState = {
        "name": "t", "idea": "i", "current_state": "initialized",
        "iteration": 0, "created_at": "2026-05-24T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "robustness": "full"},
        "sessions": {}, "plan_versions": [], "history": [],
        "meta": {
            "total_cost_usd": 0.0, "notes": [],
            "chain_policy": {
                "contract_context": {
                    "plan_only": True,
                    "milestone_label": "M-b",
                    "dependency_labels": ["M-a"],
                    "upstream_contracts": [
                        {
                            "milestone_label": "M-a",
                            "provides": [{
                                "name": "Planner surface",
                                "interfaces": [
                                    {"symbol": "Planner.run", "path": "planner.py", "signature": "run()"},
                                ],
                            }],
                        },
                    ],
                },
            },
        },
        "last_gate": {},
    }
    findings = [
        {
            "area": "a", "brief": "b", "status": "complete",
            "findings": ["f"], "files": ["planner.py", "builder.py"],
            "code_refs": [], "confidence": "high", "error": "",
        }
    ]
    upstream_paths = prep_research._collect_upstream_provided_paths(state)

    cr = prep_research._cross_reference_prep_output(
        root=tmp_path,
        findings=findings,
        prep_payload={},
        upstream_provided_paths=upstream_paths,
    )

    assert {(item["path"], item["upstream_milestone"]) for item in cr["to_be_built_files"]} == {
        ("planner.py", "M-a")
    }
    assert "planner.py" not in cr["missing_files"]
    assert "builder.py" in cr["missing_files"]


def test_cross_reference_without_upstream_paths_keeps_old_behavior(tmp_path: Path) -> None:
    """Without upstream_provided_paths, to_be_built_files is empty and all missing paths stay missing."""
    findings = [
        {
            "area": "a", "brief": "b", "status": "complete",
            "findings": ["f"], "files": ["megaplan/nonexistent.py"],
            "code_refs": [], "confidence": "high", "error": "",
        }
    ]
    prep_payload: dict[str, Any] = {}

    cr = prep_research._cross_reference_prep_output(
        root=tmp_path,
        findings=findings,
        prep_payload=prep_payload,
    )
    assert cr["to_be_built_files"] == []
    assert "megaplan/nonexistent.py" in cr["missing_files"]


def test_gap_notes_mentions_to_be_built_files() -> None:
    """_gap_notes includes a note for to_be_built_files."""
    findings: list[dict[str, Any]] = []
    prep_payload: dict[str, Any] = {"key_evidence": ["e"], "relevant_code": [], "test_expectations": []}
    cross_reference = {
        "performed": True,
        "checked_files": [],
        "existing_files": [],
        "missing_files": [],
        "shared_files": [],
        "to_be_built_files": [
            {"path": "megaplan/planner.py", "upstream_milestone": "m1"},
            {"path": "megaplan/executor.py", "upstream_milestone": "m2"},
        ],
    }
    notes = prep_research._gap_notes(findings, prep_payload, cross_reference)
    to_be_built_note = [n for n in notes if "not yet built locally" in n]
    assert len(to_be_built_note) == 1
    assert "m1" in to_be_built_note[0]
    assert "m2" in to_be_built_note[0]
    assert "megaplan/planner.py" in to_be_built_note[0]
    assert "megaplan/executor.py" in to_be_built_note[0]
