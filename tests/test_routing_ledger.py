from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from arnold.pipelines.megaplan._core.worker_fanout import WorkerUnit, scatter_worker_unit
from arnold.pipelines.megaplan.observability.routing_ledger import LEDGER_FILE, record_step_routing
from arnold.pipelines.megaplan.types import AgentMode, PlanState
from arnold.pipelines.megaplan.workers import WorkerResult, run_step_with_worker


def _state(tmp_path: Path) -> PlanState:
    return {
        "name": "routing-ledger-test",
        "idea": "record routing",
        "current_state": "planned",
        "iteration": 1,
        "created_at": "2026-06-01T00:00:00Z",
        "config": {
            "project_dir": str(tmp_path),
            "robustness": "standard",
            "mode": "code",
        },
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"total_cost_usd": 0.0, "notes": []},
    }


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        agent=None,
        hermes=None,
        phase_model=[],
        ephemeral=False,
        fresh=False,
        persist=False,
        confirm_self_review=False,
    )


def _worker(payload: dict | None = None, *, actual: str | None = "gpt-5.5") -> WorkerResult:
    return WorkerResult(
        payload=payload or {"ok": True},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="session-1",
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        model_actual=actual,
    )


def _read_ledger(plan_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (plan_dir / LEDGER_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_routing_ledger_covers_plan_critique_and_execute(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    resolved = AgentMode(
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="gpt-5.5",
        resolved_model="gpt-5.5",
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_codex_step", return_value=_worker({"plan": "ok"})):
        run_step_with_worker(
            "plan",
            state,
            plan_dir,
            _args(),
            root=tmp_path,
            resolved=resolved,
            prompt_override="plan",
        )
        scatter_worker_unit(
            0,
            WorkerUnit(
                step="critique",
                resolved=resolved,
                prompt="critique",
                output_path=plan_dir / "critique_correctness.json",
                extra={"check_id": "correctness", "ledger_complexity": 3},
            ),
            state=state,
            plan_dir=plan_dir,
            root=tmp_path,
            args=_args(),
        )

    record_step_routing(
        plan_dir,
        phase="execute",
        step_label="batch_1",
        agent="codex",
        selected_spec="codex:gpt-5.5",
        resolved_model="gpt-5.5",
        actual_model="gpt-5.5",
        tier=3,
        complexity=3,
        tier_routing_active=True,
    )

    rows = _read_ledger(plan_dir)
    assert [(row["phase"], row["step_label"]) for row in rows] == [
        ("plan", "plan"),
        ("critique", "correctness"),
        ("execute", "batch_1"),
    ]


def test_critique_records_one_ledger_entry_per_lens(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    resolved = AgentMode(
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="gpt-5.5",
        resolved_model="gpt-5.5",
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_codex_step", return_value=_worker({"checks": []})):
        for index, lens in enumerate(("correctness", "scope")):
            scatter_worker_unit(
                index,
                WorkerUnit(
                    step="critique",
                    resolved=resolved,
                    prompt=lens,
                    output_path=plan_dir / f"critique_{lens}.json",
                    extra={
                        "check_id": lens,
                        "ledger_selected_spec": "codex:gpt-5.5",
                        "ledger_complexity": index + 2,
                    },
                ),
                state=state,
                plan_dir=plan_dir,
                root=tmp_path,
                args=_args(),
            )

    rows = _read_ledger(plan_dir)
    assert [row["step_label"] for row in rows] == ["correctness", "scope"]
    assert all(row["phase"] == "critique" for row in rows)


def test_missing_codex_actual_model_records_resolved_model_without_blocking(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state(tmp_path)
    resolved = AgentMode(
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="gpt-5.5",
        resolved_model="gpt-5.5",
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_codex_step", return_value=_worker(actual=None)):
        worker, *_ = run_step_with_worker(
            "gate",
            state,
            plan_dir,
            _args(),
            root=tmp_path,
            resolved=resolved,
            prompt_override="gate",
        )

    assert worker.model_actual is None
    [row] = _read_ledger(plan_dir)
    assert row["actual_model"] == "gpt-5.5"


def test_ledger_write_failure_is_swallowed_and_phase_completes(tmp_path: Path) -> None:
    plan_dir = tmp_path / "not-a-directory"
    plan_dir.write_text("not a directory", encoding="utf-8")
    state = _state(tmp_path)
    resolved = AgentMode(
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="gpt-5.5",
        resolved_model="gpt-5.5",
    )

    with patch("arnold.pipelines.megaplan.workers._impl.run_codex_step", return_value=_worker({"plan": "ok"})):
        worker, agent, mode, refreshed = run_step_with_worker(
            "plan",
            state,
            plan_dir,
            _args(),
            root=tmp_path,
            resolved=resolved,
            prompt_override="plan",
        )

    assert worker.payload == {"plan": "ok"}
    assert (agent, mode, refreshed) == ("codex", "persistent", True)
