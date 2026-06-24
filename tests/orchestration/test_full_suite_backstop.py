from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.chain import (
    ChainState,
    load_chain_state,
    run_chain,
    save_chain_state,
)
from arnold_pipelines.megaplan.orchestration import full_suite_backstop
from arnold_pipelines.megaplan.orchestration.full_suite_backstop import (
    evaluate_full_suite_backstop,
    run_full_suite_backstop,
)
from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult


def _suite_result(
    tmp_path: Path,
    *,
    status: str,
    failures: list[str] | None = None,
    passes: list[str] | None = None,
    collected_ids: list[str] | None = None,
) -> SuiteRunResult:
    failures = list(failures or [])
    passes = list(passes or [])
    collected_ids = list(
        collected_ids if collected_ids is not None else failures + passes
    )
    return SuiteRunResult(
        run_id="run-1",
        phase="full_suite_backstop",
        command="pytest --tb=no -q --no-header -rA",
        duration=1.25,
        collected=len(collected_ids),
        collected_ids=collected_ids,
        failures=failures,
        passes=passes,
        status=status,  # type: ignore[arg-type]
        exit_code=0 if status == "passed" else 1,
        raw_log_path=tmp_path / "raw.log",
        code_hash="sha256:abc",
        collections_parse_ok=True,
    )


def _baseline(
    *, failing: list[str], collected: list[str] | None = None
) -> dict[str, object]:
    return {
        "failing_tests": sorted(failing),
        "collected_ids": sorted(collected if collected is not None else failing),
        "captured_at_sha": "base-sha",
        "milestone": "base",
    }


def test_evaluate_full_suite_backstop_delta_gate_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _baseline(
        failing=["tests/test_a.py::test_a"], collected=["tests/test_a.py::test_a"]
    )

    def run_current(
        *, failures: list[str], passes: list[str], collected_ids: list[str]
    ):
        monkeypatch.setattr(
            full_suite_backstop.suite_runner,
            "run_suite",
            lambda *args, **kwargs: _suite_result(
                tmp_path,
                status="failed" if failures else "passed",
                failures=failures,
                passes=passes,
                collected_ids=collected_ids,
            ),
        )
        return run_full_suite_backstop(
            tmp_path / "plan",
            tmp_path,
            {},
            baseline=baseline,
        )

    still_red = run_current(
        failures=["tests/test_a.py::test_a"],
        passes=[],
        collected_ids=["tests/test_a.py::test_a"],
    )
    assert still_red["delta_computed"] is True
    assert still_red["newly_failing"] == []
    assert evaluate_full_suite_backstop(still_red, "enforce")["blocks"] is False

    new_failure = run_current(
        failures=["tests/test_a.py::test_a", "tests/test_b.py::test_b"],
        passes=[],
        collected_ids=["tests/test_a.py::test_a", "tests/test_b.py::test_b"],
    )
    assert new_failure["newly_failing"] == ["tests/test_b.py::test_b"]
    assert evaluate_full_suite_backstop(new_failure, "enforce")["blocks"] is True

    deleted = run_current(failures=[], passes=[], collected_ids=[])
    assert deleted["deleted_tests"] == ["tests/test_a.py::test_a"]
    assert evaluate_full_suite_backstop(deleted, "enforce")["blocks"] is True

    for result in (still_red, new_failure, deleted, {"status": "error"}):
        assert evaluate_full_suite_backstop(result, "shadow")["blocks"] is False


def test_non_green_base_is_usable_in_enforce(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        full_suite_backstop.suite_runner,
        "run_suite",
        lambda *args, **kwargs: _suite_result(
            tmp_path,
            status="failed",
            failures=["tests/test_a.py::test_a"],
            collected_ids=["tests/test_a.py::test_a"],
        ),
    )

    result = run_full_suite_backstop(
        tmp_path / "plan",
        tmp_path,
        {},
        baseline=_baseline(
            failing=["tests/test_a.py::test_a"],
            collected=["tests/test_a.py::test_a"],
        ),
    )

    assert result["status"] == "failed"
    assert result["delta_computed"] is True
    assert result["newly_failing"] == []
    assert evaluate_full_suite_backstop(result, "enforce")["blocks"] is False


def test_uncertainty_blocks_in_enforce_and_not_shadow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        full_suite_backstop.suite_runner,
        "run_suite",
        lambda *args, **kwargs: _suite_result(
            tmp_path,
            status="passed",
            passes=["tests/test_ok.py::test_ok"],
        ),
    )

    missing_baseline = run_full_suite_backstop(tmp_path / "plan", tmp_path, {})
    runner_error = {"status": "error", "delta_computed": False}

    assert missing_baseline["delta_computed"] is False
    for result in (missing_baseline, runner_error):
        enforce = evaluate_full_suite_backstop(result, "enforce")
        assert enforce["blocks"] is True
        assert "could not verify" in enforce["reason"]
        assert evaluate_full_suite_backstop(result, "shadow")["blocks"] is False


def test_run_full_suite_backstop_passed_copies_config_and_forces_full(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_config: dict[str, object] = {}

    def fake_run_suite(
        project_dir, config, *, phase, deadline_seconds, idle_seconds=None
    ):
        del project_dir, deadline_seconds, idle_seconds
        assert phase == "full_suite_backstop"
        seen_config.update(config)
        return _suite_result(
            tmp_path, status="passed", passes=["tests/test_ok.py::test_ok"]
        )

    monkeypatch.setattr(full_suite_backstop.suite_runner, "run_suite", fake_run_suite)
    caller_config = {
        "test_selection": "scoped",
        "test_command": "pytest tests/scoped.py::test_one",
        "test_baseline_timeout": 30,
    }

    result = run_full_suite_backstop(tmp_path / "plan", tmp_path, caller_config)

    assert result["status"] == "passed"
    assert result["passed"] == 1
    assert result["failed"] == 0
    assert result["failing_tests"] == []
    assert seen_config["test_selection"] == "full"
    assert "test_command" not in seen_config
    assert caller_config == {
        "test_selection": "scoped",
        "test_command": "pytest tests/scoped.py::test_one",
        "test_baseline_timeout": 30,
    }


def test_run_full_suite_backstop_failed_returns_failing_tests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        full_suite_backstop.suite_runner,
        "run_suite",
        lambda *args, **kwargs: _suite_result(
            tmp_path,
            status="failed",
            failures=["tests/test_bad.py::test_bad"],
            passes=["tests/test_ok.py::test_ok"],
        ),
    )

    result = run_full_suite_backstop(tmp_path / "plan", tmp_path, {})

    assert result["status"] == "failed"
    assert result["passed"] == 1
    assert result["failed"] == 1
    assert result["failing_tests"] == ["tests/test_bad.py::test_bad"]
    assert result["ran"] is True


def test_run_full_suite_backstop_raised_runner_exception_is_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_suite(*args, **kwargs):
        del args, kwargs
        raise TimeoutError("suite timed out")

    monkeypatch.setattr(full_suite_backstop.suite_runner, "run_suite", fake_run_suite)

    result = run_full_suite_backstop(
        tmp_path / "plan", tmp_path, {"test_command": "pytest x"}
    )

    assert result["status"] == "error"
    assert result["ran"] is False
    assert result["passed"] is None
    assert result["failed"] is None
    assert "TimeoutError" in result["note"]
    assert result["delta_computed"] is False


def test_full_suite_backstop_baseline_persistence_and_next_delta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    plan1 = _write_plan_state(tmp_path, "plan-m1")
    plan2 = _write_plan_state(tmp_path, "plan-m2")
    baseline_path = chain_module._full_suite_backstop_baseline_path_for(spec_path)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    chain_module.atomic_write_json(
        baseline_path,
        _baseline(
            failing=["tests/test_a.py::test_a"],
            collected=["tests/test_a.py::test_a"],
        ),
    )

    runs = iter(
        [
            _suite_result(
                tmp_path,
                status="failed",
                failures=["tests/test_a.py::test_a"],
                collected_ids=["tests/test_a.py::test_a"],
            ),
            _suite_result(
                tmp_path,
                status="failed",
                failures=["tests/test_a.py::test_a", "tests/test_b.py::test_b"],
                collected_ids=["tests/test_a.py::test_a", "tests/test_b.py::test_b"],
            ),
        ]
    )
    monkeypatch.setattr(
        full_suite_backstop.suite_runner,
        "run_suite",
        lambda *args, **kwargs: next(runs),
    )

    gate1 = chain_module._run_full_suite_backstop_gate(
        tmp_path,
        spec_path,
        plan1.name,
        "m1",
        "enforce",
        log_fn=lambda _msg: None,
    )
    assert gate1["blocks"] is False
    assert chain_module._persist_full_suite_backstop_baseline(
        spec_path,
        gate1["result"],
        captured_at_sha="commit-m1",
        milestone_label="m1",
    )

    saved = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert saved == {
        "failing_tests": ["tests/test_a.py::test_a"],
        "collected_ids": ["tests/test_a.py::test_a"],
        "captured_at_sha": "commit-m1",
        "milestone": "m1",
    }

    gate2 = chain_module._run_full_suite_backstop_gate(
        tmp_path,
        spec_path,
        plan2.name,
        "m2",
        "enforce",
        log_fn=lambda _msg: None,
    )
    assert gate2["blocks"] is True
    assert gate2["result"]["newly_failing"] == ["tests/test_b.py::test_b"]
    assert gate2["result"]["baseline_failing_count"] == 1


def test_full_suite_backstop_retry_once_error_then_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    plan_dir = _write_plan_state(tmp_path, "plan-m1")
    baseline_path = chain_module._full_suite_backstop_baseline_path_for(spec_path)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    chain_module.atomic_write_json(
        baseline_path,
        _baseline(
            failing=["tests/test_a.py::test_a"],
            collected=["tests/test_a.py::test_a"],
        ),
    )
    calls = {"count": 0}

    def fake_run_suite(*args, **kwargs):
        del args, kwargs
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("transient timeout")
        return _suite_result(
            tmp_path,
            status="failed",
            failures=["tests/test_a.py::test_a"],
            collected_ids=["tests/test_a.py::test_a"],
        )

    monkeypatch.setattr(full_suite_backstop.suite_runner, "run_suite", fake_run_suite)

    gate = chain_module._run_full_suite_backstop_gate(
        tmp_path,
        spec_path,
        plan_dir.name,
        "m1",
        "enforce",
        log_fn=lambda _msg: None,
    )

    assert calls["count"] == 2
    assert gate["blocks"] is False
    assert gate["result"]["delta_computed"] is True


def test_full_suite_backstop_retry_once_still_error_blocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    plan_dir = _write_plan_state(tmp_path, "plan-m1")
    baseline_path = chain_module._full_suite_backstop_baseline_path_for(spec_path)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    chain_module.atomic_write_json(
        baseline_path,
        _baseline(
            failing=["tests/test_a.py::test_a"],
            collected=["tests/test_a.py::test_a"],
        ),
    )
    calls = {"count": 0}

    def fake_run_suite(*args, **kwargs):
        del args, kwargs
        calls["count"] += 1
        raise TimeoutError("suite timed out")

    monkeypatch.setattr(full_suite_backstop.suite_runner, "run_suite", fake_run_suite)

    gate = chain_module._run_full_suite_backstop_gate(
        tmp_path,
        spec_path,
        plan_dir.name,
        "m1",
        "enforce",
        log_fn=lambda _msg: None,
    )

    assert calls["count"] == 2
    assert gate["blocks"] is True
    assert "could not verify" in gate["reason"]


def _write_chain_spec(tmp_path: Path) -> Path:
    idea = tmp_path / "idea.txt"
    idea.write_text("ship milestone", encoding="utf-8")
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n" "milestones:\n" "  - label: m1\n" f"    idea: {idea}\n",
        encoding="utf-8",
    )
    return spec_path


def _write_plan_state(
    root: Path, plan_name: str, *, current_state: str = "done"
) -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_name,
                "current_state": current_state,
                "config": {"project_dir": str(root)},
                "meta": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize_output.json").write_text(
        json.dumps({"tasks": [{"id": "T1", "files_changed": ["src/app.py"]}]}) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["src/app.py"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return plan_dir


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc.stdout.strip()


def _init_git_with_semantic_change(root: Path) -> str:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "app.py").write_text("print('base')\n", encoding="utf-8")
    _git(root, "add", "src/app.py")
    _git(root, "commit", "-m", "base")
    base = _git(root, "rev-parse", "HEAD")
    (root / "src" / "app.py").write_text("print('done')\n", encoding="utf-8")
    _git(root, "add", "src/app.py")
    _git(root, "commit", "-m", "done")
    return base


def _patch_light_chain(
    plan_name: str,
    backstop_result: dict[str, object],
    *,
    current_head_sha: str | None = None,
):
    return (
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._init_plan", return_value=plan_name),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan",
            return_value=chain_module.DriverOutcome(
                status="done",
                plan=plan_name,
                final_state="done",
                iterations=1,
                reason="",
            ),
        ),
        patch(
            "arnold_pipelines.megaplan.chain._current_head_sha",
            return_value=current_head_sha,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._commit_phase", return_value="commit123"
        ),
        patch(
            "arnold_pipelines.megaplan.chain._plan_terminal_completion_is_authoritative",
            return_value=(True, ""),
        ),
        patch(
            "arnold_pipelines.megaplan.chain._shadow_milestone_completion_verdict",
            return_value=False,
        ),
        patch(
            "arnold_pipelines.megaplan.orchestration.full_suite_backstop.run_full_suite_backstop",
            return_value=backstop_result,
        ),
    )


def test_run_chain_full_suite_backstop_shadow_records_and_advances(
    tmp_path: Path,
) -> None:
    base_sha = _init_git_with_semantic_change(tmp_path)
    spec_path = _write_chain_spec(tmp_path)
    plan_name = "plan-m1"
    plan_dir = _write_plan_state(tmp_path, plan_name, current_state="done")
    save_chain_state(
        spec_path,
        ChainState(
            completed=[{"label": "m1", "plan": plan_name, "status": "finalized"}],
            full_suite_backstop_mode="shadow",
        ),
    )
    backstop_result = {
        "status": "failed",
        "passed": 1,
        "failed": 1,
        "failing_tests": ["tests/test_bad.py::test_bad"],
        "collected_ids": ["tests/test_bad.py::test_bad", "tests/test_ok.py::test_ok"],
        "newly_failing": [],
        "deleted_tests": [],
        "baseline_failing_count": 1,
        "current_failing_count": 1,
        "delta_computed": True,
        "command": "pytest",
        "duration_s": 1.0,
        "ran": True,
        "note": "suite status=failed",
    }

    patches = _patch_light_chain(
        plan_name,
        backstop_result,
        current_head_sha=base_sha,
    )
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            no_push=True,
            mode="execute",
            full_suite_backstop_mode="shadow",
        )

    assert result["status"] == "done"
    assert (
        json.loads((plan_dir / "full_suite_backstop.json").read_text())
        == backstop_result
    )
    saved = load_chain_state(spec_path)
    assert saved.completed[-1]["full_suite_backstop"]["status"] == "failed"
    assert saved.completed[-1]["full_suite_backstop"]["blocks"] is False


def test_run_chain_full_suite_backstop_enforce_blocks_before_commit(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    plan_name = "plan-m1"
    plan_dir = _write_plan_state(tmp_path, plan_name, current_state="finalized")
    save_chain_state(
        spec_path,
        ChainState(
            completed=[{"label": "m1", "plan": plan_name, "status": "finalized"}],
            full_suite_backstop_mode="enforce",
        ),
    )
    backstop_result = {
        "status": "failed",
        "passed": 0,
        "failed": 1,
        "failing_tests": ["tests/test_bad.py::test_bad"],
        "collected_ids": ["tests/test_bad.py::test_bad"],
        "newly_failing": ["tests/test_bad.py::test_bad"],
        "deleted_tests": [],
        "baseline_failing_count": 0,
        "current_failing_count": 1,
        "delta_computed": True,
        "command": "pytest",
        "duration_s": 1.0,
        "ran": True,
        "note": "suite status=failed",
    }

    patches = _patch_light_chain(plan_name, backstop_result)
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _msg: None,
            no_push=True,
            mode="execute",
            full_suite_backstop_mode="enforce",
        )

    assert result["status"] == "blocked"
    assert "full_suite_backstop.json" in result["reason"]
    assert "tests/test_bad.py::test_bad" in result["reason"]
    assert (
        json.loads((plan_dir / "full_suite_backstop.json").read_text())
        == backstop_result
    )
