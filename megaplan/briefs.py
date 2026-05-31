"""Canonical local brief/epic artifact helpers."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import yaml


def slugify(value: str) -> str:
    """Return a stable file-safe slug for a brief or epic name."""
    slug = value.lower().strip()
    slug = re.sub(r"[^\w\s.-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip(".-")[:96]


def briefs_dir(repo_root: str | Path) -> Path:
    """Return and create ``.megaplan/briefs/`` inside *repo_root*."""
    path = Path(repo_root) / ".megaplan" / "briefs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def brief_path(repo_root: str | Path, slug: str) -> Path:
    """Return the canonical path for a single-plan brief slug."""
    normalized = slugify(slug)
    if not normalized:
        raise ValueError("brief slug must not be empty")
    return briefs_dir(repo_root) / f"{normalized}.md"


def epic_dir(repo_root: str | Path, slug: str) -> Path:
    """Return the canonical directory for an epic's chain and milestone briefs."""
    normalized = slugify(slug)
    if not normalized:
        raise ValueError("epic slug must not be empty")
    return briefs_dir(repo_root) / normalized


def write_single_brief(
    repo_root: str | Path,
    slug: str,
    body: str,
    *,
    force: bool = False,
) -> Path:
    """Write a single-plan brief to ``.megaplan/briefs/<slug>.md``."""
    body = body.strip()
    if not body:
        raise ValueError("brief body must not be empty")
    path = brief_path(repo_root, slug)
    if path.exists() and not force:
        raise FileExistsError(path)
    path.write_text(body + "\n", encoding="utf-8")
    return path


def _parse_milestone(raw: str) -> tuple[str, str]:
    label, sep, title = raw.partition("=")
    if not sep:
        label, sep, title = raw.partition(":")
    label = slugify(label)
    title = title.strip() if sep else ""
    if not label:
        raise ValueError(f"invalid milestone spec: {raw!r}")
    return label, title or label.replace("-", " ").title()


def scaffold_epic(
    repo_root: str | Path,
    slug: str,
    milestones: Sequence[str],
    *,
    base_branch: str = "main",
    force: bool = False,
) -> tuple[Path, list[Path]]:
    """Create ``.megaplan/briefs/<epic>/chain.yaml`` and milestone stubs."""
    if not milestones:
        raise ValueError("at least one --milestone is required")
    directory = epic_dir(repo_root, slug)
    directory.mkdir(parents=True, exist_ok=True)

    parsed = [_parse_milestone(item) for item in milestones]
    written: list[Path] = []
    chain_milestones: list[dict[str, str]] = []
    for label, title in parsed:
        path = directory / f"{label}.md"
        if path.exists() and not force:
            raise FileExistsError(path)
        path.write_text(
            "\n".join(
                [
                    f"# {title}",
                    "",
                    "## Outcome",
                    "",
                    "## Scope",
                    "",
                    "## Constraints",
                    "",
                    "## Done Criteria",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        written.append(path)
        chain_milestones.append({"label": label, "idea": str(path.relative_to(repo_root))})

    chain_path = directory / "chain.yaml"
    if chain_path.exists() and not force:
        raise FileExistsError(chain_path)
    chain_path.write_text(
        yaml.safe_dump(
            {
                "base_branch": base_branch,
                "milestones": chain_milestones,
                "on_failure": {"abort": "stop_chain"},
                "on_escalate": {"abort": "stop_chain"},
                "merge_policy": "auto",
                "driver": {"robustness": "standard", "auto_approve": True},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return chain_path, written


def init_from_brief(
    repo_root: str | Path, path: Path, extra_args: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    """Run ``megaplan init`` against an already-written canonical brief file."""
    command = [
        sys.executable,
        "-m",
        "megaplan",
        "init",
        "--project-dir",
        str(Path(repo_root).resolve()),
        "--idea-file",
        str(path.resolve()),
        *extra_args,
    ]
    return subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
