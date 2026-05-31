"""Tests for the engine-readiness autonomy ladder, retry counter, and
require_clean_base enforcement in megaplan.chain."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from unittest.mock import patch

from megaplan.auto import DriverOutcome
from megaplan import chain as chain_module
from megaplan.chain import (
    ChainState,
    FailurePolicy,
    MilestoneSpec,
    _bump_one_tier,
    _handle_outcome,
    load_chain_state,
    load_spec,
    run_chain,
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
        status=status, plan=plan, final_state=status, iterations=1, reason="boom"
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )


# ---------------------------------------------------------------------------
# Ladder parsing (back-compat string + structured mapping)
# ---------------------------------------------------------------------------


def test_plain_string_on_failure_is_backcompat_abort_only(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "on_failure": "stop_chain",
            "on_escalate": "skip_milestone",
        },
    )
    spec = load_spec(spec_path)
    assert spec.on_failure == "stop_chain"
    assert spec.on_escalate == "skip_milestone"
    assert spec.on_failure_policy == FailurePolicy(abort="stop_chain")
    assert spec.on_escalate_policy == FailurePolicy(abort="skip_milestone")
    assert spec.on_failure_policy.retry is None
    assert spec.on_failure_policy.escalate is None


def test_mapping_on_failure_parses_full_ladder(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "on_failure": {
                "retry": "retry_milestone",
                "escalate": "bump_profile",
                "abort": "stop_chain",
            },
            "on_escalate": {"escalate": "bump_robustness", "abort": "stop_chain"},
        },
    )
    spec = load_spec(spec_path)
    assert spec.on_failure_policy == FailurePolicy(
        abort="stop_chain", retry="retry_milestone", escalate="bump_profile"
    )
    assert spec.on_escalate_policy == FailurePolicy(
        abort="stop_chain", retry=None, escalate="bump_robustness"
    )
    # Back-compat scalar mirrors the abort action.
    assert spec.on_failure == "stop_chain"


def test_resume_milestone_retry_option_parses(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "on_failure": {"retry": "resume_milestone", "abort": "stop_chain"},
        },
    )
    spec = load_spec(spec_path)
    assert spec.on_failure_policy.retry == "resume_milestone"
    assert spec.on_failure_policy.abort == "stop_chain"


def test_bump_actions_are_valid_vocabulary() -> None:
    assert "bump_profile" in chain_module.VALID_FAILURE_ACTIONS
    assert "bump_robustness" in chain_module.VALID_FAILURE_ACTIONS
    assert "resume_milestone" in chain_module.VALID_FAILURE_ACTIONS


def test_invalid_ladder_subkey_rejected(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "on_failure": {"retry": "nonsense"},
        },
    )
    with pytest.raises(CliError) as info:
        load_spec(spec_path)
    assert "on_failure.retry" in info.value.message


def test_bump_one_tier_ordering() -> None:
    assert _bump_one_tier("premium", chain_module.PROFILE_BUMP_ORDER) == ("apex", True)
    assert _bump_one_tier("apex", chain_module.PROFILE_BUMP_ORDER) == ("apex", False)
    assert _bump_one_tier("thorough", chain_module.ROBUSTNESS_BUMP_ORDER) == (
        "extreme",
        True,
    )
    assert _bump_one_tier("extreme", chain_module.ROBUSTNESS_BUMP_ORDER) == (
        "extreme",
        False,
    )
    # Unknown tier left alone.
    assert _bump_one_tier("weird", chain_module.PROFILE_BUMP_ORDER) == ("weird", False)


# ---------------------------------------------------------------------------
# Ladder execution: retry -> bump -> stop, with the bounded counter.
# ---------------------------------------------------------------------------


def _ladder_milestone(label: str = "m1", **kw) -> MilestoneSpec:
    return MilestoneSpec(label=label, idea="/x.txt", **kw)


def test_ladder_progression_retry_then_bump_then_stop(tmp_path: Path) -> None:
    """retry x2 -> bump_profile (retry once) -> stop, never looping forever."""
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": "/x.txt"}],
            "on_failure": {
                "retry": "retry_milestone",
                "escalate": "bump_profile",
                "abort": "stop_chain",
            },
        },
    )
    spec = load_spec(spec_path)
    state = ChainState()
    milestone = _ladder_milestone(profile="premium")
    msgs: list[str] = []
    outcome = _fake_outcome("plan-m1", "failed")

    decisions: list[str] = []
    for _ in range(6):
        d = _handle_outcome(
            outcome, spec=spec, writer=msgs.append, milestone=milestone, state=state
        )
        decisions.append(d)
        if d == "stop":
            break

    # 2 retries (default cap), then a bump_profile retry, then stop.
    assert decisions == ["retry", "retry", "retry", "stop"]
    assert state.retry_counts["m1"] == 2
    assert state.profile_bumps["m1"] == "apex"
    assert state.ladder_stage["m1"] == "terminal"
    assert any("bumping profile" in m for m in msgs)


def test_apex_milestone_retry_capped_at_one(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": "/x.txt"}],
            "on_failure": {
                "retry": "retry_milestone",
                "escalate": "bump_profile",
                "abort": "stop_chain",
            },
        },
    )
    spec = load_spec(spec_path)
    state = ChainState()
    milestone = _ladder_milestone(profile="apex")  # apex => cap 1
    outcome = _fake_outcome("plan-m1", "failed")

    decisions: list[str] = []
    for _ in range(6):
        d = _handle_outcome(
            outcome, spec=spec, writer=lambda _m: None, milestone=milestone, state=state
        )
        decisions.append(d)
        if d == "stop":
            break

    # 1 retry (apex cap), then bump_profile is a no-op at apex -> stop immediately.
    assert decisions == ["retry", "stop"]
    assert state.retry_counts["m1"] == 1
    # No bump recorded because apex is already the top tier.
    assert "m1" not in state.profile_bumps


def test_extreme_robustness_milestone_capped_at_one(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": "/x.txt"}],
            "on_failure": {"retry": "retry_milestone", "abort": "stop_chain"},
        },
    )
    spec = load_spec(spec_path)
    state = ChainState()
    milestone = _ladder_milestone(robustness="extreme")
    outcome = _fake_outcome("plan-m1", "failed")

    decisions: list[str] = []
    for _ in range(5):
        d = _handle_outcome(
            outcome, spec=spec, writer=lambda _m: None, milestone=milestone, state=state
        )
        decisions.append(d)
        if d == "stop":
            break
    assert decisions == ["retry", "stop"]
    assert state.retry_counts["m1"] == 1


def test_ladder_does_not_infinite_loop_on_deterministic_failure(tmp_path: Path) -> None:
    """The whole point: a chain run with retry+bump must terminate."""
    idea = _touch_idea(tmp_path, "m1.txt", "idea")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea), "profile": "premium"}],
            "on_failure": {
                "retry": "retry_milestone",
                "escalate": "bump_profile",
                "abort": "stop_chain",
            },
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    drive_calls: list[str] = []

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        return _fake_outcome(plan, "failed")

    init_profiles: list[str | None] = []

    def fake_init(root, idea_path, *, profile=None, **_kw):
        init_profiles.append(profile)
        return f"plan-{Path(idea_path).stem}"

    with patch("megaplan.chain._init_plan", side_effect=fake_init), patch(
        "megaplan.chain.auto_drive", side_effect=fake_drive
    ), patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "stopped"
    # 1 initial + 2 retries + 1 post-bump retry = 4 drives, then stop. Bounded.
    assert len(drive_calls) == 4
    # The post-bump re-init used the escalated apex profile.
    assert init_profiles[-1] == "apex"
    saved = load_chain_state(spec_path)
    assert saved.retry_counts["m1"] == 2
    assert saved.profile_bumps["m1"] == "apex"
    # A ladder-exhaustion ticket was auto-filed.
    ticket = (
        tmp_path
        / ".megaplan"
        / "plans"
        / ".chains"
        / "tickets"
        / "m1-ladder-exhaustion.json"
    )
    assert ticket.exists()


def test_retry_milestone_resumes_resumable_current_plan(tmp_path: Path) -> None:
    """A retry after real upstream work resumes the existing plan, not re-init."""
    idea = _touch_idea(tmp_path, "m1.txt", "idea")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "on_failure": {"retry": "retry_milestone", "abort": "stop_chain"},
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    init_calls: list[str] = []
    drive_calls: list[str] = []
    messages: list[str] = []

    def fake_init(root, idea_path, **_kw):
        init_calls.append(idea_path)
        plan_dir = root / ".megaplan" / "plans" / "plan-m1"
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "plan-m1",
                    "current_state": "finalized",
                    "iteration": 1,
                    "config": {"project_dir": str(root)},
                    "meta": {},
                }
            ),
            encoding="utf-8",
        )
        return "plan-m1"

    def fake_drive(root, plan, spec, *, on_phase_complete=None, writer):
        del root, spec, on_phase_complete, writer
        drive_calls.append(plan)
        return _fake_outcome(plan, "failed" if len(drive_calls) == 1 else "done")

    with patch("megaplan.chain._init_plan", side_effect=fake_init), patch(
        "megaplan.chain._drive_plan", side_effect=fake_drive
    ), patch("megaplan.chain._plan_state", return_value="finalized"), patch(
        "megaplan.chain._refresh_base_branch", lambda *a, **k: None
    ):
        result = run_chain(spec_path, tmp_path, writer=messages.append)

    assert result["status"] == "done"
    assert init_calls == [str(idea)]
    assert drive_calls == ["plan-m1", "plan-m1"]
    assert any(
        "retrying milestone m1 by resuming plan plan-m1 from finalized" in message
        for message in messages
    )
    saved = load_chain_state(spec_path)
    assert saved.retry_counts["m1"] == 1
    assert saved.completed == [
        {
            "label": "m1",
            "plan": "plan-m1",
            "status": "done",
            "pr_number": None,
            "pr_state": None,
        }
    ]


def test_retry_counter_survives_resume(tmp_path: Path) -> None:
    """The counter is persisted in chain state and round-trips."""
    state = ChainState(
        retry_counts={"m3": 2},
        ladder_stage={"m3": "bump"},
        profile_bumps={"m3": "apex"},
        robustness_bumps={"m3": "extreme"},
        depth_bumps={"m3": "max"},
    )
    raw = state.to_dict()
    reloaded = ChainState.from_dict(raw)
    assert reloaded.retry_counts == {"m3": 2}
    assert reloaded.ladder_stage == {"m3": "bump"}
    assert reloaded.profile_bumps == {"m3": "apex"}
    assert reloaded.robustness_bumps == {"m3": "extreme"}
    assert reloaded.depth_bumps == {"m3": "max"}


def test_old_state_json_without_ladder_fields_loads_cleanly() -> None:
    reloaded = ChainState.from_dict({"current_milestone_index": 1})
    assert reloaded.retry_counts == {}
    assert reloaded.ladder_stage == {}
    assert reloaded.profile_bumps == {}


# ---------------------------------------------------------------------------
# require_clean_base
# ---------------------------------------------------------------------------


def test_require_clean_base_parsed(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "driver": {"require_clean_base": True},
        },
    )
    assert load_spec(spec_path).require_clean_base is True
    # Default off.
    spec2 = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea)}]},
        name="chain2.yaml",
    )
    assert load_spec(spec2).require_clean_base is False


def test_require_clean_base_rejects_non_bool(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "driver": {"require_clean_base": "yes"},
        },
    )
    with pytest.raises(CliError) as info:
        load_spec(spec_path)
    assert "require_clean_base" in info.value.message


def test_require_clean_base_auto_cleans_carried_wip_local(tmp_path: Path) -> None:
    """Local (no-push) run with require_clean_base stashes carried WIP."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    # Carried WIP: an uncommitted change unrelated to megaplan.
    (tmp_path / "carried.txt").write_text("dirty work\n", encoding="utf-8")

    idea = _touch_idea(tmp_path, "m1.txt", "idea")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "driver": {"require_clean_base": True},
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True, exist_ok=True)

    with patch(
        "megaplan.chain._init_plan",
        side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}",
    ), patch(
        "megaplan.chain.auto_drive",
        side_effect=lambda plan, **_k: _fake_outcome(plan, "done"),
    ), patch(
        "megaplan.chain._refresh_base_branch", lambda *a, **k: None
    ):
        result = run_chain(
            spec_path, tmp_path, writer=lambda _m: None, no_push=True
        )

    assert result["status"] == "done"
    # carried.txt was stashed away, not left dirty in the worktree.
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "carried.txt" not in status


def test_require_clean_base_fails_loud_when_pushing(tmp_path: Path) -> None:
    """With push enabled, carried WIP fails loud (no silent discard)."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    (tmp_path / "carried.txt").write_text("dirty\n", encoding="utf-8")

    idea = _touch_idea(tmp_path, "m1.txt", "idea")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "driver": {"require_clean_base": True},
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True, exist_ok=True)

    with patch(
        "megaplan.chain._init_plan",
        side_effect=lambda root, idea_path, **_k: "plan-m1",
    ), patch(
        "megaplan.chain.auto_drive",
        side_effect=lambda plan, **_k: _fake_outcome(plan, "done"),
    ), patch(
        "megaplan.chain._refresh_base_branch", lambda *a, **k: None
    ):
        with pytest.raises(CliError) as info:
            run_chain(spec_path, tmp_path, writer=lambda _m: None, no_push=False)
    assert info.value.code == "unclean_base"


def test_require_clean_base_ignores_megaplan_artifacts(tmp_path: Path) -> None:
    """Dirty .megaplan/ runtime artifacts do NOT count as a dirty base."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    # Only .megaplan churn is dirty.
    (tmp_path / ".megaplan").mkdir(exist_ok=True)
    (tmp_path / ".megaplan" / "scratch.json").write_text("{}", encoding="utf-8")

    assert chain_module._carried_wip_paths(tmp_path) == []
