"""Gitleaks secret-scan policy helpers for worktree execute artifacts."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from megaplan.types import SECRET_SCAN_MODES

from .paths import custody_paths

GITLEAKS_POLICY_NAME = "gitleaks"


class SecretScanError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def secret_scan_report_path(project_dir: str | Path, run_id: str, task_id: str) -> Path:
    return custody_paths(project_dir).secret_scan_report(run_id, task_id)


def run_gitleaks_policy(target: str | Path, *, mode: str) -> dict[str, Any]:
    """Run or explicitly skip the named gitleaks policy."""
    if mode not in SECRET_SCAN_MODES:
        raise SecretScanError(
            "invalid_secret_scan_mode",
            "secret scan mode must be explicit: pr_pushed or local_only",
        )

    executable = shutil.which("gitleaks")
    if mode == "local_only":
        return _result(
            mode=mode,
            status="skipped",
            available=executable is not None,
            exit_class="skipped",
            redacted_reason="local_only mode explicitly skips gitleaks",
        )

    if executable is None:
        return _result(
            mode=mode,
            status="failed",
            available=False,
            exit_class="missing",
            redacted_reason="gitleaks unavailable for pr_pushed scan",
        )

    target_path = Path(target).resolve()
    with tempfile.NamedTemporaryFile(prefix="megaplan-gitleaks-", suffix=".json", delete=False) as handle:
        report_path = Path(handle.name)
    try:
        proc = subprocess.run(
            [
                executable,
                "detect",
                "--no-banner",
                "--redact",
                "--source",
                str(target_path),
                "--report-format",
                "json",
                "--report-path",
                str(report_path),
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        findings_count = _findings_count(report_path)
    except (OSError, subprocess.TimeoutExpired):
        return _result(
            mode=mode,
            status="failed",
            available=True,
            exit_class="error",
            redacted_reason="gitleaks scan failed before producing a trusted result",
        )
    finally:
        try:
            report_path.unlink()
        except FileNotFoundError:
            pass

    if proc.returncode == 0:
        return _result(
            mode=mode,
            status="passed",
            available=True,
            exit_class="clean",
            redacted_reason=None,
            findings_count=findings_count,
        )
    if proc.returncode == 1:
        return _result(
            mode=mode,
            status="failed",
            available=True,
            exit_class="findings",
            redacted_reason="gitleaks reported potential secrets",
            findings_count=findings_count,
        )
    return _result(
        mode=mode,
        status="failed",
        available=True,
        exit_class="error",
        redacted_reason="gitleaks exited with an error before producing a trusted result",
        findings_count=findings_count,
    )


def _result(
    *,
    mode: str,
    status: str,
    available: bool,
    exit_class: str,
    redacted_reason: str | None,
    findings_count: int | None = None,
) -> dict[str, Any]:
    return {
        "policy": GITLEAKS_POLICY_NAME,
        "mode": mode,
        "status": status,
        "available": available,
        "exit_class": exit_class,
        "explicit_local_only_opt_in": mode == "local_only",
        "redacted_reason": redacted_reason,
        "findings_count": findings_count,
    }


def _findings_count(report_path: Path) -> int | None:
    if not report_path.exists() or report_path.stat().st_size == 0:
        return 0
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        findings = payload.get("findings")
        if isinstance(findings, list):
            return len(findings)
    return None
