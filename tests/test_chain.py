"""Tests for megaplan.chain — the chain driver subcommand."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from megaplan.auto import DriverOutcome
from megaplan.chain import (
    ChainState,
    MilestoneSpec,
    _commit_and_push_phase,
    _enable_auto_merge,
    _pr_state,
    _state_path_for,
    format_chain_status,
    load_chain_state,
    load_spec,
    run_chain,
    run_chain_cli,
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


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
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
                {
                    "label": "m1",
                    "idea": str(idea),
                    "branch": "mp/m1",
                    "profile": "poirot",
                    "robustness": "standard",
                    "phase_model": ["plan=claude:high", "revise=claude:high"],
                    "bakeoff": {"enabled": True, "arms": ["poirot", "all-claude", "all-codex"]},
                    "notes": "contract seam",
                },
            ],
            "on_failure": {"abort": "stop_chain"},
            "on_escalate": {"abort": "skip_milestone"},
        },
    )
    spec = load_spec(spec_path)
    assert spec.seed_plan == "seed-plan-20260415"
    assert len(spec.milestones) == 1
    assert spec.milestones[0] == MilestoneSpec(
        label="m1",
        idea=str(idea),
        branch="mp/m1",
        profile="poirot",
        robustness="standard",
        phase_model=["plan=claude:high", "revise=claude:high"],
        bakeoff={"enabled": True, "arms": ["poirot", "all-claude", "all-codex"]},
        notes="contract seam",
    )
    assert spec.on_failure == "stop_chain"
    assert spec.on_escalate == "skip_milestone"
    assert spec.merge_policy == "auto"


def test_load_spec_parses_review_merge_policy(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "merge_policy": "review",
            "milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}],
        },
    )
    assert load_spec(spec_path).merge_policy == "review"


def test_load_spec_rejects_bad_merge_policy(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path, {"merge_policy": "later", "milestones": []})
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert "merge_policy" in excinfo.value.message


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


def test_commit_phase_fails_when_plan_claims_dirty_nested_repo(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")

    nested = tmp_path / "reigh-app"
    nested.mkdir()
    _git(nested, "init")
    _git(nested, "config", "user.email", "test@example.com")
    _git(nested, "config", "user.name", "Test User")
    (nested / "tracked.ts").write_text("old\n", encoding="utf-8")
    _git(nested, "add", "tracked.ts")
    _git(nested, "commit", "-m", "nested init")
    (nested / "tracked.ts").write_text("new\n", encoding="utf-8")

    plan_dir = tmp_path / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "files_changed": ["reigh-app/tracked.ts"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CliError) as excinfo:
        _commit_and_push_phase(
            tmp_path,
            "branch",
            "plan",
            "execute",
            writer=lambda _msg: None,
        )

    assert excinfo.value.code == "nested_repo_changes_uncommitted"
    assert "reigh-app" in excinfo.value.message


def test_commit_phase_ignores_unclaimed_dirty_nested_files(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "checkout", "-b", "branch")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    origin = tmp_path.parent / f"{tmp_path.name}-origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare")
    _git(tmp_path, "remote", "add", "origin", str(origin))

    nested = tmp_path / "reigh-app"
    nested.mkdir()
    _git(nested, "init")
    _git(nested, "config", "user.email", "test@example.com")
    _git(nested, "config", "user.name", "Test User")
    (nested / "claimed.ts").write_text("published\n", encoding="utf-8")
    (nested / "unrelated.ts").write_text("old\n", encoding="utf-8")
    _git(nested, "add", "claimed.ts", "unrelated.ts")
    _git(nested, "commit", "-m", "nested init")
    (nested / "unrelated.ts").write_text("user work\n", encoding="utf-8")

    plan_dir = tmp_path / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution.json").write_text(
        json.dumps({"files_changed": ["reigh-app/claimed.ts"]}),
        encoding="utf-8",
    )

    _commit_and_push_phase(
        tmp_path,
        "branch",
        "plan",
        "execute",
        writer=lambda _msg: None,
    )

    assert (nested / "unrelated.ts").read_text(encoding="utf-8") == "user work\n"


def test_commit_phase_excludes_preexisting_dirty_root_files(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "checkout", "-b", "branch")
    intended = tmp_path / "intended.txt"
    unrelated = tmp_path / "unrelated.txt"
    intended.write_text("base\n", encoding="utf-8")
    unrelated.write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "intended.txt", "unrelated.txt")
    _git(tmp_path, "commit", "-m", "init")
    origin = tmp_path.parent / f"{tmp_path.name}-origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare")
    _git(tmp_path, "remote", "add", "origin", str(origin))

    intended.write_text("base\nplanned\n", encoding="utf-8")
    unrelated.write_text("base\nuser dirty\n", encoding="utf-8")

    _commit_and_push_phase(
        tmp_path,
        "branch",
        "plan",
        "execute",
        writer=lambda _msg: None,
        preexisting_dirty_paths=[unrelated],
    )

    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert committed == ["intended.txt"]
    assert " M unrelated.txt" in status


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
        pr_number=42,
        pr_state="open",
        completed=[{"label": "m1", "plan": "m1-x", "status": "done"}],
    )
    save_chain_state(spec_path, state)
    state_path = _state_path_for(spec_path)
    assert state_path.parent == tmp_path / ".megaplan" / "plans" / ".chains"
    assert state_path.exists()
    assert not (tmp_path / "chain_state.json").exists()
    loaded = load_chain_state(spec_path)
    assert loaded.current_milestone_index == 2
    assert loaded.current_plan_name == "foo-20260415"
    assert loaded.last_state == "done"
    assert loaded.pr_number == 42
    assert loaded.pr_state == "open"
    assert loaded.completed == [{"label": "m1", "plan": "m1-x", "status": "done"}]


def test_load_chain_state_reads_legacy_sibling_state(tmp_path: Path) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    (tmp_path / "chain_state.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 4,
                "current_plan_name": "legacy-plan",
                "last_state": "done",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_chain_state(spec_path)

    assert loaded.current_milestone_index == 4
    assert loaded.current_plan_name == "legacy-plan"
    assert loaded.last_state == "done"


def test_format_chain_status_pretty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec_path = _setup_three_milestones(tmp_path, seed_plan="seed-plan-20260421")
    spec = load_spec(spec_path)
    state = ChainState(
        current_milestone_index=1,
        current_plan_name="plan-for-m2",
        last_state="done",
        completed=[{"label": "m1", "plan": "plan-for-m1", "status": "done"}],
    )
    save_chain_state(spec_path, state)

    summary = format_chain_status(spec, state)
    assert summary == {
        "current_milestone": {"label": "m2", "index": 1},
        "completed": [{"label": "m1", "index": 0}],
        "remaining": [{"label": "m2", "index": 1}, {"label": "m3", "index": 2}],
        "per_milestone": [
            {"label": "m1", "index": 0, "status": "completed"},
            {"label": "m2", "index": 1, "status": "in_progress"},
            {"label": "m3", "index": 2, "status": "pending"},
        ],
        "seed_plan": "seed-plan-20260421",
        "current_plan_name": "plan-for-m2",
        "last_state": "done",
    }

    args = argparse.Namespace(chain_action="status", spec=str(spec_path), no_git_refresh=False)
    assert run_chain_cli(tmp_path, args, writer=lambda msg: sys.stderr.write(msg)) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["summary"] == summary
    assert "Current milestone: m2 (index 1)" in captured.err
    assert "Seed plan: seed-plan-20260421" in captured.err
    assert "[in_progress] m2 (index 1)" in captured.err


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


def _setup_three_milestones(tmp_path: Path, *, seed_plan: str | None = None) -> Path:
    i1 = _touch_idea(tmp_path, "m1.txt", "idea one")
    i2 = _touch_idea(tmp_path, "m2.txt", "idea two")
    i3 = _touch_idea(tmp_path, "m3.txt", "idea three")
    payload: dict[str, object] = {
        "milestones": [
            {"label": "m1", "idea": str(i1)},
            {"label": "m2", "idea": str(i2)},
            {"label": "m3", "idea": str(i3)},
        ]
    }
    if seed_plan is not None:
        payload["seed"] = {"plan": seed_plan}
    return _write_spec(tmp_path, payload)


def test_run_chain_executes_milestones_in_order(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    init_calls: list[str] = []
    drive_calls: list[str] = []

    def fake_init(root, idea_path, *, robustness, auto_approve, profile=None, phase_model=None, writer):
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


def test_run_chain_one_pauses_after_single_milestone(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    def fake_drive(plan, **_kwargs):
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_main", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, one=True)

    assert result["status"] == "paused"
    assert result["reason"] == "completed one milestone: m1"
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 1
    assert [c["label"] for c in saved.completed] == ["m1"]


def test_chain_start_invokes_driver(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    calls: list[tuple[Path, Path, bool]] = []

    def fake_run_chain(
        spec_path_arg: Path,
        root: Path,
        *,
        no_git_refresh: bool = False,
        no_push: bool = False,
        one: bool = False,
        writer=None,
    ):
        del writer
        del no_push
        del one
        calls.append((spec_path_arg, root, no_git_refresh))
        return {"status": "done", "reason": "", "chain_state": {}, "events": []}

    with patch("megaplan.chain.run_chain", side_effect=fake_run_chain):
        start_args = argparse.Namespace(
            chain_action="start",
            spec=str(spec_path),
            no_git_refresh=True,
            no_push=False,
        )
        alias_args = argparse.Namespace(
            chain_action=None,
            spec=str(spec_path),
            no_git_refresh=False,
            no_push=False,
        )

        assert run_chain_cli(tmp_path, start_args) == 0
        start_payload = json.loads(capsys.readouterr().out)
        assert run_chain_cli(tmp_path, alias_args) == 0
        alias_payload = json.loads(capsys.readouterr().out)

    assert calls == [
        (spec_path.resolve(), tmp_path, True),
        (spec_path.resolve(), tmp_path, False),
    ]
    assert start_payload["status"] == "done"
    assert alias_payload["status"] == "done"


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

    def fake_init(root, idea_path, *, robustness, auto_approve, profile=None, phase_model=None, writer):
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


# ---------------------------------------------------------------------------
# --no-git-refresh flag
# ---------------------------------------------------------------------------


def test_no_git_refresh_suppresses_subprocess_calls(tmp_path: Path) -> None:
    """With no_git_refresh=True, _refresh_main must not invoke any subprocess."""
    from megaplan.chain import _refresh_main

    msgs: list[str] = []
    with patch("megaplan.chain.subprocess.run") as mock_run:
        _refresh_main(tmp_path, writer=msgs.append, no_git_refresh=True)
    assert mock_run.call_count == 0
    assert any("skipping git refresh" in m for m in msgs)


def test_refresh_main_default_invokes_git(tmp_path: Path) -> None:
    """Default behavior (no_git_refresh=False) still issues the git commands."""
    from megaplan.chain import _refresh_main

    class _Proc:
        returncode = 0

    with patch("megaplan.chain.subprocess.run", return_value=_Proc()) as mock_run:
        _refresh_main(tmp_path, writer=lambda _m: None)
    # fetch + checkout + pull
    assert mock_run.call_count == 3
    cmds = [call.args[0] for call in mock_run.call_args_list]
    assert cmds[0][:2] == ["git", "fetch"]
    assert cmds[1] == ["git", "checkout", "main"]
    assert cmds[2][:2] == ["git", "pull"]


def test_refresh_main_aborts_on_git_failure(tmp_path: Path) -> None:
    """A failed checkout/pull must stop the chain before stale work executes."""
    from megaplan.chain import _refresh_main

    calls = [
        subprocess.CompletedProcess(
            args=["git", "fetch", "origin", "main"],
            returncode=0,
            stdout="",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=["git", "checkout", "main"],
            returncode=1,
            stdout="",
            stderr="local changes would be overwritten",
        ),
    ]
    msgs: list[str] = []

    with patch("megaplan.chain.subprocess.run", side_effect=calls):
        with pytest.raises(CliError) as excinfo:
            _refresh_main(tmp_path, writer=msgs.append)

    assert excinfo.value.code == "git_refresh_failed"
    assert "git checkout main exited 1" in excinfo.value.message
    assert any("local changes would be overwritten" in msg for msg in msgs)


def test_plan_state_uses_module_launcher(tmp_path: Path) -> None:
    class _Proc:
        returncode = 0
        stdout = '{"state": "planned"}'

    with patch("megaplan.chain.subprocess.run", return_value=_Proc()) as mock_run:
        from megaplan.chain import _plan_state

        assert _plan_state(tmp_path, "demo-plan", timeout=5) == "planned"

    assert mock_run.call_args.args[0] == [
        sys.executable,
        "-m",
        "megaplan",
        "status",
        "--plan",
        "demo-plan",
    ]


def test_init_plan_uses_module_launcher(tmp_path: Path) -> None:
    idea_path = _touch_idea(tmp_path, "m1.txt", "hello world")
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"plan": "demo-plan"}',
        stderr="",
    )

    with patch("megaplan.chain.subprocess.run", return_value=proc) as mock_run:
        from megaplan.chain import _init_plan

        assert _init_plan(
            tmp_path,
            str(idea_path),
            robustness="standard",
            auto_approve=True,
            profile="poirot",
            phase_model=["plan=claude:high", "revise=claude:high"],
            writer=lambda _m: None,
        ) == "demo-plan"

    assert mock_run.call_args.args[0] == [
        sys.executable,
        "-m",
        "megaplan",
        "init",
        "--project-dir",
        str(tmp_path),
        "--auto-approve",
        "--robustness",
        "standard",
        "--profile",
        "poirot",
        "--phase-model",
        "plan=claude:high",
        "--phase-model",
        "revise=claude:high",
        "--idea-file",
        str(idea_path),
    ]


def test_run_chain_no_git_refresh_skips_refresh(tmp_path: Path) -> None:
    """End-to-end: run_chain(..., no_git_refresh=True) propagates the flag."""
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    refresh_calls: list[bool] = []

    def fake_refresh(root, *, writer, no_git_refresh=False):
        refresh_calls.append(no_git_refresh)

    def fake_drive(plan, **_kwargs):
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_main", side_effect=fake_refresh):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, no_git_refresh=True)

    assert result["status"] == "done"
    assert len(refresh_calls) == 2
    assert all(call is True for call in refresh_calls)


def test_run_chain_no_push_skips_branch_pr_lifecycle(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}]},
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    with patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain.auto_drive", return_value=_fake_outcome("plan-m1", "done")), \
         patch("megaplan.chain._refresh_main", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("megaplan.chain._ensure_milestone_pr") as ensure_pr:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, no_push=True)

    assert result["status"] == "done"
    checkout.assert_not_called()
    ensure_pr.assert_not_called()


def test_commit_and_push_phase_skips_empty_diff(tmp_path: Path) -> None:
    from megaplan.chain import _commit_and_push_phase

    commands: list[list[str]] = []

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code="command_failed"):
        del root, writer, timeout, error_code
        commands.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    def fake_run(cmd, **_kwargs):
        assert cmd == ["git", "diff", "--cached", "--quiet"]
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("megaplan.chain._run_command", side_effect=fake_run_command), \
         patch("megaplan.chain.subprocess.run", side_effect=fake_run):
        _commit_and_push_phase(
            tmp_path,
            "mp/m1",
            "plan-m1",
            "plan",
            writer=lambda _m: None,
        )

    assert commands == [["git", "add", "-A"]]


def test_ensure_milestone_pr_skips_when_gh_missing(tmp_path: Path) -> None:
    from megaplan.chain import _ensure_milestone_pr

    messages: list[str] = []
    with patch("megaplan.chain.shutil.which", return_value=None), \
         patch("megaplan.chain._list_open_pr_for_branch") as list_pr, \
         patch("megaplan.chain._run_command") as run_command:
        pr_number = _ensure_milestone_pr(
            tmp_path,
            MilestoneSpec(label="m1", idea="idea.txt", branch="mp/m1"),
            writer=messages.append,
        )

    assert pr_number is None
    assert "skipping PR creation" in "".join(messages)
    list_pr.assert_not_called()
    run_command.assert_not_called()


def test_run_chain_branch_pr_commit_and_auto_merge(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}]},
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    commits: list[tuple[str, str, str]] = []

    def fake_drive(root, plan, spec, *, on_phase_complete=None, writer):
        del root, spec, writer
        assert plan == "plan-m1"
        assert on_phase_complete is not None
        on_phase_complete("plan", 0, "", "")
        on_phase_complete("execute", 0, "", "")
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._refresh_main", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("megaplan.chain._ensure_milestone_pr", return_value=17) as ensure_pr, \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch("megaplan.chain._commit_and_push_phase", side_effect=lambda root, branch, plan, phase, **_kwargs: commits.append((branch, plan, phase))), \
         patch("megaplan.chain._pr_state", return_value="open"), \
         patch("megaplan.chain._mark_pr_ready") as ready, \
         patch("megaplan.chain._enable_auto_merge") as merge:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    checkout.assert_called_once()
    ensure_pr.assert_called_once()
    assert commits == [
        ("mp/m1", "plan-m1", "init"),
        ("mp/m1", "plan-m1", "plan"),
        ("mp/m1", "plan-m1", "execute"),
        ("mp/m1", "plan-m1", "done"),
    ]
    assert ready.call_args.args == (tmp_path, 17)
    assert merge.call_args.args == (tmp_path, 17)
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 1
    assert saved.pr_number is None


def test_enable_auto_merge_falls_back_when_repo_disallows_auto_merge(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    messages: list[str] = []

    def fake_run(root, argv, *, writer, timeout, error_code):
        del root, writer, timeout, error_code
        calls.append(argv)
        if "--auto" in argv:
            raise CliError(
                "gh_pr_merge_failed",
                "gh pr merge failed",
                extra={"stderr": "GraphQL: Auto merge is not allowed for this repository"},
            )
        return subprocess.CompletedProcess(argv, 0, "", "")

    with patch("megaplan.chain._run_command", side_effect=fake_run):
        _enable_auto_merge(tmp_path, 7, writer=messages.append)

    assert calls == [
        ["gh", "pr", "merge", "7", "--auto", "--squash", "--delete-branch"],
        ["gh", "pr", "merge", "7", "--squash", "--delete-branch"],
    ]
    assert "falling back" in "".join(messages)


def test_pr_state_retries_transient_gh_failures(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    messages: list[str] = []

    def fake_run(root, argv, *, writer, timeout, error_code):
        del root, writer, timeout, error_code
        calls.append(argv)
        if len(calls) == 1:
            raise CliError(
                "gh_pr_view_failed",
                "gh pr view failed",
                extra={"stderr": "HTTP 504: 504 Gateway Timeout (https://api.github.com/graphql)"},
            )
        return subprocess.CompletedProcess(argv, 0, '{"state":"OPEN"}', "")

    with patch("megaplan.chain._run_command", side_effect=fake_run), \
         patch("megaplan.chain.time.sleep") as sleep:
        state = _pr_state(tmp_path, 11, writer=messages.append)

    assert state == "open"
    assert len(calls) == 2
    assert "transient gh pr view failure" in "".join(messages)
    sleep.assert_called_once()


def test_pr_state_retries_graphql_timeout_until_attempts_exhausted(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(root, argv, *, writer, timeout, error_code):
        del root, writer, timeout, error_code
        calls.append(argv)
        raise CliError(
            "gh_pr_view_failed",
            "gh pr view failed",
            extra={"stderr": "GraphQL: timeout while checking pull request state"},
        )

    with patch("megaplan.chain._run_command", side_effect=fake_run), \
         patch("megaplan.chain.time.sleep") as sleep:
        with pytest.raises(CliError) as exc_info:
            _pr_state(tmp_path, 11, writer=lambda _m: None)

    assert exc_info.value.code == "gh_pr_view_failed"
    assert len(calls) == 3
    assert sleep.call_count == 2


def test_pr_state_does_not_retry_non_transient_gh_failures(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(root, argv, *, writer, timeout, error_code):
        del root, writer, timeout, error_code
        calls.append(argv)
        raise CliError(
            "gh_pr_view_failed",
            "gh pr view failed",
            extra={"stderr": "GraphQL: Could not resolve to a PullRequest with the number of 11."},
        )

    with patch("megaplan.chain._run_command", side_effect=fake_run), \
         patch("megaplan.chain.time.sleep") as sleep:
        with pytest.raises(CliError) as exc_info:
            _pr_state(tmp_path, 11, writer=lambda _m: None)

    assert exc_info.value.code == "gh_pr_view_failed"
    assert len(calls) == 1
    sleep.assert_not_called()


def test_run_chain_advances_when_pr_already_merged(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}]},
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    with patch("megaplan.chain._refresh_main", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch"), \
         patch("megaplan.chain._ensure_milestone_pr", return_value=17), \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")), \
         patch("megaplan.chain._commit_and_push_phase"), \
         patch("megaplan.chain._pr_state", return_value="merged"), \
         patch("megaplan.chain._mark_pr_ready") as ready, \
         patch("megaplan.chain._enable_auto_merge") as merge:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    ready.assert_not_called()
    merge.assert_not_called()
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 1
    assert saved.completed[0]["pr_state"] == "merged"


def test_run_chain_review_policy_awaits_and_resumes_after_pr_merge(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m1.txt")
    i2 = _touch_idea(tmp_path, "m2.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "merge_policy": "review",
            "milestones": [
                {"label": "m1", "idea": str(i1), "branch": "mp/m1"},
                {"label": "m2", "idea": str(i2)},
            ],
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    with patch("megaplan.chain._refresh_main", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch"), \
         patch("megaplan.chain._ensure_milestone_pr", return_value=23), \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")), \
         patch("megaplan.chain._commit_and_push_phase"), \
         patch("megaplan.chain._pr_state", return_value="open"), \
         patch("megaplan.chain._mark_pr_ready"):
        first = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert first["status"] == "awaiting_pr_merge"
    waiting = load_chain_state(spec_path)
    assert waiting.current_milestone_index == 0
    assert waiting.pr_number == 23
    assert waiting.pr_state == "awaiting_merge"

    with patch("megaplan.chain._pr_state", return_value="open"):
        second = run_chain(spec_path, tmp_path, writer=lambda _m: None)
    assert second["status"] == "awaiting_pr_merge"
    assert load_chain_state(spec_path).current_milestone_index == 0

    with patch("megaplan.chain._pr_state", return_value="merged"), \
         patch("megaplan.chain._refresh_main", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", return_value="plan-m2"), \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m2", "done")):
        final = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert final["status"] == "done"
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 2
    assert [item["label"] for item in saved.completed] == ["m1", "m2"]
