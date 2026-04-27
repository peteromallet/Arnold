"""Shared helpers for opt-in RunPod smoke tests.

Centralises the bits every test in tests/smoke/test_*runpod*.py needs:
  * loading the runpod_lifecycle package (with VIBECOMFY_RUNPOD_LIFECYCLE_ROOT fallback)
  * resolving the git repo URL + ref to install on a remote pod
  * installing the current branch onto a pod via SSH
  * a single canonical pod-name pattern so orphans are greppable
"""

from __future__ import annotations

import asyncio
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


async def install_current_branch(pod, *, retries: int = 3) -> None:
    """Clone vibecomfy + install HiddenSwitch ComfyUI onto a ready pod.

    A ``pip install git+...`` wheel is not enough: ``ready_templates/`` lives at the
    repo root and is not shipped with the wheel; ``vibecomfy.registry.ready`` resolves
    it from ``Path(__file__).parents[2]/'ready_templates'``, which only exists in a
    checked-out repo. Mirrors ``scripts/runpod_validate.py``.

    Retries the bash install up to ``retries`` times with backoff: RunPod's shared
    ``/workspace`` volume occasionally races on pack download (``tmp_pack_*: No such
    file or directory``) or post-clone checkout (``unable to create file
    requirements.txt``). A clean ``rm -rf`` between tries recovers from both.
    """
    repo_url, git_ref = resolve_repo_install_target()
    # Install onto container-local disk (/root) instead of the shared /workspace
    # network volume — `/workspace` is persistent across pod instances so prior
    # failed installs leave corrupt directories that defeat `rm -rf` on the next
    # pod (`Directory not empty`, stale .git/hooks symlinks, etc).
    repo_dir = "/root/vibecomfy"
    # --depth=1 + shallow-submodules keeps the transfer small enough that pack-write
    # races are far less likely; we don't need history for an ephemeral install.
    install_cmd = (
        "set -e && "
        f"rm -rf {repo_dir} 2>/dev/null || true && "
        f"git clone --depth=1 --branch {git_ref} --shallow-submodules --recurse-submodules "
        f"{repo_url} {repo_dir} && "
        f"cd {repo_dir} && "
        "python -m pip install --upgrade pip && "
        "python -m pip install "
        "'comfyui@git+https://github.com/peteromallet/ComfyUI.git@fix/latentupscale-model-mmap-residency' "
        "'comfy-script[default]' && "
        "python -m pip install -e ."
    )
    last_err: tuple[int, str, str] | None = None
    for attempt in range(1, retries + 1):
        code, stdout, stderr = await pod.exec_ssh(install_cmd, timeout=1800)
        if code == 0:
            return
        last_err = (code, stdout, stderr)
        if attempt < retries:
            await asyncio.sleep(min(15 * attempt, 60))
    assert last_err is not None
    code, stdout, stderr = last_err
    raise AssertionError(
        f"remote install failed with {code} after {retries} attempts\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


async def launch_with_retry(
    runpod_lifecycle, config, name: str, *, retries: int = 4
):
    """Launch a pod, retrying transient RunPod ``LaunchFailure`` with backoff.

    RunPod returns 'Something went wrong. Please try again later or contact support.'
    or 'This machine does not have the resources to deploy your pod.' for ~50% of
    4090 launches when capacity is thin. Retry covers transient capacity windows.
    """
    LaunchFailure = runpod_lifecycle.LaunchFailure  # type: ignore[attr-defined]
    last_exc: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            return await runpod_lifecycle.launch(config, name=name)
        except LaunchFailure as exc:
            last_exc = exc
            if attempt < retries:
                # 30s, 60s, 90s, ... — RunPod capacity windows recover on tens-of-seconds.
                await asyncio.sleep(30 * attempt)
    assert last_exc is not None
    raise last_exc


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
