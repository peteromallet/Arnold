"""Canonical local brief/epic artifact helpers."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

from arnold_pipelines.megaplan.artifacts import (
    artifact_title,
    filter_keyword_artifacts,
    parse_markdown_artifact,
    slugify as artifact_slugify,
    write_markdown_artifact,
)
from arnold_pipelines.megaplan.layout import (
    INITIATIVES_DIR,
    initiative_doc_dir,
    initiative_root,
    initiatives_dir,
)


def slugify(value: str) -> str:
    """Return a stable file-safe slug for a brief or epic name."""
    return artifact_slugify(value, max_length=96, allow_dots=True)


def briefs_dir(repo_root: str | Path) -> Path:
    """Return and create canonical initiative root inside *repo_root*."""
    return initiatives_dir(repo_root)


def brief_path(repo_root: str | Path, slug: str) -> Path:
    """Return the canonical path for a single-plan brief slug."""
    normalized = slugify(slug)
    if not normalized:
        raise ValueError("brief slug must not be empty")
    return initiative_doc_dir(repo_root, normalized, "briefs") / f"{normalized}.md"


def epic_dir(repo_root: str | Path, slug: str) -> Path:
    """Return the canonical directory for an epic's chain and milestone briefs."""
    normalized = slugify(slug)
    if not normalized:
        raise ValueError("epic slug must not be empty")
    return initiative_root(repo_root, normalized)


def write_single_brief(
    repo_root: str | Path,
    slug: str,
    body: str,
    *,
    force: bool = False,
) -> Path:
    """Write a single-plan brief under ``.megaplan/initiatives/<slug>/briefs``."""
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


def default_initiative_description(slug: str) -> str:
    """Return an explicit template marker for a new initiative description."""
    title = slug.replace("-", " ").title()
    return (
        f"TODO_INITIATIVE_DESCRIPTION: Describe the outcome for {title}, "
        "why it matters, and the boundary of the work."
    )


def scaffold_epic(
    repo_root: str | Path,
    slug: str,
    milestones: Sequence[str],
    *,
    base_branch: str = "main",
    merge_policy: str = "auto",
    branch_prefix: str | None = None,
    profile: str = "partnered-5",
    vendor: str = "codex",
    robustness: str = "full",
    depth: str = "high",
    with_prep: bool = True,
    force: bool = False,
) -> tuple[Path, list[Path]]:
    """Create ``.megaplan/initiatives/<epic>/chain.yaml`` and milestone stubs."""
    if not milestones:
        raise ValueError("at least one --milestone is required")
    directory = epic_dir(repo_root, slug)
    directory.mkdir(parents=True, exist_ok=True)

    parsed = [_parse_milestone(item) for item in milestones]
    written: list[Path] = []
    north_star_path = directory / "NORTHSTAR.md"
    if north_star_path.exists() and not force:
        raise FileExistsError(north_star_path)
    write_markdown_artifact(
        north_star_path,
        _default_north_star_template(slug),
        metadata={
            "type": "anchor",
            "anchor_type": "north_star",
            "slug": slug,
            "title": f"North Star: {slug.replace('-', ' ').title()}",
            "created_at": datetime.now(timezone.utc),
        },
    )
    written.append(north_star_path)
    normalized_slug = directory.name
    prefix = (branch_prefix or f"megaplan/{normalized_slug}").strip().rstrip("/")
    chain_milestones: list[dict[str, Any]] = []
    for label, title in parsed:
        path = directory / "briefs" / f"{label}.md"
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
        milestone: dict[str, Any] = {
            "label": label,
            "idea": str(path.relative_to(repo_root)),
            "branch": f"{prefix}/{label}",
            "profile": profile,
            "vendor": vendor,
            "robustness": robustness,
            "depth": depth,
        }
        if with_prep:
            milestone["with_prep"] = True
        chain_milestones.append(milestone)

    chain_path = directory / "chain.yaml"
    if chain_path.exists() and not force:
        raise FileExistsError(chain_path)
    chain_path.write_text(
        yaml.safe_dump(
            {
                "base_branch": base_branch,
                "anchors": {"north_star": "NORTHSTAR.md"},
                "milestones": chain_milestones,
                "on_failure": {"abort": "stop_chain"},
                "on_escalate": {"abort": "stop_chain"},
                "merge_policy": merge_policy,
                "driver": {
                    "robustness": robustness,
                    "phase_timeout": 10800,
                    "auto_approve": merge_policy == "auto",
                    "on_escalate": "abort",
                    "max_iterations": 60,
                    "poll_sleep": 8.0,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return chain_path, written


def write_initiative_cloud_yaml(
    repo_root: str | Path,
    slug: str,
    *,
    base_branch: str = "main",
    force: bool = False,
    repo_url: str | None = None,
    chain_session: str | None = None,
    provider: str = "ssh",
) -> Path:
    """Write an initiative-local cloud.yaml with explicit edit-before-launch markers."""
    directory = epic_dir(repo_root, slug)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "cloud.yaml"
    if path.exists() and not force:
        raise FileExistsError(path)
    normalized_slug = directory.name
    payload = {
        "provider": provider,
        "repo": {
            "url": repo_url or "TODO_REPO_URL",
            "branch": base_branch,
        },
        "agents": {"default": "codex"},
        "codex": {"model": "gpt-5.6-sol", "reasoning": "medium"},
        "mode": "idle",
        "chain": {"spec": f"/workspace/{normalized_slug}/chain.yaml"},
        "megaplan": {
            "ref": "editible-install",
            "codex_auth": "chatgpt",
            "repo": "https://github.com/peteromallet/Arnold.git",
            "src_path": "/workspace/arnold",
        },
        "resources": {"volume": "agent-volume", "port": 8080},
        "ssh": {
            "host": "TODO_SSH_HOST",
            "user": "root",
            "port": 22,
            "remote_dir": "/opt/megaplan-cloud/deploy",
            "workspace_dir": "/opt/megaplan-cloud/workspace",
            "container": "megaplan-cloud-agent",
        },
        "chain_session": chain_session or normalized_slug,
        "secrets": [],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _default_north_star_template(slug: str) -> str:
    title = slug.replace("-", " ").title()
    return "\n".join(
        [
            f"# North Star: {title}",
            "",
            "## End State",
            "",
            "TODO_NORTH_STAR_END_STATE: Describe the durable destination every milestone must preserve.",
            "",
            "## Non-Negotiables",
            "",
            "TODO_NORTH_STAR_NON_NEGOTIABLES: List invariants the chain must not violate.",
            "",
            "## Explicit Non-Goals",
            "",
            "TODO_NORTH_STAR_NON_GOALS: Name tempting work that is intentionally out of scope.",
            "",
            "## Allowed Temporary Bridges",
            "",
            "TODO_NORTH_STAR_TEMPORARY_BRIDGES: Describe any acceptable short-lived compromises.",
            "",
            "## Drift Signals",
            "",
            "TODO_NORTH_STAR_DRIFT_SIGNALS: List signs the chain is solving the wrong problem.",
            "",
        ]
    )


def list_briefs(repo_root: str | Path) -> list[dict[str, Any]]:
    """Return canonical brief records under ``.megaplan/initiatives``."""
    root = Path(repo_root) / INITIATIVES_DIR
    records: list[dict[str, Any]] = []
    if not root.exists():
        return records
    for artifact in sorted(root.rglob("briefs/*.md")):
        parsed = parse_markdown_artifact(artifact)
        if parsed is None:
            continue
        rel = artifact.relative_to(root)
        identifier = rel.with_suffix("").as_posix()
        records.append(
            {
                "id": identifier,
                "title": artifact_title(parsed.path, parsed),
                "path": str(parsed.path),
                "relative_path": str(INITIATIVES_DIR / rel),
                "slug": parsed.path.stem,
                "epic": rel.parts[0] if len(rel.parts) > 1 else None,
                "tags": parsed.metadata.get("tags", []),
                "body": parsed.body,
                "metadata": parsed.metadata,
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
