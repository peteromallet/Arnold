"""Canonical local brief/epic artifact helpers."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

from arnold_pipelines.megaplan.artifacts import (
    artifact_dir,
    artifact_title,
    filter_keyword_artifacts,
    iter_markdown_artifacts,
    slugify as artifact_slugify,
    write_markdown_artifact,
)


def slugify(value: str) -> str:
    """Return a stable file-safe slug for a brief or epic name."""
    return artifact_slugify(value, max_length=96, allow_dots=True)


def briefs_dir(repo_root: str | Path) -> Path:
    """Return and create ``.megaplan/briefs/`` inside *repo_root*."""
    return artifact_dir(repo_root, "briefs")


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
    write_markdown_artifact(
        path,
        body,
        metadata={
            "type": "brief",
            "slug": path.stem,
            "title": slug.replace("-", " ").title(),
            "created_at": datetime.now(timezone.utc),
        },
    )
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
        write_markdown_artifact(
            path,
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
            metadata={
                "type": "brief",
                "slug": label,
                "title": title,
                "epic": directory.name,
                "created_at": datetime.now(timezone.utc),
            },
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


def list_briefs(repo_root: str | Path) -> list[dict[str, Any]]:
    """Return canonical brief records under ``.megaplan/briefs``."""
    root = briefs_dir(repo_root)
    records: list[dict[str, Any]] = []
    for artifact in iter_markdown_artifacts(repo_root, "briefs", recursive=True):
        rel = artifact.path.relative_to(root)
        identifier = rel.with_suffix("").as_posix()
        records.append(
            {
                "id": identifier,
                "title": artifact_title(artifact.path, artifact),
                "path": str(artifact.path),
                "relative_path": str(Path(".megaplan") / "briefs" / rel),
                "slug": artifact.path.stem,
                "epic": rel.parts[0] if len(rel.parts) > 1 else None,
                "tags": artifact.metadata.get("tags", []),
                "body": artifact.body,
                "metadata": artifact.metadata,
            }
        )
    return records


def show_brief(repo_root: str | Path, identifier: str) -> dict[str, Any] | None:
    """Return a brief by id, slug, or path."""
    query = identifier.strip()
    query_path = Path(query)
    for record in list_briefs(repo_root):
        candidates = {
            str(record["id"]),
            str(record["slug"]),
            str(record["path"]),
            str(record["relative_path"]),
        }
        if query in candidates:
            return record
        if query_path.suffix == ".md" and query_path.name == Path(str(record["path"])).name:
            return record
    return None


def search_briefs(
    repo_root: str | Path,
    keywords: Sequence[str] | None = None,
    *,
    keywords_all: bool = False,
    sort: str = "path",
    order: str = "asc",
    limit: int | None = None,
    snippet: bool = False,
) -> list[dict[str, Any]]:
    """Search canonical brief records."""
    records = filter_keyword_artifacts(
        list_briefs(repo_root),
        keywords,
        keywords_all=keywords_all,
        fields=("id", "title", "body", "tags", "epic"),
        snippet=snippet,
    )
    if sort not in {"path", "title", "length"}:
        raise ValueError("sort must be one of 'path', 'title', or 'length'")
    if order not in {"asc", "desc"}:
        raise ValueError("order must be 'asc' or 'desc'")
    key = {
        "path": lambda item: str(item.get("relative_path") or ""),
        "title": lambda item: str(item.get("title") or "").lower(),
        "length": lambda item: len(str(item.get("body") or "")),
    }[sort]
    records.sort(key=key, reverse=(order == "desc"))
    if limit is not None:
        records = records[:limit]
    return records


def init_from_brief(
    repo_root: str | Path, path: Path, extra_args: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    """Run ``megaplan init`` against an already-written canonical brief file."""
    command = [
        sys.executable,
        "-m",
        "arnold_pipelines.megaplan",
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
