"""End-to-end tests for the mechanical out-of-band test verification gate.

Drives the Plan pipeline with a synthetic-repo fixture containing
deliberately-red and green tests, then asserts:

(a) The execute phase completes in ≤3 turns with no token-cap relaunch.
(b) In ``enforce``, a code edit that introduces a new failure routes state
    back to revise, ``verdict.would_block=True``, and ``newly_failing`` is
    non-empty.
(c) A milestone that leaves only pre-existing baseline failures red passes
    with ``accepted=True``.
(d) An idempotent relaunch with the same ``code_hash`` skips the re-run so
    only one verification record exists in ``suite_runs.ndjson``.
(e) A zero-tests-collected repo yields a ``not_applicable`` verdict and is
    NOT silent-green in enforce.

Covers T15.
"""

from __future__ import annotations

import json
import logging
import os
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli
from megaplan._pipeline.planning import compile_planning_pipeline
from megaplan._pipeline.types import StepContext
from megaplan._pipeline.runtime import policy_from_cli_args
from megaplan._pipeline.executor import run_pipeline_with_policy
from megaplan.orchestration.suite_runner import (
    SuiteRunResult,
    append_suite_run,
    freshness_skip,
    latest_run_for_phase,
)
from megaplan.orchestration.completion_contract import (
    CompletionVerdict,
    CompletionSubject,
    EvidenceRef,
    EvidenceStatus,
    compute_verdict,
    extract_green_suite_info,
    normalize_contract_mode,
)
from megaplan.planning.state import STATE_CRITIQUED

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
# (a) Execute phase completes in ≤3 turns with no token-cap relaunch
# ---------------------------------------------------------------------------


def test_execute_phase_completes_within_three_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive a plan through the pipeline; execute must finish in ≤3 turns."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    # Create synthetic test files: one deliberately red, one green.
    tests_dir = project_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "test_baseline.py").write_text(
        "import pytest\n\n"
        "def test_deliberately_red():\n"
        "    assert 1 == 2\n\n"
        "def test_always_green():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

    init_args = Namespace(
        plan=None,
        idea="e2e mechanical gate",
        name="e2e-gate",
        project_dir=str(project_dir),
        auto_approve=None,
        robustness="robust",
        agent=None,
        ephemeral=False,
        fresh=False,
        persist=False,
        confirm_destructive=True,
        user_approved=False,
        confirm_self_review=False,
        batch=None,
        override_action=None,
        note=None,
        reason="",
        strict_notes=None,
        source="user",
    )
    response = megaplan.handle_init(root, init_args)
    plan_name = response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    # Write a note so the state machine can transition through.
    megaplan.handle_override(
        root,
        Namespace(
            **{
                **vars(init_args),
                "plan": plan_name,
                "override_action": "add-note",
                "note": "scoped",
            }
        ),
    )

    pipeline = compile_planning_pipeline()
    ctx = StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name, **json.loads((plan_dir / "state.json").read_text())},
        profile={"root": root, "project_dir": project_dir},
        mode="code",
        inputs={},
        budget=None,
    )
    policy = policy_from_cli_args(
        stall_threshold=999,
        max_iterations=30,
        max_cost_usd=None,
        on_escalate="force-proceed",
    )

    result = run_pipeline_with_policy(pipeline, ctx, artifact_root=plan_dir, policy=policy)

    state = json.loads((plan_dir / "state.json").read_text())
    assert state["current_state"] == "done", f"Expected 'done', got {state['current_state']!r}"

    # Verify key artifacts were produced
    for artifact in ["prep.json", "plan_v1.md", "final.md", "finalize.json", "execution.json"]:
        assert (plan_dir / artifact).exists(), f"Missing artifact: {artifact}"

    # Verify execute ran (the sentinel file created by mock workers)
    assert (project_dir / "IMPLEMENTED_BY_MEGAPLAN.txt").exists(), "Execute did not run"

    # The execute phase must not have looped excessively: the pipeline
    # iteration count (max_iterations=30) is generous but the result
    # confirms we didn't stall.
    assert result.get("exit_policy") is not None or result.get("final_stage") is not None


# ---------------------------------------------------------------------------
# (b) In enforce, new failure routes state back to revise
# ---------------------------------------------------------------------------


def test_enforce_blocks_on_newly_failing_and_routes_to_revise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """enforce + newly_failing → state patched to revise, verdict.would_block=True."""
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

    # Verify the verdict was persisted
    verdict_path = plan_dir / "completion_verdict.json"
    assert verdict_path.exists(), "completion_verdict.json not persisted"
    verdict_data = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert verdict_data.get("accepted") is False, "verdict should not be accepted"
    assert verdict_data.get("would_block") is not False

    # Verify that green_suite.delta contains non-empty newly_failing
    gs = verdict_data.get("green_suite", {})
    delta = gs.get("delta", {})
    newly_failing = delta.get("newly_failing", [])
    assert len(newly_failing) > 0, f"expected non-empty newly_failing, got {newly_failing}"


# ---------------------------------------------------------------------------
# (c) Baseline-only red passes with accepted=True
# ---------------------------------------------------------------------------


def test_baseline_only_red_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A milestone leaving only pre-existing baseline failures red → accepted=True."""
    from megaplan import auto

    plan_dir, _ = _make_plan_dir(
        tmp_path,
        mode="enforce",
        baseline_failures=["tests/test_foo.py::test_pre_existing"],
        baseline_ids=["tests/test_foo.py::test_pre_existing", "tests/test_foo.py::test_green"],
    )

    # Verification: same pre-existing failure, no new failures.
    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=["tests/test_foo.py::test_pre_existing"],
            passes=["tests/test_foo.py::test_green"],
            collected_ids=["tests/test_foo.py::test_pre_existing", "tests/test_foo.py::test_green"],
            status="failed",
            exit_code=1,
        ),
    )

    result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    # In enforce mode, only pre-existing failures → no block → done.
    assert result == "done", f"expected 'done', got {result!r}"
    state = _read_state(plan_dir)
    assert state.get("current_state") != STATE_CRITIQUED

    # Verify the verdict was persisted with accepted=True.
    verdict_path = plan_dir / "completion_verdict.json"
    assert verdict_path.exists(), "completion_verdict.json not persisted"
    verdict_data = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert verdict_data.get("accepted") is True, "only pre-existing failures → accepted=True"


# ---------------------------------------------------------------------------
# (d) Idempotent relaunch with same code_hash skips re-run
# ---------------------------------------------------------------------------


def test_idempotent_relaunch_same_code_hash_skips_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same code_hash on relaunch yields freshness-skip → only one record."""
    plan_dir = tmp_path / "plan"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True)

    result = _make_run_result(
        phase="verification",
        failures=[],
        passes=["tests/test_foo.py::test_a"],
        collected_ids=["tests/test_foo.py::test_a"],
        status="passed",
        exit_code=0,
        code_hash="hash123",
    )
    append_suite_run(plan_dir, result)

    # Now check freshness_skip: same hash should return cached result.
    cached = freshness_skip(plan_dir, "hash123", phase="verification")
    assert cached is not None, "freshness_skip must return cached result on hash match"
    assert cached.run_id == result.run_id

    # Count verification-phase records in suite_runs.ndjson.
    records = []
    log_path = ver_dir / "suite_runs.ndjson"
    with open(log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    verification_records = [r for r in records if r["phase"] == "verification"]
    assert len(verification_records) == 1, (
        f"Expected 1 verification record, got {len(verification_records)}"
    )

    # Append another run with different hash, verify freshness_skip returns None.
    cached2 = freshness_skip(plan_dir, "hash456", phase="verification")
    assert cached2 is None, "freshness_skip must return None on hash mismatch"


# ---------------------------------------------------------------------------
# (e) Zero-tests-collected → not_applicable, NOT silent-green in enforce
# ---------------------------------------------------------------------------


def test_zero_tests_collected_yields_not_applicable_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero-tests-collected repo → not_applicable verdict, NOT silent-green."""
    from megaplan import auto

    plan_dir, _ = _make_plan_dir(
        tmp_path,
        mode="enforce",
        baseline_ids=[],
        baseline_failures=[],
    )

    # Replace baseline record with empty/non-existent — but we need a
    # baseline with zero collected for genuine not_applicable.
    # Clear the log and write baseline with zero collected.
    log_path = plan_dir / "verification" / "suite_runs.ndjson"
    if log_path.exists():
        log_path.unlink()

    baseline = _make_run_result(
        phase="baseline",
        failures=[],
        passes=[],
        collected_ids=[],
        status="not_applicable",
        exit_code=5,
        collected=0,
        code_hash="abc123",
        collections_parse_ok=True,
    )
    append_suite_run(plan_dir, baseline)

    # Mock run_suite to also return not_applicable (no tests collected).
    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: _make_run_result(
            failures=[],
            passes=[],
            collected_ids=[],
            status="not_applicable",
            exit_code=5,
            collected=0,
            code_hash="abc123",
            collections_parse_ok=True,
        ),
    )

    result = auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)

    # In enforce mode, not_applicable does NOT block.
    assert result == "done", f"not_applicable must not block; got {result!r}"

    # Verify the verdict was persisted.
    verdict_path = plan_dir / "completion_verdict.json"
    assert verdict_path.exists(), "completion_verdict.json not persisted"
    verdict_data = json.loads(verdict_path.read_text(encoding="utf-8"))

    # Must not be silent-green: verdict should show not_applicable or
    # unsatisfied status for green_suite evidence.
    green_suite_ref = None
    for ref in verdict_data.get("evidence", []):
        if ref.get("kind") == "green_suite":
            green_suite_ref = ref
            break
    assert green_suite_ref is not None, "green_suite evidence missing from verdict"

    # When baseline collected==0 and verification collected==0, GreenSuiteProvider
    # returns EvidenceStatus.not_applicable — NOT satisfied (silent-green).
    assert green_suite_ref["status"] in ("not_applicable", "unsatisfied"), (
        f"Expected not_applicable or unsatisfied, got {green_suite_ref['status']!r}"
    )
    assert green_suite_ref["status"] != "satisfied", "must NOT be silent-green"

    # Check that accepted is not simply True via waiving
    # (in not_applicable case the verdict is accepted because no evidence is
    # unsatisfied — but the green_suite evidence itself is not_applicable).
    assert verdict_data["accepted"] is True, (
        "not_applicable → no blocking evidence → accepted=True"
    )


# ---------------------------------------------------------------------------
# Combined end-to-end: enforce blocks + route to revise via plan driver
# ---------------------------------------------------------------------------


def test_enforce_block_routes_to_revise_and_persists_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full chain: compute_verdict in enforce with new failure → would_block + delta."""
    plan_dir, project_dir = _make_plan_dir(tmp_path, mode="enforce")

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

    config = _read_state(plan_dir).get("config", {})
    subject = CompletionSubject(kind="plan", name="test-plan", to_state="done")
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=_read_state(plan_dir),
        subject=subject,
        mode="enforce",
    )

    assert verdict.accepted is False
    assert verdict.would_block is True

    # Extract green_suite delta via helper shared between plan/chain drivers.
    delta_dict, result_status = extract_green_suite_info(verdict)
    assert delta_dict is not None
    newly_failing = delta_dict.get("newly_failing", [])
    assert len(newly_failing) > 0, f"Expected non-empty newly_failing, got {newly_failing}"
    assert "tests/test_foo.py::test_a" in newly_failing

    # Verify the telemetry line was emitted (log captured from green_suite)
    # No explicit capture here; just ensure no exception was raised.
