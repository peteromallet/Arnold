import json
import subprocess
from pathlib import Path

from evals import scoring
from evals.scoring import check_build, generate_results_json, run_eval_ts


def _git_init_with_commit(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "tests@hermes.local"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Hermes Tests"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return ""


def test_generate_results_json_uses_initial_commit_sha_for_git_diff(tmp_path):
    repo = tmp_path / "workspace"
    _git_init_with_commit(repo)
    app_dir = repo / "src"
    app_dir.mkdir()
    tracked_file = app_dir / "app.tsx"
    tracked_file.write_text("export const value = 1;\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    initial_commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tracked_file.write_text("export const value = 2;\n", encoding="utf-8")

    trace = {
        "messages": [
            {
                "role": "assistant",
                "reasoning": "thinking",
                "tool_calls": [
                    {
                        "id": "read-1",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "src/app.tsx"}),
                        },
                    },
                    {
                        "id": "shell-1",
                        "function": {
                            "name": "terminal",
                            "arguments": json.dumps({"command": "npm test"}),
                        },
                    },
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "shell-1",
                "content": json.dumps({"exit_code": 0}),
            },
            {
                "role": "tool",
                "tool_call_id": "read-1",
                "content": json.dumps({"success": True}),
            },
        ]
    }

    result = generate_results_json(
        trace,
        repo,
        initial_commit_sha=initial_commit_sha,
        transcript_path="traces/execute_v1.json",
        transcript_raw_path="raw/execute_v1.txt",
        build_output_path="scoring/build.json",
        eval_output_path="scoring/eval.json",
    )

    assert result["o11y"]["filesModified"] == ["src/app.tsx"]
    assert result["o11y"]["filesRead"] == ["src/app.tsx"]
    assert result["o11y"]["toolCalls"]["file_read"] == 1
    assert result["o11y"]["toolCalls"]["shell"] == 1
    assert result["o11y"]["shellCommands"][0]["command"] == "npm test"
    assert result["transcriptPath"] == "traces/execute_v1.json"
    assert result["outputPaths"]["eval"] == "scoring/eval.json"


def test_check_build_uses_subprocess_result(monkeypatch, tmp_path):
    def fake_run(command, cwd, capture_output, text, timeout, check):
        assert command == ["npm", "run", "build"]
        assert cwd == tmp_path
        return subprocess.CompletedProcess(command, 0, stdout="build ok", stderr="")

    monkeypatch.setattr(scoring.subprocess, "run", fake_run)

    result = check_build(tmp_path, timeout_seconds=12)

    assert result.success is True
    assert result.returncode == 0
    assert result.stdout == "build ok"
    assert result.command == ["npm", "run", "build"]


def test_run_eval_ts_writes_results_and_parses_vitest_json(monkeypatch, tmp_path):
    def fake_run(command, cwd, capture_output, text, timeout, check):
        assert command == ["npx", "vitest", "run", "--reporter=json"]
        assert cwd == tmp_path
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='noise before json\n{"success": true, "numPassedTests": 2, "numTotalTests": 2}\n',
            stderr="",
        )

    monkeypatch.setattr(scoring.subprocess, "run", fake_run)

    result = run_eval_ts(tmp_path, {"status": "passed"}, timeout_seconds=15)

    results_path = tmp_path / "__agent_eval__" / "results.json"
    assert results_path.exists()
    assert json.loads(results_path.read_text(encoding="utf-8")) == {"status": "passed"}
    assert result.success is True
    assert result.reporter_json == {
        "success": True,
        "numPassedTests": 2,
        "numTotalTests": 2,
    }
