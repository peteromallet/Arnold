from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan.cloud.incident_bridge import (
    append_install_sync_applied,
    append_install_sync_failed,
)
from arnold_pipelines.megaplan.cloud.redact import redact_text
from arnold_pipelines.megaplan.cloud.runtime_manifest import ManifestError


Runner = Callable[..., subprocess.CompletedProcess[str]]

_IDENTITY_PROBE = (
    "import json, pathlib, sys; "
    "import arnold_pipelines; "
    "package_file = pathlib.Path(arnold_pipelines.__file__).resolve(); "
    "print(json.dumps({"
    "'python_executable': sys.executable, "
    "'package_file': str(package_file), "
    "'package_root': str(package_file.parent.parent)"
    "}, sort_keys=True))"
)


def _run(
    command: list[str],
    *,
    cwd: Path,
    runner: Runner,
) -> subprocess.CompletedProcess[str]:
    return runner(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _tail(text: str, *, max_lines: int = 20) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    return "\n".join(lines[-max_lines:]).strip()


def _redacted_tail(text: str) -> str:
    return redact_text(_tail(text or ""))


def _command_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def capture_runtime_identity(
    source_root: Path | str,
    *,
    python_executable: str | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    root = Path(source_root).expanduser().resolve()
    python_bin = python_executable or sys.executable

    git_head_proc = _run(["git", "rev-parse", "HEAD"], cwd=root, runner=runner)
    git_branch_proc = _run(["git", "branch", "--show-current"], cwd=root, runner=runner)
    probe_proc = _run([python_bin, "-c", _IDENTITY_PROBE], cwd=root, runner=runner)

    package_identity: dict[str, Any] = {}
    if probe_proc.returncode == 0:
        try:
            import json

            loaded = json.loads(probe_proc.stdout or "{}")
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            package_identity = loaded

    return {
        "source_root": str(root),
        "python_executable": package_identity.get("python_executable") or python_bin,
        "git_head": (git_head_proc.stdout or "").strip() or None,
        "git_branch": (git_branch_proc.stdout or "").strip() or None,
        "package_file": package_identity.get("package_file"),
        "package_root": package_identity.get("package_root"),
    }


def apply_install_sync(
    *,
    source_root: Path | str,
    incident_id: str,
    session_id: str | None = None,
    problem_id: str | None = None,
    root: Path | str | None = None,
    python_executable: str | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    source = Path(source_root).expanduser().resolve()
    python_bin = python_executable or sys.executable
    command = [python_bin, "-m", "pip", "install", "-e", str(source)]
    before_identity = capture_runtime_identity(
        source,
        python_executable=python_bin,
        runner=runner,
    )
    install_proc = _run(command, cwd=source, runner=runner)
    after_identity = capture_runtime_identity(
        source,
        python_executable=python_bin,
        runner=runner,
    )

    command_text = _command_text(command)
    verification = {
        "kind": "install_sync_verification",
        "expected_git_head": before_identity.get("git_head"),
        "observed_git_head": after_identity.get("git_head"),
        "runtime_changed": before_identity != after_identity,
        "returncode": install_proc.returncode,
        "success": install_proc.returncode == 0,
    }
    evidence = [
        {
            "kind": "runtime_identity",
            "before": before_identity,
            "after": after_identity,
            "command": command_text,
            "returncode": install_proc.returncode,
        },
        {
            "kind": "command_result",
            "command": command_text,
            "returncode": install_proc.returncode,
            "stdout_tail": _redacted_tail(install_proc.stdout or ""),
            "stderr_tail": _redacted_tail(install_proc.stderr or ""),
        },
        verification,
    ]
    summary = (
        f"Editable install synced with {command_text}"
        if install_proc.returncode == 0
        else f"Editable install sync failed with {command_text}"
    )
    if install_proc.returncode == 0:
        event = append_install_sync_applied(
            incident_id=incident_id,
            summary=summary,
            evidence=evidence,
            session_id=session_id,
            problem_id=problem_id,
            root=root or source,
        )
        status = "applied"
    else:
        event = append_install_sync_failed(
            incident_id=incident_id,
            summary=summary,
            evidence=evidence,
            session_id=session_id,
            problem_id=problem_id,
            root=root or source,
        )
        status = "failed"

    return {
        "status": status,
        "command": command,
        "command_text": command_text,
        "returncode": install_proc.returncode,
        "before_identity": before_identity,
        "after_identity": after_identity,
        "stdout_tail": evidence[1]["stdout_tail"],
        "stderr_tail": evidence[1]["stderr_tail"],
        "verification": verification,
        "event": event,
    }


class EditablePointerMismatchError(RuntimeError):
    """The venv's editable pointer targets a tree other than the manifest runtime.

    Design rule 2: never write an editable pointer into an environment another
    runtime uses. A mismatched pointer means this venv already belongs to a
    different runtime tree — sync aborts instead of clobbering it.
    """

    code = "editable_pointer_mismatch"

    def __init__(
        self,
        *,
        pointer_file: Path | str,
        pointer_target: str,
        runtime_root: Path | str,
    ) -> None:
        self.pointer_file = str(pointer_file)
        self.pointer_target = pointer_target
        self.runtime_root = str(runtime_root)
        super().__init__(
            f"editable_pointer_mismatch: venv editable pointer {self.pointer_file} "
            f"targets {pointer_target!r}, expected manifest runtime {self.runtime_root!r}"
        )


def _manifest_value(manifest: Any, name: str, default: Any = None) -> Any:
    """Read a top-level manifest field from a dict OR a RuntimeManifest object."""
    if isinstance(manifest, Mapping):
        return manifest.get(name, default)
    return getattr(manifest, name, default)


def _manifest_section(manifest: Any, name: str) -> dict[str, Any]:
    section = _manifest_value(manifest, name)
    if not isinstance(section, dict):
        raise ManifestError(
            f"manifest section {name!r} must be an object, "
            f"got {type(section).__name__}"
        )
    return section


def _manifest_path(section: dict[str, Any], key: str) -> Path:
    raw = section.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise ManifestError(f"manifest epic.{key} must be a non-empty path string")
    return Path(raw).expanduser()


def _sync_policy_disabled(sync_policy: Any) -> bool:
    """True when the manifest's sync_policy disables sync.

    Mirrors :func:`arnold_pipelines.megaplan.cloud.github_sync.sync_policy_gate`
    for the two disabling forms ("disabled" / ``{"enabled": false}``) without
    pulling the GitHub publication stack into this module.
    """
    if isinstance(sync_policy, Mapping):
        return sync_policy.get("enabled") is False
    if isinstance(sync_policy, str):
        return sync_policy.strip().lower() == "disabled"
    return False


def _venv_site_packages(venv_path: Path) -> list[Path]:
    if not venv_path.is_dir():
        return []
    return sorted(venv_path.glob("lib/python*/site-packages"))


def _read_editable_pointer_targets(site_packages: list[Path]) -> list[tuple[Path, str]]:
    """(pointer_file, target) for every path-line in any ``*.pth`` under *site_packages*."""
    targets: list[tuple[Path, str]] = []
    for site_dir in site_packages:
        for pth in sorted(site_dir.glob("*.pth")):
            try:
                lines = pth.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for raw in lines:
                line = raw.strip()
                if line.startswith("/") and not line.startswith("//"):
                    targets.append((pth, line))
    return targets


def _check_editable_pointer(venv_path: Path, runtime_root: Path) -> dict[str, Any]:
    """Per-venv editable pointer check (design rule 2).

    A pointer that references a tree other than *runtime_root* means this venv
    already belongs to another runtime — error out rather than write an
    editable pointer into an environment another runtime uses. A venv with no
    editable pointer (or one pointing at *runtime_root*) is safe to sync.
    """
    site_packages = _venv_site_packages(venv_path)
    targets = _read_editable_pointer_targets(site_packages)
    expected = runtime_root.resolve()
    for pointer_file, target in targets:
        if Path(target).expanduser().resolve() == expected:
            continue
        raise EditablePointerMismatchError(
            pointer_file=pointer_file,
            pointer_target=target,
            runtime_root=runtime_root,
        )
    return {
        "site_packages": [str(site_dir) for site_dir in site_packages],
        "pointer_present": bool(targets),
        "pointer_target": targets[0][1] if targets else None,
        "matches_runtime": True,
    }


def manifest_driven_sync(
    manifest: Mapping[str, Any],
    *,
    dry_run: bool = False,
    incident_id: str | None = None,
    session_id: str | None = None,
    problem_id: str | None = None,
    root: Path | str | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Manifest-driven install sync scoped to ``manifest.epic``.

    Reads the epic section (``runtime_root``, ``venv_path``, ``branch``,
    ``expected_head``) and ``policy.sync_policy`` from an already-loaded
    runtime manifest (either a plain mapping or a
    :class:`~arnold_pipelines.megaplan.cloud.runtime_manifest.RuntimeManifest`
    object). When sync is disabled by policy, nothing runs and the result is
    ``{"status": "skipped", "reason": "sync_policy_disabled"}``. Otherwise the
    venv's editable pointer is verified against ``runtime_root`` (per-venv
    editable pointer check, design rule 2) and the same editable-install sync
    as :func:`apply_install_sync` is applied into the epic venv.

    ``dry_run=True`` performs every read/check but no mutation, returning what
    would happen.
    """
    epic = _manifest_section(manifest, "epic")
    policy = _manifest_section(manifest, "policy")

    runtime_root = _manifest_path(epic, "runtime_root")
    venv_path = _manifest_path(epic, "venv_path")
    branch = str(epic.get("branch") or "")
    expected_head = str(epic.get("expected_head") or "") or None
    sync_policy = policy.get("sync_policy")

    if _sync_policy_disabled(sync_policy):
        return {"status": "skipped", "reason": "sync_policy_disabled"}

    pointer = _check_editable_pointer(venv_path, runtime_root)

    venv_python = venv_path / "bin" / "python"
    command = [str(venv_python), "-m", "pip", "install", "-e", str(runtime_root)]

    if dry_run:
        return {
            "status": "would_sync",
            "dry_run": True,
            "runtime_root": str(runtime_root),
            "venv_path": str(venv_path),
            "branch": branch,
            "expected_head": expected_head,
            "sync_policy": sync_policy,
            "editable_pointer": pointer,
            "command": command,
            "command_text": _command_text(command),
        }

    return apply_install_sync(
        source_root=runtime_root,
        incident_id=incident_id
        or str(_manifest_value(manifest, "epic_id") or "manifest-sync"),
        session_id=session_id,
        problem_id=problem_id,
        root=root,
        python_executable=str(venv_python),
        runner=runner,
    )


__all__ = [
    "EditablePointerMismatchError",
    "apply_install_sync",
    "capture_runtime_identity",
    "manifest_driven_sync",
]
