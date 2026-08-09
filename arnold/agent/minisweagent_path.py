"""Locate an optional mini-swe-agent source tree without product imports."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _read_gitdir(repo_root: Path) -> Path | None:
    git_marker = repo_root / ".git"
    if not git_marker.is_file():
        return None
    try:
        raw = git_marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw.lower().startswith("gitdir:"):
        return None
    gitdir = Path(raw[len("gitdir:") :].strip())
    return (
        (repo_root / gitdir).resolve()
        if not gitdir.is_absolute()
        else gitdir.resolve()
    )


def discover_minisweagent_src(repo_root: Path | None = None) -> Path | None:
    """Return the first populated ``mini-swe-agent/src`` candidate."""
    repo_root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    candidates = [repo_root / "mini-swe-agent" / "src"]
    gitdir = _read_gitdir(repo_root)
    if gitdir is not None:
        if len(gitdir.parents) >= 3 and gitdir.parent.name == "worktrees":
            candidates.append(gitdir.parents[2] / "mini-swe-agent" / "src")
        elif gitdir.name == ".git":
            candidates.append(gitdir.parent / "mini-swe-agent" / "src")
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate not in seen and candidate.is_dir():
            return candidate
        seen.add(candidate)
    return None


def ensure_minisweagent_on_path(repo_root: Path | None = None) -> Path | None:
    """Prepend local mini-swe-agent sources when the package is not installed."""
    if importlib.util.find_spec("minisweagent") is not None:
        return None
    src = discover_minisweagent_src(repo_root)
    if src is None:
        return None
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    return src
