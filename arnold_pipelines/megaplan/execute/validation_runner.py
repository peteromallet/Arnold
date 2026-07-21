"""Deterministic validation job runner.

Executes compiled validation jobs as subprocesses — never model calls —
and captures evidence: command, env, exit code, stdout/stderr, duration,
code hash, and result hash.  Mutating or unavailable jobs fail visibly.

This module is the execute-side counterpart of
:mod:`arnold_pipelines.megaplan.orchestration.validation_compiler`.
Together they form the M8A guarantee that validation-only work never
consumes a model call.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ValidationJobResult:
    """Evidence captured from a single validation job execution."""

    job_id: str
    command: list[str]
    environment: dict[str, str]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    code_hash: str
    result_hash: str
    timed_out: bool = False
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "command": self.command,
            "environment": self.environment,
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "code_hash": self.code_hash,
            "result_hash": self.result_hash,
            "timed_out": self.timed_out,
            "error": self.error,
        }


@dataclass
class ValidationRunReport:
    """Aggregate report from running all validation jobs in a batch."""

    results: list[ValidationJobResult] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    admitted: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "results": [r.as_dict() for r in self.results],
            "diagnostics": self.diagnostics,
            "admitted": self.admitted,
        }


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------


def _compute_code_hash(job: dict[str, Any]) -> str:
    """Content-address the job identity: command + environment + cwd."""
    payload = {
        "command": job.get("command", []),
        "environment": job.get("environment", {}),
        "cwd": job.get("cwd", ""),
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _compute_result_hash(
    exit_code: int, stdout: str, stderr: str
) -> str:
    """Content-address the job result: exit code + stdout + stderr."""
    payload = {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Validation job classification (re-runs compile-time checks at execute time)
# ---------------------------------------------------------------------------


def _classify_job(job: dict[str, Any]) -> str | None:
    """Return a diagnostic code if the job is not executable, else None.

    Re-runs the compile-time checks at execute time so that any job that
    slipped past compilation still fails visibly.
    """
    # Mutating check
    paths = job.get("expected_output_paths")
    if isinstance(paths, list) and paths:
        return "validation_mutating"
    write_set = job.get("write_set")
    if isinstance(write_set, Mapping):
        ws_paths = write_set.get("paths")
        if isinstance(ws_paths, list) and ws_paths:
            return "validation_mutating"

    # Command check
    command = job.get("command")
    if not isinstance(command, list) or not command:
        return "validation_missing_command"
    if any(not isinstance(c, str) or not c.strip() for c in command):
        return "validation_missing_command"

    return None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _resolve_cwd(cwd: str, project_dir: Path) -> Path:
    """Resolve the job cwd, replacing ``${project_dir}`` with the real path."""
    resolved = cwd.replace("${project_dir}", str(project_dir))
    return Path(resolved)


def run_single_validation_job(
    job: dict[str, Any],
    *,
    project_dir: Path,
) -> ValidationJobResult:
    """Execute a single compiled validation job as a subprocess.

    Parameters
    ----------
    job:
        A compiled validation job dict (from
        ``validation_compiler.compile_validation_jobs``).
    project_dir:
        The project directory to resolve ``${project_dir}`` tokens against.

    Returns
    -------
    ValidationJobResult
        The captured evidence — even if the subprocess itself fails to launch,
        the result carries an ``error`` field and a non-zero exit_code.
    """
    job_id = str(job.get("id", "unknown"))
    command = job.get("command", [])
    if not isinstance(command, list):
        command = []
    environment = job.get("environment")
    if not isinstance(environment, Mapping):
        environment = {}
    env_dict = {str(k): str(v) for k, v in environment.items()}
    cwd_raw = str(job.get("cwd", "${project_dir}"))
    cwd = _resolve_cwd(cwd_raw, project_dir)
    timeout = job.get("timeout_seconds", 300)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        timeout = 300

    code_hash = _compute_code_hash(job)

    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env={**env_dict} if env_dict else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.monotonic() - start
        exit_code = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        timed_out = False
        error = None
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        exit_code = -1
        stdout = exc.stdout or "" if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr or "" if isinstance(exc.stderr, str) else ""
        timed_out = True
        error = f"Validation job {job_id!r} timed out after {timeout}s."
    except OSError as exc:
        duration = time.monotonic() - start
        exit_code = -2
        stdout = ""
        stderr = ""
        timed_out = False
        error = f"Validation job {job_id!r} failed to launch: {exc}"

    result_hash = _compute_result_hash(exit_code, stdout, stderr)

    return ValidationJobResult(
        job_id=job_id,
        command=[str(c) for c in command],
        environment=env_dict,
        cwd=str(cwd),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=round(duration, 3),
        code_hash=code_hash,
        result_hash=result_hash,
        timed_out=timed_out,
        error=error,
    )


def run_validation_jobs(
    compiled_jobs: list[dict[str, Any]],
    *,
    project_dir: Path,
) -> ValidationRunReport:
    """Execute compiled validation jobs and produce a run report.

    Each job is run as a subprocess — no model call is made.  Jobs that
    are classified as mutating or missing a command produce a diagnostic
    and are NOT executed (they fail visibly).  All other jobs run and
    produce a :class:`ValidationJobResult` regardless of success/failure.

    Parameters
    ----------
    compiled_jobs:
        List of compiled validation job dicts.
    project_dir:
        The project directory.

    Returns
    -------
    ValidationRunReport
        Aggregate results and diagnostics.
    """
    report = ValidationRunReport()

    if not isinstance(compiled_jobs, list):
        report.diagnostics.append(
            {
                "code": "validation_unavailable",
                "message": "compiled_jobs is not a list; cannot execute validation.",
            }
        )
        report.admitted = False
        return report

    if not compiled_jobs:
        # Empty job list is valid — nothing to run.
        return report

    for job in compiled_jobs:
        if not isinstance(job, Mapping):
            job_id = str(job) if job is not None else "null"
            report.diagnostics.append(
                {
                    "code": "validation_ambiguous",
                    "message": f"Validation job entry is not a dict: {job_id}",
                }
            )
            report.admitted = False
            continue

        job_dict = dict(job)
        classification = _classify_job(job_dict)
        if classification is not None:
            report.diagnostics.append(
                {
                    "code": classification,
                    "message": (
                        f"Validation job {job_dict.get('id', 'unknown')!r} "
                        f"is mutating or has an invalid command; "
                        f"refusing to execute."
                    ),
                    "job_id": job_dict.get("id"),
                }
            )
            report.admitted = False
            continue

        result = run_single_validation_job(job_dict, project_dir=project_dir)
        report.results.append(result)
        if result.error is not None:
            report.diagnostics.append(
                {
                    "code": "validation_execution_error",
                    "message": result.error,
                    "job_id": result.job_id,
                }
            )
            report.admitted = False

    return report


# ---------------------------------------------------------------------------
# Payload extraction
# ---------------------------------------------------------------------------


def extract_compiled_validation_jobs(
    finalize_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract compiled validation jobs from the finalized plan payload.

    Returns the ``validation_jobs`` list from
    ``graph_report.validation_compilation.validation_jobs`` if available,
    otherwise an empty list.
    """
    graph_report = finalize_data.get("graph_report")
    if not isinstance(graph_report, Mapping):
        return []
    compilation = graph_report.get("validation_compilation")
    if not isinstance(compilation, Mapping):
        return []
    jobs = compilation.get("validation_jobs")
    if not isinstance(jobs, list):
        return []
    return [dict(j) for j in jobs if isinstance(j, Mapping)]


__all__ = [
    "ValidationJobResult",
    "ValidationRunReport",
    "extract_compiled_validation_jobs",
    "run_single_validation_job",
    "run_validation_jobs",
]
