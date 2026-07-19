from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess

from arnold_pipelines.megaplan.resident.context_tree import POLICY_PACKS, build_context_root
from arnold_pipelines.megaplan.resident.knowledge_context import (
    CAUSAL_DOCUMENTS_OVERALL_LIMIT,
    CAUSAL_DOCUMENTS_PER_INITIATIVE_LIMIT,
    KNOWLEDGE_LIFECYCLE,
    build_knowledge_context,
    is_durable_document_path,
)


NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _write_ticket(
    root: Path,
    *,
    ticket_id: str,
    title: str,
    created_at: datetime,
    edited_at: datetime,
) -> Path:
    path = root / ".megaplan" / "tickets" / f"{ticket_id}-ticket.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: {ticket_id}\n"
        f"title: {title}\n"
        "status: open\n"
        "source: human\n"
        "tags: []\n"
        "codebase_id: null\n"
        f"created_at: {_timestamp(created_at)}\n"
        f"last_edited_at: {_timestamp(edited_at)}\n"
        "epics: []\n"
        "---\n\n"
        "Ticket body.\n",
        encoding="utf-8",
    )
    return path


def _write_document(path: Path, *, created_at: datetime | None = None, edited_at: datetime | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = ""
    if created_at is not None or edited_at is not None:
        lines = ["---"]
        if created_at is not None:
            lines.append(f"created_at: {_timestamp(created_at)}")
        if edited_at is not None:
            lines.append(f"last_edited_at: {_timestamp(edited_at)}")
        lines.append("---")
        frontmatter = "\n".join(lines) + "\n\n"
    path.write_text(frontmatter + f"# {path.stem}\n", encoding="utf-8")
    return path


def _set_mtime(path: Path, value: datetime) -> None:
    timestamp = value.timestamp()
    os.utime(path, (timestamp, timestamp))


def _names(context, category: str) -> list[str]:
    return context.recent_activity[category]["names"]


def test_ticket_added_and_edited_events_use_inclusive_one_hour_boundary(tmp_path: Path) -> None:
    old = NOW - timedelta(days=1)
    boundary = NOW - timedelta(hours=1)
    before = boundary - timedelta(microseconds=1)
    _write_ticket(
        tmp_path,
        ticket_id="01AAAAAAAAAAAAAAAAAAAAAAAA",
        title="Created at boundary",
        created_at=boundary,
        edited_at=old,
    )
    _write_ticket(
        tmp_path,
        ticket_id="01BBBBBBBBBBBBBBBBBBBBBBBB",
        title="Edited recently",
        created_at=old,
        edited_at=NOW - timedelta(minutes=2),
    )
    _write_ticket(
        tmp_path,
        ticket_id="01CCCCCCCCCCCCCCCCCCCCCCCC",
        title="Just outside",
        created_at=before,
        edited_at=before,
    )
    _write_ticket(
        tmp_path,
        ticket_id="01DDDDDDDDDDDDDDDDDDDDDDDD",
        title="Future record",
        created_at=NOW + timedelta(seconds=1),
        edited_at=NOW + timedelta(seconds=1),
    )

    context = build_knowledge_context(tmp_path, now=NOW)

    assert _names(context, "tickets_added_or_edited") == [
        "Edited recently",
        "Created at boundary",
    ]


def test_malformed_ticket_fails_closed_and_name_only_output_deduplicates(tmp_path: Path) -> None:
    recent = NOW - timedelta(minutes=5)
    old = NOW - timedelta(days=2)
    _write_ticket(
        tmp_path,
        ticket_id="01AAAAAAAAAAAAAAAAAAAAAAAA",
        title="Same title",
        created_at=recent,
        edited_at=recent,
    )
    _write_ticket(
        tmp_path,
        ticket_id="01BBBBBBBBBBBBBBBBBBBBBBBB",
        title="Same title",
        created_at=old,
        edited_at=NOW - timedelta(minutes=1),
    )
    malformed = tmp_path / ".megaplan" / "tickets" / "malformed.md"
    malformed.write_text("---\nid: broken\ntitle: Broken\ncreated_at: not-utc\n---\n", encoding="utf-8")

    context = build_knowledge_context(tmp_path, now=NOW)
    bucket = context.recent_activity["tickets_added_or_edited"]

    assert bucket["names"] == ["Same title"]
    assert all(row["title"] != "Broken" for row in context.tickets)
    rendered = json.dumps(context.recent_activity)
    assert "2026-" not in rendered
    assert "created_at" not in rendered
    assert "last_edited_at" not in rendered


def test_related_non_state_document_surfaces_initiative_but_state_and_raw_output_do_not(tmp_path: Path) -> None:
    old = NOW - timedelta(days=1)
    related = tmp_path / ".megaplan" / "initiatives" / "knowledge-model"
    readme = _write_document(related / "README.md", created_at=old, edited_at=old)
    readme.write_text(
        "---\n"
        f"created_at: {_timestamp(old)}\n"
        f"last_edited_at: {_timestamp(old)}\n"
        "---\n\n"
        "# Knowledge Model\n\nCanonical resident knowledge lifecycle.\n",
        encoding="utf-8",
    )
    _set_mtime(readme, old)
    decision = _write_document(
        related / "decisions" / "lifecycle.md",
        created_at=old,
        edited_at=NOW - timedelta(minutes=10),
    )
    _set_mtime(decision, old)

    state_only = tmp_path / ".megaplan" / "initiatives" / "state-only"
    state_readme = _write_document(state_only / "README.md", created_at=old, edited_at=old)
    state_readme.write_text(
        "---\n"
        f"created_at: {_timestamp(old)}\n"
        f"last_edited_at: {_timestamp(old)}\n"
        "---\n\n# State Only\n\nOnly runtime state changed.\n",
        encoding="utf-8",
    )
    _set_mtime(state_readme, old)
    chain = state_only / "chain.yaml"
    chain.write_text("milestones: []\n", encoding="utf-8")
    _set_mtime(chain, NOW - timedelta(minutes=1))
    raw = _write_document(
        state_only / "handoff" / "subagent-results" / "raw.txt",
        edited_at=NOW - timedelta(minutes=1),
    )
    churn = _write_document(
        state_only / "notes" / "wait-log.md",
        edited_at=NOW - timedelta(minutes=1),
    )

    context = build_knowledge_context(tmp_path, now=NOW)

    assert _names(context, "documents_added_or_edited") == [
        ".megaplan/initiatives/knowledge-model/decisions/lifecycle.md"
    ]
    assert _names(context, "initiatives_added_or_edited") == ["Knowledge Model"]
    assert not is_durable_document_path(chain, tmp_path)
    assert not is_durable_document_path(raw, tmp_path)
    assert not is_durable_document_path(churn, tmp_path)


def test_document_bounds_order_and_omitted_count_are_deterministic(tmp_path: Path) -> None:
    docs: list[Path] = []
    for index in range(6):
        path = _write_document(
            tmp_path / "docs" / f"doc-{index}.md",
            created_at=NOW - timedelta(days=1),
            edited_at=NOW - timedelta(minutes=index + 1),
        )
        _set_mtime(path, NOW - timedelta(days=1))
        docs.append(path)

    context = build_knowledge_context(tmp_path, now=NOW, limit=3)
    bucket = context.recent_activity["documents_added_or_edited"]

    assert bucket == {
        "label": "Documents added or edited in the preceding rolling hour",
        "names": ["docs/doc-0.md", "docs/doc-1.md", "docs/doc-2.md"],
        "omitted_count": 3,
    }
    assert [row["path"] for row in context.documents] == sorted(
        path.relative_to(tmp_path).as_posix() for path in docs
    )


def test_multiple_recent_documents_surface_the_related_initiative_once(tmp_path: Path) -> None:
    old = NOW - timedelta(days=1)
    initiative = tmp_path / ".megaplan" / "initiatives" / "one-owner"
    readme = _write_document(initiative / "README.md")
    readme.write_text("# One Owner\n\nOne coherent outcome.\n", encoding="utf-8")
    _set_mtime(readme, old)
    for name in ("first.md", "second.md"):
        document = _write_document(
            initiative / "research" / name,
            created_at=old,
            edited_at=NOW - timedelta(minutes=5),
        )
        _set_mtime(document, old)

    context = build_knowledge_context(tmp_path, now=NOW)

    assert _names(context, "initiatives_added_or_edited") == ["One Owner"]
    assert len(_names(context, "documents_added_or_edited")) == 2


def test_initiative_rollup_exposes_precise_document_cause_without_claiming_frontdoor_edit(
    tmp_path: Path,
) -> None:
    old = NOW - timedelta(days=1)
    initiative = tmp_path / ".megaplan" / "initiatives" / "causal-owner"
    readme = _write_document(initiative / "README.md")
    readme.write_text("# Causal Owner\n\nCommitted outcome.\n", encoding="utf-8")
    _set_mtime(readme, old)
    cause = _write_document(
        initiative / "research" / "finding.md",
        created_at=old,
        edited_at=NOW - timedelta(minutes=4),
    )
    _set_mtime(cause, old)

    context = build_knowledge_context(tmp_path, now=NOW)
    compatibility = context.recent_activity["initiatives_added_or_edited"]
    causal = context.recent_activity["initiative_document_causes"]

    assert compatibility["names"] == ["Causal Owner"]
    assert "not evidence that an initiative front-door" in compatibility["label"]
    assert causal["items"] == [
        {
            "initiative_slug": "causal-owner",
            "initiative_name": "Causal Owner",
            "initiative_path": ".megaplan/initiatives/causal-owner",
            "caused_by_recent_document_events": [
                {
                    "document_path": ".megaplan/initiatives/causal-owner/research/finding.md",
                    "evidence_source": "document_frontmatter",
                    "change": "edited",
                    "occurred_at": "2026-07-15T11:56:00Z",
                    "recommended_next_action": (
                        "Open this document and inspect its recorded recent change."
                    ),
                }
            ],
            "causal_documents_omitted_count": 0,
        }
    ]
    assert "README.md" not in json.dumps(causal["items"])
    root = build_context_root(
        status={},
        agents={},
        initiatives=[],
        todos={},
        runtime={},
        conversation={},
        recent_activity=context.recent_activity,
    )
    rendered_event = root["recent_knowledge_activity"]["initiative_document_causes"][
        "items"
    ][0]["caused_by_recent_document_events"][0]
    assert rendered_event["document_path"].endswith("research/finding.md")


def test_git_causal_events_report_authoritative_added_edited_commit_evidence(
    tmp_path: Path,
) -> None:
    subprocess.run(("git", "init", "-q"), cwd=tmp_path, check=True)
    subprocess.run(("git", "config", "user.email", "tests@example.com"), cwd=tmp_path, check=True)
    subprocess.run(("git", "config", "user.name", "Tests"), cwd=tmp_path, check=True)
    initiative = tmp_path / ".megaplan" / "initiatives" / "git-owner"
    readme = _write_document(initiative / "README.md")
    readme.write_text("# Git Owner\n\nCommitted outcome.\n", encoding="utf-8")
    edited = _write_document(initiative / "research" / "edited.md")
    subprocess.run(("git", "add", "."), cwd=tmp_path, check=True)
    old_environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-07-13T12:00:00Z",
        "GIT_COMMITTER_DATE": "2026-07-13T12:00:00Z",
    }
    subprocess.run(
        ("git", "commit", "-q", "-m", "old initiative"),
        cwd=tmp_path,
        check=True,
        env=old_environment,
    )

    edited.write_text("# edited\n\nChanged.\n", encoding="utf-8")
    added = _write_document(initiative / "decisions" / "added.md")
    subprocess.run(("git", "add", "."), cwd=tmp_path, check=True)
    recent_environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-07-15T11:55:00Z",
        "GIT_COMMITTER_DATE": "2026-07-15T11:55:00Z",
    }
    subprocess.run(
        ("git", "commit", "-q", "-m", "recent documents"),
        cwd=tmp_path,
        check=True,
        env=recent_environment,
    )
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    context = build_knowledge_context(tmp_path, now=NOW)
    events = context.recent_activity["initiative_document_causes"]["items"][0][
        "caused_by_recent_document_events"
    ]
    by_path = {event["document_path"]: event for event in events}

    assert by_path[added.relative_to(tmp_path).as_posix()]["change"] == "added"
    assert by_path[edited.relative_to(tmp_path).as_posix()]["change"] == "edited"
    assert {event["commit"] for event in events} == {commit}
    assert {event["occurred_at"] for event in events} == {"2026-07-15T11:55:00Z"}


def test_causal_document_caps_and_omitted_counts_are_enforced(tmp_path: Path) -> None:
    old = NOW - timedelta(days=1)
    for initiative_index in range(4):
        initiative = tmp_path / ".megaplan" / "initiatives" / f"owner-{initiative_index}"
        readme = _write_document(initiative / "README.md")
        readme.write_text(
            f"# Owner {initiative_index}\n\nCommitted outcome.\n", encoding="utf-8"
        )
        _set_mtime(readme, old)
        for document_index in range(4):
            document = _write_document(
                initiative / "research" / f"doc-{document_index}.md",
                edited_at=NOW - timedelta(minutes=document_index + 1),
            )
            _set_mtime(document, old)

    causal = build_knowledge_context(tmp_path, now=NOW).recent_activity[
        "initiative_document_causes"
    ]

    assert causal["per_initiative_document_limit"] == CAUSAL_DOCUMENTS_PER_INITIATIVE_LIMIT == 3
    assert causal["overall_document_limit"] == CAUSAL_DOCUMENTS_OVERALL_LIMIT == 8
    assert causal["document_pointers_included_count"] == 8
    assert causal["causal_document_pointers_omitted_count"] == 8
    assert [len(item["caused_by_recent_document_events"]) for item in causal["items"]] == [2, 2, 2, 2]
    assert [item["causal_documents_omitted_count"] for item in causal["items"]] == [2, 2, 2, 2]


def test_causal_overall_cap_reports_omitted_initiatives_and_their_documents(
    tmp_path: Path,
) -> None:
    old = NOW - timedelta(days=1)
    for index in range(10):
        initiative = tmp_path / ".megaplan" / "initiatives" / f"many-{index}"
        readme = _write_document(initiative / "README.md")
        readme.write_text(f"# Many {index}\n\nCommitted outcome.\n", encoding="utf-8")
        _set_mtime(readme, old)
        document = _write_document(
            initiative / "research" / "cause.md",
            edited_at=NOW - timedelta(minutes=index + 1),
        )
        _set_mtime(document, old)

    context = build_knowledge_context(tmp_path, now=NOW, limit=20)
    compatibility = context.recent_activity["initiatives_added_or_edited"]
    causal = context.recent_activity["initiative_document_causes"]

    assert len(compatibility["names"]) == 8
    assert compatibility["omitted_count"] == 2
    assert len(causal["items"]) == 8
    assert causal["initiatives_omitted_count"] == 2
    assert causal["document_pointers_included_count"] == 8
    assert causal["causal_document_pointers_omitted_count"] == 2


def test_per_initiative_cap_and_incomplete_metadata_fallback_do_not_fabricate_evidence(
    tmp_path: Path,
) -> None:
    old = NOW - timedelta(days=1)
    initiative = tmp_path / ".megaplan" / "initiatives" / "fallback-owner"
    readme = _write_document(initiative / "README.md")
    readme.write_text("# Fallback Owner\n\nCommitted outcome.\n", encoding="utf-8")
    _set_mtime(readme, old)
    for index in range(5):
        document = _write_document(initiative / "notes" / f"note-{index}.md")
        _set_mtime(document, NOW - timedelta(minutes=index + 1))

    causal = build_knowledge_context(tmp_path, now=NOW).recent_activity[
        "initiative_document_causes"
    ]
    item = causal["items"][0]
    rendered = json.dumps(causal)

    assert len(item["caused_by_recent_document_events"]) == 3
    assert item["causal_documents_omitted_count"] == 2
    assert causal["causal_document_pointers_omitted_count"] == 2
    for event in item["caused_by_recent_document_events"]:
        assert event["evidence_source"] == "filesystem_mtime"
        assert "change" not in event
        assert "occurred_at" not in event
        assert "commit" not in event
        assert event["document_path"].startswith(
            ".megaplan/initiatives/fallback-owner/notes/"
        )
    assert "line_count" not in rendered
    assert "line count" not in rendered.casefold()
    assert "summary" not in rendered.casefold()


def test_git_tracked_checkout_mtime_is_not_activity_but_dirty_added_and_edited_files_are(tmp_path: Path) -> None:
    subprocess.run(("git", "init", "-q"), cwd=tmp_path, check=True)
    subprocess.run(("git", "config", "user.email", "tests@example.com"), cwd=tmp_path, check=True)
    subprocess.run(("git", "config", "user.name", "Tests"), cwd=tmp_path, check=True)
    tracked = _write_document(tmp_path / "docs" / "tracked.md")
    subprocess.run(("git", "add", "docs/tracked.md"), cwd=tmp_path, check=True)
    old_environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-07-13T12:00:00Z",
        "GIT_COMMITTER_DATE": "2026-07-13T12:00:00Z",
    }
    subprocess.run(
        ("git", "commit", "-q", "-m", "old document"),
        cwd=tmp_path,
        check=True,
        env=old_environment,
    )
    _set_mtime(tracked, NOW - timedelta(minutes=5))

    clean_context = build_knowledge_context(tmp_path, now=NOW)
    assert _names(clean_context, "documents_added_or_edited") == []

    tracked.write_text("# tracked\n\nEdited.\n", encoding="utf-8")
    _set_mtime(tracked, NOW - timedelta(minutes=4))
    added = _write_document(tmp_path / "docs" / "added.md")
    _set_mtime(added, NOW - timedelta(minutes=2))

    dirty_context = build_knowledge_context(tmp_path, now=NOW)
    assert _names(dirty_context, "documents_added_or_edited") == [
        "docs/added.md",
        "docs/tracked.md",
    ]


def test_hot_lifecycle_labels_and_routes_make_categories_and_navigation_explicit() -> None:
    root = build_context_root(
        status={},
        agents={},
        initiatives=[],
        todos={},
        runtime={},
        conversation={},
        knowledge_lifecycle=KNOWLEDGE_LIFECYCLE,
        recent_activity={},
    )
    categories = root["knowledge_lifecycle"]["categories"]

    assert "not execution approval" in categories["document"]["label"]
    assert "not yet a coordinated plan" in categories["ticket"]["label"]
    assert "committed coherent outcome" in categories["initiative"]["label"]
    assert "Search rough slug, title, and description first" in categories["initiative"]["create_or_update"]
    assert "bounded recent orientation, not the database" in root["knowledge_lifecycle"]["reuse_and_navigation"]
    assert {row["node_id"] for row in root["routes"]} >= {"tickets", "initiatives", "documents", "policies"}
    assert len(json.dumps(root)) < 10_000
    assert "README.md is the current truth/front door" in POLICY_PACKS["initiatives"]
    assert "Curate subagent findings" in POLICY_PACKS["initiatives"]
