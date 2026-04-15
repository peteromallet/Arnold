"""Tests for megaplan.chain — the chain driver subcommand."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from megaplan.auto import DriverOutcome
from megaplan.chain import (
    ChainSpec,
    ChainState,
    MilestoneSpec,
    load_chain_state,
    load_spec,
    run_chain,
    save_chain_state,
)
from megaplan.types import CliError


def _write_spec(tmp_path: Path, spec_dict: dict, *, name: str = "chain.yaml") -> Path:
    spec_path = tmp_path / name
    spec_path.write_text(yaml.safe_dump(spec_dict), encoding="utf-8")
    return spec_path


def _touch_idea(tmp_path: Path, name: str, body: str = "an idea") -> Path:
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir(exist_ok=True)
    path = ideas_dir / name
    path.write_text(body, encoding="utf-8")
    return path


def _fake_outcome(plan: str, status: str = "done") -> DriverOutcome:
    return DriverOutcome(
        status=status, plan=plan, final_state=status, iterations=1, reason=""
    )


# ---------------------------------------------------------------------------
# Spec parsing
# ---------------------------------------------------------------------------


def test_load_spec_parses_milestones_and_seed(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "seed": {"plan": "seed-plan-20260415"},
            "milestones": [
                {"label": "m1", "idea": str(idea), "branch": "mp/m1"},
            ],
            "on_failure": {"abort": "stop_chain"},
            "on_escalate": {"abort": "skip_milestone"},
        },
    )
    spec = load_spec(spec_path)
    assert spec.seed_plan == "seed-plan-20260415"
    assert len(spec.milestones) == 1
    assert spec.milestones[0] == MilestoneSpec(label="m1", idea=str(idea), branch="mp/m1")
    assert spec.on_failure == "stop_chain"
    assert spec.on_escalate == "skip_milestone"


def test_load_spec_rejects_missing_label(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path, {"milestones": [{"idea": "/tmp/x.txt"}]})
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert excinfo.value.code == "invalid_spec"


def test_load_spec_rejects_bad_failure_action(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [], "on_failure": {"abort": "nonsense"}},
    )
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert "on_failure.abort" in excinfo.value.message


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


def test_run_chain_errors_when_idea_missing(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(tmp_path / "missing.txt")}]},
    )
    with pytest.raises(CliError) as excinfo:
        run_chain(spec_path, tmp_path, writer=lambda _msg: None)
    assert excinfo.value.code == "missing_idea_file"


def test_run_chain_errors_when_seed_plan_missing(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "seed": {"plan": "no-such-plan"},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    # Set up a megaplan root without the seed plan.
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    with pytest.raises(CliError) as excinfo:
        run_chain(spec_path, tmp_path, writer=lambda _msg: None)
    assert excinfo.value.code == "missing_seed_plan"


# ---------------------------------------------------------------------------
# Chain state persistence
# ---------------------------------------------------------------------------


def test_save_and_load_chain_state_roundtrip(tmp_path: Path) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    state = ChainState(
        current_milestone_index=2,
        current_plan_name="foo-20260415",
        last_state="done",
        completed=[{"label": "m1", "plan": "m1-x", "status": "done"}],
    )
    save_chain_state(spec_path, state)
    loaded = load_chain_state(spec_path)
    assert loaded.current_milestone_index == 2
    assert loaded.current_plan_name == "foo-20260415"
    assert loaded.last_state == "done"
    assert loaded.completed == [{"label": "m1", "plan": "m1-x", "status": "done"}]


# ---------------------------------------------------------------------------
# Driver orchestration (auto.drive is mocked)
# ---------------------------------------------------------------------------


def _setup_two_milestones(tmp_path: Path) -> Path:
    i1 = _touch_idea(tmp_path, "m1.txt", "idea one")
    i2 = _touch_idea(tmp_path, "m1a.txt", "idea two")
    return _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "m1", "idea": str(i1)},
                {"label": "m1a", "idea": str(i2)},
            ]
        },
    )


def test_run_chain_executes_milestones_in_order(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    init_calls: list[str] = []
    drive_calls: list[str] = []

    def fake_init(root, idea_path, *, robustness, auto_approve, writer):
        plan = f"plan-for-{Path(idea_path).stem}"
        init_calls.append(idea_path)
        return plan

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_main", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    assert len(init_calls) == 2
    assert drive_calls == ["plan-for-m1", "plan-for-m1a"]
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 2
    assert [c["label"] for c in saved.completed] == ["m1", "m1a"]


def test_run_chain_stops_on_failure(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    drive_calls: list[str] = []

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        return _fake_outcome(plan, "failed")

    with patch("megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_main", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "stopped"
    assert len(drive_calls) == 1  # did not proceed to second milestone
    saved = load_chain_state(spec_path)
    assert saved.last_state == "failed"


def test_run_chain_resumes_from_chain_state(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    # Pretend milestone m1 already completed.
    pre = ChainState(
        current_milestone_index=1,
        current_plan_name=None,
        last_state="done",
        completed=[{"label": "m1", "plan": "plan-m1", "status": "done"}],
    )
    save_chain_state(spec_path, pre)

    init_calls: list[str] = []

    def fake_init(root, idea_path, *, robustness, auto_approve, writer):
        init_calls.append(idea_path)
        return f"plan-{Path(idea_path).stem}"

    def fake_drive(plan, **_kwargs):
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_main", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    # Only the second idea (m1a) should have been init'd; m1 is skipped.
    assert result["status"] == "done"
    assert len(init_calls) == 1
    assert "m1a" in init_calls[0]


def test_run_chain_with_seed_drives_seed_first(tmp_path: Path) -> None:
    """When seed plan isn't terminal, drive it before milestones."""
    i1 = _touch_idea(tmp_path, "m1.txt")
    seed_name = "seed-plan-20260415"
    # Fake-create the seed plan dir so resolve_plan_dir accepts it.
    seed_dir = tmp_path / ".megaplan" / "plans" / seed_name
    seed_dir.mkdir(parents=True)
    (seed_dir / "state.json").write_text(
        json.dumps({"name": seed_name, "current_state": "planned", "iteration": 1}),
        encoding="utf-8",
    )
    spec_path = _write_spec(
        tmp_path,
        {
            "seed": {"plan": seed_name},
            "milestones": [{"label": "m1", "idea": str(i1)}],
        },
    )

    plan_state_calls: list[str] = []
    drive_calls: list[str] = []

    def fake_plan_state(root, plan, *, timeout):
        plan_state_calls.append(plan)
        # Seed is mid-flight; milestone plans always "missing" until init.
        if plan == seed_name:
            return "planned"
        return "missing"

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._plan_state", side_effect=fake_plan_state), \
         patch("megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_main", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    # Seed must be driven first, then the milestone plan.
    assert drive_calls[0] == seed_name
    assert drive_calls[1].startswith("plan-m1")
