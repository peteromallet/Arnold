"""Deterministic validation job compiler.

Compiles only no-file deterministic checks from the validation_jobs array in a
finalized plan payload.  Rejects ambiguous (missing/incomplete command) or
mutating (file-writing) validation as model/human work.

This module is intentionally pure — the same decision can be repeated at
execute entry and compared by content hash.  It does not add authority
semantics; the finalize schema update in finalize_contract.py is purely
structural.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Diagnostic codes
# ---------------------------------------------------------------------------
VALIDATION_AMBIGUOUS = "validation_ambiguous"
VALIDATION_MUTATING = "validation_mutating"
VALIDATION_MISSING_COMMAND = "validation_missing_command"

# ---------------------------------------------------------------------------
# Required fields for a deterministic validation job
# ---------------------------------------------------------------------------
_REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "command",
    "environment",
    "cwd",
    "timeout_seconds",
    "expected_output_paths",
    "content_addressed_evidence",
)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationDiagnostic:
    """Typed diagnostic from validation job compilation.

    Codes:
      - ``validation_ambiguous`` — the job is missing required fields, has
        an untyped / placeholder command, or requires model/human judgment.
      - ``validation_mutating`` — the job declares expected_output_paths or
        a write_set that would mutate the repository.
      - ``validation_missing_command`` — the job command is missing,
        empty, or not a list of non-empty strings.
    """

    code: str
    message: str
    job_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.job_id is not None:
            result["job_id"] = self.job_id
        return result


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def _is_ambiguous_command(command: list[str]) -> bool:
    """Return True when *command* is structurally undeterministic.

    A command is ambiguous when it uses a placeholder first token (``...``,
    ``…``, ``???``, ``<``, ``$``, ``{{``) that signals the model did not
    commit to an actual executable or when every token is non-executable
    meta-instruction text.
    """
    if not command:
        return True
    first = command[0].strip()
    if not first:
        return True
    # Placeholder / template tokens
    if first.startswith(("...", "…", "???", "<", "$", "{{")):
        return True
    # Every token looks like a prose instruction, not an executable path
    if all(" " in token and not token.startswith(("-", "--")) for token in command):
        return True
    return False


def _is_mutating(job: Mapping[str, Any]) -> bool:
    """Return True when *job* would mutate the repository.

    Mutating means:
    - ``expected_output_paths`` is a non-empty list (produces files).
    - ``write_set`` declares paths.
    """
    paths = job.get("expected_output_paths")
    if isinstance(paths, list) and paths:
        return True
    write_set = job.get("write_set")
    if isinstance(write_set, Mapping):
        ws_paths = write_set.get("paths")
        if isinstance(ws_paths, list) and ws_paths:
            return True
    return False


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


def compile_validation_jobs(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile no-file deterministic validation jobs from *payload*.

    Only jobs that are structurally deterministic and do not produce files
    are admitted.  Ambiguous or mutating jobs produce diagnostics and are
    excluded from the compiled output.

    Returns a dict with:
      - ``validation_jobs`` : list of compiled (normalized) job dicts
      - ``diagnostics`` : list of :class:`ValidationDiagnostic` dicts
      - ``admitted`` : True when diagnostics is empty
    """
    diagnostics: list[ValidationDiagnostic] = []

    raw_jobs = payload.get("validation_jobs")
    if not isinstance(raw_jobs, list):
        # Missing or non-list — produce a single diagnostic, no compiled jobs
        diagnostics.append(
            ValidationDiagnostic(
                VALIDATION_AMBIGUOUS,
                "validation_jobs must be an array; harness-owned validation cannot be model work.",
            )
        )
        return {
            "validation_jobs": [],
            "diagnostics": [d.as_dict() for d in diagnostics],
            "admitted": False,
        }

    compiled: list[dict[str, Any]] = []

    for idx, raw in enumerate(raw_jobs):
        if not isinstance(raw, Mapping):
            diagnostics.append(
                ValidationDiagnostic(
                    VALIDATION_AMBIGUOUS,
                    f"Validation job at index {idx} is not a dict; cannot compile.",
                )
            )
            continue

        job = dict(raw)
        job_id = job.get("id")
        if isinstance(job_id, str) and job_id.strip():
            job_id = job_id.strip()
        elif job_id is not None:
            job_id = str(job_id)
        else:
            job_id = f"#VJ{idx}"

        # ---- required-fields check -----------------------------------------
        missing = [f for f in _REQUIRED_FIELDS if f not in job or job[f] is None]
        if missing:
            diagnostics.append(
                ValidationDiagnostic(
                    VALIDATION_AMBIGUOUS,
                    f"Validation job {job_id!r} is missing required fields: {missing}.",
                    str(job_id),
                )
            )
            continue

        # ---- command check -------------------------------------------------
        command = job.get("command")
        if not isinstance(command, list) or not command:
            diagnostics.append(
                ValidationDiagnostic(
                    VALIDATION_MISSING_COMMAND,
                    f"Validation job {job_id!r} must have a non-empty command list.",
                    str(job_id),
                )
            )
            continue
        if any(not isinstance(c, str) or not c.strip() for c in command):
            diagnostics.append(
                ValidationDiagnostic(
                    VALIDATION_MISSING_COMMAND,
                    f"Validation job {job_id!r} command must be a list of non-empty strings.",
                    str(job_id),
                )
            )
            continue
        if _is_ambiguous_command(command):
            diagnostics.append(
                ValidationDiagnostic(
                    VALIDATION_AMBIGUOUS,
                    f"Validation job {job_id!r} command is structurally ambiguous "
                    f"(placeholder or prose instruction); only deterministic "
                    f"executables are compiled.",
                    str(job_id),
                )
            )
            continue

        # ---- mutating check ------------------------------------------------
        if _is_mutating(job):
            diagnostics.append(
                ValidationDiagnostic(
                    VALIDATION_MUTATING,
                    f"Validation job {job_id!r} declares file outputs; "
                    f"only no-file deterministic checks are compiled.",
                    str(job_id),
                )
            )
            continue

        # ---- type / normalize remaining fields -----------------------------
        environment = job.get("environment")
        if not isinstance(environment, Mapping):
            environment = {}
        else:
            environment = {str(k): str(v) for k, v in environment.items()}

        cwd = job.get("cwd")
        if not isinstance(cwd, str) or not cwd.strip():
            cwd = "${project_dir}"

        timeout = job.get("timeout_seconds")
        if isinstance(timeout, bool) or not isinstance(timeout, int):
            if not isinstance(timeout, bool):
                try:
                    timeout = int(timeout)
                except (TypeError, ValueError):
                    diagnostics.append(
                        ValidationDiagnostic(
                            VALIDATION_AMBIGUOUS,
                            f"Validation job {job_id!r} timeout_seconds must be an integer.",
                            str(job_id),
                        )
                    )
                    continue
            else:
                diagnostics.append(
                    ValidationDiagnostic(
                        VALIDATION_AMBIGUOUS,
                        f"Validation job {job_id!r} timeout_seconds must be an integer, not a boolean.",
                        str(job_id),
                    )
                )
                continue
        if timeout <= 0:
            diagnostics.append(
                ValidationDiagnostic(
                    VALIDATION_AMBIGUOUS,
                    f"Validation job {job_id!r} timeout_seconds must be positive.",
                    str(job_id),
                )
            )
            continue

        content_addressed = job.get("content_addressed_evidence", True)
        if not isinstance(content_addressed, bool):
            content_addressed = bool(content_addressed)

        compiled.append(
            {
                "id": str(job_id),
                "command": [str(c) for c in command],
                "environment": environment,
                "cwd": str(cwd),
                "timeout_seconds": int(timeout),
                "expected_output_paths": [],
                "content_addressed_evidence": bool(content_addressed),
            }
        )

    return {
        "validation_jobs": compiled,
        "diagnostics": [d.as_dict() for d in diagnostics],
        "admitted": len(diagnostics) == 0,
    }


__all__ = [
    "VALIDATION_AMBIGUOUS",
    "VALIDATION_MISSING_COMMAND",
    "VALIDATION_MUTATING",
    "ValidationDiagnostic",
    "compile_validation_jobs",
]
