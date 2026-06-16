"""Tests for watchdog process-to-plan correlation."""

from __future__ import annotations

import json

from arnold.pipelines.megaplan.pipelines.live_supervisor.model import PlanEntry
from arnold.pipelines.megaplan.watchdog.correlate import correlate_processes_to_plans


def _process(pid: int, cmdline: str):
    class _P:
        pass

    p = _P()
    p.pid = pid
    p.cmdline = cmdline
    return p


def test_correlates_process_to_plan_by_exact_name():
    plan = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir="/tmp/repo/.megaplan/plans/my-plan",
        repo_path="/tmp/repo",
        state={},
    )
    processes = (_process(123, "/usr/bin/megaplan auto --plan my-plan"),)
    correlations = correlate_processes_to_plans(processes, (plan,))
    assert len(correlations) == 1
    assert correlations[0].method == "exact_name"
    assert correlations[0].process_pid == 123


def test_correlates_process_to_plan_by_exact_dir():
    plan = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir="/tmp/repo/.megaplan/plans/my-plan",
        repo_path="/tmp/repo",
        state={},
    )
    processes = (_process(123, "/usr/bin/megaplan auto --plan-dir /tmp/repo/.megaplan/plans/my-plan"),)
    correlations = correlate_processes_to_plans(processes, (plan,))
    assert len(correlations) == 1
    # The cmdline contains the full plan path, so cmdline_plan_path/exact_dir wins.
    assert correlations[0].method in ("exact_name", "exact_dir", "cmdline_plan_path")


def test_rejects_broad_repo_path_matches(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_dir = repo / ".megaplan" / "plans" / "my-plan"
    plan_dir.mkdir(parents=True)
    plan = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir=str(plan_dir),
        repo_path=str(repo),
        state={},
    )
    # Process only mentions the repo path, not the plan name or plan dir.
    processes = (_process(123, f"/usr/bin/megaplan auto --project-dir {repo}"),)
    correlations = correlate_processes_to_plans(processes, (plan,))
    assert correlations == ()


def test_correlates_by_chain_current_plan(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_dir = repo / ".megaplan" / "plans" / "my-plan"
    plan_dir.mkdir(parents=True)
    chain_spec = repo / "chain.yaml"
    chain_state = repo / "chain_state.json"
    chain_state.write_text(json.dumps({"current_plan_name": "my-plan"}))

    plan = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir=str(plan_dir),
        repo_path=str(repo),
        state={},
        chain_spec_path=str(chain_spec),
    )
    processes = (_process(123, "/usr/bin/megaplan chain status"),)
    correlations = correlate_processes_to_plans(processes, (plan,))
    assert len(correlations) == 1
    assert correlations[0].method == "chain_current_plan"


def test_correlates_by_cwd(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    plan_dir = repo / ".megaplan" / "plans" / "my-plan"
    plan_dir.mkdir(parents=True)

    plan = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir=str(plan_dir),
        repo_path=str(repo),
        state={},
    )

    class _Proc:
        pass

    proc = _Proc()
    proc.pid = 123
    proc.cmdline = "claude daemon run"
    proc.cwd = str(repo / "src")
    correlations = correlate_processes_to_plans((proc,), (plan,))
    assert len(correlations) == 1
    assert correlations[0].method == "repo_cwd_match"


def test_correlates_when_plan_name_appears_in_brief_path():
    """A plan name embedded in a brief filename must not hide the --name argument."""
    plan = PlanEntry(
        plan_id="my-plan",
        plan_name="my-plan",
        plan_dir="/tmp/repo/.megaplan/plans/my-plan",
        repo_path="/tmp/repo",
        state={},
    )
    processes = (_process(123, "python3 -m arnold.pipelines.megaplan init .megaplan/briefs/my-plan-after-2026.md --name my-plan --project-dir ."),)
    correlations = correlate_processes_to_plans(processes, (plan,))
    assert len(correlations) == 1
    assert correlations[0].method == "exact_name"
