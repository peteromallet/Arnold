"""Shared helpers for opt-in RunPod smoke tests.

Centralises the bits every test in tests/smoke/test_*runpod*.py needs:
  * loading the runpod_lifecycle package (with VIBECOMFY_RUNPOD_LIFECYCLE_ROOT fallback)
  * resolving the git repo URL + ref to install on a remote pod
  * installing the current branch onto a pod via SSH
  * a single canonical pod-name pattern so orphans are greppable
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
from types import ModuleType

import pytest


POD_NAME_PREFIX = "vibecomfy-layer2"


def require_runpod_api_key() -> None:
    """Skip the calling test if RUNPOD_API_KEY is not set."""
    if not os.environ.get("RUNPOD_API_KEY"):
        pytest.skip("RUNPOD_API_KEY is required for the opt-in RunPod smoke test.")


def load_runpod_lifecycle() -> ModuleType:
    """Import runpod_lifecycle, honouring VIBECOMFY_RUNPOD_LIFECYCLE_ROOT for source checkouts."""
    lifecycle_root = os.environ.get("VIBECOMFY_RUNPOD_LIFECYCLE_ROOT")
    if lifecycle_root and lifecycle_root not in sys.path:
        sys.path.insert(0, lifecycle_root)
    try:
        return importlib.import_module("runpod_lifecycle")
    except ImportError:
        pytest.skip(
            "runpod_lifecycle is required; install it or set VIBECOMFY_RUNPOD_LIFECYCLE_ROOT to its source root."
        )
        raise  # unreachable; appeases type checkers


def pod_name(phase: str, family: str = "all") -> str:
    """Canonical name pattern: vibecomfy-layer2-{phase}-{family}-{epoch}."""
    return f"{POD_NAME_PREFIX}-{phase}-{family}-{int(time.time())}"


def resolve_repo_install_target() -> tuple[str, str]:
    """Return (repo_url, git_ref) for `pip install git+{url}@{ref}`.

    Skips the test when the repo URL cannot be resolved (no env var, no git remote).
    """
    repo_url = os.environ.get("VIBECOMFY_RUNPOD_REPO_URL") or _git_output("config --get remote.origin.url")
    if not repo_url:
        pytest.skip("Set VIBECOMFY_RUNPOD_REPO_URL or configure git remote.origin.url for remote install.")
    git_ref = os.environ.get("VIBECOMFY_RUNPOD_GIT_REF") or _git_output("rev-parse --abbrev-ref HEAD") or "HEAD"
    if git_ref == "HEAD":
        git_ref = _git_output("rev-parse HEAD") or "HEAD"
    return repo_url, git_ref


async def install_current_branch(pod) -> None:
    """Install the current vibecomfy branch + HiddenSwitch ComfyUI onto a ready pod.

    vibecomfy depends on the HiddenSwitch ``comfyui`` pip fork (with a vibecomfy-vendored
    ComfyUI patch branch) and ``comfy-script``. Without these, ``import comfy`` fails
    inside ``EmbeddedSession``. See ``scripts/runpod_validate.py`` for the canonical
    install line.
    """
    repo_url, git_ref = resolve_repo_install_target()
    install_cmd = (
        "set -e && "
        "python -m pip install --upgrade pip && "
        "python -m pip install "
        "'comfyui@git+https://github.com/peteromallet/ComfyUI.git@fix/latentupscale-model-mmap-residency' "
        "'comfy-script[default]' && "
        f"python -m pip install --upgrade 'git+{repo_url}@{git_ref}'"
    )
    code, stdout, stderr = await pod.exec_ssh(install_cmd, timeout=1800)
    assert code == 0, f"remote install failed with {code}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"


def _git_output(args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args.split()],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


__all__ = [
    "POD_NAME_PREFIX",
    "install_current_branch",
    "load_runpod_lifecycle",
    "pod_name",
    "require_runpod_api_key",
    "resolve_repo_install_target",
]
