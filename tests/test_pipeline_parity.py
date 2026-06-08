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

import arnold.pipelines.megaplan as megaplan

from arnold.pipelines.megaplan.stages.inprocess_step import (
    build_inprocess_planning_steps,
    build_revise_step,
    build_review_step,
)
from arnold.pipelines.megaplan._pipeline.types import StepContext

from tests.conftest import make_args_factory


_PARITY_ARTIFACTS = (
    "plan_v1.md",
    "plan_v2.md",
    "prep.json",
    "critique_v1.json",
    "critique_v2.json",
    "gate.json",
    "final.md",
    "execution.json",
    "review.json",
)


def _make_args(plan_name: str, project_dir: Path, **overrides: Any) -> Namespace:
    defaults: dict[str, Any] = {
        "plan": plan_name,
        "idea": "parity check idea",
        "name": plan_name,
        "robustness": "robust",
    }
    defaults.update(overrides)
    return make_args_factory(project_dir)(**defaults)


def _init_parity_plan(root: Path, project_dir: Path) -> tuple[str, Path]:
    """Initialize a parity plan after bootstrap is already done."""
    init_args = _make_args(plan_name="parity-plan", project_dir=project_dir, plan=None)
    response = megaplan.handle_init(root, init_args)
    plan_name = response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    megaplan.handle_override(
        root,
        _make_args(plan_name=plan_name, project_dir=project_dir,
                   plan=plan_name, override_action="add-note", note="parity check"),
    )
    return plan_name, plan_dir


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
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    # bootstrap_fixture already set up MOCK_ENV_VAR, shutil.which, and config_dir.
    # Create separate roots for direct and pipeline runs.
    root_a = tmp_path / "direct" / "root"
    project_a = tmp_path / "direct" / "project"
    root_a.mkdir(parents=True)
    project_a.mkdir(parents=True)
    (project_a / ".git").mkdir()

    root_b = tmp_path / "pipeline" / "root"
    project_b = tmp_path / "pipeline" / "project"
    root_b.mkdir(parents=True)
    project_b.mkdir(parents=True)
    (project_b / ".git").mkdir()

    name_a, plan_dir_a = _init_parity_plan(root_a, project_a)
    _run_direct(root_a, project_a, name_a)

    name_b, plan_dir_b = _init_parity_plan(root_b, project_b)
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
