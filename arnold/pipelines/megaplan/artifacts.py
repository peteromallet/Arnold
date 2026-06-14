"""Shared local artifact helpers for files under ``.megaplan/``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import yaml


@dataclass(frozen=True)
class MarkdownArtifact:
    """Parsed markdown artifact with optional YAML frontmatter."""

    path: Path
    metadata: dict[str, Any]
    body: str


def slugify(value: str, *, max_length: int = 80, allow_dots: bool = False) -> str:
    """Return a stable file-safe slug."""
    slug = value.lower().strip()
    pattern = r"[^\w\s.-]" if allow_dots else r"[^\w\s-]"
    slug = re.sub(pattern, "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip(".-" if allow_dots else "-")[:max_length]


def artifact_dir(repo_root: str | Path, kind: str) -> Path:
    """Return and create ``.megaplan/<kind>/`` inside *repo_root*."""
    path = Path(repo_root) / ".megaplan" / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_markdown_artifact(path: str | Path) -> MarkdownArtifact | None:
    """Read a markdown artifact, parsing optional YAML frontmatter."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    metadata: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            parsed = yaml.safe_load(parts[1]) if parts[1].strip() else {}
            if isinstance(parsed, dict):
                metadata = parsed
                body = parts[2]

    return MarkdownArtifact(path=path, metadata=metadata, body=body.strip())


def markdown_body(path: str | Path) -> str:
    """Return a markdown artifact body, stripping frontmatter when present."""
    artifact = parse_markdown_artifact(path)
    return artifact.body if artifact is not None else ""


def write_markdown_artifact(
    path: str | Path,
    body: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Write a markdown artifact with optional YAML frontmatter."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = body.strip()
    if metadata:
        frontmatter = yaml.dump(
            _serializable_metadata(metadata),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
        text = f"---\n{frontmatter}\n---\n\n{body}\n"
    else:
        text = f"{body}\n"
    path.write_text(text, encoding="utf-8")


def iter_markdown_artifacts(
    repo_root: str | Path,
    kind: str,
    *,
    recursive: bool = False,
) -> Iterator[MarkdownArtifact]:
    """Yield parsed markdown artifacts under ``.megaplan/<kind>/``."""
    root = artifact_dir(repo_root, kind)
    entries = root.rglob("*.md") if recursive else root.glob("*.md")
    for path in sorted(entries):
        if ".megaplan" in path.relative_to(root).parts:
            continue
        artifact = parse_markdown_artifact(path)
        if artifact is not None:
            yield artifact


def artifact_title(path: Path, artifact: MarkdownArtifact) -> str:
    """Return metadata title, first markdown heading, or filename stem."""
    raw_title = artifact.metadata.get("title")
    if isinstance(raw_title, str) and raw_title.strip():
        return raw_title.strip()
    for line in artifact.body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem.replace("-", " ").title()


def filter_keyword_artifacts(
    records: Sequence[dict[str, Any]],
    keywords: Sequence[str] | None = None,
    *,
    keywords_all: bool = False,
    fields: Sequence[str] = ("title", "body", "tags"),
    snippet: bool = False,
    snippet_width: int = 120,
) -> list[dict[str, Any]]:
    """Filter artifact records by case-insensitive substring keywords."""
    kw_list = [kw.lower() for kw in (keywords or []) if kw]
    if not kw_list:
        return list(records)
    out: list[dict[str, Any]] = []
    for record in records:
        haystack_parts: list[str] = []
        for field in fields:
            value = record.get(field)
            if isinstance(value, list):
                haystack_parts.append(" ".join(str(item) for item in value))
            elif value is not None:
                haystack_parts.append(str(value))
        haystack = "\n".join(haystack_parts).lower()
        matches = [kw in haystack for kw in kw_list]
        if keywords_all and not all(matches):
            continue
        if not keywords_all and not any(matches):
            continue
        item = dict(record)
        if snippet:
            item["snippet"] = make_snippet(
                str(record.get("body") or ""),
                str(record.get("title") or ""),
                kw_list,
                snippet_width,
            )
        out.append(item)
    return out


def make_snippet(body: str, title: str, keywords: Sequence[str], width: int = 120) -> str:
    """Return a single-line snippet centered on the first keyword hit."""
    text = (title + " - " + body) if body else title
    flat = " ".join(text.split())
    low = flat.lower()
    idx = -1
    for kw in keywords:
        i = low.find(kw.lower())
        if i >= 0 and (idx < 0 or i < idx):
            idx = i
    if idx < 0:
        return flat[:width] + ("..." if len(flat) > width else "")
    half = width // 2
    start = max(0, idx - half)
    end = min(len(flat), start + width)
    result = flat[start:end]
    if start > 0:
        result = "..." + result
    if end < len(flat):
        result = result + "..."
    return result


def _serializable_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out
