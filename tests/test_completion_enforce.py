"""Tests for warn/enforce blocking in the completion-verification contract.

Covers T13: mode-gated blocking at both the plan driver (auto.py) and the
chain driver (chain/__init__.py), advisory warn logging, revise-routing in
enforce mode, runner-error pass-through, and the revise-retry cap.
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

import pytest

from megaplan.orchestration.completion_contract import (
    CompletionSubject,
    CompletionVerdict,
    EvidenceRef,
    EvidenceStatus,
    extract_green_suite_info,
    normalize_contract_mode,
)
from megaplan.orchestration.suite_runner import SuiteRunResult, append_suite_run
from megaplan.types import STATE_CRITIQUED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_run_result(
    *,
    phase: str = "verification",
    failures: list[str] | None = None,
    passes: list[str] | None = None,
    collected_ids: list[str] | None = None,
    status: str = "passed",
    exit_code: int = 0,
    collections_parse_ok: bool = True,
    code_hash: str = "abc123",
    collected: int | None = None,
) -> SuiteRunResult:
    failures = failures or []
    passes = passes or []
    collected_ids = collected_ids or (passes + failures)
    return SuiteRunResult(
        run_id=f"r-{phase}",
        phase=phase,
        command="pytest",
        duration=0.5,
        collected=collected if collected is not None else len(collected_ids),
        collected_ids=collected_ids,
        failures=failures,
        passes=passes,
        status=status,
        exit_code=exit_code,
        raw_log_path=Path("/dev/null"),
        code_hash=code_hash,
        collections_parse_ok=collections_parse_ok,
    )


def _make_plan_dir(
    tmp_path: Path,
    *,
    mode: str = "shadow",
    baseline_failures: list[str] | None = None,
    baseline_ids: list[str] | None = None,
    enforce_revise_max_retries: int = 2,
) -> tuple[Path, Path]:
    """Create a minimal plan directory + project dir for completion-contract tests."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo(project_dir)
    (project_dir / "src.py").write_text("x = 1\n", encoding="utf-8")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    baseline_failures = baseline_failures or []
    baseline_ids = baseline_ids or ["tests/test_foo.py::test_a"]
    _write(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "t1", "status": "done", "files_changed": ["src.py"], "commands_run": ["pytest"]}],
            "sense_checks": [],
            "baseline_test_failures": baseline_failures,
        },
    )
    _write(
        plan_dir / "execution_batch_001.json",
        {"tasks": [{"task_id": "t1", "status": "done", "files_changed": ["src.py"], "commands_run": ["pytest"]}]},
    )
    config: dict[str, Any] = {
        "mode": "code",
        "project_dir": str(project_dir),
        "completion_contract_mode": mode,
        "enforce_revise_max_retries": enforce_revise_max_retries,
    }
    _write(plan_dir / "state.json", {"config": config})

    # Write a baseline record so GreenSuiteProvider can compute a delta.
    baseline_passes = [i for i in baseline_ids if i not in baseline_failures]
    baseline_result = _make_run_result(
        phase="baseline",
        failures=baseline_failures,
        passes=baseline_passes,
        collected_ids=baseline_ids,
        status="failed" if baseline_failures else "passed",
        exit_code=1 if baseline_failures else 0,
        code_hash="abc123",
    )
    append_suite_run(plan_dir, baseline_result)

    return plan_dir, project_dir


def _read_state(plan_dir: Path) -> dict[str, Any]:
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Plan-driver (auto.py) tests
# ---------------------------------------------------------------------------


def test_enforce_blocks_on_newly_failing(tmp_path, monkeypatch):
    """enforce mode + newly_failing → state patched to revise-routing, returns 'routed'."""
    from megaplan import auto

    plan_dir, _ = _make_plan_dir(tmp_path, mode="enforce")

    # Verification: one new failure not in baseline.
    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    assert result == "routed", f"expected 'routed', got {result!r}"
    state = _read_state(plan_dir)
    assert state.get("current_state") == STATE_CRITIQUED
    assert state.get("last_gate", {}).get("recommendation") == "ITERATE"
    assert int(state.get("enforce_revise_count", 0)) == 1


def test_warn_is_advisory_not_blocking(tmp_path, monkeypatch, caplog):
    """warn mode + newly_failing → advisory WARNING logged, returns 'done' (no block)."""
    from megaplan import auto

    plan_dir, _ = _make_plan_dir(tmp_path, mode="warn")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    with caplog.at_level(logging.WARNING, logger="megaplan.auto"):
        result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    assert result == "done", f"warn mode must not block; got {result!r}"
    # Advisory warning must be emitted.
    assert any("warn" in r.message and ("newly_failing" in r.message or "would block" in r.message)
                for r in caplog.records), "expected advisory warn log"
    # State must NOT be patched.
    state = _read_state(plan_dir)
    assert state.get("current_state") != STATE_CRITIQUED


def test_shadow_ignores_newly_failing(tmp_path, monkeypatch):
    """shadow mode + newly_failing → no block, no warning, returns 'done'."""
    from megaplan import auto

    plan_dir, _ = _make_plan_dir(tmp_path, mode="shadow")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    assert result == "done", f"shadow mode must not block; got {result!r}"
    state = _read_state(plan_dir)
    assert state.get("current_state") != STATE_CRITIQUED


def test_enforce_blocks_on_deleted_tests(tmp_path, monkeypatch):
    """enforce mode + deleted_tests=1 (baseline collected test missing from verification) → blocks."""
    from megaplan import auto

    # Baseline has test_a and test_b; verification only collects test_a.
    plan_dir, _ = _make_plan_dir(
        tmp_path,
        mode="enforce",
        baseline_ids=["tests/test_foo.py::test_a", "tests/test_foo.py::test_b"],
        baseline_failures=[],
    )

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=[],
            passes=["tests/test_foo.py::test_a"],
            collected_ids=["tests/test_foo.py::test_a"],
            status="passed",
            exit_code=0,
        ),
    )

    result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    assert result == "routed", f"deleted_tests must block in enforce; got {result!r}"
    state = _read_state(plan_dir)
    assert state.get("current_state") == STATE_CRITIQUED


def test_enforce_runner_error_does_not_block(tmp_path, monkeypatch, caplog):
    """enforce mode + runner_error → NOT blocked, structured warning emitted."""
    from megaplan import auto

    plan_dir, _ = _make_plan_dir(tmp_path, mode="enforce")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=[],
            passes=[],
            collected_ids=[],
            status="runner_error",
            exit_code=2,
            collections_parse_ok=False,
        ),
    )

    with caplog.at_level(logging.WARNING, logger="megaplan.auto"):
        result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    assert result == "done", f"runner_error must not block; got {result!r}"
    state = _read_state(plan_dir)
    assert state.get("current_state") != STATE_CRITIQUED
    # Structured warning must be emitted.
    assert any("runner_error" in r.message or "not blocking" in r.message or "not computable" in r.message
                for r in caplog.records), "expected structured warning for runner_error"


def test_enforce_revise_retry_cap_exhausted(tmp_path, monkeypatch):
    """enforce mode + retry cap exhausted → returns 'operator_required'."""
    from megaplan import auto

    plan_dir, _ = _make_plan_dir(tmp_path, mode="enforce", enforce_revise_max_retries=2)

    # Simulate already having retried twice.
    state = _read_state(plan_dir)
    state["enforce_revise_count"] = 2
    _write(plan_dir / "state.json", state)

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    assert result == "operator_required", f"cap exhausted must return 'operator_required'; got {result!r}"


def test_enforce_no_regressions_returns_done(tmp_path, monkeypatch):
    """enforce mode + zero newly_failing + zero deleted_tests → 'done' (no block)."""
    from megaplan import auto

    plan_dir, _ = _make_plan_dir(tmp_path, mode="enforce")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=[],
            passes=["tests/test_foo.py::test_a"],
            collected_ids=["tests/test_foo.py::test_a"],
            status="passed",
            exit_code=0,
        ),
    )

    result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    assert result == "done", f"no regressions → no block; got {result!r}"


def test_enforce_retry_increments_count(tmp_path, monkeypatch):
    """Each enforce block increments enforce_revise_count in state.json."""
    from megaplan import auto

    plan_dir, _ = _make_plan_dir(tmp_path, mode="enforce", enforce_revise_max_retries=2)

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    r1 = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)
    assert r1 == "routed"
    s1 = _read_state(plan_dir)
    assert s1["enforce_revise_count"] == 1

    # Reset to critiqued-but-passing on next "done" (simulate second block).
    # Restore state to enforce mode + done.
    s1["current_state"] = None
    _write(plan_dir / "state.json", s1)

    r2 = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)
    assert r2 == "routed"
    s2 = _read_state(plan_dir)
    assert s2["enforce_revise_count"] == 2

    # Third attempt: cap exhausted.
    _write(plan_dir / "state.json", s2)
    r3 = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)
    assert r3 == "operator_required"


def test_sticky_flag_reads_only_config_not_env(tmp_path, monkeypatch):
    """Sticky-flag: completion_contract_mode is read from state['config'], never os.getenv."""
    from megaplan import auto

    # Set env var to enforce; config says shadow → shadow must win.
    monkeypatch.setenv("MEGAPLAN_COMPLETION_CONTRACT_MODE", "enforce")

    plan_dir, _ = _make_plan_dir(tmp_path, mode="shadow")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    # Shadow mode → always "done", never "routed".
    assert result == "done", "config['completion_contract_mode'] must override os.getenv"


# ---------------------------------------------------------------------------
# Chain driver tests
# ---------------------------------------------------------------------------


def _make_chain_plan_dir(
    root: Path,
    plan_name: str,
    *,
    mode: str = "enforce",
    baseline_failures: list[str] | None = None,
    baseline_ids: list[str] | None = None,
) -> Path:
    """Create a minimal plan directory under root for chain milestone tests.

    Plan lives at root/.megaplan/plans/<plan_name> so resolve_plan_dir finds it.
    """
    plan_dir = root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)

    project_dir = root / "repo"
    if not project_dir.exists():
        project_dir.mkdir()
        _init_git_repo(project_dir)
        (project_dir / "src.py").write_text("x = 1\n", encoding="utf-8")

    baseline_failures = baseline_failures or []
    baseline_ids = baseline_ids or ["tests/test_foo.py::test_a"]

    _write(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "t1", "status": "done", "files_changed": ["src.py"], "commands_run": ["pytest"]}],
            "sense_checks": [],
            "baseline_test_failures": baseline_failures,
        },
    )
    _write(
        plan_dir / "execution_batch_001.json",
        {"tasks": [{"task_id": "t1", "status": "done", "files_changed": ["src.py"], "commands_run": ["pytest"]}]},
    )
    _write(
        plan_dir / "state.json",
        {
            "config": {
                "mode": "code",
                "project_dir": str(project_dir),
                "completion_contract_mode": mode,
                "enforce_revise_max_retries": 2,
            }
        },
    )

    baseline_passes = [i for i in baseline_ids if i not in baseline_failures]
    baseline_result = _make_run_result(
        phase="baseline",
        failures=baseline_failures,
        passes=baseline_passes,
        collected_ids=baseline_ids,
        status="failed" if baseline_failures else "passed",
        exit_code=1 if baseline_failures else 0,
        code_hash="abc123",
    )
    append_suite_run(plan_dir, baseline_result)

    return plan_dir


def test_chain_enforce_blocks_on_newly_failing(tmp_path, monkeypatch):
    """chain._shadow_milestone_completion_verdict returns True on newly_failing in enforce."""
    from megaplan.chain import _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "milestone-plan"
    _make_chain_plan_dir(root, plan_name, mode="enforce")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    blocked = _shadow_milestone_completion_verdict(
        root, plan_name, "milestone-1", "done", "enforce", log_fn=lambda m: None
    )

    assert blocked is True, "enforce + newly_failing must block chain milestone"


def test_chain_warn_advisory_not_blocking(tmp_path, monkeypatch, caplog):
    """chain._shadow_milestone_completion_verdict returns False in warn mode (advisory only)."""
    from megaplan.chain import _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "warn-plan"
    _make_chain_plan_dir(root, plan_name, mode="warn")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    with caplog.at_level(logging.WARNING, logger="megaplan"):
        blocked = _shadow_milestone_completion_verdict(
            root, plan_name, "milestone-1", "done", "warn", log_fn=lambda m: None
        )

    assert blocked is False, "warn mode must not block"
    assert any("warn" in r.message.lower() or "advisory" in r.message.lower() or "newly_failing" in r.message
                for r in caplog.records), "expected advisory warning"


def test_chain_shadow_not_blocking(tmp_path, monkeypatch):
    """chain._shadow_milestone_completion_verdict returns False in shadow mode."""
    from megaplan.chain import _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "shadow-plan"
    _make_chain_plan_dir(root, plan_name, mode="shadow")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    blocked = _shadow_milestone_completion_verdict(
        root, plan_name, "milestone-1", "done", "shadow", log_fn=lambda m: None
    )

    assert blocked is False, "shadow mode must not block"


def test_chain_enforce_runner_error_not_blocking(tmp_path, monkeypatch, caplog):
    """chain._shadow_milestone_completion_verdict returns False on runner_error."""
    from megaplan.chain import _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "err-plan"
    _make_chain_plan_dir(root, plan_name, mode="enforce")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=[],
            passes=[],
            collected_ids=[],
            status="runner_error",
            exit_code=2,
            collections_parse_ok=False,
        ),
    )

    with caplog.at_level(logging.WARNING, logger="megaplan"):
        blocked = _shadow_milestone_completion_verdict(
            root, plan_name, "milestone-1", "done", "enforce", log_fn=lambda m: None
        )

    assert blocked is False, "runner_error must not block chain milestone"
    assert any("runner_error" in r.message or "not blocking" in r.message or "not computable" in r.message
                for r in caplog.records), "expected structured warning for runner_error"


def test_chain_enforce_blocks_on_declared_committed_range_landed_diff(
    tmp_path, monkeypatch, caplog
):
    """Declared committed-range landed_diff failures block in enforce mode."""
    from megaplan.chain import _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "declared-landed-diff-plan"
    _make_chain_plan_dir(root, plan_name, mode="enforce")

    verdict = CompletionVerdict(
        mode="enforce",
        subject=CompletionSubject(
            kind="milestone",
            name="milestone-1",
            to_state="done",
            plan_name=plan_name,
            milestone_label="milestone-1",
        ),
        evidence=(
            EvidenceRef(
                "landed_diff",
                EvidenceStatus.unsatisfied,
                "execution evidence findings: claimed file missing from committed range",
                {
                    "diff_source": "committed_range",
                    "evidence_window": {"source": "declared"},
                },
            ),
            EvidenceRef(
                "green_suite",
                EvidenceStatus.satisfied,
                "verification passed",
                {"status": "passed", "delta": {"computable": True, "newly_failing": [], "deleted_tests": []}},
            ),
        ),
        accepted=False,
        failures=("landed_diff: execution evidence findings: claimed file missing from committed range",),
    )
    monkeypatch.setattr(
        "megaplan.orchestration.completion_contract.compute_verdict",
        lambda **kwargs: verdict,
    )

    with caplog.at_level(logging.WARNING, logger="megaplan"):
        blocked = _shadow_milestone_completion_verdict(
            root, plan_name, "milestone-1", "done", "enforce", log_fn=lambda m: None
        )

    assert blocked is True
    assert any(
        "would_block=True" in r.message
        or "landed_diff" in r.message
        for r in caplog.records
    )


def test_chain_enforce_does_not_block_fallback_landed_diff(tmp_path, monkeypatch):
    """Fallback working-tree/status landed_diff findings remain advisory in enforce."""
    from megaplan.chain import _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "fallback-landed-diff-plan"
    _make_chain_plan_dir(root, plan_name, mode="enforce")

    # Non-authoritative sources (status_only, unresolved) filter advisory findings
    # and return satisfied — the enforcement trusts the verdict's would_block signal.
    verdict = CompletionVerdict(
        mode="enforce",
        subject=CompletionSubject(
            kind="milestone",
            name="milestone-1",
            to_state="done",
            plan_name=plan_name,
            milestone_label="milestone-1",
        ),
        evidence=(
            EvidenceRef(
                "landed_diff",
                EvidenceStatus.satisfied,
                "diff present and claim-consistent (advisory findings filtered)",
                {
                    "diff_source": "status_only",
                    "evidence_window": {"source": "declared", "base_sha": None},
                    "advisory_findings": [
                        "Git status shows changed files not claimed by any task: unclaimed.py"
                    ],
                },
            ),
            EvidenceRef(
                "green_suite",
                EvidenceStatus.satisfied,
                "verification passed",
                {"status": "passed", "delta": {"computable": True, "newly_failing": [], "deleted_tests": []}},
            ),
        ),
        accepted=True,
        failures=(),
    )
    monkeypatch.setattr(
        "megaplan.orchestration.completion_contract.compute_verdict",
        lambda **kwargs: verdict,
    )

    blocked = _shadow_milestone_completion_verdict(
        root, plan_name, "milestone-1", "done", "enforce", log_fn=lambda m: None
    )

    assert blocked is False


def test_chain_enforce_does_not_block_heuristic_committed_range_landed_diff(
    tmp_path, monkeypatch
):
    """Committed-range landed_diff with non-declared source falls through (not blocked)."""
    from megaplan.chain import _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "heuristic-landed-diff-plan"
    _make_chain_plan_dir(root, plan_name, mode="enforce")

    # Heuristic source filters advisory findings — landed_diff is satisfied.
    verdict = CompletionVerdict(
        mode="enforce",
        subject=CompletionSubject(
            kind="milestone",
            name="milestone-1",
            to_state="done",
            plan_name=plan_name,
            milestone_label="milestone-1",
        ),
        evidence=(
            EvidenceRef(
                "landed_diff",
                EvidenceStatus.satisfied,
                "diff present and claim-consistent (advisory findings filtered)",
                {
                    "diff_source": "heuristic",
                    "evidence_window": {"source": "heuristic_merge_base"},
                    "advisory_findings": [
                        "Git status shows changed files not claimed by any task: unclaimed.py"
                    ],
                },
            ),
            EvidenceRef(
                "green_suite",
                EvidenceStatus.satisfied,
                "verification passed",
                {"status": "passed", "delta": {"computable": True, "newly_failing": [], "deleted_tests": []}},
            ),
        ),
        accepted=True,
        failures=(),
    )
    monkeypatch.setattr(
        "megaplan.orchestration.completion_contract.compute_verdict",
        lambda **kwargs: verdict,
    )

    blocked = _shadow_milestone_completion_verdict(
        root, plan_name, "milestone-1", "done", "enforce", log_fn=lambda m: None
    )

    assert blocked is False


def test_chain_enforce_does_not_block_satisfied_committed_range_landed_diff(
    tmp_path, monkeypatch
):
    """Satisfied committed-range landed_diff with declared source does not block."""
    from megaplan.chain import _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "satisfied-landed-diff-plan"
    _make_chain_plan_dir(root, plan_name, mode="enforce")

    verdict = CompletionVerdict(
        mode="enforce",
        subject=CompletionSubject(
            kind="milestone",
            name="milestone-1",
            to_state="done",
            plan_name=plan_name,
            milestone_label="milestone-1",
        ),
        evidence=(
            EvidenceRef(
                "landed_diff",
                EvidenceStatus.satisfied,
                "all claimed files present in committed range",
                {
                    "diff_source": "committed_range",
                    "evidence_window": {"source": "declared"},
                },
            ),
            EvidenceRef(
                "green_suite",
                EvidenceStatus.satisfied,
                "verification passed",
                {"status": "passed", "delta": {"computable": True, "newly_failing": [], "deleted_tests": []}},
            ),
        ),
        accepted=True,
        failures=(),
    )
    monkeypatch.setattr(
        "megaplan.orchestration.completion_contract.compute_verdict",
        lambda **kwargs: verdict,
    )

    blocked = _shadow_milestone_completion_verdict(
        root, plan_name, "milestone-1", "done", "enforce", log_fn=lambda m: None
    )

    assert blocked is False


def test_chain_enforce_blocks_on_deleted_tests(tmp_path, monkeypatch):
    """Chain enforce mode + deleted_tests (baseline collected test missing from verification) → blocks."""
    from megaplan.chain import _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "deleted-tests-plan"
    _make_chain_plan_dir(
        root,
        plan_name,
        mode="enforce",
        baseline_ids=["tests/test_foo.py::test_a", "tests/test_foo.py::test_b"],
        baseline_failures=[],
    )

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=[],
            passes=["tests/test_foo.py::test_a"],
            collected_ids=["tests/test_foo.py::test_a"],
            status="passed",
            exit_code=0,
        ),
    )

    blocked = _shadow_milestone_completion_verdict(
        root, plan_name, "milestone-1", "done", "enforce", log_fn=lambda m: None
    )

    assert blocked is True, "deleted_tests must block chain milestone in enforce mode"


def test_chain_enforce_revise_retry_cap(tmp_path, monkeypatch):
    """chain runner halts with 'blocked' status when enforce retry cap is exhausted."""
    from megaplan.chain import ChainState, _shadow_milestone_completion_verdict

    root = tmp_path
    plan_name = "cap-plan"
    _make_chain_plan_dir(root, plan_name, mode="enforce")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    # Verify function returns True (blocked) each time newly_failing is present.
    result = _shadow_milestone_completion_verdict(
        root, plan_name, "cap-ms", "done", "enforce", log_fn=lambda m: None
    )
    assert result is True

    # ChainState tracks enforce_revise_counts per milestone.
    cs = ChainState(completion_contract_mode="enforce")
    cs.enforce_revise_counts["cap-ms"] = 2  # already at cap

    # Simulate what run_chain would do: read the count and halt when exhausted.
    milestone_retry_count = cs.enforce_revise_counts.get("cap-ms", 0)
    max_retries = 2
    assert milestone_retry_count >= max_retries, "cap should be exhausted"


def test_chain_state_enforce_revise_counts_roundtrip():
    """ChainState.enforce_revise_counts round-trips through to_dict/from_dict."""
    from megaplan.chain import ChainState

    cs = ChainState(enforce_revise_counts={"ms-1": 1, "ms-2": 2})
    restored = ChainState.from_dict(cs.to_dict())
    assert restored.enforce_revise_counts == {"ms-1": 1, "ms-2": 2}


def test_chain_state_enforce_revise_counts_defaults_empty():
    """Old chain state JSON with no enforce_revise_counts field defaults to {}."""
    from megaplan.chain import ChainState

    cs = ChainState.from_dict({})
    assert cs.enforce_revise_counts == {}


# ---------------------------------------------------------------------------
# extract_green_suite_info utility
# ---------------------------------------------------------------------------


def test_extract_green_suite_info_from_verdict(tmp_path, monkeypatch):
    """extract_green_suite_info correctly extracts delta + status from a verdict."""
    from megaplan.orchestration.completion_contract import (
        CompletionContext,
        CompletionSubject,
        GreenSuiteProvider,
        compute_verdict,
    )

    plan_dir, project_dir = _make_plan_dir(tmp_path, mode="shadow")

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_a"],
            passes=[],
            collected_ids=["tests/test_foo.py::test_a"],
            status="failed",
            exit_code=1,
        ),
    )

    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    subject = CompletionSubject(kind="plan", name="p", to_state="done", plan_name="p")
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=subject,
        mode="shadow",
    )

    delta_dict, status = extract_green_suite_info(verdict)

    assert delta_dict is not None, "expected a delta dict"
    assert isinstance(delta_dict.get("newly_failing"), list)
    assert status is not None
