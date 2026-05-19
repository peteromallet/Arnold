from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import megaplan
from megaplan._core import atomic_write_json, sha256_file
from megaplan.types import STATE_CRITIQUED
from megaplan.workers import WorkerResult, _build_mock_payload, run_step_with_worker
from tests.conftest import PlanFixture, load_state, read_json


def _mark_for_revise(plan_fixture: PlanFixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = STATE_CRITIQUED
    state["last_gate"] = {"recommendation": "ITERATE"}
    atomic_write_json(plan_fixture.plan_dir / "state.json", state)
    atomic_write_json(
        plan_fixture.plan_dir / "gate.json",
        {
            "recommendation": "ITERATE",
            "rationale": "test loop",
            "signals_assessment": "test loop",
            "warnings": [],
            "settled_decisions": [],
        },
    )


def _revise_worker(state: dict, plan_dir: Path, marker: str, session_id: str) -> WorkerResult:
    payload = _build_mock_payload("revise", state, plan_dir)
    payload["plan"] = f"{payload['plan'].rstrip()}\n\n## Cache Regression Marker\n{marker}\n"
    return WorkerResult(
        payload=payload,
        raw_output="{}",
        duration_ms=25,
        cost_usd=0.01,
        session_id=session_id,
        rendered_prompt=f"revise prompt {marker}",
        prompt_tokens=100 + int(marker),
        completion_tokens=20 + int(marker),
        total_tokens=120 + (2 * int(marker)),
    )


def test_revise_iterations_write_distinct_hashes_and_sessions(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_gate(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    calls = {"count": 0}

    def fake_run_step_with_worker(
        step: str,
        state: dict,
        plan_dir: Path,
        args: argparse.Namespace,
        **kwargs: object,
    ):
        assert step == "revise"
        calls["count"] += 1
        worker = _revise_worker(
            state,
            plan_dir,
            str(calls["count"]),
            f"revise-session-{calls['count']}",
        )
        return worker, "codex", "persistent", True

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step_with_worker)

    for _ in range(3):
        _mark_for_revise(plan_fixture)
        megaplan.handle_revise(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    plan_hashes = [
        sha256_file(path)
        for path in sorted(plan_fixture.plan_dir.glob("plan_v*.md"))
        if path.name != "plan_v1.md"
    ]
    assert len(plan_hashes) == 3
    assert len(set(plan_hashes)) == 3

    receipts = [
        read_json(path)
        for path in sorted(plan_fixture.plan_dir.glob("step_receipt_revise_v*.json"))
    ]
    assert len(receipts) == 3
    triples = {
        (receipt["prompt_tokens"], receipt["completion_tokens"], receipt["session_id"])
        for receipt in receipts
    }
    assert len(triples) == 3
    assert [receipt["session_id"] for receipt in receipts] == [
        "revise-session-1",
        "revise-session-2",
        "revise-session-3",
    ]


@pytest.mark.parametrize(
    "phase",
    ["plan", "prep", "critique", "gate", "revise", "finalize", "review"],
)
def test_dispatch_forces_fresh_for_non_execute_phases(tmp_path: Path, phase: str) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    state = {
        "name": "test-plan",
        "idea": "test",
        "current_state": "critiqued",
        "iteration": 1,
        "config": {"project_dir": str(project_dir), "robustness": "standard"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
        "last_gate": {},
    }
    worker = WorkerResult(
        payload={},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="new-session",
    )

    with patch("megaplan.workers._impl.run_codex_step", return_value=worker) as run_codex:
        run_step_with_worker(
            phase,
            state,
            plan_dir,
            argparse.Namespace(
                agent="codex",
                ephemeral=False,
                fresh=False,
                persist=False,
                hermes=None,
                phase_model=[],
            ),
            root=tmp_path,
            resolved=("codex", "persistent", False, None),
        )

    assert run_codex.call_args.kwargs["fresh"] is True


def test_dispatch_preserves_execute_persistence(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    state = {
        "name": "test-plan",
        "idea": "test",
        "current_state": "finalized",
        "iteration": 1,
        "config": {"project_dir": str(project_dir), "robustness": "standard"},
        "sessions": {"codex_executor": {"id": "old-session"}},
        "plan_versions": [],
        "history": [],
        "meta": {},
        "last_gate": {},
    }
    worker = WorkerResult(
        payload={},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="old-session",
    )

    with patch("megaplan.workers._impl.run_codex_step", return_value=worker) as run_codex:
        run_step_with_worker(
            "execute",
            state,
            plan_dir,
            argparse.Namespace(
                agent="codex",
                ephemeral=False,
                fresh=False,
                persist=False,
                hermes=None,
                phase_model=[],
            ),
            root=tmp_path,
            resolved=("codex", "persistent", False, None),
        )

    assert run_codex.call_args.kwargs["fresh"] is False


def test_shannon_revise_uses_versioned_prompt_and_fresh_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, session_key_for
    from megaplan.workers.shannon import run_shannon_step

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir(exist_ok=True)
    project_dir.mkdir(exist_ok=True)
    state = {
        "name": "test-plan",
        "idea": "test",
        "current_state": "critiqued",
        "iteration": 1,
        "config": {"project_dir": str(project_dir), "robustness": "standard"},
        "sessions": {session_key_for("revise", "shannon"): {"id": "old-shannon-session"}},
        "plan_versions": [],
        "history": [],
        "meta": {},
        "last_gate": {"recommendation": "ITERATE"},
    }
    payload = _build_mock_payload("revise", state, plan_dir)
    raw = json.dumps(
        [
            {
                "type": "result",
                "subtype": "success",
                "result": json.dumps(payload),
                "session_id": "fresh-shannon-session",
                "usage": {"input_tokens": 11, "output_tokens": 7},
            }
        ]
    )
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=raw,
        stderr="",
        duration_ms=12,
    )

    with patch("megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
        result = run_shannon_step(
            "revise",
            state,
            plan_dir,
            root=tmp_path,
            fresh=False,
            prompt_override="revise prompt",
        )

    command = run_command.call_args.args[0]
    assert "--session-id" in command
    assert "--resume" not in command
    assert "old-shannon-session" not in command
    assert (plan_dir / "revise_v2_shannon_prompt.txt").exists()
    assert result.session_id == "fresh-shannon-session"
