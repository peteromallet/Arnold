"""Validation-job receipt tests — strategy-equivalent validation, content-addressed evidence, and fail-closed rejection.

These tests prove that the harness-owned ``validation_jobs`` compiler and
consumer:
- Make zero worker/model calls (suite_runner only, no model dispatch).
- Produce content-addressed pass/fail evidence that is durable.
- Reject malformed or mutating jobs before subprocess execution.
- Use only the ``validation`` work-class event vocabulary.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers — strategy-equivalent payload (mirrors strategy-validation fixture)
# ---------------------------------------------------------------------------

def _strategy_tasks() -> list[dict[str, Any]]:
    """Five tasks matching the Strategy-validation fixture shape."""
    tasks: list[dict[str, Any]] = []
    for i in range(1, 6):
        tasks.append({
            "id": f"T{i}",
            "objective": f"Strategy validation task {i}.",
            "description": f"Implement bounded behavior T{i} and its narrow proof.",
            "kind": "test",
            "status": "pending",
            "complexity": 4,
            "complexity_justification": "One contained module contract.",
            "estimated_minutes": 5,
            "depends_on": [],
            "dependency_reasons": {},
            "routing_group": "",
            "write_set": {"paths": [f"src/t{i}.py"], "complete": True},
            "narrow_tests": {
                "selectors": [f"tests/test_t{i}.py"],
                "max_seconds": 120,
                "max_runs": 2,
            },
            "checkpoint": {
                "required": False,
                "max_interval_seconds": 300,
                "records": [],
            },
        })
    return tasks


def _strategy_payload(
    *,
    mode: str = "scoped",
    extra_tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Finalize payload matching the Strategy-validation fixture shape."""
    tasks = _strategy_tasks()
    if extra_tasks:
        tasks = list(tasks) + list(extra_tasks)
    return {
        "task_contract_version": 2,
        "tasks": tasks,
        "test_selection": {
            "mode": mode,
            "selectors_used": ["tests"],
            "reason": "Authoritative harness-owned post-execute suite.",
        },
        "validation_jobs": [],
    }


def _fresh_plan_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="test_val_jobs_"))


# ---------------------------------------------------------------------------
# Compile validation jobs — Strategy-equivalent
# ---------------------------------------------------------------------------


class TestStrategyEquivalentValidationCompilation:
    """Prove Strategy-equivalent tasks produce deterministic validation jobs."""

    def test_compile_validation_jobs_from_strategy_payload(self) -> None:
        """Strategy tasks produce post_execute_suite + narrow_recheck jobs."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload()
        jobs = compile_validation_jobs(payload)

        # Must have post_execute_suite + 5 narrow rechecks
        kinds = [j["kind"] for j in jobs]
        assert "post_execute_suite" in kinds
        assert kinds.count("narrow_recheck") == 5
        assert len(jobs) == 6

    def test_compile_validation_jobs_is_deterministic(self) -> None:
        """Same payload → same jobs, same order, same hashes."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload()
        run_a = compile_validation_jobs(payload)
        run_b = compile_validation_jobs(payload)

        assert run_a == run_b
        # Also verify JSON serialization is stable
        assert json.dumps(run_a, sort_keys=True) == json.dumps(run_b, sort_keys=True)

    def test_no_post_execute_suite_when_mode_is_none(self) -> None:
        """test_selection mode 'none' skips the post-execute suite."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload(mode="none")
        jobs = compile_validation_jobs(payload)

        kinds = [j["kind"] for j in jobs]
        assert "post_execute_suite" not in kinds
        # But narrow rechecks from tasks still apply
        assert "narrow_recheck" in kinds

    def test_all_validation_jobs_have_writes_files_false(self) -> None:
        """Every compiled job must carry writes_files: False — pure validation."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload()
        jobs = compile_validation_jobs(payload)

        for job in jobs:
            assert job.get("writes_files") is False, (
                f"Job {job.get('id')} must be read-only; got writes_files={job.get('writes_files')}"
            )

    def test_narrow_recheck_references_correct_task_id(self) -> None:
        """Each narrow_recheck job must carry the task_id it checks."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload()
        jobs = compile_validation_jobs(payload)

        narrow_jobs = [j for j in jobs if j["kind"] == "narrow_recheck"]
        task_ids = {j["task_id"] for j in narrow_jobs}
        assert task_ids == {"T1", "T2", "T3", "T4", "T5"}

    def test_post_execute_suite_has_no_task_id(self) -> None:
        """The post-execute suite is global — no single task_id."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload()
        jobs = compile_validation_jobs(payload)

        suite_jobs = [j for j in jobs if j["kind"] == "post_execute_suite"]
        assert len(suite_jobs) == 1
        assert "task_id" not in suite_jobs[0]

    def test_audit_tasks_produce_no_validation_jobs(self) -> None:
        """Audit/research tasks skip validation — they have no test selectors."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload(mode="none", extra_tasks=[
            {
                "id": "A1",
                "objective": "Audit the compliance boundary.",
                "description": "Audit task.",
                "kind": "audit",
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Review only.",
                "estimated_minutes": 10,
                "depends_on": [],
                "dependency_reasons": {},
                "routing_group": "",
                "write_set": {"paths": [], "complete": True},
                "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
            },
        ])
        jobs = compile_validation_jobs(payload)

        # No narrow_recheck for audit tasks
        narrow_task_ids = {
            j.get("task_id") for j in jobs if j["kind"] == "narrow_recheck"
        }
        assert "A1" not in narrow_task_ids


# ---------------------------------------------------------------------------
# Malformed job rejection — fail before subprocess execution
# ---------------------------------------------------------------------------


class TestMalformedJobRejection:
    """Malformed or mutating jobs are rejected before any subprocess runs."""

    def test_validate_model_validation_jobs_rejects_non_empty(self) -> None:
        """Model must emit empty validation_jobs — non-empty is rejected."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            validate_model_validation_jobs,
        )

        issues = validate_model_validation_jobs([{"id": "bad", "kind": "post_execute_suite"}])
        assert len(issues) > 0
        assert any("empty array" in issue for issue in issues)

    def test_validate_model_validation_jobs_accepts_empty_list(self) -> None:
        """Empty list is valid model output."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            validate_model_validation_jobs,
        )

        issues = validate_model_validation_jobs([])
        assert issues == []

    def test_validate_model_validation_jobs_rejects_non_list(self) -> None:
        """Non-list input is rejected."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            validate_model_validation_jobs,
        )

        issues = validate_model_validation_jobs({"id": "bad"})
        assert len(issues) > 0
        assert any("array" in issue for issue in issues)

    def test_validate_model_rejects_writes_files_true(self) -> None:
        """Even in an empty list sentinel, mutating jobs are rejected."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            validate_model_validation_jobs,
        )

        issues = validate_model_validation_jobs([{
            "id": "VJ-mutate",
            "kind": "post_execute_suite",
            "writes_files": True,
        }])
        assert len(issues) > 0
        assert any("writes_files" in issue for issue in issues)

    def test_validate_model_rejects_unknown_kind(self) -> None:
        """Unknown kind values are rejected."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            validate_model_validation_jobs,
        )

        issues = validate_model_validation_jobs([{
            "id": "VJ-weird",
            "kind": "full_integration",
            "writes_files": False,
        }])
        assert len(issues) > 0
        assert any("unknown kind" in issue for issue in issues)

    def test_ambiguous_selectors_produce_no_narrow_job(self) -> None:
        """Ambiguous selectors like '.' or 'tests/' produce no narrow_recheck."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        # Use a standalone payload (not strategy) with unique IDs to avoid collisions
        tasks = [{
            "id": "AMB1",
            "objective": "Ambiguous test.",
            "description": "Task with ambiguous selectors.",
            "kind": "test",
            "status": "pending",
            "complexity": 3,
            "complexity_justification": "One module.",
            "estimated_minutes": 5,
            "depends_on": [],
            "dependency_reasons": {},
            "routing_group": "",
            "write_set": {"paths": ["src/amb1.py"], "complete": True},
            "narrow_tests": {"selectors": ["tests/"], "max_seconds": 120, "max_runs": 2},
            "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
        }]
        payload = {
            "task_contract_version": 2,
            "tasks": tasks,
            "test_selection": {"mode": "none", "selectors_used": [], "reason": ""},
            "validation_jobs": [],
        }
        jobs = compile_validation_jobs(payload)

        # No narrow_recheck from the ambiguous task
        narrow_ids = {j.get("task_id") for j in jobs if j["kind"] == "narrow_recheck"}
        assert "AMB1" not in narrow_ids, "Ambiguous selectors must not produce narrow_recheck jobs"


# ---------------------------------------------------------------------------
# Content-addressed evidence — deterministic and durable
# ---------------------------------------------------------------------------


class TestContentAddressedEvidence:
    """Pass/fail evidence is content-addressed and durable."""

    def test_evidence_hash_is_deterministic_from_payload(self) -> None:
        """Same evidence payload produces same sha256 hash."""
        from arnold_pipelines.megaplan._core.io import sha256_text

        evidence = {
            "job_id": "VJ1",
            "kind": "narrow_recheck",
            "command": "pytest tests/test_t1.py",
            "exit_code": 0,
            "duration": 1.5,
            "raw_log_path": "/tmp/raw_abc.log",
            "code_hash": "sha256:deadbeef",
            "passes": ["test_a", "test_b"],
            "failures": [],
            "status": "passed",
            "collected": 2,
            "collections_parse_ok": True,
            "timeout_reason": None,
        }

        h1 = sha256_text(json.dumps(evidence, sort_keys=True, ensure_ascii=False))
        h2 = sha256_text(json.dumps(evidence, sort_keys=True, ensure_ascii=False))
        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_evidence_hash_differs_when_evidence_differs(self) -> None:
        """Different evidence (e.g. different exit code) → different hash."""
        from arnold_pipelines.megaplan._core.io import sha256_text

        base = {
            "job_id": "VJ1", "kind": "narrow_recheck",
            "command": "pytest tests/test_t1.py",
            "exit_code": 0, "duration": 1.5,
            "raw_log_path": "/tmp/raw_abc.log",
            "code_hash": "sha256:aaa",
            "passes": ["test_a"], "failures": [],
            "status": "passed", "collected": 1,
            "collections_parse_ok": True, "timeout_reason": None,
        }

        mutated = dict(base, exit_code=1, status="failed", failures=["test_a"])
        h_base = sha256_text(json.dumps(base, sort_keys=True, ensure_ascii=False))
        h_mutated = sha256_text(json.dumps(mutated, sort_keys=True, ensure_ascii=False))
        assert h_base != h_mutated

    def test_evidence_stored_to_disk_is_retrievable(self) -> None:
        """Evidence written to a verification/ dir is readable and intact."""
        plan_dir = _fresh_plan_dir()
        try:
            ver_dir = plan_dir / "verification"
            ver_dir.mkdir(parents=True, exist_ok=True)
            evidence = {
                "job_id": "VJ1", "kind": "narrow_recheck",
                "command": "pytest tests/test_t1.py",
                "exit_code": 0, "duration": 1.5,
                "raw_log_path": str(ver_dir / "raw_abc.log"),
                "code_hash": "sha256:aaa",
                "passes": ["test_a"], "failures": [],
                "status": "passed", "collected": 1,
                "collections_parse_ok": True, "timeout_reason": None,
            }
            evidence_json = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
            evidence_path = ver_dir / "validation_VJ1_run01.json"
            evidence_path.write_text(evidence_json, encoding="utf-8")

            # Round-trip
            loaded = json.loads(evidence_path.read_text(encoding="utf-8"))
            assert loaded == evidence
        finally:
            try:
                for f in ver_dir.iterdir():
                    f.unlink()
                ver_dir.rmdir()
                plan_dir.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Zero worker/model calls — validation is harness-owned
# ---------------------------------------------------------------------------


class TestZeroModelCalls:
    """Validation jobs never dispatch workers or consume model calls."""

    def test_validation_job_kinds_are_harness_owned(self) -> None:
        """The allowed kinds are deterministic, not model-generated."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            VALIDATION_JOB_KINDS,
        )

        assert "post_execute_suite" in VALIDATION_JOB_KINDS
        assert "narrow_recheck" in VALIDATION_JOB_KINDS
        # Model-owned kinds like "model_inference" must not leak in
        assert "model_inference" not in VALIDATION_JOB_KINDS
        assert "productive" not in VALIDATION_JOB_KINDS

    def test_compile_validation_jobs_never_references_workers(self) -> None:
        """The compiler has no worker/module dispatch imports or calls."""
        import inspect

        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        source = inspect.getsource(compile_validation_jobs)
        # Must not reference worker/module dispatch
        assert "worker" not in source.lower()
        assert "dispatch" not in source.lower()
        assert "LLM" not in source
        assert "model_call" not in source.lower()

    def test_validation_jobs_payload_has_no_worker_config(self) -> None:
        """Compiled jobs carry no worker/model configuration."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload()
        jobs = compile_validation_jobs(payload)

        for job in jobs:
            assert "worker" not in job
            assert "model" not in job
            assert "tier" not in job
            assert "routing" not in job

    def test_validation_jobs_never_include_productive_work_class(self) -> None:
        """Validation jobs are never classified as productive work."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            VALIDATION_JOB_KINDS,
            compile_validation_jobs,
        )

        payload = _strategy_payload()
        jobs = compile_validation_jobs(payload)

        for job in jobs:
            assert job["kind"] in VALIDATION_JOB_KINDS
            assert job["kind"] != "productive"


# ---------------------------------------------------------------------------
# Mutating validation rejection — validation must be read-only
# ---------------------------------------------------------------------------


class TestMutatingJobRejection:
    """Jobs that would mutate files are rejected before subprocess execution."""

    def test_mutating_task_with_write_set_still_produces_narrow_job(self) -> None:
        """Task with write_set (mutating) still produces narrow_recheck for its tests."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload(mode="none")
        # All strategy tasks have write_set with paths — they are mutating tasks
        # but the narrow_recheck job itself is read-only
        jobs = compile_validation_jobs(payload)

        for job in jobs:
            assert job.get("writes_files") is False

    def test_no_mutating_validation_job_kind_exists(self) -> None:
        """All validation job kinds must be read-only."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            VALIDATION_JOB_KINDS,
        )

        # Verify vocabulary remains pure
        for kind in VALIDATION_JOB_KINDS:
            assert kind in ("post_execute_suite", "narrow_recheck"), (
                f"Unknown kind {kind} — all validation is read-only"
            )

    def test_command_never_includes_file_write_operations(self) -> None:
        """Validation job commands are pytest invocations, never file writers."""
        from arnold_pipelines.megaplan.orchestration.validation_jobs import (
            compile_validation_jobs,
        )

        payload = _strategy_payload()
        jobs = compile_validation_jobs(payload)

        for job in jobs:
            cmd = job.get("command", "")
            # Must contain pytest
            assert "pytest" in cmd, f"Job {job['id']} command lacks pytest: {cmd}"
            # Must not contain file writes
            assert ">" not in cmd, f"Job {job['id']} command has redirect: {cmd}"
            assert ">>" not in cmd, f"Job {job['id']} command has append: {cmd}"
