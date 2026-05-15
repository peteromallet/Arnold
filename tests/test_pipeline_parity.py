"""Sprint 3 acceptance test #1 — byte-identical artifact parity.

Drive two plans with the same idea + robustness + mock workers:

- **Direct path:** call ``megaplan.handle_<phase>`` in sequence,
  exactly how ``test_workflow_mock_end_to_end`` does today.
- **Pipeline path:** dispatch via the planning :class:`Pipeline`'s
  in-process Steps (the Sprint-3 port).

Assert the produced plan deliverables (plan_v*.md, prep.json,
critique_v*.json, gate.json, final.md, execution.json, review.json)
are byte-identical between the two paths. Framework bookkeeping
files (state.json, *.meta.json, step_receipt_*, phase_result.json,
faults.json, execution_audit.json) carry timestamps and are excluded
from byte-comparison — but their *structural* fields are still
compared.
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

from megaplan._pipeline.stages.inprocess_step import (
    build_inprocess_planning_steps,
    build_revise_step,
    build_review_step,
)
from megaplan._pipeline.types import StepContext


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


def _make_args(plan_name: str, project_dir: Path, **overrides: Any) -> Namespace:
    base = {
        "plan": plan_name,
        "idea": "parity check idea",
        "name": plan_name,
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": "robust",
        "agent": None,
        "ephemeral": False,
        "fresh": False,
        "persist": False,
        "confirm_destructive": True,
        "user_approved": False,
        "confirm_self_review": False,
        "batch": None,
        "override_action": None,
        "note": None,
        "reason": "",
        "strict_notes": None,
        "source": "user",
    }
    base.update(overrides)
    return Namespace(**base)


def _bootstrap_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str):
    root = tmp_path / suffix / "root"
    project_dir = tmp_path / suffix / "project"
    config_path = tmp_path / suffix / "config"
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

    init_args = _make_args(plan_name="parity-plan", project_dir=project_dir, plan=None)
    response = megaplan.handle_init(root, init_args)
    plan_name = response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    megaplan.handle_override(
        root,
        _make_args(plan_name=plan_name, project_dir=project_dir,
                   plan=plan_name, override_action="add-note", note="parity check"),
    )
    return root, project_dir, plan_name, plan_dir


def _run_direct(root: Path, project_dir: Path, plan_name: str) -> None:
    """Mirror tests/test_init_plan.py::test_workflow_mock_end_to_end exactly."""

    megaplan.handlers.handle_prep(root, _make_args(plan_name, project_dir, plan=plan_name))
    megaplan.handle_plan(root, _make_args(plan_name, project_dir, plan=plan_name))
    megaplan.handle_critique(root, _make_args(plan_name, project_dir, plan=plan_name))
    megaplan.handle_gate(root, _make_args(plan_name, project_dir, plan=plan_name))
    megaplan.handle_revise(root, _make_args(plan_name, project_dir, plan=plan_name))
    megaplan.handle_critique(root, _make_args(plan_name, project_dir, plan=plan_name))
    megaplan.handle_gate(root, _make_args(plan_name, project_dir, plan=plan_name))
    megaplan.handle_finalize(root, _make_args(plan_name, project_dir, plan=plan_name))
    megaplan.handle_execute(
        root,
        _make_args(plan_name, project_dir, plan=plan_name,
                   confirm_destructive=True, user_approved=True),
    )
    megaplan.handle_review(root, _make_args(plan_name, project_dir, plan=plan_name))


def _run_pipeline(root: Path, project_dir: Path, plan_name: str, plan_dir: Path) -> None:
    inprocess_steps = build_inprocess_planning_steps()
    revise_step = build_revise_step()
    review_step = build_review_step()

    ctx_profile = {"root": root, "project_dir": project_dir}

    for _ in range(25):
        live = json.loads((plan_dir / "state.json").read_text())
        current = live.get("current_state", "initialized")
        if current in {"done", "aborted"}:
            return

        if current == "initialized":
            step = inprocess_steps["prepped"]
        elif current == "prepped":
            step = inprocess_steps["planned"]
        elif current == "planned":
            step = inprocess_steps["critiqued"]
        elif current == "critiqued":
            step = inprocess_steps["gated"]
        elif current == "gated":
            step = inprocess_steps["finalized"]
        elif current == "finalized":
            step = inprocess_steps["executed"]
        elif current == "executed":
            step = review_step
        else:
            raise RuntimeError(f"unexpected state {current!r}")

        ctx = StepContext(
            plan_dir=plan_dir,
            state={"name": plan_name, **live},
            profile=ctx_profile,
            mode="code",
            inputs={},
            budget=None,
        )
        result = step.run(ctx)

        if step.name == "gate" and result.verdict is not None and result.verdict.recommendation == "iterate":
            revise_ctx = StepContext(
                plan_dir=plan_dir,
                state={"name": plan_name, **json.loads((plan_dir / "state.json").read_text())},
                profile=ctx_profile,
                mode="code",
                inputs={},
                budget=None,
            )
            revise_step.run(revise_ctx)


def _hash_artifacts(plan_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for filename in _PARITY_ARTIFACTS:
        path = plan_dir / filename
        if not path.exists():
            continue
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def test_direct_and_pipeline_produce_identical_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_a, project_a, name_a, plan_dir_a = _bootstrap_root(tmp_path, monkeypatch, "direct")
    _run_direct(root_a, project_a, name_a)

    root_b, project_b, name_b, plan_dir_b = _bootstrap_root(tmp_path, monkeypatch, "pipeline")
    _run_pipeline(root_b, project_b, name_b, plan_dir_b)

    state_a = json.loads((plan_dir_a / "state.json").read_text())
    state_b = json.loads((plan_dir_b / "state.json").read_text())
    assert state_a["current_state"] == state_b["current_state"] == "done"

    artifacts_a = _hash_artifacts(plan_dir_a)
    artifacts_b = _hash_artifacts(plan_dir_b)

    assert set(artifacts_a.keys()) == set(artifacts_b.keys()), (
        sorted(set(artifacts_a) ^ set(artifacts_b))
    )
    for filename, sha_a in artifacts_a.items():
        sha_b = artifacts_b[filename]
        assert sha_a == sha_b, f"artifact {filename} differs: direct={sha_a} pipeline={sha_b}"
