import json
import subprocess
from pathlib import Path

from megaplan.bakeoff.metrics import collect_profile_metrics


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "README.md")
    _git(repo, "commit", "-m", "initial")


def _state(worktree: Path) -> dict:
    return {
        "schema_version": 1,
        "experiment_id": "exp-1",
        "base_sha": "base",
        "idea_hash": "idea",
        "idea_path": str(worktree / "idea.md"),
        "mode": "code",
        "profiles": [],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }


def _record(worktree: Path, outcome: dict | None = None) -> dict:
    return {
        "name": "standard",
        "worktree": str(worktree),
        "plan_id": "exp-1",
        "pid": None,
        "launched_at": "2026-04-24T10:00:00+00:00",
        "terminated_at": "2026-04-24T10:00:05+00:00",
        "outcome": outcome,
        "log_path": str(worktree / "auto.log"),
        "outcome_path": str(worktree / "outcome.json"),
    }


def test_collect_profile_metrics_full_schema_for_missing_worktree(tmp_path: Path) -> None:
    worktree = tmp_path / "missing"

    metrics = collect_profile_metrics(_state(worktree), _record(worktree, {"status": "failed"}))

    assert set(metrics) == {
        "duration_s",
        "cost_usd",
        "rework_cycles",
        "escalations",
        "review_verdict",
        "diff_lines",
        "tests_added",
        "scope_drift_severity_by_phase",
        "final_state",
        "outcome_status",
        "receipts_ref",
    }
    assert metrics["duration_s"] == 5.0
    assert metrics["diff_lines"] is None
    assert metrics["tests_added"] is None
    assert metrics["scope_drift_severity_by_phase"]["sprint1_pending"] is True
    assert metrics["outcome_status"] == "failed"


def test_collect_profile_metrics_counts_untracked_tests_and_relative_receipts(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    _init_repo(worktree)
    plan_dir = worktree / ".megaplan" / "plans" / "exp-1"
    receipts_dir = plan_dir / "receipts"
    receipts_dir.mkdir(parents=True)
    (receipts_dir / "receipt.json").write_text("{}", encoding="utf-8")
    output_file = plan_dir / "execution.json"
    output_file.write_text("{}", encoding="utf-8")
    (plan_dir / "review.json").write_text(json.dumps({"verdict": "pass"}), encoding="utf-8")
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "current_state": "state_reviewed",
                "history": [
                    {"step": "execute", "cost_usd": 0.25, "output_file": str(output_file)},
                    {"step": "review", "cost_usd": 0.5, "recommendation": "ESCALATE"},
                    {"step": "review", "cost_usd": 0.25},
                ],
                "meta": {"total_cost_usd": 99.0},
            }
        ),
        encoding="utf-8",
    )
    test_file = worktree / "tests" / "test_new.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_new():\n    assert True\n", encoding="utf-8")

    metrics = collect_profile_metrics(
        _state(worktree),
        _record(worktree, {"status": "done", "events": [{"type": "review_rework_cycle_count", "count": 3}]}),
    )

    assert metrics["cost_usd"] == 1.0
    assert metrics["rework_cycles"] == 3
    assert metrics["escalations"] == 1
    assert metrics["review_verdict"] == "pass"
    assert metrics["diff_lines"] and metrics["diff_lines"] > 0
    assert metrics["tests_added"] == 1
    assert metrics["receipts_ref"] == ["execution.json", "receipts/receipt.json"]

