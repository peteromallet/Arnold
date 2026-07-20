"""File-system helpers for ticket frontmatter files.

Every ticket is a single ``.md`` file with YAML frontmatter stored in
``.megaplan/tickets/{ulid}-{slug}.md``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterator

import yaml

from arnold_pipelines.megaplan.artifacts import artifact_dir, slugify as artifact_slugify


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def tickets_dir(repo_root: str | Path) -> Path:
    """Return the ``.megaplan/tickets/`` directory inside *repo_root*."""
    return artifact_dir(repo_root, "tickets")


def slugify(title: str) -> str:
    """Turn *title* into a URL-safe slug (lowercase, hyphen-separated)."""
    return artifact_slugify(title, max_length=80)


# ---------------------------------------------------------------------------
# Frontmatter read / write
# ---------------------------------------------------------------------------

# Fields written to and read from YAML frontmatter.
_FRONTMATTER_FIELDS = [
    "id",
    "title",
    "status",
    "source",
    "tags",
    "filed_by_actor_id",
    "filed_in_turn_id",
    "codebase_id",
    "created_at",
    "last_edited_at",
    "resolution_note",
    "addressed_at",
    "epics",
]


def _serialise_frontmatter(record: dict) -> str:
    """Dump *record* as YAML frontmatter (no ``---`` markers)."""
    out: dict[str, object] = {}
    for k in _FRONTMATTER_FIELDS:
        v = record.get(k)
        if v is None and k in ("resolution_note", "addressed_at", "filed_by_actor_id", "filed_in_turn_id"):
            continue  # omit optional nulls
        if v is None:
            out[k] = None
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return yaml.dump(out, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip()


def _parse_frontmatter(yaml_text: str) -> dict:
    """Parse YAML frontmatter block into a dict.  Returns ``{}`` on empty input."""
    if not yaml_text.strip():
        return {}
    parsed = yaml.safe_load(yaml_text)
    if not isinstance(parsed, dict):
        return {}
    # Convert ISO date strings back to datetime objects
    for date_key in ("created_at", "last_edited_at", "addressed_at"):
        val = parsed.get(date_key)
        if isinstance(val, str):
            try:
                parsed[date_key] = datetime.fromisoformat(val)
            except (ValueError, TypeError):
                pass
    return parsed


def read_ticket_file(path: str | Path) -> dict | None:
    """Read a single ``.md`` ticket file and return its frontmatter dict.
    Returns *None* if the file cannot be read or has no frontmatter.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    # Extract YAML between --- markers
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    fm = _parse_frontmatter(parts[1])
    if not fm:
        return None
    # Attach the markdown body
    fm["__body__"] = parts[2].strip()
    return fm


def write_ticket_file(path: str | Path, record: dict) -> None:
    """Write *record* as a frontmatter ``.md`` file at *path*.

    The ``__body__`` key (if present) is placed after the frontmatter as
    the document body.
    """
    path = Path(path)
    body = record.pop("__body__", "")
    fm = _serialise_frontmatter(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{fm}\n---\n\n{body}\n".lstrip(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Iterate
# ---------------------------------------------------------------------------


def iterate_ticket_files(repo_root: str | Path) -> Iterator[tuple[Path, dict]]:
    """Yield ``(path, frontmatter_dict)`` for every ``.md`` ticket in
    ``.megaplan/tickets/`` under *repo_root*.
    """
    td = tickets_dir(repo_root)
    if not td.is_dir():
        return
    for entry in sorted(td.iterdir()):
        if not entry.suffix == ".md":
            continue
        fm = read_ticket_file(entry)
        if fm is not None:
            yield (entry, fm)


def ticket_file_path(repo_root: str | Path, ulid: str, slug: str) -> Path:
    """Return the expected ``.md`` path for a ticket with given *ulid* and *slug*."""
    return tickets_dir(repo_root) / f"{ulid}-{slug}.md"
