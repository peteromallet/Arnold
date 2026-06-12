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

from megaplan.orchestration.completion_contract import (
    CONTRACT_MODE_SHADOW,
    CompletionContext,
    CompletionSubject,
    EvidenceStatus,
    LandedDiffProvider,
    compute_verdict,
    normalize_contract_mode,
)
from megaplan.orchestration.completion_io import (
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
    from megaplan.orchestration.suite_runner import SuiteRunResult
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
        "megaplan.orchestration.suite_runner.run_suite",
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
    from megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
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
    from megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
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
    from megaplan.orchestration.suite_runner import SuiteRunResult
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
        "megaplan.orchestration.suite_runner.run_suite",
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
    from megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
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
    from megaplan.orchestration import completion_contract as cc

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
    from megaplan import auto
    from megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
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
    from megaplan import auto
    from megaplan.orchestration.suite_runner import SuiteRunResult

    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
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
    from megaplan import auto
    from megaplan.orchestration.suite_runner import SuiteRunResult
    monkeypatch.setattr(
        "megaplan.orchestration.suite_runner.run_suite",
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
    from megaplan.chain import ChainState

    cs = ChainState(completion_contract_mode="warn")
    restored = ChainState.from_dict(cs.to_dict())
    assert restored.completion_contract_mode == "warn"
    # Unknown values normalize to the shadow default.
    bad = ChainState.from_dict({"completion_contract_mode": "garbage"})
    assert bad.completion_contract_mode == "shadow"


# ---------------------------------------------------------------------------
# T8: Landed-diff provider behaviour — authoritative vs advisory gating
# ---------------------------------------------------------------------------


def _init_git_repo_with_commit(path: Path) -> str:
    """git init + config + seed commit. Returns the seed commit SHA."""
    _init_git_repo(path)
    (path / "seed.txt").write_text("seed\n")
    subprocess.run(
        ["git", "add", "seed.txt"],
        cwd=str(path),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"],
        cwd=str(path),
        check=True,
        capture_output=True,
        text=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(path),
        text=True,
        capture_output=True,
    ).stdout.strip()


def _resolve_head(project_dir: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(project_dir),
        text=True,
        capture_output=True,
    ).stdout.strip()


def test_landed_diff_phantom_claims_blocking_with_resolved_base(
    tmp_path: Path,
) -> None:
    """Claims for files absent from the committed range are blocking when the
    declared base resolves (``declared_authoritative`` diff_source)."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    base_sha = _init_git_repo_with_commit(project_dir)

    # Commit a real file so the committed range is non-empty.
    (project_dir / "real.py").write_text("real\n")
    subprocess.run(
        ["git", "add", "real.py"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "real"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "t1",
                    "status": "done",
                    "files_changed": ["real.py", "phantom.py"],
                    "commands_run": ["pytest"],
                }
            ],
            "sense_checks": [],
        },
    )

    provider = LandedDiffProvider()
    ctx = CompletionContext(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state={"config": {"mode": "code", "project_dir": str(project_dir)}},
        subject=_subject(),
        git_base_ref=base_sha,
    )
    ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.unsatisfied, (
        f"expected unsatisfied for phantom claim, got {ref.status}: {ref.summary}"
    )
    assert ref.details.get("diff_source") == "declared_authoritative"
    findings = ref.details.get("findings") or []
    assert any("phantom.py" in f for f in findings), (
        f"phantom.py should appear in findings: {findings}"
    )


def test_landed_diff_unclaimed_committed_blocking_with_resolved_base(
    tmp_path: Path,
) -> None:
    """Unclaimed files in the committed range are blocking when the declared
    base resolves (``declared_authoritative`` diff_source).

    With a resolved base the finding *\"Git status shows changed files not
    claimed by any task\"* stays in ``real_findings`` rather than being moved
    to ``advisory_findings``.
    """
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    base_sha = _init_git_repo_with_commit(project_dir)

    # Commit a file that no task claims.
    (project_dir / "unclaimed.py").write_text("unclaimed\n")
    subprocess.run(
        ["git", "add", "unclaimed.py"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "unclaimed"],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "t1",
                    "status": "done",
                    "files_changed": [],
                    "commands_run": ["echo done"],
                }
            ],
            "sense_checks": [],
        },
    )

    provider = LandedDiffProvider()
    ctx = CompletionContext(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state={"config": {"mode": "code", "project_dir": str(project_dir)}},
        subject=_subject(),
        git_base_ref=base_sha,
    )
    ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.unsatisfied, (
        f"expected unsatisfied for unclaimed committed file, got {ref.status}"
    )
    assert ref.details.get("diff_source") == "declared_authoritative"
    # With declared_authoritative the unclaimed-changes finding stays in
    # real_findings (the advisory_findings list is empty).
    advisory = ref.details.get("advisory_findings") or []
    assert advisory == [], (
        f"declared_authoritative must not relegate unclaimed changes to advisory: {advisory}"
    )
    findings = ref.details.get("findings") or []
    assert any("unclaimed.py" in f for f in findings), (
        f"unclaimed.py should appear in real findings: {findings}"
    )


def test_landed_diff_unresolved_base_advisory_unclaimed(tmp_path: Path) -> None:
    """When base_ref is declared but does not resolve, unclaimed-change
    findings remain advisory-only (``declared_unresolved`` diff_source).

    The working-tree status union can include dirty-tree noise and WIP from
    prior milestones, so without a resolved committed window the signal is
    too weak to block.
    """
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo_with_commit(project_dir)  # need HEAD to resolve

    # Leave an uncommitted file in the working tree.
    (project_dir / "unclaimed.py").write_text("dirty\n")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "t1",
                    "status": "done",
                    "files_changed": [],
                    "commands_run": ["echo done"],
                }
            ],
            "sense_checks": [],
        },
    )

    provider = LandedDiffProvider()
    ctx = CompletionContext(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state={"config": {"mode": "code", "project_dir": str(project_dir)}},
        subject=_subject(),
        git_base_ref="refs/heads/does-not-exist",
    )
    ref = provider.collect(ctx)

    assert ref.details.get("diff_source") == "declared_unresolved"
    # With declared_unresolved the unclaimed-changes finding is advisory-only,
    # so real_findings should be empty and the ref satisfied (or at worst
    # unknown, not unsatisfied for the no-diff case).
    advisory = ref.details.get("advisory_findings") or []
    assert any("unclaimed.py" in str(f) for f in advisory), (
        f"unclaimed.py should be in advisory findings: {advisory}"
    )
    # The landed diff should NOT be unsatisfied due to the advisory finding.
    if ref.status == EvidenceStatus.unsatisfied:
        # Only acceptable if due to something other than the unclaimed finding.
        findings = ref.details.get("findings") or []
        assert not any("unclaimed" in f for f in findings), (
            f"unclaimed finding leaked into real findings: {findings}"
        )


def test_landed_diff_uncommitted_only_claims_unsatisfied(tmp_path: Path) -> None:
    """When a declared milestone base resolves, claimed work must be present in
    the committed base..HEAD range.  Working-tree-only (uncommitted) claimed
    files are NOT sufficient — they produce an unsatisfied landed_diff finding.

    This covers the ``local_commit_sha=None`` / zero-divergence scenario
    where the committed range is empty and only ``git status`` paths are
    available — the claimed work has not landed.
    """
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    head_sha = _init_git_repo_with_commit(project_dir)

    # Uncommitted working-tree change.
    (project_dir / "wip.py").write_text("wip\n")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "t1",
                    "status": "done",
                    "files_changed": ["wip.py"],
                    "commands_run": ["pytest"],
                }
            ],
            "sense_checks": [],
        },
    )

    provider = LandedDiffProvider()
    ctx = CompletionContext(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state={"config": {"mode": "code", "project_dir": str(project_dir)}},
        subject=_subject(),
        git_base_ref=head_sha,  # base == HEAD → committed range empty
    )
    ref = provider.collect(ctx)

    assert ref.details.get("diff_source") == "declared_authoritative"
    # wip.py is in the working-tree status → files_in_diff includes it.
    assert "wip.py" in ref.details.get("files_in_diff", [])
    # But it is NOT in the committed range → unsatisfied.
    assert ref.status == EvidenceStatus.unsatisfied, (
        f"uncommitted-only claims should NOT satisfy landed_diff with resolved base,"
        f" got {ref.status}: {ref.summary}"
    )
    # The unlanded-claim finding is in ref.summary (real_findings), not in
    # details.findings (which holds the raw validate_execution_evidence findings).
    assert "wip.py" in ref.summary, (
        f"wip.py should appear in summary as unlanded claim: {ref.summary}"
    )


def test_landed_diff_heuristic_no_base_ref_advisory(tmp_path: Path) -> None:
    """Without any base_ref, the diff_source is ``heuristic`` and unclaimed
    changes are advisory — preserving legacy fallback behaviour."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _init_git_repo_with_commit(project_dir)  # need a commit for merge-base to resolve

    # Uncommitted change.
    (project_dir / "noise.py").write_text("noise\n")

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "t1",
                    "status": "done",
                    "files_changed": [],
                    "commands_run": ["echo done"],
                }
            ],
            "sense_checks": [],
        },
    )

    provider = LandedDiffProvider()
    ctx = CompletionContext(
        plan_dir=plan_dir,
        project_dir=project_dir,
        state={"config": {"mode": "code", "project_dir": str(project_dir)}},
        subject=_subject(),
        git_base_ref=None,  # no base → heuristic merge-base
    )
    ref = provider.collect(ctx)

    assert ref.details.get("diff_source") == "heuristic"
    advisory = ref.details.get("advisory_findings") or []
    assert any("noise.py" in str(f) for f in advisory), (
        f"unclaimed changes should be advisory in heuristic mode: {advisory}"
    )
    # Must not be unsatisfied because of advisory-only findings.
    if ref.status == EvidenceStatus.unsatisfied:
        findings = ref.details.get("findings") or []
        assert not any("noise" in f for f in findings), (
            f"advisory finding leaked into real findings: {findings}"
        )
