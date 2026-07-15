"""Canonical knowledge lifecycle and bounded resident activity context.

The hot context is an orientation surface, not an artifact store.  This module
reads the existing ticket files and durable document locations, retains UTC
timestamps while selecting recent activity, and emits a name-only summary.
Detailed inventories remain available through the resident context routes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
from typing import Any, Literal, Mapping, Sequence

import yaml

from arnold_pipelines.megaplan.layout import (
    ALLOWED_INITIATIVE_SUBDIRS,
    INITIATIVES_DIR,
    ROOT_INITIATIVE_FILES,
    initiative_metadata,
)
from arnold_pipelines.megaplan.tickets.files import (
    read_ticket_frontmatter_with_errors,
)


RECENT_ACTIVITY_SCHEMA = "megaplan-resident-knowledge-activity-v1"
RECENT_ACTIVITY_WINDOW = timedelta(hours=1)
RECENT_ACTIVITY_LIMIT = 8
MAX_TICKET_CONTEXT_RECORDS = 500
MAX_DOCUMENT_CONTEXT_RECORDS = 1_000

DOCUMENT_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".adoc", ".txt"})
ROOT_DOCUMENT_NAMES = frozenset(
    {
        "AGENTS.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "README.md",
        "SECURITY.md",
    }
)

# These locations are generated state, caches, raw execution output, or other
# churn.  Their mtimes must never make a document or initiative permanently
# recent.  Initiative-local admission is handled separately below.
EXCLUDED_TOP_LEVEL_PARTS = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)
RAW_INITIATIVE_OUTPUT_PARTS = frozenset(
    {
        "subagent-results",
        "run-output",
    }
)
CHURN_DOCUMENT_NAMES = frozenset(
    {
        "current.md",
        "current-state.md",
        "heartbeat.md",
        "progress.md",
        "run-log.md",
        "runtime-state.md",
        "state.md",
        "status.md",
        "wait-log.md",
    }
)


KNOWLEDGE_LIFECYCLE: dict[str, Any] = {
    "schema_version": "megaplan-knowledge-lifecycle-v1",
    "categories": {
        "document": {
            "label": "Document — exploratory or durable knowledge, not execution approval",
            "meaning": (
                "A speculative, exploratory, or durable knowledge artifact. Its existence does not "
                "commit anyone to execute work."
            ),
            "create_or_update": (
                "Create or update a document when the value is knowledge, evidence, a decision, a note, "
                "or a handoff; curate agent/subagent findings into a canonical document and cite raw runs."
            ),
            "location": (
                "Use the repository's established docs location, or the matching initiative's research/, "
                "decisions/, notes/, handoff/, or assets/ directory. Planning briefs belong only under "
                ".megaplan/initiatives/<slug>/briefs/."
            ),
            "promote_when": (
                "Promote a specific unresolved problem or opportunity to a ticket; promote to an initiative "
                "only after a coherent outcome is committed."
            ),
        },
        "ticket": {
            "label": "Ticket — addressable problem or opportunity, not yet a coordinated plan",
            "meaning": (
                "A specific problem, opportunity, or idea that probably should be addressed but is not yet "
                "a coordinated actionable plan."
            ),
            "create_or_update": (
                "Create a ticket for a bounded addressable item; update the same ticket as evidence or scope "
                "sharpens instead of duplicating it."
            ),
            "location": ".megaplan/tickets/<ulid>-<slug>.md via the supported ticket CLI.",
            "promote_when": (
                "Promote to an initiative when the outcome is committed and needs boundaries, success "
                "criteria, or coordinated workstreams; preserve the ticket relationship."
            ),
        },
        "initiative": {
            "label": "Initiative — committed coherent outcome, planning/execution may follow",
            "meaning": (
                "A committed coherent outcome with boundaries and success criteria, likely spanning one or "
                "more workstreams. Detailed planning or chain execution may come later."
            ),
            "create_or_update": (
                "Search rough slug, title, and description first; reuse and update a matching initiative. "
                "Create one only when no match exists and commitment to the outcome is clear."
            ),
            "location": (
                ".megaplan/initiatives/<slug>/ with README.md as the front door/current truth and canonical "
                "index; briefs/, research/, decisions/, notes/, handoff/, and assets/ are canonical. "
                "NORTHSTAR.md and chain.yaml are optional readiness artifacts."
            ),
            "promote_when": (
                "Add NORTHSTAR.md when durable end-state constraints need their own anchor; add chain.yaml "
                "only when coordinated execution is actually ready. Initiative creation alone never launches work."
            ),
        },
    },
    "reuse_and_navigation": (
        "Before creating anything, search existing initiatives, tickets, and related documents; reuse the "
        "closest canonical record and build on it. Hot context is a bounded recent orientation, not the "
        "database: follow the tickets, initiatives, documents, and policies routes or scoped search for full records."
    ),
}


ActivityChange = Literal["added", "edited"]


@dataclass(frozen=True)
class ActivityEvent:
    """Internal UTC activity evidence used to build the name-only hot view."""

    identity: str
    name: str
    occurred_at: datetime
    change: ActivityChange
    path: str
    initiative_slug: str | None = None

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("activity timestamps must be timezone-aware UTC values")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(timezone.utc))


@dataclass(frozen=True)
class KnowledgeContext:
    """Bounded hot summary plus route inventories."""

    recent_activity: dict[str, Any]
    tickets: tuple[dict[str, Any], ...]
    documents: tuple[dict[str, Any], ...]


def build_knowledge_context(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
    window: timedelta = RECENT_ACTIVITY_WINDOW,
    limit: int = RECENT_ACTIVITY_LIMIT,
) -> KnowledgeContext:
    """Read canonical artifacts and build deterministic resident context.

    The exact lower boundary is inclusive and future timestamps are excluded.
    Malformed ticket records and malformed explicit document timestamps fail
    closed: they are not included in either the detailed inventory or hot view.
    """

    root = Path(repo_root).expanduser().resolve()
    observed_at = _utc(now or datetime.now(timezone.utc))
    if window <= timedelta(0):
        raise ValueError("recent activity window must be positive")
    if limit < 1:
        raise ValueError("recent activity limit must be positive")
    cutoff = observed_at - window
    git_activity, dirty_activity, tracked = _git_activity(root, cutoff=cutoff, now=observed_at)

    ticket_rows, ticket_events = _ticket_context(root)
    document_rows, document_events = _document_context(
        root,
        git_activity=git_activity,
        dirty_activity=dirty_activity,
        tracked=tracked,
    )

    recent_tickets = _within_window(ticket_events, cutoff=cutoff, now=observed_at)
    recent_documents = _within_window(document_events, cutoff=cutoff, now=observed_at)
    initiative_events = _initiative_events(root, recent_documents)
    recent_initiatives = _within_window(initiative_events, cutoff=cutoff, now=observed_at)

    summary = {
        "schema_version": RECENT_ACTIVITY_SCHEMA,
        "window": "preceding rolling hour (inclusive lower boundary)",
        "tickets_added_or_edited": _name_bucket(
            "Tickets added or edited in the preceding rolling hour",
            recent_tickets,
            limit=limit,
        ),
        "initiatives_added_or_edited": _name_bucket(
            "Initiatives added or edited in the preceding rolling hour",
            recent_initiatives,
            limit=limit,
        ),
        "documents_added_or_edited": _name_bucket(
            "Documents added or edited in the preceding rolling hour",
            recent_documents,
            limit=limit,
        ),
    }
    return KnowledgeContext(
        recent_activity=summary,
        tickets=tuple(ticket_rows[:MAX_TICKET_CONTEXT_RECORDS]),
        documents=tuple(document_rows[:MAX_DOCUMENT_CONTEXT_RECORDS]),
    )


def _ticket_context(root: Path) -> tuple[list[dict[str, Any]], list[ActivityEvent]]:
    base = root / ".megaplan" / "tickets"
    if not base.is_dir():
        return [], []
    rows: list[dict[str, Any]] = []
    events: list[ActivityEvent] = []
    for path in sorted(base.glob("*.md")):
        frontmatter, errors = read_ticket_frontmatter_with_errors(path)
        if errors or not isinstance(frontmatter, Mapping):
            continue
        ticket_id = frontmatter.get("id")
        title = frontmatter.get("title")
        status = frontmatter.get("status")
        created_at = _strict_timestamp(frontmatter.get("created_at"))
        edited_at = _strict_timestamp(frontmatter.get("last_edited_at"))
        tags = frontmatter.get("tags") or []
        if not all((isinstance(ticket_id, str), isinstance(title, str), isinstance(status, str))):
            continue
        if (
            not ticket_id.strip()
            or not title.strip()
            or created_at is None
            or edited_at is None
            or not isinstance(tags, list)
            or not all(isinstance(tag, str) for tag in tags)
        ):
            continue
        rel = path.relative_to(root).as_posix()
        rows.append(
            {
                "id": ticket_id,
                "title": title.strip(),
                "status": status,
                "tags": list(tags),
                "created_at": _iso_utc(created_at),
                "last_edited_at": _iso_utc(edited_at),
                "path": rel,
                "detail_route": f"tickets/{ticket_id}",
            }
        )
        events.extend(
            (
                ActivityEvent(ticket_id, title.strip(), created_at, "added", rel),
                ActivityEvent(ticket_id, title.strip(), edited_at, "edited", rel),
            )
        )
    rows.sort(key=lambda row: (row["last_edited_at"], row["id"]), reverse=True)
    return rows, events


def _document_context(
    root: Path,
    *,
    git_activity: Mapping[str, tuple[datetime, ActivityChange]],
    dirty_activity: Mapping[str, tuple[datetime, ActivityChange]],
    tracked: frozenset[str],
) -> tuple[list[dict[str, Any]], list[ActivityEvent]]:
    rows: list[dict[str, Any]] = []
    events: list[ActivityEvent] = []
    for path in _iter_document_paths(root):
        rel = path.relative_to(root).as_posix()
        explicit = _document_frontmatter_events(path)
        if explicit is None:
            continue
        initiative_slug = _initiative_slug_for_path(rel)
        path_events: list[tuple[datetime, ActivityChange]] = list(explicit)
        if rel in git_activity:
            path_events.append(git_activity[rel])
        if rel in dirty_activity:
            path_events.append(dirty_activity[rel])
        if rel not in tracked and rel not in dirty_activity:
            try:
                path_events.append((_utc_from_timestamp(path.stat().st_mtime), "edited"))
            except OSError:
                continue
        rows.append(
            {
                "name": rel,
                "path": rel,
                "kind": _document_kind(rel),
                "initiative_slug": initiative_slug,
                "detail_route": (
                    f"initiatives/{initiative_slug}" if initiative_slug else "documents"
                ),
            }
        )
        for occurred_at, change in path_events:
            events.append(
                ActivityEvent(
                    identity=rel,
                    name=rel,
                    occurred_at=occurred_at,
                    change=change,
                    path=rel,
                    initiative_slug=initiative_slug,
                )
            )
    rows.sort(key=lambda row: row["path"])
    return rows, events


def _iter_document_paths(root: Path) -> Sequence[Path]:
    candidates: set[Path] = set()
    for name in ROOT_DOCUMENT_NAMES:
        path = root / name
        if path.is_file():
            candidates.add(path)
    docs = root / "docs"
    if docs.is_dir():
        candidates.update(path for path in docs.rglob("*") if path.is_file())
    initiatives = root / INITIATIVES_DIR
    if initiatives.is_dir():
        candidates.update(path for path in initiatives.rglob("*") if path.is_file())
    return sorted(path for path in candidates if is_durable_document_path(path, root))


def is_durable_document_path(path: str | Path, repo_root: str | Path) -> bool:
    """Return whether *path* is an admitted durable, non-state document."""

    root = Path(repo_root).expanduser().resolve()
    candidate = Path(path).expanduser().resolve()
    try:
        rel = candidate.relative_to(root)
    except ValueError:
        return False
    if not candidate.is_file() or candidate.suffix.casefold() not in DOCUMENT_SUFFIXES:
        return False
    if candidate.name.casefold() in CHURN_DOCUMENT_NAMES:
        return False
    parts = rel.parts
    if not parts or any(part in EXCLUDED_TOP_LEVEL_PARTS for part in parts):
        return False
    if len(parts) == 1:
        return parts[0] in ROOT_DOCUMENT_NAMES
    if parts[0] == "docs":
        return True
    if parts[:2] != INITIATIVES_DIR.parts or len(parts) < 4:
        return False
    initiative_rel = parts[3:]
    if any(part in RAW_INITIATIVE_OUTPUT_PARTS for part in initiative_rel):
        return False
    if len(parts) == 4:
        return parts[3] in ROOT_INITIATIVE_FILES and parts[3] != "chain.yaml"
    return parts[3] in ALLOWED_INITIATIVE_SUBDIRS


def _initiative_events(root: Path, document_events: Sequence[ActivityEvent]) -> list[ActivityEvent]:
    newest: dict[str, ActivityEvent] = {}
    for event in document_events:
        slug = event.initiative_slug
        if not slug:
            continue
        current = newest.get(slug)
        if current is None or _event_sort_key(event) > _event_sort_key(current):
            newest[slug] = event
    out: list[ActivityEvent] = []
    for slug, event in newest.items():
        try:
            metadata = initiative_metadata(root, slug)
        except (OSError, ValueError):
            continue
        if metadata.get("retired"):
            continue
        title = metadata.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        out.append(
            ActivityEvent(
                identity=slug,
                name=title.strip(),
                occurred_at=event.occurred_at,
                change=event.change,
                path=f".megaplan/initiatives/{slug}",
                initiative_slug=slug,
            )
        )
    return out


def _document_frontmatter_events(
    path: Path,
) -> list[tuple[datetime, ActivityChange]] | None:
    try:
        with path.open("r", encoding="utf-8") as stream:
            first = stream.readline()
            if first.strip() != "---":
                return []
            lines: list[str] = []
            for _ in range(200):
                line = stream.readline()
                if not line:
                    return None
                if line.strip() == "---":
                    break
                lines.append(line)
            else:
                return None
    except (OSError, UnicodeDecodeError):
        return None
    try:
        payload = yaml.safe_load("".join(lines)) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(payload, Mapping):
        return None
    events: list[tuple[datetime, ActivityChange]] = []
    for key, change in (
        ("created_at", "added"),
        ("last_edited_at", "edited"),
        ("updated_at", "edited"),
        ("edited_at", "edited"),
    ):
        if key not in payload:
            continue
        parsed = _strict_timestamp(payload.get(key))
        if parsed is None:
            return None
        events.append((parsed, change))
    return events


def _git_activity(
    root: Path,
    *,
    cutoff: datetime,
    now: datetime,
) -> tuple[
    dict[str, tuple[datetime, ActivityChange]],
    dict[str, tuple[datetime, ActivityChange]],
    frozenset[str],
]:
    if not (root / ".git").exists() and not _run_git(root, "rev-parse", "--git-dir"):
        return {}, {}, frozenset()
    tracked_output = _run_git(root, "ls-files", "-z")
    tracked = frozenset(part for part in tracked_output.split("\0") if part)
    committed: dict[str, tuple[datetime, ActivityChange]] = {}
    log = _run_git(
        root,
        "log",
        # Ask Git for a one-second superset, then apply the exact inclusive
        # boundary to parsed UTC timestamps below. This avoids Git's
        # second-resolution date parser dropping an exact-boundary commit.
        f"--since={_iso_utc(cutoff - timedelta(seconds=1))}",
        f"--until={_iso_utc(now)}",
        "--format=@@%cI",
        "--name-status",
        "--diff-filter=AM",
        "--",
    )
    commit_time: datetime | None = None
    for line in log.splitlines():
        if line.startswith("@@"):
            commit_time = _strict_timestamp(line[2:])
            continue
        if not line.strip() or commit_time is None:
            continue
        status, separator, rel = line.partition("\t")
        if not separator or status not in {"A", "M"}:
            continue
        change: ActivityChange = "added" if status == "A" else "edited"
        existing = committed.get(rel)
        if existing is None or commit_time > existing[0]:
            committed[rel] = (commit_time, change)

    dirty: dict[str, tuple[datetime, ActivityChange]] = {}
    status_output = _run_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    for entry in status_output.split("\0"):
        if len(entry) < 4:
            continue
        code = entry[:2]
        rel = entry[3:]
        path = root / rel
        if not path.is_file():
            continue
        try:
            occurred_at = _utc_from_timestamp(path.stat().st_mtime)
        except OSError:
            continue
        change = "added" if code == "??" or "A" in code else "edited"
        dirty[rel] = (occurred_at, change)
    return committed, dirty, tracked


def _run_git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def _within_window(
    events: Sequence[ActivityEvent],
    *,
    cutoff: datetime,
    now: datetime,
) -> list[ActivityEvent]:
    return [event for event in events if cutoff <= event.occurred_at <= now]


def _name_bucket(label: str, events: Sequence[ActivityEvent], *, limit: int) -> dict[str, Any]:
    # Identity first prevents added+edited evidence for the same artifact from
    # duplicating it. Name folding then prevents an ambiguous name-only payload
    # when distinct legacy identities share the same display name. Newest wins.
    newest_by_identity: dict[str, ActivityEvent] = {}
    for event in events:
        current = newest_by_identity.get(event.identity)
        if current is None or _event_sort_key(event) > _event_sort_key(current):
            newest_by_identity[event.identity] = event
    ordered = sorted(newest_by_identity.values(), key=_event_sort_key, reverse=True)
    unique_names: list[str] = []
    seen_names: set[str] = set()
    for event in ordered:
        key = " ".join(event.name.split()).casefold()
        if not key or key in seen_names:
            continue
        seen_names.add(key)
        unique_names.append(event.name)
    visible = unique_names[:limit]
    return {
        "label": label,
        "names": visible,
        "omitted_count": max(0, len(unique_names) - len(visible)),
    }


def _event_sort_key(event: ActivityEvent) -> tuple[datetime, str, str]:
    return (event.occurred_at, event.name.casefold(), event.identity)


def _initiative_slug_for_path(rel: str) -> str | None:
    parts = Path(rel).parts
    if len(parts) >= 4 and parts[:2] == INITIATIVES_DIR.parts:
        return parts[2]
    return None


def _document_kind(rel: str) -> str:
    parts = Path(rel).parts
    if len(parts) >= 5 and parts[:2] == INITIATIVES_DIR.parts:
        return parts[3]
    if len(parts) >= 4 and parts[:2] == INITIATIVES_DIR.parts:
        return "initiative_index" if parts[3] == "README.md" else "initiative_anchor"
    if parts and parts[0] == "docs":
        return "repository_documentation"
    return "repository_front_door"


def _strict_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return _utc(parsed)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_from_timestamp(value: float) -> datetime:
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _iso_utc(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


__all__ = [
    "DOCUMENT_SUFFIXES",
    "KNOWLEDGE_LIFECYCLE",
    "KnowledgeContext",
    "RECENT_ACTIVITY_LIMIT",
    "RECENT_ACTIVITY_SCHEMA",
    "RECENT_ACTIVITY_WINDOW",
    "build_knowledge_context",
    "is_durable_document_path",
]
