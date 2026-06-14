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
    ArtifactRef,
    CONTRACT_MODE_SHADOW,
    COMPLETION_VERDICT_CONTRACT_VERSION,
    COMPLETION_VERDICT_SCHEMA,
    COMPLETION_VERDICT_SCHEMA_VERSION,
    CompletionContext,
    CompletionSubject,
    CompletionVerdict,
    DeclaredNoopProvider,
    EvidenceRef,
    EvidenceStatus,
    LandedDiffProvider,
    PhaseCoverageProvider,
    ReviewDispositionProvider,
    TrustClass,
    WorkerDidWorkProvider,
    _BLOCKING_STATUSES,
    compute_verdict,
    normalize_contract_mode,
    normalize_evidence_status,
)
from arnold.pipelines.megaplan.orchestration.completion_io import (
    COMPLETION_VERDICT_FILENAME,
    read_completion_verdict,
    read_typed_completion_verdict,
    write_completion_verdict,
)


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


def _init_git_repo_with_commit(path: Path) -> str:
    _init_git_repo(path)
    (path / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _subject(name: str = "plan-x") -> CompletionSubject:
    return CompletionSubject(kind="plan", name=name, to_state="done", plan_name=name)


def test_completion_contract_uses_canonical_evidence_ref_deserialization() -> None:
    ref = EvidenceRef.from_dict(
        {"kind": "review_disposition", "status": "fail-not-success", "summary": "forced"}
    )

    assert ref.status == EvidenceStatus.unsatisfied
    assert ref.details["diagnostics"]["legacy_status"] == "fail-not-success"
    assert _BLOCKING_STATUSES == frozenset({EvidenceStatus.unsatisfied})


def test_landed_diff_declared_base_requires_claims_in_committed_range(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    base_sha = _init_git_repo_with_commit(project_dir)
    (project_dir / "wip.py").write_text("wip\n", encoding="utf-8")

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

    ref = LandedDiffProvider().collect(
        CompletionContext(
            plan_dir=plan_dir,
            project_dir=project_dir,
            state={"config": {"mode": "code", "project_dir": str(project_dir)}},
            subject=_subject(),
            git_base_ref=base_sha,
        )
    )

    assert ref.status == EvidenceStatus.unsatisfied
    assert ref.details["diff_source"] == "declared_authoritative"
    assert "wip.py" in ref.details["files_in_diff"]
    assert "wip.py" not in ref.details["files_in_committed_range"]


def test_completion_verdict_to_dict_stamps_current_schema_fields() -> None:
    verdict = CompletionVerdict(
        mode=CONTRACT_MODE_SHADOW,
        subject=_subject(),
        evidence=(),
        accepted=True,
    )
    payload = verdict.to_dict()

    assert payload["schema"] == COMPLETION_VERDICT_SCHEMA
    assert payload["schema_version"] == COMPLETION_VERDICT_SCHEMA_VERSION
    assert payload["evidence_contract_version"] == COMPLETION_VERDICT_CONTRACT_VERSION


def test_completion_verdict_from_dict_accepts_legacy_missing_versions() -> None:
    verdict = CompletionVerdict.from_dict(
        {
            "mode": CONTRACT_MODE_SHADOW,
            "subject": _subject().to_dict(),
            "evidence": [],
            "accepted": True,
            "failures": [],
        }
    )

    assert verdict.schema_version == 0
    assert verdict.evidence_contract_version == 0
    assert verdict.accepted is True


def test_completion_verdict_from_dict_uses_canonical_evidence_refs() -> None:
    verdict = CompletionVerdict.from_dict(
        {
            "mode": "warn",
            "subject": _subject().to_dict(),
            "evidence": [
                {
                    "kind": "review_disposition",
                    "status": "fail-not-success",
                    "summary": "force proceeded",
                }
            ],
            "accepted": False,
            "failures": ["review_disposition:force proceeded"],
        }
    )

    evidence = verdict.evidence[0]
    assert evidence.status == EvidenceStatus.unsatisfied
    assert evidence.details["diagnostics"]["legacy_status"] == "fail-not-success"
    assert verdict.accepted is False
    assert verdict.would_block is True


def test_completion_contract_reexports_compatibility_symbols() -> None:
    artifact = ArtifactRef(path="completion_verdict.json", sha256="abc123")
    normalized = normalize_evidence_status("fail-not-success")

    assert artifact.path == "completion_verdict.json"
    assert TrustClass.judgment.value == "judgment"
    assert normalized.status == EvidenceStatus.unsatisfied
    assert normalized.diagnostics["legacy_status"] == "fail-not-success"


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

    typed = read_typed_completion_verdict(plan_dir)
    assert typed is not None
    assert typed.accepted is True
    assert typed.schema == COMPLETION_VERDICT_SCHEMA


def test_typed_completion_verdict_reads_legacy_payloads(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    payload = {
        "mode": CONTRACT_MODE_SHADOW,
        "subject": _subject().to_dict(),
        "evidence": [
            {
                "kind": "review_disposition",
                "status": "fail-not-success",
                "summary": "force proceeded",
            }
        ],
        "accepted": False,
        "failures": ["review_disposition:force proceeded"],
    }
    (plan_dir / COMPLETION_VERDICT_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    raw = read_completion_verdict(plan_dir)
    typed = read_typed_completion_verdict(plan_dir)

    assert raw == payload
    assert typed is not None
    assert typed.evidence[0].status == EvidenceStatus.unsatisfied
    assert typed.evidence[0].details["diagnostics"]["legacy_status"] == "fail-not-success"
    assert typed.schema_version == 0
    assert typed.evidence_contract_version == 0


def test_typed_completion_verdict_is_fail_soft_for_invalid_payload(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / COMPLETION_VERDICT_FILENAME).write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

    assert read_completion_verdict(plan_dir) == ["not", "a", "dict"]
    assert read_typed_completion_verdict(plan_dir) is None


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
    assert by_kind["declared_noop"].status == EvidenceStatus.waived
    assert by_kind["declared_noop"].trust_class == TrustClass.claim
    assert by_kind["declared_noop"].artifact is not None
    assert by_kind["declared_noop"].artifact.path == "completion/noop.json"
    assert by_kind["declared_noop"].details["evidence_id"].startswith("sha256:")
    # landed_diff still observes the missing diff, but the waiver excuses it.
    assert "landed_diff" not in {f.split(":")[0] for f in verdict.failures}


def test_legacy_satisfied_declared_noop_still_acts_as_waiver(tmp_path):
    class _LegacyNoop:
        kind = "declared_noop"

        def collect(self, ctx):
            return EvidenceRef(
                "declared_noop",
                EvidenceStatus.satisfied,
                "legacy no-op artifact present",
                {},
            )

    class _MissingDiff:
        kind = "landed_diff"

        def collect(self, ctx):
            return EvidenceRef(
                "landed_diff",
                EvidenceStatus.unsatisfied,
                "no files in diff",
                {},
            )

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=tmp_path,
        state={"config": {}},
        subject=_subject(),
        providers=(_LegacyNoop(), _MissingDiff()),
    )
    assert verdict.accepted is True
    assert verdict.failures == ()


def test_declared_noop_waiver_only_exempts_diff_and_activity_failures(tmp_path):
    class _WaivedNoop:
        kind = "declared_noop"

        def collect(self, ctx):
            return EvidenceRef(
                "declared_noop",
                EvidenceStatus.waived,
                "typed no-op artifact present",
                {},
            )

    class _MissingDiff:
        kind = "landed_diff"

        def collect(self, ctx):
            return EvidenceRef(
                "landed_diff",
                EvidenceStatus.unsatisfied,
                "no files in diff",
                {},
            )

    class _NoWorkerTrace:
        kind = "worker_did_work"

        def collect(self, ctx):
            return EvidenceRef(
                "worker_did_work",
                EvidenceStatus.unsatisfied,
                "no worker trace",
                {},
            )

    class _ForceProceedReview:
        kind = "review_disposition"

        def collect(self, ctx):
            return EvidenceRef(
                "review_disposition",
                EvidenceStatus.unsatisfied,
                "force proceeded",
                {},
            )

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=tmp_path,
        state={"config": {}},
        subject=_subject(),
        providers=(_WaivedNoop(), _MissingDiff(), _NoWorkerTrace(), _ForceProceedReview()),
    )

    assert verdict.accepted is False
    assert verdict.failures == ("review_disposition: force proceeded",)


def test_remaining_provider_refs_include_contract_provenance(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write(
        plan_dir / "execution_batch_9.json",
        {
            "task_updates": [
                {
                    "task_id": "T12",
                    "status": "done",
                    "files_changed": ["x.py"],
                    "commands_run": ["pytest tests/test_completion_contract.py"],
                }
            ]
        },
    )
    _write(plan_dir / "review.json", {"review_verdict": "approved", "issues": []})
    (plan_dir / "completion").mkdir()
    _write(plan_dir / "completion" / "noop.json", {"reason": "already complete"})
    ctx = type(
        "Ctx",
        (),
        {
            "plan_dir": plan_dir,
            "project_dir": tmp_path,
            "state": {"config": {}},
            "subject": _subject("provider-provenance"),
        },
    )()

    phase_ref = PhaseCoverageProvider().collect(ctx)
    landed_ref = LandedDiffProvider().collect(ctx)
    worker_ref = WorkerDidWorkProvider().collect(ctx)
    review_ref = ReviewDispositionProvider().collect(ctx)
    noop_ref = DeclaredNoopProvider().collect(ctx)
    worker_ref_again = WorkerDidWorkProvider().collect(ctx)

    assert phase_ref.trust_class == TrustClass.judgment
    assert phase_ref.provider == "PhaseCoverageProvider"
    assert phase_ref.provider_version == "1"
    assert phase_ref.subject == "provider-provenance"
    assert phase_ref.details["evidence_id"].startswith("sha256:")

    assert landed_ref.status == EvidenceStatus.unknown
    assert landed_ref.trust_class == TrustClass.judgment
    assert landed_ref.provider == "LandedDiffProvider"
    assert landed_ref.provider_version == "1"
    assert landed_ref.subject == "provider-provenance"
    assert landed_ref.details["evidence_id"].startswith("sha256:")

    assert worker_ref.status == EvidenceStatus.satisfied
    assert worker_ref.trust_class == TrustClass.evidence
    assert worker_ref.provider == "WorkerDidWorkProvider"
    assert worker_ref.provider_version == "1"
    assert worker_ref.source == "execution_batch_*.json"
    assert worker_ref.subject == "provider-provenance"
    assert worker_ref.artifacts
    assert worker_ref.artifacts[0].path == "execution_batch_9.json"
    assert worker_ref.artifacts[0].sha256
    assert worker_ref.details["evidence_id"] == worker_ref_again.details["evidence_id"]

    assert review_ref.status == EvidenceStatus.satisfied
    assert review_ref.trust_class == TrustClass.judgment
    assert review_ref.artifact is not None
    assert review_ref.artifact.path == "review.json"
    assert review_ref.artifact.sha256
    assert review_ref.details["evidence_id"].startswith("sha256:")

    assert noop_ref.status == EvidenceStatus.waived
    assert noop_ref.trust_class == TrustClass.claim
    assert noop_ref.artifact is not None
    assert noop_ref.artifact.path == "completion/noop.json"
    assert noop_ref.details["evidence_id"].startswith("sha256:")


def test_declared_noop_absence_keeps_optional_provenance_fields_unset(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    ctx = type(
        "Ctx",
        (),
        {
            "plan_dir": plan_dir,
            "project_dir": tmp_path,
            "state": {"config": {}},
            "subject": _subject("missing-noop"),
        },
    )()

    noop_ref = DeclaredNoopProvider().collect(ctx)

    assert noop_ref.status == EvidenceStatus.not_applicable
    assert noop_ref.trust_class == TrustClass.claim
    assert noop_ref.provider == "DeclaredNoopProvider"
    assert noop_ref.provider_version == "1"
    assert noop_ref.source == "completion/noop.json|completion_noop.json"
    assert noop_ref.artifact is None
    assert noop_ref.artifacts == ()
    assert noop_ref.code_hash is None


def test_compute_verdict_is_fail_open_on_provider_crash(tmp_path, monkeypatch):
    """A provider that raises degrades to `unknown`, never aborts the verdict."""
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


# ---------------------------------------------------------------------------
# T7: Completion I/O round-trip and legacy payload tests
# ---------------------------------------------------------------------------


def test_completion_io_current_verdict_round_trip(tmp_path: Path) -> None:
    """Current verdict round-trip through write → raw-read → typed-read preserves
    all schema/version fields, evidence refs with provenance, and verdict fields."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    artifact = ArtifactRef(
        path="completion_verdict.json",
        sha256="abc123def456",
        artifact_type="application/json",
        schema="megaplan.artifact_ref",
        schema_version=1,
    )
    ref = EvidenceRef(
        kind="green_suite",
        status=EvidenceStatus.satisfied,
        summary="all tests pass",
        details={"status": "passed", "delta": {"newly_failing": []}},
        trust_class=TrustClass.evidence,
        provider="suite_runner",
        provider_version="1.2.3",
        artifact=artifact,
        source="test_run_42",
        observed_at="2026-06-07T20:00:00Z",
        code_hash="def456",
    )
    verdict = CompletionVerdict(
        mode=CONTRACT_MODE_SHADOW,
        subject=_subject("round-trip-plan"),
        evidence=(ref,),
        accepted=True,
        failures=(),
    )

    # Write → verify file exists
    out = write_completion_verdict(plan_dir, verdict)
    assert out == plan_dir / COMPLETION_VERDICT_FILENAME
    assert out.is_file()

    # Raw read → dict with current schema/version stamps
    raw = read_completion_verdict(plan_dir)
    assert raw is not None
    assert raw["schema"] == COMPLETION_VERDICT_SCHEMA
    assert raw["schema_version"] == COMPLETION_VERDICT_SCHEMA_VERSION
    assert raw["evidence_contract_version"] == COMPLETION_VERDICT_CONTRACT_VERSION
    assert raw["accepted"] is True
    assert raw["mode"] == CONTRACT_MODE_SHADOW
    assert raw["subject"]["kind"] == "plan"
    assert raw["subject"]["name"] == "round-trip-plan"
    assert len(raw["evidence"]) == 1

    ev_raw = raw["evidence"][0]
    assert ev_raw["kind"] == "green_suite"
    assert ev_raw["status"] == "satisfied"
    assert ev_raw["schema"] == "megaplan.evidence_ref"
    assert ev_raw["schema_version"] == 1
    assert ev_raw["evidence_contract_version"] == 1
    assert ev_raw["provider"] == "suite_runner"
    assert ev_raw["provider_version"] == "1.2.3"
    assert ev_raw["source"] == "test_run_42"
    assert ev_raw["observed_at"] == "2026-06-07T20:00:00Z"
    assert ev_raw["code_hash"] == "def456"
    assert ev_raw["trust_class"] == "evidence"
    assert ev_raw["artifact"]["path"] == "completion_verdict.json"
    assert ev_raw["artifact"]["sha256"] == "abc123def456"

    # Typed read → CompletionVerdict with populated fields
    typed = read_typed_completion_verdict(plan_dir)
    assert typed is not None
    assert typed.schema == COMPLETION_VERDICT_SCHEMA
    assert typed.schema_version == COMPLETION_VERDICT_SCHEMA_VERSION
    assert typed.evidence_contract_version == COMPLETION_VERDICT_CONTRACT_VERSION
    assert typed.accepted is True
    assert typed.mode == CONTRACT_MODE_SHADOW
    assert typed.subject.kind == "plan"
    assert typed.subject.name == "round-trip-plan"
    assert len(typed.evidence) == 1

    typed_ev = typed.evidence[0]
    assert typed_ev.kind == "green_suite"
    assert typed_ev.status == EvidenceStatus.satisfied
    assert typed_ev.summary == "all tests pass"
    assert typed_ev.trust_class == TrustClass.evidence
    assert typed_ev.provider == "suite_runner"
    assert typed_ev.provider_version == "1.2.3"
    assert typed_ev.source == "test_run_42"
    assert typed_ev.observed_at == "2026-06-07T20:00:00Z"
    assert typed_ev.code_hash == "def456"
    assert typed_ev.artifact is not None
    assert typed_ev.artifact.path == "completion_verdict.json"
    assert typed_ev.artifact.sha256 == "abc123def456"


def test_completion_io_legacy_payload_not_evaluated(tmp_path: Path) -> None:
    """Legacy ``completion_verdict.json`` with ``not_evaluated`` evidence ref
    and no schema/version fields: raw stays dict, typed normalizes to unknown."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    payload = {
        "mode": CONTRACT_MODE_SHADOW,
        "subject": _subject().to_dict(),
        "evidence": [
            {
                "kind": "worker_did_work",
                "status": "not_evaluated",
                "summary": "no worker trace found",
            }
        ],
        "accepted": True,
        "failures": [],
    }
    (plan_dir / COMPLETION_VERDICT_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    # Raw read returns the unmodified dict
    raw = read_completion_verdict(plan_dir)
    assert raw == payload
    assert raw["evidence"][0]["status"] == "not_evaluated"

    # Typed read normalizes not_evaluated → unknown with diagnostics
    typed = read_typed_completion_verdict(plan_dir)
    assert typed is not None
    assert typed.evidence[0].status == EvidenceStatus.unknown
    assert typed.evidence[0].details["diagnostics"]["legacy_status"] == "not_evaluated"
    assert typed.evidence[0].details["diagnostics"]["canonical_status"] == "unknown"
    assert typed.schema_version == 0
    assert typed.evidence_contract_version == 0
    assert typed.accepted is True  # unknown is non-blocking


def test_completion_io_legacy_payload_fail_not_success_and_not_evaluated(
    tmp_path: Path,
) -> None:
    """Legacy payload with BOTH ``fail-not-success`` and ``not_evaluated`` refs:
    both normalize through canonical path; fail-not-success remains blocking."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    payload = {
        "mode": "enforce",
        "subject": _subject().to_dict(),
        "evidence": [
            {
                "kind": "review_disposition",
                "status": "fail-not-success",
                "summary": "force proceeded",
            },
            {
                "kind": "worker_did_work",
                "status": "not_evaluated",
                "summary": "no worker trace",
            },
        ],
        "accepted": False,
        "failures": ["review_disposition:force proceeded", "worker_did_work:no worker trace"],
    }
    (plan_dir / COMPLETION_VERDICT_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    raw = read_completion_verdict(plan_dir)
    assert raw["evidence"][0]["status"] == "fail-not-success"
    assert raw["evidence"][1]["status"] == "not_evaluated"

    typed = read_typed_completion_verdict(plan_dir)
    assert typed is not None
    # fail-not-success → unsatisfied (blocking) with diagnostics
    assert typed.evidence[0].status == EvidenceStatus.unsatisfied
    assert typed.evidence[0].details["diagnostics"]["legacy_status"] == "fail-not-success"
    # not_evaluated → unknown (non-blocking) with diagnostics
    assert typed.evidence[1].status == EvidenceStatus.unknown
    assert typed.evidence[1].details["diagnostics"]["legacy_status"] == "not_evaluated"
    assert typed.accepted is False
    assert typed.would_block is True
    # Both missing schema/version → default 0
    assert typed.schema_version == 0
    assert typed.evidence_contract_version == 0


def test_completion_io_incomplete_provenance_metadata(tmp_path: Path) -> None:
    """Evidence refs with partial provenance (missing provider_version,
    no artifacts, absent trust_class) round-trip through typed IO."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    # Evidence ref with partial provenance: has provider but no version,
    # no artifact, no trust_class, no observed_at
    ref_partial = EvidenceRef(
        kind="landed_diff",
        status=EvidenceStatus.unsatisfied,
        summary="no changes landed",
        details={"files_in_diff": []},
        provider="landed_diff_provider",
        # provider_version, artifact, trust_class, source, observed_at, code_hash all default
    )
    verdict = CompletionVerdict(
        mode=CONTRACT_MODE_SHADOW,
        subject=_subject("partial-provenance"),
        evidence=(ref_partial,),
        accepted=False,
        failures=("landed_diff:no changes landed",),
    )
    write_completion_verdict(plan_dir, verdict)

    # Raw read: optional provenance keys absent from dict
    raw = read_completion_verdict(plan_dir)
    assert raw is not None
    ev_raw = raw["evidence"][0]
    assert ev_raw["provider"] == "landed_diff_provider"
    assert "provider_version" not in ev_raw
    assert "trust_class" not in ev_raw
    assert "artifact" not in ev_raw
    assert "artifacts" not in ev_raw
    assert "source" not in ev_raw
    assert "subject" not in ev_raw
    assert "observed_at" not in ev_raw
    assert "code_hash" not in ev_raw

    # Typed read: missing provenance defaults correctly
    typed = read_typed_completion_verdict(plan_dir)
    assert typed is not None
    typed_ev = typed.evidence[0]
    assert typed_ev.provider == "landed_diff_provider"
    assert typed_ev.provider_version is None
    assert typed_ev.trust_class is None
    assert typed_ev.artifact is None
    assert typed_ev.artifacts == ()
    assert typed_ev.source is None
    assert typed_ev.subject is None
    assert typed_ev.observed_at is None
    assert typed_ev.code_hash is None


def test_completion_io_raw_vs_typed_divergence(tmp_path: Path) -> None:
    """Raw read returns the exact dict (even with legacy statuses);
    typed read normalizes legacy statuses through canonical path."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    payload = {
        "mode": CONTRACT_MODE_SHADOW,
        "subject": _subject().to_dict(),
        "evidence": [
            {
                "kind": "review_disposition",
                "status": "fail-not-success",
                "summary": "legacy review outcome",
            }
        ],
        "accepted": False,
        "failures": ["review_disposition:legacy review outcome"],
    }
    (plan_dir / COMPLETION_VERDICT_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    raw = read_completion_verdict(plan_dir)
    typed = read_typed_completion_verdict(plan_dir)

    # Raw preserves the original legacy status string
    assert raw["evidence"][0]["status"] == "fail-not-success"
    # Typed normalizes to canonical unsatisfied
    assert typed.evidence[0].status == EvidenceStatus.unsatisfied
    # Diagnostics bridge the gap
    assert typed.evidence[0].details["diagnostics"]["legacy_status"] == "fail-not-success"


def test_completion_io_verdict_with_multiple_evidence_artifacts(
    tmp_path: Path,
) -> None:
    """Verdict with evidence containing multiple artifacts serializes and
    deserializes correctly through completion I/O."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    a1 = ArtifactRef(path="log.txt", sha256="aaa111", artifact_type="text/plain")
    a2 = ArtifactRef(path="report.json", sha256="bbb222", artifact_type="application/json")
    ref = EvidenceRef(
        kind="worker_did_work",
        status=EvidenceStatus.satisfied,
        summary="worker produced outputs",
        details={"files": 2},
        artifacts=(a1, a2),
        trust_class=TrustClass.evidence,
    )
    verdict = CompletionVerdict(
        mode=CONTRACT_MODE_SHADOW,
        subject=_subject("multi-artifact"),
        evidence=(ref,),
        accepted=True,
    )
    write_completion_verdict(plan_dir, verdict)

    raw = read_completion_verdict(plan_dir)
    ev_raw = raw["evidence"][0]
    assert "artifacts" in ev_raw
    assert len(ev_raw["artifacts"]) == 2
    assert ev_raw["artifacts"][0]["path"] == "log.txt"
    assert ev_raw["artifacts"][0]["sha256"] == "aaa111"
    assert ev_raw["artifacts"][1]["path"] == "report.json"
    assert ev_raw["artifacts"][1]["sha256"] == "bbb222"
    # artifact not set directly → not serialized by to_dict()
    assert "artifact" not in ev_raw

    typed = read_typed_completion_verdict(plan_dir)
    assert typed is not None
    typed_ev = typed.evidence[0]
    assert len(typed_ev.artifacts) == 2
    assert typed_ev.artifacts[0].path == "log.txt"
    assert typed_ev.artifacts[1].path == "report.json"
    # from_dict auto-populates artifact from first in artifacts list
    assert typed_ev.artifact is not None
    assert typed_ev.artifact.path == "log.txt"
