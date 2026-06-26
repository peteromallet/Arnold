import json
import subprocess
from pathlib import Path

import pytest

import evals.benchmark.bootstrap as bootstrap_mod
import evals.benchmark.scoring as benchmark_scoring
from evals.benchmark.bootstrap import bootstrap_megaplan_state, verify_bootstrap
from evals.benchmark.scoring import (
    PhaseScore,
    score_critique,
    score_execute,
    score_plan,
    score_review,
)
from evals.run_evals import _session_key_for


def test_score_plan_valid_and_empty_trace() -> None:
    score = score_plan({"success": True, "state": "planned"}, [])

    assert score == PhaseScore(
        json_valid=1,
        required_keys=1,
        tool_use=0,
        web_search=0,
        build_pass=None,
        eval_pass=None,
        phase="plan",
        model="",
        eval_name="",
        duration_seconds=0.0,
        cost_usd=0.0,
        error=None,
    )


def test_score_plan_invalid_json() -> None:
    score = score_plan("{not-json", [])

    assert score.json_valid == 0
    assert score.required_keys == 0
    assert "invalid json" in (score.error or "")


def test_score_critique_missing_required_keys() -> None:
    trace = [
        {"role": "assistant", "tool_calls": [{"function": {"name": "read_file", "arguments": "{}"}}]}
    ]
    score = score_critique({"success": True}, trace)

    assert score.json_valid == 1
    assert score.required_keys == 0
    assert score.tool_use == 1
    assert score.web_search == 0


def test_score_review_valid_json_and_web_search() -> None:
    trace = [
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "read_file", "arguments": "{}"}},
                {"function": {"name": "web_search", "arguments": "{}"}},
            ],
        }
    ]

    score = score_review({"success": True, "review_verdict": "approved"}, trace)

    assert score.json_valid == 1
    assert score.required_keys == 1
    assert score.tool_use == 1
    assert score.web_search == 1


def test_score_execute_handles_no_code_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / "file.txt").write_text("before\n", encoding="utf-8")
    sha = _commit_all(repo, "initial")

    score = score_execute({"success": True, "state": "executed"}, [], repo, sha)

    assert score.json_valid == 1
    assert score.required_keys == 1
    assert score.build_pass == 0
    assert score.eval_pass == 0
    assert score.error == "workspace has no code changes"


def test_score_execute_uses_build_and_eval_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / "file.txt").write_text("before\n", encoding="utf-8")
    sha = _commit_all(repo, "initial")
    (repo / "file.txt").write_text("after\n", encoding="utf-8")

    calls: list[str] = []

    class FakeBuild:
        success = True

    class FakeEval:
        success = True

    def fake_build(workspace):
        assert Path(workspace) == repo
        calls.append("build")
        return FakeBuild()

    def fake_eval(workspace, results_json):
        assert Path(workspace) == repo
        assert results_json["status"] == "passed"
        calls.append("eval")
        return FakeEval()

    monkeypatch.setattr(benchmark_scoring, "check_build", fake_build)
    monkeypatch.setattr(benchmark_scoring, "run_eval_ts", fake_eval)

    trace = [
        {"role": "assistant", "tool_calls": [{"function": {"name": "write_file", "arguments": "{}"}}]}
    ]
    score = score_execute({"success": True, "state": "executed"}, trace, repo, sha)

    assert calls == ["build", "eval"]
    assert score.tool_use == 1
    assert score.build_pass == 1
    assert score.eval_pass == 1


def test_bootstrap_megaplan_state_matches_session_keys_and_prerequisites(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixtures"
    monkeypatch.setattr(bootstrap_mod, "FIXTURES_ROOT", fixture_root)
    fixture_dir = fixture_root / "demo-eval"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "plan_v1.md").write_text("# Plan\n", encoding="utf-8")
    (fixture_dir / "plan_v1.meta.json").write_text(
        json.dumps({"version": 1, "questions": [], "success_criteria": [], "assumptions": []}),
        encoding="utf-8",
    )
    (fixture_dir / "finalize.json").write_text(json.dumps({"tasks": []}), encoding="utf-8")
    (fixture_dir / "execution.json").write_text(json.dumps({"output": "ok"}), encoding="utf-8")
    (fixture_dir / "workspace_diff.patch").write_text(
        "\n".join(
            [
                "diff --git a/sample.txt b/sample.txt",
                "--- a/sample.txt",
                "+++ b/sample.txt",
                "@@ -1 +1 @@",
                "-before",
                "+after",
                "",
            ]
        ),
        encoding="utf-8",
    )

    workspace = _init_repo(tmp_path / "demo-eval")
    (workspace / "sample.txt").write_text("before\n", encoding="utf-8")
    _commit_all(workspace, "initial")
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "idea": "real idea",
                "created_at": "2026-03-26T00:00:00Z",
                "config": {"project_dir": str(workspace), "auto_approve": True, "robustness": "light"},
                "meta": {"notes": ["keep"]},
            }
        ),
        encoding="utf-8",
    )

    bootstrap_megaplan_state(
        plan_dir,
        "demo-plan",
        "openai/gpt-4.1-mini",
        "review",
        tmp_path / "hermes-home",
    )
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    expected_keys = {
        _session_key_for(phase, "hermes", "openai/gpt-4.1-mini")
        for phase in ("plan", "critique", "gate", "finalize", "execute", "review")
    }

    assert set(state["sessions"]) == expected_keys
    assert state["idea"] == "real idea"
    assert state["current_state"] == "executed"
    assert [entry["step"] for entry in state["history"]] == ["plan", "finalize", "execute"]
    assert (plan_dir / "plan_v1.md").exists()
    assert (plan_dir / "finalize.json").exists()
    assert (plan_dir / "execution.json").exists()
    assert (workspace / "sample.txt").read_text(encoding="utf-8") == "after\n"
    assert verify_bootstrap(plan_dir, "review") == []


def test_verify_bootstrap_catches_missing_files(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "current_state": "review",
                "iteration": 1,
                "sessions": {},
                "history": [],
            }
        ),
        encoding="utf-8",
    )

    issues = verify_bootstrap(plan_dir, "review")

    assert "missing plan_v1.md" in issues
    assert "missing finalize.json" in issues
    assert "missing execution.json" in issues


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tests@example.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=path, check=True, capture_output=True)
    return path


def _commit_all(path: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
