from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol, Sequence


class GitRunner(Protocol):
    def __call__(
        self,
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        ...


def git_stdout(pack_dir: Path, args: Sequence[str], *, runner: GitRunner | None = None) -> str | None:
    """Run ``git -C pack_dir ...`` and return stdout, or ``None`` on failure."""

    run = subprocess.run if runner is None else runner
    try:
        return run(["git", "-C", str(pack_dir), *args], check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def git_head(pack_dir: Path, *, runner: GitRunner | None = None) -> str | None:
    stdout = git_stdout(pack_dir, ["rev-parse", "HEAD"], runner=runner)
    return (stdout or "").strip() or None


__all__ = ["GitRunner", "git_head", "git_stdout"]
