from __future__ import annotations

import argparse
from pathlib import Path

from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan._core import has_any_plan_root

def _collect_megaplan_roots(
    root: Path, *, tree: bool = False, all_system: bool = False
) -> list[Path]:
    """Collect .megaplan root directories based on search mode."""
    roots: list[Path] = [root]

    if all_system:
        # Search from home directory downward for all .megaplan directories
        home = Path.home()
        for megaplan_dir in sorted(home.rglob(".megaplan")):
            if megaplan_dir.is_dir() and (megaplan_dir / "plans").is_dir():
                candidate = megaplan_dir.parent
                if candidate.resolve() != root.resolve():
                    roots.append(candidate)
    elif tree:
        # Walk up to find parent .megaplan directories
        current = root.resolve().parent
        while True:
            if has_any_plan_root(current) and current.resolve() != root.resolve():
                roots.append(current)
            parent = current.parent
            if parent == current:
                break
            current = parent
        # Walk down to find child .megaplan directories
        for megaplan_dir in sorted(root.rglob(".megaplan")):
            if megaplan_dir.is_dir():
                candidate = megaplan_dir.parent
                if (
                    has_any_plan_root(candidate)
                    and candidate.resolve() != root.resolve()
                ):
                    roots.append(candidate)

    return roots

def _resolve_project_root(args: argparse.Namespace) -> Path:
    """Pick the authoritative project root for handlers that take ``root``.

    Precedence:

    1. ``--project-dir`` (when set on *args*) wins. The CLI flag is a deliberate
       caller override; honoring CWD-based discovery here lets a stray
       ``.megaplan/`` in an ancestor directory hijack the run. That's how
       parallel `megaplan init` invocations from sibling worktrees under
       ``~/Documents/.megaplan-worktrees/<exp>/<profile>/`` collide on a
       ``duplicate_plan`` error — the walk-up hits ``~/Documents/.megaplan/``
       and they all try to write into the same plans dir. See
       ``megaplan/bakeoff/orchestrator.py:_init_profile`` for the spawning side.
    2. Creation commands that are valid before ``.megaplan/`` exists use the
       current Git root (or CWD outside Git), so an unrelated ancestor
       ``.megaplan/`` cannot hijack initialization.
    3. Otherwise fall back to ``_find_megaplan_root(Path.cwd())`` — the legacy
       behavior that lets ``megaplan plan`` / ``status`` / etc. find the
       enclosing project without an explicit flag.
    """
    project_dir = getattr(args, "project_dir", None)
    if project_dir:
        resolved = Path(project_dir).expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise CliError(
                "invalid_project_dir",
                f"--project-dir does not exist or is not a directory: {project_dir}",
            )
        return resolved
    if getattr(args, "command", None) in {"brief", "initiative"}:
        return Path.cwd().resolve()
    import arnold_pipelines.megaplan.cli as cli_mod

    if (
        getattr(args, "command", None) == "strategy"
        and getattr(args, "strategy_action", None) == "init"
    ):
        return cli_mod._find_git_root(Path.cwd().resolve()) or Path.cwd().resolve()
    return cli_mod._find_megaplan_root(Path.cwd())


def _find_megaplan_root(start: Path) -> Path:
    """Walk up from *start* to find the git-root directory containing ``.megaplan/``.

    Strategy: find the git root first (like ``git rev-parse --show-toplevel``),
    then check if it has a ``.megaplan/`` directory.  This avoids ambiguity when
    nested subdirectories also have their own ``.megaplan/``.  Falls back to the
    nearest ancestor with ``.megaplan/`` if not in a git repo, and finally to
    *start* if nothing is found.
    """
    resolved = start.resolve()

    # Try git root first — the canonical project root.
    import arnold_pipelines.megaplan.cli as cli_mod

    git_root = cli_mod._find_git_root(resolved)
    if git_root and (git_root / ".megaplan").is_dir():
        return git_root

    # Fallback: walk up to find nearest .megaplan
    current = resolved
    while True:
        if (current / ".megaplan").is_dir():
            return current
        parent = current.parent
        if parent == current:
            return start
        current = parent


def _find_git_root(start: Path) -> Path | None:
    """Walk up to find the directory containing ``.git``."""
    current = start
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent
