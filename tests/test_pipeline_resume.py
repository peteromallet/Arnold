"""Sprint 3 acceptance test #5 — kill-mid-run / resume parity.

Drive a mock-worker plan halfway through the Pipeline, stop after
finalize, then resume from the next stage using the Pipeline driver
and assert the final artifacts are identical to an uninterrupted run.

The Pipeline's resume contract: ``resume_cursor.phase`` names a stage,
the driver looks it up in ``pipeline.stages`` by name and re-enters
it. State.json is the durable handoff — by reading it on each tick
the driver picks up wherever the previous run stopped.
"""

from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli
import megaplan.workers

from megaplan._pipeline.stages.inprocess_step import (
    build_inprocess_planning_steps,
    build_revise_step,
    build_review_step,
)
from megaplan._pipeline.types import StepContext


def _make_mock_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plan_name_seed: str
) -> tuple[Path, Path, str, Path]:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    tmp_path.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True)
    project_dir.mkdir(parents=True)
    (project_dir / ".git").mkdir()

    def _config_dir(home: Any = None) -> Path:
        return config_path

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)

    init_args = Namespace(
        plan=None,
        idea=f"resume parity {plan_name_seed}",
        name=f"resume-{plan_name_seed}",
        project_dir=str(project_dir),
        auto_approve=None,
        robustness="robust",
        agent=None,
        ephemeral=False,
        fresh=False,
        persist=False,
        confirm_destructive=True,
        user_approved=False,
        confirm_self_review=False,
        batch=None,
        override_action=None,
        note=None,
        reason="",
        strict_notes=None,
        source="user",
    )
    response = megaplan.handle_init(root, init_args)
    plan_name = response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    note_args = Namespace(**{**vars(init_args), "plan": plan_name, "override_action": "add-note", "note": "resume scoped"})
    megaplan.handle_override(root, note_args)
    return root, project_dir, plan_name, plan_dir


def _drive_until(
    plan_dir: Path,
    root: Path,
    project_dir: Path,
    plan_name: str,
    *,
    halt_after: str | None = None,
    max_steps: int = 25,
) -> dict[str, Any]:
    inprocess_steps = build_inprocess_planning_steps()
    revise_step = build_revise_step()
    review_step = build_review_step()

    ctx_profile = {"root": root, "project_dir": project_dir}
    visits: list[str] = []

    for _ in range(max_steps):
        live_state = json.loads((plan_dir / "state.json").read_text())
        current_state = live_state.get("current_state", "initialized")
        if current_state in {"done", "aborted"}:
            return {"visits": visits, "final_state": current_state}

        if current_state == "initialized":
            step = inprocess_steps["prepped"]
        elif current_state == "prepped":
            step = inprocess_steps["planned"]
        elif current_state == "planned":
            step = inprocess_steps["critiqued"]
        elif current_state == "critiqued":
            step = inprocess_steps["gated"]
        elif current_state == "gated":
            step = inprocess_steps["finalized"]
        elif current_state == "finalized":
            step = inprocess_steps["executed"]
        elif current_state == "executed":
            step = review_step
        else:
            raise RuntimeError(f"unexpected state {current_state!r}")

        ctx = StepContext(
            plan_dir=plan_dir,
            state={"name": plan_name, **live_state},
            profile=ctx_profile,
            mode="code",
            inputs={},
            budget=None,
        )
        result = step.run(ctx)
        visits.append(f"{current_state}->{step.name}={result.next}")

        if step.name == "gate" and result.verdict is not None and result.verdict.recommendation == "iterate":
            revise_ctx = StepContext(
                plan_dir=plan_dir,
                state={"name": plan_name, **json.loads((plan_dir / "state.json").read_text())},
                profile=ctx_profile,
                mode="code",
                inputs={},
                budget=None,
            )
            revise_result = revise_step.run(revise_ctx)
            visits.append(f"revise={revise_result.next}")

        if halt_after and step.name == halt_after:
            return {"visits": visits, "final_state": "halted"}

    return {"visits": visits, "final_state": "max_steps_exhausted"}


_PARITY_ARTIFACTS = (
    "plan_v1.md",
    "plan_v2.md",
    "prep.json",
    "critique_output.json",
    "critique_v1.json",
    "critique_v2.json",
    "gate.json",
    "final.md",
    "execution.json",
    "review.json",
)


def _hash_artifacts(plan_dir: Path) -> dict[str, str]:
    """Hash the durable plan-output artifacts.

    Excludes session-id-bearing files (phase_result.json, state.json,
    step_receipt_*, *.meta.json, faults.json, execution_audit.json)
    because mock workers stamp those with timestamps + UUIDs. The
    parity contract is on the plan deliverables, not on the framework's
    bookkeeping side-channels.
    """

    hashes: dict[str, str] = {}
    for filename in _PARITY_ARTIFACTS:
        path = plan_dir / filename
        if not path.exists():
            continue
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def test_pipeline_resume_matches_uninterrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Run A: uninterrupted, end-to-end.
    root_a, project_a, name_a, plan_dir_a = _make_mock_root(tmp_path / "a", monkeypatch, "p")
    result_a = _drive_until(plan_dir_a, root_a, project_a, name_a)
    assert result_a["final_state"] == "done", result_a

    artifacts_a = _hash_artifacts(plan_dir_a)

    # Run B: halt after finalize, then resume to done.
    root_b, project_b, name_b, plan_dir_b = _make_mock_root(tmp_path / "b", monkeypatch, "p")
    halt = _drive_until(plan_dir_b, root_b, project_b, name_b, halt_after="finalize")
    assert halt["final_state"] == "halted", halt
    state_at_halt = json.loads((plan_dir_b / "state.json").read_text())
    assert state_at_halt["current_state"] == "finalized"

    # Simulate a fresh process: the driver only reads state.json.
    resume = _drive_until(plan_dir_b, root_b, project_b, name_b)
    assert resume["final_state"] == "done", resume

    artifacts_b = _hash_artifacts(plan_dir_b)

    # The two runs must produce the same artifact set with the same
    # content (mock workers are deterministic). The hashing helper
    # excludes session ids / timestamps so the comparison is structural.
    assert set(artifacts_a.keys()) == set(artifacts_b.keys()), (
        sorted(set(artifacts_a) ^ set(artifacts_b))
    )
    for rel, sha_a in artifacts_a.items():
        sha_b = artifacts_b[rel]
        assert sha_a == sha_b, f"artifact {rel} differs after resume"
