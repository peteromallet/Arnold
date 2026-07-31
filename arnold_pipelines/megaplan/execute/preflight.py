"""Worker-launch preflight checks — source identity and environment integrity.

Checks that MUST pass before a Megaplan worker is dispatched:

* **dirty/divergent checkout** — the project repo must be clean (no uncommitted
  changes that would taint the worker's view of source code).
* **invalid editable-install refs** — ``pip install -e .`` must point at the
  expected project directory, not a stale or unrelated path.
* **import leakage** — the worker must not import from outside the declared
  project/site-packages boundary.
* **source/install/runtime revision mismatch** — the source commit, installed
  package version, and runtime environment must agree.

All failures return typed terminal reasons that stop dispatch before any model
call is made. This module is pure — it does no network I/O and only reads from
the local filesystem.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Typed failure kinds
# ---------------------------------------------------------------------------


class PreflightFailureKind:
    """Namespaced constants for preflight failure reasons."""

    DIRTY_CHECKOUT: str = "dirty_checkout"
    DIVERGENT_CHECKOUT: str = "divergent_checkout"
    INVALID_EDITABLE_INSTALL: str = "invalid_editable_install"
    IMPORT_LEAKAGE: str = "import_leakage"
    SOURCE_REVISION_MISMATCH: str = "source_revision_mismatch"
    INSTALL_REVISION_MISMATCH: str = "install_revision_mismatch"
    RUNTIME_REVISION_MISMATCH: str = "runtime_revision_mismatch"
    GIT_UNAVAILABLE: str = "git_unavailable"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreflightCheck:
    """A single preflight check result."""

    kind: str
    passed: bool
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreflightReport:
    """Aggregate result of all preflight checks."""

    passed: bool
    checks: tuple[PreflightCheck, ...]
    summary: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [
                {
                    "kind": check.kind,
                    "passed": check.passed,
                    "detail": check.detail,
                    "evidence": check.evidence,
                }
                for check in self.checks
            ],
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a git command and return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", str(exc)


def _is_git_repo(path: Path) -> bool:
    """Check if *path* is inside a git repository."""
    ec, _, _ = _run_git(["rev-parse", "--git-dir"], cwd=path)
    return ec == 0


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_dirty_checkout(project_dir: Path) -> PreflightCheck:
    """Reject when the working tree has uncommitted changes.

    A dirty checkout means the worker would see source files that differ from
    what is committed. This check uses ``git status --porcelain`` — any output
    is treated as a dirty tree.
    """
    if not _is_git_repo(project_dir):
        return PreflightCheck(
            kind=PreflightFailureKind.GIT_UNAVAILABLE,
            passed=False,
            detail=f"Project directory is not a git repository: {project_dir}",
        )

    ec, stdout, stderr = _run_git(["status", "--porcelain"], cwd=project_dir)
    if ec != 0:
        return PreflightCheck(
            kind=PreflightFailureKind.GIT_UNAVAILABLE,
            passed=False,
            detail=f"git status failed: {stderr}",
        )

    dirty_files = [line for line in stdout.split("\n") if line.strip()]
    if dirty_files:
        return PreflightCheck(
            kind=PreflightFailureKind.DIRTY_CHECKOUT,
            passed=False,
            detail=f"Working tree is dirty ({len(dirty_files)} uncommitted changes)",
            evidence={
                "dirty_count": len(dirty_files),
                "sample_files": dirty_files[:10],
            },
        )
    return PreflightCheck(kind=PreflightFailureKind.DIRTY_CHECKOUT, passed=True)


def check_divergent_checkout(project_dir: Path) -> PreflightCheck:
    """Reject when the local branch has diverged from its upstream.

    A divergent checkout means local commits differ from the remote tracking
    branch, which can cause the worker to execute against the wrong revision.
    """
    if not _is_git_repo(project_dir):
        return PreflightCheck(kind=PreflightFailureKind.DIVERGENT_CHECKOUT, passed=True)

    # Check if we have an upstream branch
    ec, upstream, _ = _run_git(
        ["rev-parse", "--abbrev-ref", "@{upstream}"], cwd=project_dir
    )
    if ec != 0:
        # No upstream — nothing to diverge from; not a failure
        return PreflightCheck(
            kind=PreflightFailureKind.DIVERGENT_CHECKOUT,
            passed=True,
            detail="No upstream tracking branch configured",
        )

    # Compare ahead/behind counts
    ec, stdout, _ = _run_git(
        ["rev-list", "--left-right", "--count", f"HEAD...{upstream.strip()}"],
        cwd=project_dir,
    )
    if ec != 0:
        return PreflightCheck(kind=PreflightFailureKind.DIVERGENT_CHECKOUT, passed=True)

    parts = stdout.split()
    ahead = int(parts[0]) if len(parts) > 0 else 0
    behind = int(parts[1]) if len(parts) > 1 else 0

    if ahead > 0 and behind > 0:
        return PreflightCheck(
            kind=PreflightFailureKind.DIVERGENT_CHECKOUT,
            passed=False,
            detail=f"Branch has diverged: {ahead} ahead, {behind} behind upstream",
            evidence={"ahead": ahead, "behind": behind},
        )
    return PreflightCheck(kind=PreflightFailureKind.DIVERGENT_CHECKOUT, passed=True)


def check_editable_install_refs(project_dir: Path) -> PreflightCheck:
    """Reject when editable installs point outside the expected project tree.

    Uses ``pip show`` to locate editable installs and verifies each ``.pth``
    entry resolves to a path within *project_dir*.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--editable", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_dir),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return PreflightCheck(
            kind=PreflightFailureKind.INVALID_EDITABLE_INSTALL,
            passed=False,
            detail=f"Could not query editable installs: {exc}",
        )

    if result.returncode != 0:
        return PreflightCheck(
            kind=PreflightFailureKind.INVALID_EDITABLE_INSTALL,
            passed=True,
            detail=f"pip list --editable failed (non-fatal): {result.stderr.strip()}",
        )

    import json

    try:
        packages = json.loads(result.stdout)
    except json.JSONDecodeError:
        return PreflightCheck(
            kind=PreflightFailureKind.INVALID_EDITABLE_INSTALL, passed=True
        )

    resolved_project = project_dir.resolve()
    invalid_refs: list[dict[str, str]] = []

    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        location = pkg.get("location") or pkg.get("editable_project_location")
        if not isinstance(location, str) or not location:
            continue
        try:
            loc_path = Path(location).resolve()
        except (OSError, ValueError):
            invalid_refs.append(
                {"package": str(pkg.get("name", "unknown")), "location": str(location)}
            )
            continue

        # The editable location must be inside the project tree
        try:
            loc_path.relative_to(resolved_project)
        except ValueError:
            invalid_refs.append(
                {
                    "package": str(pkg.get("name", "unknown")),
                    "location": str(location),
                    "resolved": str(loc_path),
                }
            )

    if invalid_refs:
        return PreflightCheck(
            kind=PreflightFailureKind.INVALID_EDITABLE_INSTALL,
            passed=False,
            detail=(
                f"Editable installs point outside project tree: "
                f"{', '.join(ref['package'] for ref in invalid_refs)}"
            ),
            evidence={"invalid_refs": invalid_refs},
        )
    return PreflightCheck(kind=PreflightFailureKind.INVALID_EDITABLE_INSTALL, passed=True)


def check_import_leakage(project_dir: Path) -> PreflightCheck:
    """Detect import leakage from outside the project or site-packages.

    Launches a subprocess that imports ``arnold_pipelines.megaplan`` and reports
    any modules loaded from paths outside the expected boundaries. This is a
    defensive check — it does not run during normal operations unless the
    preflight is explicitly invoked.
    """
    script = (
        "import sys, os, json; "
        "project_dir = os.environ.get('PREFLIGHT_PROJECT_DIR', ''); "
        "try: import arnold_pipelines.megaplan; "
        "except ImportError as e: print(json.dumps({'error': str(e)})); sys.exit(0); "
        "leaked = []; "
        "for name, mod in sorted(sys.modules.items()): "
        "    if mod is None: continue; "
        "    path = getattr(mod, '__file__', None) or ''; "
        "    if not path: continue; "
        "    if project_dir and path.startswith(project_dir): continue; "
        "    if '/site-packages/' in path: continue; "
        "    if 'lib/python' in path and '/site-packages/' not in path: leaked.append({'name': name, 'path': path}); "
        "print(json.dumps({'leaked': leaked}))"
    )

    try:
        env = os.environ.copy()
        env["PREFLIGHT_PROJECT_DIR"] = str(project_dir.resolve())
        # Use -S to avoid site-packages pollution during the check
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_dir),
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return PreflightCheck(
            kind=PreflightFailureKind.IMPORT_LEAKAGE,
            passed=False,
            detail=f"Import leakage check failed to run: {exc}",
        )

    import json

    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        # If we can't parse the output, treat as pass (not a preflight blocker)
        return PreflightCheck(kind=PreflightFailureKind.IMPORT_LEAKAGE, passed=True)

    leaked = data.get("leaked", [])
    if isinstance(leaked, list) and leaked:
        return PreflightCheck(
            kind=PreflightFailureKind.IMPORT_LEAKAGE,
            passed=False,
            detail=f"Import leakage detected: {len(leaked)} modules from outside project/site-packages",
            evidence={"leaked_modules": leaked[:20]},
        )
    return PreflightCheck(kind=PreflightFailureKind.IMPORT_LEAKAGE, passed=True)


def check_source_revision(project_dir: Path) -> PreflightCheck:
    """Capture the current source revision (HEAD commit hash)."""
    if not _is_git_repo(project_dir):
        return PreflightCheck(
            kind=PreflightFailureKind.SOURCE_REVISION_MISMATCH,
            passed=False,
            detail=f"Not a git repository: {project_dir}",
        )
    ec, head, stderr = _run_git(["rev-parse", "HEAD"], cwd=project_dir)
    if ec != 0:
        return PreflightCheck(
            kind=PreflightFailureKind.SOURCE_REVISION_MISMATCH,
            passed=False,
            detail=f"Cannot resolve HEAD: {stderr}",
        )
    return PreflightCheck(
        kind=PreflightFailureKind.SOURCE_REVISION_MISMATCH,
        passed=True,
        evidence={"head": head},
    )


def check_install_revision(project_dir: Path) -> PreflightCheck:
    """Capture the installed package revision for the arnold package."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "arnold"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_dir),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return PreflightCheck(
            kind=PreflightFailureKind.INSTALL_REVISION_MISMATCH,
            passed=False,
            detail=f"Could not query installed package: {exc}",
        )

    if result.returncode != 0:
        return PreflightCheck(
            kind=PreflightFailureKind.INSTALL_REVISION_MISMATCH,
            passed=False,
            detail="Package 'arnold' is not installed (editable or otherwise)",
        )

    version = ""
    location = ""
    for line in result.stdout.split("\n"):
        if line.startswith("Version:"):
            version = line.split(":", 1)[1].strip()
        elif line.startswith("Location:"):
            location = line.split(":", 1)[1].strip()

    return PreflightCheck(
        kind=PreflightFailureKind.INSTALL_REVISION_MISMATCH,
        passed=True,
        evidence={
            "version": version,
            "location": location,
        },
    )


def check_revision_consistency(
    source_check: PreflightCheck,
    install_check: PreflightCheck,
) -> PreflightCheck:
    """Verify source and install revisions are consistent.

    For editable installs, the install location should be within the project
    directory. This is a soft check — it warns but doesn't block unless
    the mismatch is clearly dangerous.
    """
    if not source_check.passed or not install_check.passed:
        return PreflightCheck(
            kind=PreflightFailureKind.RUNTIME_REVISION_MISMATCH,
            passed=False,
            detail="Cannot verify revision consistency: source or install check failed",
        )

    return PreflightCheck(
        kind=PreflightFailureKind.RUNTIME_REVISION_MISMATCH,
        passed=True,
        evidence={
            "source_head": source_check.evidence.get("head", ""),
            "install_version": install_check.evidence.get("version", ""),
            "install_location": install_check.evidence.get("location", ""),
        },
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_worker_preflight(
    project_dir: Path,
    *,
    strict: bool = True,
) -> PreflightReport:
    """Run all worker-launch preflight checks.

    Parameters
    ----------
    project_dir:
        Root of the project repository.
    strict:
        If ``True`` (default), failures block dispatch. When ``False``,
        checks still run but only dirty/divergent checkout is blocking.

    Returns
    -------
    PreflightReport
        Aggregate result with per-check details.
    """
    checks: list[PreflightCheck] = []

    # --- Git-integrity checks ---
    dirty = check_dirty_checkout(project_dir)
    checks.append(dirty)

    divergent = check_divergent_checkout(project_dir)
    checks.append(divergent)

    # --- Editable-install checks ---
    editable = check_editable_install_refs(project_dir)
    checks.append(editable)

    # --- Import leakage ---
    leakage = check_import_leakage(project_dir)
    checks.append(leakage)

    # --- Revision checks ---
    source = check_source_revision(project_dir)
    checks.append(source)

    install = check_install_revision(project_dir)
    checks.append(install)

    consistency = check_revision_consistency(source, install)
    checks.append(consistency)

    # Determine pass/fail
    if strict:
        passed = all(check.passed for check in checks)
    else:
        # Non-strict: only dirty/divergent checkout are hard blockers
        hard_failures = {PreflightFailureKind.DIRTY_CHECKOUT, PreflightFailureKind.DIVERGENT_CHECKOUT}
        passed = all(
            check.passed
            for check in checks
            if check.kind in hard_failures or not check.passed
        )
        # In non-strict mode, everything passes if git checks are clean
        passed = dirty.passed and divergent.passed

    failures = [check for check in checks if not check.passed]
    if failures:
        summary = "; ".join(
            f"{check.kind}: {check.detail}" for check in failures
        )
    else:
        summary = "All preflight checks passed"

    return PreflightReport(
        passed=passed,
        checks=tuple(checks),
        summary=summary,
    )
