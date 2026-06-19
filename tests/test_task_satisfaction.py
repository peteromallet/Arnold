from __future__ import annotations

import subprocess
from pathlib import Path

from arnold.pipelines.megaplan.orchestration.completion_contract import (
    CompletionSubject,
    CompletionVerdict,
)
from arnold.pipelines.megaplan.orchestration.evidence_contract import (
    ArtifactRef,
    EvidenceRef,
    EvidenceStatus,
)
from arnold.pipelines.megaplan.orchestration.task_satisfaction import (
    EvidenceExecutionWindow,
    is_task_satisfied,
)


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit(repo: Path, filename: str, content: str, message: str) -> str:
    (repo / filename).write_text(content, encoding="utf-8")
    _git(repo, "add", filename)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _init_repo(repo: Path) -> str:
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    return _commit(repo, "seed.txt", "seed\n", "seed")


def test_task_satisfaction_normalizes_legacy_verdict_dict_and_blocks_unsatisfied():
    result = is_task_satisfied(
        {"id": "T1"},
        {
            "evidence": [
                {
                    "kind": "review_disposition",
                    "status": "fail-not-success",
                    "summary": "force-proceed at rework cap",
                    "details": {"task_ids": ["T1"]},
                }
            ]
        },
    )

    assert result.status == EvidenceStatus.unsatisfied
    assert result.evidence[0].status == EvidenceStatus.unsatisfied
    assert result.evidence[0].details["diagnostics"]["legacy_status"] == "fail-not-success"
    assert "unsatisfied_evidence:review_disposition" in result.would_block_reasons


def test_task_satisfaction_accepts_completion_verdict_and_declared_outputs():
    verdict = CompletionVerdict(
        mode="shadow",
        subject=CompletionSubject(kind="plan", name="demo", to_state="done"),
        evidence=(
            EvidenceRef(
                "landed_diff",
                EvidenceStatus.satisfied,
                "diff present",
                {"task_ids": ["T2"], "files_changed": ["src/app.py"], "head_sha": "head"},
                artifact=ArtifactRef(path="src/app.py"),
                code_hash="hash",
            ),
            EvidenceRef(
                "green_suite",
                EvidenceStatus.satisfied,
                "tests passed",
                {"task_ids": ["T2"], "command": "pytest tests/test_app.py", "head_sha": "head"},
                code_hash="hash",
            ),
        ),
        accepted=True,
    )

    result = is_task_satisfied(
        {
            "id": "T2",
            "files_changed": ["src/app.py"],
            "commands_run": ["pytest tests/test_app.py"],
        },
        verdict,
        current_head="head",
        current_code_hash="hash",
    )

    assert result.status == EvidenceStatus.satisfied
    assert result.missing_outputs == ()
    assert result.stale_evidence == ()
    assert result.would_block_reasons == ()


def test_task_satisfaction_reports_missing_declared_outputs():
    result = is_task_satisfied(
        {"id": "T3", "files_changed": ["src/missing.py"]},
        [
            EvidenceRef(
                "worker_did_work",
                EvidenceStatus.satisfied,
                "worker activity present",
                {"task_ids": ["T3"], "files_changed": ["src/other.py"]},
            )
        ],
    )

    assert result.status == EvidenceStatus.unsatisfied
    assert result.missing_outputs == ("files_changed:src/missing.py",)
    assert "missing_output:files_changed:src/missing.py" in result.would_block_reasons


def test_task_satisfaction_reports_missing_linked_evidence():
    result = is_task_satisfied(
        {"id": "T3b"},
        [
            EvidenceRef(
                "worker_did_work",
                EvidenceStatus.satisfied,
                "activity for another task",
                {"task_ids": ["other-task"]},
            )
        ],
    )

    assert result.status == EvidenceStatus.unknown
    assert result.evidence == ()
    assert result.diagnostics["linked_evidence_count"] == 0
    assert result.would_block_reasons == ("missing_linked_evidence",)


def test_task_satisfaction_reports_stale_head_and_code_hash_mismatch():
    result = is_task_satisfied(
        {"id": "T4"},
        [
            EvidenceRef(
                "green_suite",
                EvidenceStatus.satisfied,
                "verification passed",
                {"task_ids": ["T4"], "head_sha": "old-head"},
                code_hash="old-hash",
            )
        ],
        current_head="new-head",
        current_code_hash="new-hash",
    )

    assert result.status == EvidenceStatus.unsatisfied
    assert result.stale_evidence == (
        "head_mismatch:green_suite",
        "code_hash_mismatch:green_suite",
    )
    assert "stale_evidence:head_mismatch:green_suite" in result.would_block_reasons
    assert "stale_evidence:code_hash_mismatch:green_suite" in result.would_block_reasons


def test_task_satisfaction_accepts_ancestor_head_within_execution_window(tmp_path: Path):
    repo = tmp_path / "repo"
    base_sha = _init_repo(repo)
    observed_sha = _commit(repo, "work.py", "one\n", "batch 1")
    current_sha = _commit(repo, "work.py", "two\n", "operator commit")

    result = is_task_satisfied(
        {"id": "T4b", "files_changed": ["work.py"]},
        [
            EvidenceRef(
                "landed_diff",
                EvidenceStatus.satisfied,
                "batch 1 changed work.py",
                {
                    "task_ids": ["T4b"],
                    "files_changed": ["work.py"],
                    "head_sha": observed_sha,
                },
            )
        ],
        current_head=current_sha,
        execution_window=EvidenceExecutionWindow(
            project_dir=repo,
            base_sha=base_sha,
            head_sha=current_sha,
        ),
    )

    assert result.status == EvidenceStatus.satisfied
    assert result.stale_evidence == ()


def test_task_satisfaction_rejects_ancestor_head_before_execution_window(tmp_path: Path):
    repo = tmp_path / "repo"
    observed_sha = _init_repo(repo)
    base_sha = _commit(repo, "baseline.txt", "baseline\n", "baseline")
    current_sha = _commit(repo, "work.py", "work\n", "current")

    result = is_task_satisfied(
        {"id": "T4c", "files_changed": ["seed.txt"]},
        [
            EvidenceRef(
                "landed_diff",
                EvidenceStatus.satisfied,
                "pre-baseline change",
                {
                    "task_ids": ["T4c"],
                    "files_changed": ["seed.txt"],
                    "head_sha": observed_sha,
                },
            )
        ],
        current_head=current_sha,
        execution_window=EvidenceExecutionWindow(
            project_dir=repo,
            base_sha=base_sha,
            head_sha=current_sha,
        ),
    )

    assert result.status == EvidenceStatus.unsatisfied
    assert result.stale_evidence == ("head_mismatch:landed_diff",)


def test_task_satisfaction_reports_missing_freshness_as_unknown():
    result = is_task_satisfied(
        {"id": "T5"},
        [
            EvidenceRef(
                "worker_did_work",
                EvidenceStatus.satisfied,
                "legacy activity present",
                {"task_ids": ["T5"]},
            )
        ],
        current_head="head",
        current_code_hash="hash",
    )

    assert result.status == EvidenceStatus.unknown
    assert result.stale_evidence == (
        "missing_head:worker_did_work",
        "missing_code_hash:worker_did_work",
    )


def test_task_satisfaction_normalizes_unknown_legacy_evidence():
    result = is_task_satisfied(
        {"id": "T5b"},
        {
            "evidence": [
                {
                    "kind": "green_suite",
                    "status": "not_evaluated",
                    "summary": "legacy provider skipped",
                    "details": {"task_ids": ["T5b"]},
                }
            ]
        },
    )

    assert result.status == EvidenceStatus.unknown
    assert result.evidence[0].status == EvidenceStatus.unknown
    assert result.evidence[0].details["diagnostics"]["legacy_status"] == "not_evaluated"
    assert result.would_block_reasons == ()


def test_task_satisfaction_explicit_waiver_exempts_missing_and_stale_outputs():
    result = is_task_satisfied(
        {"id": "T6", "files_changed": ["src/missing.py"]},
        [
            EvidenceRef(
                "declared_noop",
                EvidenceStatus.waived,
                "declared no-op accepted",
                {"task_ids": ["T6"], "head_sha": "old-head"},
            )
        ],
        current_head="new-head",
    )

    assert result.status == EvidenceStatus.waived
    assert result.would_block_reasons == ()
    assert result.missing_outputs == ("files_changed:src/missing.py",)
    assert result.stale_evidence == ("head_mismatch:declared_noop",)


def test_task_satisfaction_not_applicable_exempts_missing_outputs():
    result = is_task_satisfied(
        {"id": "T6b", "commands_run": ["pytest"]},
        [
            EvidenceRef(
                "declared_noop",
                EvidenceStatus.not_applicable,
                "task does not apply",
                {"task_ids": ["T6b"]},
            )
        ],
    )

    assert result.status == EvidenceStatus.not_applicable
    assert result.missing_outputs == ("commands_run:pytest",)
    assert result.would_block_reasons == ()


def test_task_satisfaction_links_by_criterion_and_section_outputs():
    result = is_task_satisfied(
        {"id": "T7", "criterion_ids": ["C1"], "sections_written": ["intro"]},
        [
            {
                "kind": "worker_did_work",
                "status": "satisfied",
                "summary": "section written",
                "details": {"criterion_ids": ["C1"], "sections_written": ["intro"]},
            }
        ],
    )

    assert result.status == EvidenceStatus.satisfied
    assert result.evidence[0].kind == "worker_did_work"
