"""Tests for the SHADOW-MODE completion-verification contract.

Verifies that:
  (i)   computing/persisting a verdict is fail-open and does not run the suite;
  (ii)  the verdict artifact is written to the plan dir;
  (iii) the computed verdict correctly FLAGS an abandoned/zero-diff case and a
        red-suite case (even though shadow never enforces);
  (iv)  a healthy plan produces an accepted verdict, and a typed no-op waiver
        excuses a missing diff.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.orchestration.completion_contract import (
    CONTRACT_MODE_SHADOW,
    CompletionSubject,
    EvidenceStatus,
    compute_verdict,
    normalize_contract_mode,
)
from arnold.pipelines.megaplan.orchestration.completion_io import (
    COMPLETION_VERDICT_FILENAME,
    read_completion_verdict,
    write_completion_verdict,
)


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _subject(name: str = "plan-x") -> CompletionSubject:
    return CompletionSubject(kind="plan", name=name, to_state="done", plan_name=name)


@pytest.fixture
def healthy_plan(tmp_path: Path) -> tuple[Path, Path, dict]:
    """A plan with a real diff, worker activity, green baseline, clean review."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo(project_dir)
    # A real, uncommitted change → non-empty working-tree diff.
    (project_dir / "src.py").write_text("print('hi')\n", encoding="utf-8")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "t1",
                    "status": "done",
                    "files_changed": ["src.py"],
                    "commands_run": ["pytest"],
                    "executor_notes": "Implemented the feature end to end.",
                }
            ],
            "sense_checks": [],
            "baseline_test_failures": [],
            "baseline_test_command": "pytest -q",
        },
    )
    _write(
        plan_dir / "execution_batch_001.json",
        {
            "tasks": [
                {"task_id": "t1", "status": "done", "files_changed": ["src.py"], "commands_run": ["pytest"]}
            ]
        },
    )
    _write(plan_dir / "review.json", {"review_verdict": "approved", "issues": []})
    state = {"config": {"mode": "code", "project_dir": str(project_dir)}}
    return plan_dir, project_dir, state


def test_normalize_contract_mode_defaults_to_shadow():
    assert normalize_contract_mode(None) == CONTRACT_MODE_SHADOW
    assert normalize_contract_mode("bogus") == CONTRACT_MODE_SHADOW
    assert normalize_contract_mode("enforce") == "enforce"


def test_healthy_plan_is_accepted_in_shadow(healthy_plan, monkeypatch):
    plan_dir, project_dir, state = healthy_plan
    # Mock run_suite to return a passed result so the suite doesn't actually run.
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    fake_result = SuiteRunResult(
        run_id="fake-run-id",
        phase="verification",
        command="pytest",
        duration=0.1,
        collected=1,
        collected_ids=["tests/test_x.py::test_pass"],
        failures=[],
        passes=["tests/test_x.py::test_pass"],
        status="passed",
        exit_code=0,
        raw_log_path=Path("/dev/null"),
        code_hash="abc123",
        collections_parse_ok=True,
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: fake_result,
    )
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=_subject(),
        mode=CONTRACT_MODE_SHADOW,
    )
    assert verdict.mode == CONTRACT_MODE_SHADOW
    assert verdict.accepted is True, verdict.failures
    assert verdict.failures == ()
    # green_suite must report the verification result (now always runs).
    green = {e.kind: e for e in verdict.evidence}["green_suite"]
    assert green.status == EvidenceStatus.satisfied
    assert green.details["status"] == "passed"


def test_verdict_artifact_is_written(healthy_plan, tmp_path, monkeypatch):
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: SuiteRunResult(
            run_id="r", phase="verification", command="pytest", duration=0.1,
            collected=1, collected_ids=["t::x"], failures=[], passes=["t::x"],
            status="passed", exit_code=0, raw_log_path=Path("/dev/null"),
            code_hash="abc", collections_parse_ok=True,
        ),
    )
    plan_dir, project_dir, state = healthy_plan
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=_subject(),
    )
    out = write_completion_verdict(plan_dir, verdict)
    assert out == plan_dir / COMPLETION_VERDICT_FILENAME
    assert out.is_file()
    roundtrip = read_completion_verdict(plan_dir)
    assert roundtrip is not None
    assert roundtrip["accepted"] is True
    assert roundtrip["subject"]["kind"] == "plan"


def test_flags_abandoned_zero_diff(tmp_path, monkeypatch):
    """Planned then quit: no diff, no batch, no waiver → flagged unsatisfied."""
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: SuiteRunResult(
            run_id="r", phase="verification", command="pytest", duration=0.1,
            collected=0, collected_ids=[], failures=[], passes=[],
            status="not_applicable", exit_code=5, raw_log_path=Path("/dev/null"),
            code_hash="abc", collections_parse_ok=False,
        ),
    )
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo(project_dir)  # clean tree → empty diff
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    # finalize claims a done task but with no files and no commands (hollow done).
    _write(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "t1", "status": "done", "files_changed": [], "commands_run": []}],
            "sense_checks": [],
        },
    )
    state = {"config": {"mode": "code", "project_dir": str(project_dir)}}
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=_subject(),
        mode=CONTRACT_MODE_SHADOW,
    )
    # Shadow does NOT enforce, but it must FLAG the abandonment.
    assert verdict.accepted is False
    kinds = {f.split(":")[0] for f in verdict.failures}
    assert "landed_diff" in kinds
    by_kind = {e.kind: e for e in verdict.evidence}
    assert by_kind["landed_diff"].status == EvidenceStatus.unsatisfied


def test_flags_red_suite(healthy_plan, monkeypatch):
    """A verification suite with failures is flagged in the verdict."""
    plan_dir, project_dir, state = healthy_plan
    # Mock run_suite to return a failed result.
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    fake_result = SuiteRunResult(
        run_id="fake-run-id",
        phase="verification",
        command="pytest",
        duration=0.2,
        collected=3,
        collected_ids=[
            "tests/test_x.py::test_a",
            "tests/test_y.py::test_b",
            "tests/test_z.py::test_c",
        ],
        failures=["tests/test_x.py::test_a", "tests/test_y.py::test_b"],
        passes=["tests/test_z.py::test_c"],
        status="failed",
        exit_code=1,
        raw_log_path=Path("/dev/null"),
        code_hash="abc123",
        collections_parse_ok=True,
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: fake_result,
    )
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=_subject(),
    )
    assert verdict.accepted is False
    by_kind = {e.kind: e for e in verdict.evidence}
    assert by_kind["green_suite"].status == EvidenceStatus.unsatisfied
    assert by_kind["green_suite"].details["failure_count"] == 2
    assert by_kind["green_suite"].details["status"] == "failed"


def test_typed_noop_waiver_excuses_missing_diff(tmp_path, monkeypatch):
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: SuiteRunResult(
            run_id="r", phase="verification", command="pytest", duration=0.1,
            collected=0, collected_ids=[], failures=[], passes=[],
            status="not_applicable", exit_code=5, raw_log_path=Path("/dev/null"),
            code_hash="abc", collections_parse_ok=False,
        ),
    )
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo(project_dir)  # clean → empty diff
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(
        plan_dir / "finalize.json",
        {"tasks": [{"id": "t1", "status": "done", "files_changed": [], "commands_run": ["pytest"]}], "sense_checks": []},
    )
    (plan_dir / "completion").mkdir()
    _write(
        plan_dir / "completion" / "noop.json",
        {"kind": "noop", "reason": "already satisfied by existing code"},
    )
    state = {"config": {"mode": "code", "project_dir": str(project_dir)}}
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        subject=_subject(),
    )
    by_kind = {e.kind: e for e in verdict.evidence}
    assert by_kind["declared_noop"].status == EvidenceStatus.satisfied
    # landed_diff still observes the missing diff, but the waiver excuses it.
    assert "landed_diff" not in {f.split(":")[0] for f in verdict.failures}


def test_compute_verdict_is_fail_open_on_provider_crash(tmp_path, monkeypatch):
    """A provider that raises degrades to `unknown`, never aborts the verdict."""
    from arnold.pipelines.megaplan.orchestration import completion_contract as cc

    class _Boom:
        kind = "boom"

        def collect(self, ctx):
            raise RuntimeError("kaboom")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=tmp_path,
        state={"config": {}},
        subject=_subject(),
        providers=(_Boom(),),
    )
    boom = verdict.evidence[0]
    assert boom.status == EvidenceStatus.unknown
    # `unknown` is not a blocking status.
    assert verdict.accepted is True


# ---------------------------------------------------------------------------
# Driver hook (auto.py): shadow verdict is computed + persisted on done,
# control flow unaffected, fully fail-open.
# ---------------------------------------------------------------------------


def _make_done_plan_dir(tmp_path: Path) -> tuple[Path, Path]:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo(project_dir)
    (project_dir / "src.py").write_text("x = 1\n", encoding="utf-8")
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(
        plan_dir / "finalize.json",
        {"tasks": [{"id": "t1", "status": "done", "files_changed": ["src.py"], "commands_run": ["pytest"]}], "sense_checks": [], "baseline_test_failures": []},
    )
    _write(
        plan_dir / "execution_batch_001.json",
        {"tasks": [{"task_id": "t1", "status": "done", "files_changed": ["src.py"], "commands_run": ["pytest"]}]},
    )
    _write(
        plan_dir / "state.json",
        {"config": {"mode": "code", "project_dir": str(project_dir), "completion_contract_mode": "shadow"}},
    )
    return plan_dir, project_dir


def test_auto_hook_writes_verdict_and_logs(tmp_path, monkeypatch):
    from arnold.pipelines.megaplan import auto 
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: SuiteRunResult(
            run_id="r", phase="verification", command="pytest", duration=0.1,
            collected=1, collected_ids=["t::x"], failures=[], passes=["t::x"],
            status="passed", exit_code=0, raw_log_path=Path("/dev/null"),
            code_hash="abc", collections_parse_ok=True,
        ),
    )

    plan_dir, _ = _make_done_plan_dir(tmp_path)
    logged: list[str] = []
    auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: logged.append(m))

    assert (plan_dir / COMPLETION_VERDICT_FILENAME).is_file()
    assert any("completion verdict" in m for m in logged)
    verdict = read_completion_verdict(plan_dir)
    assert verdict is not None and verdict["mode"] == "shadow"


def test_auto_hook_off_mode_writes_verdict_without_blocking(tmp_path, monkeypatch):
    from arnold.pipelines.megaplan import auto 
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: SuiteRunResult(
            run_id="r", phase="verification", command="pytest", duration=0.1,
            collected=1, collected_ids=["t::x"], failures=["t::x"], passes=[],
            status="failed", exit_code=1, raw_log_path=Path("/dev/null"),
            code_hash="abc", collections_parse_ok=True,
        ),
    )

    plan_dir, _ = _make_done_plan_dir(tmp_path)
    state = json.loads((plan_dir / "state.json").read_text())
    state["config"]["completion_contract_mode"] = "off"
    _write(plan_dir / "state.json", state)
    auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)
    verdict = read_completion_verdict(plan_dir)
    assert verdict is not None
    assert verdict["mode"] == "off"
    assert verdict["would_block"] is False


def test_auto_hook_is_fail_open(tmp_path, monkeypatch):
    """A broken plan dir (no state.json) must not raise."""
    from arnold.pipelines.megaplan import auto 
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
        lambda *a, **kw: SuiteRunResult(
            run_id="r", phase="verification", command="pytest", duration=0.1,
            collected=0, collected_ids=[], failures=[], passes=[],
            status="not_applicable", exit_code=5, raw_log_path=Path("/dev/null"),
            code_hash="abc", collections_parse_ok=False,
        ),
    )

    plan_dir = tmp_path / "empty_plan"
    plan_dir.mkdir()
    # Must not raise even with nothing on disk.
    auto._shadow_completion_verdict("plan-x", plan_dir, None, log=lambda m, **k: None)


def test_chain_state_roundtrips_completion_mode():
    from arnold.pipelines.megaplan.chain import ChainState

    cs = ChainState(completion_contract_mode="warn")
    restored = ChainState.from_dict(cs.to_dict())
    assert restored.completion_contract_mode == "warn"
    # Unknown values normalize to the shadow default.
    bad = ChainState.from_dict({"completion_contract_mode": "garbage"})
    assert bad.completion_contract_mode == "shadow"
