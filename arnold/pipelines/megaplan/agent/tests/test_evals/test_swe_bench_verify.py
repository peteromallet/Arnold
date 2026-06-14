import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import evals.benchmarks.swe_bench as swe_bench_module
from evals.benchmarks.swe_bench import SWEBenchBackend


def _make_prepared(tmp_path: Path, *, fail_to_pass: str = '["pkg/tests/test_demo.py::test_it"]'):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return SimpleNamespace(
        path=str(workspace),
        eval_name="demo-instance",
        initial_commit_sha="base123",
        metadata={
            "instance_id": "demo-instance",
            "base_commit": "base123",
            "fail_to_pass": fail_to_pass,
        },
    )


def _make_config():
    return SimpleNamespace(models={"execute": "execute-model"}, test_timeout=30)


def test_verify_after_execute_returns_verify_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend = SWEBenchBackend()
    prepared = _make_prepared(tmp_path)
    config = _make_config()

    def fake_run(command, **kwargs):
        if command[:3] == ["git", "diff", "--text"]:
            return subprocess.CompletedProcess(command, 0, stdout="diff --git a/x b/x\n+fix\n", stderr="")
        if command[:3] == ["python", "-m", "swebench.harness.run_evaluation"]:
            result_dir = tmp_path / "evaluation_results" / "hermes-verify-demo-instance"
            result_dir.mkdir(parents=True, exist_ok=True)
            (result_dir / "result.json").write_text(
                json.dumps({"resolved_ids": ["demo-instance"]}),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="verify stdout", stderr="verify stderr")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(swe_bench_module.subprocess, "run", fake_run)

    result = backend.verify_after_execute(prepared, config)

    assert result is not None
    assert result.passed is True
    assert result.tests_run == ["pkg/tests/test_demo.py::test_it"]
    assert "verify stdout" in result.test_output
    assert "verify stderr" in result.test_output
    assert result.duration_seconds >= 0

    predictions_path = tmp_path / "_swebench_verify" / "demo-instance.jsonl"
    prediction = json.loads(predictions_path.read_text(encoding="utf-8").strip())
    assert prediction["instance_id"] == "demo-instance"
    assert prediction["model_name_or_path"] == "execute-model"
    assert "diff --git" in prediction["model_patch"]


def test_verify_after_execute_no_patch_returns_failed_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend = SWEBenchBackend()
    prepared = _make_prepared(tmp_path)
    config = _make_config()

    def fake_run(command, **kwargs):
        if command[:3] == ["git", "diff", "--text"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(swe_bench_module.subprocess, "run", fake_run)

    result = backend.verify_after_execute(prepared, config)

    assert result is not None
    assert result.passed is False
    assert result.tests_run == ["pkg/tests/test_demo.py::test_it"]
    assert "No code changes were made by the executor." in result.test_output


def test_verify_after_execute_no_fail_to_pass_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend = SWEBenchBackend()
    prepared = _make_prepared(tmp_path, fail_to_pass="[]")
    config = _make_config()

    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called when fail_to_pass is empty")

    monkeypatch.setattr(swe_bench_module.subprocess, "run", fail_run)

    assert backend.verify_after_execute(prepared, config) is None


def test_verify_after_execute_timeout_returns_failed_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend = SWEBenchBackend()
    prepared = _make_prepared(tmp_path)
    config = _make_config()

    def fake_run(command, **kwargs):
        if command[:3] == ["git", "diff", "--text"]:
            return subprocess.CompletedProcess(command, 0, stdout="diff --git a/x b/x\n+fix\n", stderr="")
        if command[:3] == ["python", "-m", "swebench.harness.run_evaluation"]:
            raise subprocess.TimeoutExpired(
                command,
                timeout=kwargs["timeout"],
                output="verify stdout",
                stderr="verify stderr",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(swe_bench_module.subprocess, "run", fake_run)

    result = backend.verify_after_execute(prepared, config)

    assert result is not None
    assert result.passed is False
    assert "verify stdout" in result.test_output
    assert "verify stderr" in result.test_output
    assert "Timed out after 30s" in result.test_output


def test_verify_after_execute_cleans_stale_artifacts_and_filters_by_run_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend = SWEBenchBackend()
    prepared = _make_prepared(tmp_path)
    config = _make_config()
    run_count = {"harness": 0}
    verify_result_path = tmp_path / "evaluation_results" / "hermes-verify-demo-instance" / "result.json"

    def fake_run(command, **kwargs):
        if command[:3] == ["git", "diff", "--text"]:
            return subprocess.CompletedProcess(command, 0, stdout="diff --git a/x b/x\n+fix\n", stderr="")
        if command[:3] == ["python", "-m", "swebench.harness.run_evaluation"]:
            run_count["harness"] += 1
            if run_count["harness"] == 2:
                assert not verify_result_path.exists(), "stale verify result should be removed before retry"
            verify_result_path.parent.mkdir(parents=True, exist_ok=True)
            if run_count["harness"] == 1:
                verify_payload = {"resolved_ids": ["demo-instance"]}
            else:
                verify_payload = {"resolved_ids": []}
                score_path = tmp_path / "evaluation_results" / "hermes-demo-instance" / "result.json"
                score_path.parent.mkdir(parents=True, exist_ok=True)
                score_path.write_text(
                    json.dumps({"resolved_ids": ["demo-instance"]}),
                    encoding="utf-8",
                )
            verify_result_path.write_text(json.dumps(verify_payload), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(swe_bench_module.subprocess, "run", fake_run)

    first = backend.verify_after_execute(prepared, config)
    second = backend.verify_after_execute(prepared, config)

    assert first is not None and first.passed is True
    assert second is not None and second.passed is False
    assert run_count["harness"] == 2
