"""File-system helpers for ticket frontmatter files.

Every ticket is a single ``.md`` file with YAML frontmatter stored in
``.megaplan/tickets/{ulid}-{slug}.md``.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal

import yaml

from arnold_pipelines.megaplan.artifacts import artifact_dir, slugify as artifact_slugify

# ---------------------------------------------------------------------------
# ULID validation
# ---------------------------------------------------------------------------

# ULIDs are 26 characters of Crockford base32 (I, L, O, U excluded).
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def is_valid_ulid(value: str) -> bool:
    """Return *True* if *value* is a well-formed 26-character Crockford-base32 ULID."""
    return bool(_ULID_RE.match(value))


# ---------------------------------------------------------------------------
# Filename prefix shape classification
# ---------------------------------------------------------------------------

# Canonical ticket filenames follow ``{ulid}-{slug}.md``.
# The prefix is everything before the first hyphen.

FilenamePrefixShape = Literal["valid-ulid", "invalid-ulid", "non-ulid"]
"""Classification of a ticket filename's prefix segment.

``valid-ulid``:    the prefix matches the ULID regex.
``invalid-ulid``:  the prefix is 26 uppercase-alphanum chars but fails ULID (contains I/L/O/U).
``non-ulid``:      the prefix is anything else (non-canonical filename).
"""


def classify_filename_prefix(filename: str) -> FilenamePrefixShape:
    """Classify the prefix segment of a ticket *filename*.

    A canonical ticket file is ``{ulid}-{slug}.md``.  The prefix is the
    substring before the first ``-`` (or the whole stem if no hyphen).

    Returns one of ``"valid-ulid"``, ``"invalid-ulid"``, or ``"non-ulid"``.
    """
    stem = Path(filename).stem
    prefix = stem.split("-", 1)[0] if "-" in stem else stem

    if not prefix:
        return "non-ulid"

    # Quick length check before running the regex.
    if len(prefix) != 26:
        return "non-ulid"

    if _ULID_RE.match(prefix):
        return "valid-ulid"

    # 26 chars that look like base32 but contain I/L/O/U → invalid-ulid.
    if re.match(r"^[0-9A-Z]{26}$", prefix):
        return "invalid-ulid"

    return "non-ulid"


# ---------------------------------------------------------------------------
# Low-level parse helper with error reporting
# ---------------------------------------------------------------------------


def read_ticket_frontmatter_with_errors(
    path: str | Path,
) -> tuple[dict | None, list[str]]:
    """Read ticket frontmatter, returning ``(frontmatter_dict, errors)``.

    Unlike :func:`read_ticket_file`, which silently returns *None* on any
    problem, this returns a list of human-readable error strings suitable
    for inventory/diagnostic reporting.

    Returns
    -------
    (dict | None, list[str])
        The frontmatter dict (or *None* if unrecoverable) and a list of
        parse error messages (empty when the read was clean).
    """
    path = Path(path)
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"cannot read file: {exc}"]

    # Extract YAML between --- markers
    parts = text.split("---", 2)
    if len(parts) < 3:
        errors.append("no YAML frontmatter fences found (expected opening and closing '---')")
        return None, errors

    fm_text = parts[1]
    if not fm_text.strip():
        errors.append("empty YAML frontmatter block")
        return None, errors

    try:
        parsed = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        errors.append(f"YAML parse error in frontmatter: {exc}")
        return None, errors

    if not isinstance(parsed, dict):
        errors.append("frontmatter did not parse as a YAML mapping")
        return None, errors

    # Convert ISO date strings back to datetime objects (same logic as
    # _parse_frontmatter).
    for date_key in ("created_at", "last_edited_at", "addressed_at"):
        val = parsed.get(date_key)
        if isinstance(val, str):
            try:
                parsed[date_key] = datetime.fromisoformat(val)
            except (ValueError, TypeError):
                errors.append(
                    f"invalid date format for '{date_key}': {val!r}"
                )

    # Attach the markdown body.
    parsed["__body__"] = parts[2].strip()
    return parsed, errors


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
