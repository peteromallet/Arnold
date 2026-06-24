"""Known-repos registry — passive index of every repo where a megaplan
ticket command has been invoked.

Lives at ``$XDG_CONFIG_HOME/megaplan/known_repos.json`` (or
``~/.config/megaplan/known_repos.json``).  Used by ``ticket search
--all-projects`` to discover repos to scan in local-only mode.

The format is a JSON object keyed by absolute repo path:

    {
      "/abs/path/to/repo": {
        "owner": "foo",
        "name": "bar",
        "root_commit_sha": "abc123...",
        "last_seen": "2026-05-12T15:00:00+00:00"
      },
      ...
    }

Touch is best-effort and never raises — registry maintenance must not
break a ticket command if e.g. the home directory is read-only.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .identity import repo_owner_name, repo_root_sha


def _registry_path() -> Path:
    """Return the path to ``known_repos.json``.  Honours ``$XDG_CONFIG_HOME``.

    The ``MEGAPLAN_REGISTRY_HOME`` env var overrides everything (used by
    tests to isolate from the real user registry).
    """
    override = os.environ.get("MEGAPLAN_REGISTRY_HOME")
    if override:
        return Path(override) / "known_repos.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "megaplan" / "known_repos.json"


def load() -> dict[str, dict[str, Any]]:
    """Read the registry, returning an empty dict if missing or unreadable."""
    path = _registry_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _write(data: dict[str, dict[str, Any]]) -> None:
    """Write the registry atomically.  Silently swallows IO errors."""
    path = _registry_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def touch(repo_root: str | Path) -> None:
    """Record *repo_root* (or update its ``last_seen``) in the registry.

    Best-effort: never raises.  Skips repos that aren't git repos (no
    ``.git`` directory) since search has nothing to anchor onto.
    """
    root = Path(repo_root).resolve()
    if not (root / ".git").exists() and not (root / ".megaplan" / "tickets").is_dir():
        # Neither a git repo nor a tickets-bearing dir — don't pollute the registry.
        return

    try:
        owner, name = repo_owner_name(root)
    except Exception:
        owner, name = None, None
    try:
        sha = repo_root_sha(root)
    except Exception:
        sha = None

    data = load()
    data[str(root)] = {
        "owner": owner,
        "name": name,
        "root_commit_sha": sha,
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
    _write(data)


def list_repos() -> list[dict[str, Any]]:
    """Return all known repos, sorted by ``last_seen`` descending.

    Each entry has keys ``path``, ``owner``, ``name``, ``root_commit_sha``,
    ``last_seen``.  Stale entries (paths that no longer exist) are filtered
    out.
    """
    data = load()
    out: list[dict[str, Any]] = []
    for path_str, meta in data.items():
        if not Path(path_str).is_dir():
            continue
        out.append(
            {
                "path": path_str,
                "owner": meta.get("owner"),
                "name": meta.get("name"),
                "root_commit_sha": meta.get("root_commit_sha"),
                "last_seen": meta.get("last_seen"),
            }
        )
    out.sort(key=lambda r: r.get("last_seen") or "", reverse=True)
    return out


def resolve_project(specifier: str) -> Path | None:
    """Resolve a ``--project`` arg to an absolute repo path.

    The specifier may be:
      * an absolute or relative filesystem path that contains
        ``.megaplan/tickets/`` (returned as-is, resolved)
      * an ``owner/name`` form matching a known repo
      * a bare ``name`` matching a known repo (ambiguous matches lose
        — caller can pass ``owner/name`` to disambiguate)
    """
    # Path-style first
    candidate = Path(specifier).expanduser()
    if candidate.is_dir():
        return candidate.resolve()

    # Name-style: look in registry
    spec = specifier.lower()
    matches: list[Path] = []
    for repo in list_repos():
        owner = (repo.get("owner") or "").lower()
        name = (repo.get("name") or "").lower()
        full = f"{owner}/{name}" if owner and name else name
        if spec == full or spec == name:
            matches.append(Path(repo["path"]))
    if len(matches) == 1:
        return matches[0]
    return None
